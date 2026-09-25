import httpx
import pytest
from app.config import get_settings
from app.providers import GroqProvider, MockProvider, ModelResponse, call_with_retries, provider_for


class FlakyProvider:
    def __init__(self, status_code: int, headers: dict[str, str] | None = None):
        self.status_code = status_code
        self.headers = headers or {}
        self.calls = 0

    async def generate(self, messages, tools, config):
        self.calls += 1
        if self.calls == 1:
            request = httpx.Request("POST", "https://provider.test")
            response = httpx.Response(self.status_code, request=request, headers=self.headers)
            raise httpx.HTTPStatusError("provider error", request=request, response=response)
        return ModelResponse(
            content="ok",
            tool_calls=[],
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            estimated_cost_usd=None,
            pricing_version=None,
        )


@pytest.mark.anyio
async def test_retries_transient_http_status():
    provider = FlakyProvider(429)

    response = await call_with_retries(provider, [], None, {"timeout_seconds": 5})

    assert response.content == "ok"
    assert response.retry_count == 1
    assert response.retry_reasons == ["429"]


@pytest.mark.anyio
async def test_does_not_retry_normal_client_error():
    provider = FlakyProvider(400)

    with pytest.raises(httpx.HTTPStatusError):
        await call_with_retries(provider, [], None, {"timeout_seconds": 5})

    assert provider.calls == 1


@pytest.mark.anyio
async def test_retry_after_is_capped(monkeypatch):
    sleeps = []
    provider = FlakyProvider(429, {"retry-after": "999"})

    async def record_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr("app.providers.asyncio.sleep", record_sleep)

    await call_with_retries(provider, [], None, {"timeout_seconds": 5})

    assert sleeps == [30.0]


def test_groq_is_the_only_remote_provider():
    assert isinstance(provider_for("groq"), GroqProvider)
    assert isinstance(provider_for("mock"), MockProvider)


def test_unsupported_providers_are_invalid():
    with pytest.raises(ValueError, match="Use 'mock' or 'groq'"):
        provider_for("openai")
    with pytest.raises(ValueError, match="Use 'mock' or 'groq'"):
        provider_for("ollama")
    with pytest.raises(ValueError, match="Use 'mock' or 'groq'"):
        provider_for("anthropic")


@pytest.mark.anyio
async def test_groq_requires_api_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        await GroqProvider().generate([], None, {"model": "llama-3.1-8b-instant"})

    get_settings.cache_clear()


@pytest.mark.anyio
async def test_groq_external_service_failure_retries_then_raises(monkeypatch):
    attempts = []

    class FailingAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            attempts.append(url)
            request = httpx.Request("POST", url)
            return httpx.Response(503, request=request)

    async def no_sleep(delay):
        return None

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr("app.providers.httpx.AsyncClient", FailingAsyncClient)
    monkeypatch.setattr("app.providers.asyncio.sleep", no_sleep)
    get_settings.cache_clear()

    with pytest.raises(httpx.HTTPStatusError):
        await call_with_retries(
            GroqProvider(),
            [{"role": "user", "content": "refund"}],
            None,
            {"model": "llama-3.1-8b-instant", "timeout_seconds": 5},
        )

    assert len(attempts) == 4

    get_settings.cache_clear()


@pytest.mark.anyio
async def test_groq_normal_response(monkeypatch):
    calls = {}

    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            calls["url"] = url
            calls["headers"] = headers
            calls["json"] = json
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                request=request,
                json={
                    "choices": [
                        {
                            "message": {
                                "content": "ok",
                                "tool_calls": [
                                    {
                                        "function": {
                                            "name": "refund_customer",
                                            "arguments": "{\"id\":\"sub_123\"}",
                                        }
                                    }
                                ],
                            }
                        }
                    ],
                    "usage": {"prompt_tokens": 7, "completion_tokens": 3},
                },
            )

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr("app.providers.httpx.AsyncClient", FakeAsyncClient)
    get_settings.cache_clear()

    response = await GroqProvider().generate(
        [{"role": "user", "content": "refund"}],
        [{"name": "refund_customer", "description": "Refund a customer."}],
        {"model": "llama-3.1-8b-instant", "timeout_seconds": 5},
    )

    assert calls["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert calls["headers"]["authorization"] == "Bearer gsk_test"
    assert calls["json"]["model"] == "llama-3.1-8b-instant"
    assert response.content == "ok"
    assert response.tool_calls == [{"name": "refund_customer", "arguments": {"id": "sub_123"}}]
    assert response.input_tokens == 7
    assert response.output_tokens == 3
    assert response.estimated_cost_usd is None

    get_settings.cache_clear()


@pytest.mark.anyio
async def test_groq_handles_malformed_tool_arguments(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                request=request,
                json={
                    "choices": [{"message": {"content": None, "tool_calls": [{"function": {"name": "search", "arguments": "not-json"}}]}}],
                    "usage": {},
                },
            )

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr("app.providers.httpx.AsyncClient", FakeAsyncClient)
    get_settings.cache_clear()

    response = await GroqProvider().generate(
        [{"role": "user", "content": "find policy"}],
        None,
        {"model": "llama-3.1-8b-instant", "timeout_seconds": 5},
    )

    assert response.tool_calls == [{"name": "search", "arguments": {"raw": "not-json"}}]
    assert response.input_tokens == 0
    assert response.output_tokens == 0

    get_settings.cache_clear()


@pytest.mark.anyio
async def test_groq_handles_response_without_tool_calls(monkeypatch):
    class FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, headers, json):
            request = httpx.Request("POST", url)
            return httpx.Response(
                200,
                request=request,
                json={
                    "choices": [{"message": {"content": "plain answer"}}],
                    "usage": {"prompt_tokens": 2, "completion_tokens": 4},
                },
            )

    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setattr("app.providers.httpx.AsyncClient", FakeAsyncClient)
    get_settings.cache_clear()

    response = await GroqProvider().generate(
        [{"role": "user", "content": "hello"}],
        None,
        {"model": "llama-3.1-8b-instant", "timeout_seconds": 5},
    )

    assert response.content == "plain answer"
    assert response.tool_calls == []
    assert response.input_tokens == 2
    assert response.output_tokens == 4

    get_settings.cache_clear()
