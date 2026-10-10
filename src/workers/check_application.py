"""Read-only application checks against locally staged, checksum-pinned data."""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.workers.frozen_contract import (
    MAX_BYTES, PUBLIC_PURPOSE, SYNTHETIC_PURPOSE, canonical_hash, digest, frozen_bytes, load_public_sources,
    manifest_identity, read_json_bytes, require,
)

MAX_RESPONSE_BYTES = 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        raise ValueError("Application checks do not follow HTTP redirects.")


def validate_url(value):
    uri = urlsplit(value)
    require(
        uri.scheme == "https" and uri.hostname and
        re.fullmatch(r"[a-z0-9][a-z0-9.-]*\.azurecontainerapps\.io", uri.hostname) and
        uri.port in (None, 443) and not uri.username and not uri.password and
        uri.path in ("", "/") and not uri.query and not uri.fragment,
        "Application checks require the scoped app's credential-free HTTPS root URL.",
    )
    return value.rstrip("/")


def check_application(manifest_path, manifest_sha256, purpose, url, preview_state, timeout_seconds):
    base_url = validate_url(url)
    require(preview_state in ("starter", "reference"), "Invalid expected application preview state.")
    require(0 < timeout_seconds <= 3600, "Application timeout must be positive and bounded.")
    deadline = time.monotonic() + timeout_seconds
    identity = manifest_identity(manifest_path, manifest_sha256, purpose)
    content = manifest_path.read_bytes()
    require(hashlib.sha256(content).hexdigest() == manifest_sha256,
            "Frozen manifest changed after identity verification.")
    manifest = read_json_bytes(content)
    database = manifest["database"]
    require(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\.duckdb", database["path"]) and
        type(database["bytes"]) is int and 0 < database["bytes"] <= MAX_BYTES,
        "Invalid frozen database path or size.",
    )
    digest(database["sha256"])
    frozen_bytes(manifest_path.parent, database)
    draft = None
    if purpose == PUBLIC_PURPOSE:
        draft, _ = load_public_sources(manifest_path.parent, manifest)

    opener = build_opener(NoRedirect())

    def get_json(path):
        remaining = deadline - time.monotonic()
        require(remaining > 0, "Application verification timed out.")
        with opener.open(base_url + path, timeout=min(30, remaining)) as response:
            require(response.status == 200, "Application endpoint did not return HTTP 200.")
            require(response.headers.get_content_type() == "application/json",
                    "Application endpoint did not return JSON.")
            require(response.headers.get("Cache-Control") == "no-store",
                    "Application API must disable response caching.")
            content = response.read(MAX_RESPONSE_BYTES + 1)
            require(len(content) <= MAX_RESPONSE_BYTES, "Application response exceeded its byte limit.")
        require(time.monotonic() < deadline, "Application verification timed out.")
        value = read_json_bytes(content)
        require(type(value) is dict, "Application endpoint must return a JSON object.")
        return value

    health = get_json("/health")
    require(canonical_hash(health) == canonical_hash({
        "status": "healthy", "dataset_version": identity["dataset_version"],
        "dataset_kind": identity["dataset_kind"], "preview_state": preview_state,
    }), "Application health changed the pinned dataset or expected preview state.")
    metadata = get_json("/api/metadata")
    require(set(metadata) == {"manifest", "candidates", "preview_state", "fixture_warning"} and
            canonical_hash(metadata["manifest"]) == canonical_hash(manifest) and
            metadata["preview_state"] == preview_state,
            "Application metadata differs from the pinned frozen manifest.")
    candidates = metadata["candidates"]
    require(type(candidates) is list and bool(candidates) and all(
        type(candidate) is dict and set(candidate) == {"candidate_id", "name", "research_area"} and
        isinstance(candidate["candidate_id"], str) and
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", candidate["candidate_id"])
        for candidate in candidates
    ), "Application candidates have an invalid shape.")
    require(len({candidate["candidate_id"] for candidate in candidates}) == len(candidates) ==
            manifest["record_counts"]["candidates"], "Application candidate identities/count changed.")
    if draft is not None:
        require(canonical_hash(candidates) ==
                canonical_hash(sorted(draft["candidates"], key=lambda candidate: candidate["candidate_id"])) and
                metadata["fixture_warning"] is None, "Public candidates or fixture labeling changed.")
        original = get_json("/api/source-records")
        require(original.get("dataset_version") == identity["dataset_version"] and
                canonical_hash(original.get("original_extraction")) == canonical_hash(draft) and
                canonical_hash(original.get("source_use_decision")) ==
                canonical_hash(manifest["public_extract"]["source_use"]),
                "Application original source records or historical source-use decision changed.")
    else:
        require(isinstance(metadata["fixture_warning"], str) and bool(metadata["fixture_warning"].strip()),
                "Synthetic application metadata must disclose its fictional fixtures.")

    sample = get_json("/api/research?" + urlencode({"candidate": candidates[0]["candidate_id"]}))
    require(set(sample) == {
        "status", "candidate", "condition", "dataset_version", "trials", "safety_reports",
        "limitations", "fixture_warning",
    } and sample["candidate"] == candidates[0] and sample["condition"] is None and
        sample["dataset_version"] == identity["dataset_version"] and
        sample["limitations"] == manifest["limitations"] and
        sample["fixture_warning"] == metadata["fixture_warning"] and
        type(sample["trials"]) is list and type(sample["safety_reports"]) is list,
        "Application sample changed its data/limitations contract.")
    if preview_state == "starter":
        require(sample["status"] == "unavailable" and sample["trials"] == [] and
                sample["safety_reports"] == [], "The expected starter is not genuinely unavailable.")
    else:
        require(sample["status"] == "ready", "The expected completed preview is unavailable.")

    return {
        "schema_version": "1.0", "status": "pinned-development-application-ready",
        "url": base_url, "preview_state": preview_state, "identity": identity,
        "local_frozen_artifacts_verified": True, "live_manifest_verified": True,
        "live_original_sources_verified": draft is not None, "sample_state_verified": True,
        "full_functional_acceptance_rerun": False, "release_approved": False,
        "attendee_ready": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--purpose", choices=(SYNTHETIC_PURPOSE, PUBLIC_PURPOSE), required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--preview-state", choices=("starter", "reference"), required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    args = parser.parse_args()
    print(json.dumps(check_application(
        args.manifest, args.manifest_sha256, args.purpose, args.url,
        args.preview_state, args.timeout_seconds,
    ), sort_keys=True))


if __name__ == "__main__":
    main()
