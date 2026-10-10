import copy
import io
import json
import unittest
from email.message import Message
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from src.workers.check_application import (
    MAX_RESPONSE_BYTES, NoRedirect, check_application, validate_url,
)
import test_worker_public as fixtures
import test_candidate as candidate_fixtures


class ApplicationReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PublicPackagingTests("runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.manifest = self.fixture.manifest
        self.manifest["record_counts"]["candidates"] = 1
        self.fixture.bind_identity()
        self.manifest_path = self.fixture.directory / "data-manifest.json"
        self.url = "https://caldova.test.azurecontainerapps.io"
        self.candidates = self.fixture.draft["candidates"]
        self.state = "reference"
        self.responses = {
            "/health": {
                "status": "healthy", "dataset_version": self.manifest["dataset_version"],
                "dataset_kind": "reviewed-public", "preview_state": self.state,
            },
            "/api/metadata": {
                "manifest": copy.deepcopy(self.manifest), "candidates": copy.deepcopy(self.candidates),
                "preview_state": self.state, "fixture_warning": None,
            },
            "/api/source-records": {
                "dataset_version": self.manifest["dataset_version"],
                "original_extraction": copy.deepcopy(self.fixture.draft),
                "source_use_decision": copy.deepcopy(self.manifest["public_extract"]["source_use"]),
            },
            "/api/research?candidate=test-candidate": {
                "status": "ready", "candidate": self.candidates[0], "condition": None,
                "dataset_version": self.manifest["dataset_version"], "trials": [], "safety_reports": [],
                "limitations": self.manifest["limitations"], "fixture_warning": None,
            },
        }
        self.opened = []
        self.opener = Mock()
        self.opener.open.side_effect = self.open
        self.opener_patch = patch("src.workers.check_application.build_opener", return_value=self.opener)
        self.opener_patch.start()
        self.addCleanup(self.opener_patch.stop)

    def open(self, url, timeout):
        self.assertTrue(0 < timeout <= 30)
        self.opened.append(url)
        body = json.dumps(self.responses[url.removeprefix(self.url)]).encode("utf-8")
        response = io.BytesIO(body)
        response.status = 200
        response.headers = Message()
        response.headers["Content-Type"] = "application/json"
        response.headers["Cache-Control"] = "no-store"
        return response

    def run_check(self, **kwargs):
        return check_application(**{
            "manifest_path": self.manifest_path, "manifest_sha256": self.fixture.fixture.manifest_sha,
            "purpose": "public-lab-development", "url": self.url,
            "preview_state": self.state, "timeout_seconds": 60, **kwargs,
        })

    def test_public_check_binds_local_files_live_manifest_and_historical_source_decision(self):
        receipt = self.run_check()
        self.assertTrue(receipt["live_manifest_verified"])
        self.assertTrue(receipt["local_frozen_artifacts_verified"])
        self.assertTrue(receipt["live_original_sources_verified"])
        self.assertFalse(receipt["full_functional_acceptance_rerun"])
        self.assertFalse(receipt["attendee_ready"])
        self.assertFalse(receipt["release_approved"])
        self.assertEqual(len(self.opened), 4)
        self.assertFalse(self.fixture.draft["attendee_release_approved"])

    def test_starter_must_report_unavailable_and_empty_evidence(self):
        for path in ("/health", "/api/metadata"):
            self.responses[path]["preview_state"] = "starter"
        sample = self.responses["/api/research?candidate=test-candidate"]
        sample["status"] = "unavailable"
        self.assertTrue(self.run_check(preview_state="starter")["sample_state_verified"])
        sample["trials"] = [{"trial_id": "pretend"}]
        with self.assertRaisesRegex(ValueError, "genuinely unavailable"):
            self.run_check(preview_state="starter")

    def test_wrong_manifest_or_modified_local_artifact_never_reaches_network(self):
        with self.assertRaisesRegex(ValueError, "trust anchor mismatch"):
            self.run_check(manifest_sha256="f" * 64)
        self.assertEqual(self.opened, [])
        for name in ("caldova-research.duckdb", "source-records.json", "pipeline-source.zip"):
            path = self.fixture.directory / name
            original = path.read_bytes()
            with self.subTest(file=name):
                path.write_bytes(original + b"modified")
                with self.assertRaises(ValueError):
                    self.run_check()
                self.assertEqual(self.opened, [])
                path.write_bytes(original)

    def test_live_dataset_source_or_state_drift_cannot_become_ready(self):
        numeric_approval = copy.deepcopy(self.fixture.draft)
        numeric_approval["attendee_release_approved"] = 0
        cases = (
            ("/health", "dataset_version", "other-dataset"),
            ("/health", "preview_state", "starter"),
            ("/api/metadata", "manifest", {"logical_sha256": "f" * 64}),
            ("/api/source-records", "original_extraction", {}),
            ("/api/source-records", "original_extraction", numeric_approval),
            ("/api/source-records", "source_use_decision", {"attendee_release_approved": True}),
            ("/api/research?candidate=test-candidate", "status", "unavailable"),
            ("/api/research?candidate=test-candidate", "limitations", "Unsupported conclusion"),
        )
        for path, field, value in cases:
            with self.subTest(path=path, field=field):
                original = self.responses[path][field]
                self.responses[path][field] = value
                with self.assertRaises(ValueError):
                    self.run_check()
                self.responses[path][field] = original

    def test_synthetic_branch_requires_its_explicit_purpose_and_fixture_disclosure(self):
        synthetic = candidate_fixtures.CandidatePackagingTests("runTest")
        self.addCleanup(synthetic.tearDown)
        synthetic.setUp()
        synthetic.manifest["record_counts"]["candidates"] = 1
        candidate_fixtures.packager.write_json(synthetic.frozen / "data-manifest.json", synthetic.manifest)
        self.responses["/health"]["dataset_version"] = synthetic.manifest["dataset_version"]
        self.responses["/health"]["dataset_kind"] = "synthetic-development"
        self.responses["/api/metadata"]["manifest"] = synthetic.manifest
        self.responses["/api/metadata"]["fixture_warning"] = "Fictional test records, not clinical evidence."
        self.responses["/api/research?candidate=test-candidate"]["dataset_version"] = synthetic.manifest["dataset_version"]
        self.responses["/api/research?candidate=test-candidate"]["fixture_warning"] = self.responses["/api/metadata"]["fixture_warning"]
        options = {
            "manifest_path": synthetic.frozen / "data-manifest.json",
            "manifest_sha256": candidate_fixtures.packager.file_sha256(synthetic.frozen / "data-manifest.json"),
            "purpose": "synthetic-development",
        }
        receipt = self.run_check(**options)
        self.assertFalse(receipt["live_original_sources_verified"])
        self.assertNotIn(self.url + "/api/source-records", self.opened)
        with self.assertRaises(ValueError):
            self.run_check(**{**options, "purpose": "public-lab-development"})
        self.responses["/api/metadata"]["fixture_warning"] = None
        with self.assertRaisesRegex(ValueError, "fictional fixtures"):
            self.run_check(**options)

    def test_unsafe_urls_redirects_and_oversized_or_cached_responses_are_rejected(self):
        for url in (
            "http://caldova.test.azurecontainerapps.io",
            "https://example.invalid", self.url + "?sig=secret", self.url + "/api/metadata",
            "https://user:password@caldova.test.azurecontainerapps.io", self.url + ":444",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
        self.assertEqual(self.opened, [])
        with self.assertRaisesRegex(ValueError, "redirect"):
            NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")
        for fault in ("size", "cache", "content-type", "invalid-json", "duplicate-json", "array-json"):
            body = {
                "size": b"x" * (MAX_RESPONSE_BYTES + 1),
                "invalid-json": b'{"bad":',
                "duplicate-json": b'{"status":"healthy","status":"healthy"}',
                "array-json": b"[]",
            }.get(fault, b"{}")
            response = io.BytesIO(body)
            response.status = 200
            response.headers = Message()
            response.headers["Content-Type"] = "application/json"
            response.headers["Cache-Control"] = "no-store"
            if fault == "cache":
                response.headers.replace_header("Cache-Control", "public")
            elif fault == "content-type":
                response.headers.replace_header("Content-Type", "text/html")
            self.opener.open.side_effect = None
            self.opener.open.return_value = response
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, "byte limit|caching|JSON|Expecting"):
                self.run_check()

    def test_http_failure_and_expired_deadline_are_not_success_shaped(self):
        error = HTTPError(self.url, 503, "Unavailable", None, None)
        self.addCleanup(error.close)
        self.opener.open.side_effect = error
        with self.assertRaises(HTTPError):
            self.run_check()
        self.opener.open.side_effect = TimeoutError("Timed out")
        with self.assertRaises(TimeoutError):
            self.run_check()
        with patch("src.workers.check_application.time.monotonic", side_effect=[0, 61]):
            with self.assertRaisesRegex(ValueError, "timed out"):
                self.run_check()


if __name__ == "__main__":
    unittest.main()
