import httpx
import pytest

from app.providers import ModelResponse, call_with_retries


class FlakyProvider:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.calls = 0

    async def generate(self, messages, tools, config):
        self.calls += 1
        if self.calls == 1:
            request = httpx.Request("POST", "https://provider.test")
            response = httpx.Response(self.status_code, request=request)
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
