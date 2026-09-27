import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings


@dataclass(frozen=True)
class EncryptedSecret:
    ciphertext: bytes
    nonce: bytes
    key_version: int = 1


def _key() -> bytes:
    value = get_settings().promptdiff_secret_encryption_key
    if not value:
        raise RuntimeError("PROMPTDIFF_SECRET_ENCRYPTION_KEY is required")
    key = base64.b64decode(value)
    if len(key) != 32:
        raise ValueError("PROMPTDIFF_SECRET_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def _aad(workspace_id: str, provider: str) -> bytes:
    return f"{workspace_id}:{provider}".encode()


def encrypt_secret(workspace_id: str, provider: str, plaintext: str) -> EncryptedSecret:
    nonce = os.urandom(12)
    ciphertext = AESGCM(_key()).encrypt(nonce, plaintext.encode(), _aad(workspace_id, provider))
    return EncryptedSecret(ciphertext=ciphertext, nonce=nonce)


def decrypt_secret(workspace_id: str, provider: str, ciphertext: bytes, nonce: bytes) -> str:
    return AESGCM(_key()).decrypt(nonce, ciphertext, _aad(workspace_id, provider)).decode()


def key_hint(secret: str) -> str:
    return f"...{secret[-5:]}"
