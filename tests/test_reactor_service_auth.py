import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from src.reactor.service_auth import ServiceTokenVerifier


class ServiceAuthentication(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        self.tenant, self.caller = str(uuid4()), str(uuid4())
        self.verifier = ServiceTokenVerifier(self.tenant, "api://execution", {self.caller})
        self.verifier.keys = Mock()
        self.verifier.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=self.private.public_key())

    def token(self, **changes):
        claims = {
            "iss": f"https://sts.windows.net/{self.tenant}/", "tid": self.tenant,
            "aud": "api://execution", "oid": self.caller,
            "iat": int(time.time()), "exp": int(time.time()) + 60,
        }
        claims.update(changes)
        return "Bearer " + jwt.encode(claims, self.private, algorithm="RS256")

    async def test_allowed_service_identity_has_no_demo_user_claim(self):
        caller = await self.verifier.verify(self.token())
        self.assertEqual(caller.object_id, self.caller)
        self.assertEqual(caller.authentication, "service-authenticated")

    async def test_wrong_audience_issuer_identity_delegation_and_expiry_denied(self):
        for changes in [
            {"aud": "api://other"}, {"iss": "https://attacker.example"},
            {"tid": str(uuid4())}, {"oid": str(uuid4())}, {"scp": "user.read"},
            {"exp": int(time.time()) - 1},
        ]:
            with self.subTest(changes=changes), self.assertRaises(PermissionError):
                await self.verifier.verify(self.token(**changes))

    async def test_bad_signature_and_missing_bearer_denied(self):
        other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        token = jwt.encode(jwt.decode(self.token()[7:], options={"verify_signature": False}), other, algorithm="RS256")
        with self.assertRaises(PermissionError):
            await self.verifier.verify("Bearer " + token)
        with self.assertRaises(PermissionError):
            await self.verifier.verify("")


if __name__ == "__main__":
    unittest.main()
