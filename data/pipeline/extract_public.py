import argparse
import hashlib
import json
import os
import re
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Self, TypeVar

import duckdb
from pydantic import ConfigDict, Field, model_validator

from data.pipeline.build_dataset import normalize_reports
from data.pipeline.contracts import (
    Candidate, Condition, Contract, Identifier, LIMITATIONS, SafetyReport, Source, Text, Trial,
)
from data.pipeline.download_aact import ROOT, load_source, verify_file
from data.pipeline.validate_dataset import file_sha256
from src.workers.frozen_contract import PUBLIC_MAPPING_LIMITS, public_mapping_limits

OPENFDA_PIN_PATH = ROOT / "data" / "sources" / "openfda-intake.json"
CANDIDATES = ("semaglutide", "liraglutide", "tirzepatide")
CONDITION_ALIASES: dict[Condition, tuple[str, ...]] = {
    "obesity": ("obesity",),
    "type-2-diabetes": ("diabetes mellitus, type 2", "type 2 diabetes", "type 2 diabetes mellitus"),
}
LIMIT = 10
MAX_DRAFT_BYTES = 64 * 1024 * 1024
REQUIRED_COLUMNS = {
    "studies": {
        "nct_id": "VARCHAR", "brief_title": "VARCHAR", "phase": "VARCHAR",
        "overall_status": "VARCHAR", "study_type": "VARCHAR",
    },
    "conditions": {"nct_id": "VARCHAR", "name": "VARCHAR"},
    "interventions": {
        "id": "BIGINT", "nct_id": "VARCHAR", "name": "VARCHAR", "intervention_type": "VARCHAR",
    },
}


class SourceIntervention(Contract):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    intervention_id: int = Field(gt=0, strict=True)
    candidate_id: Identifier
    name: Text
    intervention_type: Literal["DRUG"]


class DraftTrial(Trial):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    source_conditions: list[Text] = Field(min_length=1)
    source_interventions: list[SourceIntervention] = Field(min_length=1)


class SourceDrug(Contract):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    candidate_ids: list[Identifier] = Field(min_length=1)
    medicinalproduct: Text | None
    generic_names: list[Text]
    brand_names: list[Text]
    substance_names: list[Text]


class DraftReport(SafetyReport):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)

    source_drugs: list[SourceDrug] = Field(min_length=1)
    original_reaction_terms: list[Text] = Field(min_length=1)


class PublicDraft(Contract):
    schema_version: Literal["1.0"] = "1.0"
    dataset_kind: Literal["unreviewed-public"] = "unreviewed-public"
    dataset_version: Identifier = "caldova-public-review-draft-v1"
    built_at: datetime
    mapping_version: Literal[
        "conservative-exact-generics-v1", "conservative-exact-generics-v2"
    ] = "conservative-exact-generics-v1"
    source_review_approved: Literal[False] = False
    attendee_release_approved: Literal[False] = False
    candidates: list[Candidate]
    sources: list[Source]
    trials: list[DraftTrial] = Field(min_length=1)
    safety_reports: list[DraftReport]
    trial_bucket_counts: dict[str, int]
    report_candidate_counts: dict[str, int]
    source_quality_counts: dict[str, int]
    limitations: str = LIMITATIONS
    coverage_notes: list[str]

    @model_validator(mode="after")
    def check_records_and_bounds(self) -> Self:
        candidates = {candidate.candidate_id for candidate in self.candidates}
        sources = {source.source_id for source in self.sources}
        if len(candidates) != len(self.candidates) or len(sources) != len(self.sources):
            raise ValueError("Draft candidate and source IDs must be unique.")
        for collection, field in ((self.trials, "trial_id"), (self.safety_reports, "report_id")):
            if len({getattr(item, field) for item in collection}) != len(collection):
                raise ValueError("Draft evidence IDs must be unique.")
            for item in collection:
                if item.source_id not in sources or not set(item.candidate_ids).issubset(candidates):
                    raise ValueError("Draft evidence references an unknown source or candidate.")
                if item.source_url is None:
                    raise ValueError("Draft evidence requires an actual source URL.")
        trial_counts = Counter(
            f"{candidate}/{condition}"
            for trial in self.trials for candidate in trial.candidate_ids for condition in trial.conditions
        )
        report_counts = Counter(candidate for report in self.safety_reports for candidate in report.candidate_ids)
        if dict(trial_counts) != self.trial_bucket_counts or dict(report_counts) != self.report_candidate_counts:
            raise ValueError("Draft selection counts disagree with the complete evidence collections.")
        trial_limit, report_limit = public_mapping_limits(self.mapping_version)
        if (any(count > trial_limit for count in trial_counts.values()) or
                any(count > report_limit for count in report_counts.values())):
            raise ValueError("Draft records exceed the selected per-candidate/topic bounds.")
        return self


def load_openfda_pin() -> dict:
    pin = json.loads(OPENFDA_PIN_PATH.read_text(encoding="utf-8"))
    if not isinstance(pin, dict):
        raise ValueError("The openFDA intake pin must be a JSON object.")
    filename = pin.get("zip_member")
    if (
        pin.get("schema_version") != "1.0" or pin.get("purpose") != "raw-source-intake"
        or not isinstance(pin.get("url"), str)
        or not re.fullmatch(
            r"https://download\.open\.fda\.gov/drug/event/\d{4}q[1-4]/drug-event-\d{4}-of-\d{4}\.json\.zip",
            pin["url"],
        )
        or type(pin.get("bytes")) is not int or not 0 < pin["bytes"] <= 64 * 1024 * 1024
        or not isinstance(pin.get("sha256"), str) or not re.fullmatch(r"[a-f0-9]{64}", pin["sha256"])
        or not isinstance(filename, str) or Path(filename).name != filename or "\\" in filename
        or not filename.endswith(".json")
        or type(pin.get("zip_member_bytes")) is not int
        or not 0 < pin["zip_member_bytes"] <= 128 * 1024 * 1024
        or type(pin.get("records")) is not int or pin["records"] <= 0
        or not isinstance(pin.get("quarter"), str) or not re.fullmatch(r"\d{4}q[1-4]", pin["quarter"])
        or f"/{pin['quarter']}/" not in pin["url"] or not pin["url"].endswith(f"/{filename}.zip")
        or not isinstance(pin.get("export_date"), str)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", pin["export_date"])
        or pin.get("source_review_approved") is not False or pin.get("attendee_release_approved") is not False
    ):
        raise ValueError("The openFDA raw-source pin has invalid fields or approval state.")
    return pin


def read_receipt(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Raw source inputs require a regular acquisition receipt.")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("The raw acquisition receipt must be an object.")
    return receipt


def read_trials(database: Path, quality: Counter) -> list[DraftTrial]:
    with duckdb.connect(
        str(database), read_only=True,
        config={
            "enable_external_access": False, "autoinstall_known_extensions": False,
            "autoload_known_extensions": False, "memory_limit": "512MB", "threads": 1,
        },
    ) as connection:
        for table, expected in REQUIRED_COLUMNS.items():
            columns = dict(connection.execute(
                "SELECT column_name,data_type FROM information_schema.columns "
                "WHERE table_schema='main' AND table_name=?", [table],
            ).fetchall())
            kind = connection.execute(
                "SELECT table_type FROM information_schema.tables WHERE table_schema='main' AND table_name=?",
                [table],
            ).fetchall()
            if kind != [("BASE TABLE",)] or any(columns.get(name) != dtype for name, dtype in expected.items()):
                raise ValueError(f"The AACT source lacks the required base-table schema for {table}.")
        records = connection.execute(
            "SELECT s.nct_id,s.brief_title,s.phase,s.overall_status FROM main.studies s "
            "WHERE s.study_type='INTERVENTIONAL' AND EXISTS("
            "SELECT 1 FROM main.interventions i WHERE i.nct_id=s.nct_id AND i.intervention_type='DRUG' "
            "AND lower(trim(i.name))=ANY(?)) AND EXISTS("
            "SELECT 1 FROM main.conditions c WHERE c.nct_id=s.nct_id AND lower(trim(c.name))=ANY(?)) "
            "ORDER BY s.nct_id",
            [list(CANDIDATES), [alias for aliases in CONDITION_ALIASES.values() for alias in aliases]],
        ).fetchall()
        ids = [record[0] for record in records]
        if len(set(ids)) != len(ids):
            raise ValueError("The eligible AACT source contains duplicate study IDs.")
        conditions = defaultdict(list)
        for study_id, name in connection.execute(
            "SELECT nct_id,name FROM main.conditions WHERE nct_id=ANY(?) ORDER BY nct_id,name", [ids]
        ).fetchall():
            conditions[study_id].append(name)
        interventions = defaultdict(list)
        for intervention_id, study_id, name in connection.execute(
            "SELECT id,nct_id,name FROM main.interventions WHERE nct_id=ANY(?) "
            "AND intervention_type='DRUG' AND lower(trim(name))=ANY(?) ORDER BY nct_id,id",
            [ids, list(CANDIDATES)],
        ).fetchall():
            interventions[study_id].append(SourceIntervention(
                intervention_id=intervention_id, candidate_id=name.strip().lower(),
                name=name, intervention_type="DRUG",
            ))
    result = []
    for study_id, title, phase, status in records:
        if not isinstance(study_id, str) or not re.fullmatch(r"NCT\d{8}", study_id):
            raise ValueError("The source study ID is not a canonical NCT ID.")
        if any(not isinstance(value, str) or not value.strip() or len(value.strip()) > 2000
               for value in (title, phase, status)):
            quality["trials_excluded_invalid_required_fields"] += 1
            continue
        source_conditions = sorted(set(conditions[study_id]))
        canonical: list[Condition] = [
            topic for topic, aliases in CONDITION_ALIASES.items()
            if any(name.strip().lower() in aliases for name in source_conditions)
        ]
        result.append(DraftTrial(
            trial_id=study_id, title=title, phase=phase, status=status, conditions=canonical,
            candidate_ids=sorted({item.candidate_id for item in interventions[study_id]}),
            source_id="aact-mirror", source_record_id=study_id,
            source_url=f"https://clinicaltrials.gov/study/{study_id}",
            source_conditions=source_conditions, source_interventions=interventions[study_id],
        ))
    quality["eligible_trials_before_bound"] = len(result)
    return result


def source_drug(drug: dict) -> SourceDrug | None:
    if not isinstance(drug, dict):
        raise ValueError("A source drug entry must be an object.")
    medicinal = drug.get("medicinalproduct")
    if medicinal is not None and (not isinstance(medicinal, str) or not medicinal.strip()):
        raise ValueError("A source medicinalproduct must be a nonempty string.")
    harmonized = drug.get("openfda", {})
    if not isinstance(harmonized, dict):
        raise ValueError("Source harmonized fields must be an object.")
    names = {}
    for field in ("generic_name", "brand_name", "substance_name"):
        values = harmonized.get(field, [])
        if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("Source harmonized names must be arrays of nonempty strings.")
        names[field] = values
    exact_labels = {value.strip().lower() for value in names["generic_name"]}
    if medicinal:
        exact_labels.add(medicinal.strip().lower())
    substances = {value.strip().lower() for value in names["substance_name"]}
    candidates = [
        candidate for candidate in CANDIDATES
        if candidate in exact_labels and (not substances or substances == {candidate})
    ]
    if not candidates:
        return None
    return SourceDrug(
        candidate_ids=candidates, medicinalproduct=medicinal, generic_names=names["generic_name"],
        brand_names=names["brand_name"], substance_names=names["substance_name"],
    )


def read_reports(archive_path: Path, pin: dict, quality: Counter) -> list[DraftReport]:
    if archive_path.is_symlink() or not archive_path.is_file() or archive_path.stat().st_size != pin["bytes"]:
        raise ValueError("The openFDA archive does not match the pinned regular-file size.")
    if file_sha256(archive_path) != pin["sha256"]:
        raise ValueError("The openFDA archive SHA-256 does not match the intake pin.")
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if (
            len(members) != 1 or members[0].filename != pin["zip_member"]
            or members[0].file_size != pin["zip_member_bytes"] or members[0].flag_bits & 1
        ):
            raise ValueError("The openFDA ZIP has an unexpected member, size, or encryption state.")
        with archive.open(members[0]) as stream:
            document = json.load(stream)
    if not isinstance(document, dict) or not isinstance(document.get("results"), list):
        raise ValueError("The openFDA ZIP must contain a results array.")
    reports = document["results"]
    metadata = document.get("meta")
    if (
        len(reports) != pin["records"] or not isinstance(metadata, dict)
        or metadata.get("last_updated") != pin["export_date"]
    ):
        raise ValueError("The openFDA count/export metadata disagrees with the intake pin.")
    versions = {}
    latest = {}
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("An openFDA source report must be an object.")
        report_id = report.get("safetyreportid")
        version_text = report.get("safetyreportversion")
        if (
            not isinstance(report_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", report_id)
            or not isinstance(version_text, str) or not re.fullmatch(r"[1-9]\d*", version_text)
        ):
            raise ValueError("An openFDA report lacks a valid ID/positive version.")
        version = int(version_text)
        digest = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        previous = versions.get((report_id, version))
        if previous is not None:
            if previous != digest:
                raise ValueError(f"Conflicting raw copies of report {report_id} version {version}.")
            quality["identical_raw_report_copies"] += 1
        versions[report_id, version] = digest
        if report_id not in latest or version > latest[report_id][0]:
            latest[report_id] = (version, report)
    quality["raw_reports"] = len(reports)
    quality["distinct_reports_within_input"] = len(latest)
    result = []
    for report_id, (version, report) in sorted(latest.items()):
        patient = report.get("patient")
        if not isinstance(patient, dict) or not isinstance(patient.get("drug", []), list):
            raise ValueError("The source report must have a patient object with a drug array.")
        drugs = [match for drug in patient.get("drug", []) if (match := source_drug(drug)) is not None]
        if not drugs:
            continue
        reactions = patient.get("reaction", [])
        if not isinstance(reactions, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("reactionmeddrapt"), str)
            or not item["reactionmeddrapt"].strip() for item in reactions
        ):
            raise ValueError("The source report has invalid reaction terms.")
        if not reactions:
            quality["reports_excluded_missing_reaction_terms"] += 1
            continue
        original_terms = [item["reactionmeddrapt"] for item in reactions]
        base = SafetyReport(
            report_id=report_id, version=version, source_id="openfda-single-shard",
            source_record_id=report_id, source_url=f"{pin['url']}#report={report_id}&version={version}",
            candidate_ids=sorted({candidate for drug in drugs for candidate in drug.candidate_ids}),
            reaction_terms=original_terms,
        )
        normalized = normalize_reports([base])[0]
        result.append(DraftReport(
            **normalized.model_dump(), source_drugs=drugs, original_reaction_terms=original_terms,
        ))
    quality["eligible_reports_before_bound"] = len(result)
    return result


Record = TypeVar("Record", DraftTrial, DraftReport)


def bounded(records: list[Record], limit: int = LIMIT) -> tuple[list[Record], dict[str, int]]:
    selected: list[Record] = []
    counts = Counter()
    for record in sorted(
        records, key=lambda item: item.trial_id if isinstance(item, DraftTrial) else item.report_id,
    ):
        keys = {
            f"{candidate}/{condition}" if isinstance(record, DraftTrial) else candidate
            for candidate in record.candidate_ids
            for condition in (record.conditions if isinstance(record, DraftTrial) else (None,))
        }
        if any(counts[key] >= limit for key in keys):
            continue
        selected.append(record)
        counts.update(keys)
    return selected, dict(sorted(counts.items()))


def extract_public(
    database: Path, archive: Path, output: Path,
    mapping_version: str = "conservative-exact-generics-v1",
) -> dict:
    trial_limit, report_limit = public_mapping_limits(mapping_version)
    output = output.expanduser().resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("Keep the unreviewed public extract outside the repository checkout.")
    if output.exists():
        raise FileExistsError("Refusing to overwrite a retained public-review draft.")
    if database.resolve().is_relative_to(ROOT) or archive.resolve().is_relative_to(ROOT):
        raise ValueError("Raw public inputs must remain outside the repository checkout.")
    aact_pin, fda_pin = load_source(), load_openfda_pin()
    verify_file(database, aact_pin)
    aact_receipt = read_receipt(database.parent / "acquisition-receipt.json")
    fda_receipt = read_receipt(archive.parent / "intake-receipt.json")
    fda_archive_receipt = fda_receipt.get("archive")
    if (
        aact_receipt.get("source") != aact_pin or aact_receipt.get("checksum_verified") is not True
        or not isinstance(fda_archive_receipt, dict)
        or fda_archive_receipt.get("sha256") != fda_pin["sha256"]
        or fda_archive_receipt.get("url") != fda_pin["url"]
        or fda_receipt.get("event_export_date") != fda_pin["export_date"]
    ):
        raise ValueError("Raw source receipts disagree with the selected immutable intake pins.")
    aact_retrieved = aact_receipt.get("download_completed_at_utc")
    fda_retrieved = fda_receipt.get("acquired_at_utc")
    if not isinstance(aact_retrieved, str) or not isinstance(fda_retrieved, str):
        raise ValueError("Raw source receipts require actual acquisition timestamps.")
    quality = Counter()
    eligible_trials = read_trials(database, quality)
    eligible_reports = read_reports(archive, fda_pin, quality)
    trials, trial_counts = bounded(eligible_trials, trial_limit)
    reports, report_counts = bounded(eligible_reports, report_limit)
    quality["trials_skipped_bucket_bound"] = len(eligible_trials) - len(trials)
    quality["reports_skipped_candidate_bound"] = len(eligible_reports) - len(reports)
    draft = PublicDraft(
        built_at=datetime.now(timezone.utc),
        mapping_version=mapping_version,
        dataset_version=("caldova-public-review-draft-v2" if mapping_version.endswith("-v2")
                         else "caldova-public-review-draft-v1"),
        candidates=[
            Candidate(candidate_id=name, name=name, research_area="Bounded diabetes/obesity software demonstration")
            for name in CANDIDATES
        ],
        sources=[
            Source(
                source_id="aact-mirror", name="AACT-derived DuckDB mirror by Nason",
                url=aact_pin["url"], release=aact_pin["publisher_snapshot_date"],
                retrieved_at=aact_retrieved,
                attribution="ClinicalTrials.gov; AACT / CTTI; DuckDB conversion by Nason.",
                license_notes="Publisher CC0 label and upstream reuse/attribution terms require human review.",
            ),
            Source(
                source_id="openfda-single-shard", name="openFDA drug/event single-partition intake",
                url=fda_pin["url"], release=fda_pin["export_date"], retrieved_at=fda_retrieved,
                attribution="openFDA / U.S. Food and Drug Administration.",
                license_notes="Rights, marked exceptions and residual privacy review remain pending.",
            ),
        ],
        trials=trials, safety_reports=reports, trial_bucket_counts=trial_counts,
        report_candidate_counts=report_counts, source_quality_counts=dict(sorted(quality.items())),
        coverage_notes=[
            "Unapproved review draft, not an attendee artifact or accepted build_dataset input.",
            "Exact trimmed case-insensitive generic names only; no brand/code/substring expansion.",
            "Trials require DRUG interventions, INTERVENTIONAL study type and the listed exact condition aliases.",
            "Original source conditions and matched intervention names are separate from canonical topic categories.",
            "Drug objects listing additional harmonized substances are excluded.",
            "Harmonized brand arrays are source metadata, not proof of products taken.",
            "A single disclosed openFDA shard is not complete or representative clinical evidence.",
            "Latest report versions are selected within the input before candidate matching.",
            "Conflicting full raw ID/version copies fail; identical copies and reaction terms are normalized.",
            "Stable ascending IDs with strict bucket budgets; whole shared records are kept or skipped, never narrowed.",
            "Trial registry links are live references; frozen record values come from the pinned mirror.",
            "No demographic/contact, seriousness, outcome, dose, route or indication fields are retained.",
            "No trial/report linkage or globally latest-version assertion is made.",
        ],
    )
    payload = (draft.model_dump_json(indent=2) + "\n").encode("utf-8")
    if len(payload) > MAX_DRAFT_BYTES:
        raise ValueError("The review draft exceeds the bounded artifact budget.")
    provenance = {
        "schema_version": "1.0", "dataset_kind": "unreviewed-public",
        "extractor_sha256": file_sha256(Path(__file__)),
        "aact_input": aact_pin, "openfda_input": fda_pin,
        "condition_aliases": CONDITION_ALIASES, "candidate_names": CANDIDATES,
        "maximum_trials_per_candidate_topic": trial_limit, "maximum_reports_per_candidate": report_limit,
        "draft_bytes": len(payload), "draft_sha256": hashlib.sha256(payload).hexdigest(),
        "trial_count": len(trials), "report_count": len(reports),
        "trial_bucket_counts": trial_counts, "report_candidate_counts": report_counts,
        "source_quality_counts": dict(quality), "source_review_approved": False,
        "attendee_release_approved": False, "dataset_published": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".caldova-public-draft-", dir=output.parent) as temporary:
        staged = Path(temporary) / "draft"
        staged.mkdir()
        (staged / "public-review-draft.json").write_bytes(payload)
        (staged / "draft-provenance.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
        os.rename(staged, output)
    return {"output": str(output), **provenance}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a bounded, unapproved public-source review draft.")
    parser.add_argument("--aact-database", type=Path, required=True)
    parser.add_argument("--openfda-archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mapping-version", choices=tuple(PUBLIC_MAPPING_LIMITS),
                        default="conservative-exact-generics-v1")
    arguments = parser.parse_args()
    try:
        result = extract_public(arguments.aact_database, arguments.openfda_archive, arguments.output,
                                arguments.mapping_version)
    except (OSError, ValueError, duckdb.Error, zipfile.BadZipFile) as error:
        parser.exit(1, f"PUBLIC_EXTRACT_ERROR {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
