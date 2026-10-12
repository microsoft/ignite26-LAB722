def records(connection, sql: str, parameters: list[object]) -> list[dict]:
    cursor = connection.execute(sql, parameters)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
