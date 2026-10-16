import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

import duckdb

from data.pipeline.build_dataset import build_dataset
from data.pipeline.contracts import DatasetInput, PublicExtract, Review, SafetyReport, SourceUseApproval, Trial
from data.pipeline.extract_public import PublicDraft, ROOT, load_openfda_pin, load_source
from data.pipeline.validate_dataset import file_sha256

MAX_BYTES = 64 * 1024 * 1024


def bounded_file(path: Path, limit: int = MAX_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError(f"A public freeze input must be a bounded regular file: {path.name}")
    return path.read_bytes()


def snapshot_sources(target: Path, extras: dict[str, bytes], pipeline_commit: str | None = None) -> None:
    frontend = ROOT / "src" / "research-portal" / "frontend"
    paths = {
        ROOT / "data" / "pipeline" / "requirements.txt",
        ROOT / "data" / "sources" / "aact-mirror.json",
        ROOT / "data" / "sources" / "openfda-intake.json",
        ROOT / "src" / "research-portal" / "backend" / "requirements.txt",
        ROOT / "src" / "research-portal" / "Containerfile",
        ROOT / "data" / "fixtures" / "research-data.json",
        ROOT / "tests" / "test_research.py",
        ROOT / "src" / "workers" / "frozen_contract.py",
    }
    paths.update(frontend / name for name in ("package.json", "package-lock.json", "tsconfig.json", "index.html"))
    for directory, pattern in (
        (ROOT / "data" / "pipeline", "*.py"),
        (ROOT / "src" / "research-portal" / "backend", "*.py"),
        (frontend / "src", "*.tsx"), (frontend / "src", "*.ts"), (frontend / "src", "*.css"),
        (ROOT / "tests", "test_public*.py"),
    ):
        paths.update(directory.glob(pattern))
    content = {}
    for path in sorted(paths):
        if not path.resolve().is_relative_to(ROOT):
            raise ValueError("The pipeline snapshot source escaped the checkout.")
        content[path.relative_to(ROOT).as_posix()] = bounded_file(path)
    if pipeline_commit is not None:
        if not re.fullmatch("[a-f0-9]{40}", pipeline_commit):
            raise ValueError("A pipeline commit must be a full lowercase Git SHA.")
        for name, payload in content.items():
            try:
                committed = subprocess.run(
                    ["git", "-C", str(ROOT), "show", f"{pipeline_commit}:{name}"],
                    capture_output=True, check=True,
                ).stdout
            except subprocess.CalledProcessError as error:
                raise ValueError(f"Specified Git commit does not contain an allowlisted source file: {name}") from error
            if committed != payload:
                raise ValueError(f"Pipeline snapshot differs from the specified Git commit: {name}")
    content.update(extras)
    if sum(map(len, content.values())) > MAX_BYTES:
        raise ValueError("The frozen pipeline sources exceed the bounded size.")
    content["pipeline-source.json"] = (json.dumps({
        "schema_version": "1.0",
        "source_kind": "git-commit" if pipeline_commit else "uncommitted-working-tree",
        **({"source_revision": pipeline_commit} if pipeline_commit else {}),
        "note": ("Allowlisted source bytes verified against the recorded Git commit."
                 if pipeline_commit else "Actual allowlisted working-tree bytes, not an attendee release."),
        "files": {name: hashlib.sha256(payload).hexdigest() for name, payload in sorted(content.items())},
    }, indent=2, sort_keys=True) + "\n").encode("utf-8")
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in sorted(content.items()):
            member = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            member.compress_type = zipfile.ZIP_DEFLATED
            member.external_attr = 0o100644 << 16
            archive.writestr(member, payload)


def freeze_public(
    draft_directory: Path, approval_path: Path, output: Path, dataset_version: str,
    pipeline_commit: str | None = None,
):
    output = output.expanduser().resolve()
    draft_directory = draft_directory.expanduser().resolve()
    if output.is_relative_to(ROOT) or draft_directory.is_relative_to(ROOT):
        raise ValueError("Keep the frozen public artifact and selected draft outside the checkout.")
    if output.exists():
        raise FileExistsError("Refusing to replace an immutable public artifact.")
    approval_bytes = bounded_file(approval_path, 16 * 1024)
    approval = SourceUseApproval.model_validate_json(approval_bytes)
    draft_bytes = bounded_file(draft_directory / "public-review-draft.json")
    provenance_bytes = bounded_file(draft_directory / "draft-provenance.json", 128 * 1024)
    if (
        hashlib.sha256(draft_bytes).hexdigest() != approval.draft_sha256
        or hashlib.sha256(provenance_bytes).hexdigest() != approval.draft_provenance_sha256
    ):
        raise ValueError("The selected draft/provenance does not match the project-owner source-use decision.")
    draft = PublicDraft.model_validate_json(draft_bytes)
    provenance = json.loads(provenance_bytes)
    if (
        not isinstance(provenance, dict) or provenance.get("aact_input") != load_source()
        or provenance.get("openfda_input") != load_openfda_pin()
        or provenance.get("extractor_sha256") != file_sha256(ROOT / "data" / "pipeline" / "extract_public.py")
        or provenance.get("draft_sha256") != approval.draft_sha256
        or provenance.get("draft_bytes") != len(draft_bytes)
        or approval.approved_at < draft.built_at
    ):
        raise ValueError("The draft provenance differs from the pinned sources, extractor or decision chronology.")
    sources = [
        source.model_copy(update={"license_notes": (
            source.license_notes + " Historical draft note; the project owner has now authorized "
            "this selected slice for local lab use, without claiming an independent expert audit."
        )}) for source in draft.sources
    ]
    data = DatasetInput(
        schema_version="1.0", dataset_version=dataset_version, dataset_kind="reviewed-public",
        review=Review(approved_by=approval.approved_by, approved_at=approval.approved_at),
        public_extract=PublicExtract(
            source_use=approval, mapping_version=draft.mapping_version,
            coverage_notes=[
                "Project-owner selected public lab extract; publication, live replacement and attendee release are separate.",
                *draft.coverage_notes[1:],
            ],
            trial_bucket_counts=draft.trial_bucket_counts,
            report_candidate_counts=draft.report_candidate_counts,
            source_quality_counts=draft.source_quality_counts,
        ),
        sources=sources, candidates=draft.candidates,
        trials=[
            Trial.model_validate(item.model_dump(include=set(Trial.model_fields))) for item in draft.trials
        ],
        safety_reports=[
            SafetyReport.model_validate(item.model_dump(include=set(SafetyReport.model_fields)))
            for item in draft.safety_reports
        ],
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".caldova-public-freeze-", dir=output.parent) as temporary:
        workspace = Path(temporary)
        input_path = workspace / "dataset-input.json"
        input_bytes = (data.model_dump_json(indent=2) + "\n").encode("utf-8")
        input_path.write_bytes(input_bytes)
        records_path = workspace / "source-records.json"
        records_path.write_bytes(draft_bytes)
        snapshot = workspace / "pipeline-source.zip"
        snapshot_sources(snapshot, {
            "dataset-input.json": input_bytes, "source-use-approval.json": approval_bytes,
            "draft-provenance.json": provenance_bytes,
        }, pipeline_commit)
        return build_dataset(
            input_path, output, pipeline_commit or "uncommitted-development",
            source_records=records_path, pipeline_source=snapshot,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze an exactly approved public lab slice without publishing it.")
    parser.add_argument("--draft-directory", type=Path, required=True)
    parser.add_argument("--source-use-approval", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--pipeline-commit")
    args = parser.parse_args()
    try:
        manifest = freeze_public(args.draft_directory, args.source_use_approval, args.output,
                                 args.dataset_version, args.pipeline_commit)
    except (OSError, ValueError, duckdb.Error, zipfile.BadZipFile) as error:
        parser.exit(1, f"PUBLIC_FREEZE_ERROR {error}\n")
    print(f"PUBLIC_DATA_FROZEN {manifest.dataset_version} {manifest.database.sha256}")


if __name__ == "__main__":
    main()
