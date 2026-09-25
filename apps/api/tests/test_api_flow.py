import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import models
from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import Base
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_db() -> Generator[Session, None, None]:
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def test_local_experiment_flow():
    project = client.post("/api/v1/projects", json={"name": "Demo"}).json()
    prompt_a = client.post("/api/v1/prompts", json={"project_id": project["id"], "name": "baseline"}).json()
    prompt_b = client.post("/api/v1/prompts", json={"project_id": project["id"], "name": "candidate"}).json()
    version_a = client.post(
        f"/api/v1/prompts/{prompt_a['id']}/versions",
        json={"system_prompt": "Escalate enterprise refunds.", "user_template": "{{message}}"},
    ).json()
    version_b = client.post(
        f"/api/v1/prompts/{prompt_b['id']}/versions",
        json={"system_prompt": "Refund monthly plans; escalate enterprise.", "user_template": "{{message}}"},
    ).json()
    dataset = client.post("/api/v1/datasets", json={"project_id": project["id"], "name": "refunds"}).json()
    client.post(
        f"/api/v1/datasets/{dataset['id']}/cases",
        json={
            "name": "enterprise",
            "input": {"message": "Refund my annual enterprise plan"},
            "expected_output": {"tool": {"name": "escalate_to_human"}},
        },
    )
    client.post(
        f"/api/v1/datasets/{dataset['id']}/cases",
        json={
            "name": "monthly",
            "input": {"message": "Refund my monthly subscription"},
            "expected_output": {"tool": {"name": "refund_customer"}},
        },
    )

    experiment = client.post(
        "/api/v1/experiments",
        json={
            "project_id": project["id"],
            "name": "demo",
            "baseline_prompt_version_id": version_a["id"],
            "candidate_prompt_version_id": version_b["id"],
            "dataset_id": dataset["id"],
            "provider": "mock",
            "model": "mock-support",
            "evaluators": [{"name": "tool-selection", "type": "tool_selection", "category": "tool", "hard_gate": True}],
            "regression": {},
        },
    ).json()

    assert experiment["status"] == "completed"
    assert experiment["verdict"] == "PASS"
    assert experiment["dataset_snapshot_id"]

    comparison = client.get(f"/api/v1/experiments/{experiment['id']}/comparison").json()
    assert len(comparison["items"]) == 2


def test_provider_failure_is_error_not_pass(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    get_settings.cache_clear()
    project = client.post("/api/v1/projects", json={"name": "Failure Demo"}).json()
    prompt_a = client.post("/api/v1/prompts", json={"project_id": project["id"], "name": "baseline"}).json()
    prompt_b = client.post("/api/v1/prompts", json={"project_id": project["id"], "name": "candidate"}).json()
    version_a = client.post(f"/api/v1/prompts/{prompt_a['id']}/versions", json={"system_prompt": "A", "user_template": "{{message}}"}).json()
    version_b = client.post(f"/api/v1/prompts/{prompt_b['id']}/versions", json={"system_prompt": "B", "user_template": "{{message}}"}).json()
    dataset = client.post("/api/v1/datasets", json={"project_id": project["id"], "name": "cases"}).json()
    client.post(f"/api/v1/datasets/{dataset['id']}/cases", json={"input": {"message": "hello"}})

    experiment = client.post(
        "/api/v1/experiments",
        json={
            "project_id": project["id"],
            "name": "provider-error",
            "baseline_prompt_version_id": version_a["id"],
            "candidate_prompt_version_id": version_b["id"],
            "dataset_id": dataset["id"],
            "provider": "groq",
            "model": "example-model",
            "evaluators": [],
            "regression": {},
        },
    ).json()

    assert experiment["status"] == "failed"
    assert experiment["verdict"] == "ERROR"
    get_settings.cache_clear()


def test_failed_run_errors_are_redacted(monkeypatch):
    class SecretFailProvider:
        async def generate(self, messages, tools, config):
            raise RuntimeError("provider failed with Bearer abc.def.ghi")

    monkeypatch.setattr("app.services.provider_for", lambda name: SecretFailProvider())

    project = client.post("/api/v1/projects", json={"name": "Secret Failure Demo"}).json()
    prompt_a = client.post("/api/v1/prompts", json={"project_id": project["id"], "name": "baseline"}).json()
    prompt_b = client.post("/api/v1/prompts", json={"project_id": project["id"], "name": "candidate"}).json()
    version_a = client.post(f"/api/v1/prompts/{prompt_a['id']}/versions", json={"system_prompt": "A", "user_template": "{{message}}"}).json()
    version_b = client.post(f"/api/v1/prompts/{prompt_b['id']}/versions", json={"system_prompt": "B", "user_template": "{{message}}"}).json()
    dataset = client.post("/api/v1/datasets", json={"project_id": project["id"], "name": "cases"}).json()
    client.post(f"/api/v1/datasets/{dataset['id']}/cases", json={"input": {"message": "hello"}})

    experiment = client.post(
        "/api/v1/experiments",
        json={
            "project_id": project["id"],
            "name": "provider-error-redacted",
            "baseline_prompt_version_id": version_a["id"],
            "candidate_prompt_version_id": version_b["id"],
            "dataset_id": dataset["id"],
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
        },
    ).json()

    with TestingSession() as db:
        run = db.scalars(select(models.Run).where(models.Run.experiment_id == experiment["id"])).first()

    assert run.error_message == "provider failed with [REDACTED]"


def test_rejects_oversized_project_name():
    response = client.post("/api/v1/projects", json={"name": "x" * 201})

    assert response.status_code == 422


def test_rejects_invalid_dataset_import():
    project = client.post("/api/v1/projects", json={"name": "Import Validation Demo"}).json()

    response = client.post("/api/v1/datasets/import", json={"project_id": project["id"], "content": "[", "format": "yaml"})

    assert response.status_code == 400


def test_rejects_oversized_dataset_import():
    project = client.post("/api/v1/projects", json={"name": "Large Import Demo"}).json()

    response = client.post("/api/v1/datasets/import", json={"project_id": project["id"], "content": "x" * 1_000_001, "format": "yaml"})

    assert response.status_code == 422
