import json
import os
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from unittest.mock import patch

import duckdb
from pydantic import ValidationError

from data.pipeline.build_dataset import build_dataset, normalize_reports
from data.pipeline.contracts import DatasetInput, Manifest
from data.pipeline.stage_dataset import stage_dataset
from data.pipeline.validate_dataset import validate_artifact

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "fixtures" / "research-data.json"


class PipelineTests(unittest.TestCase):
    def test_report_versions_and_duplicate_terms_are_normalized(self):
        data = DatasetInput.model_validate_json(FIXTURE.read_text())
        reports = normalize_reports(data.safety_reports)
        self.assertEqual([(report.report_id, report.version) for report in reports], [
            ("DEMO-REPORT-001", 2), ("DEMO-REPORT-002", 1), ("DEMO-REPORT-003", 1),
        ])
        self.assertEqual(reports[0].reaction_terms, ["NAUSEA", "VOMITING"])
        conflict = reports[0].model_copy(update={"reaction_terms": ["DIFFERENT"]})
        with self.assertRaisesRegex(ValueError, "Conflicting copies"):
            normalize_reports([reports[0], conflict])

    def test_two_builds_have_the_same_logical_identity_and_query_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = build_dataset(FIXTURE, root / "first", "uncommitted-development")
            second = build_dataset(FIXTURE, root / "second", "uncommitted-development")
            self.assertEqual(first.logical_sha256, second.logical_sha256)
            self.assertEqual(first.record_counts, second.record_counts)
            self.assertEqual(first.record_counts["raw_safety_reports"], 5)
            self.assertEqual(first.record_counts["safety_reports"], 3)
            for folder in ("first", "second"):
                validated = validate_artifact(root / folder / "data-manifest.json")
                with duckdb.connect(str(root / folder / validated.database.path), read_only=True) as connection:
                    matches = connection.execute(
                        "SELECT trial_id FROM trial_conditions WHERE condition = ? ORDER BY trial_id",
                        ["obesity"],
                    ).fetchall()
                self.assertEqual(matches, [("DEMO-TRIAL-001",), ("DEMO-TRIAL-003",)])

    def test_staging_rejects_corruption_without_publishing_a_destination(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = build_dataset(FIXTURE, root / "source", "uncommitted-development")
            staged = stage_dataset(str(root / "source" / "data-manifest.json"), root / "valid", None)
            self.assertEqual(staged.database.sha256, manifest.database.sha256)
            with (root / "source" / manifest.database.path).open("ab") as database:
                database.write(b"corruption")
            with self.assertRaisesRegex(ValueError, "size does not match"):
                stage_dataset(str(root / "source" / "data-manifest.json"), root / "invalid", None)
            self.assertFalse((root / "invalid").exists())

    def test_remote_staging_requires_a_manifest_trust_anchor(self):
        with tempfile.TemporaryDirectory() as temporary, patch("data.pipeline.stage_dataset.urlopen") as request:
            with self.assertRaisesRegex(ValueError, "trust anchor"):
                stage_dataset("https://example.com/data-manifest.json", Path(temporary) / "dataset", None)
            request.assert_not_called()

    def test_public_data_cannot_bypass_review_or_use_a_traversal_path(self):
        fixture = json.loads(FIXTURE.read_text())
        fixture["dataset_kind"] = "reviewed-public"
        with self.assertRaisesRegex(ValidationError, "recorded source review"):
            DatasetInput.model_validate(fixture)
        with tempfile.TemporaryDirectory() as temporary:
            manifest = build_dataset(FIXTURE, Path(temporary) / "source", "uncommitted-development")
            invalid = manifest.model_dump(mode="json")
            invalid["database"]["path"] = "../other.duckdb"
            with self.assertRaisesRegex(ValidationError, "filename"):
                Manifest.model_validate(invalid)


@contextmanager
def api_server(port: int, preview_state: str | None):
    environment = dict(os.environ)
    if preview_state is not None:
        environment["CALDOVA_PREVIEW_STATE"] = preview_state
    server = subprocess.Popen(
        [
            "uvicorn", "app:app", "--app-dir",
            str(ROOT / "src" / "research-portal" / "backend"),
            "--host", "127.0.0.1", "--port", str(port),
        ],
        cwd=ROOT,
        env=environment,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if server.poll() is not None:
                raise RuntimeError(f"Test server exited with status {server.returncode}.")
            try:
                with urlopen(base_url + "/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except URLError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Test server did not become healthy within 15 seconds.")
        yield base_url
    finally:
        server.terminate()
        server.wait(timeout=5)


class ResearchApiTests(unittest.TestCase):
    server_context = None
    base_url = os.environ.get("CALDOVA_TEST_URL", "http://127.0.0.1:8099")

    @classmethod
    def setUpClass(cls):
        if os.environ.get("CALDOVA_TEST_URL"):
            return
        cls.server_context = api_server(8099, "reference")
        cls.base_url = cls.server_context.__enter__()

    @classmethod
    def tearDownClass(cls):
        if cls.server_context is not None:
            cls.server_context.__exit__(None, None, None)

    def get_json(self, path):
        with urlopen(self.base_url + path, timeout=10) as response:
            return json.load(response)

    def test_condition_filter_and_citations(self):
        data = self.get_json("/api/research?candidate=candidate-a&condition=obesity")
        self.assertEqual(data["status"], "ready")
        self.assertEqual([trial["trial_id"] for trial in data["trials"]], ["DEMO-TRIAL-001"])
        self.assertEqual([report["report_id"] for report in data["safety_reports"]], [
            "DEMO-REPORT-001", "DEMO-REPORT-002",
        ])
        self.assertEqual(data["safety_reports"][0]["version"], 2)
        self.assertTrue(all(record["source_record_id"] for record in [*data["trials"], *data["safety_reports"]]))
        self.assertIn("not clinical evidence", data["fixture_warning"])
        self.assertIn("do not establish causation", data["limitations"])

    def test_safety_mentions_are_not_misrepresented_as_trial_condition_matches(self):
        obesity = self.get_json("/api/research?candidate=candidate-a&condition=obesity")
        diabetes = self.get_json("/api/research?candidate=candidate-a&condition=type-2-diabetes")
        self.assertNotEqual(obesity["trials"], diabetes["trials"])
        self.assertEqual(obesity["safety_reports"], diabetes["safety_reports"])
        with self.assertRaises(HTTPError) as unknown:
            self.get_json("/api/research?candidate=unknown")
        self.assertEqual(unknown.exception.code, 404)
        with self.assertRaises(HTTPError) as invalid:
            self.get_json("/api/research?candidate=candidate-a&condition=invalid")
        self.assertEqual(invalid.exception.code, 422)

    def test_known_candidate_with_no_evidence_is_an_explicit_empty_result(self):
        data = self.get_json("/api/research?candidate=candidate-c")
        self.assertEqual(data["status"], "ready")
        self.assertEqual(data["candidate"]["candidate_id"], "candidate-c")
        self.assertEqual(data["trials"], [])
        self.assertEqual(data["safety_reports"], [])

    def test_image_default_state_controls_the_unavailable_or_ready_response(self):
        if os.environ.get("CALDOVA_TEST_URL"):
            self.skipTest("Image defaults require the packaged local runtime.")
        expected_state = os.environ.get("CALDOVA_EXPECTED_PREVIEW_STATE", "reference")
        with api_server(8098, None) as base_url:
            with urlopen(base_url + "/health", timeout=10) as response:
                health = json.load(response)
            with urlopen(base_url + "/api/research?candidate=candidate-a", timeout=10) as response:
                research = json.load(response)
        self.assertEqual(health["preview_state"], expected_state)
        self.assertTrue(research["fixture_warning"])
        if expected_state == "starter":
            self.assertEqual(research["status"], "unavailable")
            self.assertEqual(research["trials"], [])
            self.assertEqual(research["safety_reports"], [])
        else:
            self.assertEqual(research["status"], "ready")
            self.assertEqual(len(research["trials"]), 2)
            self.assertEqual(len(research["safety_reports"]), 2)


if __name__ == "__main__":
    unittest.main()
