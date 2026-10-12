import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.workers.frozen_contract import (
    PUBLIC_PURPOSE, SYNTHETIC_PURPOSE, acceptance_selection, load_public_sources, public_identity,
)


def build_inputs() -> list[Path]:
    files = {
        ROOT / ".dockerignore",
        ROOT / "data" / "fixtures" / "research-data.json",
        ROOT / "data" / "pipeline" / "requirements.txt",
        ROOT / "src" / "research-portal" / "Containerfile",
        ROOT / "src" / "research-portal" / "backend" / "requirements.txt",
        ROOT / "src" / "developer-image" / "Containerfile",
        ROOT / "tests" / "test_research.py",
        ROOT / "tests" / "test_frozen_public_research.py",
        ROOT / "src" / "workers" / "frozen_contract.py",
    }
    frontend = ROOT / "src" / "research-portal" / "frontend"
    files.update(frontend / name for name in ("package.json", "package-lock.json", "tsconfig.json", "index.html"))
    for directory, pattern in (
        (ROOT / "data" / "pipeline", "*.py"),
        (ROOT / "src" / "research-portal" / "backend", "*.py"),
        (ROOT / "src" / "developer-image", "*.py"),
        (ROOT / "src" / "workers" / "starter", "*.py"),
        (frontend / "src", "*.tsx"),
        (frontend / "src", "*.css"),
    ):
        matches = list(directory.glob(pattern))
        if not matches:
            raise FileNotFoundError(f"No source files match {directory.name}/{pattern}.")
        files.update(matches)
    for path in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Source inputs must be regular files: {path.name}")
        path.resolve().relative_to(ROOT)
    return sorted(files)


def source_revision() -> str:
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True)
    return revision + ("-working-tree" if dirty else "")


def stage_frozen_data(source: str, destination: Path, expected_sha256: str, purpose: str) -> dict:
    spec = importlib.util.spec_from_file_location("caldova_packaging_checks", ROOT / "src" / "developer-image" / "stage_candidate.py")
    checks = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checks)
    sys.path.insert(0, str(ROOT))
    from data.pipeline.stage_dataset import download

    remote = urlsplit(source).scheme == "https"
    uri = urlsplit(source)
    if remote and (not uri.hostname or uri.username or uri.password or uri.query or uri.fragment):
        raise ValueError("Frozen manifests require credential-free HTTPS URLs without query or fragment.")
    if urlsplit(source).scheme and not remote and not Path(source).is_absolute():
        raise ValueError("Frozen input must be a local manifest or a credential-free HTTPS URL.")
    destination.mkdir(parents=True)
    manifest_path = destination / "data-manifest.json"
    if remote:
        download(source, manifest_path, 128 * 1024)
    else:
        checks.regular_file(Path(source))
        shutil.copyfile(source, manifest_path)
    manifest = checks.read_json(manifest_path, limit=128 * 1024, expected_sha256=expected_sha256)
    checks.require(type(manifest) is dict, "Frozen manifest must be a JSON object.")
    if purpose == SYNTHETIC_PURPOSE and manifest.get("dataset_kind") != "synthetic-development":
        raise ValueError("The default export currently supports only synthetic development; public-lab-development must be explicit.")
    checks.check_manifest(manifest, purpose)
    database = manifest["database"]
    database_path = destination / database["path"]
    if remote:
        download(urljoin(source, database["path"]), database_path, database["bytes"])
    else:
        database_source = checks.regular_file(Path(source).parent / database["path"])
        if database_source.stat().st_size != database["bytes"]:
            raise ValueError("Frozen database size does not match the pinned manifest.")
        shutil.copyfile(database_source, database_path)
    if database_path.stat().st_size != database["bytes"] or checks.file_sha256(database_path) != database["sha256"]:
        raise ValueError("Frozen database bytes do not match the pinned manifest.")
    if purpose == PUBLIC_PURPOSE:
        for field in ("source_records", "pipeline_source"):
            artifact = manifest[field]
            target = destination / artifact["path"]
            if remote:
                download(urljoin(source, artifact["path"]), target, artifact["bytes"])
            else:
                original = checks.regular_file(Path(source).parent / artifact["path"])
                if original.stat().st_size != artifact["bytes"]:
                    raise ValueError("Frozen auxiliary size mismatch.")
                shutil.copyfile(original, target)
        load_public_sources(destination, manifest, ROOT)
    return manifest


def export_context(
    destination: Path, revision: str, manifest_source: str | None = None,
    manifest_sha256: str | None = None,
    purpose: str = SYNTHETIC_PURPOSE,
) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", revision):
        raise ValueError("Source revision must be a bounded, single-line identifier.")
    if (manifest_source is None) != (manifest_sha256 is None):
        raise ValueError("Frozen source export requires both a manifest and its SHA-256 trust anchor.")
    if purpose not in {SYNTHETIC_PURPOSE, PUBLIC_PURPOSE} or (purpose == PUBLIC_PURPOSE and manifest_source is None):
        raise ValueError("Public development export requires an explicit pinned frozen manifest.")
    if manifest_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", manifest_sha256):
        raise ValueError("The frozen manifest trust anchor must be a lowercase SHA-256.")
    destination = destination.resolve()
    if destination == ROOT or not destination.is_relative_to(ROOT):
        raise ValueError("Export the source context into a new directory inside this repository.")
    if destination.exists():
        raise FileExistsError("Refusing to replace an existing source-context directory.")
    files = build_inputs()
    destination.mkdir(parents=True)
    try:
        frozen = None
        if manifest_source is not None:
            frozen = stage_frozen_data(
                manifest_source, destination / "data" / "artifacts" / "development", manifest_sha256, purpose
            )
        for path in files:
            target = destination / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        containerfile = destination / "src" / "developer-image" / "Containerfile"
        dockerfile = containerfile.read_text(encoding="utf-8").replace(
            "ARG SOURCE_REVISION=uncommitted-development", f"ARG SOURCE_REVISION={revision}"
        )
        if frozen is not None:
            build_instruction = (
                "RUN python -m data.pipeline.build_dataset \\\n"
                "        --input data/fixtures/research-data.json --output data/artifacts/development"
            )
            if dockerfile.count(build_instruction) != 1:
                raise ValueError("The trusted Containerfile no longer has the expected data preparation step.")
            stage_instruction = (
                "COPY data/artifacts/development/ /opt/caldova-frozen/\n"
                "RUN python -m data.pipeline.stage_dataset \\\n"
                "        --manifest /opt/caldova-frozen/data-manifest.json \\\n"
                f"        --manifest-sha256 {manifest_sha256} \\\n"
                "        --destination data/artifacts/development"
            )
            dockerfile = dockerfile.replace(build_instruction, stage_instruction)
            pattern, _ = acceptance_selection(frozen, purpose)
            dockerfile = dockerfile.replace("-p test_research.py -v", f"-p {pattern} -v")
            dockerfile = dockerfile.replace(
                "CALDOVA_ACCEPTANCE_PURPOSE=synthetic-development",
                f"CALDOVA_ACCEPTANCE_PURPOSE={purpose} CALDOVA_DATA_MANIFEST_SHA256={manifest_sha256}",
            )
        (destination / "Dockerfile").write_text(dockerfile, encoding="utf-8")
        with (destination / ".dockerignore").open("a", encoding="utf-8") as stream:
            stream.write("\n!Dockerfile\n")
            if frozen is not None:
                stream.write(
                    "!data/artifacts/\n!data/artifacts/development/\n"
                    "!data/artifacts/development/data-manifest.json\n"
                    f"!data/artifacts/development/{frozen['database']['path']}\n"
                )
                if purpose == PUBLIC_PURPOSE:
                    for field in ("source_records", "pipeline_source"):
                        stream.write(f"!data/artifacts/development/{frozen[field]['path']}\n")
        checksums = {}
        for path in sorted(destination.rglob("*")):
            if path.is_file():
                with path.open("rb") as stream:
                    checksums[path.relative_to(destination).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
        record = {
            "schema_version": "1.0",
            "source_revision": revision,
            "trusted_image_builder_only": True,
            "files": checksums,
        }
        frozen_identity = None
        if frozen is not None:
            frozen_identity = {
                "dataset_version": frozen["dataset_version"], "dataset_kind": frozen["dataset_kind"],
                "database_sha256": frozen["database"]["sha256"], "data_manifest_sha256": manifest_sha256,
                "logical_sha256": frozen["logical_sha256"],
            }
            if purpose == PUBLIC_PURPOSE:
                frozen_identity.update(public_identity(frozen))
                frozen_identity["acceptance_purpose"] = purpose
            record["frozen_data"] = frozen_identity
        manifest_path = destination / "source-context.json"
        manifest_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        with manifest_path.open("rb") as stream:
            manifest_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
        result = {
            "directory": str(destination),
            "source_revision": revision,
            "files": len(checksums),
            "source_context_manifest_sha256": manifest_sha256,
            "usage": "Use this directory only as the trusted image builder's --source, not as a worker source bundle.",
        }
        if frozen_identity is not None:
            result["frozen_data"] = frozen_identity
        return result
    except BaseException:
        shutil.rmtree(destination)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Export an allowlisted, credential-free native image-build context.")
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--source-revision")
    parser.add_argument("--manifest", help="Frozen artifact manifest; never rebuilt.")
    parser.add_argument("--manifest-sha256", help="Required trust anchor when --manifest is supplied.")
    parser.add_argument("--purpose", choices=(SYNTHETIC_PURPOSE, PUBLIC_PURPOSE), default=SYNTHETIC_PURPOSE)
    args = parser.parse_args()
    print(json.dumps(export_context(
        args.destination, args.source_revision or source_revision(), args.manifest, args.manifest_sha256, args.purpose
    ), indent=2))


if __name__ == "__main__":
    main()
