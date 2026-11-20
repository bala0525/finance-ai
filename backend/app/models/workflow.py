"""Tables backing the advanced AI-employee workflows.

payment batches (AP), collection reminders / dispute cases (AR),
workflow resolutions (AP exceptions + reconciliation exceptions),
expense policies / decisions (Expense), report schedules (Financial Reporting).
"""

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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PaymentBatch(Base):
    __tablename__ = "payment_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", server_default="DRAFT"
    )  # DRAFT | PAID
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=Decimal("0")
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    transfer_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    transfer_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_proof_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payment_proof_bucket: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_proof_path: Mapped[str | None] = mapped_column(String(1024), nullable=True, unique=True)
    payment_proof_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submitted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PaymentBatchItem(Base):
    __tablename__ = "payment_batch_items"
    __table_args__ = (
        # An invoice can sit in only one batch at a time.
        UniqueConstraint("document_id", name="uq_payment_batch_item_document"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("payment_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)


class WorkflowResolution(Base):
    """Human resolution of a computed exception (AP exception / recon item)."""

    __tablename__ = "workflow_resolutions"
    __table_args__ = (
        UniqueConstraint("scope", "document_id", "item_key", name="uq_workflow_resolution"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(30), nullable=False)  # AP_EXCEPTION | RECON_ITEM
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    item_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # RESOLVED | WRITTEN_OFF
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DisputeCase(Base):
    __tablename__ = "dispute_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="OPEN", server_default="OPEN"
    )  # OPEN | IN_REVIEW | RESOLVED
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class CollectionReminder(Base):
    __tablename__ = "collection_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage: Mapped[str] = mapped_column(String(30), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    ai_generated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="DRAFT", server_default="DRAFT"
    )  # DRAFT | MARKED_SENT
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExpensePolicy(Base):
    """Organisation-wide expense policy per expense type."""

    __tablename__ = "expense_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    expense_type: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    claim_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    receipt_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExpenseDecision(Base):
    __tablename__ = "expense_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # APPROVED | PARTIAL | REJECTED
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manager_approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    manager_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    admin_decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    admin_decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReportSchedule(Base):
    __tablename__ = "report_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    report_type: Mapped[str] = mapped_column(String(40), nullable=False)  # DOCUMENT_SUMMARY | FINANCIAL_STATEMENTS
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)  # WEEKLY | MONTHLY | QUARTERLY
    next_run: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )  # ACTIVE | PAUSED
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_report_id: Mapped[int | None] = mapped_column(
        ForeignKey("reports.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
