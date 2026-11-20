"""Add Supabase Storage references to documents and reports.

Revision ID: d8f2a6c4b1e7
Revises: c3e9a1b7d5f4

Columns are nullable so legacy rows (files that lived on local disk) survive;
run scripts/migrate_local_uploads_to_supabase.py to backfill them.
"""

from alembic import op
import sqlalchemy as sa


revision = "d8f2a6c4b1e7"
down_revision = "c3e9a1b7d5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("documents", "reports"):
        op.add_column(table, sa.Column("storage_bucket", sa.String(length=100), nullable=True))
        op.add_column(table, sa.Column("storage_path", sa.String(length=1024), nullable=True))
        op.create_unique_constraint(f"uq_{table}_storage_path", table, ["storage_path"])


def downgrade() -> None:
    for table in ("documents", "reports"):
        op.drop_constraint(f"uq_{table}_storage_path", table, type_="unique")
        op.drop_column(table, "storage_path")
        op.drop_column(table, "storage_bucket")
