"""Frozen-source research contracts shared by agent tools and trusted checks."""
from collections import Counter


ROLES = ("clinical_trials", "drug_specialist", "quality_assurance")
CONDITIONS = ("", "obesity", "type-2-diabetes")


def validate_selection(source, selection):
    if not isinstance(selection, dict) or selection.get("condition", "") not in CONDITIONS:
        raise ValueError("Choose a supported research condition.")
    candidate = next(
        (row for row in source["candidates"] if row["candidate_id"] == selection.get("candidate_id")), None,
    )
    if candidate is None:
        raise ValueError("Choose a drug from the frozen public catalog.")
    return {"candidate_id": candidate["candidate_id"], "condition": selection.get("condition", "")}


def selected_records(source, selection):
    selection = validate_selection(source, selection)
    candidate, condition = selection["candidate_id"], selection["condition"]
    trials = sorted(
        (row for row in source["trials"] if candidate in row["candidate_ids"]
         and (not condition or condition in row["conditions"])),
        key=lambda row: row["trial_id"],
    )
    reports = sorted(
        (row for row in source["safety_reports"] if candidate in row["candidate_ids"]),
        key=lambda row: row["report_id"],
    )
    return trials, reports


def reference_results(source, selection):
    trials, reports = selected_records(source, selection)
    return {
        "clinical_trials": {
            "source_ids": [row["trial_id"] for row in trials],
            "phase_counts": dict(sorted(Counter(row["phase"] or "NA" for row in trials).items())),
        },
        "drug_specialist": {
            "source_ids": [row["report_id"] for row in reports],
            "reaction_counts": dict(sorted(Counter(
                term for row in reports for term in set(row["reaction_terms"])
            ).items())),
        },
    }


def assess_specialist(role, output, source, selection):
    if role not in ROLES or not isinstance(output, dict):
        return {"passed": False, "task": role, "explanation": "Missing structured specialist result."}
    if role == "quality_assurance":
        expected = reference_results(source, selection)
        passed = (
            set(output) == {"passed", "issues", "clinical_source_ids", "safety_source_ids"}
            and output.get("passed") is True and output.get("issues") == []
            and output.get("clinical_source_ids") == expected["clinical_trials"]["source_ids"]
            and output.get("safety_source_ids") == expected["drug_specialist"]["source_ids"]
        )
    else:
        expected = reference_results(source, selection)[role]
        passed = set(output) == set(expected) and all(output.get(key) == value for key, value in expected.items())
        counts = output.get("phase_counts" if role == "clinical_trials" else "reaction_counts")
        passed = passed and isinstance(counts, dict) and all(type(value) is int for value in counts.values())
    return {
        "passed": bool(passed), "task": role,
        "explanation": "Matches the independently selected frozen records."
        if passed else "Result does not match the selected frozen records or QA approval contract.",
    }


def research_metadata(source):
    return {
        key: source[key] for key in ("dataset_version", "candidates", "sources", "limitations", "coverage_notes")
    }


def research_view(source, selection):
    selection = validate_selection(source, selection)
    trials, reports = selected_records(source, selection)
    reference = reference_results(source, selection)
    return {
        "candidate": next(row for row in source["candidates"] if row["candidate_id"] == selection["candidate_id"]),
        "condition": selection["condition"], "trials": trials, "safety_reports": reports,
        "phase_counts": reference["clinical_trials"]["phase_counts"],
        "reaction_counts": reference["drug_specialist"]["reaction_counts"],
        "dataset_version": source["dataset_version"], "limitations": source["limitations"],
        "coverage_notes": source["coverage_notes"],
    }
