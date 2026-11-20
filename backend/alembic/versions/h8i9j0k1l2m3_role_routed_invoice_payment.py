"""Add role-routed document approval, payer assignment and payment audit.

Revision ID: h8i9j0k1l2m3
Revises: g6h7i8j9k0l1
"""
from alembic import op
import sqlalchemy as sa

revision = "h8i9j0k1l2m3"
down_revision = "g6h7i8j9k0l1"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable fields preserve all existing document rows and their current state.
    op.add_column("documents", sa.Column("uploader_role", sa.String(length=50), nullable=True))
    op.add_column("documents", sa.Column("assigned_finance_user_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_assigned_finance_user", "documents", "users", ["assigned_finance_user_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_documents_assigned_finance_user_id", "documents", ["assigned_finance_user_id"])

    op.add_column("documents", sa.Column("first_reviewed_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_first_reviewed_by", "documents", "users", ["first_reviewed_by"], ["id"], ondelete="SET NULL")
    op.add_column("documents", sa.Column("first_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("first_review_action", sa.String(length=30), nullable=True))

    op.add_column("documents", sa.Column("verified_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_verified_by", "documents", "users", ["verified_by"], ["id"], ondelete="SET NULL")
    op.add_column("documents", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("approved_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_approved_by", "documents", "users", ["approved_by"], ["id"], ondelete="SET NULL")
    op.add_column("documents", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("rejected_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_rejected_by", "documents", "users", ["rejected_by"], ["id"], ondelete="SET NULL")
    op.add_column("documents", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("documents", sa.Column("chief_accountant_approved_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_chief_accountant_approved_by", "documents", "users", ["chief_accountant_approved_by"], ["id"], ondelete="SET NULL")
    op.add_column("documents", sa.Column("chief_accountant_approved_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("documents", sa.Column("paid_by", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_paid_by", "documents", "users", ["paid_by"], ["id"], ondelete="SET NULL")
    op.add_column("documents", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("documents", sa.Column("payment_amount", sa.Numeric(14, 2), nullable=True))
    op.add_column("documents", sa.Column("payment_reference", sa.String(length=120), nullable=True))
    op.add_column("documents", sa.Column("payment_bank_name", sa.String(length=120), nullable=True))
    op.add_column("documents", sa.Column("payment_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("ledger_voucher_no", sa.String(length=60), nullable=True))

    # Existing journal lines remain valid; new AP/expense payments link back to their stored document.
    op.add_column("journal_lines", sa.Column("source_document_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_journal_lines_source_document", "journal_lines", "documents", ["source_document_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_journal_lines_source_document_id", "journal_lines", ["source_document_id"])


def downgrade():
    op.drop_index("ix_journal_lines_source_document_id", table_name="journal_lines")
    op.drop_constraint("fk_journal_lines_source_document", "journal_lines", type_="foreignkey")
    op.drop_column("journal_lines", "source_document_id")

    for name in ("ledger_voucher_no", "payment_date", "payment_bank_name", "payment_reference", "payment_amount", "paid_at"):
        op.drop_column("documents", name)
    op.drop_constraint("fk_documents_paid_by", "documents", type_="foreignkey")
    op.drop_column("documents", "paid_by")
    op.drop_column("documents", "chief_accountant_approved_at")
    op.drop_constraint("fk_documents_chief_accountant_approved_by", "documents", type_="foreignkey")
    op.drop_column("documents", "chief_accountant_approved_by")
    op.drop_column("documents", "rejected_at")
    op.drop_constraint("fk_documents_rejected_by", "documents", type_="foreignkey")
    op.drop_column("documents", "rejected_by")
    op.drop_column("documents", "approved_at")
    op.drop_constraint("fk_documents_approved_by", "documents", type_="foreignkey")
    op.drop_column("documents", "approved_by")
    op.drop_column("documents", "verified_at")
    op.drop_constraint("fk_documents_verified_by", "documents", type_="foreignkey")
    op.drop_column("documents", "verified_by")
    op.drop_column("documents", "first_review_action")
    op.drop_column("documents", "first_reviewed_at")
    op.drop_constraint("fk_documents_first_reviewed_by", "documents", type_="foreignkey")
    op.drop_column("documents", "first_reviewed_by")
    op.drop_index("ix_documents_assigned_finance_user_id", table_name="documents")
    op.drop_constraint("fk_documents_assigned_finance_user", "documents", type_="foreignkey")
    op.drop_column("documents", "assigned_finance_user_id")
    op.drop_column("documents", "uploader_role")
