import base64
import copy
import unittest
from html.parser import HTMLParser
from unittest.mock import patch

import test_candidate as fixtures
import test_worker_public as public_fixtures
from src.workers.inspect_evidence import inspect_evidence, render_html


class EvidenceInspectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CandidatePackagingTests("runTest")
        self.addCleanup(self.fixture.tearDown)
        self.fixture.setUp()
        staged = fixtures.packager.stage_candidate(**self.fixture.options())
        self.image_path = self.fixture.workspace / "image.json"
        self.approval_path = self.fixture.workspace / "approval.json"
        self.startup_path = self.fixture.workspace / "startup.json"
        self.image = {
            "schema_version": "1.0", "status": "container-validated-unapproved-candidate",
            **{field: staged[field] for field in (
                "run_id", "dataset_version", "dataset_kind", "logical_sha256", "frozen_identity",
                "candidate_sources", "database", "result_sha256", "baseline_descriptor_sha256",
                "source_revision", "acceptance_purpose", "provenance_sha256",
            )},
            "validation": staged["validation_contract"],
            "image": {
                "registry": "fictionalregistry", "repository": "caldova/research-portal",
                "subscription": "40000000-0000-0000-0000-000000000001", "digest": "sha256:" + "d" * 64,
                "acr_run_id": "test-run", "reference": "fictionalregistry.azurecr.io/caldova/research-portal@sha256:" + "d" * 64,
                "platform": "linux/amd64", "target": "candidate",
            }, "human_approval": False, "release_approved": False, "deployed": False,
        }
        self.approval = {
            "run_id": self.fixture.run_id, "logical_sha256": "a" * 64,
            "image_digest": self.image["image"]["digest"], "approved_by": "Fictional test approver",
        }
        self.startup = {
            "observed_at": "2026-10-10T17:08:24+00:00",
            "report": {
                "schema_version": "1.0", "mode": "Readiness",
                "infrastructure_ready": True, "application_ready": True,
                "application_manifest_verified": True, "frozen_data_verified": True,
                "data_ready": False, "attendee_ready": False,
                "application": {
                    "schema_version": "1.0", "status": "pinned-development-application-ready",
                    "identity": {
                        name: value for name, value in self.fixture.descriptor["frozen_identity"].items()
                        if name != "baseline_manifest_sha256"
                    } | {
                        "acceptance_purpose": "synthetic-development", "dataset_kind": "synthetic-development",
                        "dataset_version": self.fixture.manifest["dataset_version"],
                    },
                    "image": self.image["image"]["reference"], "preview_state": "reference",
                    "local_frozen_artifacts_verified": True, "live_manifest_verified": True,
                    "sample_state_verified": True, "attendee_ready": False, "release_approved": False,
                    "full_functional_acceptance_rerun": False,
                    "url": "https://test-app.example.azurecontainerapps.io",
                    "resource_id": "/subscriptions/40000000-0000-0000-0000-000000000001/resourceGroups/test-rg/providers/Microsoft.App/containerApps/test-app",
                },
                "outputs": {
                    "AZURE_SUBSCRIPTION_ID": self.image["image"]["subscription"], "AZURE_RESOURCE_GROUP": "test-rg",
                    "CALDOVA_APPLICATION_NAME": "test-app",
                    "CALDOVA_APPLICATION_URL": "https://test-app.example.azurecontainerapps.io",
                    "CALDOVA_APPLICATION_IMAGE": self.image["image"]["reference"],
                },
            },
        }
        self.save_receipts()

    def save_receipts(self):
        for path, value in ((self.image_path, self.image), (self.approval_path, self.approval),
                            (self.startup_path, self.startup)):
            fixtures.packager.write_json(path, value)

    def options(self, optional=True):
        result = {
            "result_path": self.fixture.result_path,
            "result_sha256": fixtures.packager.file_sha256(self.fixture.result_path),
            "descriptor_path": self.fixture.descriptor_path,
            "descriptor_sha256": fixtures.packager.file_sha256(self.fixture.descriptor_path),
            "manifest_path": self.fixture.frozen / "data-manifest.json",
            "manifest_sha256": self.fixture.manifest_sha, "purpose": "synthetic-development",
        }
        if optional:
            for name, path in (("image", self.image_path), ("approval", self.approval_path), ("startup", self.startup_path)):
                result[name + "_path"] = path
                result[name + "_sha256"] = fixtures.packager.file_sha256(path)
        return result

    def test_complete_receipts_join_without_candidate_execution_network_or_release_approval(self):
        with patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("Network forbidden")):
            report = inspect_evidence(**self.options())
        self.assertEqual(report["status"], "evidence-integrity-verified")
        self.assertEqual(len(report["checks"]), 11)
        self.assertEqual(report["missing_stages"], [])
        self.assertEqual(report["application_observation"]["observed_at"], self.startup["observed_at"])
        self.assertEqual(report["human_approval"]["approved_by"], "Fictional test approver")
        for field in ("release_approved", "attendee_ready", "current_live_state_checked", "full_functional_acceptance_rerun"):
            self.assertIs(report[field], False)
        self.assertNotIn("must never execute", str(report))
        self.assertEqual(report["checks"], sorted(report["checks"], key=lambda check: check["name"]))

    def test_missing_stages_are_explicit_and_partial_receipt_pins_are_errors(self):
        report = inspect_evidence(**self.options(optional=False))
        self.assertEqual(len(report["missing_stages"]), 3)
        for changes in (
            {"image_path": self.image_path},
            {"approval_path": self.approval_path, "approval_sha256": fixtures.packager.file_sha256(self.approval_path)},
            {"startup_path": self.startup_path, "startup_sha256": fixtures.packager.file_sha256(self.startup_path)},
        ):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "requires|require"):
                inspect_evidence(**{**self.options(optional=False), **changes})

    def test_modified_inputs_and_foreign_or_failed_checks_are_rejected(self):
        options = self.options()
        for name in ("result", "descriptor", "manifest", "image", "approval", "startup"):
            path = options[name + "_path"]
            content = path.read_bytes()
            path.write_bytes(content + b" ")
            with self.subTest(input=name), self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                inspect_evidence(**options)
            path.write_bytes(content)
        original = copy.deepcopy(self.fixture.result)
        for fault in ("foreign-run", "failed-check", "worker-blocker", "changed-source"):
            self.fixture.result = copy.deepcopy(original)
            if fault == "foreign-run":
                self.fixture.result["workers"][0]["run_id"] = self.fixture.primary_id
            elif fault == "failed-check":
                self.fixture.result["integration_evidence"][0]["passed"] = False
            elif fault == "worker-blocker":
                self.fixture.result["workers"][0]["blockers"] = ["Unresolved"]
            else:
                next(iter(self.fixture.result["candidate_sources"].values()))["content"] += "tampered"
            self.fixture.save_result()
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                inspect_evidence(**self.options())

    def test_foreign_images_approvals_observations_and_historical_flag_rewrites_fail(self):
        original_image = copy.deepcopy(self.image)
        original_approval = copy.deepcopy(self.approval)
        original_startup = copy.deepcopy(self.startup)
        for fault in ("run", "source", "no-push-digest", "build-flags", "test-count", "numeric-flag",
                      "approval", "observation", "timestamp", "live-claim"):
            self.image = copy.deepcopy(original_image)
            self.approval = copy.deepcopy(original_approval)
            self.startup = copy.deepcopy(original_startup)
            if fault == "run":
                self.image["run_id"] = self.fixture.primary_id
            elif fault == "source":
                self.image["candidate_sources"][next(iter(self.image["candidate_sources"]))] = "f" * 64
            elif fault == "no-push-digest":
                self.image["image"]["digest"] = ""
            elif fault == "build-flags":
                self.image["human_approval"] = True
            elif fault == "test-count":
                self.image["validation"]["tests_required"] = 8
            elif fault == "numeric-flag":
                self.image["validation"]["container_only"] = 1
            elif fault == "approval":
                self.approval["image_digest"] = "sha256:" + "f" * 64
            elif fault == "observation":
                self.startup["report"]["application"]["image"] = "different-image"
            elif fault == "timestamp":
                self.startup["observed_at"] = "2026-10-10T17:08:24"
            else:
                self.startup["report"]["application"]["full_functional_acceptance_rerun"] = True
            self.save_receipts()
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                inspect_evidence(**self.options())

    def test_public_sources_and_unchanged_historical_flags_are_verified(self):
        fixture = public_fixtures.PublicPackagingTests("runTest")
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        options = {
            "result_path": fixture.fixture.result_path,
            "result_sha256": fixtures.packager.file_sha256(fixture.fixture.result_path),
            "descriptor_path": fixture.fixture.descriptor_path,
            "descriptor_sha256": fixtures.packager.file_sha256(fixture.fixture.descriptor_path),
            "manifest_path": fixture.directory / "data-manifest.json",
            "manifest_sha256": fixture.fixture.manifest_sha, "purpose": "public-lab-development",
        }
        report = inspect_evidence(**options)
        self.assertEqual(report["pipeline_provenance"], "uncommitted-development")
        self.assertEqual(report["dataset"]["source_use_sha256"],
                         fixture.fixture.descriptor["frozen_identity"]["source_use_sha256"])
        self.assertFalse(report["attendee_ready"])
        source = fixture.directory / "source-records.json"
        source.write_bytes(source.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "mismatch"):
            inspect_evidence(**options)

    def test_html_escapes_untrusted_labels_and_has_no_script_or_external_assets(self):
        class AssetParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.urls = []
                self.images = []

            def handle_starttag(self, tag, attributes):
                attributes = dict(attributes)
                self.urls.extend(attributes[name] for name in ("src", "href") if name in attributes)
                if tag == "img":
                    self.images.append(attributes)

        report = inspect_evidence(**self.options())
        report["human_approval"]["approved_by"] = '<script>alert("bad")</script>'
        document = render_html(report)
        self.assertIn("&lt;script&gt;", document)
        self.assertNotIn("<script", document)
        parser = AssetParser()
        parser.feed(document)
        prefix = "data:image/svg+xml;base64,"
        self.assertTrue(all(url.startswith("#") or url.startswith(prefix) for url in parser.urls))
        self.assertEqual(len(parser.images), 1)
        self.assertEqual(parser.images[0]["alt"], "Caldova")
        self.assertEqual(
            base64.b64decode(parser.images[0]["src"].removeprefix(prefix), validate=True),
            (fixtures.ROOT / "src/research-portal/frontend/src/assets/caldova-logo.svg").read_bytes(),
        )
        self.assertIn("img-src data:;", document)
        self.assertIn("Current live state checked: false", document)
        self.assertIn("None reported", document)
        self.assertIn('id="evidence"', document)

    def test_dashboard_navigation_and_counts_work_with_missing_optional_receipts(self):
        class DashboardParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
                self.targets = []
                self.summary_depth = 0
                self.metric = None
                self.metrics = []

            def handle_starttag(self, tag, attributes):
                attributes = dict(attributes)
                if "id" in attributes:
                    self.ids.append(attributes["id"])
                if tag == "a" and attributes.get("href", "").startswith("#"):
                    self.targets.append(attributes["href"][1:])
                if attributes.get("aria-label") == "Recorded evidence summary":
                    self.summary_depth = 1
                elif self.summary_depth:
                    self.summary_depth += 1
                    if tag == "strong":
                        self.metric = ""

            def handle_data(self, data):
                if self.metric is not None:
                    self.metric += data

            def handle_endtag(self, tag):
                if self.summary_depth:
                    if tag == "strong" and self.metric is not None:
                        self.metrics.append(self.metric)
                        self.metric = None
                    self.summary_depth -= 1

        for optional in (True, False):
            with self.subTest(optional_receipts=optional):
                report = inspect_evidence(**self.options(optional=optional))
                parser = DashboardParser()
                parser.feed(render_html(report))
                self.assertEqual(len(parser.ids), len(set(parser.ids)))
                self.assertTrue(parser.targets)
                self.assertTrue(set(parser.targets).issubset(parser.ids))
                self.assertEqual(parser.metrics, [
                    str(len(report["workers"])), str(len(report["checks"])), "Not checked",
                ])
                self.assertFalse(report["attendee_ready"])
                self.assertFalse(report["current_live_state_checked"])


if __name__ == "__main__":
    unittest.main()
