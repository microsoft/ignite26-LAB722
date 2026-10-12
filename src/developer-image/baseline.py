import argparse
import asyncio
import json
import os
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

from data.pipeline.contracts import FIXTURE_WARNING, LIMITATIONS
from data.pipeline.validate_dataset import file_sha256, validate_artifact
from src.workers.frozen_contract import (
    PUBLIC_PURPOSE, SYNTHETIC_PURPOSE, acceptance_selection, load_public_sources, public_identity,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "src" / "research-portal" / "backend"
FRONTEND = ROOT / "src" / "research-portal" / "frontend"
MANIFEST_PATH = ROOT / "data" / "artifacts" / "development" / "data-manifest.json"
BASELINE_PATH = ROOT / "prepared-baseline.json"
EDITABLE_MODULES = {
    "clinical-trials": "src/research-portal/backend/trial_feature.py",
    "drug-safety": "src/research-portal/backend/safety_feature.py",
}


class BuiltAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "link" and attributes.get("rel") == "icon" and attributes.get("href") == "data:,":
            return
        for name, value in attrs:
            if tag in {"script", "link"} and name in {"src", "href"} and value:
                if not value.startswith("/assets/"):
                    raise ValueError("The built frontend must use local bundled assets.")
                self.paths.append(value[1:])


def toolchains() -> dict[str, str]:
    if sys.version_info[:2] != (3, 13):
        raise ValueError("The prepared toolchain must use Python 3.13.")
    node = subprocess.check_output(["node", "--version"], text=True).strip()
    if not node.startswith("v24."):
        raise ValueError("The prepared toolchain must use Node 24.")
    return {"python": sys.version.split()[0], "node": node}


def protected_files() -> dict[str, str]:
    paths = {
        ROOT / "tests" / "test_research.py",
        ROOT / "tests" / "test_frozen_public_research.py",
        ROOT / "src" / "workers" / "frozen_contract.py",
        ROOT / "src" / "developer-image" / "baseline.py",
        ROOT / "data" / "fixtures" / "research-data.json",
        ROOT / "data" / "pipeline" / "requirements.txt",
        BACKEND / "requirements.txt",
        ROOT / "src" / "research-portal" / "Containerfile",
        FRONTEND / "package.json",
        FRONTEND / "package-lock.json",
        FRONTEND / "tsconfig.json",
        FRONTEND / "index.html",
        MANIFEST_PATH,
    }
    paths.update((ROOT / "data" / "pipeline").glob("*.py"))
    paths.update(BACKEND.glob("*.py"))
    paths.update((ROOT / "src" / "workers" / "starter").glob("*.py"))
    paths.update(path for path in (FRONTEND / "src").rglob("*") if path.is_file())
    paths.update(path for path in (FRONTEND / "dist").rglob("*") if path.is_file())
    paths.update(MANIFEST_PATH.parent.glob("*.duckdb"))
    manifest = json.loads(MANIFEST_PATH.read_bytes())
    for field in ("source_records", "pipeline_source"):
        if manifest.get(field) is not None:
            paths.add(MANIFEST_PATH.parent / manifest[field]["path"])
    excluded = {ROOT / path for path in EDITABLE_MODULES.values()}
    return {
        path.relative_to(ROOT).as_posix(): file_sha256(path)
        for path in sorted(paths - excluded)
    }


def check_data_contract():
    manifest = validate_artifact(MANIFEST_PATH)
    raw = json.loads(MANIFEST_PATH.read_bytes())
    purpose = os.environ.get("CALDOVA_ACCEPTANCE_PURPOSE", SYNTHETIC_PURPOSE)
    acceptance_selection(raw, purpose)
    if purpose == PUBLIC_PURPOSE:
        if file_sha256(MANIFEST_PATH) != os.environ.get("CALDOVA_DATA_MANIFEST_SHA256"):
            raise ValueError("Public baseline requires its explicit frozen manifest trust anchor.")
        load_public_sources(MANIFEST_PATH.parent, raw, ROOT)
    return manifest, raw, purpose


def record_baseline(source_revision: str) -> None:
    if BASELINE_PATH.exists():
        raise FileExistsError("Refusing to replace the prepared baseline trust record.")
    manifest, raw, purpose = check_data_contract()
    record = {
        "schema_version": "1.0",
        "source_revision": source_revision,
        "toolchains": toolchains(),
        "dataset_version": manifest.dataset_version,
        "dataset_kind": manifest.dataset_kind,
        "database_sha256": manifest.database.sha256,
        "data_manifest_sha256": file_sha256(MANIFEST_PATH),
        "editable_modules": EDITABLE_MODULES,
        "protected_files": protected_files(),
    }
    if purpose == PUBLIC_PURPOSE:
        record.update(acceptance_purpose=purpose, public_identity=public_identity(raw))
    BASELINE_PATH.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_baseline() -> dict:
    record = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    manifest, raw, purpose = check_data_contract()
    if (
        record["dataset_kind"] != manifest.dataset_kind or record["dataset_version"] != manifest.dataset_version
        or record["database_sha256"] != manifest.database.sha256
        or record["data_manifest_sha256"] != file_sha256(MANIFEST_PATH)
        or record.get("acceptance_purpose", SYNTHETIC_PURPOSE) != purpose
        or (purpose == PUBLIC_PURPOSE and record.get("public_identity") != public_identity(raw))
    ):
        raise ValueError("The prepared baseline frozen dataset or source-use identity changed.")
    if record["protected_files"] != protected_files():
        raise ValueError("A trusted source, test, frontend asset or frozen data file has changed.")
    if record["toolchains"] != toolchains() or record["editable_modules"] != EDITABLE_MODULES:
        raise ValueError("The prepared toolchain or worker file boundary has changed.")
    parser = BuiltAssets()
    parser.feed((FRONTEND / "dist" / "index.html").read_text(encoding="utf-8"))
    if not parser.paths or not all((FRONTEND / "dist" / path).is_file() for path in parser.paths):
        raise ValueError("The frontend has not been built with its local asset bundle.")
    if not (FRONTEND / "node_modules" / "typescript" / "bin" / "tsc").is_file():
        raise ValueError("The prepared frontend dependencies are missing.")
    for path in EDITABLE_MODULES.values():
        active = ROOT / path
        starter = ROOT / "src" / "workers" / "starter" / active.name
        if file_sha256(active) != file_sha256(starter):
            raise ValueError(f"The prepared feature must contain its checked-in starter: {active.name}")
        if not os.access(active, os.W_OK):
            raise ValueError(f"The worker feature slot is not writable: {active.name}")
    if os.geteuid() == 0:
        raise ValueError("Baseline verification must run as a non-root user.")
    for path in record["protected_files"]:
        protected = ROOT / path
        if os.access(protected, os.W_OK) or os.access(protected.parent, os.W_OK):
            raise ValueError(f"A trusted source, test or data file is writable: {path}")
    sys.path.insert(0, str(BACKEND))
    import app as portal
    from safety_feature import query_safety_reports
    from trial_feature import query_trials

    def require_missing(function, *args):
        try:
            function(*args)
        except NotImplementedError:
            return
        raise ValueError("A starter feature unexpectedly contains a working query implementation.")

    with portal.duckdb.connect(
        str(MANIFEST_PATH.parent / manifest.database.path),
        read_only=True,
        config={"enable_external_access": False},
    ) as connection:
        candidates = [row[0] for row in connection.execute(
            "SELECT candidate_id FROM candidates ORDER BY candidate_id"
        ).fetchall()]
        if not candidates:
            raise ValueError("The prepared baseline has no frozen candidates.")
        for candidate in candidates:
            for condition in (None, "obesity", "type-2-diabetes"):
                require_missing(query_trials, connection, candidate, condition)
            require_missing(query_safety_reports, connection, candidate)

    async def check_portal():
        os.environ["CALDOVA_PREVIEW_STATE"] = "reference"
        async with portal.lifespan(portal.app):
            for candidate in candidates:
                portal.app.state.preview_state = "reference"
                require_missing(portal.research, candidate, "obesity")
                portal.app.state.preview_state = "starter"
                response = portal.research(candidate, "obesity")
                if (
                    response.status != "unavailable" or response.trials or response.safety_reports
                    or response.fixture_warning != (FIXTURE_WARNING if purpose == SYNTHETIC_PURPOSE else None)
                    or response.limitations != LIMITATIONS
                ):
                    raise ValueError("The visual baseline lost its unavailable state or responsible-use text.")

    asyncio.run(check_portal())
    receipt = {
        "dataset_version": manifest.dataset_version,
        "dataset_kind": manifest.dataset_kind,
        "database_sha256": manifest.database.sha256,
        "data_manifest_sha256": file_sha256(MANIFEST_PATH),
        "baseline_manifest_sha256": file_sha256(BASELINE_PATH),
        "source_revision": record["source_revision"],
        "toolchains": record["toolchains"],
        "frontend_assets": len(parser.paths),
        "missing_feature_modules": list(EDITABLE_MODULES.values()),
        "reference_state": "NotImplementedError",
        "trusted_tests": "read-only",
    }
    if purpose == PUBLIC_PURPOSE:
        receipt.update(acceptance_purpose=purpose, **public_identity(raw))
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description="Record or verify the frozen, genuinely incomplete baseline.")
    parser.add_argument("--record", action="store_true")
    parser.add_argument("--source-revision", default="uncommitted-development")
    args = parser.parse_args()
    if args.record:
        record_baseline(args.source_revision)
    else:
        print("BASELINE_VERIFIED " + json.dumps(verify_baseline(), sort_keys=True))


if __name__ == "__main__":
    main()
