"""Offline, idempotent handoff of the versioned dataset shipped in the checkout."""

import argparse
import json
import os
import re
import shutil
import tempfile
from pathlib import Path, PurePosixPath

from src.workers.frozen_contract import PUBLIC_PURPOSE, read_json_bytes, require, verify_frozen_artifacts

ROOT = Path(__file__).resolve().parents[2]


def stage_bundle(release_path: Path, destination: Path | None = None) -> dict:
    require(release_path.is_file() and not release_path.is_symlink(),
            "The versioned lab release must be a regular file in this checkout.")
    release_path.resolve().relative_to(ROOT.resolve())
    require(release_path.stat().st_size <= 16 * 1024, "Lab release metadata exceeds its size limit.")
    release = read_json_bytes(release_path.read_bytes())
    require(type(release) is dict and set(release) == {
        "schema_version", "purpose", "dataset_version", "manifest", "distribution_authorization",
    }, "Invalid lab release fields.")
    require(release["schema_version"] == "1.0" and release["purpose"] == PUBLIC_PURPOSE,
            "The lab bundle requires the explicit public-lab-development purpose.")
    version = release["dataset_version"]
    require(isinstance(version, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,95}", version),
            "Invalid lab dataset version.")
    pin = release["manifest"]
    require(type(pin) is dict and set(pin) == {"path", "sha256"} and
            pin["path"] == f"data/lab-datasets/{version}/data-manifest.json" and
            isinstance(pin["sha256"], str) and re.fullmatch(r"[a-f0-9]{64}", pin["sha256"]),
            "The lab release must pin the versioned manifest path and lowercase SHA-256.")
    authorization = release["distribution_authorization"]
    require(type(authorization) is dict and set(authorization) == {
        "authorized_by", "authorized_at", "instruction",
    } and all(isinstance(value, str) and 0 < len(value.strip()) <= 2000
              for value in authorization.values()),
            "Lab distribution requires the recorded project-owner instruction.")
    source = ROOT.joinpath(*PurePosixPath(pin["path"]).parts)
    require(not source.is_symlink(), "The bundled manifest cannot be a symbolic link.")
    source.resolve().relative_to(ROOT.resolve())
    _, manifest, _ = verify_frozen_artifacts(source, pin["sha256"], PUBLIC_PURPOSE)
    require(manifest["dataset_version"] == version, "The pinned manifest has a different dataset version.")
    receipt = {
        "schema_version": "1.0", "purpose": PUBLIC_PURPOSE, "dataset_version": version,
        "manifest_sha256": pin["sha256"], "manifest": str(source.resolve()),
        "frozen_files_verified": True, "staged": False, "reused": False,
        "full_functional_acceptance_rerun": False, "attendee_ready": False,
    }
    if destination is None:
        return receipt
    require(not destination.is_symlink(), "The staging destination cannot be a symbolic link.")
    destination = destination.expanduser().resolve()
    require(not destination.is_relative_to(source.parent.resolve()),
            "Stage the lab data outside the immutable bundled source directory.")
    target = destination / "data-manifest.json"
    if destination.exists():
        verify_frozen_artifacts(target, pin["sha256"], PUBLIC_PURPOSE)
        return {**receipt, "manifest": str(target), "staged": True, "reused": True}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".caldova-lab-stage-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "dataset"
        staged.mkdir()
        shutil.copyfile(source, staged / source.name)
        for field in ("database", "source_records", "pipeline_source"):
            artifact = manifest[field]
            shutil.copyfile(source.parent / artifact["path"], staged / artifact["path"])
        verify_frozen_artifacts(staged / source.name, pin["sha256"], PUBLIC_PURPOSE)
        os.rename(staged, destination)
    return {**receipt, "manifest": str(target), "staged": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=ROOT / "data" / "lab-release.json")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    arguments = parser.parse_args()
    if arguments.validate_only and arguments.destination is not None:
        parser.error("--validate-only cannot be combined with a staging destination.")
    destination = None if arguments.validate_only else (
        arguments.destination or ROOT / "data" / "artifacts" / "lab-use-v2"
    )
    try:
        receipt = stage_bundle(arguments.release, destination)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"LAB_DATA_ERROR {error}\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
