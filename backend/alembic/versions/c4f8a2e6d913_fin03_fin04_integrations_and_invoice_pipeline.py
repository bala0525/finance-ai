"""FIN-03 integration layer + FIN-04 invoice processing pipeline.

Revision ID: c4f8a2e6d913
Revises: b7e3d5a1c902
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c4f8a2e6d913"
down_revision = "b7e3d5a1c902"
branch_labels = None
depends_on = None

NEW_TABLES = ["confidence_thresholds", "extraction_corrections", "domain_events", "connections",
              "sync_runs", "sync_records", "bank_transactions"]

DOC_COLUMNS = [
    sa.Column("source_channel", sa.String(20), nullable=False, server_default="WEB"),
    sa.Column("source_ref", sa.String(255), nullable=True),
    sa.Column("source_sender", sa.String(255), nullable=True),
    sa.Column("pipeline_status", sa.String(20), nullable=False, server_default="NOT_RUN"),
    sa.Column("review_reasons", postgresql.JSONB(), nullable=True),
    sa.Column("validation_findings", postgresql.JSONB(), nullable=True),
    sa.Column("party_id", sa.Integer(), nullable=True),
    sa.Column("vendor_gstin", sa.String(15), nullable=True),
    sa.Column("vendor_pan", sa.String(10), nullable=True),
    sa.Column("buyer_gstin", sa.String(15), nullable=True),
    sa.Column("bank_last4", sa.String(4), nullable=True),
    sa.Column("bank_ifsc", sa.String(11), nullable=True),
    sa.Column("tax_breakup", postgresql.JSONB(), nullable=True),
    sa.Column("verified_fields", postgresql.JSONB(), nullable=True),
]


def _ts(name="created_at"):
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    for col in DOC_COLUMNS:
        op.add_column("documents", col)
    op.create_foreign_key("fk_documents_party_id", "documents", "parties", ["party_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_documents_source_channel", "documents", ["source_channel"])
    op.create_index("ix_documents_pipeline_status", "documents", ["pipeline_status"])

    op.create_table(
        "confidence_thresholds",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("agent", sa.String(40), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=True),
        sa.Column("overall", sa.Numeric(4, 3), nullable=False),
        sa.Column("field_min", sa.Numeric(4, 3), nullable=False),
        sa.Column("require_known_vendor", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_by", sa.Integer(), nullable=True),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_confidence_thresholds_tenant_id", "confidence_thresholds", ["tenant_id"])
    op.create_index("uq_conf_thr_tenant_agent", "confidence_thresholds", ["tenant_id", "agent"], unique=True,
                    postgresql_where=sa.text("party_id IS NULL"))
    op.create_index("uq_conf_thr_tenant_agent_party", "confidence_thresholds", ["tenant_id", "agent", "party_id"], unique=True,
                    postgresql_where=sa.text("party_id IS NOT NULL"))

    op.create_table(
        "extraction_corrections",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("vendor_name", sa.String(255), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("field", sa.String(40), nullable=False),
        sa.Column("original_value", sa.Text(), nullable=True),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("original_confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("corrected_by", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        _ts(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tenant_id", "document_id", "vendor_name"):
        op.create_index(f"ix_extraction_corrections_{col}", "extraction_corrections", [col])

    op.create_table(
        "domain_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        _ts(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tenant_id", "name", "created_at"):
        op.create_index(f"ix_domain_events_{col}", "domain_events", [col])

    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("credentials_enc", sa.Text(), nullable=True),
        sa.Column("intake_token", sa.String(64), nullable=True),
        sa.Column("cursor", postgresql.JSONB(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        _ts(), _ts("updated_at"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("intake_token", name="uq_connections_intake_token"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_connections_tenant_id", "connections", ["tenant_id"])
    op.create_index("ix_connections_provider", "connections", ["provider"])

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("window_start", sa.Date(), nullable=True),
        sa.Column("window_end", sa.Date(), nullable=True),
        sa.Column("counts", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=True),
        _ts("started_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_runs_tenant_id", "sync_runs", ["tenant_id"])
    op.create_index("ix_sync_runs_connection_id", "sync_runs", ["connection_id"])

    op.create_table(
        "sync_records",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("record_type", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("local_ref", postgresql.JSONB(), nullable=True),
        _ts("updated_at"),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("connection_id", "record_type", "external_id", name="uq_sync_records_external"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_records_connection_id", "sync_records", ["connection_id"])

    op.create_table(
        "bank_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=True),
        sa.Column("account_label", sa.String(100), nullable=False),
        sa.Column("txn_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("ref_no", sa.String(100), nullable=True),
        sa.Column("debit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("credit", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("balance", sa.Numeric(18, 2), nullable=True),
        sa.Column("external_id", sa.String(64), nullable=False),
        _ts(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["connection_id"], ["connections.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "external_id", name="uq_bank_txn_external"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tenant_id", "owner_id", "txn_date"):
        op.create_index(f"ix_bank_transactions_{col}", "bank_transactions", [col])

    for table in ("extraction_corrections", "domain_events"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION fin_forbid_mutation()"
        )
    for table in NEW_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    for table in ("domain_events", "extraction_corrections"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    for table in ("bank_transactions", "sync_records", "sync_runs", "connections", "domain_events",
                  "extraction_corrections", "confidence_thresholds"):
        op.drop_table(table)
    op.drop_index("ix_documents_pipeline_status", table_name="documents")
    op.drop_index("ix_documents_source_channel", table_name="documents")
    op.drop_constraint("fk_documents_party_id", "documents", type_="foreignkey")
    for col in reversed(DOC_COLUMNS):
        op.drop_column("documents", col.name)
