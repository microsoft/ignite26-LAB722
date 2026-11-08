"""Managed-identity model relay; tokens never enter a research Sandbox."""
import asyncio
import logging
import math
import time
from urllib.parse import urlparse

import httpx

from .agent_runtime import MAX_TURNS, WALL_SECONDS, tools_for


LOG = logging.getLogger("reactor.models")


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
        remaining = request.get("remaining_seconds", WALL_SECONDS)
        if type(remaining) not in {int, float} or not math.isfinite(remaining) or not 0 < remaining <= WALL_SECONDS:
            raise ValueError("Sandbox requested an invalid model wall-time budget.")
        deadline = time.monotonic() + remaining
        token = await self.credential.get_token("https://cognitiveservices.azure.com/.default")
        body = {
            "model": self.model, "messages": request["messages"], "tools": tools_for(role),
            "tool_choice": "required", "parallel_tool_calls": False, "max_completion_tokens": 4096,
            "reasoning_effort": "low",
        }
        for attempt in range(3):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Model relay exceeded the specialist wall-time budget.")
            response = await self.http.post(
                self.endpoint, headers={"Authorization": "Bearer " + token.token},
                json=body, timeout=min(60, remaining),
            )
            if response.status_code != 429 or attempt == 2:
                break
            try:
                delay = float(response.headers.get("retry-after", str(2 ** (attempt + 1))))
            except ValueError:
                LOG.error("role=%s model throttle has an invalid retry-after header", role)
                response.raise_for_status()
            if not math.isfinite(delay) or delay < 0 or delay >= deadline - time.monotonic():
                LOG.error("role=%s model throttle exceeds remaining wall-time budget", role)
                response.raise_for_status()
            LOG.warning("role=%s model status=429 retry=%s delay=%s", role, attempt + 1, delay)
            await asyncio.sleep(delay)
        if not response.is_success:
            LOG.error("role=%s model status=%s", role, response.status_code)
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
