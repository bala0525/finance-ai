"""Finance Analyst, Expense, Fraud Detection and Financial Reporting workflows."""

from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_roles
from app.models.document import Document
from app.models.document_audit_event import DocumentAuditEvent
from app.models.fraud_review import FraudReview
from app.models.ledger import JournalLine, LedgerAccount, LedgerImport
from app.models.user import User
from app.services.notifications import notify_user, notify_roles
from app.models.workflow import ExpenseDecision, ExpensePolicy, ReportSchedule
from app.routes.documents import add_audit_event
from app.routes.reports import create_financial_report
from app.routes.workflow_common import (
    AP_CATEGORIES,
    AR_CATEGORIES,
    EXPENSE_CATEGORIES,
    INVOICE_LIKE,
    REVIEWER_ROLE_NAMES,
    amount_of,
    doc_date,
    gemini_text,
    get_doc,
    is_dup,
    iso,
    today,
    visible_docs,
    xlsx_response,
)
from app.services import analysis, exports, expense_policy, fraud_scoring, insights, statements, posting

router = APIRouter(prefix="/agents", tags=["Workflows"])
logger = logging.getLogger(__name__)
MAX_LEDGER_BYTES = 5 * 1024 * 1024


def _rows(db: Session, user: User, category: str | None = None) -> list[dict]:
    docs = visible_docs(db, user, INVOICE_LIKE)
    if category:
        docs = [d for d in docs if (d.category or "").lower() == category.strip().lower()]
    return [
        {"date": doc_date(d), "amount": amount_of(d), "category": d.category, "vendor": d.vendor_name}
        for d in docs
        if amount_of(d) is not None and doc_date(d) is not None
    ]


# ================================================================= Finance Analyst
class VarianceBody(BaseModel):
    current_start: date
    current_end: date
    base_start: date | None = None
    base_end: date | None = None
    budget: dict[str, float] | None = None
    group_by: str = Field(default="category", pattern="^(category|vendor)$")
    category: str | None = Field(default=None, max_length=100)
    use_ai: bool = False


def _variance_summary(result: dict) -> str:
    t = result["totals"]
    pct = f" ({t['variancePct']:+.1f}%)" if t["variancePct"] is not None else ""
    top = result["lines"][0] if result["lines"] else None
    text = f"Total actual INR {t['actual']:,.2f} versus INR {t['reference']:,.2f}: variance INR {t['variance']:+,.2f}{pct}."
    if top and top["variance"]:
        text += f" Largest movement: {top['group']} at INR {top['variance']:+,.2f}."
    return text


@router.post("/finance-analyst/variance")
def analyst_variance(body: VarianceBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    base = (body.base_start, body.base_end) if body.base_start and body.base_end else None
    try:
        result = analysis.variance_analysis(
            _rows(db, user, body.category), (body.current_start, body.current_end), base, body.budget, body.group_by
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result["dataPoints"] == 0:
        raise HTTPException(status_code=422, detail="Insufficient data: no documents with amounts and dates were found.")
    result["commentary"] = {"text": _variance_summary(result), "ai": False}
    if body.use_ai:
        text = gemini_text(
            "Write a 3-sentence management commentary on this variance analysis. Use ONLY the figures given; "
            "do not invent numbers or causes.\n" + _variance_summary(result) + "\n"
            + "\n".join(f"{l['group']}: reference {l['reference']}, actual {l['actual']}, variance {l['variance']}" for l in result["lines"][:8])
        )
        if text:
            result["commentary"] = {"text": text, "ai": True, "label": "AI-written from the computed figures above. Review before use."}
    return result


class ForecastBody(BaseModel):
    periods: int = Field(default=3, ge=1, le=12)
    method: str = Field(default="moving_average", pattern="^(moving_average|linear_trend)$")
    category: str | None = Field(default=None, max_length=100)


@router.post("/finance-analyst/forecast")
def analyst_forecast(body: ForecastBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    monthly = analysis.monthly_totals(_rows(db, user, body.category))
    try:
        return analysis.forecast_series(monthly, body.periods, body.method)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class ScenarioBody(BaseModel):
    revenue_change_pct: float = Field(default=0, ge=-100, le=1000)
    expense_change_pct: float = Field(default=0, ge=-100, le=1000)
    collection_delay_days: int = Field(default=0, ge=0, le=365)


@router.post("/finance-analyst/scenario")
def analyst_scenario(body: ScenarioBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    start = today() - timedelta(days=365)
    docs = visible_docs(db, user, INVOICE_LIKE)

    def total(categories: set[str]) -> float:
        return sum(
            amount_of(d) or 0.0 for d in docs
            if (d.category or "").lower() in categories and doc_date(d) and doc_date(d) >= start
        )

    open_ar = [
        {"amount": amount_of(d), "due_date": d.due_date}
        for d in docs
        if (d.category or "").lower() in AR_CATEGORIES and d.status != "PAID" and d.review_status != "REJECTED"
    ]
    revenue, expenses = total(AR_CATEGORIES), total(AP_CATEGORIES | EXPENSE_CATEGORIES)
    if revenue == 0 and expenses == 0 and not open_ar:
        raise HTTPException(status_code=422, detail="Insufficient data: upload receivable, payable or expense documents first.")
    result = analysis.scenario_analysis(
        revenue, expenses, open_ar, body.revenue_change_pct, body.expense_change_pct, body.collection_delay_days, today()
    )
    result["basis"] = (
        "Revenue = receivable documents and expenses = payable/invoice/expense documents dated in the last 12 months. "
        "Inflows use due dates of unpaid receivables."
    )
    return result


class InsightsBody(BaseModel):
    use_ai: bool = False


@router.post("/finance-analyst/insights")
def analyst_insights(body: InsightsBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = visible_docs(db, user, INVOICE_LIKE)

    def kind(d: Document) -> str:
        cat = (d.category or "").lower()
        return "AR" if cat in AR_CATEGORIES else "EXPENSE" if cat in EXPENSE_CATEGORIES else "AP"

    rows = [
        {
            "id": d.id, "name": d.name, "kind": kind(d), "vendor": d.vendor_name, "amount": amount_of(d),
            "date": doc_date(d), "due_date": d.due_date, "status": d.status, "review_status": d.review_status,
            "validation_status": d.validation_status, "is_duplicate": is_dup(d),
            "confidence": float(d.extraction_confidence) if d.extraction_confidence is not None else None,
        }
        for d in docs
    ]
    try:
        result = insights.build_insights(rows, today())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["summary"] = None
    if body.use_ai and result["insights"]:
        text = gemini_text(
            "Write a 3-4 sentence management summary of these finance insights for a finance manager. "
            "Use ONLY the facts given, do not add numbers, causes or predictions. Mention the most urgent item first.\n"
            + "\n".join(f"[{i['severity']}] {i['title']}: {i['message']}" for i in result["insights"])
        )
        if text:
            result["summary"] = {"text": text, "label": "AI-written from the calculated insights above. Review before use."}
    return result


# ======================================================================== Expense
def _policies(db: Session) -> dict[str, dict]:
    rows = db.scalars(select(ExpensePolicy)).all()
    if not rows:
        for kind, limit in expense_policy.DEFAULT_POLICIES.items():
            db.add(ExpensePolicy(expense_type=kind, claim_limit=Decimal(str(limit)), receipt_required=True, is_default=True))
        db.commit()
        rows = db.scalars(select(ExpensePolicy)).all()
    return {
        p.expense_type: {
            "limit": float(p.claim_limit) if p.claim_limit is not None else None,
            "receipt_required": p.receipt_required,
            "is_default": p.is_default,
        }
        for p in rows
    }


@router.get("/expense/policies")
def expense_get_policies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    policies = _policies(db)
    return {
        "policies": [
            {"expenseType": k, "claimLimit": v["limit"], "receiptRequired": v["receipt_required"], "isDefault": v["is_default"]}
            for k, v in sorted(policies.items())
        ],
        "canEdit": user.can_review,
    }


class PolicyItem(BaseModel):
    expense_type: str
    claim_limit: Decimal | None = Field(default=None, ge=0)
    receipt_required: bool = True


class PoliciesBody(BaseModel):
    policies: list[PolicyItem] = Field(min_length=1, max_length=20)


@router.put("/expense/policies")
def expense_put_policies(
    body: PoliciesBody, db: Session = Depends(get_db), user: User = Depends(require_roles(*REVIEWER_ROLE_NAMES))
):
    _policies(db)
    existing = {p.expense_type: p for p in db.scalars(select(ExpensePolicy)).all()}
    for item in body.policies:
        if item.expense_type not in expense_policy.EXPENSE_TYPES:
            raise HTTPException(status_code=422, detail=f"Unknown expense type '{item.expense_type}'.")
        row = existing.get(item.expense_type) or ExpensePolicy(expense_type=item.expense_type)
        row.claim_limit, row.receipt_required = item.claim_limit, item.receipt_required
        row.is_default, row.updated_by, row.updated_at = False, user.id, datetime.now(timezone.utc)
        db.add(row)
    db.commit()
    return expense_get_policies(db, user)


@router.get("/expense/evaluation")
def expense_evaluation(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    policies = _policies(db)
    docs = visible_docs(db, user, EXPENSE_CATEGORIES)
    decisions = {
        d.document_id: d
        for d in db.scalars(select(ExpenseDecision).where(ExpenseDecision.document_id.in_([x.id for x in docs]))).all()
    } if docs else {}
    out = []
    for d in docs:
        result = expense_policy.evaluate_expense(
            {
                "name": d.name, "vendor": d.vendor_name, "invoice_number": d.invoice_number,
                "invoice_date": d.invoice_date, "amount": amount_of(d), "is_duplicate": is_dup(d),
            },
            policies, today(),
        )
        decision = decisions.get(d.id)
        out.append(
            {
                "documentId": d.id, "documentName": d.name, "vendor": d.vendor_name, "invoiceNumber": d.invoice_number,
                "date": iso(d.invoice_date), "amount": amount_of(d), "ownerName": d.owner.full_name if d.owner else None,
                # NEW: role/action visibility and payment audit fields for Expense Employee UI.
                "ownerId": d.owner_id, "status": d.status, "paidBy": d.paid_by,
                "paidAt": iso(d.paid_at), "ledgerVoucherNo": d.ledger_voucher_no,
                **result,
                "decision": {
                    "decision": decision.decision,
                    "approvedAmount": float(decision.approved_amount) if decision.approved_amount is not None else None,
                    "note": decision.note,
                    "decidedAt": iso(decision.decided_at),
                } if decision else None,
            }
        )
    return {
        "expenses": out,
        # CHANGED: only Finance User / Finance Manager may decide Employee expenses.
        "canDecide": user.role_name in {"Finance User", "Finance Manager"},
        "canVerify": user.role_name == "Finance User",
    }


class ExpenseDecisionBody(BaseModel):
    document_id: int
    decision: str = Field(pattern="^(VERIFIED|APPROVED|PARTIAL|REJECTED|CHANGES_REQUESTED)$")
    approved_amount: Decimal | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=2000)


@router.post("/expense/decision")
def expense_decide(
    body: ExpenseDecisionBody,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Finance User", "Finance Manager")),
):
    """NEW: Employee expenses can be approved/rejected by Finance User or Manager only."""
    doc = get_doc(db, user, body.document_id)
    if (doc.category or "").strip().lower() not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=422, detail="Only expense documents can receive a reimbursement decision.")
    if doc.owner_id == user.id:
        raise HTTPException(status_code=403, detail="You cannot decide your own expense claim.")
    if doc.status not in {"PENDING_REVIEW", "PENDING_FINANCE_USER_VERIFICATION", "PENDING_MANAGER_APPROVAL", "READY_FOR_REVIEW"}:
        raise HTTPException(status_code=409, detail="This expense is not awaiting an authorized review decision.")

    role = user.role_name
    note = body.note.strip() if body.note and body.note.strip() else None
    now = datetime.now(timezone.utc)
    existing = db.scalar(select(ExpenseDecision).where(ExpenseDecision.document_id == doc.id))

    if body.decision == "VERIFIED":
        if role != "Finance User":
            raise HTTPException(status_code=403, detail="Only Finance Users can record an initial verification.")
        if existing is not None and existing.verified_by is not None:
            raise HTTPException(status_code=409, detail="This expense has already been verified.")
        row = existing or ExpenseDecision(document_id=doc.id, decision="FINANCE_USER_VERIFIED", approved_amount=None)
        row.verified_by, row.verified_at = user.id, now
        doc.verified_by, doc.verified_at = user.id, now  # NEW: mirror verification on the source document.
        row.note = note
        row.decision = "FINANCE_USER_VERIFIED"
        doc.first_reviewed_by, doc.first_reviewed_at, doc.first_review_action = user.id, now, "VERIFIED"
        doc.status = doc.review_status = "PENDING_MANAGER_APPROVAL"
        action_name, next_step = "EXPENSE_FINANCE_USER_VERIFIED", "FINANCE_MANAGER_OR_FINANCE_USER_DECISION"
        amount = Decimal("0")
    elif body.decision in {"APPROVED", "PARTIAL", "REJECTED", "CHANGES_REQUESTED"}:
        if body.decision in {"REJECTED", "CHANGES_REQUESTED"}:
            if not note:
                raise HTTPException(status_code=422, detail="Add a reason when rejecting or requesting changes to an expense claim.")
            amount = Decimal("0")
            stored_decision = body.decision
            doc.status = "NEEDS_CHANGES" if body.decision == "CHANGES_REQUESTED" else "REJECTED"
            doc.review_status = "CHANGES_REQUESTED" if body.decision == "CHANGES_REQUESTED" else "REJECTED"
            doc.rejection_reason = note
            if body.decision == "REJECTED":
                doc.rejected_by, doc.rejected_at = user.id, now  # NEW: explicit expense rejection audit.
            else:
                doc.verified_by, doc.verified_at = user.id, now
            next_step = "UPLOADER_RESUBMISSION_OR_CANCELLATION"
        else:
            if doc.total_amount is None:
                raise HTTPException(status_code=422, detail="The claim has no extracted amount to approve.")
            if body.decision == "PARTIAL":
                if body.approved_amount is None or not (0 < body.approved_amount < doc.total_amount):
                    raise HTTPException(status_code=422, detail="For partial approval enter an amount above zero and below the claim total.")
                amount = body.approved_amount
                stored_decision = "PARTIAL"
            else:
                amount = body.approved_amount or doc.total_amount
                if amount <= 0 or amount > doc.total_amount:
                    raise HTTPException(status_code=422, detail="Approved amount must be above zero and cannot exceed the claim total.")
                stored_decision = "APPROVED"
            doc.status = doc.review_status = "PENDING_PAYMENT"
            doc.rejection_reason = None
            doc.approved_by, doc.approved_at = user.id, now  # NEW: explicit expense approval audit.
            next_step = "FINANCE_USER_REIMBURSEMENT"
        row = existing or ExpenseDecision(document_id=doc.id, decision=stored_decision, approved_amount=amount)
        row.decision, row.approved_amount, row.note = stored_decision, amount, note
        row.decided_by, row.decided_at = user.id, now
        doc.first_reviewed_by, doc.first_reviewed_at, doc.first_review_action = user.id, now, stored_decision
        action_name = f"EXPENSE_{role.upper().replace(' ', '_')}_{body.decision}"
    else:
        raise HTTPException(status_code=422, detail="Unsupported expense decision.")

    row.decided_by, row.decided_at = user.id, now
    db.add(row)
    add_audit_event(db, doc.id, user.id, action_name, {"decision": row.decision, "amount": str(amount), "role": role, "next_step": next_step}, reason=note, owner_id=doc.owner_id)
    if body.decision in {"REJECTED", "CHANGES_REQUESTED"}:
        event_type = "EXPENSE_CHANGES_REQUESTED" if body.decision == "CHANGES_REQUESTED" else "EXPENSE_REJECTED"
        title = "Expense changes required" if body.decision == "CHANGES_REQUESTED" else "Expense claim rejected"
        message = f"Please correct your expense claim and re-upload it. Remarks: {note}" if body.decision == "CHANGES_REQUESTED" else f"Your expense claim was rejected. Reason: {note}"
        notify_user(db, doc.owner, event_type, title, message, "/employees/expense-employee")
    elif body.decision in {"APPROVED", "PARTIAL"}:
        notify_user(db, doc.owner, "EXPENSE_APPROVED", "Expense approved", f"Your expense was approved for INR {amount} and is ready for Finance User reimbursement.", "/employees/expense-employee")
        notify_roles(db, user.tenant_id, {"Finance User"}, "EXPENSE_REIMBURSEMENT_READY", "Expense ready for reimbursement", f"Expense claim #{doc.id} was approved by {user.full_name}.", "/employees/expense-employee")
    db.commit()
    return {"decision": row.decision, "approvedAmount": float(amount), "nextStep": next_step, "status": doc.status}


@router.post("/expense/{document_id}/reimburse")
def expense_reimburse(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Finance User")),
):
    doc = get_doc(db, user, document_id)
    if (doc.category or "").strip().lower() not in EXPENSE_CATEGORIES:
        raise HTTPException(status_code=422, detail="Only expense documents can be reimbursed.")
    decision = db.scalar(select(ExpenseDecision).where(ExpenseDecision.document_id == doc.id))
    if decision is None or decision.decision not in {"APPROVED", "PARTIAL"} or decision.approved_amount is None or decision.approved_amount <= 0:
        raise HTTPException(status_code=409, detail="An approved expense decision is required before reimbursement.")
    if doc.assigned_finance_user_id not in {None, user.id}:
        raise HTTPException(status_code=403, detail="This expense is assigned to another Finance User.")
    if doc.status == "ON_HOLD":
        raise HTTPException(status_code=409, detail="This expense is on fraud-review hold and cannot be reimbursed until Admin resolves the alert.")
    if doc.status == "PAID":
        raise HTTPException(status_code=409, detail="This expense has already been reimbursed.")
    voucher = posting.post_expense_reimbursement(
        db, user.id, doc.id, today(), Decimal(str(decision.approved_amount)),
        doc.account_code or doc.suggested_account_code, doc.owner.full_name if doc.owner else None,
    )
    doc.status = doc.review_status = "PAID"
    doc.assigned_finance_user_id = doc.assigned_finance_user_id or user.id
    doc.paid_by, doc.paid_at = user.id, datetime.now(timezone.utc)
    doc.payment_amount = Decimal(str(decision.approved_amount))
    doc.payment_date = today()
    doc.ledger_voucher_no = voucher
    add_audit_event(db, doc.id, user.id, "EXPENSE_REIMBURSED_AND_POSTED", {"voucher": voucher, "amount": float(decision.approved_amount), "paid_by": user.id, "source_document_id": doc.id}, owner_id=doc.owner_id)
    notify_user(db, doc.owner, "EXPENSE_REIMBURSED", "Expense reimbursed", f"Your approved expense was reimbursed. Voucher: {voucher}.", "/employees/expense-employee")
    db.commit()
    return {"status": "PAID", "voucher": voucher, "amount": float(decision.approved_amount)}


# ================================================================ Fraud Detection
def _risk_docs(db: Session, user: User) -> list[Document]:
    return visible_docs(db, user, INVOICE_LIKE)


def _risk_input(docs: list[Document]) -> list[dict]:
    return [
        {
            "id": d.id, "name": d.name, "vendor": d.vendor_name, "invoice_number": d.invoice_number,
            "invoice_date": d.invoice_date, "amount": amount_of(d), "is_duplicate": is_dup(d),
        }
        for d in docs
    ]


@router.get("/fraud-detection/risk")
def fraud_risk(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return fraud_scoring.score_documents(_risk_input(_risk_docs(db, user)), float(settings.manager_approval_limit))


@router.get("/fraud-detection/evidence/{document_id}")
def fraud_evidence(
    document_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*REVIEWER_ROLE_NAMES))
):
    doc = get_doc(db, user, document_id)
    docs = _risk_docs(db, user)
    scored = fraud_scoring.score_documents(_risk_input(docs), float(settings.manager_approval_limit))
    risk = next((r for r in scored["documents"] if r["documentId"] == doc.id), None)
    if risk is None:
        raise HTTPException(status_code=422, detail="Risk scoring applies to invoice, payable, receivable and expense documents.")

    def related_reason(other: Document) -> str | None:
        same_vendor = doc.vendor_name and other.vendor_name and doc.vendor_name.strip().lower() == other.vendor_name.strip().lower()
        if same_vendor and doc.invoice_number and doc.invoice_number == other.invoice_number:
            return "Same vendor and invoice number"
        if same_vendor and doc.total_amount is not None and other.total_amount == doc.total_amount:
            return "Same vendor and amount"
        return None

    related = [
        {
            "id": o.id, "name": o.name, "vendor": o.vendor_name, "invoiceNumber": o.invoice_number,
            "amount": amount_of(o), "date": iso(o.invoice_date), "why": why,
        }
        for o in docs if o.id != doc.id and (why := related_reason(o))
    ]
    names: dict[int, str] = {}

    def who(user_id: int | None) -> str | None:
        if user_id is None:
            return None
        if user_id not in names:
            u = db.get(User, user_id)
            names[user_id] = (u.full_name or u.email) if u else f"User {user_id}"
        return names[user_id]

    events = db.scalars(select(DocumentAuditEvent).where(DocumentAuditEvent.document_id == doc.id).order_by(DocumentAuditEvent.created_at)).all()
    reviews = db.scalars(select(FraudReview).where(FraudReview.document_id == doc.id)).all()
    add_audit_event(db, doc.id, user.id, "EVIDENCE_PACK_EXPORTED", {"score": risk["score"]}, owner_id=doc.owner_id)
    db.commit()
    content = exports.evidence_pack_xlsx(
        risk,
        {"name": doc.name, "vendor": doc.vendor_name, "invoiceNumber": doc.invoice_number, "amount": amount_of(doc), "owner": who(doc.owner_id)},
        related,
        [{"when": iso(e.created_at), "action": e.action, "actor": who(e.actor_id), "reason": e.reason} for e in events],
        [{"signal": r.signal_type, "status": r.status, "note": r.note, "reviewer": who(r.reviewed_by), "reviewedAt": iso(r.reviewed_at)} for r in reviews],
    )
    return xlsx_response(content, f"Evidence pack - document {doc.id}.xlsx")


# ============================================================ Financial Reporting
def _ledger(db: Session, user: User) -> tuple[list[dict], list[dict]]:
    accounts = [
        {"code": a.code, "name": a.name, "type": a.account_type}
        for a in db.scalars(select(LedgerAccount).where(LedgerAccount.owner_id == user.id)).all()
    ]
    lines = [
        {"date": l.entry_date, "voucher_no": l.voucher_no, "account_code": l.account_code, "narration": l.narration, "debit": float(l.debit), "credit": float(l.credit)}
        for l in db.scalars(select(JournalLine).where(JournalLine.owner_id == user.id)).all()
    ]
    return accounts, lines


@router.get("/financial-reporting/ledger")
def ledger_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    accounts = db.scalar(select(func.count()).select_from(LedgerAccount).where(LedgerAccount.owner_id == user.id)) or 0
    count, first, last = db.execute(
        select(func.count(), func.min(JournalLine.entry_date), func.max(JournalLine.entry_date)).where(JournalLine.owner_id == user.id)
    ).one()
    latest = db.scalars(select(LedgerImport).where(LedgerImport.owner_id == user.id).order_by(LedgerImport.created_at.desc())).first()
    journal_lines = db.scalars(
        select(JournalLine).where(JournalLine.owner_id == user.id).order_by(JournalLine.entry_date, JournalLine.id)
    ).all()
    vouchers: dict[str, dict[str, Decimal | int]] = {}
    for line in journal_lines:
        item = vouchers.setdefault(line.voucher_no, {"debit": Decimal("0"), "credit": Decimal("0"), "lines": 0})
        item["debit"] += Decimal(str(line.debit))
        item["credit"] += Decimal(str(line.credit))
        item["lines"] += 1
    unbalanced = [
        {"voucherNo": voucher, "debit": float(values["debit"]), "credit": float(values["credit"]), "lineCount": values["lines"]}
        for voucher, values in vouchers.items()
        if values["debit"] != values["credit"] or values["lines"] < 2
    ]
    total_debit = sum((Decimal(str(line.debit)) for line in journal_lines), Decimal("0"))
    total_credit = sum((Decimal(str(line.credit)) for line in journal_lines), Decimal("0"))
    return {
        "accountCount": accounts, "journalLineCount": count, "firstEntry": iso(first), "lastEntry": iso(last),
        "lastImport": {"filename": latest.filename, "at": iso(latest.created_at)} if latest else None,
        "totalDebit": float(total_debit), "totalCredit": float(total_credit),
        "isBalanced": bool(journal_lines) and total_debit == total_credit and not unbalanced,
        "unbalancedVoucherCount": len(unbalanced), "unbalancedVouchers": unbalanced[:100],
    }


@router.get("/financial-reporting/ledger/template")
def ledger_template(user: User = Depends(get_current_user)):
    return xlsx_response(statements.ledger_template_xlsx(), "ledger-template.xlsx")


@router.post("/financial-reporting/ledger/import", status_code=201)
async def ledger_import(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    name = file.filename or "ledger.xlsx"
    if not name.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=415, detail="Upload an .xlsx ledger workbook (download the template for the layout).")
    content = await file.read(MAX_LEDGER_BYTES + 1)
    if len(content) > MAX_LEDGER_BYTES:
        raise HTTPException(status_code=413, detail="The ledger workbook is larger than 5 MB.")
    try:
        accounts, lines = statements.parse_ledger_workbook(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - corrupt workbook
        logger.warning("Ledger import could not read workbook", exc_info=True)
        raise HTTPException(status_code=422, detail="The workbook could not be read. Use the template layout.") from exc
    try:
        # Import is append-only: never delete or overwrite historical accounting records.
        existing_vouchers = set(db.scalars(select(JournalLine.voucher_no).where(JournalLine.owner_id == user.id)).all())
        incoming_vouchers = {line["voucher_no"] for line in lines}
        if existing_vouchers.intersection(incoming_vouchers):
            raise HTTPException(status_code=409, detail="The workbook contains voucher numbers that already exist. Remove duplicates before importing.")
        existing_codes = set(db.scalars(select(LedgerAccount.code).where(LedgerAccount.owner_id == user.id)).all())
        db.add_all(LedgerAccount(
            owner_id=user.id, tenant_id=user.tenant_id, code=a["code"], name=a["name"],
            account_type=a["type"],
            normal_balance="DEBIT" if a["type"] in {"ASSET", "EXPENSE"} else "CREDIT",
            is_active=True,
        ) for a in accounts if a["code"] not in existing_codes)
        db.add_all(
            JournalLine(
                owner_id=user.id, tenant_id=user.tenant_id, created_by=user.id,
                source_type="IMPORT", source_id=name[:80], entry_date=l["date"], voucher_no=l["voucher_no"], account_code=l["account_code"],
                narration=l["narration"], debit=l["debit"], credit=l["credit"],
            )
            for l in lines
        )
        db.add(LedgerImport(owner_id=user.id, filename=name[:255], account_count=len(accounts), journal_line_count=len(lines), invoice_count=0))
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Ledger import failed")
        raise HTTPException(status_code=500, detail="The ledger could not be saved. Nothing was changed.") from exc
    return {"accountCount": len(accounts), "journalLineCount": len(lines), "replaced": False, "mode": "APPEND_ONLY"}


class StatementsBody(BaseModel):
    start: date
    end: date
    compare_start: date | None = None
    compare_end: date | None = None
    use_ai: bool = False


def _statement_bundle(db: Session, user: User, body: StatementsBody) -> tuple[dict, dict | None, list[str]]:
    accounts, lines = _ledger(db, user)
    if not accounts or not lines:
        raise HTTPException(status_code=422, detail="No ledger data yet. Download the template, fill it, and import it first.")
    try:
        current = statements.build_statements(accounts, lines, body.start, body.end)
        comparison, commentary = None, []
        if body.compare_start and body.compare_end:
            previous = statements.build_statements(accounts, lines, body.compare_start, body.compare_end)
            comparison = statements.compare_statements(current, previous)
            commentary = comparison["commentaryLines"]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return current, comparison, commentary


@router.post("/financial-reporting/statements")
def reporting_statements(body: StatementsBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    current, comparison, commentary = _statement_bundle(db, user, body)
    result = {"statements": current, "comparison": comparison, "commentary": {"lines": commentary, "ai": None}}
    if body.use_ai and commentary:
        text = gemini_text(
            "Write a short management commentary (4 sentences max) from ONLY these computed facts. "
            "Do not add numbers, causes or predictions.\n" + "\n".join(commentary)
        )
        if text:
            result["commentary"]["ai"] = {"text": text, "label": "AI-written from the computed lines above. Review before use."}
    return result


@router.get("/financial-reporting/statements/export")
def reporting_statements_export(
    start: date, end: date, compare_start: date | None = None, compare_end: date | None = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    body = StatementsBody(start=start, end=end, compare_start=compare_start, compare_end=compare_end)
    current, comparison, commentary = _statement_bundle(db, user, body)
    return xlsx_response(exports.statements_xlsx(current, comparison, commentary), f"Financial statements {start} to {end}.xlsx")


# --- schedules (no background scheduler: runs are manual / due-now)
def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    year, month = index // 12, index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _advance(value: date, frequency: str) -> date:
    return value + timedelta(days=7) if frequency == "WEEKLY" else _add_months(value, 1 if frequency == "MONTHLY" else 3)


def _previous_period(frequency: str, now: date) -> tuple[date, date]:
    if frequency == "WEEKLY":
        return now - timedelta(days=7), now - timedelta(days=1)
    step = 1 if frequency == "MONTHLY" else 3
    first_this = date(now.year, now.month, 1) if frequency == "MONTHLY" else date(now.year, ((now.month - 1) // 3) * 3 + 1, 1)
    start = _add_months(first_this, -step)
    return start, first_this - timedelta(days=1)


def _schedule_dict(s: ReportSchedule) -> dict:
    return {
        "id": s.id, "name": s.name, "reportType": s.report_type, "frequency": s.frequency, "nextRun": iso(s.next_run),
        "status": s.status, "lastRunAt": iso(s.last_run_at), "lastReportId": s.last_report_id,
        "due": s.status == "ACTIVE" and s.next_run <= today(),
    }


def _get_schedule(db: Session, user: User, schedule_id: int) -> ReportSchedule:
    s = db.get(ReportSchedule, schedule_id)
    if s is None or (s.owner_id != user.id and not user.can_review):
        raise HTTPException(status_code=404, detail="Schedule not found.")
    return s


@router.get("/financial-reporting/schedules")
def schedules_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(ReportSchedule).order_by(ReportSchedule.next_run, ReportSchedule.id)
    if not user.can_review:
        statement = statement.where(ReportSchedule.owner_id == user.id)
    return {
        "schedules": [_schedule_dict(s) for s in db.scalars(statement).all()],
        "note": "Schedules are tracked and run on demand (or when due). There is no background job, so nothing runs by itself.",
    }


class ScheduleBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    report_type: str = Field(pattern="^(DOCUMENT_SUMMARY|FINANCIAL_STATEMENTS)$")
    frequency: str = Field(pattern="^(WEEKLY|MONTHLY|QUARTERLY)$")
    first_run: date


@router.post("/financial-reporting/schedules", status_code=201)
def schedules_create(body: ScheduleBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = ReportSchedule(
        owner_id=user.id, name=body.name.strip(), report_type=body.report_type, frequency=body.frequency, next_run=body.first_run
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return _schedule_dict(s)


@router.post("/financial-reporting/schedules/{schedule_id}/{action}")
def schedules_action(schedule_id: int, action: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _get_schedule(db, user, schedule_id)
    if action == "pause":
        s.status = "PAUSED"
    elif action == "resume":
        s.status = "ACTIVE"
    elif action == "run":
        return _run_schedule(db, user, s)
    else:
        raise HTTPException(status_code=404, detail="Unknown schedule action.")
    db.commit()
    return _schedule_dict(s)


def _run_schedule(db: Session, user: User, s: ReportSchedule) -> dict:
    now = today()
    extra: dict = {}
    if s.report_type == "DOCUMENT_SUMMARY":
        report, _ = create_financial_report(db, user, f"{s.name} {now.isoformat()}", now.strftime("%B %Y"))
        s.last_report_id = report.id
        extra["reportId"] = report.id
    else:
        start, end = _previous_period(s.frequency, now)
        body = StatementsBody(start=start, end=end)
        current, _, _ = _statement_bundle(db, user, body)
        extra["statements"] = current
        extra["period"] = {"start": start.isoformat(), "end": end.isoformat()}
    s.last_run_at = datetime.now(timezone.utc)
    while s.next_run <= now:
        s.next_run = _advance(s.next_run, s.frequency)
    db.commit()
    return {**_schedule_dict(s), **extra}


@router.delete("/financial-reporting/schedules/{schedule_id}")
def schedules_delete(schedule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.delete(_get_schedule(db, user, schedule_id))
    db.commit()
    return {"deleted": True}


@router.get("/financial-reporting/operational-reports/{report_type}")
def operational_financial_report(
    report_type: str,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AP/AR operational report sourced from persisted invoice documents."""
    kind = report_type.strip().lower()
    if kind not in {"accounts-payable", "accounts-receivable"}:
        raise HTTPException(status_code=404, detail="Report type must be accounts-payable or accounts-receivable.")
    categories = AP_CATEGORIES if kind == "accounts-payable" else AR_CATEGORIES
    docs = visible_docs(db, user, categories)
    if start and end and start > end:
        raise HTTPException(status_code=422, detail="Start date must not be after end date.")
    rows = []
    for doc in docs:
        doc_day = doc.invoice_date or doc.created_at.date()
        if start and doc_day < start or end and doc_day > end:
            continue
        rows.append({
            "documentId": doc.id, "documentName": doc.name, "party": doc.vendor_name,
            "invoiceNumber": doc.invoice_number, "invoiceDate": iso(doc.invoice_date),
            "dueDate": iso(doc.due_date), "amount": amount_of(doc), "status": doc.status,
            "approvalStatus": doc.review_status, "validationStatus": doc.validation_status,
        })
    total = sum((r["amount"] or 0) for r in rows)
    outstanding = sum((r["amount"] or 0) for r in rows if r["status"] != "PAID")
    return {"reportType": kind, "start": iso(start), "end": iso(end), "count": len(rows),
            "totalAmount": round(total, 2), "outstandingAmount": round(outstanding, 2), "rows": rows,
            "basis": "Persisted uploaded invoice document records; completeness depends on the documents uploaded."}


@router.get("/financial-reporting/operational-reports/{report_type}/export")
def operational_financial_report_export(
    report_type: str, start: date | None = None, end: date | None = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    report = operational_financial_report(report_type, start, end, db, user)
    filename = f"{report_type}-{start or 'all'}-to-{end or 'all'}.xlsx"
    return xlsx_response(exports.operational_report_xlsx(report), filename)
