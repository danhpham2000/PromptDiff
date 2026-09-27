import json

import httpx

from app.config import get_settings

QUEUE_NAME = "promptdiff:experiments"


class UpstashQueue:
    def __init__(self, url: str, token: str):
        self.url = url.rstrip("/")
        self.token = token

    async def enqueue_experiment(self, experiment_id: str, workspace_id: str) -> None:
        payload = json.dumps({"experiment_id": experiment_id, "workspace_id": workspace_id})
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                self.url,
                headers={"Authorization": f"Bearer {self.token}"},
                json=["LPUSH", QUEUE_NAME, payload],
            )
            response.raise_for_status()


def hosted_queue() -> UpstashQueue:
    settings = get_settings()
    if not settings.upstash_redis_rest_url or not settings.upstash_redis_rest_token:
        raise RuntimeError("UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required")
    return UpstashQueue(settings.upstash_redis_rest_url, settings.upstash_redis_rest_token)
