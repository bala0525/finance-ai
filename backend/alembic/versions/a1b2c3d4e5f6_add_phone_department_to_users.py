"""Add phone and department columns to users table."""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "a7c2e9f14b63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("phone", sa.String(30), nullable=True))
    op.add_column("users", sa.Column("department", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "department")
    op.drop_column("users", "phone")
