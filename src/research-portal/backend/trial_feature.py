from data.pipeline.contracts import Condition
from queries import records


def query_trials(connection, candidate: str, condition: Condition | None) -> list[dict]:
    return records(
        connection,
        """
        SELECT t.*,
            (SELECT list(condition ORDER BY condition) FROM trial_conditions WHERE trial_id = t.trial_id) AS conditions,
            (SELECT list(candidate_id ORDER BY candidate_id) FROM trial_candidates WHERE trial_id = t.trial_id) AS candidate_ids
        FROM trials t JOIN trial_candidates tc ON tc.trial_id = t.trial_id
        WHERE tc.candidate_id = ?
          AND (? IS NULL OR EXISTS (
            SELECT 1 FROM trial_conditions c WHERE c.trial_id = t.trial_id AND c.condition = ?
          ))
        ORDER BY t.trial_id
        """,
        [candidate, condition, condition],
    )
