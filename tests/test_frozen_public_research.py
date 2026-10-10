"""Public runtime acceptance. Expectations come from the pinned ORIGINAL extraction, never query output."""

import json
import os
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from data.pipeline.contracts import LIMITATIONS, SafetyReport, Trial
from data.pipeline.extract_public import DraftReport, DraftTrial
from data.pipeline.validate_dataset import file_sha256, validate_artifact
from src.workers.frozen_contract import (
    PUBLIC_PURPOSE, acceptance_selection, load_public_sources, public_identity, read_json_bytes,
)
from test_research import api_server

ROOT = Path(__file__).resolve().parents[1]


class FrozenPublicResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.environ.get("CALDOVA_TEST_URL"):
            raise ValueError("Public acceptance must launch its own local frozen runtime.")
        cls.directory = Path(os.environ.get("CALDOVA_DATA_DIR", ROOT / "data/artifacts/development"))
        cls.path = cls.directory / "data-manifest.json"
        cls.manifest = validate_artifact(cls.path)
        cls.raw_manifest = read_json_bytes(cls.path.read_bytes())
        acceptance_selection(cls.raw_manifest, os.environ.get("CALDOVA_ACCEPTANCE_PURPOSE"))
        cls.anchor = os.environ.get("CALDOVA_DATA_MANIFEST_SHA256")
        if file_sha256(cls.path) != cls.anchor:
            raise ValueError("Public acceptance requires the exact harness manifest trust anchor.")
        cls.draft, cls.data = load_public_sources(cls.directory, cls.raw_manifest)
        cls.candidates = sorted(cls.draft["candidates"], key=lambda item: item["candidate_id"])
        cls.conditions = [None, "obesity", "type-2-diabetes"]
        cls.context = api_server(8099, "reference")
        cls.base_url = cls.context.__enter__()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "context", None):
            cls.context.__exit__(None, None, None)

    def get_json(self, path, base_url=None):
        with urlopen((base_url or self.base_url) + path, timeout=10) as response:
            self.assertEqual(response.headers["cache-control"], "no-store")
            return json.load(response)

    def research(self, candidate, condition=None, base_url=None):
        path = "/api/research?candidate=" + candidate
        if condition is not None:
            path += "&condition=" + condition
        return self.get_json(path, base_url)

    def expected_trials(self, candidate, condition):
        records = []
        for original in sorted(self.draft["trials"], key=lambda item: item["trial_id"]):
            if candidate not in original["candidate_ids"] or (
                condition is not None and condition not in original["conditions"]
            ):
                continue
            canonical = Trial.model_validate({name: original[name] for name in Trial.model_fields}).model_dump(mode="json")
            for name in ("conditions", "candidate_ids"):
                canonical[name] = sorted(set(canonical[name]))
            records.append(DraftTrial.model_validate({
                **canonical, "source_conditions": original["source_conditions"],
                "source_interventions": original["source_interventions"],
            }).model_dump(mode="json"))
        return records

    def expected_reports(self, candidate):
        # Latest means within this frozen single-shard selection, never a global report version.
        latest = {}
        for original in self.draft["safety_reports"]:
            canonical = SafetyReport.model_validate({
                name: original[name] for name in SafetyReport.model_fields
            }).model_dump(mode="json")
            canonical["candidate_ids"] = sorted(set(canonical["candidate_ids"]))
            canonical["reaction_terms"] = sorted({term.upper() for term in canonical["reaction_terms"]})
            record = DraftReport.model_validate({
                **canonical, "source_drugs": original["source_drugs"],
                "original_reaction_terms": original["original_reaction_terms"],
            }).model_dump(mode="json")
            previous = latest.get(record["report_id"])
            if previous is None or record["version"] > previous["version"]:
                latest[record["report_id"]] = record
        return [latest[name] for name in sorted(latest) if candidate in latest[name]["candidate_ids"]]

    def test_frozen_identity_and_separate_source_use_are_exact(self):
        self.assertEqual(file_sha256(self.path), self.anchor)
        validated = validate_artifact(self.path)
        self.assertEqual(validated.model_dump(mode="json"), self.manifest.model_dump(mode="json"))
        self.assertEqual(public_identity(self.raw_manifest)["source_records_sha256"],
                         self.raw_manifest["public_extract"]["source_use"]["draft_sha256"])
        self.assertEqual(os.environ["CALDOVA_ACCEPTANCE_PURPOSE"], PUBLIC_PURPOSE)

    def test_metadata_shape_candidates_coverage_and_citations(self):
        metadata = self.get_json("/api/metadata")
        self.assertEqual(set(metadata), {"manifest", "candidates", "preview_state", "fixture_warning"})
        self.assertEqual(metadata["manifest"], self.manifest.model_dump(mode="json"))
        self.assertEqual(metadata["candidates"], self.candidates)
        self.assertEqual(metadata["preview_state"], "reference")
        self.assertIsNone(metadata["fixture_warning"])
        sources = {source["source_id"] for source in self.draft["sources"]}
        for original in [*self.draft["trials"], *self.draft["safety_reports"]]:
            self.assertIn(original["source_id"], sources)
            self.assertTrue(original["source_record_id"])
            self.assertTrue(original["source_url"].startswith("https://"))

    def test_all_filters_retain_complete_original_trial_projections(self):
        for candidate in self.candidates:
            for condition in self.conditions:
                with self.subTest(candidate=candidate["candidate_id"], condition=condition):
                    response = self.research(candidate["candidate_id"], condition)
                    self.assertEqual(set(response), {
                        "status", "candidate", "condition", "dataset_version", "trials",
                        "safety_reports", "limitations", "fixture_warning",
                    })
                    self.assertEqual(response["status"], "ready")
                    self.assertEqual(response["candidate"], candidate)
                    self.assertEqual(response["condition"], condition)
                    self.assertEqual(response["dataset_version"], self.manifest.dataset_version)
                    self.assertEqual(response["trials"], self.expected_trials(candidate["candidate_id"], condition))
                    self.assertEqual(response["limitations"], LIMITATIONS)
                    self.assertIsNone(response["fixture_warning"])

    def test_complete_safety_projections_and_honest_empty_coverage(self):
        empty = []
        for candidate in self.candidates:
            name = candidate["candidate_id"]
            expected = self.expected_reports(name)
            response = self.research(name)
            self.assertEqual(response["safety_reports"], expected)
            if not expected:
                empty.append(name)
                self.assertEqual(self.raw_manifest["public_extract"]["report_candidate_counts"].get(name, 0), 0)
                self.assertEqual(response["status"], "ready")
        self.assertTrue(empty, "The selected public slice must retain honest empty report coverage.")

    def test_trial_condition_filter_never_filters_safety(self):
        for candidate in self.candidates:
            name = candidate["candidate_id"]
            expected = self.expected_reports(name)
            for condition in self.conditions:
                self.assertEqual(self.research(name, condition)["safety_reports"], expected)

    def test_source_endpoint_preserves_original_flags_arrays_and_decision(self):
        response = self.get_json("/api/source-records")
        self.assertEqual(set(response), {"dataset_version", "source_use_decision", "note", "original_extraction"})
        self.assertEqual(response["original_extraction"], self.draft)
        self.assertEqual(response["source_use_decision"], self.raw_manifest["public_extract"]["source_use"])
        self.assertFalse(response["original_extraction"]["source_review_approved"])
        self.assertFalse(response["original_extraction"]["attendee_release_approved"])
        self.assertEqual(response["dataset_version"], self.manifest.dataset_version)
        self.assertIn("historical", response["note"].lower())

    def test_unknown_candidate_and_invalid_condition_are_rejected(self):
        for path, status in (
            ("/api/research?candidate=not-a-frozen-candidate", 404),
            ("/api/research?candidate=" + self.candidates[0]["candidate_id"] + "&condition=invalid", 422),
        ):
            with self.assertRaises(HTTPError) as error:
                self.get_json(path)
            self.assertEqual(error.exception.code, status)

    def test_image_default_is_genuinely_unavailable_or_accepted_reference(self):
        expected_state = os.environ.get("CALDOVA_EXPECTED_PREVIEW_STATE", "reference")
        with api_server(8098, None) as base_url:
            health = self.get_json("/health", base_url)
            self.assertEqual(health, {
                "status": "healthy", "dataset_version": self.manifest.dataset_version,
                "dataset_kind": "reviewed-public", "preview_state": expected_state,
            })
            candidate = self.candidates[0]["candidate_id"]
            response = self.research(candidate, base_url=base_url)
        self.assertIsNone(response["fixture_warning"])
        self.assertEqual(response["limitations"], LIMITATIONS)
        if expected_state == "starter":
            self.assertEqual(response["status"], "unavailable")
            self.assertEqual(response["trials"], [])
            self.assertEqual(response["safety_reports"], [])
        else:
            self.assertEqual(expected_state, "reference")
            self.assertEqual(response["status"], "ready")
            self.assertEqual(response["trials"], self.expected_trials(candidate, None))
            self.assertEqual(response["safety_reports"], self.expected_reports(candidate))


if __name__ == "__main__":
    unittest.main()
