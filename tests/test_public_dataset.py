import json
import os
import sys
import unittest
import zipfile
from types import SimpleNamespace
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import patch

import duckdb
from pydantic import ValidationError

import test_public_extract as fixtures
from test_research import api_server
from data.pipeline import freeze_public as freezer
from data.pipeline.contracts import SourceUseApproval
from data.pipeline.stage_dataset import stage_dataset
from data.pipeline.validate_dataset import file_sha256, read_pipeline_snapshot, validate_artifact

ROOT = Path(__file__).resolve().parents[1]
class PublicDatasetTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PublicExtractTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.fixture.extract()
        self.draft_directory = self.fixture.output
        self.output = self.fixture.root / "public-artifact"
        self.approval_path = self.fixture.root / "source-use.json"
        self.provenance = json.loads((self.draft_directory / "draft-provenance.json").read_text())
        self.approval = SourceUseApproval(
            approved_by="Fictional unit-test project owner", approved_at=datetime.now(timezone.utc),
            scope="project-owner-selected-public-lab-use",
            draft_sha256=file_sha256(self.draft_directory / "public-review-draft.json"),
            draft_provenance_sha256=file_sha256(self.draft_directory / "draft-provenance.json"),
            instruction="Use the exact fictional test slice for a local lab artifact.",
        )
        self.approval_path.write_text(self.approval.model_dump_json(indent=2) + "\n", encoding="utf-8")

    def freeze(self, output=None):
        with patch.object(freezer, "load_source", return_value=self.provenance["aact_input"]), patch.object(
            freezer, "load_openfda_pin", return_value=self.provenance["openfda_input"]
        ):
            return freezer.freeze_public(
                self.draft_directory, self.approval_path, output or self.output, "fictional-public-test-v1",
            )

    def rewrite_manifest(self, update):
        path = self.output / "data-manifest.json"
        content = json.loads(path.read_text())
        update(content)
        path.write_text(json.dumps(content), encoding="utf-8")

    def test_freeze_and_staging_preserve_original_bytes_and_honest_working_tree_identity(self):
        manifest = self.freeze()
        self.assertEqual(manifest.dataset_kind, "reviewed-public")
        self.assertFalse(manifest.has_committed_pipeline)
        self.assertFalse(manifest.public_extract.source_use.expert_audit_performed)
        self.assertEqual(
            (self.output / manifest.source_records.path).read_bytes(),
            (self.draft_directory / "public-review-draft.json").read_bytes(),
        )
        snapshot = read_pipeline_snapshot(self.output / manifest.pipeline_source.path)
        self.assertEqual(snapshot["data/pipeline/freeze_public.py"], (ROOT / "data" / "pipeline" / "freeze_public.py").read_bytes())
        self.assertEqual(snapshot["draft-provenance.json"], (self.draft_directory / "draft-provenance.json").read_bytes())
        staged = self.fixture.root / "staged"
        stage_dataset(str(self.output / "data-manifest.json"), staged, file_sha256(self.output / "data-manifest.json"))
        for name in ("data-manifest.json", manifest.database.path, manifest.source_records.path, manifest.pipeline_source.path):
            self.assertEqual((self.output / name).read_bytes(), (staged / name).read_bytes())
        validate_artifact(staged / "data-manifest.json")
        with self.assertRaises(FileExistsError):
            self.freeze()

    def test_committed_snapshot_requires_every_allowlisted_file_to_match_git_bytes(self):
        snapshot = self.fixture.root / "committed.zip"
        commit = "b" * 40

        def committed_source(arguments, **kwargs):
            name = arguments[-1].split(":", 1)[1]
            return SimpleNamespace(stdout=(ROOT / name).read_bytes())

        with patch.object(freezer.subprocess, "run", side_effect=committed_source):
            freezer.snapshot_sources(snapshot, {}, commit)
        inventory = json.loads(read_pipeline_snapshot(snapshot)["pipeline-source.json"])
        self.assertEqual(inventory["source_kind"], "git-commit")
        self.assertEqual(inventory["source_revision"], commit)
        invalid = self.fixture.root / "invalid-commit.zip"
        with patch.object(freezer.subprocess, "run", return_value=SimpleNamespace(stdout=b"wrong bytes")):
            with self.assertRaisesRegex(ValueError, "differs from the specified Git commit"):
                freezer.snapshot_sources(invalid, {}, commit)
        self.assertFalse(invalid.exists())

    def test_mismatched_decision_provenance_and_unsafe_output_publish_nothing(self):
        for fault in ("draft", "provenance", "approval-state", "chronology", "output"):
            with self.subTest(fault=fault):
                content = self.approval.model_dump(mode="json")
                if fault == "draft":
                    content["draft_sha256"] = "a" * 64
                elif fault == "provenance":
                    content["draft_provenance_sha256"] = "b" * 64
                elif fault == "approval-state":
                    content["publication_authorized"] = True
                elif fault == "chronology":
                    content["approved_at"] = "2000-01-01T00:00:00Z"
                self.approval_path.write_text(json.dumps(content))
                output = ROOT / ".unsupported-public-freeze" if fault == "output" else self.output
                with self.assertRaises(ValueError):
                    self.freeze(output)
                self.assertFalse(output.exists())
        content = self.approval.model_dump(mode="json")
        content["approved_at"] = "2026-10-10T00:00:00"
        with self.assertRaisesRegex(ValidationError, "time zone"):
            SourceUseApproval.model_validate(content)

    def test_tampered_database_and_auxiliary_files_cannot_pass_hash_only_or_stage(self):
        manifest = self.freeze()
        database = self.output / manifest.database.path
        original_database = database.read_bytes()
        with duckdb.connect(str(database)) as connection:
            connection.execute("UPDATE safety_reports SET source_url='https://example.invalid/changed' WHERE report_id='R01'")
        self.rewrite_manifest(lambda value: value["database"].update(
            sha256=file_sha256(database), bytes=database.stat().st_size,
        ))
        with self.assertRaisesRegex(ValueError, "complete frozen source projection"):
            validate_artifact(self.output / "data-manifest.json")
        database.write_bytes(original_database)
        self.rewrite_manifest(lambda value: value["database"].update(
            sha256=file_sha256(database), bytes=database.stat().st_size,
        ))
        for artifact in (manifest.source_records, manifest.pipeline_source):
            path = self.output / artifact.path
            original = path.read_bytes()
            path.write_bytes(original + b"corruption")
            try:
                with self.assertRaisesRegex(ValueError, "size does not match"):
                    stage_dataset(str(self.output / "data-manifest.json"), self.fixture.root / "invalid-stage", None)
                self.assertFalse((self.fixture.root / "invalid-stage").exists())
            finally:
                path.write_bytes(original)
        snapshot = self.output / manifest.pipeline_source.path
        with zipfile.ZipFile(snapshot, "a") as archive:
            archive.writestr("../outside.py", b"Do not extract or execute this fictional test entry.")
        self.rewrite_manifest(lambda value: value["pipeline_source"].update(
            sha256=file_sha256(snapshot), bytes=snapshot.stat().st_size,
        ))
        with self.assertRaisesRegex(ValueError, "unsafe member"):
            validate_artifact(self.output / "data-manifest.json")

    def test_api_retains_complete_source_arrays_empty_safety_and_condition_independence(self):
        self.freeze()
        static = self.fixture.root / "static"
        static.mkdir()
        (static / "index.html").write_text("<html>Fictional public test portal</html>")
        with patch.dict(os.environ, {
            "CALDOVA_DATA_DIR": str(self.output), "CALDOVA_STATIC_DIR": str(static),
            "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
        }):
            with api_server(8097, "reference") as base_url:
                def get_json(path):
                    with urlopen(base_url + path, timeout=10) as response:
                        return json.load(response)

                metadata = get_json("/api/metadata")
                self.assertIsNone(metadata["fixture_warning"])
                self.assertEqual(metadata["manifest"]["public_extract"]["source_use"]["scope"], self.approval.scope)
                obesity = get_json("/api/research?candidate=semaglutide&condition=obesity")
                diabetes = get_json("/api/research?candidate=semaglutide&condition=type-2-diabetes")
                self.assertNotEqual(obesity["trials"], diabetes["trials"])
                self.assertEqual(obesity["safety_reports"], diabetes["safety_reports"])
                shared = next(item for item in obesity["trials"] if item["trial_id"] == "NCT00000001")
                self.assertEqual(shared["candidate_ids"], ["liraglutide", "semaglutide"])
                self.assertEqual(shared["source_conditions"], [" Unmapped source condition ", "Obesity", "Type 2 Diabetes"])
                self.assertEqual([item["name"] for item in shared["source_interventions"]], [" Semaglutide ", "LIRAGLUTIDE"])
                report = next(item for item in obesity["safety_reports"] if item["report_id"] == "R01")
                self.assertEqual(report["candidate_ids"], ["liraglutide", "semaglutide"])
                self.assertEqual(report["original_reaction_terms"], [" Nausea ", "nausea", "Fatigue"])
                self.assertEqual(report["reaction_terms"], ["FATIGUE", "NAUSEA"])
                self.assertEqual([item["medicinalproduct"] for item in report["source_drugs"]], ["SEMAGLUTIDE", "Liraglutide"])
                empty = get_json("/api/research?candidate=tirzepatide")
                self.assertTrue(empty["trials"])
                self.assertEqual(empty["safety_reports"], [])
                with urlopen(base_url + "/api/source-records", timeout=10) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers["cache-control"], "no-store")
                    projections = json.load(response)
                self.assertEqual(projections["source_use_decision"], self.approval.model_dump(mode="json"))
                self.assertFalse(projections["original_extraction"]["source_review_approved"])
                for path, status in (
                    ("/api/research?candidate=unknown", 404),
                    ("/api/research?candidate=semaglutide&condition=invalid", 422),
                ):
                    with self.assertRaises(HTTPError) as error:
                        get_json(path)
                    self.assertEqual(error.exception.code, status)
                self.assertIn("do not establish causation", obesity["limitations"])


if __name__ == "__main__":
    unittest.main()
