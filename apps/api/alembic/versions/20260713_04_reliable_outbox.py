"""reliable outbox state

Revision ID: 20260713_04
Revises: 20260713_03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_04"
down_revision = "20260713_03"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("outbox_events", sa.Column("status", sa.String(24), nullable=False, server_default="pending"))
    op.add_column("outbox_events", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("outbox_events", sa.Column("next_attempt_at", sa.DateTime(), nullable=True))
    op.add_column("outbox_events", sa.Column("locked_at", sa.DateTime(), nullable=True))
    op.add_column("outbox_events", sa.Column("error", sa.Text(), nullable=False, server_default=""))
    op.execute("UPDATE outbox_events SET status = CASE WHEN processed THEN 'processed' ELSE 'pending' END")
    op.create_index("ix_outbox_events_status", "outbox_events", ["status"])
    with op.batch_alter_table("outbox_events") as batch:
        batch.drop_column("processed")

def downgrade():
    op.add_column("outbox_events", sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE outbox_events SET processed = CASE WHEN status = 'processed' THEN 1 ELSE 0 END")
    op.drop_index("ix_outbox_events_status", table_name="outbox_events")
    op.drop_column("outbox_events", "error")
    op.drop_column("outbox_events", "locked_at")
    op.drop_column("outbox_events", "next_attempt_at")
    op.drop_column("outbox_events", "attempts")
    op.drop_column("outbox_events", "status")
