"""remember the journey phase that was paused

Revision ID: 20260714_17
Revises: 20260714_16
"""
from alembic import op
import sqlalchemy as sa

revision = "20260714_17"
down_revision = "20260714_16"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("quit_plans") as batch:
        batch.add_column(sa.Column("paused_from", sa.String(length=24), nullable=True))
        batch.create_check_constraint("ck_quit_plan_paused_from", "paused_from IS NULL OR paused_from IN ('preparation','last_pack','quit')")
    op.execute(sa.text("UPDATE quit_plans SET paused_from = CASE WHEN remaining > 0 THEN 'last_pack' ELSE 'quit' END WHERE phase = 'paused'"))


def downgrade():
    with op.batch_alter_table("quit_plans") as batch:
        batch.drop_constraint("ck_quit_plan_paused_from", type_="check")
        batch.drop_column("paused_from")
