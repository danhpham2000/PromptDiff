"""initial schema

Revision ID: 20260924_0001
Revises:
Create Date: 2026-09-24
"""

import sqlalchemy as sa
from alembic import op

revision = "20260924_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "prompts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("prompt_id", sa.String(), sa.ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sa.Text()),
        sa.Column("user_template", sa.Text()),
        sa.Column("tool_definitions", sa.JSON()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("prompt_id", "version_number"),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "dataset_cases",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dataset_id", sa.String(), sa.ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("expected_output", sa.JSON()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "dataset_snapshots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("dataset_id", sa.String(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "regression_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "name", "version"),
    )
    op.create_table(
        "experiments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("project_id", sa.String(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("baseline_prompt_version_id", sa.String(), sa.ForeignKey("prompt_versions.id"), nullable=False),
        sa.Column("candidate_prompt_version_id", sa.String(), sa.ForeignKey("prompt_versions.id"), nullable=False),
        sa.Column("dataset_id", sa.String(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("dataset_snapshot_id", sa.String(), sa.ForeignKey("dataset_snapshots.id")),
        sa.Column("regression_config_id", sa.String(), sa.ForeignKey("regression_configs.id")),
        sa.Column("regression_config_version", sa.Integer()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("verdict", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "experiment_variants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("experiment_id", sa.String(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("temperature", sa.Numeric()),
        sa.Column("max_tokens", sa.Integer()),
        sa.Column("config", sa.JSON()),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("experiment_id", sa.String(), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.String(), sa.ForeignKey("experiment_variants.id"), nullable=False),
        sa.Column("dataset_case_id", sa.String(), nullable=False),
        sa.Column("prompt_version_id", sa.String(), sa.ForeignKey("prompt_versions.id"), nullable=False),
        sa.Column("repetition", sa.Integer(), nullable=False),
        sa.Column("input", sa.JSON()),
        sa.Column("output", sa.JSON()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("total_tokens", sa.Integer()),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6)),
        sa.Column("pricing_version", sa.String()),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("retry_reasons", sa.JSON()),
        sa.Column("error_message", sa.Text()),
        sa.Column("seed_status", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "tool_calls",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("arguments", sa.JSON()),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "evaluations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), sa.ForeignKey("runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluator_name", sa.String(), nullable=False),
        sa.Column("evaluator_version", sa.String()),
        sa.Column("category", sa.String()),
        sa.Column("score", sa.Numeric()),
        sa.Column("weight", sa.Numeric()),
        sa.Column("include_in_quality_score", sa.Boolean()),
        sa.Column("passed", sa.Boolean()),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("hard_gate", sa.Boolean()),
        sa.Column("details", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "comparisons",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("experiment_id", sa.String(), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("baseline_run_id", sa.String(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("candidate_run_id", sa.String(), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("output_diff", sa.JSON()),
        sa.Column("tool_diff", sa.JSON()),
        sa.Column("token_delta", sa.Integer()),
        sa.Column("latency_delta_ms", sa.Integer()),
        sa.Column("cost_delta_usd", sa.Numeric(12, 6)),
        sa.Column("regression_status", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for table in [
        "comparisons",
        "evaluations",
        "tool_calls",
        "runs",
        "experiment_variants",
        "experiments",
        "regression_configs",
        "dataset_snapshots",
        "dataset_cases",
        "datasets",
        "prompt_versions",
        "prompts",
        "projects",
    ]:
        op.drop_table(table)
