from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen

if TYPE_CHECKING:
    from data.pipeline.contracts import Manifest


def download(url: str, destination: Path, limit: int) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Artifact downloads require HTTPS URLs without credentials.")
    with urlopen(url, timeout=30) as response, destination.open("wb") as output:
        if urlsplit(response.url).scheme != "https":
            raise ValueError("Artifact download redirected to an insecure URL.")
        received = 0
        while chunk := response.read(64 * 1024):
            received += len(chunk)
            if received > limit:
                raise ValueError("Artifact download exceeded its permitted size.")
            output.write(chunk)


def stage_dataset(manifest_source: str, destination: Path, expected_manifest_sha256: str | None) -> Manifest:
    from data.pipeline.contracts import Manifest
    from data.pipeline.validate_dataset import validate_artifact

    scheme = urlsplit(manifest_source).scheme
    remote = scheme == "https"
    if scheme and not remote and not Path(manifest_source).is_absolute():
        raise ValueError("The manifest source must be a local path or an HTTPS URL.")
    if remote and expected_manifest_sha256 is None:
        raise ValueError("Remote staging requires the published manifest SHA-256 trust anchor.")
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite staged dataset directory: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".caldova-stage-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "dataset"
        staged.mkdir()
        manifest_path = staged / "data-manifest.json"
        if remote:
            download(manifest_source, manifest_path, 128 * 1024)
        else:
            shutil.copyfile(Path(manifest_source), manifest_path)
        manifest_bytes = manifest_path.read_bytes()
        if expected_manifest_sha256 is not None:
            actual = hashlib.sha256(manifest_bytes).hexdigest()
            if actual != expected_manifest_sha256:
                raise ValueError("Manifest SHA-256 does not match the published trust anchor.")
        manifest = Manifest.model_validate_json(manifest_bytes)
        for artifact in (manifest.database, manifest.source_records, manifest.pipeline_source):
            if artifact is None:
                continue
            target = staged / artifact.path
            if remote:
                download(urljoin(manifest_source, artifact.path), target, artifact.bytes)
            else:
                source = Path(manifest_source).parent / artifact.path
                if source.is_symlink():
                    raise ValueError("A source artifact must not be a symbolic link.")
                if source.stat().st_size != artifact.bytes:
                    raise ValueError("Source artifact size does not match the manifest.")
                shutil.copyfile(source, target)
        validate_artifact(manifest_path)
        os.rename(staged, destination)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage and verify the shared Caldova artifact once.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--manifest-sha256")
    arguments = parser.parse_args()
    manifest = stage_dataset(
        arguments.manifest, arguments.destination, arguments.manifest_sha256
    )
    print(f"DATA_STAGED {manifest.dataset_version} {manifest.database.sha256}")


if __name__ == "__main__":
    main()
