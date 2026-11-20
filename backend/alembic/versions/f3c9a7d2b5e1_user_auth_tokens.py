"""Add single-use password reset tokens.

Revision ID: f3c9a7d2b5e1
Revises: f2b8d4a6c1e9
"""
from alembic import op
import sqlalchemy as sa

revision = "f3c9a7d2b5e1"
down_revision = "f2b8d4a6c1e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_auth_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_user_auth_tokens_hash"),
    )
    op.create_index("ix_user_auth_tokens_user_id", "user_auth_tokens", ["user_id"])
    op.create_index("ix_user_auth_tokens_purpose", "user_auth_tokens", ["purpose"])
    op.create_index("ix_user_auth_tokens_token_hash", "user_auth_tokens", ["token_hash"])


def downgrade():
    op.drop_index("ix_user_auth_tokens_token_hash", table_name="user_auth_tokens")
    op.drop_index("ix_user_auth_tokens_purpose", table_name="user_auth_tokens")
    op.drop_index("ix_user_auth_tokens_user_id", table_name="user_auth_tokens")
    op.drop_table("user_auth_tokens")
