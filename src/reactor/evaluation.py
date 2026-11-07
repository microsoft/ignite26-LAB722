"""Independent known-answer evaluation, not model approval."""
import json

PHASE_COUNTS = {"NA": 2, "PHASE1": 45, "PHASE2": 23, "PHASE2/PHASE3": 1, "PHASE3": 76, "PHASE4": 21}


def evaluate(task: str, stdout: str, source_records: dict) -> dict:
    value = json.loads(stdout)
    if not isinstance(value, dict):
        raise ValueError("The result must be a JSON object.")
    if task == "phases":
        expected_ids = sorted(record["trial_id"] for record in source_records["trials"])
        counts = value.get("counts")
        passed = (
            isinstance(counts, dict) and all(type(count) is int for count in counts.values())
            and counts == PHASE_COUNTS and value.get("source_ids") == expected_ids
        )
        expected_count = len(expected_ids)
    elif task == "safety":
        expected_count = len(source_records["safety_reports"])
        expected_ids = sorted(record["report_id"] for record in source_records["safety_reports"])
        passed = (
            type(value.get("count")) is int and value["count"] == expected_count
            and value.get("source_ids") == expected_ids
        )
    else:
        raise ValueError("The evaluator supports only the two approved research tasks.")
    return {
        "passed": passed, "task": task, "expected_records": expected_count,
        "method": "independent frozen-source check",
        "explanation": "Execution success alone does not establish a correct research result.",
    }
