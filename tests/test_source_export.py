import importlib.util
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from data.pipeline.build_dataset import build_dataset
from data.pipeline.stage_dataset import stage_dataset
from data.pipeline.validate_dataset import file_sha256

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "source_export", ROOT / "src" / "developer-image" / "export_source.py"
)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class FrozenSourceExportTests(unittest.TestCase):
    def setUp(self):
        self.workspace = ROOT / ".build-contexts" / f"source-test-{uuid4().hex}"
        self.workspace.mkdir(parents=True)
        self.source = self.workspace / "dataset"
        self.manifest = build_dataset(
            ROOT / "data" / "fixtures" / "research-data.json", self.source, "synthetic-test"
        )
        self.manifest_path = self.source / "data-manifest.json"
        self.manifest_sha = file_sha256(self.manifest_path)

    def tearDown(self):
        shutil.rmtree(self.workspace)

    def test_frozen_export_and_container_staging_preserve_every_artifact_byte(self):
        destination = self.workspace / "export"
        with patch("data.pipeline.build_dataset.build_dataset", side_effect=AssertionError("No rebuild")):
            result = exporter.export_context(
                destination, "synthetic-test", str(self.manifest_path), self.manifest_sha
            )
            frozen = destination / "data" / "artifacts" / "development"
            staged = self.workspace / "image-data"
            stage_dataset(str(frozen / "data-manifest.json"), staged, self.manifest_sha)
        for name in ("data-manifest.json", self.manifest.database.path):
            expected = (self.source / name).read_bytes()
            self.assertEqual((frozen / name).read_bytes(), expected)
            self.assertEqual((staged / name).read_bytes(), expected)
        dockerfile = (destination / "Dockerfile").read_text()
        self.assertNotIn("RUN python -m data.pipeline.build_dataset", dockerfile)
        self.assertIn("RUN python -m data.pipeline.stage_dataset", dockerfile)
        self.assertIn(f"--manifest-sha256 {self.manifest_sha}", dockerfile)
        self.assertIn("python -m unittest discover -s tests -p test_research.py", dockerfile)
        self.assertIn("USER caldova", dockerfile)
        self.assertEqual(result["frozen_data"]["database_sha256"], self.manifest.database.sha256)
        self.assertEqual(result["frozen_data"]["data_manifest_sha256"], self.manifest_sha)
        record = json.loads((destination / "source-context.json").read_text())
        self.assertEqual(record["frozen_data"], result["frozen_data"])
        logo = "src/research-portal/frontend/src/assets/caldova-logo.svg"
        self.assertEqual((destination / logo).read_bytes(), (ROOT / logo).read_bytes())
        self.assertEqual(record["files"][logo], file_sha256(ROOT / logo))
        for name, digest in record["files"].items():
            self.assertEqual(file_sha256(destination / name), digest)

    def test_bad_anchor_corrupt_database_and_changed_template_publish_no_context(self):
        for fault in ("anchor", "database", "template", "root"):
            with self.subTest(fault=fault):
                destination = self.workspace / fault
                manifest_sha = "0" * 64 if fault == "anchor" else self.manifest_sha
                manifest_path = self.manifest_path
                if fault == "root":
                    manifest_path = self.workspace / "bad-root.json"
                    manifest_path.write_text("[]")
                    manifest_sha = file_sha256(manifest_path)
                database = self.source / self.manifest.database.path
                original = database.read_bytes()
                if fault == "database":
                    database.write_bytes(original + b"corrupt")
                original_read = Path.read_text

                def read_text(path, *args, **kwargs):
                    text = original_read(path, *args, **kwargs)
                    if fault == "template" and path.name == "Containerfile":
                        return text.replace("RUN python -m data.pipeline.build_dataset", "RUN changed")
                    return text

                try:
                    with patch.object(Path, "read_text", read_text), self.assertRaises(ValueError):
                        exporter.export_context(destination, "synthetic-test", str(manifest_path), manifest_sha)
                    self.assertFalse(destination.exists())
                finally:
                    database.write_bytes(original)

    def test_missing_anchor_does_not_read_or_download_and_default_export_stays_synthetic(self):
        with patch("data.pipeline.stage_dataset.stage_dataset") as stage:
            for source, anchor in (("https://example.invalid/data-manifest.json", None), (None, self.manifest_sha)):
                with self.assertRaisesRegex(ValueError, "both"):
                    exporter.export_context(self.workspace / "invalid", "synthetic-test", source, anchor)
            stage.assert_not_called()
        result = exporter.export_context(self.workspace / "default", "synthetic-test")
        self.assertNotIn("frozen_data", result)
        self.assertIn("RUN python -m data.pipeline.build_dataset", (self.workspace / "default" / "Dockerfile").read_text())

    def test_public_review_shape_cannot_enable_unimplemented_attendee_acceptance(self):
        data = json.loads((ROOT / "data" / "fixtures" / "research-data.json").read_text())
        data["dataset_kind"] = "reviewed-public"
        data["review"] = {"approved_by": "Fictional unit-test reviewer", "approved_at": "2026-10-09T00:00:00Z"}
        for source in data["sources"]:
            source["url"] = "https://example.invalid/unit-test-source"
            source["retrieved_at"] = "2026-10-09T00:00:00Z"
        for record in [*data["trials"], *data["safety_reports"]]:
            record["source_url"] = "https://example.invalid/unit-test-record"
        input_path = self.workspace / "public-shape-test.json"
        input_path.write_text(json.dumps(data))
        source = self.workspace / "public-shape"
        build_dataset(input_path, source, "b" * 40)
        manifest_path = source / "data-manifest.json"
        destination = self.workspace / "unsupported-public"
        with self.assertRaisesRegex(ValueError, "currently supports only"):
            exporter.export_context(destination, "synthetic-test", str(manifest_path), file_sha256(manifest_path))
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
