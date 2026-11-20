"""Add durable retry metadata to the domain event outbox."""
from alembic import op
import sqlalchemy as sa

revision = "b8d3f1a6c9e2"
down_revision = "a7c2e9d4b6f1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("domain_events", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("domain_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("domain_events", sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("domain_events", sa.Column("last_error", sa.Text(), nullable=True))
    op.create_index("ix_domain_events_next_attempt_at", "domain_events", ["next_attempt_at"])


def downgrade():
    op.drop_index("ix_domain_events_next_attempt_at", table_name="domain_events")
    op.drop_column("domain_events", "last_error")
    op.drop_column("domain_events", "processed_at")
    op.drop_column("domain_events", "next_attempt_at")
    op.drop_column("domain_events", "attempt_count")
