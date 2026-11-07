"""Validate the service caller separately from application-asserted ownership."""
import asyncio
from dataclasses import dataclass
from uuid import UUID

import jwt


@dataclass(frozen=True)
class ServiceCaller:
    object_id: str
    tenant_id: str
    audience: str
    authentication: str = "service-authenticated"


class ServiceTokenVerifier:
    def __init__(self, tenant_id: str, audience: str, permitted_object_ids: set[str]):
        self.tenant_id = str(UUID(tenant_id))
        self.audience = audience
        self.permitted = {str(UUID(value)) for value in permitted_object_ids}
        if not audience or not self.permitted:
            raise ValueError("An API audience and permitted service identities are required.")
        self.keys = jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys",
            timeout=10,
        )

    def _verify(self, token: str) -> ServiceCaller:
        key = self.keys.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=["RS256"], audience=self.audience,
            options={"require": ["exp", "iat", "iss", "aud", "tid", "oid"]},
        )
        issuers = {
            f"https://sts.windows.net/{self.tenant_id}/",
            f"https://login.microsoftonline.com/{self.tenant_id}/v2.0",
        }
        if claims["iss"] not in issuers or claims["tid"] != self.tenant_id:
            raise PermissionError("The service token issuer does not match this allocation.")
        object_id = str(UUID(claims["oid"]))
        if object_id not in self.permitted:
            raise PermissionError("The authenticated identity is not a permitted service caller.")
        if "scp" in claims:
            raise PermissionError("Delegated user tokens are not accepted by the execution API.")
        return ServiceCaller(object_id, self.tenant_id, self.audience)

    async def verify(self, authorization: str) -> ServiceCaller:
        if not authorization.startswith("Bearer ") or len(authorization) > 16384:
            raise PermissionError("A bounded bearer service token is required.")
        try:
            return await asyncio.to_thread(self._verify, authorization[7:])
        except (jwt.PyJWTError, ValueError) as error:
            raise PermissionError("Service token validation failed.") from error
