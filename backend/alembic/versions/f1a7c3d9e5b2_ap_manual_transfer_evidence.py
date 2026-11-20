"""Persist manual AP bank transfer evidence.

Revision ID: f1a7c3d9e5b2
Revises: e2f6a9c1b4d8
"""
from alembic import op
import sqlalchemy as sa

revision = "f1a7c3d9e5b2"
down_revision = "e2f6a9c1b4d8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment_batches", sa.Column("transfer_reference", sa.String(120), nullable=True))
    op.add_column("payment_batches", sa.Column("bank_name", sa.String(120), nullable=True))
    op.add_column("payment_batches", sa.Column("transfer_date", sa.Date(), nullable=True))
    op.add_column("payment_batches", sa.Column("payment_proof_reference", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("payment_batches", "payment_proof_reference")
    op.drop_column("payment_batches", "transfer_date")
    op.drop_column("payment_batches", "bank_name")
    op.drop_column("payment_batches", "transfer_reference")
