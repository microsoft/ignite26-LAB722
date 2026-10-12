from queries import records


def query_safety_reports(connection, candidate: str) -> list[dict]:
    return records(
        connection,
        """
        SELECT s.*,
            (SELECT list(candidate_id ORDER BY candidate_id) FROM safety_report_candidates WHERE report_id = s.report_id) AS candidate_ids,
            (SELECT list(reaction_term ORDER BY reaction_term) FROM safety_reactions WHERE report_id = s.report_id) AS reaction_terms
        FROM safety_reports s JOIN safety_report_candidates sc ON sc.report_id = s.report_id
        WHERE sc.candidate_id = ? ORDER BY s.report_id
        """,
        [candidate],
    )
