"""FIN-01 platform foundation + FIN-02 ledger and master data.

Revision ID: b7e3d5a1c902
Revises: a9d4f6b2c801

FIN-01: tenants, users.tenant_id, append-only audit_events, append-only consent_log.
FIN-02: journal_entries (+ balanced / append-only enforcement in the database), parties,
        insert-only party_bank_details, party_alerts.
Existing users are all placed in one "Default organisation" tenant, which keeps today's
behaviour (one company per deployment) until more tenants are created.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7e3d5a1c902"
down_revision = "a9d4f6b2c801"
branch_labels = None
depends_on = None

NEW_TABLES = [
    "tenants", "audit_events", "consent_log", "journal_entries",
    "parties", "party_bank_details", "party_alerts",
]

FUNCTIONS = """
CREATE OR REPLACE FUNCTION fin_forbid_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION '% on % is not allowed: this table is append-only', TG_OP, TG_TABLE_NAME
    USING ERRCODE = 'integrity_constraint_violation';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fin_forbid_posted_line_mutation() RETURNS trigger AS $$
BEGIN
  IF OLD.entry_id IS NOT NULL THEN
    RAISE EXCEPTION '% on a posted journal line is not allowed: post a reversing entry instead', TG_OP
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION fin_check_entry_balanced() RETURNS trigger AS $$
DECLARE d numeric; c numeric;
BEGIN
  IF NEW.entry_id IS NULL THEN RETURN NULL; END IF;
  SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0) INTO d, c
    FROM journal_lines WHERE entry_id = NEW.entry_id;
  IF d <> c THEN
    RAISE EXCEPTION 'journal entry % is not balanced (debit %, credit %)', NEW.entry_id, d, c
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    # ---------------------------------------------------------------- FIN-01
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute("INSERT INTO tenants (name) VALUES ('Default organisation')")
    op.add_column("users", sa.Column("tenant_id", sa.Integer(), nullable=True))
    op.execute("UPDATE users SET tenant_id = (SELECT MIN(id) FROM tenants)")
    op.alter_column("users", "tenant_id", nullable=False)
    op.create_foreign_key("fk_users_tenant_id", "users", "tenants", ["tenant_id"], ["id"])
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("actor_type", sa.String(10), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(60), nullable=True),
        sa.Column("before", postgresql.JSONB(), nullable=True),
        sa.Column("after", postgresql.JSONB(), nullable=True),
        sa.Column("source_document_id", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(10), nullable=False, server_default="ALLOWED"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tenant_id", "actor_id", "action", "source_document_id", "created_at"):
        op.create_index(f"ix_audit_events_{col}", "audit_events", [col])

    op.create_table(
        "consent_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("scope", sa.String(255), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_log_tenant_id", "consent_log", ["tenant_id"])
    op.create_index("ix_consent_log_user_id", "consent_log", ["user_id"])

    # ---------------------------------------------------------------- FIN-02
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("voucher_no", sa.String(60), nullable=False),
        sa.Column("narration", sa.String(500), nullable=True),
        sa.Column("source_document_id", sa.Integer(), nullable=False),
        sa.Column("posted_by_type", sa.String(10), nullable=False),
        sa.Column("posted_by_id", sa.Integer(), nullable=False),
        sa.Column("approval_id", sa.Integer(), nullable=False),
        sa.Column("is_reversal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("reverses_entry_id", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("fx_rate", sa.Numeric(18, 8), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reverses_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("reverses_entry_id", name="uq_journal_entries_reverses"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("tenant_id", "owner_id", "voucher_no", "source_document_id"):
        op.create_index(f"ix_journal_entries_{col}", "journal_entries", [col])

    op.add_column("journal_lines", sa.Column("entry_id", sa.Integer(), nullable=True))
    op.add_column("journal_lines", sa.Column("debit_fc", sa.Numeric(18, 2), nullable=True))
    op.add_column("journal_lines", sa.Column("credit_fc", sa.Numeric(18, 2), nullable=True))
    op.create_foreign_key(
        "fk_journal_lines_entry_id", "journal_lines", "journal_entries", ["entry_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_journal_lines_entry_id", "journal_lines", ["entry_id"])
    op.create_check_constraint(
        "ck_journal_lines_posted_amounts", "journal_lines",
        "entry_id IS NULL OR (debit >= 0 AND credit >= 0 AND (debit = 0 OR credit = 0) AND (debit + credit) > 0)",
    )

    op.create_table(
        "parties",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("party_type", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("pan", sa.String(10), nullable=True),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("is_msme", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("udyam_number", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_parties_tenant_id", "parties", ["tenant_id"])
    op.create_index("ix_parties_owner_id", "parties", ["owner_id"])
    op.create_index(
        "uq_parties_tenant_gstin", "parties", ["tenant_id", "gstin"], unique=True,
        postgresql_where=sa.text("gstin IS NOT NULL"),
    )

    op.create_table(
        "party_bank_details",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("account_holder", sa.String(255), nullable=False),
        sa.Column("account_number_enc", sa.Text(), nullable=False),
        sa.Column("account_last4", sa.String(4), nullable=False),
        sa.Column("ifsc", sa.String(11), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=True),
        sa.Column("changed_by", sa.Integer(), nullable=False),
        sa.Column("change_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_party_bank_details_party_id", "party_bank_details", ["party_id"])

    op.create_table(
        "party_alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("party_id", sa.Integer(), nullable=False),
        sa.Column("alert_type", sa.String(40), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="OPEN"),
        sa.Column("acknowledged_by", sa.Integer(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["party_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_party_alerts_tenant_id", "party_alerts", ["tenant_id"])
    op.create_index("ix_party_alerts_party_id", "party_alerts", ["party_id"])

    # --------------------------------------------- append-only / balance enforcement
    op.execute(FUNCTIONS)
    for table in ("audit_events", "consent_log", "journal_entries", "party_bank_details"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION fin_forbid_mutation()"
        )
    op.execute(
        "CREATE TRIGGER trg_journal_lines_posted_immutable BEFORE UPDATE OR DELETE ON journal_lines "
        "FOR EACH ROW EXECUTE FUNCTION fin_forbid_posted_line_mutation()"
    )
    op.execute(
        "CREATE CONSTRAINT TRIGGER trg_journal_lines_balanced AFTER INSERT ON journal_lines "
        "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION fin_check_entry_balanced()"
    )

    for table in NEW_TABLES:
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_journal_lines_balanced ON journal_lines")
    op.execute("DROP TRIGGER IF EXISTS trg_journal_lines_posted_immutable ON journal_lines")
    for table in ("party_bank_details", "journal_entries", "consent_log", "audit_events"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_append_only ON {table}")
    op.drop_table("party_alerts")
    op.drop_table("party_bank_details")
    op.drop_table("parties")
    op.drop_constraint("ck_journal_lines_posted_amounts", "journal_lines", type_="check")
    op.drop_index("ix_journal_lines_entry_id", table_name="journal_lines")
    op.drop_constraint("fk_journal_lines_entry_id", "journal_lines", type_="foreignkey")
    for col in ("credit_fc", "debit_fc", "entry_id"):
        op.drop_column("journal_lines", col)
    op.drop_table("journal_entries")
    op.drop_table("consent_log")
    op.drop_table("audit_events")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_constraint("fk_users_tenant_id", "users", type_="foreignkey")
    op.drop_column("users", "tenant_id")
    op.drop_table("tenants")
    op.execute("DROP FUNCTION IF EXISTS fin_check_entry_balanced()")
    op.execute("DROP FUNCTION IF EXISTS fin_forbid_posted_line_mutation()")
    op.execute("DROP FUNCTION IF EXISTS fin_forbid_mutation()")
