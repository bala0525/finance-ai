"""Add invoice extraction, review, and audit fields.

Revision ID: d4a6b8c2e910
Revises: c91a5d2e7f40
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d4a6b8c2e910"
down_revision = "c91a5d2e7f40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("vendor_name", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("invoice_number", sa.String(150), nullable=True))
    op.add_column("documents", sa.Column("invoice_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("due_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("subtotal", sa.Numeric(14, 2), nullable=True))
    op.add_column("documents", sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("documents", sa.Column("total_amount", sa.Numeric(14, 2), nullable=True))

    op.add_column(
        "documents",
        sa.Column("validation_status", sa.String(30), server_default="NOT_RUN", nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column("validation_errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("is_duplicate", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "documents",
        sa.Column("review_status", sa.String(30), server_default="NOT_READY", nullable=False),
    )
    op.add_column("documents", sa.Column("reviewed_by", sa.Integer(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("documents", sa.Column("rejection_reason", sa.Text(), nullable=True))

    op.create_foreign_key(
        "fk_documents_reviewed_by_users",
        "documents",
        "users",
        ["reviewed_by"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "document_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_audit_events_document_id",
        "document_audit_events",
        ["document_id"],
    )
    op.create_index(
        "ix_document_audit_events_owner_id",
        "document_audit_events",
        ["owner_id"],
    )


def downgrade() -> None:
    op.drop_table("document_audit_events")
    op.drop_constraint(
        "fk_documents_reviewed_by_users", "documents", type_="foreignkey"
    )

    for column in [
        "rejection_reason",
        "reviewed_at",
        "reviewed_by",
        "review_status",
        "is_duplicate",
        "validation_errors",
        "validation_status",
        "total_amount",
        "tax_amount",
        "subtotal",
        "due_date",
        "invoice_date",
        "invoice_number",
        "vendor_name",
    ]:
        op.drop_column("documents", column)
