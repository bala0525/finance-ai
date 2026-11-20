"""Add Chief Accountant authorization to AP payment batches."""

from alembic import op
import sqlalchemy as sa

revision = "c9e4a7b2d610"
down_revision = "b8d3f1a6c9e2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payment_batches",
        sa.Column("submitted_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_batches_submitted_by_users",
        "payment_batches", "users",
        ["submitted_by"], ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "payment_batches",
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        "payment_batches",
        sa.Column("approved_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_batches_approved_by_users",
        "payment_batches", "users",
        ["approved_by"], ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "payment_batches",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payment_batches",
        sa.Column("approval_note", sa.Text(), nullable=True),
    )

    op.add_column(
        "payment_batches",
        sa.Column("rejected_by", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_batches_rejected_by_users",
        "payment_batches", "users",
        ["rejected_by"], ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "payment_batches",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "payment_batches",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_constraint(
        "fk_payment_batches_rejected_by_users",
        "payment_batches", type_="foreignkey",
    )
    op.drop_constraint(
        "fk_payment_batches_approved_by_users",
        "payment_batches", type_="foreignkey",
    )
    op.drop_constraint(
        "fk_payment_batches_submitted_by_users",
        "payment_batches", type_="foreignkey",
    )

    op.drop_column("payment_batches", "rejection_reason")
    op.drop_column("payment_batches", "rejected_at")
    op.drop_column("payment_batches", "rejected_by")
    op.drop_column("payment_batches", "approval_note")
    op.drop_column("payment_batches", "approved_at")
    op.drop_column("payment_batches", "approved_by")
    op.drop_column("payment_batches", "submitted_at")
    op.drop_column("payment_batches", "submitted_by")
