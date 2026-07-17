"""add adaptive support outcomes and recovery context

Revision ID: 20260717_21
Revises: 20260715_20
"""
from alembic import op
import sqlalchemy as sa

revision = "20260717_21"
down_revision = "20260715_20"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("coping_sessions") as batch_op:
        batch_op.add_column(sa.Column("outcome", sa.String(length=16), nullable=True))
        batch_op.create_check_constraint("ck_coping_session_outcome", "outcome IS NULL OR outcome IN ('helped','same','worse')")
    with op.batch_alter_table("behavior_events") as batch_op:
        batch_op.add_column(sa.Column("relapse_context", sa.String(length=24), nullable=True))
        batch_op.create_check_constraint("ck_behavior_event_relapse_context", "relapse_context IS NULL OR (kind = 'relapse' AND relapse_context IN ('one','day','days','afraid','angry','hopeless'))")


def downgrade():
    with op.batch_alter_table("behavior_events") as batch_op:
        batch_op.drop_constraint("ck_behavior_event_relapse_context", type_="check")
        batch_op.drop_column("relapse_context")
    with op.batch_alter_table("coping_sessions") as batch_op:
        batch_op.drop_constraint("ck_coping_session_outcome", type_="check")
        batch_op.drop_column("outcome")
