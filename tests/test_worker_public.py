"""Native public packaging regressions: fictional bytes are never imported or executed."""

import copy
import importlib.util
import json
import os
import re
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_candidate as fixtures
from src.workers.frozen_contract import PUBLIC_PURPOSE, acceptance_selection, canonical_hash, public_identity

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("public_source_export", ROOT / "src/developer-image/export_source.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
packager = fixtures.packager


class PublicPackagingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CandidatePackagingTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.workspace = self.fixture.workspace
        self.directory = self.fixture.frozen
        approval = {
            "schema_version": "1.0", "approved_by": "Fictional test project owner",
            "approved_at": "2026-10-10T05:17:00Z", "scope": "project-owner-selected-public-lab-use",
            "draft_sha256": "", "draft_provenance_sha256": "", "instruction": "Use the fictional test slice.",
            "expert_audit_performed": False, "publication_authorized": False,
            "live_replacement_authorized": False, "attendee_release_approved": False,
        }
        candidate = {"candidate_id": "test-candidate", "name": "Fictional candidate", "research_area": "Software test"}
        self.draft = {
            "built_at": "2026-10-10T05:00:00Z", "source_review_approved": False,
            "attendee_release_approved": False, "candidates": [candidate],
            "trials": [{"trial_id": "TEST-TRIAL"}], "safety_reports": [],
            "trial_bucket_counts": {"test-candidate/obesity": 1}, "report_candidate_counts": {},
            "source_quality_counts": {}, "mapping_version": "conservative-exact-generics-v1",
            "coverage_notes": ["Historical draft", "One shard only; no clinical coverage claim."],
        }
        packager.write_json(self.directory / "source-records.json", self.draft)
        approval["draft_sha256"] = packager.file_sha256(self.directory / "source-records.json")
        self.provenance = {
            "draft_sha256": approval["draft_sha256"],
            "draft_bytes": (self.directory / "source-records.json").stat().st_size,
            "trial_count": 1, "report_count": 0, "trial_bucket_counts": self.draft["trial_bucket_counts"],
            "report_candidate_counts": {},
        }
        provenance_bytes = json.dumps(self.provenance).encode()
        approval["draft_provenance_sha256"] = packager.sha256_bytes(provenance_bytes)
        self.manifest = copy.deepcopy(self.fixture.manifest)
        self.manifest.update(
            dataset_kind="reviewed-public", pipeline_commit="uncommitted-development",
            review={name: approval[name] for name in ("approved_by", "approved_at")},
            public_extract={
                "source_use": approval, "mapping_version": self.draft["mapping_version"],
                "coverage_notes": ["Project-owner selected lab use", *self.draft["coverage_notes"][1:]],
                "trial_bucket_counts": self.draft["trial_bucket_counts"],
                "report_candidate_counts": {}, "source_quality_counts": {},
            },
        )
        self.manifest["sources"][0].update(url="https://example.invalid/fictional-source", retrieved_at="2026-10-10T05:00:00Z")
        self.data = {
            "dataset_version": self.manifest["dataset_version"], "dataset_kind": "reviewed-public",
            "review": self.manifest["review"], "public_extract": self.manifest["public_extract"],
            "sources": self.manifest["sources"], "candidates": [candidate],
        }
        self.manifest["logical_sha256"] = canonical_hash(self.data)
        self.contents = {
            "dataset-input.json": json.dumps(self.data).encode(),
            "source-use-approval.json": json.dumps(approval).encode(),
            "draft-provenance.json": provenance_bytes,
        }
        for path in (self.fixture.root / "data/pipeline").glob("*.py"):
            self.contents[path.relative_to(self.fixture.root).as_posix()] = path.read_bytes()
        self.write_snapshot()
        self.bind_identity()

    def write_snapshot(self):
        content = dict(self.contents)
        content["pipeline-source.json"] = json.dumps({
            "schema_version": "1.0", "source_kind": "uncommitted-working-tree",
            "files": {name: packager.sha256_bytes(value) for name, value in content.items()},
        }).encode()
        with zipfile.ZipFile(self.directory / "pipeline-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for name, value in content.items():
                archive.writestr(name, value)

    def bind_identity(self):
        for field, filename in (("source_records", "source-records.json"), ("pipeline_source", "pipeline-source.zip")):
            path = self.directory / filename
            self.manifest[field] = {"path": filename, "bytes": path.stat().st_size, "sha256": packager.file_sha256(path)}
        packager.write_json(self.directory / "data-manifest.json", self.manifest)
        anchor = packager.file_sha256(self.directory / "data-manifest.json")
        self.fixture.manifest_sha = anchor
        identity = public_identity(self.manifest)
        baseline = self.fixture.baseline
        baseline.update(dataset_kind="reviewed-public", data_manifest_sha256=anchor,
                        acceptance_purpose=PUBLIC_PURPOSE, public_identity=identity)
        for path in self.directory.iterdir():
            baseline["protected_files"][f"data/artifacts/development/{path.name}"] = packager.file_sha256(path)
        packager.write_json(self.workspace / "prepared-baseline.json", baseline)
        descriptor = self.fixture.descriptor
        descriptor.update(dataset_kind="reviewed-public", acceptance_purpose=PUBLIC_PURPOSE)
        descriptor["frozen_identity"].update(
            logical_sha256=self.manifest["logical_sha256"], data_manifest_sha256=anchor,
            baseline_manifest_sha256=packager.file_sha256(self.workspace / "prepared-baseline.json"),
            **identity,
        )
        packager.write_json(self.fixture.descriptor_path, descriptor)
        self.fixture.result["plan"]["logical_sha256"] = self.manifest["logical_sha256"]
        for worker in self.fixture.result["workers"]:
            worker["logical_sha256"] = self.manifest["logical_sha256"]
        self.fixture.save_result()

    def options(self, name="public-candidate"):
        return {**self.fixture.options(name), "purpose": PUBLIC_PURPOSE}

    def test_native_public_stage_preserves_every_frozen_file_and_separate_suite(self):
        staged = packager.stage_candidate(**self.options())
        root = Path(staged["directory"])
        for path in self.directory.iterdir():
            self.assertEqual((root / "data/artifacts/development" / path.name).read_bytes(), path.read_bytes())
        self.assertEqual(staged["frozen_identity"], self.fixture.descriptor["frozen_identity"])
        self.assertEqual(staged["validation_contract"]["test_pattern"], "test_frozen_public_research.py")
        self.assertEqual(staged["validation_contract"]["tests_required"], 8)
        self.assertTrue(staged["validation_contract"]["original_synthetic_tests_preserved"])
        self.assertFalse(staged["human_approval"])
        self.assertFalse(staged["release_approved"])
        self.assertFalse(staged["deployed"])
        self.assertEqual((root / "tests/test_research.py").read_bytes(),
                         (self.fixture.root / "tests/test_research.py").read_bytes())
        packager.verify_context(root, staged["provenance_sha256"])

    def test_public_branch_cannot_be_inferred_or_relabelled_from_review(self):
        for purpose in ("synthetic-development", "attendee-release", None):
            with self.subTest(purpose=purpose), self.assertRaises(ValueError):
                packager.stage_candidate(**{**self.options(), "purpose": purpose})
        self.manifest["dataset_kind"] = "synthetic-development"
        with self.assertRaises(ValueError):
            acceptance_selection(self.manifest, "synthetic-development")
        self.assertFalse(self.options()["destination"].exists())

    def test_missing_modified_original_or_zip_and_incomplete_public_pins_fail_closed(self):
        for field in ("source_records", "pipeline_source"):
            path = self.directory / self.manifest[field]["path"]
            original = path.read_bytes()
            for fault in ("modified", "missing"):
                with self.subTest(field=field, fault=fault):
                    if fault == "modified":
                        path.write_bytes(original + b"x")
                    else:
                        path.unlink()
                    with self.assertRaises(ValueError):
                        packager.stage_candidate(**self.options())
                    self.assertFalse(self.options()["destination"].exists())
                    path.write_bytes(original)
        self.fixture.descriptor["frozen_identity"].pop("source_use_sha256")
        packager.write_json(self.fixture.descriptor_path, self.fixture.descriptor)
        with self.assertRaisesRegex(ValueError, "frozen identity"):
            packager.stage_candidate(**self.options())

    def test_scope_flags_review_identity_and_historical_flags_cannot_be_widened(self):
        original = copy.deepcopy(self.manifest)
        for fault in ("scope", "publication", "review", "historical"):
            with self.subTest(fault=fault):
                self.manifest = copy.deepcopy(original)
                if fault == "scope":
                    self.manifest["public_extract"]["source_use"]["scope"] = "attendee-release"
                elif fault == "publication":
                    self.manifest["public_extract"]["source_use"]["publication_authorized"] = True
                elif fault == "review":
                    self.manifest["review"]["approved_by"] = "Different fictional reviewer"
                else:
                    self.draft["source_review_approved"] = True
                    packager.write_json(self.directory / "source-records.json", self.draft)
                    self.manifest["public_extract"]["source_use"]["draft_sha256"] = \
                        packager.file_sha256(self.directory / "source-records.json")
                self.bind_identity()
                with self.assertRaises(ValueError):
                    packager.stage_candidate(**self.options())
                self.assertFalse(self.options()["destination"].exists())

    def test_frozen_pipeline_is_checked_against_packaging_inputs_not_executed(self):
        path = self.fixture.root / "data/pipeline/contracts.py"
        path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "Frozen pipeline differs"):
            packager.stage_candidate(**self.options())
        self.assertFalse(self.options()["destination"].exists())
        self.assertNotIn("duckdb", exporter.__dict__)

    def test_native_public_export_never_rebuilds_and_rejects_tampered_auxiliary(self):
        destination = self.workspace / "export"
        manifest_path = self.directory / "data-manifest.json"
        # Export checks the actual pipeline bytes in the trusted checkout, without importing them.
        for name in self.contents:
            if name.startswith("data/pipeline/"):
                self.contents[name] = (ROOT / name).read_bytes()
        self.write_snapshot()
        self.bind_identity()
        result = exporter.stage_frozen_data(str(manifest_path), destination,
                                           self.fixture.manifest_sha, PUBLIC_PURPOSE)
        self.assertEqual(result, self.manifest)
        for path in self.directory.iterdir():
            self.assertEqual((destination / path.name).read_bytes(), path.read_bytes())
        (self.directory / "pipeline-source.zip").write_bytes(b"not the pinned source ZIP")
        with self.assertRaises(ValueError):
            exporter.stage_frozen_data(str(manifest_path), self.workspace / "bad-export",
                                       self.fixture.manifest_sha, PUBLIC_PURPOSE)

    def test_retained_synthetic_reuse_does_not_require_new_public_image_helpers(self):
        source = (ROOT / "scripts/prepare-worker-baseline.ps1").read_text()
        embedded = re.search(r"\$python = @'\n(.*?)\n'@", source, re.S).group(1)
        segment = embedded[embedded.index("manifest = baseline.validate_artifact(manifest_path)"):
                           embedded.index("manifest_sha = hashlib.sha256(manifest_bytes)")]
        manifest = SimpleNamespace(dataset_kind="synthetic-development", review=None)
        legacy = SimpleNamespace(validate_artifact=lambda _: manifest)
        values = {
            "baseline": legacy, "manifest_path": Path("not-opened"),
            "record": {"dataset_kind": "synthetic-development"}, "os": os, "PURPOSE": "synthetic-development",
        }
        with patch.dict(os.environ):
            exec(compile(segment, "<legacy-synthetic-reuse>", "exec"), values)
            self.assertEqual(values["manifest"].dataset_kind, "synthetic-development")
        values["PURPOSE"] = "public-lab-development"
        values["record"]["data_manifest_sha256"] = "0" * 64
        with patch.dict(os.environ), self.assertRaises(AttributeError):
            exec(compile(segment, "<public-requires-new-baseline>", "exec"), values)


if __name__ == "__main__":
    unittest.main()
