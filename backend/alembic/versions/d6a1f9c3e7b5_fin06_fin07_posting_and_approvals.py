"""FIN-06 posting and learning loop + FIN-07 approvals and policy engine.

Revision ID: d6a1f9c3e7b5
Revises: c4f8a2e6d913
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d6a1f9c3e7b5"
down_revision = "c4f8a2e6d913"
branch_labels = None
depends_on = None

NEW_TABLES = ["approval_policies", "approvals", "approval_decisions", "category_corrections",
              "posting_schedules", "posting_schedule_items"]


def _ts(name="created_at"):
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "approval_policies",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("autopilot_level", sa.String(20), nullable=False, server_default="SUGGEST_ONLY"),
        sa.Column("auto_approve_limit", sa.Numeric(14, 2), nullable=False, server_default="10000"),
        sa.Column("second_approver_limit", sa.Numeric(14, 2), nullable=True),
        sa.Column("known_vendor_only", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.UniqueConstraint("tenant_id", name="uq_approval_policies_tenant"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("required_approvals", sa.Integer(), nullable=False),
        sa.Column("rule_applied", sa.String(60), nullable=False),
        sa.Column("autopilot_level", sa.String(20), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="PENDING"),
        _ts(),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_tenant_id", "approvals", ["tenant_id"])
    op.create_index("ix_approvals_document_id", "approvals", ["document_id"])
    op.create_index("uq_approvals_open_document", "approvals", ["document_id"], unique=True,
                    postgresql_where=sa.text("status IN ('PENDING','APPROVED')"))
    op.create_table(
        "approval_decisions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("approval_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("approver_type", sa.String(10), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("rule_applied", sa.String(60), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        _ts(),
        sa.ForeignKeyConstraint(["approval_id"], ["approvals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approval_decisions_approval_id", "approval_decisions", ["approval_id"])
    op.create_index("uq_approval_decisions_user", "approval_decisions", ["approval_id", "approver_id"], unique=True,
                    postgresql_where=sa.text("approver_type = 'USER'"))
    op.create_table(
        "category_corrections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("vendor_key", sa.String(255), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("suggested_code", sa.String(30), nullable=True),
        sa.Column("chosen_code", sa.String(30), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        _ts(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tenant_id", "vendor_key", "created_at"):
        op.create_index(f"ix_category_corrections_{col}", "category_corrections", [col])
    op.create_table(
        "posting_schedules",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("params", postgresql.JSONB(), nullable=False),
        sa.Column("total", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="ACTIVE"),
        _ts(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tenant_id", "owner_id", "source_document_id"):
        op.create_index(f"ix_posting_schedules_{col}", "posting_schedules", [col])
    op.create_table(
        "posting_schedule_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schedule_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("period_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reverses", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("entry_id", sa.Integer(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["schedule_id"], ["posting_schedules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entry_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("entry_id", name="uq_posting_schedule_items_entry"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_posting_schedule_items_schedule_id", "posting_schedule_items", ["schedule_id"])
    op.create_index("ix_posting_schedule_items_period_date", "posting_schedule_items", ["period_date"])

    # fin_forbid_mutation() comes from migration b7e3d5a1c902 (FIN-01).
    for table in ("approval_decisions", "category_corrections"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION fin_forbid_mutation()"
        )
    for table in NEW_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    for table in ("category_corrections", "approval_decisions"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    for table in ("posting_schedule_items", "posting_schedules", "category_corrections",
                  "approval_decisions", "approvals", "approval_policies"):
        op.drop_table(table)
