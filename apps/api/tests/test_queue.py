import pytest
from app.queue import UpstashQueue


@pytest.mark.anyio
async def test_enqueue_experiment_posts_upstash_command(monkeypatch):
    calls = {}

    class FakeClient:
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

            class Response:
                def raise_for_status(self):
                    return None

            return Response()

    monkeypatch.setattr("app.queue.httpx.AsyncClient", FakeClient)

    await UpstashQueue("https://redis.test", "secret").enqueue_experiment("exp-1", "workspace-1")

    assert calls["url"] == "https://redis.test"
    assert calls["headers"]["Authorization"] == "Bearer secret"
    assert calls["json"][0] == "LPUSH"
    assert calls["json"][1] == "promptdiff:experiments"
    assert '"experiment_id": "exp-1"' in calls["json"][2]
