"""database constraints for critical domain state

Revision ID: 20260713_08
Revises: 20260713_07
"""
from alembic import op

revision = "20260713_08"
down_revision = "20260713_07"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("quit_plans") as batch:
        batch.create_check_constraint("ck_quit_plan_remaining_nonnegative", "remaining >= 0")
        batch.create_check_constraint("ck_quit_plan_phase", "phase IN ('preparation','last_pack','quit','paused')")
    with op.batch_alter_table("behavior_events") as batch:
        batch.create_check_constraint("ck_behavior_event_kind", "kind IN ('smoked','craving','relapse')")
        batch.create_check_constraint("ck_behavior_event_intensity", "intensity IS NULL OR (intensity >= 1 AND intensity <= 5)")

def downgrade():
    with op.batch_alter_table("behavior_events") as batch:
        batch.drop_constraint("ck_behavior_event_intensity", type_="check")
        batch.drop_constraint("ck_behavior_event_kind", type_="check")
    with op.batch_alter_table("quit_plans") as batch:
        batch.drop_constraint("ck_quit_plan_phase", type_="check")
        batch.drop_constraint("ck_quit_plan_remaining_nonnegative", type_="check")
