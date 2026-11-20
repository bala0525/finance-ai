from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SalesInvoice(Base):
    """Customer invoice with an explicit Finance Manager -> Administrator approval path."""
    __tablename__ = "sales_invoices"
    __table_args__ = (UniqueConstraint("tenant_id", "invoice_number", name="uq_sales_invoice_tenant_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_gstin: Mapped[str | None] = mapped_column(String(20))
    invoice_number: Mapped[str | None] = mapped_column(String(60))
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0.00"), server_default="0")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT", server_default="DRAFT", index=True)
    manager_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    manager_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admin_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    admin_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))  # NEW: E3 rejection actor.
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # NEW: E3 rejection timestamp.
    email_status: Mapped[str] = mapped_column(String(20), nullable=False, default="NOT_SENT", server_default="NOT_SENT")
    emailed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    lines: Mapped[list["SalesInvoiceLine"]] = relationship(back_populates="invoice", cascade="all, delete-orphan")


class SalesInvoiceLine(Base):
    __tablename__ = "sales_invoice_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    invoice: Mapped[SalesInvoice] = relationship(back_populates="lines")


class StripePayment(Base):
    __tablename__ = "stripe_payments"
    __table_args__ = (
        UniqueConstraint("checkout_session_id", name="uq_stripe_payment_checkout_session"),
        UniqueConstraint("stripe_event_id", name="uq_stripe_payment_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    checkout_session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    stripe_event_id: Mapped[str | None] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", server_default="PENDING")
    payer_email: Mapped[str | None] = mapped_column(String(255))  # NEW: E3 customer payer identity snapshot.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SalesInvoiceEvent(Base):
    """Append-only audit history for AR invoice state changes."""
    __tablename__ = "sales_invoice_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StripeRefund(Base):
    __tablename__ = "stripe_refunds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("sales_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_payment_id: Mapped[int] = mapped_column(ForeignKey("stripe_payments.id", ondelete="RESTRICT"), nullable=False)
    stripe_refund_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="PENDING", server_default="PENDING")
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
