"""FIN-08 ledger reconciliation/month close and FIN-09 orchestrator inbox."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f9a8c7d6e5b4"
down_revision = "d6a1f9c3e7b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "bank_reconciliation_matches",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bank_transaction_id", sa.BigInteger(), sa.ForeignKey("bank_transactions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="RESTRICT")),
        sa.Column("status", sa.String(20), nullable=False, server_default="UNMATCHED"),
        sa.Column("suggested_journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id", ondelete="SET NULL")),
        sa.Column("suggestion_reason", sa.Text()),
        sa.Column("confirmed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_bank_reconciliation_matches_tenant_id", "bank_reconciliation_matches", ["tenant_id"])
    op.create_index("ix_bank_reconciliation_matches_owner_id", "bank_reconciliation_matches", ["owner_id"])
    op.create_index("ix_bank_recon_tenant_status", "bank_reconciliation_matches", ["tenant_id", "status"])
    op.create_unique_constraint("uq_bank_recon_transaction", "bank_reconciliation_matches", ["bank_transaction_id"])

    op.create_table(
        "month_closes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False), sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("checklist", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "period_start", "period_end", name="uq_month_close_period"),
    )
    op.create_index("ix_month_closes_tenant_id", "month_closes", ["tenant_id"])
    op.create_index("ix_month_closes_owner_id", "month_closes", ["owner_id"])

    op.create_table(
        "orchestrator_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_event_id", sa.BigInteger(), sa.ForeignKey("domain_events.id", ondelete="SET NULL")),
        sa.Column("dedupe_key", sa.String(160), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("source_agent", sa.String(60), nullable=False, server_default="Chief Accountant"),
        sa.Column("assigned_owner", sa.String(120), nullable=False, server_default="Finance Team"),
        sa.Column("due_date", sa.Date()), sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"), sa.Column("blocking_reason", sa.Text()),
        sa.Column("related_records", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_orchestrator_task_dedupe"),
    )
    op.create_index("ix_orchestrator_tasks_tenant_id", "orchestrator_tasks", ["tenant_id"])
    op.create_index("ix_orchestrator_tasks_owner_id", "orchestrator_tasks", ["owner_id"])
    op.create_index("ix_orchestrator_tasks_source_event_id", "orchestrator_tasks", ["source_event_id"])
    op.create_index("ix_orchestrator_tasks_tenant_status", "orchestrator_tasks", ["tenant_id", "status"])

    op.create_table(
        "orchestrator_decisions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False), sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("related_records", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_orchestrator_decision_dedupe"),
    )
    op.create_index("ix_orchestrator_decisions_tenant_id", "orchestrator_decisions", ["tenant_id"])
    op.create_index("ix_orchestrator_decisions_owner_id", "orchestrator_decisions", ["owner_id"])

    op.create_table(
        "inbox_notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dedupe_key", sa.String(160), nullable=False), sa.Column("category", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_agent", sa.String(60), nullable=False), sa.Column("priority", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("related_records", postgresql.JSONB()), sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "dedupe_key", name="uq_inbox_notification_dedupe"),
    )
    op.create_index("ix_inbox_notifications_tenant_id", "inbox_notifications", ["tenant_id"])
    op.create_index("ix_inbox_notifications_owner_id", "inbox_notifications", ["owner_id"])
    op.create_index("ix_inbox_tenant_created", "inbox_notifications", ["tenant_id", "created_at"])

    op.create_table(
        "daily_digests",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("digest_date", sa.Date(), nullable=False),
        sa.Column("summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "digest_date", name="uq_daily_digest_tenant_date"),
    )
    op.create_index("ix_daily_digests_tenant_id", "daily_digests", ["tenant_id"])
    op.create_index("ix_daily_digests_owner_id", "daily_digests", ["owner_id"])


def downgrade():
    for table in ("daily_digests", "inbox_notifications", "orchestrator_decisions", "orchestrator_tasks", "month_closes", "bank_reconciliation_matches"):
        op.drop_table(table)
