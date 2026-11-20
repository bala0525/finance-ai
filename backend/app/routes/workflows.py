"""AP, AR, Invoice Processing and Reconciliation workflows."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.permissions import require_roles
from app.models.document import Document
from app.models.ledger import LedgerAccount
from app.models.reconciliation_run import ReconciliationRun
from app.models.user import User
from app.services.notifications import notify_user, notify_roles
from app.models.workflow import (
    CollectionReminder,
    DisputeCase,
    PaymentBatch,
    PaymentBatchItem,
    WorkflowResolution,
)
from app.routes.documents import add_audit_event
from app.routes.workflow_common import (
    AP_CATEGORIES,
    AR_CATEGORIES,
    REVIEWER_ROLE_NAMES,
    amount_of,
    gemini_text,
    is_dup,
    get_doc,
    iso,
    today,
    visible_docs,
    xlsx_response,
)
from app.services import coding, exports, receivables, recon_exceptions, posting
from app.services.confidence import LOW_CONFIDENCE_THRESHOLD
from app.services.storage import storage, build_object_path, StorageError
from app.core.config import settings

router = APIRouter(prefix="/agents", tags=["Workflows"])
logger = logging.getLogger(__name__)


def _note(value: str | None) -> str | None:
    return value.strip() if value and value.strip() else None


# =============================================================== Accounts Payable
def _payable_docs(db: Session, user: User) -> list[Document]:
    return visible_docs(db, user, AP_CATEGORIES)


def _batched_ids(db: Session, doc_ids: list[int]) -> set[int]:
    if not doc_ids:
        return set()
    return set(
        db.scalars(select(PaymentBatchItem.document_id).where(PaymentBatchItem.document_id.in_(doc_ids))).all()
    )


def _is_payment_ready(doc: Document) -> bool:
    return (
        doc.review_status == "APPROVED"
        and doc.validation_status == "VALID"
        and not is_dup(doc)
        and doc.status not in {"PAID", "ON_HOLD"}
        and doc.total_amount is not None
        and doc.total_amount > 0
    )


def _ap_exception_rows(doc: Document, user: User) -> list[dict]:
    if doc.review_status == "REJECTED" or doc.status == "PAID":
        return []
    found: list[tuple[str, str, str]] = []
    if doc.validation_status in ("INVALID", "ERROR"):
        detail = "; ".join(str(e) for e in (doc.validation_errors or [])[:3]) or "Validation failed."
        found.append(("INVALID_INVOICE", "HIGH", detail))
    if is_dup(doc):
        found.append(("DUPLICATE_INVOICE", "HIGH", "Matches an earlier invoice (same vendor, number and amount)."))
    if doc.total_amount is None:
        found.append(("MISSING_AMOUNT", "HIGH", "No total amount could be read."))
    if doc.due_date is None and doc.validation_status != "ERROR":
        found.append(("MISSING_DUE_DATE", "MEDIUM", "No due date, so payment timing is unknown."))
    if doc.extraction_confidence is not None and float(doc.extraction_confidence) < LOW_CONFIDENCE_THRESHOLD:
        found.append(("LOW_CONFIDENCE", "MEDIUM", f"Extraction confidence is {float(doc.extraction_confidence):.0%}. Check the fields."))
    return [
        {
            "documentId": doc.id,
            "documentName": doc.name,
            "vendor": doc.vendor_name,
            "invoiceNumber": doc.invoice_number,
            "amount": amount_of(doc),
            "code": code,
            "severity": severity,
            "detail": detail,
        }
        for code, severity, detail in found
    ]


@router.get("/accounts-payable/exceptions")
def ap_exceptions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = _payable_docs(db, user)
    rows = [r for d in docs for r in _ap_exception_rows(d, user)]
    resolved = {}
    if rows:
        for res in db.scalars(
            select(WorkflowResolution).where(
                WorkflowResolution.scope == "AP_EXCEPTION",
                WorkflowResolution.document_id.in_([r["documentId"] for r in rows]),
            )
        ).all():
            resolved[(res.document_id, res.item_key)] = res
    for r in rows:
        res = resolved.get((r["documentId"], r["code"]))
        r["status"] = "RESOLVED" if res else "OPEN"
        r["resolutionNote"] = res.note if res else None
        r["resolvedAt"] = iso(res.resolved_at) if res else None
    rows.sort(key=lambda r: (r["status"] != "OPEN", {"HIGH": 0, "MEDIUM": 1}.get(r["severity"], 2), r["documentId"]))
    return {
        "exceptions": rows,
        "openCount": sum(1 for r in rows if r["status"] == "OPEN"),
        "resolvedCount": sum(1 for r in rows if r["status"] == "RESOLVED"),
    }


class ResolveExceptionBody(BaseModel):
    document_id: int
    code: str = Field(min_length=1, max_length=60)
    note: str | None = Field(default=None, max_length=2000)
    reopen: bool = False


@router.post("/accounts-payable/exceptions/resolve")
def ap_resolve_exception(
    body: ResolveExceptionBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    doc = get_doc(db, user, body.document_id)
    if body.code not in {r["code"] for r in _ap_exception_rows(doc, user)}:
        raise HTTPException(status_code=404, detail="That exception no longer applies to this document.")
    existing = db.scalars(
        select(WorkflowResolution).where(
            WorkflowResolution.scope == "AP_EXCEPTION",
            WorkflowResolution.document_id == doc.id,
            WorkflowResolution.item_key == body.code,
        )
    ).first()
    if body.reopen:
        if existing:
            db.delete(existing)
        add_audit_event(db, doc.id, user.id, "AP_EXCEPTION_REOPENED", {"code": body.code}, owner_id=doc.owner_id)
        db.commit()
        return {"status": "OPEN"}
    note = _note(body.note)
    if not note:
        raise HTTPException(status_code=422, detail="Add a short note explaining how this exception was resolved.")
    if existing is None:
        existing = WorkflowResolution(scope="AP_EXCEPTION", document_id=doc.id, item_key=body.code, status="RESOLVED")
        db.add(existing)
    existing.note, existing.resolved_by, existing.resolved_at = note, user.id, datetime.now(timezone.utc)
    add_audit_event(db, doc.id, user.id, "AP_EXCEPTION_RESOLVED", {"code": body.code}, reason=note, owner_id=doc.owner_id)
    db.commit()
    return {"status": "RESOLVED"}


@router.get("/accounts-payable/payment-ready")
def ap_payment_ready(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = _payable_docs(db, user)
    batched = _batched_ids(db, [d.id for d in docs])
    ready = [d for d in docs if _is_payment_ready(d) and d.id not in batched]
    return {
        "invoices": [_ready_row(d) for d in ready],
        "count": len(ready),
        "totalAmount": round(sum(float(d.total_amount) for d in ready), 2),
    }


def _ready_row(d: Document) -> dict:
    return {
        "documentId": d.id,
        "documentName": d.name,
        "vendor": d.vendor_name,
        "invoiceNumber": d.invoice_number,
        "invoiceDate": iso(d.invoice_date),
        "dueDate": iso(d.due_date),
        "accountCode": d.account_code,
        "amount": float(d.total_amount),
    }


def _batch_dict(b: PaymentBatch) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "paymentDate": iso(b.payment_date),
        "status": b.status,
        "itemCount": b.item_count,
        "totalAmount": float(b.total_amount),
        "createdAt": iso(b.created_at),
        "paidAt": iso(b.paid_at),
        "submittedBy": b.submitted_by,
        "submittedAt": iso(b.submitted_at),
        "approvedBy": b.approved_by,
        "approvedAt": iso(b.approved_at),
        "approvalNote": b.approval_note,
        "rejectedBy": b.rejected_by,
        "rejectedAt": iso(b.rejected_at),
        "rejectionReason": b.rejection_reason,
        "transferReference": b.transfer_reference,
        "bankName": b.bank_name,
        "transferDate": iso(b.transfer_date),
        "paymentProofReference": b.payment_proof_reference,
        "paymentProofFilename": b.payment_proof_filename,
    }


def _get_batch(db: Session, user: User, batch_id: int) -> PaymentBatch:
    batch = db.get(PaymentBatch, batch_id)
    can_view_all = user.can_review or user.role_name == "Chief Accountant"
    owner = db.get(User, batch.owner_id) if batch is not None else None
    if batch is None or owner is None or owner.tenant_id != user.tenant_id or (batch.owner_id != user.id and not can_view_all):
        raise HTTPException(status_code=404, detail="Payment batch not found.")
    return batch


@router.get("/accounts-payable/payment-batches")
def ap_batches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenant_user_ids = select(User.id).where(User.tenant_id == user.tenant_id)
    statement = select(PaymentBatch).where(PaymentBatch.owner_id.in_(tenant_user_ids)).order_by(PaymentBatch.created_at.desc(), PaymentBatch.id.desc())
    if not user.can_review and user.role_name != "Chief Accountant":
        statement = statement.where(PaymentBatch.owner_id == user.id)
    return {"batches": [_batch_dict(b) for b in db.scalars(statement).all()]}


class CreateBatchBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    payment_date: date
    document_ids: list[int] = Field(min_length=1, max_length=200)


class RejectBatchBody(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


@router.post("/accounts-payable/payment-batches", status_code=201)
def ap_create_batch(body: CreateBatchBody, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User"))):
    ids = list(dict.fromkeys(body.document_ids))
    docs = {d.id: d for d in _payable_docs(db, user) if d.id in ids}
    batched = _batched_ids(db, ids)
    problems = [
        f"Document {i} is not available" if i not in docs
        else f"'{docs[i].name}' is not payment-ready (needs an approved, valid, non-duplicate invoice)" if not _is_payment_ready(docs[i])
        else f"'{docs[i].name}' is already in a payment batch"
        for i in ids
        if i not in docs or not _is_payment_ready(docs[i]) or i in batched
    ]
    if problems:
        raise HTTPException(status_code=422, detail="; ".join(problems[:5]))

    total = sum((docs[i].total_amount for i in ids), Decimal("0"))
    batch = PaymentBatch(
        owner_id=user.id, name=body.name.strip(), payment_date=body.payment_date,
        item_count=len(ids), total_amount=total,
    )
    db.add(batch)
    try:
        db.flush()
        for i in ids:
            db.add(PaymentBatchItem(batch_id=batch.id, document_id=i, amount=docs[i].total_amount))
            add_audit_event(db, i, user.id, "ADDED_TO_PAYMENT_BATCH", {"batchId": batch.id}, owner_id=docs[i].owner_id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="One of these invoices was just added to another batch. Refresh and retry.") from exc
    db.refresh(batch)
    return _batch_dict(batch)


@router.post("/accounts-payable/payment-batches/{batch_id}/submit")
def ap_submit_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Finance User")),
):
    batch = _get_batch(db, user, batch_id)
    if batch.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the batch creator can submit it.")
    if batch.status != "DRAFT":
        raise HTTPException(status_code=409, detail="Only draft batches can be submitted.")

    items = db.scalars(
        select(PaymentBatchItem).where(PaymentBatchItem.batch_id == batch.id)
    ).all()
    if not items:
        raise HTTPException(status_code=422, detail="This batch has no invoices.")

    documents = []
    for item in items:
        doc = db.get(Document, item.document_id)
        if (
            doc is None
            or not _is_payment_ready(doc)
            or Decimal(str(doc.total_amount)) != Decimal(str(item.amount))
        ):
            raise HTTPException(
                status_code=409,
                detail="A batch invoice is no longer payment-ready or its amount changed. Refresh the batch.",
            )
        documents.append(doc)

    now = datetime.now(timezone.utc)
    batch.status = "PENDING_CA_APPROVAL"
    batch.submitted_by = user.id
    batch.submitted_at = now

    for doc in documents:
        add_audit_event(
            db, doc.id, user.id, "PAYMENT_BATCH_SUBMITTED",
            {"batchId": batch.id, "batchName": batch.name},
            owner_id=doc.owner_id,
        )

    notify_roles(db, user.tenant_id, {"Chief Accountant"}, "AP_BATCH_APPROVAL", "AP payment batch awaiting approval", f"Payment batch '{batch.name}' is awaiting your approval.", "/employees/accounts-payable")
    db.commit()
    db.refresh(batch)
    return _batch_dict(batch)


@router.post("/accounts-payable/payment-batches/{batch_id}/approve")
def ap_approve_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Chief Accountant")),
):
    batch = _get_batch(db, user, batch_id)
    if batch.status != "PENDING_CA_APPROVAL":
        raise HTTPException(status_code=409, detail="This batch is not awaiting Chief Accountant approval.")
    if batch.submitted_by == user.id:
        raise HTTPException(status_code=403, detail="The batch submitter cannot approve the same batch.")

    items = db.scalars(
        select(PaymentBatchItem).where(PaymentBatchItem.batch_id == batch.id)
    ).all()
    if not items:
        raise HTTPException(status_code=422, detail="This batch has no invoices.")

    documents = []
    for item in items:
        doc = db.get(Document, item.document_id)
        if (
            doc is None
            or not _is_payment_ready(doc)
            or Decimal(str(doc.total_amount)) != Decimal(str(item.amount))
        ):
            raise HTTPException(
                status_code=409,
                detail="A batch invoice is no longer payment-ready or its amount changed. Approval is blocked.",
            )
        documents.append(doc)

    now = datetime.now(timezone.utc)
    batch.status = "APPROVED"
    batch.approved_by = user.id
    batch.approved_at = now
    batch.approval_note = "Approved by Chief Accountant"

    for doc in documents:
        add_audit_event(
            db, doc.id, user.id, "PAYMENT_BATCH_APPROVED",
            {"batchId": batch.id, "approvedBy": user.id},
            owner_id=doc.owner_id,
        )

    creator = db.get(User, batch.owner_id)
    notify_user(db, creator, "AP_BATCH_APPROVED", "AP payment batch approved", f"Your payment batch '{batch.name}' was approved by the Chief Accountant.", "/employees/accounts-payable")
    db.commit()
    db.refresh(batch)
    return _batch_dict(batch)


@router.post("/accounts-payable/payment-batches/{batch_id}/reject")
def ap_reject_batch(
    batch_id: int,
    body: RejectBatchBody,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Chief Accountant")),
):
    batch = _get_batch(db, user, batch_id)
    if batch.status != "PENDING_CA_APPROVAL":
        raise HTTPException(status_code=409, detail="This batch is not awaiting Chief Accountant approval.")
    if batch.submitted_by == user.id:
        raise HTTPException(status_code=403, detail="The batch submitter cannot reject the same batch.")

    reason = body.reason.strip()
    if len(reason) < 3:
        raise HTTPException(status_code=422, detail="Provide a meaningful rejection reason.")

    items = db.scalars(
        select(PaymentBatchItem).where(PaymentBatchItem.batch_id == batch.id)
    ).all()

    batch.status = "REJECTED"
    batch.rejected_by = user.id
    batch.rejected_at = datetime.now(timezone.utc)
    batch.rejection_reason = reason

    for item in items:
        doc = db.get(Document, item.document_id)
        if doc:
            add_audit_event(
                db, doc.id, user.id, "PAYMENT_BATCH_REJECTED",
                {"batchId": batch.id}, reason=reason, owner_id=doc.owner_id,
            )

    creator = db.get(User, batch.owner_id)
    notify_user(db, creator, "AP_BATCH_REJECTED", "AP payment batch rejected", f"Your payment batch '{batch.name}' was rejected. Reason: {reason}", "/employees/accounts-payable")
    db.commit()
    db.refresh(batch)
    return _batch_dict(batch)


@router.get("/accounts-payable/payment-batches/{batch_id}/export")
def ap_export_batch(batch_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = _get_batch(db, user, batch_id)
    rows = db.execute(
        select(PaymentBatchItem, Document)
        .join(Document, Document.id == PaymentBatchItem.document_id)
        .where(PaymentBatchItem.batch_id == batch.id)
        .order_by(Document.vendor_name, Document.invoice_number)
    ).all()
    items = [
        {
            "vendor": d.vendor_name, "invoiceNumber": d.invoice_number, "invoiceDate": iso(d.invoice_date),
            "dueDate": iso(d.due_date), "accountCode": d.account_code, "amount": float(i.amount), "documentName": d.name,
        }
        for i, d in rows
    ]
    return xlsx_response(exports.payment_batch_xlsx(_batch_dict(batch), items), f"{batch.name}.xlsx")


class ManualPaymentConfirmation(BaseModel):
    transfer_reference: str = Field(min_length=4, max_length=120)
    bank_name: str | None = Field(default=None, max_length=120)
    transfer_date: date
    payment_proof_reference: str | None = Field(default=None, max_length=500)


@router.post("/accounts-payable/payment-batches/{batch_id}/payment-proof")
async def ap_upload_payment_proof(
    batch_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Finance User")),
):
    batch = _get_batch(db, user, batch_id)
    if batch.owner_id != user.id or batch.status != "APPROVED":
        raise HTTPException(status_code=409, detail="Only the batch owner can upload proof for a Chief Accountant-approved batch.")
    filename = (file.filename or "").replace("\\", "/").split("/")[-1].strip()
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = {"pdf", "png", "jpg", "jpeg"}
    if extension not in allowed:
        raise HTTPException(status_code=415, detail="Payment proof must be a PDF, PNG or JPEG file.")
    content = await file.read(5 * 1024 * 1024 + 1)
    await file.close()
    if not content or len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payment proof must be between 1 byte and 5 MB.")
    valid_signature = (
        (extension == "pdf" and content.startswith(b"%PDF-"))
        or (extension == "png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
        or (extension in {"jpg", "jpeg"} and content.startswith(b"\xff\xd8\xff"))
    )
    if not valid_signature:
        raise HTTPException(status_code=415, detail="The uploaded file content does not match its PDF/PNG/JPEG extension.")
    path, _ = build_object_path("payment-proofs", user.id, filename)
    try:
        bucket = storage.bucket
        storage.upload(path, content, file.content_type or "application/octet-stream")
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    old_path = batch.payment_proof_path
    batch.payment_proof_bucket = bucket
    batch.payment_proof_path = path
    batch.payment_proof_filename = filename[:255]
    batch.payment_proof_reference = path
    db.commit()
    if old_path:
        try:
            storage.delete(old_path)
        except StorageError:
            logger.warning("Old payment proof could not be removed for batch %s", batch.id)
    return {"uploaded": True, "filename": batch.payment_proof_filename}


@router.get("/accounts-payable/payment-batches/{batch_id}/payment-proof")
def ap_payment_proof_url(batch_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    batch = _get_batch(db, user, batch_id)
    if user.role_name not in {"Finance User", "Finance Manager", "Chief Accountant", "Administrator"}:
        raise HTTPException(status_code=403, detail="You cannot access payment evidence.")
    if not batch.payment_proof_path:
        raise HTTPException(status_code=404, detail="No payment proof has been uploaded.")
    try:
        url = storage.create_signed_url(batch.payment_proof_path, expires_in=120, download_name=batch.payment_proof_filename)
    except StorageError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"url": url, "expiresIn": 120, "filename": batch.payment_proof_filename}


@router.post("/accounts-payable/payment-batches/{batch_id}/mark-paid")
def ap_mark_paid(
    batch_id: int,
    body: ManualPaymentConfirmation,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Finance User")),
):
    batch = _get_batch(db, user, batch_id)
    if batch.status != "APPROVED":
        raise HTTPException(
            status_code=409,
            detail="Only Chief Accountant-approved batches can be marked as paid.",
        )
    if not batch.payment_proof_path:
        raise HTTPException(status_code=409, detail="Upload the actual bank transfer proof before marking this batch paid.")
    if batch.approved_by is None:
        raise HTTPException(status_code=409, detail="Chief Accountant approval record is missing.")
    if batch.approved_by == user.id:
        raise HTTPException(status_code=403, detail="The batch approver cannot execute the same payment.")
    items = db.scalars(select(PaymentBatchItem).where(PaymentBatchItem.batch_id == batch.id)).all()
    documents = []
    for item in items:
        doc = db.get(Document, item.document_id)
        if doc is None or not _is_payment_ready(doc) or Decimal(str(doc.total_amount)) != Decimal(str(item.amount)):
            raise HTTPException(status_code=409, detail="A batch invoice is no longer payment-ready or its amount changed. No payment was posted.")
        documents.append((item, doc))
    # Validate and create all journal entries in the same DB transaction as the paid state.
    for item, doc in documents:
        posting.post_ap_payment(db, doc.owner_id, doc.id, batch.payment_date, Decimal(str(item.amount)), doc.vendor_name)
    for item, doc in documents:
        doc.status = "PAID"
        # NEW: mirror batch payment audit details onto every source invoice.
        doc.paid_by = user.id
        doc.paid_at = datetime.now(timezone.utc)
        doc.payment_amount = Decimal(str(item.amount))
        doc.payment_reference = body.transfer_reference.strip()
        doc.payment_bank_name = body.bank_name.strip() if body.bank_name else None
        doc.payment_date = body.transfer_date
        doc.ledger_voucher_no = f"AP-PAY-{doc.id}"
        add_audit_event(db, doc.id, user.id, "PAYMENT_BATCH_PAID_AND_POSTED", {
            "batchId": batch.id, "voucher": f"AP-PAY-{doc.id}",
            "amount": str(item.amount), "paid_by": user.id,
            "transfer_reference": body.transfer_reference.strip(),
            "bank_name": body.bank_name.strip() if body.bank_name else None,
            "payment_date": body.transfer_date.isoformat(),
            "ledger_source_document_id": doc.id,
        }, owner_id=doc.owner_id)
    batch.status, batch.paid_at, batch.paid_by = "PAID", datetime.now(timezone.utc), user.id
    batch.transfer_reference = body.transfer_reference.strip()
    batch.bank_name = body.bank_name.strip() if body.bank_name else None
    batch.transfer_date = body.transfer_date
    batch.payment_proof_reference = body.payment_proof_reference.strip() if body.payment_proof_reference else None
    for _, doc in documents:
        notify_user(db, doc.owner, "AP_INVOICE_PAID", "Supplier invoice payment recorded", f"Supplier invoice '{doc.name}' has been marked paid. Transfer reference: {batch.transfer_reference}.", "/employees/accounts-payable")
    db.commit()
    return _batch_dict(batch)


@router.post("/accounts-payable/payment-batches/{batch_id}/cancel")
def ap_cancel_batch(
    batch_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("Finance User")),
):
    batch = _get_batch(db, user, batch_id)
    if batch.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only the batch creator can cancel it.")
    if batch.status not in {"DRAFT", "REJECTED"}:
        raise HTTPException(
            status_code=409,
            detail="Only draft or rejected batches can be cancelled.",
        )

    items = db.scalars(
        select(PaymentBatchItem).where(PaymentBatchItem.batch_id == batch.id)
    ).all()

    for item in items:
        doc = db.get(Document, item.document_id)
        if doc:
            add_audit_event(
                db, doc.id, user.id, "PAYMENT_BATCH_CANCELLED",
                {"batchId": batch.id, "previousStatus": batch.status},
                owner_id=doc.owner_id,
            )

    db.execute(delete(PaymentBatchItem).where(PaymentBatchItem.batch_id == batch.id))
    db.delete(batch)
    db.commit()
    return {"cancelled": True}


# ============================================================ Accounts Receivable
def _open_receivables(db: Session, user: User) -> list[Document]:
    return [
        d for d in visible_docs(db, user, AR_CATEGORIES)
        if d.status != "PAID" and d.review_status != "REJECTED" and d.total_amount is not None
    ]


def _ar_dict(d: Document) -> dict:
    return {
        "id": d.id, "name": d.name, "party": d.vendor_name, "invoice_number": d.invoice_number,
        "amount": amount_of(d), "due_date": d.due_date,
    }


@router.get("/accounts-receivable/priorities")
def ar_priorities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = _open_receivables(db, user)
    rows = receivables.priority_rows([_ar_dict(d) for d in docs], today())
    ids = [r["documentId"] for r in rows]
    disputed = set(
        db.scalars(
            select(DisputeCase.document_id).where(DisputeCase.document_id.in_(ids), DisputeCase.status != "RESOLVED")
        ).all()
    ) if ids else set()
    for r in rows:
        r["hasOpenDispute"] = r["documentId"] in disputed
    return {
        "priorities": rows,
        "openBalance": round(sum(r["amount"] for r in rows), 2),
        "overdueBalance": round(sum(r["amount"] for r in rows if r["daysOverdue"] > 0), 2),
        "method": "Score = urgency (days overdue) + size (share of the largest open balance). Computed, not AI-estimated.",
    }


@router.get("/accounts-receivable/cash-forecast")
def ar_cash_forecast(
    delay_days: int = Query(default=0, ge=0, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    docs = _open_receivables(db, user)
    return receivables.cash_forecast_weeks([_ar_dict(d) for d in docs], today(), 12, delay_days)


@router.post("/accounts-receivable/documents/{document_id}/collected")
def ar_mark_collected(document_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles("Finance User"))):
    doc = get_doc(db, user, document_id)
    if (doc.category or "").strip().lower() not in AR_CATEGORIES or doc.total_amount is None or doc.total_amount <= 0:
        raise HTTPException(status_code=422, detail="Only receivable documents with a positive total can be marked as collected.")
    if doc.status == "ON_HOLD":
        raise HTTPException(status_code=409, detail="This receivable is on fraud-review hold and cannot be collected until Admin resolves the alert.")
    if doc.status == "PAID":
        raise HTTPException(status_code=409, detail="This receivable is already marked as collected.")
    posting.post_ar_collection(db, doc.owner_id, doc.id, today(), Decimal(str(doc.total_amount)), doc.vendor_name)
    doc.status = "PAID"
    add_audit_event(db, doc.id, user.id, "RECEIVABLE_COLLECTED_AND_POSTED", {"voucher": f"AR-COLLECT-{doc.id}"}, owner_id=doc.owner_id)
    db.commit()
    return {"status": doc.status, "voucher": f"AR-COLLECT-{doc.id}"}


def _reminder_dict(r: CollectionReminder, doc: Document | None) -> dict:
    return {
        "id": r.id, "documentId": r.document_id, "documentName": doc.name if doc else None,
        "customer": doc.vendor_name if doc else None, "stage": r.stage, "subject": r.subject, "body": r.body,
        "aiGenerated": r.ai_generated, "status": r.status, "createdAt": iso(r.created_at), "sentAt": iso(r.sent_at),
    }


@router.get("/accounts-receivable/reminders")
def ar_reminders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(CollectionReminder).order_by(CollectionReminder.created_at.desc(), CollectionReminder.id.desc()).limit(100)
    if not user.can_review:
        statement = statement.where(CollectionReminder.owner_id == user.id)
    reminders = db.scalars(statement).all()
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_([r.document_id for r in reminders]))).all()} if reminders else {}
    return {"reminders": [_reminder_dict(r, docs.get(r.document_id)) for r in reminders]}


class GenerateReminderBody(BaseModel):
    document_id: int
    use_ai: bool = False


@router.post("/accounts-receivable/reminders/generate", status_code=201)
def ar_generate_reminder(body: GenerateReminderBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = get_doc(db, user, body.document_id)
    if (doc.category or "").strip().lower() not in AR_CATEGORIES or doc.total_amount is None:
        raise HTTPException(status_code=422, detail="Reminders are drafted for receivable documents that have a total amount.")
    stage = receivables.stage_for(doc.due_date, today())
    draft = receivables.reminder_draft(stage, doc.vendor_name or "Customer", doc.invoice_number, float(doc.total_amount), doc.due_date)
    ai = False
    if body.use_ai:
        polished = gemini_text(
            "Rewrite this payment reminder email to be polite and professional. Keep every fact, name, "
            "invoice number and amount EXACTLY as written; do not add numbers or promises. Return only the email body.\n\n"
            + draft["body"]
        )
        if polished and (doc.invoice_number or "") in polished:
            draft["body"], ai = polished, True
    reminder = CollectionReminder(
        owner_id=user.id, document_id=doc.id, stage=stage, subject=draft["subject"], body=draft["body"], ai_generated=ai,
    )
    db.add(reminder)
    add_audit_event(db, doc.id, user.id, "REMINDER_DRAFTED", {"stage": stage, "ai": ai}, owner_id=doc.owner_id)
    db.commit()
    db.refresh(reminder)
    return _reminder_dict(reminder, doc)


@router.post("/accounts-receivable/reminders/{reminder_id}/mark-sent")
def ar_mark_reminder_sent(reminder_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    reminder = db.get(CollectionReminder, reminder_id)
    if reminder is None or (reminder.owner_id != user.id and not user.can_review):
        raise HTTPException(status_code=404, detail="Reminder not found.")
    reminder.status, reminder.sent_at = "MARKED_SENT", datetime.now(timezone.utc)
    db.commit()
    return _reminder_dict(reminder, db.get(Document, reminder.document_id))


def _dispute_dict(c: DisputeCase) -> dict:
    return {
        "id": c.id, "documentId": c.document_id, "customer": c.customer_name,
        "amount": float(c.amount) if c.amount is not None else None, "reason": c.reason, "status": c.status,
        "resolutionNote": c.resolution_note, "createdAt": iso(c.created_at), "updatedAt": iso(c.updated_at),
    }


@router.get("/accounts-receivable/disputes")
def ar_disputes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    statement = select(DisputeCase).order_by(DisputeCase.updated_at.desc(), DisputeCase.id.desc())
    if not user.can_review:
        statement = statement.where(DisputeCase.owner_id == user.id)
    return {"disputes": [_dispute_dict(c) for c in db.scalars(statement).all()]}


class CreateDisputeBody(BaseModel):
    document_id: int | None = None
    customer_name: str | None = Field(default=None, max_length=255)
    amount: Decimal | None = Field(default=None, ge=0)
    reason: str = Field(min_length=3, max_length=2000)


@router.post("/accounts-receivable/disputes", status_code=201)
def ar_create_dispute(body: CreateDisputeBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customer, amount = _note(body.customer_name), body.amount
    if body.document_id is not None:
        doc = get_doc(db, user, body.document_id)
        customer = customer or doc.vendor_name
        amount = amount if amount is not None else doc.total_amount
        add_audit_event(db, doc.id, user.id, "DISPUTE_OPENED", {}, reason=body.reason, owner_id=doc.owner_id)
    if not customer:
        raise HTTPException(status_code=422, detail="Enter the customer name (or link a document that has one).")
    case = DisputeCase(owner_id=user.id, document_id=body.document_id, customer_name=customer, amount=amount, reason=body.reason.strip())
    db.add(case)
    db.commit()
    db.refresh(case)
    return _dispute_dict(case)


class UpdateDisputeBody(BaseModel):
    status: str = Field(pattern="^(OPEN|IN_REVIEW|RESOLVED)$")
    resolution_note: str | None = Field(default=None, max_length=2000)


@router.patch("/accounts-receivable/disputes/{dispute_id}")
def ar_update_dispute(
    dispute_id: int, body: UpdateDisputeBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    case = db.get(DisputeCase, dispute_id)
    if case is None or (case.owner_id != user.id and not user.can_review):
        raise HTTPException(status_code=404, detail="Dispute case not found.")
    note = _note(body.resolution_note)
    if body.status == "RESOLVED" and not note:
        raise HTTPException(status_code=422, detail="Add a resolution note before closing the dispute.")
    case.status, case.resolution_note = body.status, note or case.resolution_note
    case.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _dispute_dict(case)


# ============================================================== Invoice Processing
def _chart(db: Session, user: User) -> list[dict]:
    return [
        {"code": a.code, "name": a.name, "type": a.account_type}
        for a in db.scalars(select(LedgerAccount).where(LedgerAccount.owner_id == user.id).order_by(LedgerAccount.code)).all()
    ]


@router.get("/invoice-processing/chart-of-accounts")
def ip_chart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"accounts": _chart(db, user)}


@router.post("/invoice-processing/chart-of-accounts/load-default", status_code=201)
def ip_load_default_chart(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if db.scalar(select(func.count()).select_from(LedgerAccount).where(LedgerAccount.owner_id == user.id)):
        raise HTTPException(status_code=409, detail="You already have a chart of accounts. Import a ledger workbook to replace it.")
    for code, name, kind in coding.DEFAULT_CHART:
        db.add(LedgerAccount(owner_id=user.id, code=code, name=name, account_type=kind))
    db.commit()
    return {"accounts": _chart(db, user)}


class SuggestCodingBody(BaseModel):
    use_ai: bool = False


@router.post("/invoice-processing/documents/{document_id}/coding/suggest")
def ip_suggest_coding(
    document_id: int, body: SuggestCodingBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    doc = get_doc(db, user, document_id)
    chart = _chart(db, user)
    if not chart:
        raise HTTPException(status_code=422, detail="Load or import a chart of accounts first. Suggestions only use your own accounts.")
    text = f"{doc.vendor_name or ''} {doc.name}"
    suggestion = None if body.use_ai else coding.suggest_account_by_keywords(text, chart)
    if suggestion is None:
        try:
            suggestion = coding.suggest_account_with_gemini(text, chart)
        except Exception:  # noqa: BLE001
            logger.warning("AI coding suggestion failed", exc_info=True)
    if suggestion is None:
        raise HTTPException(status_code=404, detail="No suitable account found for this invoice. Choose one manually.")
    doc.suggested_account_code, doc.suggested_account_name = suggestion["code"], suggestion["name"]
    doc.coding_confidence, doc.coding_source, doc.coding_status = Decimal(str(suggestion["confidence"])), suggestion["source"], "SUGGESTED"
    add_audit_event(db, doc.id, user.id, "CODING_SUGGESTED", suggestion, owner_id=doc.owner_id)
    db.commit()
    return {"suggestion": suggestion}


class AcceptCodingBody(BaseModel):
    account_code: str = Field(min_length=1, max_length=30)


@router.post("/invoice-processing/documents/{document_id}/coding/accept")
def ip_accept_coding(
    document_id: int, body: AcceptCodingBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    doc = get_doc(db, user, document_id)
    account = next((a for a in _chart(db, user) if a["code"] == body.account_code.strip()), None)
    if account is None:
        raise HTTPException(status_code=422, detail="That account is not in your chart of accounts.")
    changed = doc.suggested_account_code is not None and doc.suggested_account_code != account["code"]
    doc.account_code = account["code"]
    doc.coding_status = "CHANGED" if changed or doc.suggested_account_code is None else "ACCEPTED"
    add_audit_event(db, doc.id, user.id, "CODING_ACCEPTED", {"accountCode": account["code"], "status": doc.coding_status}, owner_id=doc.owner_id)
    db.commit()
    return {"accountCode": doc.account_code, "accountName": account["name"], "codingStatus": doc.coding_status}


# ================================================================== Reconciliation
def _latest_run(db: Session, user: User, document_id: int) -> tuple[Document, ReconciliationRun]:
    doc = db.scalars(select(Document).where(Document.id == document_id, Document.owner_id == user.id)).first()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    run = db.scalars(
        select(ReconciliationRun)
        .where(ReconciliationRun.document_id == doc.id, ReconciliationRun.owner_id == user.id)
        .order_by(ReconciliationRun.created_at.desc(), ReconciliationRun.id.desc())
    ).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run a reconciliation for this document first.")
    return doc, run


def _recon_state(db: Session, doc: Document, run: ReconciliationRun) -> tuple[list[dict], dict]:
    resolutions = {
        r.item_key: {"status": r.status, "note": r.note, "resolvedAt": iso(r.resolved_at)}
        for r in db.scalars(
            select(WorkflowResolution).where(WorkflowResolution.scope == "RECON_ITEM", WorkflowResolution.document_id == doc.id)
        ).all()
    }
    rows = recon_exceptions.flatten_exceptions(run.results or {}, resolutions)
    return rows, recon_exceptions.statement_totals(run.results or {}, rows)


@router.get("/reconciliation/{document_id}/exceptions")
def recon_exception_list(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc, run = _latest_run(db, user, document_id)
    rows, totals = _recon_state(db, doc, run)
    return {"documentId": doc.id, "documentName": doc.name, "runId": run.id, "exceptions": rows, "totals": totals}


class ResolveReconBody(BaseModel):
    item_key: str = Field(min_length=3, max_length=120)
    status: str = Field(pattern="^(OPEN|RESOLVED|WRITTEN_OFF)$")
    note: str | None = Field(default=None, max_length=2000)


@router.post("/reconciliation/{document_id}/exceptions/resolve")
def recon_resolve_exception(
    document_id: int, body: ResolveReconBody, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    doc, run = _latest_run(db, user, document_id)
    rows, _ = _recon_state(db, doc, run)
    if body.item_key not in {r["itemKey"] for r in rows}:
        raise HTTPException(status_code=404, detail="That item is not in the latest reconciliation run.")
    existing = db.scalars(
        select(WorkflowResolution).where(
            WorkflowResolution.scope == "RECON_ITEM",
            WorkflowResolution.document_id == doc.id,
            WorkflowResolution.item_key == body.item_key,
        )
    ).first()
    if body.status == "OPEN":
        if existing:
            db.delete(existing)
    else:
        note = _note(body.note)
        if not note:
            raise HTTPException(status_code=422, detail="Add a note explaining the resolution.")
        if existing is None:
            existing = WorkflowResolution(scope="RECON_ITEM", document_id=doc.id, item_key=body.item_key, status=body.status)
            db.add(existing)
        existing.status, existing.note = body.status, note
        existing.resolved_by, existing.resolved_at = user.id, datetime.now(timezone.utc)
    add_audit_event(db, doc.id, user.id, "RECON_EXCEPTION_" + body.status, {"itemKey": body.item_key}, reason=_note(body.note), owner_id=doc.owner_id)
    db.commit()
    rows, totals = _recon_state(db, doc, run)
    return {"exceptions": rows, "totals": totals}


@router.get("/reconciliation/{document_id}/statement")
def recon_statement(document_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc, run = _latest_run(db, user, document_id)
    rows, totals = _recon_state(db, doc, run)
    content = exports.reconciliation_statement_xlsx(doc.name, run.summary or {}, totals, rows, (run.results or {}).get("matched", []))
    return xlsx_response(content, f"Reconciliation statement - {doc.name}.xlsx")
