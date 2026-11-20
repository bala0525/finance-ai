"""Add user_profiles and user_settings; enable Row Level Security.

Revision ID: c3e9a1b7d5f4
Revises: b5d1e8a3c7f2

RLS note: this app authenticates with its own JWT (not Supabase Auth) and the
FastAPI backend connects as the database owner, which bypasses RLS. Enabling
RLS with NO policies therefore blocks all direct access through Supabase's
public REST/GraphQL API (anon / authenticated roles) while the backend keeps
working. Per-user ownership is enforced in the API layer.
"""

from alembic import op
import sqlalchemy as sa

revision = "c3e9a1b7d5f4"
down_revision = "b5d1e8a3c7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("job_title", sa.String(100), nullable=True),
        sa.Column("location", sa.String(100), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "user_settings",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("email_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("task_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("security_alerts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("weekly_reports", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("session_timeout_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("session_timeout_minutes IN (15, 30, 60, 120, 480)", name="ck_user_settings_timeout"),
    )

    bind = op.get_bind()
    for table in sa.inspect(bind).get_table_names(schema="public"):
        op.execute(sa.text(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade() -> None:
    op.drop_table("user_settings")
    op.drop_table("user_profiles")
