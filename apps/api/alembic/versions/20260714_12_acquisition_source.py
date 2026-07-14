"""privacy-safe acquisition source"""

from alembic import op
import sqlalchemy as sa

revision = "20260714_12"
down_revision = "20260713_11"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("acquisition_source", sa.String(length=64), nullable=True))
    op.create_index("ix_users_acquisition_source", "users", ["acquisition_source"])


def downgrade():
    op.drop_index("ix_users_acquisition_source", table_name="users")
    op.drop_column("users", "acquisition_source")
