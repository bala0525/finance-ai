"""Add notification inbox and verify existing accounts for legacy compatibility.

Revision ID: f4a1b8c2d6e0
Revises: f3c9a7d2b5e1
"""
from alembic import op
import sqlalchemy as sa

revision = "f4a1b8c2d6e0"
down_revision = "f3c9a7d2b5e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("supersedes_document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_documents_supersedes_document_id", "documents", ["supersedes_document_id"])
    op.add_column("payment_batches", sa.Column("payment_proof_bucket", sa.String(100), nullable=True))
    op.add_column("payment_batches", sa.Column("payment_proof_path", sa.String(1024), nullable=True))
    op.add_column("payment_batches", sa.Column("payment_proof_filename", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_payment_batches_payment_proof_path", "payment_batches", ["payment_proof_path"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_key", sa.String(80), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("link", sa.String(500), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "read_at"])
    # Existing accounts predate mandatory verification. Preserve their access;
    # all newly registered accounts must verify their email before login.
    op.execute("UPDATE users SET is_verified = TRUE WHERE is_verified = FALSE")


def downgrade():
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_tenant_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_documents_supersedes_document_id", table_name="documents")
    op.drop_column("documents", "supersedes_document_id")
    op.drop_constraint("uq_payment_batches_payment_proof_path", "payment_batches", type_="unique")
    op.drop_column("payment_batches", "payment_proof_filename")
    op.drop_column("payment_batches", "payment_proof_path")
    op.drop_column("payment_batches", "payment_proof_bucket")
