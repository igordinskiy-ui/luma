"""pilot feedback queue

Revision ID: 20260713_10
Revises: 20260713_09
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_10"
down_revision = "20260713_09"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("category", sa.String(24), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("category IN ('bug','idea','support','content')", name="ck_feedback_category"),
        sa.CheckConstraint("status IN ('open','resolved')", name="ck_feedback_status"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_status", "feedback", ["status"])

def downgrade():
    op.drop_table("feedback")
