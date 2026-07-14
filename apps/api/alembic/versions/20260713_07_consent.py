"""versioned privacy consent

Revision ID: 20260713_07
Revises: 20260713_06
"""
from alembic import op
import sqlalchemy as sa

revision = "20260713_07"
down_revision = "20260713_06"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("consent_version", sa.String(32), nullable=False, server_default=""))
    op.add_column("users", sa.Column("consented_at", sa.DateTime(), nullable=True))

def downgrade():
    op.drop_column("users", "consented_at")
    op.drop_column("users", "consent_version")
