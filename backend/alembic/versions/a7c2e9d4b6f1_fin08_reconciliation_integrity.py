"""Enforce one-to-one confirmed bank/journal reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "a7c2e9d4b6f1"
down_revision = "f9a8c7d6e5b4"
branch_labels = None
depends_on = None


def upgrade():
    # Repair any historical duplicate confirmed matches before enforcing the invariant.
    # Keep the earliest match; release later duplicates back to the unmatched queue.
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY journal_entry_id ORDER BY CASE WHEN status = 'MATCHED' THEN 0 ELSE 1 END, confirmed_at NULLS LAST, id) AS rn
            FROM bank_reconciliation_matches
            WHERE journal_entry_id IS NOT NULL
        )
        UPDATE bank_reconciliation_matches AS m
        SET journal_entry_id = NULL, status = 'UNMATCHED', confirmed_by = NULL, confirmed_at = NULL,
            suggestion_reason = 'Previous duplicate match was released during reconciliation integrity migration.'
        FROM ranked r
        WHERE m.id = r.id AND r.rn > 1
    """))
    op.create_unique_constraint(
        "uq_bank_recon_journal_entry", "bank_reconciliation_matches", ["journal_entry_id"]
    )


def downgrade():
    op.drop_constraint("uq_bank_recon_journal_entry", "bank_reconciliation_matches", type_="unique")
