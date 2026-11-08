"""Managed-identity model relay; tokens never enter a research Sandbox."""
from urllib.parse import urlparse

import httpx

from .agent_runtime import MAX_TURNS, tools_for


class ModelRelay:
    def __init__(self, endpoint, model, credential):
        parsed = urlparse(endpoint)
        if (
            parsed.scheme != "https" or not parsed.hostname
            or not parsed.hostname.endswith(".openai.azure.com")
            or parsed.path != "/openai/v1/chat/completions" or parsed.query
            or parsed.username or parsed.password or parsed.fragment or not model
        ):
            raise ValueError("Configure the allocated Azure OpenAI v1 model endpoint and deployment.")
        self.endpoint, self.model, self.credential = endpoint, model, credential
        self.http = httpx.AsyncClient(timeout=60)

    async def complete(self, role, request):
        if (
            type(request.get("turn")) is not int or not 1 <= request["turn"] <= MAX_TURNS
            or request.get("tools") != tools_for(role)
            or not isinstance(request.get("messages"), list) or not request["messages"]
            or len(request["messages"]) > 64
        ):
            raise ValueError("Sandbox requested an invalid model/tool contract.")
        token = await self.credential.get_token("https://cognitiveservices.azure.com/.default")
        response = await self.http.post(self.endpoint, headers={"Authorization": "Bearer " + token.token}, json={
            "model": self.model, "messages": request["messages"], "tools": tools_for(role),
            "tool_choice": "required", "parallel_tool_calls": False, "max_completion_tokens": 4096,
            "reasoning_effort": "low",
        })
        response.raise_for_status()
        value = response.json()
        choices = value.get("choices") if isinstance(value, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ValueError("Model returned no valid assistant choice.")
        message = choices[0].get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise ValueError("Model returned an invalid assistant message.")
        return {"request_id": request["request_id"], "message": message, "usage": value.get("usage", {})}

    async def close(self):
        await self.http.aclose()
