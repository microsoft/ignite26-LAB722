from data.pipeline.contracts import Condition


def query_trials(connection, candidate: str, condition: Condition | None) -> list[dict]:
    raise NotImplementedError(
        "The clinical-trials worker must implement the parameterized, read-only trial query."
    )
