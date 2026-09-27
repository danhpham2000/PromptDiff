from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models

DEFAULT_RAW_MODEL_OUTPUT_DAYS = 30
DEFAULT_RAW_PROVIDER_RESPONSE_DAYS = 7


def cleanup_retention(db: Session, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    changed = 0
    rows = db.execute(
        select(models.Run, models.Project.workspace_id)
        .join(models.Experiment, models.Run.experiment_id == models.Experiment.id)
        .join(models.Project, models.Experiment.project_id == models.Project.id)
    ).all()
    for run, workspace_id in rows:
        output = dict(run.output or {})
        if not output:
            continue
        setting = db.get(models.RetentionSetting, workspace_id)
        raw_response_days = setting.raw_provider_response_days if setting else DEFAULT_RAW_PROVIDER_RESPONSE_DAYS
        model_output_days = setting.raw_model_output_days if setting else DEFAULT_RAW_MODEL_OUTPUT_DAYS
        age_days = _age_days(run.created_at, now)
        if age_days > raw_response_days and "raw_response" in output:
            output.pop("raw_response", None)
        if age_days > model_output_days and "content" in output:
            output.pop("content", None)
        if output != (run.output or {}):
            run.output = output
            changed += 1
    if changed:
        db.commit()
    return changed


def _age_days(created_at: datetime, now: datetime) -> int:
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return (now - created_at).days
