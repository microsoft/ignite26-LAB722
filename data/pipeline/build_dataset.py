import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from data.pipeline.contracts import Artifact, AuxiliaryArtifact, DatasetInput, Manifest, SafetyReport
from data.pipeline.validate_dataset import ROW_COUNT_SQL, file_sha256, logical_identity, validate_artifact

SCHEMA_SQL = """
CREATE TABLE dataset_metadata(dataset_version VARCHAR, dataset_kind VARCHAR, logical_sha256 VARCHAR);
CREATE TABLE candidates(candidate_id VARCHAR PRIMARY KEY, name VARCHAR, research_area VARCHAR);
CREATE TABLE trials(
    trial_id VARCHAR PRIMARY KEY, title VARCHAR, phase VARCHAR, status VARCHAR,
    source_id VARCHAR, source_record_id VARCHAR, source_url VARCHAR
);
CREATE TABLE trial_conditions(trial_id VARCHAR, condition VARCHAR, PRIMARY KEY(trial_id, condition));
CREATE TABLE trial_candidates(trial_id VARCHAR, candidate_id VARCHAR, PRIMARY KEY(trial_id, candidate_id));
CREATE TABLE safety_reports(
    report_id VARCHAR PRIMARY KEY, version INTEGER, source_id VARCHAR,
    source_record_id VARCHAR, source_url VARCHAR
);
CREATE TABLE safety_report_candidates(
    report_id VARCHAR, candidate_id VARCHAR, PRIMARY KEY(report_id, candidate_id)
);
CREATE TABLE safety_reactions(report_id VARCHAR, reaction_term VARCHAR, PRIMARY KEY(report_id, reaction_term));
"""


def normalize_reports(reports: list[SafetyReport]) -> list[SafetyReport]:
    versions: dict[tuple[str, int], SafetyReport] = {}
    for report in reports:
        normalized = report.model_copy(
            update={
                "candidate_ids": sorted(set(report.candidate_ids)),
                "reaction_terms": sorted({term.upper() for term in report.reaction_terms}),
            }
        )
        key = (normalized.report_id, normalized.version)
        previous = versions.get(key)
        if previous is not None and previous != normalized:
            raise ValueError(f"Conflicting copies of safety report {key}.")
        versions[key] = normalized
    latest: dict[str, SafetyReport] = {}
    for report in versions.values():
        previous = latest.get(report.report_id)
        if previous is None or report.version > previous.version:
            latest[report.report_id] = report
    return [latest[report_id] for report_id in sorted(latest)]


def build_dataset(
    input_path: Path, output: Path, pipeline_commit: str, *,
    source_records: Path | None = None, pipeline_source: Path | None = None,
) -> Manifest:
    data = DatasetInput.model_validate_json(input_path.read_text(encoding="utf-8"))
    reports = normalize_reports(data.safety_reports)
    logical_sha256 = logical_identity(data)
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite immutable artifact directory: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".caldova-build-", dir=output.parent) as temporary:
        staged = Path(temporary) / "dataset"
        staged.mkdir()
        database_path = staged / "caldova-research.duckdb"
        with duckdb.connect(str(database_path)) as connection:
            connection.execute(SCHEMA_SQL)
            connection.execute(
                "INSERT INTO dataset_metadata VALUES (?, ?, ?)",
                [data.dataset_version, data.dataset_kind, logical_sha256],
            )
            connection.executemany(
                "INSERT INTO candidates VALUES (?, ?, ?)",
                [
                    (candidate.candidate_id, candidate.name, candidate.research_area)
                    for candidate in sorted(data.candidates, key=lambda item: item.candidate_id)
                ],
            )
            for trial in sorted(data.trials, key=lambda item: item.trial_id):
                connection.execute(
                    "INSERT INTO trials VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [
                        trial.trial_id, trial.title, trial.phase, trial.status, trial.source_id,
                        trial.source_record_id, str(trial.source_url) if trial.source_url else None,
                    ],
                )
                connection.executemany(
                    "INSERT INTO trial_conditions VALUES (?, ?)",
                    [(trial.trial_id, condition) for condition in sorted(set(trial.conditions))],
                )
                connection.executemany(
                    "INSERT INTO trial_candidates VALUES (?, ?)",
                    [(trial.trial_id, candidate) for candidate in sorted(set(trial.candidate_ids))],
                )
            for report in reports:
                connection.execute(
                    "INSERT INTO safety_reports VALUES (?, ?, ?, ?, ?)",
                    [
                        report.report_id, report.version, report.source_id, report.source_record_id,
                        str(report.source_url) if report.source_url else None,
                    ],
                )
                connection.executemany(
                    "INSERT INTO safety_report_candidates VALUES (?, ?)",
                    [(report.report_id, candidate) for candidate in report.candidate_ids],
                )
                connection.executemany(
                    "INSERT INTO safety_reactions VALUES (?, ?)",
                    [(report.report_id, term) for term in report.reaction_terms],
                )
            record_counts = {
                table: connection.execute(sql).fetchone()[0]
                for table, sql in ROW_COUNT_SQL.items()
            }
        record_counts["raw_safety_reports"] = len(data.safety_reports)
        auxiliaries = {}
        for field, source, name in (
            ("source_records", source_records, "source-records.json"),
            ("pipeline_source", pipeline_source, "pipeline-source.zip"),
        ):
            if source is not None:
                if source.is_symlink() or not source.is_file():
                    raise ValueError(f"The {field} input must be a regular file.")
                if not 0 < source.stat().st_size <= 64 * 1024 * 1024:
                    raise ValueError(f"The {field} input exceeds its bounded size.")
                target = staged / name
                shutil.copyfile(source, target)
                auxiliaries[field] = AuxiliaryArtifact(
                    path=name, bytes=target.stat().st_size, sha256=file_sha256(target),
                )
        manifest = Manifest(
            schema_version="1.0",
            dataset_version=data.dataset_version,
            dataset_kind=data.dataset_kind,
            built_at=datetime.now(timezone.utc),
            pipeline_commit=pipeline_commit,
            logical_sha256=logical_sha256,
            database=Artifact(
                path=database_path.name,
                sha256=file_sha256(database_path),
                bytes=database_path.stat().st_size,
            ),
            record_counts=record_counts,
            sources=data.sources,
            review=data.review,
            public_extract=data.public_extract,
            **auxiliaries,
        )
        manifest_path = staged / "data-manifest.json"
        excluded = {
            field for field in ("source_records", "pipeline_source", "public_extract")
            if getattr(manifest, field) is None
        }
        manifest_path.write_text(manifest.model_dump_json(indent=2, exclude=excluded) + "\n", encoding="utf-8")
        validate_artifact(manifest_path)
        os.rename(staged, output)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a bounded, versioned Caldova DuckDB artifact.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pipeline-commit", default="uncommitted-development")
    parser.add_argument("--schema-dir", type=Path)
    arguments = parser.parse_args()
    manifest = build_dataset(arguments.input, arguments.output, arguments.pipeline_commit)
    if arguments.schema_dir:
        arguments.schema_dir.mkdir(parents=True, exist_ok=True)
        for filename, model in (("dataset.schema.json", DatasetInput), ("manifest.schema.json", Manifest)):
            (arguments.schema_dir / filename).write_text(
                json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8"
            )
    print(f"DATA_BUILT {manifest.dataset_version} {manifest.database.sha256}")


if __name__ == "__main__":
    main()
