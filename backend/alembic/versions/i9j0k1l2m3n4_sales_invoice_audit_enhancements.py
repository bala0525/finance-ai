"""Add AR rejection and customer payer audit details.

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
"""
from alembic import op
import sqlalchemy as sa

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade():
    # NEW: nullable audit fields preserve existing invoice/payment records.
    op.add_column("sales_invoices", sa.Column("rejected_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_sales_invoices_rejected_by", "sales_invoices", "users", ["rejected_by"], ["id"], ondelete="SET NULL")
    op.add_column("sales_invoices", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("stripe_payments", sa.Column("payer_email", sa.String(length=255), nullable=True))
    # Backfill payer identity where the invoice already contains customer email.
    op.execute("UPDATE stripe_payments SET payer_email = sales_invoices.customer_email FROM sales_invoices WHERE stripe_payments.invoice_id = sales_invoices.id AND stripe_payments.payer_email IS NULL")


def downgrade():
    op.drop_column("stripe_payments", "payer_email")
    op.drop_column("sales_invoices", "rejected_at")
    op.drop_constraint("fk_sales_invoices_rejected_by", "sales_invoices", type_="foreignkey")
    op.drop_column("sales_invoices", "rejected_by")
