from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InvoiceRecord(Base):
    """An individual invoice extracted from an uploaded document or register."""

    __tablename__ = "invoice_records"
    __table_args__ = (
        UniqueConstraint(
            "source_document_id",
            "row_number",
            name="uq_invoice_records_source_row",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    source_document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    invoice_number: Mapped[str | None] = mapped_column(String(150))
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)

    po_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    payment_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UNKNOWN", server_default="UNKNOWN"
    )
    validation_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NOT_RUN", server_default="NOT_RUN"
    )
    validation_errors: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    flags: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )

    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="NOT_READY", server_default="NOT_READY"
    )
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    source_document = relationship("Document")
    owner = relationship("User", foreign_keys=[owner_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
