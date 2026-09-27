import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String, default="local-user", nullable=False)
    workspace_id: Mapped[str] = mapped_column(String, default="local-workspace", nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    prompts = relationship("Prompt", cascade="all, delete-orphan")
    datasets = relationship("Dataset", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("auth_provider", "auth_subject"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    auth_provider: Mapped[str] = mapped_column(String, default="neon", nullable=False)
    auth_subject: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderSecret(Base):
    __tablename__ = "provider_secrets"
    __table_args__ = (UniqueConstraint("workspace_id", "provider"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    key_hint: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    actor_id: Mapped[str] = mapped_column(String, nullable=False)
    workspace_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetentionSetting(Base):
    __tablename__ = "retention_settings"

    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True)
    experiment_metadata_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    raw_model_output_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    raw_provider_response_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    application_log_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    audit_log_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)


class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versions = relationship("PromptVersion", cascade="all, delete-orphan", order_by="PromptVersion.version_number")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_id", "version_number"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text)
    user_template: Mapped[str | None] = mapped_column(Text)
    tool_definitions: Mapped[list | None] = mapped_column(JSON)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cases = relationship("DatasetCase", cascade="all, delete-orphan", order_by="DatasetCase.created_at")


class DatasetCase(Base):
    __tablename__ = "dataset_cases"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str | None] = mapped_column(String)
    input: Mapped[dict] = mapped_column(JSON, nullable=False)
    expected_output: Mapped[dict | None] = mapped_column(JSON)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DatasetSnapshot(Base):
    __tablename__ = "dataset_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RegressionConfig(Base):
    __tablename__ = "regression_configs"
    __table_args__ = (UniqueConstraint("project_id", "name", "version"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    baseline_prompt_version_id: Mapped[str] = mapped_column(ForeignKey("prompt_versions.id"), nullable=False)
    candidate_prompt_version_id: Mapped[str] = mapped_column(ForeignKey("prompt_versions.id"), nullable=False)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), nullable=False)
    dataset_snapshot_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_snapshots.id"))
    regression_config_id: Mapped[str | None] = mapped_column(ForeignKey("regression_configs.id"))
    regression_config_version: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, nullable=False, default="created")
    verdict: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExperimentVariant(Base):
    __tablename__ = "experiment_variants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    temperature: Mapped[float | None] = mapped_column(Numeric)
    max_tokens: Mapped[int | None] = mapped_column(Integer)
    config: Mapped[dict | None] = mapped_column(JSON)


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False)
    variant_id: Mapped[str] = mapped_column(ForeignKey("experiment_variants.id"), nullable=False)
    dataset_case_id: Mapped[str] = mapped_column(String, nullable=False)
    prompt_version_id: Mapped[str] = mapped_column(ForeignKey("prompt_versions.id"), nullable=False)
    repetition: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    input: Mapped[dict | None] = mapped_column(JSON)
    output: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    pricing_version: Mapped[str | None] = mapped_column(String)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_reasons: Mapped[list | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    seed_status: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolCall(Base):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(String, nullable=False)
    arguments: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Evaluation(Base):
    __tablename__ = "evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    evaluator_name: Mapped[str] = mapped_column(String, nullable=False)
    evaluator_version: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)
    score: Mapped[float | None] = mapped_column(Numeric)
    weight: Mapped[float | None] = mapped_column(Numeric)
    include_in_quality_score: Mapped[bool] = mapped_column(Boolean, default=False)
    passed: Mapped[bool | None] = mapped_column(Boolean)
    state: Mapped[str] = mapped_column(String, default="passed", nullable=False)
    hard_gate: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    baseline_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    candidate_run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), nullable=False)
    output_diff: Mapped[dict | None] = mapped_column(JSON)
    tool_diff: Mapped[dict | None] = mapped_column(JSON)
    token_delta: Mapped[int | None] = mapped_column(Integer)
    latency_delta_ms: Mapped[int | None] = mapped_column(Integer)
    cost_delta_usd: Mapped[float | None] = mapped_column(Numeric(12, 6))
    regression_status: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
