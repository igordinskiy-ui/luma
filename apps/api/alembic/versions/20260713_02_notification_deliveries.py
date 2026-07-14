"""notification delivery log

Revision ID: 20260713_02
Revises: 20260713_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_02"
down_revision = "20260713_01"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("notification_deliveries", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("channel", sa.String(24), nullable=False), sa.Column("template", sa.String(64), nullable=False), sa.Column("status", sa.String(24), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_notification_deliveries_user_id", "notification_deliveries", ["user_id"])

def downgrade():
    op.drop_table("notification_deliveries")
