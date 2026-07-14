"""recovery mode after relapse

Revision ID: 20260713_11
Revises: 20260713_10
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_11"
down_revision = "20260713_10"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("quit_plans", sa.Column("recovery_until", sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column("quit_plans", "recovery_until")
