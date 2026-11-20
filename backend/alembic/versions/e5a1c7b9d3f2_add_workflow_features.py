"""Add AI-employee workflow tables and document confidence / coding columns.

Revision ID: e5a1c7b9d3f2
Revises: d8f2a6c4b1e7
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5a1c7b9d3f2"
down_revision = "d8f2a6c4b1e7"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "payment_batches",
    "payment_batch_items",
    "workflow_resolutions",
    "dispute_cases",
    "collection_reminders",
    "expense_policies",
    "expense_decisions",
    "report_schedules",
]


def upgrade() -> None:
    # ---- documents: extraction confidence + GL coding ----
    op.add_column("documents", sa.Column("extraction_confidence", sa.Numeric(4, 3), nullable=True))
    op.add_column("documents", sa.Column("field_confidence", postgresql.JSONB(), nullable=True))
    op.add_column("documents", sa.Column("suggested_account_code", sa.String(30), nullable=True))
    op.add_column("documents", sa.Column("suggested_account_name", sa.String(255), nullable=True))
    op.add_column("documents", sa.Column("coding_confidence", sa.Numeric(4, 3), nullable=True))
    op.add_column("documents", sa.Column("coding_source", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("account_code", sa.String(30), nullable=True))
    op.add_column(
        "documents",
        sa.Column("coding_status", sa.String(20), nullable=False, server_default="NONE"),
    )

    # ---- AP payment batches ----
    op.create_table(
        "payment_batches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("payment_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False, server_default="0"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paid_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["paid_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_batches_owner_id", "payment_batches", ["owner_id"])

    op.create_table(
        "payment_batch_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["payment_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_payment_batch_item_document"),
    )
    op.create_index("ix_payment_batch_items_batch_id", "payment_batch_items", ["batch_id"])

    # ---- exception / reconciliation resolutions ----
    op.create_table(
        "workflow_resolutions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(30), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("item_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "document_id", "item_key", name="uq_workflow_resolution"),
    )
    op.create_index("ix_workflow_resolutions_document_id", "workflow_resolutions", ["document_id"])

    # ---- AR disputes + reminders ----
    op.create_table(
        "dispute_cases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dispute_cases_owner_id", "dispute_cases", ["owner_id"])
    op.create_index("ix_dispute_cases_document_id", "dispute_cases", ["document_id"])

    op.create_table(
        "collection_reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_collection_reminders_owner_id", "collection_reminders", ["owner_id"])
    op.create_index("ix_collection_reminders_document_id", "collection_reminders", ["document_id"])

    # ---- expense policy + decisions ----
    op.create_table(
        "expense_policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("expense_type", sa.String(40), nullable=False),
        sa.Column("claim_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("receipt_required", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("expense_type"),
    )

    op.create_table(
        "expense_decisions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("approved_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.Integer(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id"),
    )

    # ---- report schedules ----
    op.create_table(
        "report_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("report_type", sa.String(40), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("next_run", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_report_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["last_report_id"], ["reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_report_schedules_owner_id", "report_schedules", ["owner_id"])

    # Same policy as the existing tables: RLS on, no policies, so Supabase's
    # public REST endpoints expose nothing. The API enforces access.
    for table in NEW_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
    for column in (
        "coding_status",
        "account_code",
        "coding_source",
        "coding_confidence",
        "suggested_account_name",
        "suggested_account_code",
        "field_confidence",
        "extraction_confidence",
    ):
        op.drop_column("documents", column)
