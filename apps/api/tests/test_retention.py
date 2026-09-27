from datetime import datetime, timedelta, timezone

from app import models
from app.models import Base
from app.retention import cleanup_retention
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def add_run(db, workspace_id: str, run_id: str, created_at: datetime, output: dict):
    project = models.Project(id=f"project-{run_id}", workspace_id=workspace_id, user_id="user-1", name=run_id, slug=run_id)
    prompt = models.Prompt(id=f"prompt-{run_id}", project_id=project.id, name=run_id)
    dataset = models.Dataset(id=f"dataset-{run_id}", project_id=project.id, name=run_id)
    version = models.PromptVersion(id=f"version-{run_id}", prompt_id=prompt.id, version_number=1, content_hash=run_id)
    experiment = models.Experiment(
        id=f"experiment-{run_id}",
        project_id=project.id,
        name=run_id,
        baseline_prompt_version_id=version.id,
        candidate_prompt_version_id=version.id,
        dataset_id=dataset.id,
        status="completed",
    )
    variant = models.ExperimentVariant(experiment_id=experiment.id, name="baseline", provider="mock", model="mock")
    db.add_all([project, prompt, dataset, version, experiment, variant])
    db.flush()
    db.add(
        models.Run(
            id=run_id,
            experiment_id=experiment.id,
            variant_id=variant.id,
            dataset_case_id="case-1",
            prompt_version_id=version.id,
            status="completed",
            output=output,
            created_at=created_at,
        )
    )


def test_cleanup_retention_scrubs_expired_raw_provider_response():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    with TestingSession() as db:
        db.add(models.Workspace(id="workspace-retention-raw", name="Retention"))
        db.add(models.RetentionSetting(workspace_id="workspace-retention-raw", raw_provider_response_days=7))
        add_run(
            db,
            "workspace-retention-raw",
            "old-raw",
            now - timedelta(days=8),
            {"content": "keep me", "raw_response": {"id": "provider-response"}},
        )
        db.commit()

        cleanup_retention(db, now=now)

        assert db.get(models.Run, "old-raw").output == {"content": "keep me"}


def test_cleanup_retention_scrubs_expired_model_output_content():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    with TestingSession() as db:
        db.add(models.Workspace(id="workspace-retention-content", name="Retention"))
        db.add(models.RetentionSetting(workspace_id="workspace-retention-content", raw_model_output_days=30, raw_provider_response_days=7))
        add_run(
            db,
            "workspace-retention-content",
            "old-content",
            now - timedelta(days=31),
            {"content": "remove me", "raw_response": {"id": "provider-response"}},
        )
        db.commit()

        cleanup_retention(db, now=now)

        assert db.get(models.Run, "old-content").output == {}


def test_cleanup_retention_keeps_non_expired_and_uses_defaults():
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    output = {"content": "keep me", "raw_response": {"id": "provider-response"}}
    with TestingSession() as db:
        db.add(models.Workspace(id="workspace-retention-defaults", name="Retention"))
        add_run(db, "workspace-retention-defaults", "fresh-run", now - timedelta(days=1), output)
        db.commit()

        cleanup_retention(db, now=now)

        assert db.get(models.Run, "fresh-run").output == output
