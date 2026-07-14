"""initial schema

Revision ID: 20260713_01
Revises:
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_01"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("telegram_id", sa.String(64), nullable=False, unique=True), sa.Column("timezone", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])
    op.create_table("quit_plans", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False), sa.Column("cigarettes_per_pack", sa.Integer(), nullable=False), sa.Column("remaining", sa.Integer(), nullable=False), sa.Column("pack_price", sa.Float(), nullable=False), sa.Column("phase", sa.String(24), nullable=False), sa.Column("quit_started_at", sa.DateTime()), sa.Column("reasons", sa.Text(), nullable=False))
    op.create_table("behavior_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("kind", sa.String(24), nullable=False), sa.Column("trigger", sa.String(64)), sa.Column("intensity", sa.Integer()), sa.Column("note", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_behavior_events_user_id", "behavior_events", ["user_id"])
    op.create_index("ix_behavior_events_kind", "behavior_events", ["kind"])
    op.create_table("notification_preferences", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("max_daily", sa.Integer(), nullable=False), sa.Column("quiet_start", sa.Integer(), nullable=False), sa.Column("quiet_end", sa.Integer(), nullable=False))
    op.create_table("outbox_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("topic", sa.String(64), nullable=False), sa.Column("payload", sa.Text(), nullable=False), sa.Column("processed", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_outbox_events_user_id", "outbox_events", ["user_id"])
    op.create_index("ix_outbox_events_topic", "outbox_events", ["topic"])

def downgrade():
    op.drop_table("outbox_events"); op.drop_table("notification_preferences"); op.drop_table("behavior_events"); op.drop_table("quit_plans"); op.drop_table("users")
