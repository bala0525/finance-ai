"""Add report file columns and fraud_reviews table.

Revision ID: b5d1e8a3c7f2
Revises: a1b2c3d4e5f6
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b5d1e8a3c7f2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("stored_filename", sa.String(255), nullable=True))
    op.add_column("reports", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("reports", sa.Column("summary", postgresql.JSONB(), nullable=True))
    op.add_column("reports", sa.Column("limitations", sa.Text(), nullable=True))

    op.create_table(
        "fraud_reviews",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_type", sa.String(60), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="OPEN"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("document_id", "signal_type", name="uq_fraud_review_doc_signal"),
    )
    op.create_index("ix_fraud_reviews_document_id", "fraud_reviews", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_fraud_reviews_document_id", table_name="fraud_reviews")
    op.drop_table("fraud_reviews")
    for column in ("limitations", "summary", "file_size", "stored_filename"):
        op.drop_column("reports", column)
