import base64
import os
from collections.abc import Generator

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import anyio
import pytest
from app import models
from app.auth import mint_promptdiff_jwt
from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import Base
from app.provider_secrets import decrypt_secret
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_db() -> Generator[Session, None, None]:
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def use_test_db_override():
    app.dependency_overrides[get_db] = override_db
    yield
    app.dependency_overrides.pop(get_db, None)


def configure_hosted(monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    monkeypatch.setenv("PROMPTDIFF_MODE", "hosted")
    monkeypatch.setenv("PROMPTDIFF_JWT_ISSUER", "https://app.test")
    monkeypatch.setenv("PROMPTDIFF_JWT_AUDIENCE", "promptdiff-api")
    monkeypatch.setenv("PROMPTDIFF_JWT_KEY_ID", "test-key")
    monkeypatch.setenv("PROMPTDIFF_JWT_PRIVATE_KEY", private_pem)
    monkeypatch.setenv("PROMPTDIFF_JWT_PUBLIC_KEY", public_pem)
    monkeypatch.setenv("PROMPTDIFF_SECRET_ENCRYPTION_KEY", base64.b64encode(os.urandom(32)).decode())
    get_settings.cache_clear()


def test_hosted_rejects_missing_auth(monkeypatch):
    configure_hosted(monkeypatch)

    response = client.get("/api/v1/projects")

    assert response.status_code == 401
    get_settings.cache_clear()


def test_hosted_project_uses_token_workspace(monkeypatch):
    configure_hosted(monkeypatch)
    with TestingSession() as db:
        db.add(models.User(id="user-1", auth_provider="neon", auth_subject="neon-user-1", email="u@example.com"))
        db.add(models.Workspace(id="workspace-1", name="Hosted Workspace"))
        db.add(models.WorkspaceMember(user_id="user-1", workspace_id="workspace-1", role="owner"))
        db.commit()
    token = mint_promptdiff_jwt("user-1", "workspace-1", "owner")

    response = client.post("/api/v1/projects", headers={"Authorization": f"Bearer {token}"}, json={"name": "Hosted Demo"})

    assert response.status_code == 200
    with TestingSession() as db:
        project = db.get(models.Project, response.json()["id"])
        assert project.user_id == "user-1"
        assert project.workspace_id == "workspace-1"
    get_settings.cache_clear()


def test_hosted_hides_other_workspace_projects(monkeypatch):
    configure_hosted(monkeypatch)
    with TestingSession() as db:
        db.add(models.User(id="user-2", auth_provider="neon", auth_subject="neon-user-2", email="u2@example.com"))
        db.add(models.Workspace(id="workspace-2", name="Visible Workspace"))
        db.add(models.Workspace(id="workspace-3", name="Hidden Workspace"))
        db.add(models.WorkspaceMember(user_id="user-2", workspace_id="workspace-2", role="owner"))
        db.add(models.Project(id="project-visible", user_id="user-2", workspace_id="workspace-2", name="Visible", slug="visible"))
        db.add(models.Project(id="project-hidden", user_id="other-user", workspace_id="workspace-3", name="Hidden", slug="hidden"))
        db.commit()
    token = mint_promptdiff_jwt("user-2", "workspace-2", "owner")

    response = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert [project["id"] for project in response.json()] == ["project-visible"]
    get_settings.cache_clear()


def test_hosted_provider_secret_is_encrypted_and_never_returned(monkeypatch):
    configure_hosted(monkeypatch)
    with TestingSession() as db:
        db.add(models.User(id="user-3", auth_provider="neon", auth_subject="neon-user-3", email="u3@example.com"))
        db.add(models.Workspace(id="workspace-4", name="Secret Workspace"))
        db.add(models.WorkspaceMember(user_id="user-3", workspace_id="workspace-4", role="owner"))
        db.commit()
    token = mint_promptdiff_jwt("user-3", "workspace-4", "owner")

    response = client.post(
        "/api/v1/workspaces/workspace-4/provider-secrets",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "groq", "api_key": "gsk_secret12345678901234567890"},
    )

    assert response.status_code == 200
    assert response.json()["key_hint"] == "...67890"
    assert "gsk_secret" not in response.text
    with TestingSession() as db:
        row = db.query(models.ProviderSecret).filter_by(workspace_id="workspace-4", provider="groq").one()
        assert row.ciphertext != b"gsk_secret12345678901234567890"
        assert decrypt_secret("workspace-4", "groq", row.ciphertext, row.nonce) == "gsk_secret12345678901234567890"

    audit_response = client.get(
        "/api/v1/workspaces/workspace-4/audit-events",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert audit_response.status_code == 200
    assert audit_response.json()["items"][0]["action"] == "provider_secret.upsert"
    get_settings.cache_clear()


def test_hosted_provider_secret_requires_owner(monkeypatch):
    configure_hosted(monkeypatch)
    with TestingSession() as db:
        db.add(models.User(id="user-4", auth_provider="neon", auth_subject="neon-user-4", email="u4@example.com"))
        db.add(models.Workspace(id="workspace-5", name="Viewer Workspace"))
        db.add(models.WorkspaceMember(user_id="user-4", workspace_id="workspace-5", role="viewer"))
        db.commit()
    token = mint_promptdiff_jwt("user-4", "workspace-5", "viewer")

    response = client.post(
        "/api/v1/workspaces/workspace-5/provider-secrets",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "groq", "api_key": "gsk_secret12345678901234567890"},
    )

    assert response.status_code == 403
    get_settings.cache_clear()


def test_provider_secret_validation_does_not_echo_secret(monkeypatch):
    configure_hosted(monkeypatch)
    with TestingSession() as db:
        db.add(models.User(id="user-secret-validation", auth_provider="neon", auth_subject="neon-secret-validation"))
        db.add(models.Workspace(id="workspace-secret-validation", name="Secret Validation Workspace"))
        db.add(models.WorkspaceMember(user_id="user-secret-validation", workspace_id="workspace-secret-validation", role="owner"))
        db.commit()
    token = mint_promptdiff_jwt("user-secret-validation", "workspace-secret-validation", "owner")
    secret = "gsk_" + ("x" * 2_500)

    response = client.post(
        "/api/v1/workspaces/workspace-secret-validation/provider-secrets",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "groq", "api_key": secret},
    )

    assert response.status_code == 422
    assert secret not in response.text
    assert "gsk_" not in response.text
    get_settings.cache_clear()


def test_neon_exchange_provisions_user_workspace_and_token(monkeypatch):
    configure_hosted(monkeypatch)
    monkeypatch.setattr(
        "app.routes.validate_neon_jwt",
        lambda token: {"sub": "neon-user-6", "email": "six@example.com", "name": "Six"},
    )

    response = client.post("/api/v1/auth/neon/exchange", headers={"Authorization": "Bearer neon-session"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "six@example.com"
    assert body["workspace"]["role"] == "owner"
    with TestingSession() as db:
        user = db.query(models.User).filter_by(auth_subject="neon-user-6").one()
        member = db.query(models.WorkspaceMember).filter_by(user_id=user.id).one()
        assert member.role == "owner"
    get_settings.cache_clear()


def test_hosted_experiment_reports_queue_failure(monkeypatch):
    configure_hosted(monkeypatch)
    with TestingSession() as db:
        db.add(models.User(id="user-5", auth_provider="neon", auth_subject="neon-user-5", email="u5@example.com"))
        db.add(models.Workspace(id="workspace-6", name="Queue Workspace"))
        db.add(models.WorkspaceMember(user_id="user-5", workspace_id="workspace-6", role="owner"))
        db.commit()
    token = mint_promptdiff_jwt("user-5", "workspace-6", "owner")
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Queue Failure"}).json()
    prompt_a = client.post("/api/v1/prompts", headers=headers, json={"project_id": project["id"], "name": "baseline"}).json()
    prompt_b = client.post("/api/v1/prompts", headers=headers, json={"project_id": project["id"], "name": "candidate"}).json()
    version_a = client.post(
        f"/api/v1/prompts/{prompt_a['id']}/versions",
        headers=headers,
        json={"system_prompt": "A", "user_template": "{{message}}"},
    ).json()
    version_b = client.post(
        f"/api/v1/prompts/{prompt_b['id']}/versions",
        headers=headers,
        json={"system_prompt": "B", "user_template": "{{message}}"},
    ).json()
    dataset = client.post("/api/v1/datasets", headers=headers, json={"project_id": project["id"], "name": "cases"}).json()
    client.post(f"/api/v1/datasets/{dataset['id']}/cases", headers=headers, json={"input": {"message": "hello"}})

    class BrokenQueue:
        async def enqueue_experiment(self, experiment_id, workspace_id):
            raise RuntimeError("redis unavailable")

    monkeypatch.setattr("app.routes.hosted_queue", lambda: BrokenQueue())

    response = client.post(
        "/api/v1/experiments",
        headers=headers,
        json={
            "project_id": project["id"],
            "name": "queue-failure",
            "baseline_prompt_version_id": version_a["id"],
            "candidate_prompt_version_id": version_b["id"],
            "dataset_id": dataset["id"],
            "provider": "groq",
            "model": "llama-3.1-8b-instant",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "QUEUE_UNAVAILABLE"
    get_settings.cache_clear()


def test_hosted_worker_uses_saved_experiment_config(monkeypatch):
    configure_hosted(monkeypatch)
    captured = {}

    class CapturingQueue:
        async def enqueue_experiment(self, experiment_id, workspace_id):
            captured["job"] = {"experiment_id": experiment_id, "workspace_id": workspace_id}

    monkeypatch.setattr("app.routes.hosted_queue", lambda: CapturingQueue())
    with TestingSession() as db:
        db.add(models.User(id="user-worker", auth_provider="neon", auth_subject="neon-worker", email="worker@example.com"))
        db.add(models.Workspace(id="workspace-worker", name="Worker Workspace"))
        db.add(models.WorkspaceMember(user_id="user-worker", workspace_id="workspace-worker", role="owner"))
        db.commit()
    token = mint_promptdiff_jwt("user-worker", "workspace-worker", "owner")
    headers = {"Authorization": f"Bearer {token}"}
    project = client.post("/api/v1/projects", headers=headers, json={"name": "Worker Demo"}).json()
    prompt_a = client.post("/api/v1/prompts", headers=headers, json={"project_id": project["id"], "name": "baseline"}).json()
    prompt_b = client.post("/api/v1/prompts", headers=headers, json={"project_id": project["id"], "name": "candidate"}).json()
    version_a = client.post(
        f"/api/v1/prompts/{prompt_a['id']}/versions",
        headers=headers,
        json={"system_prompt": "Escalate enterprise refunds.", "user_template": "{{message}}"},
    ).json()
    version_b = client.post(
        f"/api/v1/prompts/{prompt_b['id']}/versions",
        headers=headers,
        json={"system_prompt": "Refund monthly plans; escalate enterprise.", "user_template": "{{message}}"},
    ).json()
    dataset = client.post("/api/v1/datasets", headers=headers, json={"project_id": project["id"], "name": "cases"}).json()
    client.post(
        f"/api/v1/datasets/{dataset['id']}/cases",
        headers=headers,
        json={"input": {"message": "Refund my annual enterprise plan"}},
    )
    experiment = client.post(
        "/api/v1/experiments",
        headers=headers,
        json={
            "project_id": project["id"],
            "name": "worker-run",
            "baseline_prompt_version_id": version_a["id"],
            "candidate_prompt_version_id": version_b["id"],
            "dataset_id": dataset["id"],
            "provider": "mock",
            "model": "saved-model",
            "repetitions": 2,
            "timeout_seconds": 42,
        },
    ).json()

    async def fake_pop_job():
        return captured["job"]

    monkeypatch.setattr("app.worker.pop_job", fake_pop_job)
    monkeypatch.setattr("app.worker.SessionLocal", TestingSession)

    from app.worker import run_once

    assert anyio.run(run_once) is True
    with TestingSession() as db:
        refreshed = db.get(models.Experiment, experiment["id"])
        variants = db.query(models.ExperimentVariant).filter_by(experiment_id=experiment["id"]).all()
        runs = db.query(models.Run).filter_by(experiment_id=experiment["id"]).all()
        assert refreshed.status == "completed"
        assert {variant.model for variant in variants} == {"saved-model"}
        assert {variant.config["timeout_seconds"] for variant in variants} == {42}
        assert len(runs) == 4
    assert anyio.run(run_once) is True
    with TestingSession() as db:
        assert db.query(models.Run).filter_by(experiment_id=experiment["id"]).count() == 4
    get_settings.cache_clear()


def test_hosted_worker_skips_cancelled_experiment(monkeypatch):
    configure_hosted(monkeypatch)
    with TestingSession() as db:
        project = models.Project(id="cancel-project", user_id="user-worker-cancel", workspace_id="workspace-worker-cancel", name="Cancel", slug="cancel")
        db.add(project)
        prompt = models.Prompt(id="cancel-prompt", project_id=project.id, name="prompt")
        dataset = models.Dataset(id="cancel-dataset", project_id=project.id, name="dataset")
        db.add_all([prompt, dataset])
        version_a = models.PromptVersion(id="cancel-version-a", prompt_id=prompt.id, version_number=1, content_hash="a")
        version_b = models.PromptVersion(id="cancel-version-b", prompt_id=prompt.id, version_number=2, content_hash="b")
        db.add_all([version_a, version_b])
        experiment = models.Experiment(
            id="cancel-experiment",
            project_id=project.id,
            name="cancelled",
            baseline_prompt_version_id=version_a.id,
            candidate_prompt_version_id=version_b.id,
            dataset_id=dataset.id,
            status="cancelled",
        )
        db.add(experiment)
        db.commit()

    async def fake_pop_job():
        return {"experiment_id": "cancel-experiment", "workspace_id": "workspace-worker-cancel"}

    monkeypatch.setattr("app.worker.pop_job", fake_pop_job)
    monkeypatch.setattr("app.worker.SessionLocal", TestingSession)

    from app.worker import run_once

    assert anyio.run(run_once) is True
    with TestingSession() as db:
        assert db.query(models.Run).filter_by(experiment_id="cancel-experiment").count() == 0
    get_settings.cache_clear()
