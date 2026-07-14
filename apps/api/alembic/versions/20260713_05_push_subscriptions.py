"""web push subscriptions

Revision ID: 20260713_05
Revises: 20260713_04
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_05"
down_revision = "20260713_04"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("push_subscriptions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("endpoint", sa.Text(), nullable=False, unique=True), sa.Column("p256dh", sa.Text(), nullable=False), sa.Column("auth", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])

def downgrade():
    op.drop_table("push_subscriptions")
