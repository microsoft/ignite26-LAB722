"""Package accepted feature bytes without importing or executing them on the host."""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.workers.frozen_contract import (
    PUBLIC_IDENTITY_FIELDS, PUBLIC_PURPOSE, SYNTHETIC_PURPOSE, acceptance_selection,
    load_public_sources, public_identity,
)
MODULES = {
    "clinical-trials": "src/research-portal/backend/trial_feature.py",
    "drug-safety": "src/research-portal/backend/safety_feature.py",
}
ROLES = {*MODULES, "quality-governance"}
INTEGRATION_CHECKS = {
    "trial-fixtures", "safety-normalization", "citations", "responsible-use",
    "application-acceptance",
}
EGRESS_CHECKS = {"egress-allowed", "egress-denied"}
WORKER_CHECKS = {f"{role}-feature-contract" for role in ROLES} | {"worker-schema"}
ROLE_CHECKS = {
    "clinical-trials": {"citations", "trial-fixtures"},
    "drug-safety": {"citations", "responsible-use", "safety-normalization"},
    "quality-governance": {
        "application-acceptance", "egress-allowed", "egress-denied", "responsible-use",
        "worker-schema",
    },
}
ROW_COUNTS = {
    "candidates", "trials", "trial_conditions", "trial_candidates", "safety_reports",
    "safety_report_candidates", "safety_reactions", "raw_safety_reports",
}
LIMITATIONS = (
    "Adverse-event reports do not establish causation, incidence rates, or comparative "
    "safety. This lab does not provide treatment recommendations or medical advice."
)
BUILDER_FILES = {
    "src/developer-image/Candidate.Containerfile", "src/developer-image/stage_candidate.py",
}
TRUSTED_FILES = {
    "data/fixtures/research-data.json", "data/pipeline/requirements.txt",
    "data/pipeline/build_dataset.py", "data/pipeline/contracts.py",
    "data/pipeline/stage_dataset.py", "data/pipeline/validate_dataset.py",
    "src/research-portal/Containerfile", "src/research-portal/backend/requirements.txt",
    "src/research-portal/backend/app.py", "src/research-portal/backend/queries.py",
    "src/research-portal/frontend/package.json", "src/research-portal/frontend/package-lock.json",
    "src/research-portal/frontend/tsconfig.json", "src/research-portal/frontend/index.html",
    "tests/test_research.py",
    "tests/test_frozen_public_research.py", "src/workers/frozen_contract.py",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def file_sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value), "Invalid SHA-256.")
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", value),
            "Invalid bounded identifier.")
    return value


def uuid(value):
    require(isinstance(value, str), "UUID must be a string.")
    require(str(UUID(value)) == value and UUID(value).int != 0, "UUID must be canonical and nonzero.")
    return value


def object_fields(value, fields, label):
    require(type(value) is dict and set(value) == set(fields), f"Invalid {label} fields.")


def unique_objects(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON object key.")
        result[key] = value
    return result


def regular_file(path):
    require(path.is_file(), f"Missing regular file: {path.name}")
    for item in (path, *path.parents):
        require(not item.is_symlink() and not item.is_junction(), "Links are not packaging inputs.")
    return path


def read_json(path, limit=1024 * 1024, expected_sha256=None):
    regular_file(path)
    require(path.stat().st_size <= limit, "JSON input exceeds the bounded size.")
    content = path.read_bytes()
    require(len(content) <= limit, "JSON input exceeds the bounded size.")
    if expected_sha256 is not None:
        require(sha256_bytes(content) == digest(expected_sha256), "JSON input SHA-256 mismatch.")
    return json.loads(content.decode("utf-8"), object_pairs_hook=unique_objects,
                      parse_constant=lambda _: require(False, "Non-finite JSON value."))


def relative_path(value):
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*", value),
            "Invalid canonical relative path.")
    require(all(part not in {".", ".."} for part in value.split("/")), "Path traversal is forbidden.")
    return value


def write_json(path, value):
    path.write_bytes((json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def check_manifest(manifest, purpose=SYNTHETIC_PURPOSE):
    fields = {
        "schema_version", "dataset_version", "dataset_kind", "built_at", "pipeline_commit",
        "logical_sha256", "database", "record_counts", "sources", "review", "limitations",
    }
    if manifest.get("dataset_kind") == "reviewed-public":
        fields |= {"source_records", "pipeline_source", "public_extract"}
    object_fields(manifest, fields, "data manifest")
    require(manifest["schema_version"] == "1.0", "Unsupported data manifest schema.")
    identifier(manifest["dataset_version"])
    digest(manifest["logical_sha256"])
    acceptance_selection(manifest, purpose)
    require(manifest["limitations"] == LIMITATIONS, "Responsible-use limitations changed.")
    database = manifest["database"]
    object_fields(database, {"path", "sha256", "bytes"}, "database")
    require(isinstance(database["path"], str) and
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.duckdb", database["path"]),
            "Database must be a canonical DuckDB filename.")
    digest(database["sha256"])
    require(type(database["bytes"]) is int and 0 < database["bytes"] <= 64 * 1024 * 1024,
            "Invalid database byte count.")
    require(type(manifest["record_counts"]) is dict and set(manifest["record_counts"]) == ROW_COUNTS
            and all(type(count) is int and count >= 0 for count in manifest["record_counts"].values()),
            "Invalid record-count contract.")
    require(type(manifest["sources"]) is list and bool(manifest["sources"]),
            "Manifest sources are missing.")


def check_result(result, approved_run_id, descriptor, manifest):
    object_fields(result, {
        "plan", "release_status", "workers", "integration_evidence", "egress_evidence",
        "worker_evidence", "candidate_sources",
    }, "accepted result")
    require(result["release_status"] == "requires-complete-release-evidence-and-human-approval",
            "Result must not claim release approval.")
    plan = result["plan"]
    object_fields(plan, {
        "schema_version", "run_id", "dataset_version", "logical_sha256", "assignments",
        "release_requires_human_approval", "limitations",
    }, "plan")
    require(plan["schema_version"] == "1.0", "Unsupported plan schema.")
    require(uuid(plan["run_id"]) == uuid(approved_run_id), "Accepted run ID does not match.")
    require(plan["dataset_version"] == manifest["dataset_version"] and
            plan["logical_sha256"] == manifest["logical_sha256"], "Plan dataset identity mismatch.")
    require(plan["release_requires_human_approval"] is True and plan["limitations"] == LIMITATIONS,
            "The plan cannot bypass human approval or responsible-use limitations.")
    require(type(plan["assignments"]) is list and len(plan["assignments"]) == 3,
            "Exactly three assignments are required.")
    assigned = set()
    for assignment in plan["assignments"]:
        object_fields(assignment, {"role", "task", "acceptance_criteria"}, "assignment")
        role = assignment["role"]
        require(role in ROLES and role not in assigned, "Duplicate or foreign assignment.")
        assigned.add(role)
        require(isinstance(assignment["task"], str) and 0 < len(assignment["task"]) <= 4000,
                "Invalid assignment task.")
        criteria = assignment["acceptance_criteria"]
        require(type(criteria) is list and all(isinstance(item, str) for item in criteria) and
                len(criteria) == len(ROLE_CHECKS[role]) and set(criteria) == ROLE_CHECKS[role],
                "Assignment checks do not match its role.")
    bindings = descriptor["bindings"]
    require(type(bindings) is list and len(bindings) == 3, "Exactly three clone bindings are required.")
    bound = {}
    for binding in bindings:
        object_fields(binding, {"role", "sandbox_id", "snapshot_id", "workspace"}, "binding")
        role = binding["role"]
        require(role in ROLES and role not in bound, "Duplicate or foreign clone role.")
        bound[role] = uuid(binding["sandbox_id"])
        require(uuid(binding["snapshot_id"]) == uuid(descriptor["snapshot_id"]) and
                binding["workspace"] == "/opt/caldova-lab", "Clone baseline identity mismatch.")
    primary = uuid(descriptor["primary_id"])
    require(len(set(bound.values())) == 3 and primary not in bound.values(),
            "Independent acceptance requires distinct clones and a separate primary.")
    require(type(result["workers"]) is list and len(result["workers"]) == 3,
            "Exactly three workers are required.")
    workers = {}
    for worker in result["workers"]:
        object_fields(worker, {
            "schema_version", "run_id", "role", "sandbox_id", "dataset_version", "logical_sha256",
            "summary", "source_record_ids", "blockers",
        }, "worker")
        role = worker["role"]
        require(role in bound and role not in workers, "Duplicate or foreign worker.")
        require(worker["schema_version"] == "1.0", "Unsupported worker schema.")
        require(uuid(worker["run_id"]) == approved_run_id and
                uuid(worker["sandbox_id"]) == bound[role], "Foreign worker run or sandbox.")
        require(worker["dataset_version"] == manifest["dataset_version"] and
                worker["logical_sha256"] == manifest["logical_sha256"], "Worker dataset mismatch.")
        require(type(worker["blockers"]) is list and not worker["blockers"], "Worker has blockers.")
        require(isinstance(worker["summary"], str) and 0 < len(worker["summary"]) <= 4000,
                "Invalid worker summary.")
        ids = worker["source_record_ids"]
        require(type(ids) is list and len(ids) <= 100, "Invalid worker record IDs.")
        for record_id in ids:
            identifier(record_id)
        require(len(set(ids)) == len(ids), "Duplicate worker record ID.")
        workers[role] = {"role": role, "sandbox_id": bound[role], "source_record_ids": ids}
    evidence = []
    for field, names in (
        ("integration_evidence", INTEGRATION_CHECKS), ("egress_evidence", EGRESS_CHECKS),
        ("worker_evidence", WORKER_CHECKS),
    ):
        checks = result[field]
        require(type(checks) is list and len(checks) == len(names), f"Missing or duplicate {field}.")
        seen = set()
        for check in checks:
            object_fields(check, {
                "run_id", "name", "sandbox_id", "exit_code", "passed", "output_sha256",
            }, "check evidence")
            name = check["name"]
            require(isinstance(name, str) and name in names and name not in seen,
                    "Missing, duplicate or foreign check name.")
            seen.add(name)
            sandbox = primary
            if name.endswith("-feature-contract"):
                sandbox = bound[name.removesuffix("-feature-contract")]
            require(uuid(check["run_id"]) == approved_run_id and uuid(check["sandbox_id"]) == sandbox,
                    "Foreign check run or sandbox.")
            require(type(check["exit_code"]) is int and check["exit_code"] == 0 and
                    check["passed"] is True, "Failed or malformed acceptance check.")
            digest(check["output_sha256"])
            evidence.append(check)
    object_fields(result["candidate_sources"], MODULES.values(), "candidate sources")
    sources = {}
    for path, source in result["candidate_sources"].items():
        object_fields(source, {"path", "content", "sha256"}, "candidate source")
        require(source["path"] == path, "Candidate source path does not match the canonical allowlist.")
        require(isinstance(source["content"], str), "Candidate source content must be text.")
        content = source["content"].encode("utf-8")
        require(0 < len(content) <= 64 * 1024 and b"\0" not in content, "Invalid candidate source size.")
        require(sha256_bytes(content) == digest(source["sha256"]), "Candidate source SHA-256 mismatch.")
        sources[path] = content
    return sources, list(workers.values()), evidence


def stage_candidate(*, result_path, result_sha256, baseline_descriptor_path, frozen_artifact_directory,
                    manifest_sha256, approved_run_id, destination, repository_root=ROOT,
                    purpose=SYNTHETIC_PURPOSE):
    root = repository_root.resolve()
    raw_destination = destination.absolute()
    require(not raw_destination.exists() and not raw_destination.is_symlink() and
            not raw_destination.is_junction(), "Refusing to replace a preexisting destination.")
    for parent in raw_destination.parents:
        require(not parent.is_symlink() and not parent.is_junction(), "Destination parents cannot be links.")
    destination = raw_destination.resolve()
    require(destination.is_relative_to(root / ".build-contexts") and destination != root / ".build-contexts",
            "Use a new destination inside this repository's .build-contexts directory.")
    result = read_json(result_path, 256 * 1024, result_sha256)
    descriptor_sha256 = file_sha256(regular_file(baseline_descriptor_path))
    descriptor = read_json(baseline_descriptor_path, expected_sha256=descriptor_sha256)
    require(type(descriptor) is dict and descriptor.get("schema_version") == "1.0",
            "Unsupported baseline descriptor schema.")
    for field in ("dataset_version", "dataset_kind", "source_revision", "frozen_identity",
                  "bindings", "primary_id", "snapshot_id", "artifacts"):
        require(field in descriptor, f"Missing baseline descriptor field: {field}")
    identifier(descriptor["source_revision"])
    object_fields(descriptor["artifacts"], {"manifest", "baseline", "bindings"}, "baseline artifacts")
    require(descriptor["artifacts"] == {
        "manifest": "data-manifest.json", "baseline": "prepared-baseline.json", "bindings": "bindings.json",
    }, "Baseline artifact paths must be canonical.")
    frozen = descriptor["frozen_identity"]
    public = descriptor["dataset_kind"] == "reviewed-public"
    require(descriptor.get("acceptance_purpose", SYNTHETIC_PURPOSE) == purpose,
            "Candidate purpose differs from the prepared baseline.")
    object_fields(frozen, {
        "database_sha256", "logical_sha256", "data_manifest_sha256", "baseline_manifest_sha256",
    } | (PUBLIC_IDENTITY_FIELDS if public else set()), "frozen identity")
    for value in frozen.values():
        digest(value)
    manifest_path = frozen_artifact_directory / "data-manifest.json"
    require(digest(manifest_sha256) == frozen["data_manifest_sha256"], "Frozen manifest SHA-256 mismatch.")
    manifest = read_json(manifest_path, expected_sha256=manifest_sha256)
    check_manifest(manifest, purpose)
    pattern, count = acceptance_selection(manifest, purpose)
    require(manifest["dataset_version"] == descriptor["dataset_version"] and
            manifest["dataset_kind"] == descriptor["dataset_kind"] and
            manifest["logical_sha256"] == frozen["logical_sha256"] and
            manifest["database"]["sha256"] == frozen["database_sha256"], "Frozen dataset identity mismatch.")
    database_path = regular_file(frozen_artifact_directory / manifest["database"]["path"])
    require(database_path.stat().st_size == manifest["database"]["bytes"] and
            file_sha256(database_path) == frozen["database_sha256"], "Frozen database bytes or SHA-256 mismatch.")
    artifact_paths = [manifest_path, database_path]
    if public:
        load_public_sources(frozen_artifact_directory, manifest, root)
        require(all(frozen[name] == value for name, value in public_identity(manifest).items()),
                "Frozen original records, pipeline or source-use identity mismatch.")
        artifact_paths.extend(regular_file(frozen_artifact_directory / manifest[field]["path"])
                              for field in ("source_records", "pipeline_source"))
    baseline_path = baseline_descriptor_path.parent / "prepared-baseline.json"
    baseline = read_json(baseline_path, expected_sha256=frozen["baseline_manifest_sha256"])
    object_fields(baseline, {
        "schema_version", "source_revision", "toolchains", "dataset_version", "dataset_kind",
        "database_sha256", "data_manifest_sha256", "editable_modules", "protected_files",
    } | ({"acceptance_purpose", "public_identity"} if public else set()), "prepared baseline")
    require(baseline["schema_version"] == "1.0", "Unsupported prepared baseline schema.")
    object_fields(baseline["toolchains"], {"python", "node"}, "prepared toolchains")
    require(isinstance(baseline["toolchains"]["python"], str) and
            re.fullmatch(r"3\.13\.[0-9]+", baseline["toolchains"]["python"]) and
            isinstance(baseline["toolchains"]["node"], str) and
            re.fullmatch(r"v24\.[0-9]+\.[0-9]+", baseline["toolchains"]["node"]),
            "Unsupported prepared toolchains.")
    require(baseline["source_revision"] == descriptor["source_revision"] and
            baseline["dataset_version"] == manifest["dataset_version"] and
            baseline["dataset_kind"] == manifest["dataset_kind"] and
            baseline["database_sha256"] == frozen["database_sha256"] and
            baseline["data_manifest_sha256"] == manifest_sha256 and
            baseline["editable_modules"] == MODULES, "Prepared baseline identity mismatch.")
    if public:
        require(baseline["acceptance_purpose"] == purpose and baseline["public_identity"] == public_identity(manifest),
                "Prepared public trust anchors changed.")
        for path in artifact_paths:
            require(baseline["protected_files"].get(f"data/artifacts/development/{path.name}") == file_sha256(path),
                    "Public frozen artifacts are not protected by the prepared baseline.")
    require(type(baseline["protected_files"]) is dict, "Missing protected source files.")
    for name, value in baseline["protected_files"].items():
        relative_path(name)
        digest(value)
    sources, workers, evidence = check_result(result, approved_run_id, descriptor, manifest)
    trusted_files = set(TRUSTED_FILES)
    trusted_files.update(name for name in baseline["protected_files"] if name.startswith("data/pipeline/"))
    frontend = root / "src" / "research-portal" / "frontend" / "src"
    require(frontend.is_dir(), "Missing trusted frontend source.")
    for path in frontend.rglob("*"):
        if path.is_file():
            require(path.suffix in {".tsx", ".css"}, "Unexpected frontend source input.")
            trusted_files.add(path.relative_to(root).as_posix())
    require(any(name.endswith(".tsx") for name in trusted_files) and
            any(name.endswith(".css") for name in trusted_files), "Missing trusted frontend source inputs.")
    require({name for name in trusted_files if name.startswith("src/research-portal/frontend/src/")} ==
            {name for name in baseline["protected_files"] if name.startswith("src/research-portal/frontend/src/")},
            "The prepared frontend source set changed.")
    # Additional executable files in a copied directory must not evade the prepared trust record.
    for directory, expected in (
        (root / "data" / "pipeline", {name for name in trusted_files if name.startswith("data/pipeline/")}),
        (root / "src" / "research-portal" / "backend",
         {name for name in trusted_files if name.startswith("src/research-portal/backend/")} | set(MODULES.values())),
    ):
        actual = {path.relative_to(root).as_posix() for path in directory.glob("*.py")}
        require(actual == {name for name in expected if name.endswith(".py")}, "Unexpected trusted Python input.")
    hashes = {}
    for name in sorted(trusted_files | BUILDER_FILES):
        source = regular_file(root / name)
        value = file_sha256(source)
        if name in trusted_files:
            require(baseline["protected_files"].get(name) == value, f"Prepared trusted source changed: {name}")
        hashes[name] = value
    stage = destination.parent / f".s-{uuid4().hex[:16]}"
    stage.mkdir(parents=True)
    try:
        for name in hashes:
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
            require(file_sha256(target) == hashes[name], "Trusted source changed while staging.")
        for name, content in sources.items():
            (stage / name).write_bytes(content)
            hashes[name] = sha256_bytes(content)
        artifact_root = stage / "data" / "artifacts" / "development"
        artifact_root.mkdir(parents=True)
        for source in artifact_paths:
            target = artifact_root / source.name
            shutil.copyfile(source, target)
            hashes[target.relative_to(stage).as_posix()] = file_sha256(target)
        require(hashes["data/artifacts/development/data-manifest.json"] == manifest_sha256 and
                hashes[f"data/artifacts/development/{database_path.name}"] == frozen["database_sha256"],
                "Frozen artifact changed while staging.")
        if public:
            load_public_sources(artifact_root, manifest)
        hashes["Dockerfile"] = hashes["src/developer-image/Candidate.Containerfile"]
        shutil.copyfile(stage / "src" / "developer-image" / "Candidate.Containerfile", stage / "Dockerfile")
        ignore = "**/.runtime\n**/__pycache__\n**/*.pyc\ncandidate-image.json\n"
        (stage / ".dockerignore").write_bytes(ignore.encode("utf-8"))
        hashes[".dockerignore"] = sha256_bytes(ignore.encode("utf-8"))
        provenance = {
            "schema_version": "1.0", "kind": "agent-runtime-candidate", "run_id": approved_run_id,
            "dataset_version": manifest["dataset_version"], "dataset_kind": manifest["dataset_kind"],
            "logical_sha256": manifest["logical_sha256"], "frozen_identity": frozen,
            "database": manifest["database"], "result_sha256": result_sha256,
            "baseline_descriptor_sha256": descriptor_sha256,
            "source_revision": descriptor["source_revision"], "snapshot_id": descriptor["snapshot_id"],
            "primary_id": descriptor["primary_id"], "workers": workers, "evidence": evidence,
            "candidate_sources": {name: sha256_bytes(content) for name, content in sources.items()},
            "trusted_files": {name: hashes[name] for name in sorted(trusted_files | BUILDER_FILES)},
            "context_files": hashes, "preview_state": "reference",
            "validation_contract": {
                "original_research_tests": 9 if not public else 0,
                "original_synthetic_tests_preserved": True, "test_pattern": pattern, "tests_required": count,
                "public_research_tests": count if public else 0, "purpose": purpose,
                "container_only": True, "frozen_artifact_unchanged": True,
            },
            "acceptance_purpose": purpose,
            "status": "staged-awaiting-container-validation", "human_approval": False,
            "release_approved": False, "deployed": False,
        }
        write_json(stage / "candidate-provenance.json", provenance)
        provenance_sha256 = file_sha256(stage / "candidate-provenance.json")
        verify_context(stage, provenance_sha256)
        stage.rename(destination)
        return {"directory": str(destination), "provenance_sha256": provenance_sha256, **provenance}
    except BaseException:
        shutil.rmtree(stage)
        raise


def verify_context(directory, provenance_sha256):
    path = regular_file(directory / "candidate-provenance.json")
    require(file_sha256(path) == digest(provenance_sha256), "Candidate provenance SHA-256 mismatch.")
    provenance = read_json(path, expected_sha256=provenance_sha256)
    require(provenance.get("schema_version") == "1.0" and provenance.get("kind") == "agent-runtime-candidate",
            "Unsupported candidate provenance.")
    files = provenance["context_files"]
    require(type(files) is dict and bool(files), "Missing build-context checksum contract.")
    for name, expected in files.items():
        relative_path(name)
        require(file_sha256(regular_file(directory / name)) == digest(expected),
                f"Staged input checksum mismatch: {name}")
    entries = list(directory.rglob("*"))
    require(all(not path.is_symlink() and not path.is_junction() for path in entries),
            "Build-context links are forbidden.")
    actual = {path.relative_to(directory).as_posix() for path in entries if path.is_file()}
    require(actual == set(files) | {"candidate-provenance.json"}, "Unexpected build-context file.")
    return provenance


def validate_container():
    require(ROOT == Path("/app") and hasattr(os, "geteuid") and os.geteuid() == 10001 and
            os.environ.get("CALDOVA_PREVIEW_STATE") == "reference" and
            os.environ.get("CALDOVA_EXPECTED_PREVIEW_STATE") == "reference" and
            not os.environ.get("CALDOVA_TEST_URL") and
            os.environ.get("CALDOVA_DATA_DIR") == "/app/data/artifacts/development",
            "Candidate execution is restricted to the non-root container validation target.")
    import unittest

    import duckdb
    from data.pipeline.validate_dataset import validate_artifact

    provenance = read_json(ROOT / "candidate-provenance.json")
    manifest_path = ROOT / "data" / "artifacts" / "development" / "data-manifest.json"

    def verify_runtime():
        for name, expected in {**provenance["trusted_files"], **provenance["candidate_sources"]}.items():
            # The original portal Containerfile and packaging-only files are not runtime inputs.
            if name not in BUILDER_FILES and name != "src/research-portal/Containerfile":
                require(file_sha256(regular_file(ROOT / name)) == expected, "Runtime source bytes changed.")
        require(file_sha256(manifest_path) == provenance["frozen_identity"]["data_manifest_sha256"],
                "Runtime frozen manifest changed.")
        manifest = validate_artifact(manifest_path)
        require(manifest.database.sha256 == provenance["database"]["sha256"] and
                manifest.logical_sha256 == provenance["logical_sha256"] and
                manifest.dataset_version == provenance["dataset_version"], "Runtime frozen identity changed.")
        with duckdb.connect(str(manifest_path.parent / manifest.database.path), read_only=True,
                            config={"enable_external_access": False}) as connection:
            known = {row[0] for row in connection.execute(
                "SELECT source_record_id FROM trials UNION SELECT source_record_id FROM safety_reports"
            ).fetchall()}
        require(all(set(worker["source_record_ids"]).issubset(known) for worker in provenance["workers"]),
                "Worker cited an ID outside the frozen dataset.")

    verify_runtime()
    manifest = read_json(manifest_path)
    purpose = provenance["acceptance_purpose"]
    pattern, count = acceptance_selection(manifest, purpose)
    if manifest["dataset_kind"] == "reviewed-public":
        require(provenance["frozen_identity"].items() >= public_identity(manifest).items(),
                "Candidate public trust anchors changed.")
        load_public_sources(manifest_path.parent, manifest, ROOT)
    os.environ["CALDOVA_ACCEPTANCE_PURPOSE"] = purpose
    os.environ["CALDOVA_DATA_MANIFEST_SHA256"] = provenance["frozen_identity"]["data_manifest_sha256"]
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern=pattern)
    require(suite.countTestCases() == count, "The exact dataset-specific research acceptance suite is required.")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    require(result.wasSuccessful() and result.testsRun == count and not result.skipped and
            not result.expectedFailures and not result.unexpectedSuccesses, "Candidate acceptance failed.")
    verify_runtime()
    write_json(ROOT / ".runtime" / "candidate-validation.json", {
        "schema_version": "1.0", "status": "container-validation-passed", "tests_run": count,
        "test_pattern": pattern, "acceptance_purpose": purpose,
        "run_id": provenance["run_id"], "result_sha256": provenance["result_sha256"],
        "provenance_sha256": file_sha256(ROOT / "candidate-provenance.json"),
        "candidate_sources": provenance["candidate_sources"], "frozen_identity": provenance["frozen_identity"],
        "logical_sha256": provenance["logical_sha256"], "preview_state": "reference",
        "human_approval": False, "release_approved": False, "deployed": False,
    })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--validate-container", action="store_true")
    modes.add_argument("--verify-context", type=Path)
    parser.add_argument("--provenance-sha256")
    parser.add_argument("--result", type=Path)
    parser.add_argument("--result-sha256")
    parser.add_argument("--baseline-descriptor", type=Path)
    parser.add_argument("--frozen-artifact-directory", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--approved-run-id")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--purpose", choices=(SYNTHETIC_PURPOSE, PUBLIC_PURPOSE), default=SYNTHETIC_PURPOSE)
    args = parser.parse_args()
    if args.validate_container:
        validate_container()
    elif args.verify_context:
        require(args.provenance_sha256 is not None, "The provenance trust anchor is required.")
        print(json.dumps(verify_context(args.verify_context, args.provenance_sha256), sort_keys=True))
    else:
        require(all(value is not None for value in (
            args.result, args.result_sha256, args.baseline_descriptor, args.frozen_artifact_directory,
            args.manifest_sha256, args.approved_run_id, args.destination,
        )), "All explicit staging inputs and trust anchors are required.")
        print(json.dumps(stage_candidate(
            result_path=args.result, result_sha256=args.result_sha256,
            baseline_descriptor_path=args.baseline_descriptor,
            frozen_artifact_directory=args.frozen_artifact_directory, manifest_sha256=args.manifest_sha256,
            approved_run_id=args.approved_run_id, destination=args.destination,
            purpose=args.purpose,
        ), sort_keys=True))


if __name__ == "__main__":
    main()
