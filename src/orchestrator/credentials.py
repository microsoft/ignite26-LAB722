import json
import time

from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError


class InMemoryFoundryCredential:
    """A bounded Foundry-only token handoff across local runtime boundaries."""

    def __init__(self, payload: str):
        value = json.loads(payload)
        if not isinstance(value, dict) or not isinstance(value.get("accessToken"), str) or \
                not value["accessToken"] or not isinstance(value.get("expires_on"), (int, str)):
            raise ValueError("A token handoff requires the Azure CLI token and epoch expiry fields.")
        self._token: AccessToken | None = AccessToken(value["accessToken"], int(value["expires_on"]))
        if self._token.expires_on <= time.time() + 60:
            raise ClientAuthenticationError("The in-memory Foundry credential has expired.")

    async def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:
        if scopes != ("https://ai.azure.com/.default",):
            raise ClientAuthenticationError("The in-memory credential is restricted to Foundry.")
        if kwargs.get("claims"):
            raise ClientAuthenticationError("Claims-based reauthentication requires a fresh token handoff.")
        if self._token is None or self._token.expires_on <= time.time() + 60:
            raise ClientAuthenticationError("Acquire a fresh Foundry token; token handoff cannot refresh.")
        return self._token

    async def close(self) -> None:
        self._token = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
