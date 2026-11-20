"""Create reports table.

Revision ID: c91a5d2e7f40
Revises: b82e7f3a91c4
"""

from alembic import op
import sqlalchemy as sa


revision = "c91a5d2e7f40"
down_revision = "b82e7f3a91c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column(
            "id",
            sa.Integer(),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "category",
            sa.String(length=100),
            server_default="Financial Report",
            nullable=False,
        ),
        sa.Column("period", sa.String(length=100), nullable=True),
        sa.Column(
            "format",
            sa.String(length=30),
            server_default="Not generated",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            server_default="REQUESTED",
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
    )

    op.create_index(
        "ix_reports_owner_id",
        "reports",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_reports_owner_id", table_name="reports")
    op.drop_table("reports")
