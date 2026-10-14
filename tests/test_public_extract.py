import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import duckdb
from pydantic import ValidationError

from data.pipeline import extract_public as extractor
from data.pipeline.contracts import DatasetInput
from data.pipeline.download_aact import load_source
from data.pipeline.validate_dataset import file_sha256


def report(report_id, version, *drugs):
    return {
        "safetyreportid": report_id, "safetyreportversion": str(version),
        "patient": {
            "patientsex": "DO_NOT_RETAIN",
            "drug": [{"medicinalproduct": drug} for drug in drugs],
            "reaction": [{"reactionmeddrapt": term} for term in (" Nausea ", "nausea", "Fatigue")],
        },
        "serious": "DO_NOT_RETAIN",
    }


class PublicExtractTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.root = Path(self.workspace.name)
        self.aact_dir = self.root / "aact"
        self.fda_dir = self.root / "fda"
        self.aact_dir.mkdir()
        self.fda_dir.mkdir()
        self.database = self.aact_dir / "fictional.duckdb"
        self.archive = self.fda_dir / "fictional.json.zip"
        self.output = self.root / "draft"
        with duckdb.connect(str(self.database)) as connection:
            connection.execute(
                "CREATE TABLE studies(nct_id VARCHAR,brief_title VARCHAR,phase VARCHAR,"
                "overall_status VARCHAR,study_type VARCHAR)"
            )
            connection.execute("CREATE TABLE conditions(nct_id VARCHAR,name VARCHAR)")
            connection.execute(
                "CREATE TABLE interventions(id BIGINT,nct_id VARCHAR,name VARCHAR,intervention_type VARCHAR)"
            )
        self.intervention_id = 0
        self.add_trial(
            1, (" Semaglutide ", "LIRAGLUTIDE"),
            ("Obesity", "Type 2 Diabetes", " Unmapped source condition "),
        )
        for number in range(2, 14):
            self.add_trial(number, ("semaglutide",), ("Obesity",))
        self.add_trial(20, ("semaglutide",), ("Obesity",), phase=None)
        self.add_trial(21, ("semaglutide analogue",), ("Obesity",))
        self.add_trial(22, ("semaglutide",), ("Diabetes",))
        self.add_trial(23, ("liraglutide",), ("Obesity",), study_type="OBSERVATIONAL")
        self.add_trial(24, ("liraglutide",), ("Obesity",), intervention_type="OTHER")
        self.add_trial(25, ("tirzepatide",), ("Type 2 Diabetes Mellitus",), phase="NA")
        self.reports = [
            report("R01", 1, "SEMAGLUTIDE", "Liraglutide"),
            report("R02", 1, "Semaglutide"),
            report("R02", 2, "Unmapped latest drug"),
            report("BRAND", 1, "VICTOZA"),
            report("COMPOUND", 1, "CYANOCOBALAMIN\\TIRZEPATIDE"),
        ]
        combination = report("COMBINATION", 1, "Brand")
        combination["patient"]["drug"][0]["openfda"] = {
            "generic_name": ["LIRAGLUTIDE"],
            "substance_name": ["LIRAGLUTIDE", "INSULIN DEGLUDEC"],
        }
        self.reports.append(combination)
        self.reports.extend(report(f"S{number:02}", 1, "semaglutide") for number in range(12))
        self.reports.append(copy.deepcopy(self.reports[0]))

    def tearDown(self):
        self.workspace.cleanup()

    def add_trial(self, number, names, conditions, *, phase="PHASE2",
                  study_type="INTERVENTIONAL", intervention_type="DRUG"):
        study_id = f"NCT{number:08}"
        with duckdb.connect(str(self.database)) as connection:
            connection.execute(
                "INSERT INTO studies VALUES(?,?,?,?,?)",
                [study_id, f"Fictional trial {number}", phase, "RECRUITING", study_type],
            )
            connection.executemany("INSERT INTO conditions VALUES(?,?)", [(study_id, value) for value in conditions])
            for name in names:
                self.intervention_id += 1
                connection.execute(
                    "INSERT INTO interventions VALUES(?,?,?,?)",
                    [self.intervention_id, study_id, name, intervention_type],
                )

    def pins(self):
        aact = {**load_source(), "bytes": self.database.stat().st_size, "sha256": file_sha256(self.database)}
        fda = extractor.load_openfda_pin()
        payload = json.dumps({
            "meta": {"last_updated": fda["export_date"]}, "results": self.reports,
        }).encode()
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(fda["zip_member"], payload)
        fda = {
            **fda, "bytes": self.archive.stat().st_size, "sha256": file_sha256(self.archive),
            "zip_member_bytes": len(payload), "records": len(self.reports),
        }
        (self.aact_dir / "acquisition-receipt.json").write_text(json.dumps({
            "source": aact, "checksum_verified": True,
            "download_completed_at_utc": "2026-10-10T00:00:00Z",
        }))
        (self.fda_dir / "intake-receipt.json").write_text(json.dumps({
            "archive": {"sha256": fda["sha256"], "url": fda["url"]},
            "event_export_date": fda["export_date"], "acquired_at_utc": "2026-10-10T00:00:00Z",
        }))
        return aact, fda

    def extract(self, mapping_version="conservative-exact-generics-v1"):
        aact, fda = self.pins()
        with patch.object(extractor, "load_source", return_value=aact), patch.object(
            extractor, "load_openfda_pin", return_value=fda
        ):
            return extractor.extract_public(self.database, self.archive, self.output, mapping_version)

    def test_v2_expands_real_selection_without_relaxing_v1_bounds(self):
        result = self.extract("conservative-exact-generics-v2")
        draft = json.loads((self.output / "public-review-draft.json").read_text())
        self.assertEqual(result["maximum_trials_per_candidate_topic"], 30)
        self.assertEqual(result["maximum_reports_per_candidate"], 50)
        self.assertEqual(draft["trial_bucket_counts"]["semaglutide/obesity"], 13)
        self.assertEqual(draft["report_candidate_counts"]["semaglutide"], 13)
        self.assertFalse(draft["source_review_approved"])
        self.assertFalse(draft["attendee_release_approved"])
        draft["mapping_version"] = "conservative-exact-generics-v1"
        with self.assertRaisesRegex(ValidationError, "bounds"):
            extractor.PublicDraft.model_validate(draft)

    def test_draft_preserves_shared_source_records_and_enforces_actual_bounds(self):
        result = self.extract()
        path = self.output / "public-review-draft.json"
        draft = json.loads(path.read_text())
        shared_trial = next(item for item in draft["trials"] if item["trial_id"] == "NCT00000001")
        self.assertEqual(shared_trial["candidate_ids"], ["liraglutide", "semaglutide"])
        self.assertEqual(shared_trial["conditions"], ["obesity", "type-2-diabetes"])
        self.assertEqual(
            shared_trial["source_conditions"], [" Unmapped source condition ", "Obesity", "Type 2 Diabetes"]
        )
        self.assertEqual(
            [item["name"] for item in shared_trial["source_interventions"]], [" Semaglutide ", "LIRAGLUTIDE"]
        )
        self.assertEqual(result["trial_bucket_counts"]["semaglutide/obesity"], 10)
        self.assertTrue(all(count <= 10 for count in result["trial_bucket_counts"].values()))
        self.assertEqual(result["source_quality_counts"]["trials_excluded_invalid_required_fields"], 1)
        trial_ids = {item["trial_id"] for item in draft["trials"]}
        self.assertTrue({f"NCT{number:08}" for number in (20, 21, 22, 23, 24)}.isdisjoint(trial_ids))
        self.assertEqual(next(item for item in draft["trials"] if item["trial_id"] == "NCT00000025")["phase"], "NA")
        shared_report = next(item for item in draft["safety_reports"] if item["report_id"] == "R01")
        self.assertEqual(shared_report["candidate_ids"], ["liraglutide", "semaglutide"])
        self.assertEqual(shared_report["reaction_terms"], ["FATIGUE", "NAUSEA"])
        self.assertEqual(shared_report["original_reaction_terms"], [" Nausea ", "nausea", "Fatigue"])
        self.assertEqual(result["report_candidate_counts"]["semaglutide"], 10)
        self.assertTrue(all(count <= 10 for count in result["report_candidate_counts"].values()))
        self.assertEqual(result["source_quality_counts"]["identical_raw_report_copies"], 1)
        self.assertNotIn("DO_NOT_RETAIN", path.read_text())
        self.assertEqual(result["draft_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertLessEqual(result["draft_bytes"], 64 * 1024 * 1024)
        self.assertFalse(draft["source_review_approved"])
        self.assertFalse(draft["attendee_release_approved"])
        with self.assertRaises(ValidationError):
            DatasetInput.model_validate_json(path.read_text())

    def test_latest_version_precedes_matching_and_exact_policy_keeps_true_empty_states(self):
        self.extract()
        draft = json.loads((self.output / "public-review-draft.json").read_text())
        report_ids = {item["report_id"] for item in draft["safety_reports"]}
        self.assertTrue({"R02", "BRAND", "COMPOUND", "COMBINATION"}.isdisjoint(report_ids))
        self.assertFalse(any("tirzepatide" in item["candidate_ids"] for item in draft["safety_reports"]))
        self.assertTrue(any("tirzepatide" in item["candidate_ids"] for item in draft["trials"]))

    def test_raw_same_version_conflicts_fail_even_when_changed_field_is_excluded(self):
        changed = copy.deepcopy(self.reports[0])
        changed["patient"]["patientsex"] = "DIFFERENT_SOURCE_VALUE"
        self.reports.append(changed)
        with self.assertRaisesRegex(ValueError, "Conflicting raw copies"):
            self.extract()
        self.assertFalse(self.output.exists())

    def test_bad_input_pin_or_receipt_and_unsafe_destination_publish_nothing(self):
        aact, fda = self.pins()
        with patch.object(extractor, "load_source", return_value=aact), patch.object(
            extractor, "load_openfda_pin", return_value=fda
        ):
            with patch.object(extractor, "verify_file") as verify:
                with self.assertRaisesRegex(ValueError, "outside the repository"):
                    extractor.extract_public(self.database, self.archive, extractor.ROOT / ".unreviewed-draft")
                verify.assert_not_called()
            (self.fda_dir / "intake-receipt.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "receipts disagree"):
                extractor.extract_public(self.database, self.archive, self.output)
            self.assertFalse(self.output.exists())
        aact, fda = self.pins()
        with patch.object(extractor, "load_source", return_value=aact), patch.object(
            extractor, "load_openfda_pin", return_value={**fda, "sha256": "0" * 64}
        ):
            with self.assertRaises(ValueError):
                extractor.extract_public(self.database, self.archive, self.output)
            self.assertFalse(self.output.exists())
        self.output.mkdir()
        retained = self.output / "existing.txt"
        retained.write_text("keep this")
        with self.assertRaises(FileExistsError):
            extractor.extract_public(self.database, self.archive, self.output)
        self.assertEqual(retained.read_text(), "keep this")


if __name__ == "__main__":
    unittest.main()
