"""Add reconciliation run storage."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e71c4a8b2d90"
down_revision = "d4a6b8c2e910"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "summary",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "results",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_reconciliation_runs_document_id",
        "reconciliation_runs",
        ["document_id"],
    )
    op.create_index(
        "ix_reconciliation_runs_owner_id",
        "reconciliation_runs",
        ["owner_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reconciliation_runs_owner_id",
        table_name="reconciliation_runs",
    )
    op.drop_index(
        "ix_reconciliation_runs_document_id",
        table_name="reconciliation_runs",
    )
    op.drop_table("reconciliation_runs")
