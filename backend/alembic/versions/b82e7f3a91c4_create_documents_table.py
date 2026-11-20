"""Create documents table.

Revision ID: b82e7f3a91c4
Revises: 0407c030a7ed
"""

from alembic import op
import sqlalchemy as sa


revision = "b82e7f3a91c4"
down_revision = "0407c030a7ed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=150), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "category",
            sa.String(length=100),
            server_default="Uncategorized",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stored_filename"),
    )
    op.create_index(
        "ix_documents_owner_id",
        "documents",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_documents_owner_id", table_name="documents")
    op.drop_table("documents")
