"""explicit notification opt-in and delivery idempotency

Revision ID: 20260714_16
Revises: 20260714_15
"""
from alembic import op
import sqlalchemy as sa

revision = "20260714_16"
down_revision = "20260714_15"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(sa.text("UPDATE notification_preferences SET enabled = false"))
    with op.batch_alter_table("notification_preferences") as batch:
        batch.alter_column("enabled", existing_type=sa.Boolean(), server_default=sa.false())
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.add_column(sa.Column("outbox_event_id", sa.Integer(), nullable=True))
        batch.create_unique_constraint("uq_notification_deliveries_outbox_event_id", ["outbox_event_id"])


def downgrade():
    with op.batch_alter_table("notification_deliveries") as batch:
        batch.drop_constraint("uq_notification_deliveries_outbox_event_id", type_="unique")
        batch.drop_column("outbox_event_id")
    with op.batch_alter_table("notification_preferences") as batch:
        batch.alter_column("enabled", existing_type=sa.Boolean(), server_default=sa.true())
