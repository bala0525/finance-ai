"""Add structured invoice details and line-item JSON storage.

Revision ID: j1k2l3m4n5o6
Revises: i9j0k1l2m3n4
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "j1k2l3m4n5o6"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("extracted_invoice_details", postgresql.JSONB(), nullable=True))
    op.add_column("documents", sa.Column("line_items", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "line_items")
    op.drop_column("documents", "extracted_invoice_details")
