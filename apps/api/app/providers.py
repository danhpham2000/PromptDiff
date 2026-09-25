import asyncio
import json
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.pricing import estimate_cost


@dataclass
class ModelResponse:
    content: str | None
    tool_calls: list[dict[str, Any]]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost_usd: float | None
    pricing_version: str | None
    raw_response: dict[str, Any] | None = None
    retry_count: int = 0
    retry_reasons: list[str] = field(default_factory=list)


class ModelProvider(Protocol):
    async def generate(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None, config: dict[str, Any]) -> ModelResponse:
        ...


class MockProvider:
    async def generate(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None, config: dict[str, Any]) -> ModelResponse:
        started = time.perf_counter()
        text = messages[-1]["content"] if messages else ""
        wants_enterprise = "enterprise" in text.lower() or "annual" in text.lower()
        tool_name = "escalate_to_human" if wants_enterprise else "refund_customer"
        content = f"Mock response using {tool_name}."
        input_tokens = max(1, len(text.split()))
        output_tokens = len(content.split())
        cost, pricing_version = estimate_cost("mock", config.get("model", "mock-support"), input_tokens, output_tokens)
        return ModelResponse(
            content=content,
            tool_calls=[{"name": tool_name, "arguments": {}}],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
            estimated_cost_usd=cost,
            pricing_version=pricing_version,
            raw_response={"provider": "mock"},
        )


class OpenAIProvider:
    async def generate(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None, config: dict[str, Any]) -> ModelResponse:
        settings = get_settings()
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for provider 'openai'")
        started = time.perf_counter()
        payload: dict[str, Any] = {
            "model": config["model"],
            "messages": messages,
        }
        if tools:
            payload["tools"] = [{"type": "function", "function": tool} for tool in tools]
        if config.get("temperature") is not None:
            payload["temperature"] = config["temperature"]
        if config.get("max_tokens") is not None:
            payload["max_tokens"] = config["max_tokens"]
        async with httpx.AsyncClient(timeout=float(config.get("timeout_seconds", 60))) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"authorization": f"Bearer {settings.openai_api_key}"},
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        message = data["choices"][0]["message"]
        usage = data.get("usage") or {}
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function = call.get("function") or {}
            try:
                arguments = json.loads(function.get("arguments") or "{}")
            except json.JSONDecodeError:
                arguments = {"raw": function.get("arguments")}
            tool_calls.append({"name": function.get("name"), "arguments": arguments})
        input_tokens = int(usage.get("prompt_tokens") or 0)
        output_tokens = int(usage.get("completion_tokens") or 0)
        cost, pricing_version = estimate_cost("openai", config["model"], input_tokens, output_tokens)
        return ModelResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
            estimated_cost_usd=cost,
            pricing_version=pricing_version,
            raw_response=data,
        )


class AnthropicProvider:
    async def generate(self, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None, config: dict[str, Any]) -> ModelResponse:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for provider 'anthropic'")
        started = time.perf_counter()
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        user_messages = [m for m in messages if m["role"] != "system"]
        payload: dict[str, Any] = {
            "model": config["model"],
            "messages": user_messages,
            "max_tokens": config.get("max_tokens") or 1024,
        }
        if system:
            payload["system"] = system
        if tools:
            payload["tools"] = tools
        if config.get("temperature") is not None:
            payload["temperature"] = config["temperature"]
        async with httpx.AsyncClient(timeout=float(config.get("timeout_seconds", 60))) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        content_parts = data.get("content") or []
        text = "\n".join(part.get("text", "") for part in content_parts if part.get("type") == "text") or None
        tool_calls = [
            {"name": part.get("name"), "arguments": part.get("input") or {}}
            for part in content_parts
            if part.get("type") == "tool_use"
        ]
        usage = data.get("usage") or {}
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cost, pricing_version = estimate_cost("anthropic", config["model"], input_tokens, output_tokens)
        return ModelResponse(
            content=text,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((time.perf_counter() - started) * 1000),
            estimated_cost_usd=cost,
            pricing_version=pricing_version,
            raw_response=data,
        )


async def call_with_retries(provider: ModelProvider, messages: list[dict[str, str]], tools: list[dict[str, Any]] | None, config: dict[str, Any]) -> ModelResponse:
    retry_reasons: list[str] = []
    delays = [1, 2, 4]
    for attempt in range(4):
        try:
            response = await asyncio.wait_for(
                provider.generate(messages, tools, config),
                timeout=float(config.get("timeout_seconds", 60)),
            )
            response.retry_count = attempt
            response.retry_reasons = retry_reasons
            return response
        except (TimeoutError, ConnectionError, httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
            if status_code is not None and status_code not in {408, 429, 500, 502, 503, 504}:
                raise
            retry_reasons.append(str(status_code or type(exc).__name__))
            if attempt == 3:
                raise
            await asyncio.sleep(_retry_delay(exc, delays[attempt]))
    raise RuntimeError("unreachable")


def _retry_delay(exc: Exception, fallback: int) -> float:
    if isinstance(exc, httpx.HTTPStatusError):
        retry_after = exc.response.headers.get("retry-after")
        if retry_after:
            if retry_after.isdigit():
                return float(retry_after)
            try:
                return max(0.0, (parsedate_to_datetime(retry_after).timestamp() - time.time()))
            except (TypeError, ValueError):
                pass
    return float(fallback)


def provider_for(name: str) -> ModelProvider:
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAIProvider()
    if name == "anthropic":
        return AnthropicProvider()
    raise ValueError(f"Provider '{name}' is not configured. Use 'mock' or add provider credentials.")
