"""Offline ownership tests. Injected fake hashes DO NOT prove live authentication."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import hashlib
import hmac
from pathlib import Path
import secrets
import shutil
import sqlite3
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from reactor.ownership import (
    ACCOUNTS, AccessDenied, CapacityExceeded, Conflict, OwnershipStore,
    Principal, StateUnavailable,
)


class FakePasswordHelper:
    """Dependency-isolation fake only; deliberately NOT a password KDF."""

    def hash(self, password: str) -> str:
        return "TEST-ONLY:" + hashlib.sha256(password.encode()).hexdigest()

    def verify(self, password: str, hash: str) -> bool:
        return hmac.compare_digest(self.hash(password), hash)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        # Scratch lives inside the project, never an OS temporary directory.
        self.directory = Path(__file__).resolve().parent / (".reactor-test-" + secrets.token_hex(12))
        self.directory.mkdir()
        self.addCleanup(shutil.rmtree, self.directory)
        self.path = self.directory / "state.sqlite"
        self.now = 1000.0
        self.helper = FakePasswordHelper()
        self.store = self.open(create=True)
        self.passwords = {
            "REACTOR_ALICE_PASSWORD": secrets.token_urlsafe(24),
            "REACTOR_BOB_PASSWORD": secrets.token_urlsafe(24),
        }
        self.store.seed_from_env(self.passwords)
        self.alice = self.store.authenticate("alice", self.passwords["REACTOR_ALICE_PASSWORD"])
        self.bob = self.store.authenticate("bob", self.passwords["REACTOR_BOB_PASSWORD"])

    def open(self, **kwargs):
        return OwnershipStore(self.path, password_helper=self.helper, clock=lambda: self.now, **kwargs)

    @staticmethod
    def ids(run):
        return {key: getattr(run, key) for key in
                ("run_id", "user_id", "customer_id", "conversation_id")}

    def execute(self, owner, key, *, success=True):
        run = self.store.create_run(owner, key, {"task": "frozen-public-check"})
        token = self.store.issue_grant(owner, run.run_id, "execute")
        execution = self.store.start_execution(token, **self.ids(run))
        bound = self.store.bind_sandbox(token, execution.run, "sandbox-" + secrets.token_hex(12))
        finished = self.store.finish_execution(token, bound, success=success,
                                               artifacts={"answer": {"count": 3}})
        return finished, self.store.list_artifacts(owner, run.run_id)[0][0]

    def test_accounts_require_explicit_passwords_and_persist_hashes(self):
        self.assertEqual((self.alice, self.bob), ACCOUNTS)
        with self.assertRaises(Conflict):
            self.store.seed_from_env({})
        same = secrets.token_urlsafe(24)
        with self.assertRaises(Conflict):
            self.store.seed_from_env(dict.fromkeys(self.passwords, same))
        for username in ("alice", "bob", "unknown"):
            with self.subTest(username=username), self.assertRaises(AccessDenied):
                self.store.authenticate(username, secrets.token_urlsafe(24))
        with closing(sqlite3.connect(self.path)) as db:
            hashes = [r[0] for r in db.execute("SELECT password_hash FROM accounts")]
        for password in self.passwords.values():
            self.assertNotIn(password, self.path.read_bytes().decode(errors="ignore"))
        self.assertTrue(all(value.startswith("TEST-ONLY:") for value in hashes))
        reopened = self.open()
        self.assertEqual(reopened.authenticate("alice", self.passwords["REACTOR_ALICE_PASSWORD"]), self.alice)

    def test_allowed_both_users_and_swapped_run_result_conversation_denied(self):
        alice_run, alice_result = self.execute(self.alice, "alice")
        bob_run, bob_result = self.execute(self.bob, "bob", success=False)
        self.assertEqual(alice_run.state, "completed")
        self.assertEqual(bob_run.state, "failed")
        for owner, own, own_result, foreign, foreign_result in (
            (self.alice, alice_run, alice_result, bob_run, bob_result),
            (self.bob, bob_run, bob_result, alice_run, alice_result),
        ):
            with self.subTest(owner=owner.username):
                self.assertEqual(self.store.get_artifact(owner, own.run_id, own_result), {"count": 3})
                self.assertEqual(self.store.get_conversation(owner, own.run_id, own.conversation_id), own)
                with self.assertRaises(AccessDenied):
                    self.store.get_run(owner, foreign.run_id)
                with self.assertRaises(AccessDenied):
                    self.store.get_conversation(owner, own.run_id, foreign.conversation_id)
                with self.assertRaises(AccessDenied):
                    self.store.get_artifact(owner, own.run_id, foreign_result)
                with self.assertRaises(AccessDenied):
                    self.store.get_artifact(owner, foreign.run_id, foreign_result)
                with self.assertRaises(AccessDenied):
                    self.store.cancel_run(owner, foreign.run_id)
                with self.assertRaises(AccessDenied):
                    self.store.acknowledge_cleanup(owner, foreign.run_id, sandbox_id=foreign.sandbox_id)

    def test_owned_ids_notes_and_platform_bindings_ignore_forged_metadata(self):
        alice = self.store.create_run(self.alice, "same-key", {
            "user_id": self.bob.user_id, "customer_id": self.bob.customer_id,
            "conversation_id": "model-selected", "run_id": "model-selected",
        })
        bob = self.store.create_run(self.bob, "same-key", {})
        self.assertEqual(alice.user_id, self.alice.user_id)
        self.assertNotEqual(alice.run_id, "model-selected")
        self.assertNotEqual(alice.conversation_id, "model-selected")
        self.store.bind_foundry_session(self.alice, alice.run_id, "platform-created-session")
        self.store.bind_foundry_session(self.alice, alice.run_id, "platform-created-session")
        with self.assertRaises(AccessDenied):
            self.store.bind_foundry_session(self.bob, bob.run_id, "platform-created-session")
        with self.assertRaises(Conflict):
            self.store.bind_foundry_session(self.alice, alice.run_id, "other-session")
        forged = Principal(self.alice.user_id, self.bob.customer_id, self.alice.username)
        with self.assertRaises(AccessDenied):
            self.store.get_run(forged, alice.run_id)
        for owner, run in ((self.alice, alice), (self.bob, bob)):
            token = self.store.issue_grant(owner, run.run_id, "execute")
            execution = self.store.start_execution(token, **self.ids(run))
            self.assertIn(owner.username, execution.customer_note)
            other = self.bob if owner == self.alice else self.alice
            self.assertNotIn(other.username, execution.customer_note)
            self.assertNotIn(token.value, repr(token))
            self.assertNotIn(execution.customer_note, repr(execution))

    def test_grants_expire_tamper_and_reject_every_swapped_binding(self):
        alice = self.store.create_run(self.alice, "alice", {})
        bob = self.store.create_run(self.bob, "bob", {})
        for owner, own, foreign in ((self.alice, alice, bob), (self.bob, bob, alice)):
            token = self.store.issue_grant(owner, own.run_id, "execute", ttl_seconds=10)
            self.assertEqual(self.store.verify_grant(token, **self.ids(own), permission="execute"), own)
            for field in self.ids(own):
                with self.subTest(owner=owner.username, field=field), self.assertRaises(AccessDenied):
                    ids = self.ids(own)
                    ids[field] = getattr(foreign, field)
                    self.store.start_execution(token, **ids, lease_seconds=5)
            with self.assertRaises(AccessDenied):
                self.store.verify_grant(token, **self.ids(own), permission="read")
            tampered = ("A" if token.value[0] != "A" else "B") + token.value[1:]
            with self.assertRaises(AccessDenied):
                self.store.start_execution(tampered, **self.ids(own), lease_seconds=5)
            self.assertNotIn(token.value, self.path.read_bytes().decode(errors="ignore"))
        self.now += 10
        with self.assertRaises(AccessDenied):
            self.store.start_execution(token, **self.ids(bob), lease_seconds=1)
        with self.assertRaises(AccessDenied):
            self.store.start_execution(secrets.token_urlsafe(32), **self.ids(alice))

    def test_idempotency_capacity_and_scoped_cleanup(self):
        alice = self.store.create_run(self.alice, "key", {"a": 1, "b": 2})
        self.assertEqual(self.store.create_run(self.alice, "key", {"b": 2, "a": 1}), alice)
        with self.assertRaises(Conflict):
            self.store.create_run(self.alice, "key", {"a": 2})
        bob = self.store.create_run(self.bob, "key", {})
        with self.assertRaises(CapacityExceeded):
            self.store.create_run(self.alice, "new", {})
        cancelled = self.store.cancel_run(self.alice, alice.run_id)
        self.assertEqual(cancelled.state, "cancelled")
        with self.assertRaises(CapacityExceeded):
            self.store.create_run(self.alice, "new", {})
        self.store.acknowledge_cleanup(self.alice, alice.run_id, sandbox_id=None)
        self.assertEqual(self.store.get_run(self.bob, bob.run_id), bob)
        self.store.create_run(self.alice, "new", {})
        tombstone = self.store.create_run(self.alice, "key", {"a": 1, "b": 2})
        self.assertTrue(tombstone.cleaned)
        self.assertEqual(tombstone.state, "cancelled")

    def test_transactional_concurrent_creation_and_single_execution_claim(self):
        barrier = threading.Barrier(2)
        def create(key):
            store = self.open()
            barrier.wait()
            try:
                return store.create_run(self.alice, key, {})
            except CapacityExceeded:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create, ("a", "b")))
        run = next(r for r in outcomes if r is not None)
        self.assertEqual(sum(r is not None for r in outcomes), 1)
        token = self.store.issue_grant(self.alice, run.run_id, "execute")
        barrier = threading.Barrier(2)
        def start(_):
            store = self.open()
            barrier.wait()
            try:
                return store.start_execution(token, **self.ids(run))
            except Conflict:
                return None
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(start, (0, 1)))
        self.assertEqual(sum(c is not None for c in claims), 1)

    def test_global_capacity_and_concurrent_idempotent_creation(self):
        limited = OwnershipStore(self.directory / "limited.sqlite", create=True,
                                 password_helper=self.helper, capacity=1)
        limited.seed_from_env(self.passwords)
        first = limited.create_run(self.alice, "a", {})
        with self.assertRaises(CapacityExceeded):
            limited.create_run(self.bob, "b", {})
        limited.cancel_run(self.alice, first.run_id)
        limited.acknowledge_cleanup(self.alice, first.run_id, sandbox_id=None)
        self.assertEqual(limited.create_run(self.bob, "b", {}).user_id, self.bob.user_id)
        barrier = threading.Barrier(2)
        def create(_):
            store = self.open()
            barrier.wait()
            return store.create_run(self.alice, "concurrent-retry", {"a": 1})
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = pool.map(create, (0, 1))
        self.assertEqual(first, second)

    def test_execution_fencing_and_sandbox_association_cannot_be_swapped(self):
        alice = self.store.create_run(self.alice, "a", {})
        bob = self.store.create_run(self.bob, "b", {})
        alice_token = self.store.issue_grant(self.alice, alice.run_id, "execute")
        bob_token = self.store.issue_grant(self.bob, bob.run_id, "execute")
        alice_exec = self.store.start_execution(alice_token, **self.ids(alice))
        bob_exec = self.store.start_execution(bob_token, **self.ids(bob))
        self.store.bind_sandbox(alice_token, alice_exec.run, "alice-service-sandbox")
        with self.assertRaises(AccessDenied):
            self.store.bind_sandbox(bob_token, bob_exec.run, "alice-service-sandbox")
        with self.assertRaises(Conflict):
            self.store.bind_sandbox(alice_token, alice_exec.run, "replacement-sandbox")
        for token, execution, foreign in (
            (alice_token, alice_exec, bob_exec), (bob_token, bob_exec, alice_exec)
        ):
            with self.assertRaises(AccessDenied):
                self.store.finish_execution(token, foreign.run, success=True, artifacts={})
            stale = replace(execution.run, execution_id=foreign.run.execution_id)
            with self.assertRaises(Conflict):
                self.store.finish_execution(token, stale, success=True, artifacts={})

    def test_restart_stale_execution_and_cancel_fence_late_results(self):
        run = self.store.create_run(self.alice, "a", {})
        token = self.store.issue_grant(self.alice, run.run_id, "execute")
        execution = self.store.start_execution(token, **self.ids(run), lease_seconds=5)
        bound = self.store.bind_sandbox(token, execution.run, "service-created-sandbox")
        reopened = self.open()
        self.assertEqual(reopened.get_run(self.alice, run.run_id), bound)
        with self.assertRaises(Conflict):
            reopened.start_execution(token, **self.ids(run))
        self.now += 5
        with self.assertRaises(Conflict):
            reopened.finish_execution(token, bound, success=True, artifacts={"answer": 3})
        with self.assertRaises(Conflict):
            reopened.acknowledge_cleanup(self.alice, run.run_id, sandbox_id=bound.sandbox_id)
        reopened.cancel_run(self.alice, run.run_id)
        with self.assertRaises(AccessDenied):
            reopened.finish_execution(token, bound, success=True, artifacts={"answer": 3})
        with self.assertRaises(Conflict):
            reopened.acknowledge_cleanup(self.alice, run.run_id, sandbox_id="foreign-sandbox")
        reopened.acknowledge_cleanup(self.alice, run.run_id, sandbox_id=bound.sandbox_id)
        reopened.create_run(self.alice, "explicit-new-retry", {})

    def test_granted_cancel_and_cleanup_delete_only_owned_artifacts(self):
        alice, alice_result = self.execute(self.alice, "a")
        bob, bob_result = self.execute(self.bob, "b")
        token = self.store.issue_grant(self.alice, alice.run_id, "cancel")
        with self.assertRaises(AccessDenied):
            self.store.cancel_with_grant(token, **self.ids(bob))
        self.store.cancel_with_grant(token, **self.ids(alice))
        self.store.acknowledge_cleanup(self.alice, alice.run_id, sandbox_id=alice.sandbox_id,
                                       delete_artifacts=True)
        with self.assertRaises(AccessDenied):
            self.store.get_artifact(self.alice, alice.run_id, alice_result)
        self.assertEqual(self.store.get_artifact(self.bob, bob.run_id, bob_result), {"count": 3})

    def test_missing_or_lost_state_and_inconsistent_capacity_fail_closed(self):
        missing = self.directory / "missing.sqlite"
        with self.assertRaises(StateUnavailable):
            OwnershipStore(missing, password_helper=self.helper)
        self.assertFalse(missing.exists())
        with self.assertRaises(StateUnavailable):
            self.open(capacity=3)
        self.path.unlink()
        with self.assertRaises(StateUnavailable):
            self.store.get_run(self.alice, "any-run")
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
