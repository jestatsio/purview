"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspace",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
    )
    op.create_table(
        "app_user",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
    )
    op.create_table(
        "membership",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspace.id"), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("app_user.id"), primary_key=True),
        sa.Column("role", sa.String(length=20), nullable=False),
    )
    op.create_table(
        "project",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
    )
    op.create_table(
        "task",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
    )
    op.create_table(
        "legacy_import",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.String(length=200), nullable=False),
    )


def downgrade() -> None:
    for table in ("legacy_import", "task", "project", "membership", "app_user", "workspace"):
        op.drop_table(table)
