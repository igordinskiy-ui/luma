"""preserve quit attempt history

Revision ID: 20260714_14
Revises: 20260714_13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260714_14"
down_revision = "20260714_13"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quit_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("end_reason", sa.String(length=24), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_reason IS NULL OR end_reason IN ('paused','relapse','restarted')", name="ck_quit_attempt_end_reason"),
    )
    op.create_index("ix_quit_attempts_user_id", "quit_attempts", ["user_id"])
    op.execute(sa.text("INSERT INTO quit_attempts (user_id, started_at) SELECT user_id, quit_started_at FROM quit_plans WHERE phase = 'quit' AND quit_started_at IS NOT NULL"))


def downgrade():
    op.drop_index("ix_quit_attempts_user_id", table_name="quit_attempts")
    op.drop_table("quit_attempts")
