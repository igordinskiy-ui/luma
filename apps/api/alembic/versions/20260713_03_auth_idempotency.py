"""session version and idempotent client events

Revision ID: 20260713_03
Revises: 20260713_02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_03"
down_revision = "20260713_02"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("behavior_events", sa.Column("client_event_id", sa.String(64), nullable=True))
    with op.batch_alter_table("behavior_events") as batch:
        batch.create_unique_constraint("uq_behavior_events_user_client_event", ["user_id", "client_event_id"])
    op.add_column("notification_deliveries", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("notification_deliveries", sa.Column("sent_at", sa.DateTime(), nullable=True))
    op.create_index("ix_delivery_user_status_created", "notification_deliveries", ["user_id", "status", "created_at"])

def downgrade():
    op.drop_index("ix_delivery_user_status_created", table_name="notification_deliveries")
    op.drop_column("notification_deliveries", "sent_at")
    op.drop_column("notification_deliveries", "attempts")
    with op.batch_alter_table("behavior_events") as batch:
        batch.drop_constraint("uq_behavior_events_user_client_event", type_="unique")
    op.drop_column("behavior_events", "client_event_id")
    op.drop_column("users", "auth_version")
