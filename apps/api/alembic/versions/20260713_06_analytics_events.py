"""privacy-safe product analytics event log

Revision ID: 20260713_06
Revises: 20260713_05
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_06"
down_revision = "20260713_05"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("analytics_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("event_name", sa.String(64), nullable=False), sa.Column("properties", sa.Text(), nullable=False), sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_analytics_events_user_id", "analytics_events", ["user_id"])
    op.create_index("ix_analytics_events_event_name", "analytics_events", ["event_name"])

def downgrade():
    op.drop_table("analytics_events")
