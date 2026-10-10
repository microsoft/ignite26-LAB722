def query_safety_reports(connection, candidate: str) -> list[dict]:
    raise NotImplementedError(
        "The drug-safety worker must implement the parameterized, read-only safety-report query."
    )
