"""Add standard ledger tables (accounts, journal lines, party invoices, imports).

Revision ID: f3b7c9d1a2e5
Revises: e71c4a8b2d90
"""

from alembic import op
import sqlalchemy as sa


revision = "f3b7c9d1a2e5"
down_revision = "e71c4a8b2d90"
branch_labels = None
depends_on = None


def _owner_fk():
    return sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE")


def upgrade() -> None:
    op.create_table(
        "ledger_accounts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        _owner_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "code", name="uq_ledger_accounts_owner_code"),
    )
    op.create_index("ix_ledger_accounts_owner_id", "ledger_accounts", ["owner_id"])

    op.create_table(
        "journal_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("voucher_no", sa.String(length=60), nullable=False),
        sa.Column("account_code", sa.String(length=30), nullable=False),
        sa.Column("narration", sa.String(length=500), nullable=True),
        sa.Column("debit", sa.Numeric(18, 2), server_default="0", nullable=False),
        sa.Column("credit", sa.Numeric(18, 2), server_default="0", nullable=False),
        _owner_fk(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_journal_lines_owner_id", "journal_lines", ["owner_id"])
    op.create_index("ix_journal_lines_voucher_no", "journal_lines", ["voucher_no"])
    op.create_index("ix_journal_lines_account_code", "journal_lines", ["account_code"])

    op.create_table(
        "party_invoices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("invoice_type", sa.String(length=10), nullable=False),
        sa.Column("invoice_no", sa.String(length=60), nullable=False),
        sa.Column("party_name", sa.String(length=255), nullable=False),
        sa.Column("gstin", sa.String(length=20), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("taxable_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("gst_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(18, 2), server_default="0", nullable=False),
        _owner_fk(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id", "invoice_type", "invoice_no", name="uq_party_invoices_owner_type_no"
        ),
    )
    op.create_index("ix_party_invoices_owner_id", "party_invoices", ["owner_id"])

    op.create_table(
        "ledger_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("account_count", sa.Integer(), nullable=False),
        sa.Column("journal_line_count", sa.Integer(), nullable=False),
        sa.Column("invoice_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _owner_fk(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ledger_imports_owner_id", "ledger_imports", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_ledger_imports_owner_id", table_name="ledger_imports")
    op.drop_table("ledger_imports")
    op.drop_index("ix_party_invoices_owner_id", table_name="party_invoices")
    op.drop_table("party_invoices")
    op.drop_index("ix_journal_lines_account_code", table_name="journal_lines")
    op.drop_index("ix_journal_lines_voucher_no", table_name="journal_lines")
    op.drop_index("ix_journal_lines_owner_id", table_name="journal_lines")
    op.drop_table("journal_lines")
    op.drop_index("ix_ledger_accounts_owner_id", table_name="ledger_accounts")
    op.drop_table("ledger_accounts")
