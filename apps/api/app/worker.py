import asyncio
import json
import time

import httpx

from app import models
from app.config import get_settings
from app.db import SessionLocal
from app.queue import QUEUE_NAME
from app.retention import cleanup_retention
from app.schemas import ExperimentCreate
from app.services import run_experiment

RETENTION_CLEANUP_INTERVAL_SECONDS = 3600
_last_retention_cleanup = 0.0


async def pop_job() -> dict | None:
    settings = get_settings()
    if not settings.upstash_redis_rest_url or not settings.upstash_redis_rest_token:
        raise RuntimeError("Upstash settings are required")
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            settings.upstash_redis_rest_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.upstash_redis_rest_token}"},
            json=["RPOP", QUEUE_NAME],
        )
        response.raise_for_status()
    result = response.json().get("result")
    return json.loads(result) if result else None


async def run_once() -> bool:
    job = await pop_job()
    if job is None:
        return False
    with SessionLocal() as db:
        experiment = db.get(models.Experiment, job["experiment_id"])
        if experiment is None:
            return True
        if experiment.status != "queued":
            return True
        experiment.status = "running"
        db.commit()
        config = db.get(models.RegressionConfig, experiment.regression_config_id)
        if config is None:
            experiment.status = "failed"
            experiment.verdict = "ERROR"
            db.commit()
            return True
        execution = config.config.get("execution") or {}
        request = ExperimentCreate(
            project_id=experiment.project_id,
            name=experiment.name,
            baseline_prompt_version_id=experiment.baseline_prompt_version_id,
            candidate_prompt_version_id=experiment.candidate_prompt_version_id,
            dataset_id=experiment.dataset_id,
            provider=execution.get("provider", "mock"),
            model=execution.get("model", "mock-support"),
            temperature=execution.get("temperature"),
            max_tokens=execution.get("max_tokens"),
            repetitions=execution.get("repetitions", 1),
            concurrency=execution.get("concurrency", 5),
            timeout_seconds=execution.get("timeout_seconds", 60),
            evaluators=config.config.get("evaluators") or [],
            regression=config.config.get("regression") or {},
        )
        await run_experiment(db, experiment, request)
    return True


def maybe_cleanup_retention() -> None:
    global _last_retention_cleanup
    now = time.monotonic()
    if now - _last_retention_cleanup < RETENTION_CLEANUP_INTERVAL_SECONDS:
        return
    with SessionLocal() as db:
        cleanup_retention(db)
    _last_retention_cleanup = now


async def main() -> None:
    while True:
        maybe_cleanup_retention()
        ran = await run_once()
        if not ran:
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(main())
