from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserSetting(Base):
    """Per-user preferences, one row per user. No row = defaults."""

    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    email_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    task_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    security_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    weekly_reports: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), default=False)
    session_timeout_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("30"), default=30)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
