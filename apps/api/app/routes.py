import csv
import io
import json
from typing import Any

import yaml
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models, schemas
from app.db import get_db
from app.services import create_prompt_version, run_experiment, slugify

router = APIRouter(prefix="/api/v1")


def require(row: Any, name: str = "resource") -> Any:
    if row is None:
        raise HTTPException(status_code=404, detail=f"{name} not found")
    return row


@router.post("/projects", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: Session = Depends(get_db)) -> models.Project:
    project = models.Project(name=payload.name, slug=payload.slug or slugify(payload.name), description=payload.description)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/projects", response_model=list[schemas.ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[models.Project]:
    return list(db.scalars(select(models.Project).order_by(models.Project.created_at.desc())))


@router.get("/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> models.Project:
    return require(db.get(models.Project, project_id), "project")


@router.post("/prompts", response_model=schemas.PromptOut)
def create_prompt(payload: schemas.PromptCreate, db: Session = Depends(get_db)) -> models.Prompt:
    require(db.get(models.Project, payload.project_id), "project")
    prompt = models.Prompt(project_id=payload.project_id, name=payload.name, description=payload.description)
    db.add(prompt)
    db.commit()
    db.refresh(prompt)
    return prompt


@router.get("/prompts", response_model=list[schemas.PromptOut])
def list_prompts(project_id: str | None = None, db: Session = Depends(get_db)) -> list[models.Prompt]:
    stmt = select(models.Prompt).order_by(models.Prompt.created_at.desc())
    if project_id:
        stmt = stmt.where(models.Prompt.project_id == project_id)
    return list(db.scalars(stmt))


@router.get("/prompts/{prompt_id}", response_model=schemas.PromptOut)
def get_prompt(prompt_id: str, db: Session = Depends(get_db)) -> models.Prompt:
    return require(db.get(models.Prompt, prompt_id), "prompt")


@router.post("/prompts/{prompt_id}/versions", response_model=schemas.PromptVersionOut)
def create_version(prompt_id: str, payload: schemas.PromptVersionCreate, db: Session = Depends(get_db)) -> models.PromptVersion:
    require(db.get(models.Prompt, prompt_id), "prompt")
    return create_prompt_version(db, prompt_id, payload)


@router.get("/prompts/{prompt_id}/versions", response_model=list[schemas.PromptVersionOut])
def list_versions(prompt_id: str, db: Session = Depends(get_db)) -> list[models.PromptVersion]:
    return list(db.scalars(select(models.PromptVersion).where(models.PromptVersion.prompt_id == prompt_id).order_by(models.PromptVersion.version_number)))


@router.get("/prompt-versions/{version_id}", response_model=schemas.PromptVersionOut)
def get_version(version_id: str, db: Session = Depends(get_db)) -> models.PromptVersion:
    return require(db.get(models.PromptVersion, version_id), "prompt version")


@router.post("/datasets", response_model=schemas.DatasetOut)
def create_dataset(payload: schemas.DatasetCreate, db: Session = Depends(get_db)) -> models.Dataset:
    require(db.get(models.Project, payload.project_id), "project")
    dataset = models.Dataset(project_id=payload.project_id, name=payload.name, description=payload.description)
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("/datasets", response_model=list[schemas.DatasetOut])
def list_datasets(project_id: str | None = None, db: Session = Depends(get_db)) -> list[models.Dataset]:
    stmt = select(models.Dataset).order_by(models.Dataset.created_at.desc())
    if project_id:
        stmt = stmt.where(models.Dataset.project_id == project_id)
    return list(db.scalars(stmt))


@router.post("/datasets/import", response_model=schemas.DatasetOut)
def import_dataset(payload: schemas.DatasetImport, db: Session = Depends(get_db)) -> models.Dataset:
    parsed = yaml.safe_load(payload.content) if payload.format == "yaml" else json.loads(payload.content)
    dataset = models.Dataset(project_id=payload.project_id, name=parsed["name"], description=parsed.get("description"))
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    for case in parsed.get("cases", []):
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
def add_case(dataset_id: str, payload: schemas.DatasetCaseCreate, db: Session = Depends(get_db)) -> models.DatasetCase:
    require(db.get(models.Dataset, dataset_id), "dataset")
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
def list_cases(dataset_id: str, db: Session = Depends(get_db)) -> list[models.DatasetCase]:
    return list(db.scalars(select(models.DatasetCase).where(models.DatasetCase.dataset_id == dataset_id).order_by(models.DatasetCase.created_at)))


@router.post("/projects/{project_id}/regression-configs")
def create_regression_config(project_id: str, payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    require(db.get(models.Project, project_id), "project")
    name = payload.get("name", "default")
    version = 1
    row = models.RegressionConfig(project_id=project_id, name=name, version=version, schema_version=payload.get("config", {}).get("schema_version", 1), config=payload.get("config", {}), created_by="local-user")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "name": row.name, "version": row.version, "config": row.config}


@router.post("/experiments", response_model=schemas.ExperimentOut)
async def create_experiment(payload: schemas.ExperimentCreate, db: Session = Depends(get_db)) -> models.Experiment:
    require(db.get(models.Project, payload.project_id), "project")
    require(db.get(models.PromptVersion, payload.baseline_prompt_version_id), "baseline prompt version")
    require(db.get(models.PromptVersion, payload.candidate_prompt_version_id), "candidate prompt version")
    require(db.get(models.Dataset, payload.dataset_id), "dataset")
    config = models.RegressionConfig(
        project_id=payload.project_id,
        name=f"{payload.name}-config",
        version=1,
        schema_version=1,
        config={"evaluators": [item.model_dump() for item in payload.evaluators], "regression": payload.regression},
        created_by="local-user",
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
    return await run_experiment(db, experiment, payload)


@router.get("/experiments", response_model=list[schemas.ExperimentOut])
def list_experiments(project_id: str | None = None, db: Session = Depends(get_db)) -> list[models.Experiment]:
    stmt = select(models.Experiment).order_by(models.Experiment.created_at.desc())
    if project_id:
        stmt = stmt.where(models.Experiment.project_id == project_id)
    return list(db.scalars(stmt))


@router.get("/experiments/{experiment_id}", response_model=schemas.ExperimentOut)
def get_experiment(experiment_id: str, db: Session = Depends(get_db)) -> models.Experiment:
    return require(db.get(models.Experiment, experiment_id), "experiment")


@router.post("/experiments/{experiment_id}/cancel")
def cancel_experiment(experiment_id: str, payload: schemas.CancelRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    experiment = require(db.get(models.Experiment, experiment_id), "experiment")
    if experiment.status in {"cancelling", "cancelled"}:
        return {"id": experiment.id, "status": experiment.status, "completed_runs": 0, "pending_runs": 0}
    if experiment.status in {"completed", "failed"}:
        raise HTTPException(status_code=409, detail="EXPERIMENT_NOT_CANCELLABLE")
    experiment.status = "cancelled"
    experiment.verdict = "CANCELLED"
    db.commit()
    return {"id": experiment.id, "status": "cancelled", "completed_runs": 0, "pending_runs": 0}


@router.get("/experiments/{experiment_id}/comparison")
def comparison(experiment_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    experiment = require(db.get(models.Experiment, experiment_id), "experiment")
    rows = list(db.scalars(select(models.Comparison).where(models.Comparison.experiment_id == experiment_id)))
    return {
        "experiment": {"id": experiment.id, "status": experiment.status, "verdict": experiment.verdict},
        "items": [
            {
                "id": row.id,
                "baseline_run_id": row.baseline_run_id,
                "candidate_run_id": row.candidate_run_id,
                "output_diff": row.output_diff,
                "tool_diff": row.tool_diff,
                "token_delta": row.token_delta,
                "latency_delta_ms": row.latency_delta_ms,
                "cost_delta_usd": None if row.cost_delta_usd is None else float(row.cost_delta_usd),
                "regression_status": row.regression_status,
            }
            for row in rows
        ],
    }


@router.get("/experiments/{experiment_id}/export")
def export_experiment(experiment_id: str, format: str = "json", db: Session = Depends(get_db)) -> Response:
    data = comparison(experiment_id, db)
    if format == "json":
        return Response(json.dumps(data, default=str, indent=2), media_type="application/json")
    if format == "markdown":
        verdict = data["experiment"]["verdict"]
        body = [f"# PromptDiff Report", "", f"Result: {verdict}", "", "| Case | Tool Changed | Token Delta | Latency Delta |", "|---|---:|---:|---:|"]
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

