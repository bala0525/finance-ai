from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="Financial Report",
        server_default="Financial Report",
    )

    period: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    format: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="Not generated",
        server_default="Not generated",
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="REQUESTED",
        server_default="REQUESTED",
    )

    stored_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, unique=True
    )
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    owner = relationship("User")
