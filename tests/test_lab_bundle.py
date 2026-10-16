import json
import shutil
import unittest
from unittest.mock import patch

import test_worker_public as fixtures
from data.pipeline import lab_bundle


class LabBundleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.PublicPackagingTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.fixture.root
        self.release = self.root / "data" / "lab-release.json"
        self.version = self.fixture.manifest["dataset_version"]
        self.bundle = self.root / "data" / "lab-datasets" / self.version
        shutil.copytree(self.fixture.directory, self.bundle)
        self.metadata = {
            "schema_version": "1.0", "purpose": "public-lab-development", "dataset_version": self.version,
            "manifest": {"path": f"data/lab-datasets/{self.version}/data-manifest.json",
                         "sha256": self.fixture.fixture.manifest_sha},
            "distribution_authorization": {"authorized_by": "Fictional owner",
                                          "authorized_at": "2026-10-14T00:00:00Z",
                                          "instruction": "Distribute this fictional test fixture."},
        }
        self.save_release()
        self.destination = self.root / "staged-data"
        self.override = patch.object(lab_bundle, "ROOT", self.root)
        self.override.start()
        self.addCleanup(self.override.stop)

    def save_release(self):
        self.release.write_text(json.dumps(self.metadata), encoding="utf-8")

    def test_offline_staging_is_exact_and_idempotent_but_never_repairs_corruption(self):
        validated = lab_bundle.stage_bundle(self.release)
        self.assertTrue(validated["frozen_files_verified"])
        self.assertFalse(self.destination.exists())
        first = lab_bundle.stage_bundle(self.release, self.destination)
        self.assertTrue(first["staged"])
        self.assertFalse(first["reused"])
        self.assertFalse(first["attendee_ready"])
        for source in self.bundle.iterdir():
            self.assertEqual((self.destination / source.name).read_bytes(), source.read_bytes())
        self.assertTrue(lab_bundle.stage_bundle(self.release, self.destination)["reused"])
        database = self.destination / self.fixture.manifest["database"]["path"]
        database.write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            lab_bundle.stage_bundle(self.release, self.destination)
        self.assertEqual(database.read_bytes(), b"corrupt")

    def test_unpinned_wrong_version_and_traversal_releases_never_publish_a_destination(self):
        for invalid in (
            {"manifest": {**self.metadata["manifest"], "sha256": "0" * 64}},
            {"manifest": {**self.metadata["manifest"], "path": "../data-manifest.json"}},
            {"purpose": "attendee-release"},
        ):
            with self.subTest(invalid=invalid):
                original = dict(self.metadata)
                self.metadata.update(invalid)
                self.save_release()
                with self.assertRaises(ValueError):
                    lab_bundle.stage_bundle(self.release, self.destination)
                self.assertFalse(self.destination.exists())
                self.metadata = original


if __name__ == "__main__":
    unittest.main()
