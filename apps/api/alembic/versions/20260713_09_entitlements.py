"""unified entitlement boundary

Revision ID: 20260713_09
Revises: 20260713_08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_09"
down_revision = "20260713_08"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("entitlements", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("feature", sa.String(64), nullable=False), sa.Column("source", sa.String(32), nullable=False), sa.Column("expires_at", sa.DateTime(), nullable=True), sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")))
    op.create_index("ix_entitlements_user_id", "entitlements", ["user_id"])
    op.create_index("ix_entitlements_feature", "entitlements", ["feature"])

def downgrade():
    op.drop_table("entitlements")
