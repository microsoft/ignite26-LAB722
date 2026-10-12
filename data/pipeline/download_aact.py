import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATH = ROOT / "data" / "sources" / "aact-mirror.json"
DOWNLOAD_HOSTS = {
    "huggingface.co",
    "cas-server.xethub.hf.co",
    "cas-server.xethub-eu.hf.co",
    "transfer.xethub.hf.co",
    "transfer.xethub-eu.hf.co",
    "us.aws.cdn.hf.co",
    "us.gcp.cdn.hf.co",
    "cdn-lfs-us-1.hf.co",
    "cdn-lfs-eu-1.hf.co",
}
CHUNK_BYTES = 1024 * 1024
DISK_RESERVE_BYTES = 256 * 1024 * 1024


def load_source() -> dict:
    source = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise ValueError("The AACT source pin must be a JSON object.")
    revision = source.get("revision")
    if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("The AACT source requires an immutable commit revision.")
    if (
        source.get("schema_version") != "1.0"
        or source.get("purpose") != "raw-source-intake"
        or source.get("filename") != "clinicaltrials.duckdb"
        or source.get("url") != (
            "https://huggingface.co/datasets/Nason/clinicaltrials-database/"
            f"resolve/{revision}/clinicaltrials.duckdb"
        )
        or type(source.get("bytes")) is not int
        or source["bytes"] <= 0
        or not isinstance(source.get("sha256"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", source["sha256"])
        or source.get("source_review_approved") is not False
        or source.get("attendee_release_approved") is not False
    ):
        raise ValueError("The AACT raw-source descriptor has invalid pins or approval state.")
    return source


def check_download_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in DOWNLOAD_HOSTS
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("AACT downloads must remain on an allowlisted Hugging Face HTTPS host.")


class HuggingFaceRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        check_download_url(newurl)
        return super().redirect_request(request, fp, code, message, headers, newurl)


def open_source(source: dict, *, offset: int = 0, method: str = "GET"):
    check_download_url(source["url"])
    headers = {"Accept-Encoding": "identity"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    return build_opener(HuggingFaceRedirects()).open(
        Request(source["url"], headers=headers, method=method), timeout=60
    )


def check_source(source: dict) -> dict:
    with open_source(source, method="HEAD") as response:
        check_download_url(response.url)
        if response.status != 200 or response.headers.get("Content-Length") != str(source["bytes"]):
            raise ValueError("AACT source availability or advertised size disagrees with the pin.")
        return {
            "source": source, "http_status": response.status,
            "download_host": urlsplit(response.url).hostname,
            "downloaded": False, "checksum_verified": False,
            "source_review_approved": False, "attendee_release_approved": False,
        }


def default_cache_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "Caldova" / "source-cache"


def verify_file(path: Path, source: dict) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("The cached AACT input must be a regular file, not a symlink.")
    if path.stat().st_size != source["bytes"]:
        raise ValueError("Cached AACT size does not match the source pin; inspect the retained input.")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != source["sha256"]:
        raise ValueError("Cached AACT SHA-256 does not match the source pin; inspect the retained input.")


def transfer(source: dict, partial: Path, offset: int) -> None:
    with open_source(source, offset=offset) as response:
        check_download_url(response.url)
        expected_status = 206 if offset else 200
        expected_range = f"bytes {offset}-{source['bytes'] - 1}/{source['bytes']}"
        if (
            response.status != expected_status
            or response.headers.get("Content-Length") != str(source["bytes"] - offset)
            or response.headers.get("Content-Encoding", "identity") != "identity"
            or (offset and response.headers.get("Content-Range") != expected_range)
        ):
            raise ValueError("AACT response violates the pinned size/range contract; partial input retained.")
        received = offset
        with partial.open("ab" if offset or partial.exists() else "xb") as output:
            while chunk := response.read(min(CHUNK_BYTES, source["bytes"] - received + 1)):
                received += len(chunk)
                if received > source["bytes"]:
                    raise ValueError("AACT download exceeded the pinned size; partial input retained.")
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if received != source["bytes"]:
            raise ValueError("AACT download was truncated; rerun to resume the retained partial input.")


def download_aact(source: dict, cache_dir: Path) -> dict:
    cache = cache_dir.expanduser().resolve()
    if cache.is_relative_to(ROOT):
        raise ValueError("The raw AACT cache must be outside the repository checkout.")
    cache = (cache / "aact" / source["revision"] / source["sha256"]).resolve()
    if cache.is_relative_to(ROOT):
        raise ValueError("The resolved raw AACT cache must be outside the repository checkout.")
    cache.mkdir(parents=True, exist_ok=True)
    database = cache / source["filename"]
    partial = database.with_suffix(".duckdb.partial")
    receipt_path = cache / "acquisition-receipt.json"
    lock_path = cache / ".download.lock"
    try:
        lock = lock_path.open("x", encoding="ascii")
    except FileExistsError:
        raise FileExistsError(f"AACT cache is locked; inspect the owner before retrying: {lock_path}") from None
    try:
        with lock:
            lock.write(str(os.getpid()))
            lock.flush()
            if receipt_path.is_symlink() or partial.is_symlink() or database.is_symlink():
                raise ValueError("AACT cache inputs and receipts must not be symbolic links.")
            if database.exists():
                verify_file(database, source)
                if not receipt_path.is_file():
                    raise ValueError("AACT cache has no acquisition receipt; inspect it before reuse.")
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                if (
                    not isinstance(receipt, dict)
                    or receipt.get("schema_version") != "1.0"
                    or receipt.get("source") != source
                    or receipt.get("bytes") != source["bytes"]
                    or receipt.get("sha256") != source["sha256"]
                    or receipt.get("checksum_verified") is not True
                    or receipt.get("source_review_approved") is not False
                    or receipt.get("attendee_release_approved") is not False
                    or receipt.get("dataset_published") is not False
                ):
                    raise ValueError("AACT cache receipt does not match the pinned source.")
                reused = True
            else:
                if receipt_path.exists():
                    raise ValueError("AACT receipt exists without its database; inspect the cache.")
                if partial.exists() and not partial.is_file():
                    raise ValueError("AACT partial input must be a regular file.")
                offset = partial.stat().st_size if partial.exists() else 0
                if offset > source["bytes"]:
                    raise ValueError("AACT partial input exceeds the source pin; inspect it before retrying.")
                required = source["bytes"] - offset + DISK_RESERVE_BYTES
                if shutil.disk_usage(cache).free < required:
                    raise OSError(f"Insufficient cache space: require {required} free bytes before downloading.")
                if offset < source["bytes"]:
                    print(f"AACT_DOWNLOAD {offset}/{source['bytes']} bytes; cache={cache}", file=sys.stderr)
                    transfer(source, partial, offset)
                verify_file(partial, source)
                receipt = {
                    "schema_version": "1.0", "source": source,
                    "download_completed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "bytes": source["bytes"], "sha256": source["sha256"],
                    "checksum_verified": True, "source_review_approved": False,
                    "attendee_release_approved": False, "dataset_published": False,
                }
                with receipt_path.open("x", encoding="utf-8") as stream:
                    json.dump(receipt, stream, indent=2, sort_keys=True)
                    stream.write("\n")
                partial.rename(database)
                reused = False
            return {
                "database_path": str(database), "receipt_path": str(receipt_path),
                "bytes": source["bytes"], "sha256": source["sha256"],
                "cache_reused": reused, "checksum_verified": True,
                "verified_at_utc": datetime.now(timezone.utc).isoformat(),
                "source_review_approved": False, "attendee_release_approved": False,
            }
    finally:
        lock_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the pinned raw AACT mirror (7.59 GB) into an external maintainer cache."
    )
    parser.add_argument("--cache-dir", type=Path, help="External cache root; defaults to the local user cache.")
    parser.add_argument("--check", action="store_true", help="Verify availability/size only; do not download.")
    arguments = parser.parse_args()
    try:
        source = load_source()
        result = check_source(source) if arguments.check else download_aact(
            source, arguments.cache_dir if arguments.cache_dir is not None else default_cache_dir()
        )
    except (OSError, ValueError) as error:
        parser.exit(1, f"AACT_SOURCE_ERROR {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
