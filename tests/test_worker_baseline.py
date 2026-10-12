import importlib.util
import hashlib
import json
import os
import shutil
import sys
import unittest
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from data.pipeline.build_dataset import build_dataset, normalize_reports
from data.pipeline.contracts import DatasetInput, PublicExtract, Review, SourceUseApproval
from data.pipeline.extract_public import PublicDraft
from data.pipeline.validate_dataset import file_sha256
from src.workers.frozen_contract import PUBLIC_PURPOSE
import test_source_export as exports

ROOT = Path(__file__).resolve().parents[1]


def public_fixture(workspace):
    """Fictional records exercise the public contract without downloading or approving real sources."""
    data = DatasetInput.model_validate_json((ROOT / "data/fixtures/research-data.json").read_bytes())
    values = data.model_dump(mode="json")
    for source in values["sources"]:
        source.update(url="https://example.invalid/fictional-source", retrieved_at="2026-10-09T00:00:00Z")
    for item in [*values["trials"], *values["safety_reports"]]:
        item["source_url"] = "https://example.invalid/fictional-record/" + item["source_record_id"]
    values["safety_reports"] = [item.model_dump(mode="json") for item in normalize_reports(
        DatasetInput.model_validate(values).safety_reports
    )]
    trial_counts = dict(Counter(f"{candidate}/{condition}" for item in values["trials"]
                               for candidate in item["candidate_ids"] for condition in item["conditions"]))
    report_counts = dict(Counter(candidate for item in values["safety_reports"] for candidate in item["candidate_ids"]))
    draft = PublicDraft.model_validate({
        "built_at": "2026-10-09T00:00:00Z", "sources": values["sources"], "candidates": values["candidates"],
        "trials": [{
            **item, "source_conditions": [*item["conditions"], " Unmapped fictional condition "],
            "source_interventions": [{
                "intervention_id": index + 1, "candidate_id": item["candidate_ids"][0],
                "name": " Fictional intervention ", "intervention_type": "DRUG",
            }],
        } for index, item in enumerate(values["trials"])],
        "safety_reports": [{
            **item, "original_reaction_terms": [" fictional reaction ", *item["reaction_terms"]],
            "source_drugs": [{
                "candidate_ids": item["candidate_ids"], "medicinalproduct": " FICTIONAL ",
                "generic_names": [" Fictional generic "], "brand_names": [], "substance_names": [],
            }],
        } for item in values["safety_reports"]],
        "trial_bucket_counts": trial_counts, "report_candidate_counts": report_counts,
        "source_quality_counts": {}, "coverage_notes": ["Historical draft", "Fictional one-shard test only."],
    })
    original = workspace / "source-records.json"
    original.write_text(draft.model_dump_json(indent=2) + "\n")
    provenance = json.dumps({
        "draft_sha256": file_sha256(original), "draft_bytes": original.stat().st_size,
        "trial_count": len(draft.trials), "report_count": len(draft.safety_reports),
        "trial_bucket_counts": trial_counts, "report_candidate_counts": report_counts,
    }).encode()
    approval = SourceUseApproval(
        approved_by="Fictional software-test owner", approved_at=datetime.now(timezone.utc),
        scope="project-owner-selected-public-lab-use", draft_sha256=file_sha256(original),
        draft_provenance_sha256=hashlib.sha256(provenance).hexdigest(),
        instruction="Use only the invented software-test records.",
    )
    values.update(dataset_kind="reviewed-public", review=Review(
        approved_by=approval.approved_by, approved_at=approval.approved_at,
    ).model_dump(mode="json"), public_extract=PublicExtract(
        source_use=approval, mapping_version=draft.mapping_version,
        coverage_notes=["Fictional owner decision", *draft.coverage_notes[1:]],
        trial_bucket_counts=trial_counts, report_candidate_counts=report_counts, source_quality_counts={},
    ).model_dump(mode="json"))
    data = DatasetInput.model_validate(values)
    input_path = workspace / "dataset-input.json"
    input_path.write_text(data.model_dump_json(indent=2) + "\n")
    content = {
        path.relative_to(ROOT).as_posix(): path.read_bytes()
        for path in (ROOT / "data/pipeline").glob("*.py")
    }
    content.update({
        "dataset-input.json": input_path.read_bytes(), "source-use-approval.json": approval.model_dump_json().encode(),
        "draft-provenance.json": provenance,
    })
    content["pipeline-source.json"] = json.dumps({
        "schema_version": "1.0", "source_kind": "uncommitted-working-tree",
        "files": {name: hashlib.sha256(value).hexdigest() for name, value in content.items()},
    }).encode()
    snapshot = workspace / "pipeline-source.zip"
    with zipfile.ZipFile(snapshot, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in content.items():
            archive.writestr(name, value)
    return input_path, original, snapshot


class WorkerBaselineTests(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / ".validation-workspaces" / ("baseline-" + uuid4().hex)
        self.workspace.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.workspace)
        self.root = self.workspace / "source"
        exports.exporter.export_context(self.root, "fictional-baseline-test")
        spec = importlib.util.spec_from_file_location("worker_baseline_test", self.root / "src/developer-image/baseline.py")
        self.baseline = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.baseline)
        frontend = self.root / "src/research-portal/frontend"
        shutil.copytree(ROOT / "src/research-portal/frontend/dist", frontend / "dist")
        tsc = frontend / "node_modules/typescript/bin/tsc"
        tsc.parent.mkdir(parents=True)
        tsc.write_text("Fictional dependency-presence test; not executed.")
        for relative in self.baseline.EDITABLE_MODULES.values():
            path = self.root / relative
            shutil.copyfile(self.root / "src/workers/starter" / path.name, path)
        self.modules = ["app", "trial_feature", "safety_feature", "queries"]
        self.saved_modules = {name: sys.modules.pop(name) for name in self.modules if name in sys.modules}
        self.saved_path = sys.path[:]
        self.addCleanup(self.restore_imports)
        self.addCleanup(patch.stopall)
        # Production verification requires real Python 3.13, Node 24 and read-only root ownership.
        # These local unit tests exercise the checker, not an imported UID-10001 image receipt.
        patch.object(self.baseline, "toolchains", return_value={"python": "3.13.16", "node": "v24.21.0"}).start()
        patch.object(self.baseline.os, "geteuid", return_value=10001).start()
        editable = {self.root / relative for relative in self.baseline.EDITABLE_MODULES.values()}
        patch.object(self.baseline.os, "access", side_effect=lambda path, mode: Path(path) in editable).start()

    def restore_imports(self):
        for name in self.modules:
            sys.modules.pop(name, None)
        sys.modules.update(self.saved_modules)
        sys.path[:] = self.saved_path

    def prepare(self, public):
        destination = self.baseline.MANIFEST_PATH.parent
        if public:
            input_path, original, snapshot = public_fixture(self.workspace)
            build_dataset(input_path, destination, "uncommitted-development",
                          source_records=original, pipeline_source=snapshot)
        else:
            build_dataset(ROOT / "data/fixtures/research-data.json", destination, "fictional-baseline-test")
        patch.dict(os.environ, {
            "CALDOVA_DATA_DIR": str(destination), "CALDOVA_STATIC_DIR": str(self.baseline.FRONTEND / "dist"),
            "CALDOVA_ACCEPTANCE_PURPOSE": PUBLIC_PURPOSE if public else "synthetic-development",
            "CALDOVA_DATA_MANIFEST_SHA256": file_sha256(self.baseline.MANIFEST_PATH),
        }).start()

    def test_public_baseline_protects_all_four_files_and_checks_truly_missing_functions(self):
        self.prepare(True)
        self.baseline.record_baseline("fictional-baseline-test")
        receipt = self.baseline.verify_baseline()
        self.assertEqual(receipt["dataset_kind"], "reviewed-public")
        self.assertEqual(receipt["acceptance_purpose"], PUBLIC_PURPOSE)
        self.assertEqual(receipt["reference_state"], "NotImplementedError")
        record = json.loads(self.baseline.BASELINE_PATH.read_bytes())
        for name in ("data-manifest.json", "caldova-research.duckdb", "source-records.json", "pipeline-source.zip"):
            self.assertEqual(record["protected_files"]["data/artifacts/development/" + name],
                             file_sha256(self.baseline.MANIFEST_PATH.parent / name))
        with self.assertRaises(FileExistsError):
            self.baseline.record_baseline("no-overwrite")

    def test_synthetic_baseline_remains_unapproved_and_incomplete(self):
        self.prepare(False)
        self.baseline.record_baseline("fictional-baseline-test")
        receipt = self.baseline.verify_baseline()
        self.assertEqual(receipt["dataset_kind"], "synthetic-development")
        self.assertNotIn("public_identity", json.loads(self.baseline.BASELINE_PATH.read_bytes()))

    def test_matching_starter_bytes_with_a_working_function_cannot_pass_missing_oracle(self):
        self.prepare(True)
        for relative in self.baseline.EDITABLE_MODULES.values():
            path = self.root / relative
            function = "query_trials(connection, candidate, condition)" if path.name == "trial_feature.py" else "query_safety_reports(connection, candidate)"
            content = f"def {function}:\n    return []\n"
            path.write_text(content)
            (self.root / "src/workers/starter" / path.name).write_text(content)
        self.baseline.record_baseline("fictional-baseline-test")
        with self.assertRaisesRegex(ValueError, "unexpectedly contains a working query"):
            self.baseline.verify_baseline()

    def test_public_requires_explicit_purpose_pin_and_unmodified_original_bytes(self):
        self.prepare(True)
        with patch.dict(os.environ, {"CALDOVA_ACCEPTANCE_PURPOSE": "synthetic-development"}), self.assertRaises(ValueError):
            self.baseline.record_baseline("fictional-baseline-test")
        with patch.dict(os.environ, {"CALDOVA_DATA_MANIFEST_SHA256": "0" * 64}), self.assertRaises(ValueError):
            self.baseline.record_baseline("fictional-baseline-test")
        self.assertFalse(self.baseline.BASELINE_PATH.exists())
        self.baseline.record_baseline("fictional-baseline-test")
        original = self.baseline.MANIFEST_PATH.parent / "source-records.json"
        original.write_bytes(original.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "size does not match"):
            self.baseline.verify_baseline()


if __name__ == "__main__":
    unittest.main()
