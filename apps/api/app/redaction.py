import re
from typing import Any

SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "passwd",
    "secret",
    "client_secret",
    "private_key",
    "cookie",
    "set-cookie",
}

VALUE_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.I),
    re.compile(r"Basic\s+[A-Za-z0-9+/=]+", re.I),
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\b(?:sk|ak|rk|xai|anthropic|AIza)[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"[a-z]+://[^:\s]+:[^@\s]+@[^)\s]+", re.I),
]


def redact(value: Any, custom_keys: list[str] | None = None, custom_regex: list[str] | None = None) -> Any:
    keys = SECRET_KEYS | {k.lower() for k in custom_keys or []}
    patterns = VALUE_PATTERNS + [re.compile(p) for p in custom_regex or []]

    def clean(item: Any, key: str | None = None) -> Any:
        if key and key.lower() in keys:
            return "[REDACTED]"
        if isinstance(item, dict):
            return {k: clean(v, k) for k, v in item.items()}
        if isinstance(item, list):
            return [clean(v) for v in item]
        if isinstance(item, str):
            out = item
            for pattern in patterns:
                out = pattern.sub("[REDACTED]", out)
            return out
        return item

    return clean(value)
