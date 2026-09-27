"""hosted tables

Revision ID: 20260926_0002
Revises: 20260924_0001
Create Date: 2026-09-26
"""

import sqlalchemy as sa
from alembic import op

revision = "20260926_0002"
down_revision = "20260924_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("auth_provider", sa.String(), nullable=False),
        sa.Column("auth_subject", sa.String(), nullable=False),
        sa.Column("email", sa.String()),
        sa.Column("name", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("auth_provider", "auth_subject"),
    )
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "workspace_members",
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "provider_secrets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("key_hint", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "provider"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("workspace_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "retention_settings",
        sa.Column("workspace_id", sa.String(), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("experiment_metadata_days", sa.Integer(), nullable=False),
        sa.Column("raw_model_output_days", sa.Integer(), nullable=False),
        sa.Column("raw_provider_response_days", sa.Integer(), nullable=False),
        sa.Column("application_log_days", sa.Integer(), nullable=False),
        sa.Column("audit_log_days", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    for table in [
        "retention_settings",
        "audit_events",
        "provider_secrets",
        "workspace_members",
        "workspaces",
        "users",
    ]:
        op.drop_table(table)
