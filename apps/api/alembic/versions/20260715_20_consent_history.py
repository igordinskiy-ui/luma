"""persist immutable versioned consent history

Revision ID: 20260715_20
Revises: 20260714_19
"""
from alembic import op
import sqlalchemy as sa

revision = "20260715_20"
down_revision = "20260714_19"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("consent_digest", sa.String(length=64), nullable=False, server_default=""))
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("document_version", sa.String(length=32), nullable=False),
        sa.Column("document_digest", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column("age_confirmed", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("accepted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "document_version", "document_digest", name="uq_consent_record_document"),
        sa.CheckConstraint("source IN ('legacy','onboarding','reconsent')", name="ck_consent_record_source"),
    )
    op.create_index("ix_consent_records_user_id", "consent_records", ["user_id"])
    op.execute(sa.text(
        """INSERT INTO consent_records
        (user_id, document_version, document_digest, source, age_confirmed, accepted_at)
        SELECT id, consent_version, '', 'legacy',
               CASE WHEN age_confirmed_at IS NULL THEN 0 ELSE 1 END,
               consented_at
        FROM users
        WHERE consented_at IS NOT NULL"""
    ))


def downgrade():
    op.drop_index("ix_consent_records_user_id", table_name="consent_records")
    op.drop_table("consent_records")
    op.drop_column("users", "consent_digest")
