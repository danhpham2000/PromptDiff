import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

import yaml
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import models, schemas
from app.auth import AuthContext, current_context, mint_promptdiff_jwt, require_role, validate_neon_jwt
from app.config import get_settings
from app.db import get_db
from app.provider_secrets import encrypt_secret, key_hint
from app.queue import hosted_queue
from app.services import create_prompt_version, run_experiment, slugify

router = APIRouter(prefix="/api/v1")


def require(row: Any, name: str = "resource") -> Any:
    if row is None:
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return row


def require_permission(ctx: AuthContext, role: str) -> None:
    if error := require_role(ctx.role, role):
        raise error


def require_workspace(ctx: AuthContext, workspace_id: str) -> None:
    if ctx.mode == "hosted" and ctx.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="FORBIDDEN")


def require_hosted(ctx: AuthContext) -> None:
    if ctx.mode != "hosted":
        raise HTTPException(status_code=404, detail="HOSTED_ONLY")


def require_project(db: Session, project_id: str, ctx: AuthContext) -> models.Project:
    project = require(db.get(models.Project, project_id), "project")
    if ctx.mode == "hosted" and project.workspace_id != ctx.workspace_id:
        raise HTTPException(status_code=404, detail="project not found")
    return project


def require_prompt(db: Session, prompt_id: str, ctx: AuthContext) -> models.Prompt:
    prompt = require(db.get(models.Prompt, prompt_id), "prompt")
    require_project(db, prompt.project_id, ctx)
    return prompt


def require_dataset(db: Session, dataset_id: str, ctx: AuthContext) -> models.Dataset:
    dataset = require(db.get(models.Dataset, dataset_id), "dataset")
    require_project(db, dataset.project_id, ctx)
    return dataset


def require_experiment(db: Session, experiment_id: str, ctx: AuthContext) -> models.Experiment:
    experiment = require(db.get(models.Experiment, experiment_id), "experiment")
    require_project(db, experiment.project_id, ctx)
    return experiment


def require_regression_config(db: Session, config_id: str, ctx: AuthContext) -> models.RegressionConfig:
    config = require(db.get(models.RegressionConfig, config_id), "regression config")
    require_project(db, config.project_id, ctx)
    return config


def record_audit(
    db: Session,
    ctx: AuthContext,
    action: str,
    resource_type: str,
    resource_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if ctx.mode != "hosted":
        return
    db.add(
        models.AuditEvent(
            actor_id=ctx.user_id,
            workspace_id=ctx.workspace_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_json=metadata or {},
        )
    )
    db.commit()


def experiment_config(payload: schemas.ExperimentCreate) -> dict[str, Any]:
    return {
        "execution": {
            "provider": payload.provider,
            "model": payload.model,
            "temperature": payload.temperature,
            "max_tokens": payload.max_tokens,
            "repetitions": payload.repetitions,
            "concurrency": payload.concurrency,
            "timeout_seconds": payload.timeout_seconds,
        },
        "evaluators": [item.model_dump() for item in payload.evaluators],
        "regression": payload.regression,
    }


@router.post("/auth/neon/exchange")
def exchange_neon_token(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="AUTH_REQUIRED")
    claims = validate_neon_jwt(authorization.split(" ", 1)[1])
    subject = claims["sub"]
    email = claims.get("email")
    name = claims.get("name") or email or "PromptDiff User"
    now = datetime.now(timezone.utc)
    user = db.scalar(select(models.User).where(models.User.auth_provider == "neon", models.User.auth_subject == subject))
    if user is None:
        user = models.User(auth_provider="neon", auth_subject=subject, email=email, name=name, last_login_at=now)
        db.add(user)
        db.flush()
    else:
        user.email = email
        user.name = name
        user.last_login_at = now
    member = db.scalar(select(models.WorkspaceMember).where(models.WorkspaceMember.user_id == user.id))
    if member is None:
        workspace = models.Workspace(name=f"{name}'s Workspace")
        db.add(workspace)
        db.flush()
        member = models.WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
        db.add(member)
        db.commit()
        record_audit(db, AuthContext(user.id, workspace.id, "owner", "hosted"), "workspace.create", "workspace", workspace.id)
    else:
        db.commit()
        workspace = require(db.get(models.Workspace, member.workspace_id), "workspace")
    token = mint_promptdiff_jwt(user.id, workspace.id, member.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
        "workspace": {"id": workspace.id, "name": workspace.name, "role": member.role},
    }


@router.get("/me")
def get_me(ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    if ctx.mode != "hosted":
        return {
            "id": ctx.user_id,
            "email": None,
            "name": "Local User",
            "active_workspace": {"id": ctx.workspace_id, "name": "Local Workspace", "role": ctx.role},
        }
    user = require(db.get(models.User, ctx.user_id), "user")
    workspace = require(db.get(models.Workspace, ctx.workspace_id), "workspace")
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "active_workspace": {"id": workspace.id, "name": workspace.name, "role": ctx.role},
    }


@router.get("/workspaces")
def list_workspaces(ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    if ctx.mode != "hosted":
        return {"items": [{"id": ctx.workspace_id, "name": "Local Workspace", "role": ctx.role, "created_at": None}]}
    rows = db.execute(
        select(models.Workspace, models.WorkspaceMember.role)
        .join(models.WorkspaceMember, models.Workspace.id == models.WorkspaceMember.workspace_id)
        .where(models.WorkspaceMember.user_id == ctx.user_id)
    ).all()
    return {"items": [{"id": workspace.id, "name": workspace.name, "role": role, "created_at": workspace.created_at} for workspace, role in rows]}


@router.post("/workspaces")
def create_workspace(payload: schemas.WorkspaceCreate, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_hosted(ctx)
    require_permission(ctx, "editor")
    workspace = models.Workspace(name=payload.name)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    db.add(models.WorkspaceMember(workspace_id=workspace.id, user_id=ctx.user_id, role="owner"))
    db.commit()
    created_context = AuthContext(user_id=ctx.user_id, workspace_id=workspace.id, role="owner", mode=ctx.mode)
    record_audit(db, created_context, "workspace.create", "workspace", workspace.id)
    return {"id": workspace.id, "name": workspace.name, "role": "owner", "created_at": workspace.created_at}


@router.get("/workspaces/{workspace_id}/provider-secrets")
def list_provider_secrets(workspace_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_hosted(ctx)
    require_workspace(ctx, workspace_id)
    require_permission(ctx, "owner")
    rows = db.scalars(select(models.ProviderSecret).where(models.ProviderSecret.workspace_id == workspace_id)).all()
    return {"items": [{"provider": row.provider, "configured": True, "key_hint": row.key_hint, "created_at": row.created_at} for row in rows]}


@router.post("/workspaces/{workspace_id}/provider-secrets", response_model=schemas.ProviderSecretOut)
def upsert_provider_secret(
    workspace_id: str,
    payload: schemas.ProviderSecretCreate,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_hosted(ctx)
    require_workspace(ctx, workspace_id)
    require_permission(ctx, "owner")
    encrypted = encrypt_secret(workspace_id, payload.provider, payload.api_key)
    row = db.scalar(
        select(models.ProviderSecret).where(
            models.ProviderSecret.workspace_id == workspace_id,
            models.ProviderSecret.provider == payload.provider,
        )
    )
    if row is None:
        row = models.ProviderSecret(workspace_id=workspace_id, provider=payload.provider)
        db.add(row)
    row.ciphertext = encrypted.ciphertext
    row.nonce = encrypted.nonce
    row.key_version = encrypted.key_version
    row.key_hint = key_hint(payload.api_key)
    db.commit()
    db.refresh(row)
    record_audit(db, ctx, "provider_secret.upsert", "provider_secret", row.id, {"provider": row.provider})
    return {"provider": row.provider, "configured": True, "key_hint": row.key_hint, "created_at": row.created_at}


@router.delete("/workspaces/{workspace_id}/provider-secrets/{provider}")
def delete_provider_secret(workspace_id: str, provider: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> Response:
    require_hosted(ctx)
    require_workspace(ctx, workspace_id)
    require_permission(ctx, "owner")
    row = db.scalar(
        select(models.ProviderSecret).where(
            models.ProviderSecret.workspace_id == workspace_id,
            models.ProviderSecret.provider == provider,
        )
    )
    if row is not None:
        secret_id = row.id
        db.delete(row)
        db.commit()
        record_audit(db, ctx, "provider_secret.delete", "provider_secret", secret_id, {"provider": provider})
    return Response(status_code=204)


@router.get("/workspaces/{workspace_id}/retention", response_model=schemas.RetentionOut)
def get_retention(workspace_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.RetentionSetting:
    require_hosted(ctx)
    require_workspace(ctx, workspace_id)
    require_permission(ctx, "viewer")
    row = db.get(models.RetentionSetting, workspace_id)
    if row is None:
        row = models.RetentionSetting(workspace_id=workspace_id)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.put("/workspaces/{workspace_id}/retention", response_model=schemas.RetentionOut)
def update_retention(
    workspace_id: str,
    payload: schemas.RetentionOut,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> models.RetentionSetting:
    require_hosted(ctx)
    require_workspace(ctx, workspace_id)
    require_permission(ctx, "owner")
    row = db.get(models.RetentionSetting, workspace_id) or models.RetentionSetting(workspace_id=workspace_id)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    record_audit(db, ctx, "retention.update", "retention_setting", workspace_id)
    return row


@router.get("/workspaces/{workspace_id}/audit-events")
def list_audit_events(workspace_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    require_hosted(ctx)
    require_workspace(ctx, workspace_id)
    require_permission(ctx, "owner")
    rows = db.scalars(
        select(models.AuditEvent)
        .where(models.AuditEvent.workspace_id == workspace_id)
        .order_by(models.AuditEvent.created_at.desc())
    ).all()
    return {
        "items": [
            {
                "id": row.id,
                "actor_id": row.actor_id,
                "workspace_id": row.workspace_id,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "metadata": row.metadata_json or {},
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "next_cursor": None,
    }


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Project:
    require_permission(ctx, "editor")
    project = models.Project(
        user_id=ctx.user_id,
        workspace_id=ctx.workspace_id,
        name=payload.name,
        slug=payload.slug or slugify(payload.name),
        description=payload.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> list[models.Project]:
    stmt = select(models.Project).order_by(models.Project.created_at.desc())
    if ctx.mode == "hosted":
        stmt = stmt.where(models.Project.workspace_id == ctx.workspace_id)
    return list(db.scalars(stmt))


@router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Project:
    return require_project(db, project_id, ctx)


@router.post("/prompts", response_model=schemas.PromptOut)
def create_prompt(payload: schemas.PromptCreate, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Prompt:
    require_permission(ctx, "editor")
    require_project(db, payload.project_id, ctx)
    prompt = models.Prompt(project_id=payload.project_id, name=payload.name, description=payload.description)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("/prompts", response_model=list[schemas.PromptOut])
def list_prompts(project_id: str | None = None, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> list[models.Prompt]:
    stmt = select(models.Prompt).order_by(models.Prompt.created_at.desc())
    if project_id:
        require_project(db, project_id, ctx)
        stmt = stmt.where(models.Prompt.project_id == project_id)
    elif ctx.mode == "hosted":
        stmt = stmt.join(models.Project, models.Prompt.project_id == models.Project.id).where(models.Project.workspace_id == ctx.workspace_id)
    return list(db.scalars(stmt))


@router.get("/prompts/{prompt_id}", response_model=schemas.PromptOut)
def get_prompt(prompt_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Prompt:
    return require_prompt(db, prompt_id, ctx)


@router.post("/prompts/{prompt_id}/versions", response_model=schemas.PromptVersionOut)
def create_version(
    prompt_id: str,
    payload: schemas.PromptVersionCreate,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> models.PromptVersion:
    require_permission(ctx, "editor")
    require_prompt(db, prompt_id, ctx)
    return create_prompt_version(db, prompt_id, payload)


@router.get("/prompts/{prompt_id}/versions", response_model=list[schemas.PromptVersionOut])
def list_versions(prompt_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> list[models.PromptVersion]:
    require_prompt(db, prompt_id, ctx)
    return list(db.scalars(select(models.PromptVersion).where(models.PromptVersion.prompt_id == prompt_id).order_by(models.PromptVersion.version_number)))


@router.get("/prompt-versions/{version_id}", response_model=schemas.PromptVersionOut)
def get_version(version_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.PromptVersion:
    version = require(db.get(models.PromptVersion, version_id), "prompt version")
    require_prompt(db, version.prompt_id, ctx)
    return version


@router.post("/datasets", response_model=schemas.DatasetOut)
def create_dataset(payload: schemas.DatasetCreate, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Dataset:
    require_permission(ctx, "editor")
    require_project(db, payload.project_id, ctx)
    dataset = models.Dataset(project_id=payload.project_id, name=payload.name, description=payload.description)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=list[schemas.DatasetOut])
def list_datasets(project_id: str | None = None, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> list[models.Dataset]:
    stmt = select(models.Dataset).order_by(models.Dataset.created_at.desc())
    if project_id:
        require_project(db, project_id, ctx)
        stmt = stmt.where(models.Dataset.project_id == project_id)
    elif ctx.mode == "hosted":
        stmt = stmt.join(models.Project, models.Dataset.project_id == models.Project.id).where(models.Project.workspace_id == ctx.workspace_id)
    return list(db.scalars(stmt))


@router.post("/datasets/import", response_model=schemas.DatasetOut)
def import_dataset(payload: schemas.DatasetImport, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Dataset:
    require_permission(ctx, "editor")
    require_project(db, payload.project_id, ctx)
    try:
        parsed = yaml.safe_load(payload.content) if payload.format == "yaml" else json.loads(payload.content)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise HTTPException(status_code=400, detail="invalid dataset import content") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("name"), str):
        raise HTTPException(status_code=400, detail="dataset import requires a name")
    cases = parsed.get("cases", [])
    if not isinstance(cases, list):
        raise HTTPException(status_code=400, detail="dataset import cases must be a list")
    if len(cases) > 1_000:
        raise HTTPException(status_code=400, detail="dataset import supports at most 1000 cases")
    for case in cases:
        if not isinstance(case, dict) or "input" not in case:
            raise HTTPException(status_code=400, detail="dataset case requires input")
    dataset = models.Dataset(project_id=payload.project_id, name=parsed["name"], description=parsed.get("description"))
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    for case in cases:
        db.add(
            models.DatasetCase(
                dataset_id=dataset.id,
                name=case.get("name"),
                input=case["input"],
                expected_output=case.get("expected") or case.get("expected_output"),
                metadata_json=case.get("metadata") or {},
            )
        )
    db.commit()
    return dataset


@router.post("/datasets/{dataset_id}/cases", response_model=schemas.DatasetCaseOut)
def add_case(
    dataset_id: str,
    payload: schemas.DatasetCaseCreate,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> models.DatasetCase:
    require_permission(ctx, "editor")
    require_dataset(db, dataset_id, ctx)
    case = models.DatasetCase(
        dataset_id=dataset_id,
        name=payload.name,
        input=payload.input,
        expected_output=payload.expected_output,
        metadata_json=payload.metadata,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.get("/datasets/{dataset_id}/cases", response_model=list[schemas.DatasetCaseOut])
def list_cases(dataset_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> list[models.DatasetCase]:
    require_dataset(db, dataset_id, ctx)
    return list(db.scalars(select(models.DatasetCase).where(models.DatasetCase.dataset_id == dataset_id).order_by(models.DatasetCase.created_at)))


@router.post("/projects/{project_id}/regression-configs", response_model=schemas.RegressionConfigOut)
def create_regression_config(
    project_id: str,
    payload: dict[str, Any],
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> models.RegressionConfig:
    require_permission(ctx, "editor")
    require_project(db, project_id, ctx)
    name = payload.get("name", "default")
    version = 1
    row = models.RegressionConfig(
        project_id=project_id,
        name=name,
        version=version,
        schema_version=payload.get("config", {}).get("schema_version", 1),
        config=payload.get("config", {}),
        created_by=ctx.user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/projects/{project_id}/regression-configs", response_model=list[schemas.RegressionConfigOut])
def list_regression_configs(
    project_id: str,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> list[models.RegressionConfig]:
    require_project(db, project_id, ctx)
    return list(
        db.scalars(
            select(models.RegressionConfig)
            .where(models.RegressionConfig.project_id == project_id)
            .order_by(models.RegressionConfig.created_at.desc())
        )
    )


@router.get("/projects/{project_id}/regression-configs/{config_id}", response_model=schemas.RegressionConfigOut)
def get_project_regression_config(
    project_id: str,
    config_id: str,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> models.RegressionConfig:
    require_project(db, project_id, ctx)
    config = require_regression_config(db, config_id, ctx)
    if config.project_id != project_id:
        raise HTTPException(status_code=404, detail="regression config not found")
    return config


@router.get("/regression-configs/{config_id}", response_model=schemas.RegressionConfigOut)
def get_regression_config(
    config_id: str,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> models.RegressionConfig:
    return require_regression_config(db, config_id, ctx)


@router.post("/experiments", response_model=schemas.ExperimentOut)
async def create_experiment(payload: schemas.ExperimentCreate, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Experiment:
    require_permission(ctx, "editor")
    require_project(db, payload.project_id, ctx)
    baseline = require(db.get(models.PromptVersion, payload.baseline_prompt_version_id), "baseline prompt version")
    candidate = require(db.get(models.PromptVersion, payload.candidate_prompt_version_id), "candidate prompt version")
    require_prompt(db, baseline.prompt_id, ctx)
    require_prompt(db, candidate.prompt_id, ctx)
    require_dataset(db, payload.dataset_id, ctx)
    config = models.RegressionConfig(
        project_id=payload.project_id,
        name=f"{payload.name}-config",
        version=1,
        schema_version=1,
        config=experiment_config(payload),
        created_by=ctx.user_id,
    )
    db.add(config)
    db.commit()
    experiment = models.Experiment(
        project_id=payload.project_id,
        name=payload.name,
        baseline_prompt_version_id=payload.baseline_prompt_version_id,
        candidate_prompt_version_id=payload.candidate_prompt_version_id,
        dataset_id=payload.dataset_id,
        regression_config_id=config.id,
        regression_config_version=config.version,
        status="created",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    if get_settings().promptdiff_mode == "hosted":
        experiment.status = "queued"
        db.commit()
        db.refresh(experiment)
        try:
            await hosted_queue().enqueue_experiment(experiment.id, ctx.workspace_id)
        except Exception as exc:
            experiment.status = "failed"
            experiment.verdict = "ERROR"
            db.commit()
            raise HTTPException(status_code=503, detail="QUEUE_UNAVAILABLE") from exc
        record_audit(db, ctx, "experiment.queued", "experiment", experiment.id)
        return experiment
    return await run_experiment(db, experiment, payload)


@router.get("/experiments", response_model=list[schemas.ExperimentOut])
def list_experiments(project_id: str | None = None, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> list[models.Experiment]:
    stmt = select(models.Experiment).order_by(models.Experiment.created_at.desc())
    if project_id:
        require_project(db, project_id, ctx)
        stmt = stmt.where(models.Experiment.project_id == project_id)
    elif ctx.mode == "hosted":
        stmt = stmt.join(models.Project, models.Experiment.project_id == models.Project.id).where(models.Project.workspace_id == ctx.workspace_id)
    return list(db.scalars(stmt))


@router.get("/experiments/{experiment_id}", response_model=schemas.ExperimentOut)
def get_experiment(experiment_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> models.Experiment:
    return require_experiment(db, experiment_id, ctx)


def _seconds_between(start: datetime, end: datetime | None) -> int:
    finished_at = end or datetime.now(timezone.utc)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if finished_at.tzinfo is None:
        finished_at = finished_at.replace(tzinfo=timezone.utc)
    return max(0, int((finished_at - start).total_seconds()))


def _expected_run_count(db: Session, experiment: models.Experiment) -> int | None:
    if not experiment.dataset_snapshot_id:
        return None
    snapshot = db.get(models.DatasetSnapshot, experiment.dataset_snapshot_id)
    if snapshot is None:
        return None
    config = db.get(models.RegressionConfig, experiment.regression_config_id) if experiment.regression_config_id else None
    repetitions = ((config.config if config else {}).get("execution") or {}).get("repetitions", 1)
    cases = snapshot.snapshot.get("cases") or []
    try:
        parsed_repetitions = int(repetitions or 1)
    except (TypeError, ValueError):
        parsed_repetitions = 1
    parsed_repetitions = min(max(parsed_repetitions, 1), 5)
    return len(cases) * parsed_repetitions * 2


@router.get("/experiments/{experiment_id}/progress")
def experiment_progress(experiment_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    experiment = require_experiment(db, experiment_id, ctx)
    total_runs = _expected_run_count(db, experiment)
    completed_runs = db.scalar(
        select(func.count()).select_from(models.Run).where(models.Run.experiment_id == experiment.id, models.Run.status == "completed")
    )
    failed_runs = db.scalar(
        select(func.count()).select_from(models.Run).where(models.Run.experiment_id == experiment.id, models.Run.status == "failed")
    )
    completed_runs = int(completed_runs or 0)
    failed_runs = int(failed_runs or 0)
    pending_runs = 0 if total_runs is None else max(total_runs - completed_runs - failed_runs, 0)
    progress_percent = None if total_runs is None or total_runs == 0 else round(((completed_runs + failed_runs) / total_runs) * 100)
    return {
        "id": experiment.id,
        "status": experiment.status,
        "verdict": experiment.verdict,
        "created_at": experiment.created_at,
        "completed_at": experiment.completed_at,
        "elapsed_seconds": _seconds_between(experiment.created_at, experiment.completed_at),
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "failed_runs": failed_runs,
        "pending_runs": pending_runs,
        "progress_percent": progress_percent,
    }


@router.post("/experiments/{experiment_id}/cancel")
def cancel_experiment(
    experiment_id: str,
    payload: schemas.CancelRequest,
    ctx: AuthContext = Depends(current_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    require_permission(ctx, "editor")
    experiment = require_experiment(db, experiment_id, ctx)
    if experiment.status in {"cancelling", "cancelled"}:
        return {"id": experiment.id, "status": experiment.status, "completed_runs": 0, "pending_runs": 0}
    if experiment.status in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="EXPERIMENT_NOT_CANCELLABLE")
    experiment.status = "cancelled"
    experiment.verdict = "CANCELLED"
    db.commit()
    return {"id": experiment.id, "status": "cancelled", "completed_runs": 0, "pending_runs": 0}


def _run_detail(db: Session, run_id: str) -> dict[str, Any] | None:
    run = db.get(models.Run, run_id)
    if run is None:
        return None
    tool_calls = db.scalars(select(models.ToolCall).where(models.ToolCall.run_id == run.id).order_by(models.ToolCall.sequence_number)).all()
    evaluations = db.scalars(select(models.Evaluation).where(models.Evaluation.run_id == run.id).order_by(models.Evaluation.created_at)).all()
    output = run.output or {}
    return {
        "id": run.id,
        "status": run.status,
        "output": {"content": output.get("content")},
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
        "total_tokens": run.total_tokens,
        "latency_ms": run.latency_ms,
        "estimated_cost_usd": None if run.estimated_cost_usd is None else float(run.estimated_cost_usd),
        "error_message": run.error_message,
        "tool_calls": [
            {
                "sequence_number": call.sequence_number,
                "name": call.tool_name,
                "arguments": call.arguments,
                "result": call.result,
            }
            for call in tool_calls
        ],
        "evaluations": [
            {
                "evaluator_name": evaluation.evaluator_name,
                "category": evaluation.category,
                "score": None if evaluation.score is None else float(evaluation.score),
                "weight": None if evaluation.weight is None else float(evaluation.weight),
                "include_in_quality_score": evaluation.include_in_quality_score,
                "passed": evaluation.passed,
                "state": evaluation.state,
                "hard_gate": evaluation.hard_gate,
                "details": evaluation.details,
            }
            for evaluation in evaluations
        ],
    }


def _comparison_item(db: Session, row: models.Comparison) -> dict[str, Any]:
    baseline_run = require(db.get(models.Run, row.baseline_run_id), "baseline run")
    return {
        "id": row.id,
        "baseline_run_id": row.baseline_run_id,
        "candidate_run_id": row.candidate_run_id,
        "dataset_case_id": baseline_run.dataset_case_id,
        "repetition": baseline_run.repetition,
        "input": baseline_run.input,
        "baseline": _run_detail(db, row.baseline_run_id),
        "candidate": _run_detail(db, row.candidate_run_id),
        "output_diff": row.output_diff,
        "tool_diff": row.tool_diff,
        "token_delta": row.token_delta,
        "latency_delta_ms": row.latency_delta_ms,
        "cost_delta_usd": None if row.cost_delta_usd is None else float(row.cost_delta_usd),
        "regression_status": row.regression_status,
    }


@router.get("/experiments/{experiment_id}/comparison")
def comparison(experiment_id: str, ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    experiment = require_experiment(db, experiment_id, ctx)
    rows = list(db.scalars(select(models.Comparison).where(models.Comparison.experiment_id == experiment_id)))
    return {
        "experiment": {"id": experiment.id, "status": experiment.status, "verdict": experiment.verdict},
        "items": [_comparison_item(db, row) for row in rows],
    }


@router.get("/experiments/{experiment_id}/export")
def export_experiment(experiment_id: str, format: str = "json", ctx: AuthContext = Depends(current_context), db: Session = Depends(get_db)) -> Response:
    data = comparison(experiment_id, ctx, db)
    if format == "json":
        return Response(json.dumps(data, default=str, indent=2), media_type="application/json")
    if format == "markdown":
        verdict = data["experiment"]["verdict"]
        body = ["# PromptDiff Report", "", f"Result: {verdict}", "", "| Case | Tool Changed | Token Delta | Latency Delta |", "|---|---:|---:|---:|"]
        for item in data["items"]:
            body.append(f"| {item['id']} | {item['tool_diff']['changed']} | {item['token_delta']} | {item['latency_delta_ms']} |")
        return Response("\n".join(body), media_type="text/markdown")
    if format == "csv":
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=["id", "token_delta", "latency_delta_ms", "regression_status"])
        writer.writeheader()
        for item in data["items"]:
            writer.writerow({k: item[k] for k in writer.fieldnames})
        return Response(out.getvalue(), media_type="text/csv")
    if format == "junit":
        failures = 1 if data["experiment"]["verdict"] == "FAIL" else 0
        xml = f'<testsuite name="promptdiff" tests="1" failures="{failures}"><testcase name="{experiment_id}" /></testsuite>'
        return Response(xml, media_type="application/xml")
    raise HTTPException(status_code=400, detail="unsupported export format")
