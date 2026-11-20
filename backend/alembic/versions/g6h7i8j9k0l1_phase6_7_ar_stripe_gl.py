"""Phase 6 AR Stripe lifecycle hardening and Phase 7 GL controls.

Revision ID: g6h7i8j9k0l1
Revises: f4a1b8c2d6e0
"""
from alembic import op
import sqlalchemy as sa

revision = "g6h7i8j9k0l1"
down_revision = "f4a1b8c2d6e0"
branch_labels = None
depends_on = None


def upgrade():
    # Tenant-scope the existing per-user ledger without discarding historical rows.
    op.add_column("ledger_accounts", sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True))
    op.add_column("ledger_accounts", sa.Column("normal_balance", sa.String(6), nullable=False, server_default="DEBIT"))
    op.add_column("ledger_accounts", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("ledger_accounts", sa.Column("parent_code", sa.String(30), nullable=True))
    op.create_index("ix_ledger_accounts_tenant_id", "ledger_accounts", ["tenant_id"])
    op.execute("UPDATE ledger_accounts SET tenant_id = users.tenant_id FROM users WHERE ledger_accounts.owner_id = users.id")
    op.execute("UPDATE ledger_accounts SET normal_balance = CASE WHEN upper(account_type) IN ('ASSET','EXPENSE') THEN 'DEBIT' ELSE 'CREDIT' END")
    op.create_index("ix_ledger_accounts_tenant_code", "ledger_accounts", ["tenant_id", "code"])

    op.add_column("journal_lines", sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True))
    op.add_column("journal_lines", sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("journal_lines", sa.Column("source_type", sa.String(40), nullable=True))
    op.add_column("journal_lines", sa.Column("source_id", sa.String(80), nullable=True))
    op.add_column("journal_lines", sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("journal_lines", sa.Column("reversed_voucher_no", sa.String(60), nullable=True))
    op.create_index("ix_journal_lines_tenant_id", "journal_lines", ["tenant_id"])
    op.create_index("ix_journal_lines_tenant_voucher", "journal_lines", ["tenant_id", "voucher_no"])
    op.execute("UPDATE journal_lines SET tenant_id = users.tenant_id FROM users WHERE journal_lines.owner_id = users.id")

    op.create_table(
        "ledger_period_closes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="CLOSED"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "period_start", "period_end", name="uq_ledger_period_close"),
    )
    op.create_index("ix_ledger_period_closes_tenant_id", "ledger_period_closes", ["tenant_id"])
    op.create_index("ix_ledger_period_closes_owner_id", "ledger_period_closes", ["owner_id"])

    op.create_table(
        "stripe_refunds",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stripe_payment_id", sa.Integer(), sa.ForeignKey("stripe_payments.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("stripe_refund_id", sa.String(255), nullable=True, unique=True),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_stripe_refunds_tenant_id", "stripe_refunds", ["tenant_id"])
    op.create_index("ix_stripe_refunds_invoice_id", "stripe_refunds", ["invoice_id"])


def downgrade():
    op.drop_index("ix_stripe_refunds_invoice_id", table_name="stripe_refunds")
    op.drop_index("ix_stripe_refunds_tenant_id", table_name="stripe_refunds")
    op.drop_table("stripe_refunds")
    op.drop_index("ix_ledger_period_closes_owner_id", table_name="ledger_period_closes")
    op.drop_index("ix_ledger_period_closes_tenant_id", table_name="ledger_period_closes")
    op.drop_table("ledger_period_closes")
    op.drop_index("ix_journal_lines_tenant_voucher", table_name="journal_lines")
    op.drop_index("ix_journal_lines_tenant_id", table_name="journal_lines")
    for col in ("reversed_voucher_no", "is_reversal", "source_id", "source_type", "created_by", "tenant_id"):
        op.drop_column("journal_lines", col)
    op.drop_index("ix_ledger_accounts_tenant_code", table_name="ledger_accounts")
    op.drop_index("ix_ledger_accounts_tenant_id", table_name="ledger_accounts")
    for col in ("parent_code", "is_active", "normal_balance", "tenant_id"):
        op.drop_column("ledger_accounts", col)
