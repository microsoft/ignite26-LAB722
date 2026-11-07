import json

from starlette.exceptions import HTTPException


async def json_body(request, *, maximum=65536):
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Use application/json.")
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > maximum:
            raise HTTPException(413, "Request exceeds the lab input budget.")
        chunks.append(chunk)
    try:
        result = json.loads(b"".join(chunks), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        json.dumps(result, allow_nan=False)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(400, "Request must contain finite JSON.") from None
    if not isinstance(result, dict):
        raise HTTPException(400, "Request must contain a JSON object.")
    return result
