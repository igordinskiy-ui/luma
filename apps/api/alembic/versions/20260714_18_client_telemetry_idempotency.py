"""deduplicate privacy-safe client telemetry under concurrency

Revision ID: 20260714_18
Revises: 20260714_17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260714_18"
down_revision = "20260714_17"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "uq_analytics_client_session_event",
        "analytics_events",
        ["user_id", "event_name", "properties"],
        unique=True,
        sqlite_where=sa.text("event_name IN ('client_session_started','client_crash')"),
        postgresql_where=sa.text("event_name IN ('client_session_started','client_crash')"),
    )


def downgrade():
    op.drop_index("uq_analytics_client_session_event", table_name="analytics_events")
