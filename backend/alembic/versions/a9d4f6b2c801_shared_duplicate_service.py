"""Shared duplicate service columns on documents (FIN-05).

Revision ID: a9d4f6b2c801
Revises: e5a1c7b9d3f2

Hashes for existing rows are filled by scripts/backfill_duplicate_hashes.py.
"""

from alembic import op
import sqlalchemy as sa

revision = "a9d4f6b2c801"
down_revision = "e5a1c7b9d3f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("duplicate_hash", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("duplicate_of_id", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("duplicate_score", sa.Numeric(4, 3), nullable=True))
    op.add_column("documents", sa.Column("duplicate_match_type", sa.String(10), nullable=True))
    op.add_column(
        "documents",
        sa.Column("duplicate_overridden", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_foreign_key(
        "fk_documents_duplicate_of_id", "documents", "documents",
        ["duplicate_of_id"], ["id"], ondelete="SET NULL",
    )
    op.create_index("ix_documents_duplicate_hash", "documents", ["duplicate_hash"])


def downgrade() -> None:
    op.drop_index("ix_documents_duplicate_hash", table_name="documents")
    op.drop_constraint("fk_documents_duplicate_of_id", "documents", type_="foreignkey")
    for col in ("duplicate_overridden", "duplicate_match_type", "duplicate_score",
                "duplicate_of_id", "duplicate_hash"):
        op.drop_column("documents", col)
