import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base


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


def test_provider_failure_is_error_not_pass():
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
            "provider": "openai",
            "model": "example-model",
            "evaluators": [],
            "regression": {},
        },
    ).json()

    assert experiment["status"] == "failed"
    assert experiment["verdict"] == "ERROR"
