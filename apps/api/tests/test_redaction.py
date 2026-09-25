from app.redaction import redact


def test_redacts_key_and_value_patterns():
    data = {
        "api_key": "sk-secret12345678901234567890",
        "nested": {"Authorization": "Bearer abc.def.ghi"},
        "url": "postgres://user:pass@example.com/db",
        "safe": "hello",
    }

    assert redact(data) == {
        "api_key": "[REDACTED]",
        "nested": {"Authorization": "[REDACTED]"},
        "url": "[REDACTED]",
        "safe": "hello",
    }


def test_redacts_groq_keys():
    assert redact("gsk_secret12345678901234567890") == "[REDACTED]"
