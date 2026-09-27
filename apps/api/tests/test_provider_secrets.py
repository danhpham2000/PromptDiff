import base64
import os

from app.config import get_settings
from app.provider_secrets import decrypt_secret, encrypt_secret, key_hint


def test_encrypts_and_decrypts_provider_secret(monkeypatch):
    monkeypatch.setenv("PROMPTDIFF_SECRET_ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())
    get_settings.cache_clear()

    encrypted = encrypt_secret("workspace-1", "groq", "gsk_secret12345678901234567890")

    assert encrypted.ciphertext != b"gsk_secret12345678901234567890"
    assert encrypted.nonce
    assert decrypt_secret("workspace-1", "groq", encrypted.ciphertext, encrypted.nonce) == "gsk_secret12345678901234567890"
    get_settings.cache_clear()


def test_key_hint_never_returns_full_secret():
    assert key_hint("gsk_secret12345678901234567890") == "...67890"
