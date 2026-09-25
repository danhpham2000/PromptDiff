from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str | None = None


class ProjectOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class PromptCreate(BaseModel):
    project_id: str
    name: str
    description: str | None = None


class PromptOut(ORMModel):
    id: str
    project_id: str
    name: str
    description: str | None
    created_at: datetime


class PromptVersionCreate(BaseModel):
    system_prompt: str | None = ""
    user_template: str | None = ""
    tool_definitions: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1


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
    name: str
    description: str | None = None


class DatasetOut(ORMModel):
    id: str
    project_id: str
    name: str
    description: str | None
    created_at: datetime


class DatasetCaseCreate(BaseModel):
    name: str | None = None
    input: dict[str, Any]
    expected_output: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DatasetImport(BaseModel):
    project_id: str
    content: str
    format: str = "yaml"


class DatasetCaseOut(ORMModel):
    id: str
    dataset_id: str
    name: str | None
    input: dict[str, Any]
    expected_output: dict[str, Any] | None
    metadata_json: dict[str, Any] | None
    created_at: datetime


class EvaluatorConfig(BaseModel):
    name: str
    type: str
    category: str = "quality"
    weight: float = 1.0
    include_in_quality_score: bool = False
    required: bool = False
    threshold: float | None = None
    hard_gate: bool = False


class ExperimentCreate(BaseModel):
    project_id: str
    name: str
    baseline_prompt_version_id: str
    candidate_prompt_version_id: str
    dataset_id: str
    provider: str = "mock"
    model: str = "mock-support"
    temperature: float | None = None
    max_tokens: int | None = None
    repetitions: int = Field(default=1, ge=1, le=5)
    concurrency: int = Field(default=5, ge=1, le=50)
    timeout_seconds: int = Field(default=60, ge=5, le=300)
    evaluators: list[EvaluatorConfig] = Field(default_factory=list)
    regression: dict[str, Any] = Field(default_factory=dict)


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
    reason: str = "user_cancelled"

