import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models
from app.providers import call_with_retries, provider_for
from app.redaction import redact
from app.schemas import EvaluatorConfig, ExperimentCreate, PromptVersionCreate


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def create_prompt_version(db: Session, prompt_id: str, payload: PromptVersionCreate) -> models.PromptVersion:
    next_number = (db.scalar(select(func.max(models.PromptVersion.version_number)).where(models.PromptVersion.prompt_id == prompt_id)) or 0) + 1
    content = {
        "system_prompt": payload.system_prompt,
        "user_template": payload.user_template,
        "tool_definitions": payload.tool_definitions,
        "metadata": payload.metadata,
        "schema_version": payload.schema_version,
    }
    version = models.PromptVersion(
        prompt_id=prompt_id,
        version_number=next_number,
        system_prompt=payload.system_prompt,
        user_template=payload.user_template,
        tool_definitions=payload.tool_definitions,
        metadata_json=payload.metadata,
        schema_version=payload.schema_version,
        content_hash=stable_hash(content),
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def snapshot_dataset(db: Session, dataset_id: str) -> models.DatasetSnapshot:
    cases = db.scalars(select(models.DatasetCase).where(models.DatasetCase.dataset_id == dataset_id).order_by(models.DatasetCase.created_at)).all()
    snapshot = {
        "schema_version": 1,
        "cases": [
            {
                "id": case.id,
                "name": case.name,
                "input": case.input,
                "expected_output": case.expected_output,
                "metadata": case.metadata_json or {},
            }
            for case in cases
        ],
    }
    row = models.DatasetSnapshot(
        dataset_id=dataset_id,
        content_hash=stable_hash(snapshot),
        schema_version=1,
        snapshot=snapshot,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def render_template(template: str | None, data: dict[str, Any]) -> str:
    out = template or ""
    for key, value in data.items():
        out = out.replace("{{" + key + "}}", str(value))
    return out


def text_diff(a: str | None, b: str | None) -> dict[str, Any]:
    return {"changed": a != b, "baseline": a or "", "candidate": b or ""}


def tool_diff(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = [item.get("name") or item.get("tool_name") for item in a]
    candidate = [item.get("name") or item.get("tool_name") for item in b]
    return {
        "changed": baseline != candidate,
        "baseline_sequence": baseline,
        "candidate_sequence": candidate,
    }


def evaluate_run(db: Session, run: models.Run, expected: dict[str, Any] | None, evaluators: list[EvaluatorConfig], tool_calls: list[dict[str, Any]]) -> None:
    expected = expected or {}
    for evaluator in evaluators:
        state = "passed"
        passed: bool | None = True
        score: float | None = 1.0
        details: dict[str, Any] = {}

        if evaluator.type == "tool_selection":
            expected_tool = (expected.get("tool") or {}).get("name")
            if not expected_tool:
                state, passed, score = "skipped", None, None
            else:
                observed = tool_calls[0].get("name") if tool_calls else None
                passed = observed == expected_tool
                score = 1.0 if passed else 0.0
                details = {"expected": expected_tool, "observed": observed}
        elif evaluator.type == "exact_match":
            expected_text = expected.get("text")
            actual_text = (run.output or {}).get("content")
            if expected_text is None:
                state, passed, score = "skipped", None, None
            else:
                passed = actual_text == expected_text
                score = 1.0 if passed else 0.0
        elif evaluator.type == "contains":
            expected_text = expected.get("contains")
            actual_text = (run.output or {}).get("content") or ""
            if expected_text is None:
                state, passed, score = "skipped", None, None
            else:
                passed = expected_text in actual_text
                score = 1.0 if passed else 0.0
        else:
            state, passed, score = "skipped", None, None
            details = {"reason": f"evaluator '{evaluator.type}' is not implemented in v0.1"}

        db.add(
            models.Evaluation(
                run_id=run.id,
                evaluator_name=evaluator.name,
                evaluator_version="1",
                category=evaluator.category,
                score=score,
                weight=evaluator.weight,
                include_in_quality_score=evaluator.include_in_quality_score,
                passed=passed,
                state=state,
                hard_gate=evaluator.hard_gate,
                details=details,
            )
        )


def quality_score(db: Session, run_ids: list[str]) -> float | None:
    evaluations = db.scalars(select(models.Evaluation).where(models.Evaluation.run_id.in_(run_ids))).all()
    weighted_sum = 0.0
    weight_sum = 0.0
    for ev in evaluations:
        if ev.include_in_quality_score and ev.state == "passed" and ev.score is not None and ev.weight is not None:
            weighted_sum += float(ev.score) * float(ev.weight)
            weight_sum += float(ev.weight)
    return None if weight_sum == 0 else round((weighted_sum / weight_sum) * 100, 2)


def experiment_verdict(db: Session, experiment_id: str, baseline_run_ids: list[str], candidate_run_ids: list[str], regression: dict[str, Any]) -> str:
    failed_runs = db.scalar(select(func.count()).select_from(models.Run).where(models.Run.experiment_id == experiment_id, models.Run.status == "failed"))
    if failed_runs:
        return "ERROR"

    evals = db.scalars(select(models.Evaluation).where(models.Evaluation.run_id.in_(candidate_run_ids))).all()
    if any(ev.hard_gate and ev.state == "passed" and ev.passed is False for ev in evals):
        return "FAIL"

    baseline_quality = quality_score(db, baseline_run_ids)
    candidate_quality = quality_score(db, candidate_run_ids)
    max_drop = (regression.get("quality") or {}).get("max_drop_points")
    if baseline_quality is not None and candidate_quality is not None and max_drop is not None:
        if baseline_quality - candidate_quality > float(max_drop):
            return "FAIL"
    return "PASS"


async def run_experiment(db: Session, experiment: models.Experiment, request: ExperimentCreate) -> models.Experiment:
    experiment.status = "running"
    snapshot = snapshot_dataset(db, request.dataset_id)
    experiment.dataset_snapshot_id = snapshot.id

    baseline_variant = models.ExperimentVariant(
        experiment_id=experiment.id,
        name="baseline",
        provider=request.provider,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        config={"timeout_seconds": request.timeout_seconds},
    )
    candidate_variant = models.ExperimentVariant(
        experiment_id=experiment.id,
        name="candidate",
        provider=request.provider,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        config={"timeout_seconds": request.timeout_seconds},
    )
    db.add_all([baseline_variant, candidate_variant])
    db.commit()

    baseline_prompt = db.get(models.PromptVersion, request.baseline_prompt_version_id)
    candidate_prompt = db.get(models.PromptVersion, request.candidate_prompt_version_id)
    provider = provider_for(request.provider)
    baseline_run_ids: list[str] = []
    candidate_run_ids: list[str] = []

    for case in snapshot.snapshot["cases"]:
        for repetition in range(1, request.repetitions + 1):
            for prompt, variant, bucket in (
                (baseline_prompt, baseline_variant, baseline_run_ids),
                (candidate_prompt, candidate_variant, candidate_run_ids),
            ):
                messages = [
                    {"role": "system", "content": prompt.system_prompt or ""},
                    {"role": "user", "content": render_template(prompt.user_template, case["input"]) or json.dumps(case["input"])},
                ]
                try:
                    response = await call_with_retries(
                        provider,
                        messages,
                        prompt.tool_definitions or [],
                        {
                            "model": request.model,
                            "timeout_seconds": request.timeout_seconds,
                            "temperature": request.temperature,
                            "max_tokens": request.max_tokens,
                        },
                    )
                    output = redact({"content": response.content, "raw_response": response.raw_response})
                    run = models.Run(
                        experiment_id=experiment.id,
                        variant_id=variant.id,
                        dataset_case_id=case["id"],
                        prompt_version_id=prompt.id,
                        repetition=repetition,
                        input=redact(case["input"]),
                        output=output,
                        status="completed",
                        latency_ms=response.latency_ms,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        total_tokens=response.input_tokens + response.output_tokens,
                        estimated_cost_usd=response.estimated_cost_usd,
                        pricing_version=response.pricing_version,
                        retry_count=response.retry_count,
                        retry_reasons=response.retry_reasons,
                        seed_status="unsupported",
                    )
                    db.add(run)
                    db.commit()
                    db.refresh(run)
                    bucket.append(run.id)
                    for i, call in enumerate(response.tool_calls, start=1):
                        db.add(
                            models.ToolCall(
                                run_id=run.id,
                                sequence_number=i,
                                tool_name=call["name"],
                                arguments=redact(call.get("arguments") or {}),
                            )
                        )
                    evaluate_run(db, run, case.get("expected_output"), request.evaluators, response.tool_calls)
                    db.commit()
                except Exception as exc:
                    run = models.Run(
                        experiment_id=experiment.id,
                        variant_id=variant.id,
                        dataset_case_id=case["id"],
                        prompt_version_id=prompt.id,
                        repetition=repetition,
                        input=redact(case["input"]),
                        status="failed",
                        error_message=redact(str(exc)),
                    )
                    db.add(run)
                    db.commit()
                    bucket.append(run.id)

    _create_comparisons(db, experiment.id)
    experiment.verdict = experiment_verdict(db, experiment.id, baseline_run_ids, candidate_run_ids, request.regression)
    experiment.status = "completed" if experiment.verdict in {"PASS", "FAIL"} else "failed"
    experiment.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(experiment)
    return experiment


def _create_comparisons(db: Session, experiment_id: str) -> None:
    variants = db.scalars(select(models.ExperimentVariant).where(models.ExperimentVariant.experiment_id == experiment_id)).all()
    by_name = {variant.name: variant.id for variant in variants}
    baseline_runs = db.scalars(select(models.Run).where(models.Run.variant_id == by_name.get("baseline"))).all()
    candidate_runs = db.scalars(select(models.Run).where(models.Run.variant_id == by_name.get("candidate"))).all()
    candidates = {(run.dataset_case_id, run.repetition): run for run in candidate_runs}
    for baseline in baseline_runs:
        candidate = candidates.get((baseline.dataset_case_id, baseline.repetition))
        if candidate is None:
            continue
        baseline_tools = [
            {"name": row.tool_name, "arguments": row.arguments}
            for row in db.scalars(select(models.ToolCall).where(models.ToolCall.run_id == baseline.id).order_by(models.ToolCall.sequence_number))
        ]
        candidate_tools = [
            {"name": row.tool_name, "arguments": row.arguments}
            for row in db.scalars(select(models.ToolCall).where(models.ToolCall.run_id == candidate.id).order_by(models.ToolCall.sequence_number))
        ]
        db.add(
            models.Comparison(
                experiment_id=experiment_id,
                baseline_run_id=baseline.id,
                candidate_run_id=candidate.id,
                output_diff=text_diff((baseline.output or {}).get("content"), (candidate.output or {}).get("content")),
                tool_diff=tool_diff(baseline_tools, candidate_tools),
                token_delta=(candidate.total_tokens or 0) - (baseline.total_tokens or 0),
                latency_delta_ms=(candidate.latency_ms or 0) - (baseline.latency_ms or 0),
                cost_delta_usd=None
                if baseline.estimated_cost_usd is None or candidate.estimated_cost_usd is None
                else float(candidate.estimated_cost_usd) - float(baseline.estimated_cost_usd),
                regression_status="changed" if baseline.output != candidate.output or baseline_tools != candidate_tools else "unchanged",
            )
        )
    db.commit()
