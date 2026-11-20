"""AR sales invoice lifecycle and Stripe payment records.

Revision ID: e2f6a9c1b4d8
Revises: c9e4a7b2d610
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e2f6a9c1b4d8"
down_revision = "c9e4a7b2d610"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sales_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=False),
        sa.Column("customer_gstin", sa.String(20)),
        sa.Column("invoice_number", sa.String(60)),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("subtotal", sa.Numeric(16, 2), nullable=False),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("gst_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(40), nullable=False, server_default="DRAFT"),
        sa.Column("manager_approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("manager_approved_at", sa.DateTime(timezone=True)),
        sa.Column("admin_approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("admin_approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("email_status", sa.String(20), nullable=False, server_default="NOT_SENT"),
        sa.Column("emailed_at", sa.DateTime(timezone=True)),
        sa.Column("email_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "invoice_number", name="uq_sales_invoice_tenant_number"),
    )
    op.create_index("ix_sales_invoices_tenant_id", "sales_invoices", ["tenant_id"])
    op.create_index("ix_sales_invoices_owner_id", "sales_invoices", ["owner_id"])
    op.create_index("ix_sales_invoices_status", "sales_invoices", ["status"])
    op.create_table(
        "sales_invoice_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 3), nullable=False),
        sa.Column("unit_price", sa.Numeric(16, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(16, 2), nullable=False),
    )
    op.create_index("ix_sales_invoice_lines_invoice_id", "sales_invoice_lines", ["invoice_id"])
    op.create_table(
        "stripe_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("checkout_session_id", sa.String(255), nullable=False),
        sa.Column("payment_intent_id", sa.String(255)),
        sa.Column("stripe_event_id", sa.String(255)),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("checkout_session_id", name="uq_stripe_payment_checkout_session"),
        sa.UniqueConstraint("stripe_event_id", name="uq_stripe_payment_event"),
    )
    op.create_index("ix_stripe_payments_tenant_id", "stripe_payments", ["tenant_id"])
    op.create_index("ix_stripe_payments_invoice_id", "stripe_payments", ["invoice_id"])
    op.create_index("ix_stripe_payments_payment_intent_id", "stripe_payments", ["payment_intent_id"])
    op.create_table(
        "sales_invoice_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("from_status", sa.String(40)),
        sa.Column("to_status", sa.String(40)),
        sa.Column("reason", sa.Text()),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sales_invoice_events_tenant_id", "sales_invoice_events", ["tenant_id"])
    op.create_index("ix_sales_invoice_events_invoice_id", "sales_invoice_events", ["invoice_id"])


def downgrade():
    op.drop_table("sales_invoice_events")
    op.drop_table("stripe_payments")
    op.drop_table("sales_invoice_lines")
    op.drop_table("sales_invoices")
