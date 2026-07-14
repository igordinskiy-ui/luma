"""persist coping session lifecycle

Revision ID: 20260714_15
Revises: 20260714_14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260714_15"
down_revision = "20260714_14"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "coping_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("client_session_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("trigger", sa.String(length=64), nullable=True),
        sa.Column("intensity_before", sa.Integer(), nullable=False),
        sa.Column("intensity_after", sa.Integer(), nullable=True),
        sa.Column("technique", sa.String(length=32), nullable=True),
        sa.Column("content_version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="active", nullable=False),
        sa.Column("started_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("source IN ('dashboard','journal','notification','offline')", name="ck_coping_session_source"),
        sa.CheckConstraint("status IN ('active','paused','completed','abandoned')", name="ck_coping_session_status"),
        sa.CheckConstraint("intensity_before >= 1 AND intensity_before <= 10", name="ck_coping_session_intensity_before"),
        sa.CheckConstraint("intensity_after IS NULL OR (intensity_after >= 1 AND intensity_after <= 10)", name="ck_coping_session_intensity_after"),
        sa.UniqueConstraint("user_id", "client_session_id", name="uq_coping_sessions_user_client_session"),
    )
    op.create_index("ix_coping_sessions_user_id", "coping_sessions", ["user_id"])


def downgrade():
    op.drop_index("ix_coping_sessions_user_id", table_name="coping_sessions")
    op.drop_table("coping_sessions")
