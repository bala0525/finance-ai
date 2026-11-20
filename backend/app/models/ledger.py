from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    Boolean,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LedgerAccount(Base):
    """Chart of accounts entry (per user)."""

    __tablename__ = "ledger_accounts"
    __table_args__ = (
        UniqueConstraint("owner_id", "code", name="uq_ledger_accounts_owner_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    normal_balance: Mapped[str] = mapped_column(String(6), nullable=False, default="DEBIT", server_default="DEBIT")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    parent_code: Mapped[str | None] = mapped_column(String(30), nullable=True)


class JournalLine(Base):
    """One debit-or-credit line of a balanced voucher."""

    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    voucher_no: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    account_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    narration: Mapped[str | None] = mapped_column(String(500), nullable=True)
    debit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    credit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    tenant_id: Mapped[int | None] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # NEW: direct reference to the original invoice/receipt stored in Supabase.
    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_reversal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reversed_voucher_no: Mapped[str | None] = mapped_column(String(60), nullable=True)


class PartyInvoice(Base):
    """Sales invoice (receivable) or purchase bill (payable) with paid amount."""

    __tablename__ = "party_invoices"
    __table_args__ = (
        UniqueConstraint(
            "owner_id", "invoice_type", "invoice_no", name="uq_party_invoices_owner_type_no"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_type: Mapped[str] = mapped_column(String(10), nullable=False)  # SALES / PURCHASE
    invoice_no: Mapped[str] = mapped_column(String(60), nullable=False)
    party_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    gst_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0"), server_default="0"
    )


class LedgerImport(Base):
    """Audit record of each ledger workbook import."""

    __tablename__ = "ledger_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    account_count: Mapped[int] = mapped_column(Integer, nullable=False)
    journal_line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    invoice_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LedgerPeriodClose(Base):
    """Accounting period lock; closed periods reject new journal postings."""
    __tablename__ = "ledger_period_closes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "period_start", "period_end", name="uq_ledger_period_close"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="CLOSED", server_default="CLOSED")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
