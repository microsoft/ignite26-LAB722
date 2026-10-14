"""Standard-library-only checks for the explicitly pinned public development branch."""

import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from data.pipeline.public_policy import PUBLIC_MAPPING_LIMITS, public_mapping_limits

PUBLIC_PURPOSE = "public-lab-development"
SYNTHETIC_PURPOSE = "synthetic-development"
PUBLIC_TEST_PATTERN = "test_frozen_public_research.py"
PUBLIC_TEST_COUNT = 8
MAX_BYTES = 64 * 1024 * 1024
PUBLIC_IDENTITY_FIELDS = {"source_records_sha256", "pipeline_source_sha256", "source_use_sha256"}
APPROVAL_FLAGS = {
    "expert_audit_performed", "publication_authorized", "live_replacement_authorized",
    "attendee_release_approved",
}
def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def unique_object(pairs):
    result = {}
    for name, value in pairs:
        require(name not in result, "Duplicate frozen JSON field.")
        result[name] = value
    return result


def read_json_bytes(content):
    return json.loads(content.decode("utf-8"), object_pairs_hook=unique_object,
                      parse_constant=lambda _: require(False, "Non-finite frozen JSON value."))


def digest(value):
    require(isinstance(value, str) and re.fullmatch("[a-f0-9]{64}", value), "Invalid frozen SHA-256.")
    return value


def https(value):
    require(isinstance(value, str), "Missing public source URL.")
    uri = urlsplit(value)
    require(uri.scheme == "https" and uri.hostname and not uri.username and not uri.password,
            "Public sources require credential-free HTTPS URLs.")


def timestamp(value):
    require(isinstance(value, str), "Missing source-use date.")
    date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(date.utcoffset() is not None, "Source-use dates require an explicit time zone.")
    return date


def check_public_manifest(manifest, purpose):
    require(purpose == PUBLIC_PURPOSE,
            "Public acceptance requires explicit public-lab-development purpose, not attendee approval.")
    require(manifest.get("dataset_kind") == "reviewed-public" and
            all(manifest.get(field) is not None for field in ("public_extract", "source_records", "pipeline_source")),
            "Public development requires the exact frozen source records, source-use decision and pipeline ZIP.")
    public = manifest["public_extract"]
    require(type(public) is dict and set(public) == {
        "source_use", "mapping_version", "coverage_notes", "trial_bucket_counts",
        "report_candidate_counts", "source_quality_counts",
    }, "Invalid frozen public extraction fields.")
    approval = public["source_use"]
    require(type(approval) is dict and set(approval) == {
        "schema_version", "approved_by", "approved_at", "scope", "draft_sha256",
        "draft_provenance_sha256", "instruction", *APPROVAL_FLAGS,
    }, "Invalid source-use decision fields.")
    require(approval["schema_version"] == "1.0" and
            approval["scope"] == "project-owner-selected-public-lab-use" and
            all(approval[flag] is False for flag in APPROVAL_FLAGS),
            "Source-use scope cannot authorize expert audit, publication, deployment or attendee release.")
    for field in ("approved_by", "instruction"):
        require(isinstance(approval[field], str) and 0 < len(approval[field].strip()) <= 2000,
                "Missing named project-owner source-use decision.")
    timestamp(approval["approved_at"])
    digest(approval["draft_sha256"])
    digest(approval["draft_provenance_sha256"])
    require(manifest["review"] == {
        "approved_by": approval["approved_by"], "approved_at": approval["approved_at"],
    }, "Review identity must match the separate source-use decision exactly.")
    trial_limit, report_limit = public_mapping_limits(public["mapping_version"])
    require(type(public["coverage_notes"]) is list and bool(public["coverage_notes"]) and
            all(isinstance(note, str) and note.strip() for note in public["coverage_notes"]),
            "Frozen extraction mapping and coverage notes are required.")
    for field in ("trial_bucket_counts", "report_candidate_counts", "source_quality_counts"):
        require(type(public[field]) is dict and all(
            isinstance(name, str) and type(count) is int and count >= 0 and
            (field == "source_quality_counts" or
             count <= (trial_limit if field == "trial_bucket_counts" else report_limit))
            for name, count in public[field].items()
        ), "Invalid bounded public selection counts.")
    for field, suffix in (("source_records", ".json"), ("pipeline_source", ".zip")):
        artifact = manifest[field]
        require(type(artifact) is dict and set(artifact) == {"path", "sha256", "bytes"},
                "Invalid frozen auxiliary artifact.")
        require(isinstance(artifact["path"], str) and
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}" + re.escape(suffix), artifact["path"]),
                "Auxiliary artifacts require canonical filenames.")
        digest(artifact["sha256"])
        require(type(artifact["bytes"]) is int and 0 < artifact["bytes"] <= MAX_BYTES,
                "Invalid auxiliary artifact size.")
    require(manifest["source_records"]["sha256"] == approval["draft_sha256"],
            "Source-use approval is not bound to the original source bytes.")
    commit = manifest["pipeline_commit"]
    require(commit == "uncommitted-development" or
            (isinstance(commit, str) and re.fullmatch("[a-f0-9]{40}", commit)),
            "Public development requires a full source commit or frozen working-tree ZIP.")
    for source in manifest["sources"]:
        https(source.get("url"))
        timestamp(source.get("retrieved_at"))


def public_identity(manifest):
    return {
        "source_records_sha256": manifest["source_records"]["sha256"],
        "pipeline_source_sha256": manifest["pipeline_source"]["sha256"],
        "source_use_sha256": canonical_hash(manifest["public_extract"]["source_use"]),
    }


def frozen_bytes(directory, artifact):
    path = directory / artifact["path"]
    require(path.is_file() and not path.is_symlink() and
            not any(item.is_symlink() or item.is_junction() for item in path.parents),
            "Frozen artifacts must be regular files without links.")
    require(path.stat().st_size == artifact["bytes"], "Frozen auxiliary size mismatch.")
    content = path.read_bytes()
    require(len(content) == artifact["bytes"] and hashlib.sha256(content).hexdigest() == artifact["sha256"],
            "Frozen auxiliary checksum mismatch.")
    return content


def load_public_sources(directory, manifest, repository_root=None):
    check_public_manifest(manifest, PUBLIC_PURPOSE)
    draft = read_json_bytes(frozen_bytes(directory, manifest["source_records"]))
    archive_bytes = frozen_bytes(directory, manifest["pipeline_source"])
    import io

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        members = archive.infolist()
        require(0 < len(members) <= 1000 and sum(item.file_size for item in members) <= MAX_BYTES,
                "Frozen pipeline ZIP exceeds its bounded inventory.")
        require(len({item.filename for item in members}) == len(members), "Duplicate pipeline ZIP member.")
        for item in members:
            name = item.filename
            require(not item.is_dir() and not item.flag_bits & 1 and
                    "\\" not in name and ":" not in name and not name.startswith("/") and
                    all(part not in {".", ".."} for part in name.split("/")) and
                    PurePosixPath(name).as_posix() == name and
                    (item.external_attr >> 16) & 0o170000 not in {0o120000},
                    "Unsafe pipeline ZIP member.")
        content = {item.filename: archive.read(item) for item in members}
    inventory = read_json_bytes(content.get("pipeline-source.json", b"null"))
    require(type(inventory) is dict and inventory.get("schema_version") == "1.0" and
            inventory.get("source_kind") in {"uncommitted-working-tree", "git-commit"} and
            type(inventory.get("files")) is dict and
            set(content) == {*inventory["files"], "pipeline-source.json"},
            "Missing complete frozen pipeline checksum inventory.")
    if inventory["source_kind"] == "git-commit":
        require(re.fullmatch("[a-f0-9]{40}", str(inventory.get("source_revision", ""))) and
                inventory["source_revision"] == manifest["pipeline_commit"],
                "Frozen pipeline commit differs from the manifest.")
    for name, expected in inventory["files"].items():
        require(hashlib.sha256(content[name]).hexdigest() == digest(expected), "Frozen pipeline member changed.")
        if repository_root is not None and name.startswith("data/pipeline/"):
            path = repository_root / name
            require(path.is_file() and not path.is_symlink() and path.read_bytes() == content[name],
                    f"Frozen pipeline differs from the packaging source: {name}")
    require({"dataset-input.json", "source-use-approval.json", "draft-provenance.json"}.issubset(content),
            "Missing frozen public input, decision or provenance.")
    approval = manifest["public_extract"]["source_use"]
    require(read_json_bytes(content["source-use-approval.json"]) == approval,
            "Frozen pipeline decision differs from the manifest.")
    require(hashlib.sha256(content["draft-provenance.json"]).hexdigest() == approval["draft_provenance_sha256"],
            "Frozen draft provenance checksum mismatch.")
    provenance = read_json_bytes(content["draft-provenance.json"])
    require(draft.get("source_review_approved") is False and draft.get("attendee_release_approved") is False,
            "Historical original extraction flags must remain false.")
    require(timestamp(approval["approved_at"]) >= timestamp(draft["built_at"]),
            "Source-use decision predates its original extraction.")
    public = manifest["public_extract"]
    require(provenance.get("draft_sha256") == approval["draft_sha256"] and
            provenance.get("draft_bytes") == manifest["source_records"]["bytes"] and
            provenance.get("trial_count") == len(draft["trials"]) and
            provenance.get("report_count") == len(draft["safety_reports"]),
            "Frozen original extraction provenance mismatch.")
    for field in ("trial_bucket_counts", "report_candidate_counts"):
        require(public[field] == draft[field] == provenance.get(field), "Frozen selection coverage changed.")
    require(public["source_quality_counts"] == draft["source_quality_counts"] and
            public["mapping_version"] == draft["mapping_version"] and
            all(note in public["coverage_notes"] for note in draft["coverage_notes"][1:]),
            "Frozen mapping, quality or coverage notes changed.")
    data = read_json_bytes(content["dataset-input.json"])
    require(canonical_hash(data) == manifest["logical_sha256"] and
            data["dataset_version"] == manifest["dataset_version"] and
            data["dataset_kind"] == manifest["dataset_kind"] and data["review"] == manifest["review"] and
            data["public_extract"] == public and data["sources"] == manifest["sources"] and
            data["candidates"] == draft["candidates"],
            "Frozen public logical/source-use identity mismatch.")
    return draft, data


def acceptance_selection(manifest, purpose):
    if manifest["dataset_kind"] == "synthetic-development":
        require(purpose == SYNTHETIC_PURPOSE and manifest.get("review") is None and
                all(manifest.get(field) is None for field in ("public_extract", "source_records", "pipeline_source")),
                "Synthetic acceptance cannot conceal public data or source-use approval.")
        return "test_research.py", 9
    check_public_manifest(manifest, purpose)
    return PUBLIC_TEST_PATTERN, PUBLIC_TEST_COUNT


def manifest_identity(path, expected_sha256, purpose):
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= 128 * 1024,
            "The frozen manifest must be a bounded regular file.")
    content = path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == digest(expected_sha256), "Frozen manifest trust anchor mismatch.")
    manifest = read_json_bytes(content)
    acceptance_selection(manifest, purpose)
    identity = {
        "dataset_kind": manifest["dataset_kind"], "dataset_version": manifest["dataset_version"],
        "database_sha256": digest(manifest["database"]["sha256"]),
        "logical_sha256": digest(manifest["logical_sha256"]),
        "data_manifest_sha256": expected_sha256, "acceptance_purpose": purpose,
    }
    if purpose == PUBLIC_PURPOSE:
        identity.update(public_identity(manifest))
    return identity


def verify_frozen_artifacts(path, expected_sha256, purpose):
    identity = manifest_identity(path, expected_sha256, purpose)
    manifest = read_json_bytes(path.read_bytes())
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256,
            "Frozen manifest changed after identity verification.")
    database = manifest["database"]
    require(
        isinstance(database["path"], str) and
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.duckdb", database["path"]) and
        type(database["bytes"]) is int and 0 < database["bytes"] <= MAX_BYTES,
        "Invalid frozen database path or size.",
    )
    digest(database["sha256"])
    frozen_bytes(path.parent, database)
    draft = None
    if purpose == PUBLIC_PURPOSE:
        draft, _ = load_public_sources(path.parent, manifest)
    return identity, manifest, draft


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Read a pinned manifest identity without DuckDB or candidate execution.")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--purpose", choices=(SYNTHETIC_PURPOSE, PUBLIC_PURPOSE), required=True)
    arguments = parser.parse_args()
    print(json.dumps(manifest_identity(arguments.manifest, arguments.manifest_sha256, arguments.purpose), sort_keys=True))
