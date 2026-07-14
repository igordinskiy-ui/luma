"""purge duplicated product details from analytics

Revision ID: 20260714_19
Revises: 20260714_18
"""
from alembic import op
import sqlalchemy as sa

revision = "20260714_19"
down_revision = "20260714_18"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text(
        "DELETE FROM analytics_events WHERE event_name NOT IN ('client_session_started','client_crash')"
    ))


def downgrade():
    # Deleted duplicated signals cannot and should not be reconstructed.
    pass
