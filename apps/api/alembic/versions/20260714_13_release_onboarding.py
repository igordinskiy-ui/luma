"""age gate and preparation target

Revision ID: 20260714_13
Revises: 20260714_12
"""
from alembic import op
import sqlalchemy as sa

revision = "20260714_13"
down_revision = "20260714_12"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("age_confirmed_at", sa.DateTime(), nullable=True))
    op.add_column("quit_plans", sa.Column("target_quit_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("quit_plans", "target_quit_at")
    op.drop_column("users", "age_confirmed_at")
