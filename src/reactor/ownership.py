"""Server-owned demo identity and execution state; no HTTP or cloud dependencies.

Install ``pwdlib[argon2]`` in the runtime manifest. Only dependency-isolation
tests should inject a password helper. The facilitator explicitly creates a
durable SQLite file and seeds REACTOR_ALICE_PASSWORD / REACTOR_BOB_PASSWORD.
Normal app startup opens an existing database, failing closed if it disappeared.
Protect the database/volume with OS permissions; never expose it to generated code.

Principal arguments MUST come from authenticate() or a maintained, validated
server session, never model/browser metadata. Backend service authentication,
session protection, login throttling and grant injection outside model control
belong to the integrating apps. Grants are opaque secrets, not diagnostic IDs.
The execution app is the sole store authority. The front end registers/retrieves
runs through its service-authenticated API; it must not keep a copied SQLite DB.
That API may accept the fixed Principal map only from the permitted front-end
service identity after validated demo login, not from arbitrary service callers.
EmptyDir deployment loses authority on replica replacement: startup must fail
closed, with explicit facilitator reinitialization and abandoned-resource
cleanup. Reinitialized state will not recognize any previous run or grant.

Submission reserves capacity until verified external resource cleanup is
acknowledged. Running executions cannot be resumed/replayed after restart or
lease expiry: cancel, delete the task's Sandbox, acknowledge cleanup, then submit
with a NEW idempotency key. Cancellation fences late writes but does not itself
stop a Sandbox. Cleanup acknowledgement must follow actual resource deletion.
No automatic timeout releases capacity or claims an external task was stopped.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from typing import Callable, Iterator, Literal, Mapping, Protocol
from uuid import uuid4


Permission = Literal["execute", "read", "cancel"]
RunState = Literal["submitted", "running", "completed", "failed", "cancelled"]


class OwnershipError(Exception):
    """Safe generic error; never includes credentials or foreign content."""


class AccessDenied(OwnershipError):
    pass


class Conflict(OwnershipError):
    pass


class CapacityExceeded(OwnershipError):
    pass


class StateUnavailable(OwnershipError):
    pass


class PasswordHelper(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, hash: str) -> bool: ...


@dataclass(frozen=True)
class Principal:
    user_id: str
    customer_id: str
    username: str


@dataclass(frozen=True)
class Run:
    run_id: str
    user_id: str
    customer_id: str
    conversation_id: str
    state: RunState
    foundry_session_id: str | None
    sandbox_id: str | None
    execution_id: str | None
    lease_expires_at: float | None
    cleaned: bool


@dataclass(frozen=True)
class Grant:
    value: str = field(repr=False)
    expires_at: float


@dataclass(frozen=True)
class Execution:
    run: Run
    input_data: dict = field(repr=False)
    customer_note: str = field(repr=False)


ACCOUNTS = (
    Principal("user-alice", "customer-alice", "alice"),
    Principal("user-bob", "customer-bob", "bob"),
)
_PERMISSIONS = {"execute", "read", "cancel"}
_TERMINAL = {"completed", "failed", "cancelled"}
_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
 user_id TEXT PRIMARY KEY, customer_id TEXT NOT NULL UNIQUE,
 username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES accounts(user_id),
 customer_id TEXT NOT NULL, conversation_id TEXT NOT NULL UNIQUE,
 idempotency_key TEXT NOT NULL, input_json TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN
 ('submitted','running','completed','failed','cancelled')),
 foundry_session_id TEXT UNIQUE, sandbox_id TEXT UNIQUE,
 execution_id TEXT UNIQUE, lease_expires_at REAL, cleaned INTEGER NOT NULL DEFAULT 0,
 created_at REAL NOT NULL, UNIQUE(user_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS grants (
 digest TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
 user_id TEXT NOT NULL, customer_id TEXT NOT NULL, conversation_id TEXT NOT NULL,
 permission TEXT NOT NULL, expires_at REAL NOT NULL, consumed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS artifacts (
 artifact_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
 name TEXT NOT NULL, content_json TEXT NOT NULL, UNIQUE(run_id, name)
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _json(value: object) -> str:
    try:
        result = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise Conflict("Input must be finite JSON.") from None
    if len(result.encode("utf-8")) > 262144:
        raise Conflict("JSON exceeds the output/input budget.")
    return result


def _identifier(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise Conflict("Invalid identifier.")
    return value


class OwnershipStore:
    def __init__(
        self, database: str | Path, *, create: bool = False,
        password_helper: PasswordHelper | None = None,
        capacity: int = 2, per_owner_capacity: int = 1,
        clock: Callable[[], float] = time.time,
    ):
        if (type(capacity) is not int or type(per_owner_capacity) is not int
                or not 1 <= per_owner_capacity <= capacity <= 16):
            raise ValueError("Invalid concurrency budget.")
        self.path = Path(database).resolve()
        if str(database) == ":memory:" or not self.path.parent.is_dir():
            raise StateUnavailable("An existing durable state directory is required.")
        if not create and not self.path.is_file():
            raise StateUnavailable("State is missing; facilitator recovery is required.")
        if password_helper is None:
            try:
                from pwdlib import PasswordHash
                password_helper = PasswordHash.recommended()
            except ImportError:
                raise StateUnavailable("Runtime requires pwdlib[argon2].") from None
        self.password_helper = password_helper
        self.clock = clock
        self.capacity = capacity
        self.per_owner_capacity = per_owner_capacity
        with self._connect(create=create) as db:
            if create:
                db.executescript(_SCHEMA)
                db.execute("INSERT OR IGNORE INTO settings VALUES ('version','1')")
                db.commit()
            try:
                version = db.execute(
                    "SELECT value FROM settings WHERE key='version'"
                ).fetchone()
            except sqlite3.Error:
                raise StateUnavailable("Unrecognized state; facilitator recovery required.") from None
            if not version or version[0] != "1":
                raise StateUnavailable("Unrecognized state version.")
        # Match budgets across processes sharing this authority.
        with self._transaction() as db:
            budget = f"{capacity}:{per_owner_capacity}"
            db.execute("INSERT OR IGNORE INTO settings VALUES ('budget',?)", (budget,))
            if db.execute("SELECT value FROM settings WHERE key='budget'").fetchone()[0] != budget:
                raise StateUnavailable("Concurrency budget differs from durable configuration.")

    @contextmanager
    def _connect(self, *, create: bool = False) -> Iterator[sqlite3.Connection]:
        # mode=rw prevents accidentally recreating lost state during a request.
        uri = self.path.as_uri() + ("?mode=rwc" if create else "?mode=rw")
        try:
            db = sqlite3.connect(uri, uri=True, timeout=10)
        except sqlite3.Error:
            raise StateUnavailable("Durable state unavailable.") from None
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        if not self.path.is_file():
            raise StateUnavailable("Durable state was lost; refusing recovery by recreation.")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def seed_from_env(self, env: Mapping[str, str] | None = None) -> None:
        """Facilitator-only; never silently rotates existing account passwords."""
        env = os.environ if env is None else env
        passwords = [env.get(f"REACTOR_{p.username.upper()}_PASSWORD", "") for p in ACCOUNTS]
        if any(len(p) < 12 or len(p) > 1024 for p in passwords) or hmac.compare_digest(*passwords):
            raise Conflict("Supply two different facilitator passwords of 12–1024 characters.")
        hashes = [self.password_helper.hash(p) for p in passwords]
        with self._transaction() as db:
            for principal, password_hash in zip(ACCOUNTS, hashes):
                existing = db.execute("SELECT * FROM accounts WHERE user_id=?",
                                      (principal.user_id,)).fetchone()
                if existing:
                    self._principal(db, principal)
                    continue
                db.execute("INSERT INTO accounts VALUES (?,?,?,?,?)", (
                    principal.user_id, principal.customer_id, principal.username,
                    password_hash, f"Private fictional {principal.username} research marker.",
                ))

    def authenticate(self, username: str, password: str) -> Principal:
        """Authenticate demo credentials; return only server-derived identity."""
        if not isinstance(username, str) or not isinstance(password, str) or len(password) > 1024:
            raise AccessDenied("Invalid credentials.")
        with self._transaction() as db:
            row = db.execute("SELECT * FROM accounts WHERE username=?", (username,)).fetchone()
            if row is None:
                # Perform a maintained hash check even for unknown usernames.
                dummy = self.password_helper.hash(secrets.token_urlsafe(32))
                self.password_helper.verify(password, dummy)
                raise AccessDenied("Invalid credentials.")
            if not self.password_helper.verify(password, row["password_hash"]):
                raise AccessDenied("Invalid credentials.")
            return Principal(row["user_id"], row["customer_id"], row["username"])

    def _principal(self, db: sqlite3.Connection, owner: Principal) -> None:
        if not isinstance(owner, Principal):
            raise AccessDenied("Validated application identity required.")
        row = db.execute("SELECT user_id FROM accounts WHERE user_id=? AND customer_id=? "
                         "AND username=?", (owner.user_id, owner.customer_id, owner.username)).fetchone()
        if row is None:
            raise AccessDenied("Validated application identity required.")

    def _owned(self, db: sqlite3.Connection, owner: Principal, run_id: str) -> sqlite3.Row:
        self._principal(db, owner)
        row = db.execute("SELECT * FROM runs WHERE run_id=? AND user_id=? AND customer_id=?",
                         (run_id, owner.user_id, owner.customer_id)).fetchone()
        if row is None:
            raise AccessDenied("Owned resource not available.")
        return row

    @staticmethod
    def _run(row: sqlite3.Row) -> Run:
        return Run(*(row[k] for k in (
            "run_id", "user_id", "customer_id", "conversation_id", "state",
            "foundry_session_id", "sandbox_id", "execution_id", "lease_expires_at",
        )), cleaned=bool(row["cleaned"]))

    def create_run(self, owner: Principal, idempotency_key: str, input_data: dict) -> Run:
        """Reserve a slot; IDs and notes cannot be selected through input metadata."""
        _identifier(idempotency_key)
        if not isinstance(input_data, dict):
            raise Conflict("Input must be a JSON object.")
        encoded = _json(input_data)
        with self._transaction() as db:
            self._principal(db, owner)
            row = db.execute("SELECT * FROM runs WHERE user_id=? AND idempotency_key=?",
                             (owner.user_id, idempotency_key)).fetchone()
            if row:
                if row["input_json"] != encoded:
                    raise Conflict("Idempotency key was already used for different input.")
                return self._run(row)
            total = db.execute("SELECT COUNT(*) FROM runs WHERE cleaned=0").fetchone()[0]
            own = db.execute("SELECT COUNT(*) FROM runs WHERE cleaned=0 AND user_id=?",
                             (owner.user_id,)).fetchone()[0]
            if total >= self.capacity or own >= self.per_owner_capacity:
                raise CapacityExceeded("Execution capacity is reserved until cleanup.")
            run_id = str(uuid4())
            db.execute("INSERT INTO runs (run_id,user_id,customer_id,conversation_id,"
                       "idempotency_key,input_json,state,created_at) VALUES (?,?,?,?,?,?,?,?)",
                       (run_id, owner.user_id, owner.customer_id, "conversation-" + secrets.token_hex(16),
                        idempotency_key, encoded, "submitted", self.clock()))
            return self._run(self._owned(db, owner, run_id))

    def get_run(self, owner: Principal, run_id: str) -> Run:
        with self._transaction() as db:
            return self._run(self._owned(db, owner, run_id))

    def get_conversation(self, owner: Principal, run_id: str, conversation_id: str) -> Run:
        with self._transaction() as db:
            row = self._owned(db, owner, run_id)
            if row["conversation_id"] != conversation_id:
                raise AccessDenied("Owned conversation not available.")
            return self._run(row)

    def bind_foundry_session(self, owner: Principal, run_id: str, session_id: str) -> Run:
        """Runtime-only: bind the platform-created session, never a model's ID."""
        _identifier(session_id)
        with self._transaction() as db:
            row = self._owned(db, owner, run_id)
            # The real platform session can arrive after the tool has completed
            # and cleaned up; ownership and immutable uniqueness still apply.
            if row["foundry_session_id"] not in (None, session_id):
                raise Conflict("Conversation binding is immutable.")
            try:
                db.execute("UPDATE runs SET foundry_session_id=? WHERE run_id=?", (session_id, run_id))
            except sqlite3.IntegrityError:
                raise AccessDenied("Conversation is already bound.") from None
            return self._run(self._owned(db, owner, run_id))

    def issue_grant(self, owner: Principal, run_id: str, permission: Permission,
                    *, ttl_seconds: int = 300) -> Grant:
        if permission not in _PERMISSIONS or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 900:
            raise Conflict("Invalid permission or grant lifetime.")
        with self._transaction() as db:
            row = self._owned(db, owner, run_id)
            if row["cleaned"] or (permission == "execute" and row["state"] != "submitted"):
                raise Conflict("Run cannot receive this grant.")
            token = secrets.token_urlsafe(32)
            expiry = self.clock() + ttl_seconds
            db.execute("INSERT INTO grants VALUES (?,?,?,?,?,?,?,0)", (
                self._digest(token), run_id, owner.user_id, owner.customer_id,
                row["conversation_id"], permission, expiry,
            ))
            return Grant(token, expiry)

    @staticmethod
    def _digest(token: str | Grant) -> str:
        value = token.value if isinstance(token, Grant) else token
        if not isinstance(value, str) or not 32 <= len(value) <= 128:
            raise AccessDenied("Execution authorization denied.")
        return hashlib.sha256(value.encode()).hexdigest()

    def _authorized(self, db: sqlite3.Connection, token: str | Grant, run_id: str,
                    user_id: str, customer_id: str, conversation_id: str,
                    permission: Permission) -> tuple[sqlite3.Row, sqlite3.Row]:
        grant = db.execute("SELECT * FROM grants WHERE digest=?", (self._digest(token),)).fetchone()
        if (grant is None or grant["expires_at"] <= self.clock()
                or (grant["run_id"], grant["user_id"], grant["customer_id"],
                    grant["conversation_id"], grant["permission"])
                != (run_id, user_id, customer_id, conversation_id, permission)):
            raise AccessDenied("Execution authorization denied.")
        owner = next((p for p in ACCOUNTS if p.user_id == user_id and p.customer_id == customer_id), None)
        row = self._owned(db, owner, run_id)
        if row["cleaned"] or row["conversation_id"] != conversation_id:
            raise AccessDenied("Execution authorization denied.")
        return row, grant

    def verify_grant(self, token: str | Grant, *, run_id: str, user_id: str,
                     customer_id: str, conversation_id: str, permission: Permission) -> Run:
        with self._transaction() as db:
            row, _ = self._authorized(db, token, run_id, user_id, customer_id, conversation_id, permission)
            return self._run(row)

    def start_execution(self, token: str | Grant, *, run_id: str, user_id: str,
                        customer_id: str, conversation_id: str,
                        lease_seconds: int = 240) -> Execution:
        """Service-authenticated execution API calls this once, outside model code."""
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 900:
            raise Conflict("Invalid execution lease.")
        with self._transaction() as db:
            row, grant = self._authorized(db, token, run_id, user_id, customer_id,
                                          conversation_id, "execute")
            if row["state"] != "submitted" or grant["consumed"]:
                raise Conflict("Execution already claimed; do not replay ambiguous work.")
            if self.clock() + lease_seconds > grant["expires_at"]:
                raise Conflict("Execution lease exceeds grant lifetime.")
            db.execute("UPDATE grants SET consumed=1 WHERE digest=?", (grant["digest"],))
            db.execute("UPDATE runs SET state='running',execution_id=?,lease_expires_at=? WHERE run_id=?",
                       ("execution-" + secrets.token_hex(16), self.clock() + lease_seconds, run_id))
            note = db.execute("SELECT note FROM accounts WHERE user_id=?", (user_id,)).fetchone()[0]
            return Execution(self._run(db.execute("SELECT * FROM runs WHERE run_id=?",
                                                 (run_id,)).fetchone()),
                             json.loads(row["input_json"]), note)

    def _active_execution(self, db: sqlite3.Connection, token: str | Grant, run: Run) -> sqlite3.Row:
        row, grant = self._authorized(db, token, run.run_id, run.user_id, run.customer_id,
                                      run.conversation_id, "execute")
        if (not grant["consumed"] or row["state"] != "running"
                or row["execution_id"] != run.execution_id
                or row["lease_expires_at"] <= self.clock()):
            raise Conflict("Execution is stale or ambiguous; cancel and clean up before retry.")
        return row

    def bind_sandbox(self, token: str | Grant, run: Run, sandbox_id: str) -> Run:
        """Bind actual service-created resource; preserve it for scoped cleanup."""
        _identifier(sandbox_id)
        with self._transaction() as db:
            row = self._active_execution(db, token, run)
            if row["sandbox_id"] not in (None, sandbox_id):
                raise Conflict("Sandbox binding is immutable.")
            try:
                db.execute("UPDATE runs SET sandbox_id=? WHERE run_id=?", (sandbox_id, run.run_id))
            except sqlite3.IntegrityError:
                raise AccessDenied("Sandbox is already bound.") from None
            return self._run(db.execute("SELECT * FROM runs WHERE run_id=?", (run.run_id,)).fetchone())

    def finish_execution(self, token: str | Grant, run: Run, *, success: bool,
                         artifacts: Mapping[str, object]) -> Run:
        """Persist bounded JSON artifacts atomically; no filesystem paths are acted on."""
        if type(success) is not bool or len(artifacts) > 8:
            raise Conflict("Invalid completion or artifact budget.")
        encoded = { _identifier(name): _json(value) for name, value in artifacts.items() }
        if sum(len(v.encode()) for v in encoded.values()) > 262144:
            raise Conflict("Artifacts exceed output budget.")
        with self._transaction() as db:
            self._active_execution(db, token, run)
            for name, content in encoded.items():
                db.execute("INSERT INTO artifacts VALUES (?,?,?,?)",
                           ("artifact-" + secrets.token_hex(16), run.run_id, name, content))
            db.execute("UPDATE runs SET state=? WHERE run_id=?",
                       ("completed" if success else "failed", run.run_id))
            db.execute("DELETE FROM grants WHERE run_id=? AND permission='execute'", (run.run_id,))
            return self._run(db.execute("SELECT * FROM runs WHERE run_id=?", (run.run_id,)).fetchone())

    def list_artifacts(self, owner: Principal, run_id: str) -> list[tuple[str, str]]:
        with self._transaction() as db:
            self._owned(db, owner, run_id)
            return [(r["artifact_id"], r["name"]) for r in db.execute(
                "SELECT artifact_id,name FROM artifacts WHERE run_id=? ORDER BY name", (run_id,))]

    def get_artifact(self, owner: Principal, run_id: str, artifact_id: str) -> object:
        with self._transaction() as db:
            self._owned(db, owner, run_id)
            row = db.execute("SELECT content_json FROM artifacts WHERE run_id=? AND artifact_id=?",
                             (run_id, artifact_id)).fetchone()
            if row is None:
                raise AccessDenied("Owned artifact not available.")
            return json.loads(row["content_json"])

    def cancel_run(self, owner: Principal, run_id: str) -> Run:
        with self._transaction() as db:
            row = self._owned(db, owner, run_id)
            if row["state"] not in _TERMINAL:
                db.execute("UPDATE runs SET state='cancelled' WHERE run_id=?", (run_id,))
            db.execute("DELETE FROM grants WHERE run_id=?", (run_id,))
            return self._run(self._owned(db, owner, run_id))

    def cancel_with_grant(self, token: str | Grant, *, run_id: str, user_id: str,
                          customer_id: str, conversation_id: str) -> Run:
        with self._transaction() as db:
            row, _ = self._authorized(db, token, run_id, user_id, customer_id, conversation_id, "cancel")
            if row["state"] not in _TERMINAL:
                db.execute("UPDATE runs SET state='cancelled' WHERE run_id=?", (run_id,))
            db.execute("DELETE FROM grants WHERE run_id=?", (run_id,))
            return self._run(db.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())

    def acknowledge_cleanup(self, owner: Principal, run_id: str, *,
                            sandbox_id: str | None, delete_artifacts: bool = False) -> Run:
        """Trusted app only, AFTER external deletion; retain ownership/idempotency tombstone."""
        with self._transaction() as db:
            row = self._owned(db, owner, run_id)
            if row["state"] not in _TERMINAL or row["sandbox_id"] != sandbox_id:
                raise Conflict("Cleanup requires terminal state and the owned Sandbox binding.")
            if delete_artifacts:
                db.execute("DELETE FROM artifacts WHERE run_id=?", (run_id,))
            db.execute("DELETE FROM grants WHERE run_id=?", (run_id,))
            db.execute("UPDATE runs SET cleaned=1 WHERE run_id=?", (run_id,))
            return self._run(self._owned(db, owner, run_id))
