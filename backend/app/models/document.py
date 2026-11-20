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
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supersedes_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    stored_filename: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )

    content_type: Mapped[str | None] = mapped_column(
        String(150), nullable=True
    )

    # Supabase Storage object holding the file bytes (source of truth).
    # NULL only for legacy rows created before the Storage migration.
    storage_bucket: Mapped[str | None] = mapped_column(String(100), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(
        String(1024), nullable=True, unique=True
    )

    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    category: Mapped[str] = mapped_column(
        String(100),
        default="Uncategorized",
        server_default="Uncategorized",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="PENDING",
        server_default="PENDING",
        nullable=False,
    )

    # Invoice extraction fields; null until extraction succeeds.
    vendor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(150), nullable=True)
    invoice_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # Expanded extracted invoice structure; null/empty means fields were not detected.
    extracted_invoice_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    line_items: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    validation_status: Mapped[str] = mapped_column(
        String(30),
        default="NOT_RUN",
        server_default="NOT_RUN",
        nullable=False,
    )
    validation_errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    is_duplicate: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    # Shared duplicate-detection fields introduced by FIN-05 migration.
    duplicate_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    duplicate_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    duplicate_match_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duplicate_overridden: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)

    review_status: Mapped[str] = mapped_column(
        String(30),
        default="NOT_READY",
        server_default="NOT_READY",
        nullable=False,
    )

    # NEW: role-routed workflow and payment audit fields. owner_id remains the uploader.
    uploader_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    assigned_finance_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    first_reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    first_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_review_action: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # NEW: explicit audit columns required for approval, rejection and verification reporting.
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chief_accountant_approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    chief_accountant_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ledger_voucher_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Extraction confidence (0-1) and per-field breakdown; null until extraction runs.
    extraction_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    field_confidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # GL coding suggestion (account must exist in the user's chart of accounts).
    suggested_account_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    suggested_account_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    coding_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    coding_source: Mapped[str | None] = mapped_column(String(20), nullable=True)  # KEYWORD | AI
    account_code: Mapped[str | None] = mapped_column(String(30), nullable=True)  # accepted / chosen
    coding_status: Mapped[str] = mapped_column(
        String(20), default="NONE", server_default="NONE", nullable=False
    )  # NONE | SUGGESTED | ACCEPTED | CHANGED


    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    owner = relationship("User", foreign_keys=[owner_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    assigned_finance_user = relationship("User", foreign_keys=[assigned_finance_user_id])
    first_reviewer = relationship("User", foreign_keys=[first_reviewed_by])
    verifier = relationship("User", foreign_keys=[verified_by])
    approver = relationship("User", foreign_keys=[approved_by])
    rejector = relationship("User", foreign_keys=[rejected_by])
    chief_accountant_approver = relationship("User", foreign_keys=[chief_accountant_approved_by])
    payer = relationship("User", foreign_keys=[paid_by])
