"""Shared, idempotent journal posting helpers for finance workflows."""
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ledger import JournalLine, LedgerAccount, LedgerPeriodClose
from app.models.user import User


def _tenant_id(db: Session, owner_id: int) -> int | None:
    user = db.get(User, owner_id)
    return user.tenant_id if user else None


def _assert_period_open(db: Session, owner_id: int, entry_date) -> int | None:
    tenant_id = _tenant_id(db, owner_id)
    if tenant_id is not None:
        closed = db.scalar(select(LedgerPeriodClose).where(
            LedgerPeriodClose.tenant_id == tenant_id,
            LedgerPeriodClose.status == "CLOSED",
            LedgerPeriodClose.period_start <= entry_date,
            LedgerPeriodClose.period_end >= entry_date,
        ))
        if closed:
            raise HTTPException(status_code=423, detail=f"Accounting period {closed.period_start} to {closed.period_end} is closed.")
    return tenant_id


def ensure_default_accounts(db: Session, owner_id: int, tenant_id: int | None = None) -> None:
    existing = {a.code for a in db.scalars(select(LedgerAccount).where(LedgerAccount.owner_id == owner_id)).all()}
    defaults = [
        ("1000", "Cash and Bank", "ASSET", "DEBIT"),
        ("1100", "Accounts Receivable", "ASSET", "DEBIT"),
        ("2000", "Accounts Payable", "LIABILITY", "CREDIT"),
        ("2100", "GST Payable", "LIABILITY", "CREDIT"),
        ("3000", "Owner Equity", "EQUITY", "CREDIT"),
        ("4000", "Sales Revenue", "INCOME", "CREDIT"),
        ("5000", "Operating Expenses", "EXPENSE", "DEBIT"),
    ]
    for code, name, kind, normal in defaults:
        if code not in existing:
            db.add(LedgerAccount(owner_id=owner_id, tenant_id=tenant_id or _tenant_id(db, owner_id),
                                 code=code, name=name, account_type=kind, normal_balance=normal, is_active=True))


def _find_account(db: Session, owner_id: int, account_type: str, terms: tuple[str, ...]) -> LedgerAccount:
    rows = db.scalars(select(LedgerAccount).where(LedgerAccount.owner_id == owner_id, LedgerAccount.is_active.is_(True))).all()
    candidates = [a for a in rows if (a.account_type or "").strip().upper() == account_type]
    match = next((a for a in candidates if any(t in a.name.lower() for t in terms)), None)
    if not match:
        raise HTTPException(status_code=422, detail=f"Configure a {account_type.lower()} ledger account matching {', '.join(terms)} before posting.")
    return match


def _existing_voucher(db: Session, owner_id: int, voucher: str, amount: Decimal) -> bool:
    existing = db.scalars(select(JournalLine).where(JournalLine.owner_id == owner_id, JournalLine.voucher_no == voucher)).all()
    if not existing:
        return False
    debit = sum((Decimal(str(x.debit)) for x in existing), Decimal("0"))
    credit = sum((Decimal(str(x.credit)) for x in existing), Decimal("0"))
    if debit == credit == amount:
        return True
    raise HTTPException(status_code=409, detail=f"An inconsistent journal already exists for {voucher}.")


def post_ap_payment(db: Session, owner_id: int, document_id: int, entry_date, amount: Decimal, vendor: str | None) -> str:
    tenant_id = _assert_period_open(db, owner_id, entry_date)
    voucher = f"AP-PAY-{document_id}"
    if _existing_voucher(db, owner_id, voucher, amount):
        return voucher
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Payment amount must be greater than zero.")
    ensure_default_accounts(db, owner_id, tenant_id)
    db.flush()
    payable = _find_account(db, owner_id, "LIABILITY", ("accounts payable", "trade payable", "sundry creditor"))
    bank = _find_account(db, owner_id, "ASSET", ("bank", "cash"))
    narration = f"Supplier payment - {vendor or 'Vendor'} - document {document_id}"[:500]
    db.add_all([
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="AP_PAYMENT", source_id=str(document_id), source_document_id=document_id, entry_date=entry_date, voucher_no=voucher, account_code=payable.code, narration=narration, debit=amount, credit=Decimal("0.00")),
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="AP_PAYMENT", source_id=str(document_id), source_document_id=document_id, entry_date=entry_date, voucher_no=voucher, account_code=bank.code, narration=narration, debit=Decimal("0.00"), credit=amount),
    ])
    return voucher


def post_ar_invoice_recognition(db: Session, owner_id: int, tenant_id: int | None, invoice_id: int,
                                entry_date, subtotal: Decimal, gst_amount: Decimal, customer: str | None) -> str:
    _assert_period_open(db, owner_id, entry_date)
    voucher = f"AR-INVOICE-{invoice_id}"
    total = subtotal + gst_amount
    if _existing_voucher(db, owner_id, voucher, total):
        return voucher
    ensure_default_accounts(db, owner_id, tenant_id)
    db.flush()
    receivable = _find_account(db, owner_id, "ASSET", ("accounts receivable", "trade receivable"))
    revenue = _find_account(db, owner_id, "INCOME", ("sales revenue", "revenue"))
    gst = _find_account(db, owner_id, "LIABILITY", ("gst payable",))
    narration = f"Sales invoice recognition - {customer or 'Customer'} - invoice {invoice_id}"[:500]
    rows = [
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="AR_INVOICE", source_id=f"AR-SALES-INVOICE-{invoice_id}", entry_date=entry_date, voucher_no=voucher, account_code=receivable.code, narration=narration, debit=total, credit=Decimal("0.00")),
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="AR_INVOICE", source_id=f"AR-SALES-INVOICE-{invoice_id}", entry_date=entry_date, voucher_no=voucher, account_code=revenue.code, narration=narration, debit=Decimal("0.00"), credit=subtotal),
    ]
    if gst_amount > 0:
        rows.append(JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="AR_INVOICE", source_id=f"AR-SALES-INVOICE-{invoice_id}", entry_date=entry_date, voucher_no=voucher, account_code=gst.code, narration=narration, debit=Decimal("0.00"), credit=gst_amount))
    db.add_all(rows)
    return voucher


def post_ar_collection(db: Session, owner_id: int, document_id: int, entry_date, amount: Decimal,
                       customer: str | None, reference: str | None = None) -> str:
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Collection amount must be greater than zero.")
    tenant_id = _assert_period_open(db, owner_id, entry_date)
    voucher = f"AR-COLLECT-{document_id}-{reference}" if reference else f"AR-COLLECT-{document_id}"
    if _existing_voucher(db, owner_id, voucher, amount):
        return voucher
    ensure_default_accounts(db, owner_id, tenant_id)
    db.flush()
    bank = _find_account(db, owner_id, "ASSET", ("bank", "cash"))
    receivable = _find_account(db, owner_id, "ASSET", ("accounts receivable", "trade receivable"))
    narration = f"Customer collection - {customer or 'Customer'} - document {document_id}"[:500]
    db.add_all([
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="AR_COLLECTION", source_id=str(reference or document_id), entry_date=entry_date, voucher_no=voucher, account_code=bank.code, narration=narration, debit=amount, credit=Decimal("0.00")),
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="AR_COLLECTION", source_id=str(reference or document_id), entry_date=entry_date, voucher_no=voucher, account_code=receivable.code, narration=narration, debit=Decimal("0.00"), credit=amount),
    ])
    return voucher


def post_expense_reimbursement(db: Session, owner_id: int, document_id: int, entry_date, amount: Decimal, expense_code: str | None, claimant: str | None) -> str:
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Reimbursement amount must be greater than zero.")
    tenant_id = _assert_period_open(db, owner_id, entry_date)
    voucher = f"EXP-REIMB-{document_id}"
    if _existing_voucher(db, owner_id, voucher, amount):
        return voucher
    ensure_default_accounts(db, owner_id, tenant_id)
    db.flush()
    expense = db.scalar(select(LedgerAccount).where(LedgerAccount.owner_id == owner_id, LedgerAccount.code == expense_code, LedgerAccount.is_active.is_(True))) if expense_code else None
    if expense is None or (expense.account_type or "").upper() != "EXPENSE":
        raise HTTPException(status_code=422, detail="Choose a valid Expense account in the Chart of Accounts before reimbursement.")
    bank = _find_account(db, owner_id, "ASSET", ("bank", "cash"))
    narration = f"Expense reimbursement - {claimant or 'Employee'} - document {document_id}"[:500]
    db.add_all([
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="EXPENSE_REIMBURSEMENT", source_id=str(document_id), source_document_id=document_id, entry_date=entry_date, voucher_no=voucher, account_code=expense.code, narration=narration, debit=amount, credit=Decimal("0.00")),
        JournalLine(owner_id=owner_id, tenant_id=tenant_id, created_by=owner_id, source_type="EXPENSE_REIMBURSEMENT", source_id=str(document_id), source_document_id=document_id, entry_date=entry_date, voucher_no=voucher, account_code=bank.code, narration=narration, debit=Decimal("0.00"), credit=amount),
    ])
    return voucher
