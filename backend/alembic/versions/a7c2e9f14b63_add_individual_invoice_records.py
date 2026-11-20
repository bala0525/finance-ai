"""Add individual invoice records for AP registers."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7c2e9f14b63"
down_revision = "f3b9c1d4a7e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "source_document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("invoice_number", sa.String(150)),
        sa.Column("vendor_name", sa.String(255)),
        sa.Column("invoice_date", sa.Date()),
        sa.Column("due_date", sa.Date()),
        sa.Column("po_amount", sa.Numeric(14, 2)),
        sa.Column("subtotal", sa.Numeric(14, 2)),
        sa.Column("tax_amount", sa.Numeric(14, 2)),
        sa.Column("total_amount", sa.Numeric(14, 2)),
        sa.Column(
            "payment_status",
            sa.String(30),
            nullable=False,
            server_default="UNKNOWN",
        ),
        sa.Column(
            "validation_status",
            sa.String(30),
            nullable=False,
            server_default="NOT_RUN",
        ),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "flags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "review_status",
            sa.String(30),
            nullable=False,
            server_default="NOT_READY",
        ),
        sa.Column(
            "reviewed_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "source_document_id",
            "row_number",
            name="uq_invoice_records_source_row",
        ),
    )
    op.create_index(
        "ix_invoice_records_source_document_id",
        "invoice_records",
        ["source_document_id"],
    )
    op.create_index(
        "ix_invoice_records_owner_id",
        "invoice_records",
        ["owner_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_invoice_records_owner_id",
        table_name="invoice_records",
    )
    op.drop_index(
        "ix_invoice_records_source_document_id",
        table_name="invoice_records",
    )
    op.drop_table("invoice_records")
