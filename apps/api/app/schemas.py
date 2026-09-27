import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2_000
MAX_PROMPT_LENGTH = 100_000
MAX_JSON_BYTES = 100_000
MAX_DATASET_IMPORT_BYTES = 1_000_000


def _check_json_size(value: Any) -> Any:
    if value is not None and len(json.dumps(value, default=str).encode()) > MAX_JSON_BYTES:
        raise ValueError(f"JSON fields must be {MAX_JSON_BYTES} bytes or smaller")
    return value


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    slug: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)


class WorkspaceOut(ORMModel):
    id: str
    name: str
    role: str | None = None
    created_at: datetime


class CurrentUserOut(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None
    active_workspace: dict[str, Any]


class ProviderSecretCreate(BaseModel):
    provider: Literal["groq"]
    api_key: str = Field(min_length=1, max_length=2_000)


class ProviderSecretOut(BaseModel):
    provider: str
    configured: bool
    key_hint: str
    created_at: datetime


class RetentionOut(BaseModel):
    experiment_metadata_days: int = 90
    raw_model_output_days: int = 30
    raw_provider_response_days: int = 7
    application_log_days: int = 14
    audit_log_days: int = 90


class RegressionConfigOut(ORMModel):
    id: str
    project_id: str
    name: str
    version: int
    schema_version: int
    config: dict[str, Any]
    created_at: datetime


class ProjectOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class PromptCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)


class PromptOut(ORMModel):
    id: str
    project_id: str
    name: str
    description: str | None
    created_at: datetime


class PromptVersionCreate(BaseModel):
    system_prompt: str | None = Field(default="", max_length=MAX_PROMPT_LENGTH)
    user_template: str | None = Field(default="", max_length=MAX_PROMPT_LENGTH)
    tool_definitions: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1

    @field_validator("tool_definitions", "metadata")
    @classmethod
    def json_fields_are_bounded(cls, value: Any) -> Any:
        return _check_json_size(value)


class PromptVersionOut(ORMModel):
    id: str
    prompt_id: str
    version_number: int
    system_prompt: str | None
    user_template: str | None
    tool_definitions: list[dict[str, Any]] | None
    metadata_json: dict[str, Any] | None
    schema_version: int
    content_hash: str
    created_at: datetime


class DatasetCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION_LENGTH)


class DatasetOut(ORMModel):
    id: str
    project_id: str
    name: str
    description: str | None
    created_at: datetime


class DatasetCaseCreate(BaseModel):
    name: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    input: dict[str, Any]
    expected_output: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input", "expected_output", "metadata")
    @classmethod
    def json_fields_are_bounded(cls, value: Any) -> Any:
        return _check_json_size(value)


class DatasetImport(BaseModel):
    project_id: str
    content: str = Field(max_length=MAX_DATASET_IMPORT_BYTES)
    format: Literal["yaml", "json"] = "yaml"


class DatasetCaseOut(ORMModel):
    id: str
    dataset_id: str
    name: str | None
    input: dict[str, Any]
    expected_output: dict[str, Any] | None
    metadata_json: dict[str, Any] | None
    created_at: datetime


class EvaluatorConfig(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    type: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    category: str = Field(default="quality", max_length=MAX_NAME_LENGTH)
    weight: float = 1.0
    include_in_quality_score: bool = False
    required: bool = False
    threshold: float | None = None
    hard_gate: bool = False


class ExperimentCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    baseline_prompt_version_id: str
    candidate_prompt_version_id: str
    dataset_id: str
    provider: Literal["mock", "groq"] = "mock"
    model: str = "mock-support"
    temperature: float | None = None
    max_tokens: int | None = None
    repetitions: int = Field(default=1, ge=1, le=5)
    concurrency: int = Field(default=5, ge=1, le=50)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    evaluators: list[EvaluatorConfig] = Field(default_factory=list)
    regression: dict[str, Any] = Field(default_factory=dict)

    @field_validator("regression")
    @classmethod
    def json_fields_are_bounded(cls, value: Any) -> Any:
        return _check_json_size(value)


class ExperimentOut(ORMModel):
    id: str
    project_id: str
    name: str
    status: str
    verdict: str | None
    dataset_snapshot_id: str | None
    created_at: datetime
    completed_at: datetime | None


class CancelRequest(BaseModel):
    reason: str = Field(default="user_cancelled", max_length=MAX_DESCRIPTION_LENGTH)
