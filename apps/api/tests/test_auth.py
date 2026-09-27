import time

import jwt
import pytest
from app.auth import jwks_client, mint_promptdiff_jwt, require_role, validate_neon_jwt, validate_promptdiff_jwt
from app.config import get_settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import HTTPException


def key_pair() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


def configure_jwt(monkeypatch: pytest.MonkeyPatch) -> str:
    private_pem, public_pem = key_pair()
    monkeypatch.setenv("PROMPTDIFF_JWT_ISSUER", "https://app.test")
    monkeypatch.setenv("PROMPTDIFF_JWT_AUDIENCE", "promptdiff-api")
    monkeypatch.setenv("PROMPTDIFF_JWT_KEY_ID", "test-key")
    monkeypatch.setenv("PROMPTDIFF_JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("PROMPTDIFF_JWT_PUBLIC_KEY", public_pem)
    get_settings.cache_clear()
    return private_pem


def test_mints_and_validates_promptdiff_jwt(monkeypatch):
    configure_jwt(monkeypatch)

    token = mint_promptdiff_jwt("user-1", "workspace-1", "owner")
    context = validate_promptdiff_jwt(token)

    assert context.user_id == "user-1"
    assert context.workspace_id == "workspace-1"
    assert context.role == "owner"
    assert context.mode == "hosted"


def test_rejects_wrong_algorithm(monkeypatch):
    configure_jwt(monkeypatch)
    token = jwt.encode(
        {
            "iss": "https://app.test",
            "aud": "promptdiff-api",
            "sub": "user-1",
            "workspace_id": "workspace-1",
            "role": "owner",
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "exp": int(time.time()) + 900,
        },
        "not-ed25519",
        algorithm="HS256",
        headers={"kid": "test-key"},
    )

    with pytest.raises(HTTPException) as exc:
        validate_promptdiff_jwt(token)

    assert exc.value.status_code == 401


def test_role_checks():
    assert require_role("viewer", "viewer") is None
    assert require_role("editor", "viewer") is None
    assert require_role("viewer", "editor").status_code == 403


def test_neon_jwt_requires_correct_audience(monkeypatch):
    calls = {}

    class FakeKey:
        key = "public-key"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def get_signing_key_from_jwt(self, token):
            return FakeKey()

    def fake_decode(token, key, **kwargs):
        calls["kwargs"] = kwargs
        if kwargs.get("audience") != "neon-client-id":
            raise jwt.InvalidAudienceError("wrong audience")
        return {"sub": "neon-user-1", "aud": "neon-client-id", "iss": "https://neon.test"}

    monkeypatch.setenv("NEON_AUTH_BASE_URL", "https://neon.test")
    monkeypatch.setenv("NEON_AUTH_JWKS_URL", "https://neon.test/.well-known/jwks.json")
    monkeypatch.setenv("NEON_AUTH_AUDIENCE", "neon-client-id")
    monkeypatch.setattr("app.auth.jwt.PyJWKClient", FakeClient)
    monkeypatch.setattr("app.auth.jwt.decode", fake_decode)
    get_settings.cache_clear()
    jwks_client.cache_clear()

    claims = validate_neon_jwt("neon-token")

    assert claims["sub"] == "neon-user-1"
    assert calls["kwargs"]["audience"] == "neon-client-id"
    assert calls["kwargs"]["issuer"] == "https://neon.test"
    get_settings.cache_clear()
    jwks_client.cache_clear()


def test_neon_jwks_client_is_cached_with_timeout(monkeypatch):
    created = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            created.append((args, kwargs))

    monkeypatch.setenv("NEON_AUTH_JWKS_URL", "https://neon.test/.well-known/jwks.json")
    get_settings.cache_clear()
    jwks_client.cache_clear()
    monkeypatch.setattr("app.auth.jwt.PyJWKClient", FakeClient)

    assert jwks_client() is jwks_client()

    assert len(created) == 1
    assert created[0][1]["timeout"] == 5
    assert created[0][1]["lifespan"] == 300
    assert created[0][1]["cache_jwk_set"] is True
    get_settings.cache_clear()
    jwks_client.cache_clear()
