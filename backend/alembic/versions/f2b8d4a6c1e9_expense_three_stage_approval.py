"""Add explicit Finance User, Finance Manager and Administrator expense stages.

Revision ID: f2b8d4a6c1e9
Revises: f1a7c3d9e5b2
"""
from alembic import op
import sqlalchemy as sa

revision = "f2b8d4a6c1e9"
down_revision = "f1a7c3d9e5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("expense_decisions", sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("expense_decisions", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expense_decisions", sa.Column("manager_approved_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("expense_decisions", sa.Column("manager_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("expense_decisions", sa.Column("admin_decided_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True))
    op.add_column("expense_decisions", sa.Column("admin_decided_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("expense_decisions", "admin_decided_at")
    op.drop_column("expense_decisions", "admin_decided_by")
    op.drop_column("expense_decisions", "manager_approved_at")
    op.drop_column("expense_decisions", "manager_approved_by")
    op.drop_column("expense_decisions", "verified_at")
    op.drop_column("expense_decisions", "verified_by")
