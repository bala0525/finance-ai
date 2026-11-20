"""Tenant-scoped General Ledger, Chart of Accounts and financial statements."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_roles
from app.models.ledger import LedgerAccount, JournalLine, LedgerPeriodClose
from app.models.user import User
from app.services.posting import ensure_default_accounts, _assert_period_open
from app.services.accounting import validate_balanced_journal

router = APIRouter(prefix="/ledger", tags=["General Ledger"])
VIEW_ROLES = ("Finance User", "Finance Manager", "Chief Accountant", "Administrator")
POST_ROLES = ("Chief Accountant", "Administrator")


def _tenant_accounts(db: Session, user: User):
    stmt = select(LedgerAccount).where(LedgerAccount.tenant_id == user.tenant_id)
    if user.tenant_id is None:
        stmt = select(LedgerAccount).where(LedgerAccount.owner_id == user.id)
    rows = db.scalars(stmt.order_by(LedgerAccount.code, LedgerAccount.id)).all()
    # Multiple legacy users may own a copy of the same standard account code.
    by_code = {}
    for row in rows:
        by_code.setdefault(row.code, row)
    return list(by_code.values())


def _tenant_lines(db: Session, user: User, start: date | None = None, end: date | None = None):
    stmt = select(JournalLine).where(JournalLine.tenant_id == user.tenant_id)
    if user.tenant_id is None:
        stmt = select(JournalLine).where(JournalLine.owner_id == user.id)
    if start:
        stmt = stmt.where(JournalLine.entry_date >= start)
    if end:
        stmt = stmt.where(JournalLine.entry_date <= end)
    return db.scalars(stmt.order_by(JournalLine.entry_date, JournalLine.voucher_no, JournalLine.id)).all()


class AccountIn(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=255)
    account_type: Literal["ASSET", "LIABILITY", "EQUITY", "INCOME", "EXPENSE"]
    normal_balance: Literal["DEBIT", "CREDIT"] | None = None
    parent_code: str | None = Field(default=None, max_length=30)


class JournalLineIn(BaseModel):
    account_code: str = Field(min_length=1, max_length=30)
    debit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)
    credit: Decimal = Field(default=Decimal("0"), ge=0, max_digits=18, decimal_places=2)


class JournalIn(BaseModel):
    voucher_no: str = Field(min_length=2, max_length=60)
    entry_date: date
    narration: str = Field(min_length=2, max_length=500)
    lines: list[JournalLineIn] = Field(min_length=2, max_length=100)


class ClosePeriodIn(BaseModel):
    period_start: date
    period_end: date
    reason: str | None = Field(default=None, max_length=1000)


@router.post("/accounts/seed-defaults")
def seed_default_accounts(db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    ensure_default_accounts(db, user.id, user.tenant_id)
    db.commit()
    return {"created": True, "accounts": [{"code": a.code, "name": a.name} for a in _tenant_accounts(db, user)]}


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    accounts = _tenant_accounts(db, user)
    return {"accounts": [{
        "id": a.id, "code": a.code, "name": a.name, "accountType": a.account_type,
        "normalBalance": a.normal_balance, "active": a.is_active, "parentCode": a.parent_code,
    } for a in accounts]}


@router.post("/accounts", status_code=201)
def create_account(body: AccountIn, db: Session = Depends(get_db), user: User = Depends(require_roles("Chief Accountant", "Administrator"))):
    code = body.code.strip().upper()
    exists = db.scalar(select(LedgerAccount).where(LedgerAccount.tenant_id == user.tenant_id, LedgerAccount.code == code))
    if exists:
        raise HTTPException(status_code=409, detail="An account with this code already exists in this company.")
    normal = body.normal_balance or ("DEBIT" if body.account_type in {"ASSET", "EXPENSE"} else "CREDIT")
    row = LedgerAccount(owner_id=user.id, tenant_id=user.tenant_id, code=code, name=body.name.strip(),
                        account_type=body.account_type, normal_balance=normal, parent_code=body.parent_code, is_active=True)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "code": row.code, "name": row.name, "accountType": row.account_type, "normalBalance": row.normal_balance}


@router.get("/journals")
def list_journals(start: date | None = None, end: date | None = None,
                  db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="Start date must not be after end date.")
    rows = _tenant_lines(db, user, start, end)
    grouped = {}
    for row in rows:
        item = grouped.setdefault(row.voucher_no, {"voucherNo": row.voucher_no, "entryDate": row.entry_date.isoformat(),
            "narration": row.narration, "lines": [], "debit": Decimal("0"), "credit": Decimal("0")})
        item["lines"].append({"accountCode": row.account_code, "debit": str(row.debit), "credit": str(row.credit)})
        item["debit"] += Decimal(str(row.debit)); item["credit"] += Decimal(str(row.credit))
    return {"journals": [{**v, "debit": str(v["debit"]), "credit": str(v["credit"]),
                          "balanced": v["debit"] == v["credit"]} for v in grouped.values()]}


@router.post("/journals", status_code=201)
def create_journal(body: JournalIn, db: Session = Depends(get_db), user: User = Depends(require_roles(*POST_ROLES))):
    if body.entry_date > date.today():
        raise HTTPException(status_code=422, detail="Future-dated manual journals are not permitted.")
    try:
        debit, credit = validate_balanced_journal([{"debit": x.debit, "credit": x.credit} for x in body.lines])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _assert_period_open(db, user.id, body.entry_date)
    duplicate = db.scalar(select(JournalLine).where(JournalLine.tenant_id == user.tenant_id, JournalLine.voucher_no == body.voucher_no))
    if duplicate:
        raise HTTPException(status_code=409, detail="Voucher number already exists.")
    codes = {x.account_code for x in body.lines}
    accounts = db.scalars(select(LedgerAccount).where(LedgerAccount.tenant_id == user.tenant_id,
                                                       LedgerAccount.code.in_(codes), LedgerAccount.is_active.is_(True))).all()
    if {a.code for a in accounts} != codes:
        raise HTTPException(status_code=422, detail="One or more accounts do not exist or are inactive.")
    db.add_all([JournalLine(owner_id=user.id, tenant_id=user.tenant_id, created_by=user.id,
        source_type="MANUAL", source_id=body.voucher_no, entry_date=body.entry_date,
        voucher_no=body.voucher_no, account_code=line.account_code, narration=body.narration,
        debit=line.debit, credit=line.credit) for line in body.lines])
    db.commit()
    return {"voucherNo": body.voucher_no, "debit": str(debit), "credit": str(credit), "status": "POSTED"}


@router.post("/journals/{voucher_no}/reverse")
def reverse_journal(voucher_no: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*POST_ROLES))):
    original = db.scalars(select(JournalLine).where(JournalLine.tenant_id == user.tenant_id,
        JournalLine.voucher_no == voucher_no).order_by(JournalLine.id)).all()
    if not original:
        raise HTTPException(status_code=404, detail="Journal voucher not found.")
    if any(x.is_reversal for x in original):
        raise HTTPException(status_code=409, detail="A reversal voucher cannot itself be reversed.")
    reversal_no = f"REV-{voucher_no}"[:60]
    if db.scalar(select(JournalLine.id).where(JournalLine.tenant_id == user.tenant_id, JournalLine.voucher_no == reversal_no)):
        raise HTTPException(status_code=409, detail="This journal has already been reversed.")
    entry_date = date.today()
    _assert_period_open(db, user.id, entry_date)
    db.add_all([JournalLine(owner_id=user.id, tenant_id=user.tenant_id, created_by=user.id,
        source_type="REVERSAL", source_id=voucher_no, is_reversal=True, reversed_voucher_no=voucher_no,
        entry_date=entry_date, voucher_no=reversal_no, account_code=x.account_code,
        narration=f"Reversal of {voucher_no}: {x.narration or ''}"[:500],
        debit=x.credit, credit=x.debit) for x in original])
    db.commit()
    return {"originalVoucher": voucher_no, "reversalVoucher": reversal_no, "status": "REVERSED"}


def _balances(db: Session, user: User, start: date | None = None, end: date | None = None):
    accounts = _tenant_accounts(db, user)
    rows = _tenant_lines(db, user, start, end)
    totals = {a.code: {"debit": Decimal("0"), "credit": Decimal("0")} for a in accounts}
    for row in rows:
        totals.setdefault(row.account_code, {"debit": Decimal("0"), "credit": Decimal("0")})
        totals[row.account_code]["debit"] += Decimal(str(row.debit))
        totals[row.account_code]["credit"] += Decimal(str(row.credit))
    result = []
    known_codes = set()
    for a in accounts:
        known_codes.add(a.code)
        d, c = totals[a.code]["debit"], totals[a.code]["credit"]
        balance = d - c if a.normal_balance == "DEBIT" else c - d
        result.append({"code": a.code, "name": a.name, "accountType": a.account_type,
                       "debit": d, "credit": c, "balance": balance})
    for code, values in totals.items():
        if code not in known_codes:
            result.append({"code": code, "name": "UNMAPPED ACCOUNT — configure in Chart of Accounts",
                           "accountType": "UNMAPPED", "debit": values["debit"],
                           "credit": values["credit"], "balance": values["debit"]-values["credit"]})
    return result


@router.get("/trial-balance")
def trial_balance(as_of: date | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    rows = _balances(db, user, end=as_of)
    debit = sum((x["debit"] for x in rows), Decimal("0"))
    credit = sum((x["credit"] for x in rows), Decimal("0"))
    return {"asOf": as_of.isoformat() if as_of else date.today().isoformat(),
            "accounts": [{**x, "debit": str(x["debit"]), "credit": str(x["credit"]), "balance": str(x["balance"])} for x in rows],
            "totalDebit": str(debit), "totalCredit": str(credit), "balanced": debit == credit}


@router.get("/profit-and-loss")
def profit_and_loss(start: date, end: date, db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    if start > end: raise HTTPException(status_code=422, detail="Start date must not be after end date.")
    rows = _balances(db, user, start, end)
    income = sum((x["credit"] - x["debit"] for x in rows if x["accountType"] == "INCOME"), Decimal("0"))
    expenses = sum((x["debit"] - x["credit"] for x in rows if x["accountType"] == "EXPENSE"), Decimal("0"))
    return {"periodStart": start.isoformat(), "periodEnd": end.isoformat(), "income": str(income),
            "expenses": str(expenses), "netProfit": str(income-expenses),
            "incomeAccounts": [x for x in rows if x["accountType"] == "INCOME"],
            "expenseAccounts": [x for x in rows if x["accountType"] == "EXPENSE"]}


@router.get("/balance-sheet")
def balance_sheet(as_of: date | None = None, db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    rows = _balances(db, user, end=as_of)
    assets = sum((x["balance"] for x in rows if x["accountType"] == "ASSET"), Decimal("0"))
    liabilities = sum((x["balance"] for x in rows if x["accountType"] == "LIABILITY"), Decimal("0"))
    equity = sum((x["balance"] for x in rows if x["accountType"] == "EQUITY"), Decimal("0"))
    current_earnings = (
        sum((x["credit"] - x["debit"] for x in rows if x["accountType"] == "INCOME"), Decimal("0"))
        - sum((x["debit"] - x["credit"] for x in rows if x["accountType"] == "EXPENSE"), Decimal("0"))
    )
    total_equity = equity + current_earnings
    return {"asOf": (as_of or date.today()).isoformat(), "assets": str(assets), "liabilities": str(liabilities),
            "equity": str(equity), "currentEarnings": str(current_earnings),
            "totalEquity": str(total_equity), "liabilitiesAndEquity": str(liabilities+total_equity),
            "balanced": assets == liabilities+total_equity,
            "assetAccounts": [x for x in rows if x["accountType"] == "ASSET"],
            "liabilityAccounts": [x for x in rows if x["accountType"] == "LIABILITY"],
            "equityAccounts": [x for x in rows if x["accountType"] == "EQUITY"]}


@router.get("/cash-flow")
def cash_flow(start: date, end: date, db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    if start > end: raise HTTPException(status_code=422, detail="Start date must not be after end date.")
    accounts = {a.code: a for a in _tenant_accounts(db, user) if a.account_type == "ASSET" and ("bank" in a.name.lower() or "cash" in a.name.lower())}
    rows = [x for x in _tenant_lines(db, user, start, end) if x.account_code in accounts]
    inflow = sum((Decimal(str(x.debit)) for x in rows), Decimal("0"))
    outflow = sum((Decimal(str(x.credit)) for x in rows), Decimal("0"))
    return {"periodStart": start.isoformat(), "periodEnd": end.isoformat(),
            "cashInflows": str(inflow), "cashOutflows": str(outflow), "netCashMovement": str(inflow-outflow),
            "transactions": [{"date": x.entry_date.isoformat(), "voucher": x.voucher_no,
                              "account": x.account_code, "debit": str(x.debit), "credit": str(x.credit),
                              "narration": x.narration} for x in rows]}


@router.get("/period-closes")
def list_period_closes(db: Session = Depends(get_db), user: User = Depends(require_roles(*VIEW_ROLES))):
    rows = db.scalars(select(LedgerPeriodClose).where(LedgerPeriodClose.tenant_id == user.tenant_id)
                      .order_by(LedgerPeriodClose.period_start.desc())).all()
    return {"periods": [{"id": x.id, "start": x.period_start.isoformat(), "end": x.period_end.isoformat(),
                         "status": x.status, "reason": x.reason, "closedAt": x.closed_at.isoformat()} for x in rows]}


@router.post("/period-closes", status_code=201)
def close_period(body: ClosePeriodIn, db: Session = Depends(get_db), user: User = Depends(require_roles("Chief Accountant"))):
    if body.period_start > body.period_end:
        raise HTTPException(status_code=422, detail="Period start must not be after period end.")
    existing = db.scalar(select(LedgerPeriodClose).where(LedgerPeriodClose.tenant_id == user.tenant_id,
        LedgerPeriodClose.period_start == body.period_start, LedgerPeriodClose.period_end == body.period_end))
    if existing:
        raise HTTPException(status_code=409, detail="This accounting period is already closed.")
    lines = _tenant_lines(db, user, body.period_start, body.period_end)
    voucher_totals = {}
    for line in lines:
        bucket = voucher_totals.setdefault(line.voucher_no, [Decimal("0"), Decimal("0")])
        bucket[0] += Decimal(str(line.debit)); bucket[1] += Decimal(str(line.credit))
    unbalanced = [v for v, totals in voucher_totals.items() if totals[0] != totals[1]]
    if unbalanced:
        raise HTTPException(status_code=409, detail=f"Cannot close period: unbalanced vouchers found: {', '.join(unbalanced[:10])}")
    tb = _balances(db, user, end=body.period_end)
    debit = sum((x["debit"] for x in tb), Decimal("0"))
    credit = sum((x["credit"] for x in tb), Decimal("0"))
    if debit != credit:
        raise HTTPException(status_code=409, detail="Cannot close period: Trial Balance is not balanced.")
    row = LedgerPeriodClose(tenant_id=user.tenant_id, owner_id=user.id, period_start=body.period_start,
        period_end=body.period_end, status="CLOSED", reason=body.reason, closed_by=user.id)
    db.add(row); db.commit(); db.refresh(row)
    return {"id": row.id, "status": row.status, "closedAt": row.closed_at.isoformat()}
