import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

import duckdb

from data.pipeline.contracts import AuxiliaryArtifact, DatasetInput, Manifest, SafetyReport, SourceUseApproval, Trial

ROW_COUNT_SQL = {
    "candidates": "SELECT count(*) FROM candidates",
    "trials": "SELECT count(*) FROM trials",
    "trial_conditions": "SELECT count(*) FROM trial_conditions",
    "trial_candidates": "SELECT count(*) FROM trial_candidates",
    "safety_reports": "SELECT count(*) FROM safety_reports",
    "safety_report_candidates": "SELECT count(*) FROM safety_report_candidates",
    "safety_reactions": "SELECT count(*) FROM safety_reactions",
}


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def logical_identity(data: DatasetInput) -> str:
    excluded = {"public_extract"} if data.public_extract is None else set()
    payload = json.dumps(data.model_dump(mode="json", exclude=excluded), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_auxiliary(directory: Path, artifact: AuxiliaryArtifact) -> Path:
    path = directory / artifact.path
    if path.is_symlink() or not path.is_file():
        raise ValueError("An auxiliary artifact must be a regular file.")
    if path.stat().st_size != artifact.bytes:
        raise ValueError(f"Auxiliary artifact size does not match the manifest: {artifact.path}")
    if file_sha256(path) != artifact.sha256:
        raise ValueError(f"Auxiliary artifact SHA-256 does not match the manifest: {artifact.path}")
    return path


def read_pipeline_snapshot(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if not 0 < len(members) <= 1000 or sum(item.file_size for item in members) > 64 * 1024 * 1024:
            raise ValueError("The pipeline source ZIP exceeds its bounded size.")
        names = [item.filename for item in members]
        if len(set(names)) != len(names):
            raise ValueError("The pipeline source ZIP contains duplicate members.")
        for member in members:
            parts = PurePosixPath(member.filename).parts
            if (
                member.is_dir() or member.flag_bits & 1 or "\\" in member.filename
                or ":" in member.filename or member.filename.startswith("/")
                or any(part in {".", ".."} for part in parts)
                or PurePosixPath(member.filename).as_posix() != member.filename
            ):
                raise ValueError("The pipeline source ZIP contains an unsafe member.")
        content = {item.filename: archive.read(item) for item in members}
    snapshot = json.loads(content.get("pipeline-source.json", b"null"))
    if (
        not isinstance(snapshot, dict) or snapshot.get("schema_version") != "1.0"
        or snapshot.get("source_kind") != "uncommitted-working-tree"
        or not isinstance(snapshot.get("files"), dict)
        or set(content) != {*snapshot["files"], "pipeline-source.json"}
    ):
        raise ValueError("The pipeline source ZIP lacks its complete working-tree identity.")
    for name, digest in snapshot["files"].items():
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("The pipeline source ZIP has an invalid file checksum.")
        if hashlib.sha256(content[name]).hexdigest() != digest:
            raise ValueError(f"The frozen pipeline source checksum differs for {name}.")
    return content


def read_original_records(directory: Path, manifest: Manifest):
    from data.pipeline.extract_public import PublicDraft

    if manifest.public_extract is None or manifest.source_records is None:
        raise ValueError("This manifest has no frozen public extract.")
    path = validate_auxiliary(directory, manifest.source_records)
    return PublicDraft.model_validate_json(path.read_bytes())


def validate_public_content(directory: Path, manifest: Manifest, connection) -> None:
    from data.pipeline.build_dataset import normalize_reports

    draft = read_original_records(directory, manifest)
    public = manifest.public_extract
    content = read_pipeline_snapshot(directory / manifest.pipeline_source.path)
    required = {"dataset-input.json", "source-use-approval.json", "draft-provenance.json"}
    if not required.issubset(content):
        raise ValueError("The frozen public source package lacks its input, decision or provenance.")
    approval = SourceUseApproval.model_validate_json(content["source-use-approval.json"])
    if approval != public.source_use:
        raise ValueError("The frozen source-use decision differs from the manifest.")
    provenance_bytes = content["draft-provenance.json"]
    if hashlib.sha256(provenance_bytes).hexdigest() != approval.draft_provenance_sha256:
        raise ValueError("The original draft provenance checksum differs from the source-use decision.")
    provenance = json.loads(provenance_bytes)
    if (
        provenance.get("draft_sha256") != manifest.source_records.sha256
        or provenance.get("draft_bytes") != manifest.source_records.bytes
        or provenance.get("trial_count") != len(draft.trials)
        or provenance.get("report_count") != len(draft.safety_reports)
        or provenance.get("trial_bucket_counts") != draft.trial_bucket_counts
        or provenance.get("report_candidate_counts") != draft.report_candidate_counts
        or public.trial_bucket_counts != draft.trial_bucket_counts
        or public.report_candidate_counts != draft.report_candidate_counts
        or public.source_quality_counts != draft.source_quality_counts
        or public.mapping_version != draft.mapping_version
        or not all(note in public.coverage_notes for note in draft.coverage_notes[1:])
    ):
        raise ValueError("The public extract disagrees with its original selection or coverage.")
    data = DatasetInput.model_validate_json(content["dataset-input.json"])
    if (
        logical_identity(data) != manifest.logical_sha256
        or data.dataset_version != manifest.dataset_version or data.dataset_kind != manifest.dataset_kind
        or data.review != manifest.review or data.sources != manifest.sources
        or data.public_extract != public or data.candidates != draft.candidates
    ):
        raise ValueError("The frozen public input identity differs from the manifest or draft.")
    if (
        [item.model_dump(mode="json", exclude={"license_notes"}) for item in data.sources]
        != [item.model_dump(mode="json", exclude={"license_notes"}) for item in draft.sources]
        or any(not approved.license_notes.startswith(original.license_notes)
               for approved, original in zip(data.sources, draft.sources, strict=True))
    ):
        raise ValueError("The public artifact changed its original source identity or attribution notes.")
    expected_trials = [
        Trial.model_validate(item.model_dump(include=set(Trial.model_fields)))
        for item in draft.trials
    ]
    expected_reports = [
        SafetyReport.model_validate(item.model_dump(include=set(SafetyReport.model_fields)))
        for item in draft.safety_reports
    ]
    if data.trials != expected_trials or data.safety_reports != expected_reports:
        raise ValueError("The public input changed a complete selected source record.")
    if manifest.record_counts["raw_safety_reports"] != len(data.safety_reports):
        raise ValueError("The selected raw report count differs from the frozen input.")

    def rows(sql):
        cursor = connection.execute(sql)
        return [dict(zip([column[0] for column in cursor.description], row, strict=True)) for row in cursor.fetchall()]

    actual_trials = [
        Trial.model_validate(item) for item in rows(
            "SELECT t.*, (SELECT list(condition ORDER BY condition) FROM trial_conditions "
            "WHERE trial_id=t.trial_id) AS conditions, (SELECT list(candidate_id ORDER BY candidate_id) "
            "FROM trial_candidates WHERE trial_id=t.trial_id) AS candidate_ids FROM trials t ORDER BY trial_id"
        )
    ]
    expected_trials = [
        item.model_copy(update={
            "conditions": sorted(set(item.conditions)), "candidate_ids": sorted(set(item.candidate_ids)),
        }) for item in sorted(expected_trials, key=lambda item: item.trial_id)
    ]
    actual_reports = [
        SafetyReport.model_validate(item) for item in rows(
            "SELECT s.*, (SELECT list(candidate_id ORDER BY candidate_id) FROM safety_report_candidates "
            "WHERE report_id=s.report_id) AS candidate_ids, (SELECT list(reaction_term ORDER BY reaction_term) "
            "FROM safety_reactions WHERE report_id=s.report_id) AS reaction_terms "
            "FROM safety_reports s ORDER BY report_id"
        )
    ]
    actual_candidates = rows("SELECT * FROM candidates ORDER BY candidate_id")
    expected_candidates = [item.model_dump() for item in sorted(data.candidates, key=lambda item: item.candidate_id)]
    if (
        actual_trials != expected_trials or actual_reports != normalize_reports(expected_reports)
        or actual_candidates != expected_candidates
    ):
        raise ValueError("The public database changed a complete frozen source projection.")


def validate_artifact(manifest_path: Path) -> Manifest:
    manifest = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    database_path = manifest_path.parent / manifest.database.path
    if database_path.is_symlink():
        raise ValueError("The database artifact must not be a symbolic link.")
    if database_path.stat().st_size != manifest.database.bytes:
        raise ValueError("Database size does not match the manifest.")
    if file_sha256(database_path) != manifest.database.sha256:
        raise ValueError("Database SHA-256 does not match the manifest.")
    for artifact in (manifest.source_records, manifest.pipeline_source):
        if artifact is not None:
            validate_auxiliary(manifest_path.parent, artifact)
    if set(manifest.record_counts) != {*ROW_COUNT_SQL, "raw_safety_reports"}:
        raise ValueError("The manifest contains an unexpected record-count contract.")
    with duckdb.connect(
        str(database_path), read_only=True, config={"enable_external_access": False}
    ) as connection:
        metadata = connection.execute(
            "SELECT dataset_version, dataset_kind, logical_sha256 FROM dataset_metadata"
        ).fetchall()
        if metadata != [
            (manifest.dataset_version, manifest.dataset_kind, manifest.logical_sha256)
        ]:
            raise ValueError("Database identity does not match the manifest.")
        for table, sql in ROW_COUNT_SQL.items():
            actual = connection.execute(sql).fetchone()[0]
            if actual != manifest.record_counts[table]:
                raise ValueError(f"Record count does not match for {table}.")
        if manifest.public_extract is not None:
            validate_public_content(manifest_path.parent, manifest, connection)
        elif manifest.pipeline_source is not None:
            read_pipeline_snapshot(manifest_path.parent / manifest.pipeline_source.path)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the immutable Caldova data artifact.")
    parser.add_argument("--manifest", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = validate_artifact(arguments.manifest)
    print(f"DATA_VERIFIED {manifest.dataset_version} {manifest.database.sha256}")


if __name__ == "__main__":
    main()
