
import csv
import hashlib
import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from openpyxl import load_workbook
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.document_audit_event import DocumentAuditEvent
from app.models.ledger import LedgerAccount
from app.models.user import User
from app.services.posting import post_ap_payment
from app.services.notifications import notify_user, notify_roles
from app.services.document_classifier import (
    classify_document,
    extract_document_text,
)
from app.services.invoice_extractor import (
    extract_invoice,
    extract_structured_invoice_spreadsheet,
)
from app.services.coding import suggest_account_by_keywords
from app.services import invoice_edit
from app.services.duplicate_detection import normalize_invoice_number, normalize_vendor_identity, sha256_document
from app.services.confidence import LOW_CONFIDENCE_THRESHOLD, compute_extraction_confidence
from app.services.storage import (
    DOCUMENTS_PREFIX,
    StorageError,
    StorageNotConfigured,
    StorageObjectNotFound,
    build_object_path,
    path_belongs_to,
    storage,
)

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


MAX_FILE_SIZE = 10 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".csv",
    ".xls",
    ".xlsx",
    ".xlsm",
    ".docx",
}


AP_DOCUMENT_CATEGORIES = {"accounts payable", "invoice", "invoices"}
AP_WORKFLOW_ROLES = {"Finance User", "Chief Accountant"}


def is_ap_document(document: Document) -> bool:
    return (document.category or "").strip().lower() in AP_DOCUMENT_CATEGORIES


def can_access_document(user: User, document: Document) -> bool:
    # Documents inherit tenant scope through their owner; never grant cross-company access.
    owner = document.owner
    if owner is None or owner.tenant_id != user.tenant_id:
        return False
    if document.owner_id == user.id:
        return True
    category = (document.category or "").strip().lower()
    if category in {"accounts payable", "invoice", "invoices", "expense", "expenses", "accounts receivable", "receivables", "sales invoice"}:
        return user.role_name in {"Finance User", "Finance Manager", "Chief Accountant", "Administrator"}
    return document.owner_id == user.id or user.role_name in {"Finance Manager", "Chief Accountant", "Administrator"}

def is_reconciliation_workbook(content: bytes, extension: str) -> bool:
    """Return True only for workbooks with both required reconciliation sheets."""
    if extension.lower() not in {".xlsx", ".xlsm"}:
        return False

    workbook = None
    try:
        workbook = load_workbook(
            BytesIO(content),
            read_only=True,
            data_only=True,
        )
        return (
            "Company Cashbook" in workbook.sheetnames
            and "Bank Statement" in workbook.sheetnames
        )
    except Exception:
        logger.warning("Could not inspect workbook structure", exc_info=True)
        return False
    finally:
        if workbook is not None:
            workbook.close()


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def serialize_document(document: Document) -> dict:
    uploaded_at = document.created_at

    if uploaded_at.tzinfo is None:
        uploaded_at = uploaded_at.replace(tzinfo=timezone.utc)

    reviewed_at = document.reviewed_at

    if reviewed_at and reviewed_at.tzinfo is None:
        reviewed_at = reviewed_at.replace(tzinfo=timezone.utc)

    return {
        "id": document.id,
        "name": document.name,
        "supersedesDocumentId": document.supersedes_document_id,
        "type": Path(document.name).suffix.lstrip(".").upper() or "FILE",
        "size": format_size(document.size_bytes),
        "sizeBytes": document.size_bytes,
        "category": document.category,
        "uploadedAt": uploaded_at.strftime("%d %b %Y"),
        "status": document.status,
        "vendorName": document.vendor_name,
        "invoiceNumber": document.invoice_number,
        "invoiceDate": (
            document.invoice_date.isoformat()
            if document.invoice_date else None
        ),
        "dueDate": (
            document.due_date.isoformat()
            if document.due_date else None
        ),
        "subtotal": (
            str(document.subtotal)
            if document.subtotal is not None else None
        ),
        "taxAmount": (
            str(document.tax_amount)
            if document.tax_amount is not None else None
        ),
        "totalAmount": (
            str(document.total_amount)
            if document.total_amount is not None else None
        ),
        "extractedInvoiceDetails": document.extracted_invoice_details or {},
        "lineItems": document.line_items or [],
        "validationStatus": document.validation_status,
        "validationErrors": document.validation_errors or [],
        "isDuplicate": document.is_duplicate,
        "duplicateHash": document.duplicate_hash,
        "duplicateOfId": document.duplicate_of_id,
        "duplicateScore": float(document.duplicate_score) if document.duplicate_score is not None else None,
        "duplicateMatchType": document.duplicate_match_type,
        "duplicateOverridden": document.duplicate_overridden,
        "extractionConfidence": (
            float(document.extraction_confidence)
            if document.extraction_confidence is not None else None
        ),
        "lowConfidence": (
            document.extraction_confidence is not None
            and float(document.extraction_confidence) < LOW_CONFIDENCE_THRESHOLD
        ),
        "fieldConfidence": document.field_confidence or {},
        "suggestedAccountCode": document.suggested_account_code,
        "suggestedAccountName": document.suggested_account_name,
        "codingConfidence": (
            float(document.coding_confidence)
            if document.coding_confidence is not None else None
        ),
        "codingSource": document.coding_source,
        "accountCode": document.account_code,
        "codingStatus": document.coding_status,
        "reviewStatus": document.review_status,
        "reviewedBy": document.reviewed_by,
        "reviewedAt": (
            reviewed_at.isoformat() if reviewed_at else None
        ),
        "rejectionReason": document.rejection_reason,
        "ownerId": document.owner_id,
        "ownerName": document.owner.full_name if document.owner else None,
        "uploaderRole": document.uploader_role or (document.owner.role_name if document.owner else None),
        "assignedFinanceUserId": document.assigned_finance_user_id,
        "assignedFinanceUserName": document.assigned_finance_user.full_name if document.assigned_finance_user else None,
        "firstReviewedBy": document.first_reviewed_by,
        "firstReviewedByName": document.first_reviewer.full_name if document.first_reviewer else None,
        "firstReviewedAt": document.first_reviewed_at.isoformat() if document.first_reviewed_at else None,
        "firstReviewAction": document.first_review_action,
        # NEW: explicit actor/timestamp fields for invoice audit drill-down.
        "verifiedBy": document.verified_by,
        "verifiedByName": document.verifier.full_name if document.verifier else None,
        "verifiedAt": document.verified_at.isoformat() if document.verified_at else None,
        "approvedBy": document.approved_by,
        "approvedByName": document.approver.full_name if document.approver else None,
        "approvedAt": document.approved_at.isoformat() if document.approved_at else None,
        "rejectedBy": document.rejected_by,
        "rejectedByName": document.rejector.full_name if document.rejector else None,
        "rejectedAt": document.rejected_at.isoformat() if document.rejected_at else None,
        "chiefAccountantApprovedBy": document.chief_accountant_approved_by,
        "chiefAccountantApprovedByName": document.chief_accountant_approver.full_name if document.chief_accountant_approver else None,
        "chiefAccountantApprovedAt": document.chief_accountant_approved_at.isoformat() if document.chief_accountant_approved_at else None,
        "paidBy": document.paid_by,
        "paidByName": document.payer.full_name if document.payer else None,
        "paidAt": document.paid_at.isoformat() if document.paid_at else None,
        "paymentAmount": str(document.payment_amount) if document.payment_amount is not None else None,
        "paymentReference": document.payment_reference,
        "paymentBankName": document.payment_bank_name,
        "paymentDate": document.payment_date.isoformat() if document.payment_date else None,
        "ledgerVoucherNo": document.ledger_voucher_no,
    }


REVIEW_ONLY_CATEGORIES = {"accounts receivable", "expense", "expenses"}


def add_audit_event(
    db: Session,
    document_id: int,
    user_id: int,
    action: str,
    details: dict | None = None,
    reason: str | None = None,
    owner_id: int | None = None,
) -> None:
    db.add(
        DocumentAuditEvent(
            document_id=document_id,
            owner_id=owner_id or user_id,
            actor_id=user_id,
            action=action,
            details=details or {},
            reason=reason,
        )
    )


def is_invoice_category(category: str | None) -> bool:
    normalized = (category or "").strip().lower()

    return (
        "invoice" in normalized
        or "accounts payable" in normalized
        or normalized in REVIEW_ONLY_CATEGORIES
    )


def detect_invoice_fallback(content: bytes, extension: str) -> bool:
    """Detect likely invoices when Gemini returns Uncategorized."""
    text = extract_document_text(content, extension).lower()

    invoice_signals = (
        "invoice number",
        "invoice no",
        "tax invoice",
        "bill to",
        "amount due",
        "subtotal",
        "gstin",
        "total amount",
    )

    signal_count = sum(
        signal in text for signal in invoice_signals
    )

    return "invoice" in text and signal_count >= 2


def _set_duplicate_match(document: Document, candidate: Document | None, match_type: str | None = None) -> None:
    document.is_duplicate = candidate is not None
    document.duplicate_of_id = candidate.id if candidate is not None else None
    document.duplicate_match_type = match_type if candidate is not None else None
    document.duplicate_score = Decimal("1.000") if candidate is not None else None
    if candidate is not None:
        document.validation_status = "DUPLICATE"
        document.review_status = "DUPLICATE"
        document.status = "NEEDS_REVIEW"


def find_duplicate_invoice(
    db: Session,
    document: Document,
    user_id: int,
) -> Document | None:
    """Find exact-file or business duplicates within the uploader's tenant.

    Hash matches take priority. Business matches require a normalized invoice
    number and compare vendor names when both are present.
    """
    owner = db.get(User, user_id)
    if owner is None:
        return None
    tenant_owner_ids = select(User.id).where(User.tenant_id == owner.tenant_id)
    candidates = db.scalars(
        select(Document).where(
            Document.owner_id.in_(tenant_owner_ids),
            Document.id != document.id,
        )
    ).all()

    # Exact file content is the strongest duplicate signal, independent of names.
    if document.duplicate_hash:
        for candidate in candidates:
            if candidate.duplicate_hash and candidate.duplicate_hash == document.duplicate_hash:
                return candidate

    invoice_identity = normalize_invoice_number(document.invoice_number)
    if not invoice_identity:
        return None
    vendor_identity = normalize_vendor_identity(document.vendor_name)
    for candidate in candidates:
        if normalize_invoice_number(candidate.invoice_number) != invoice_identity:
            continue
        candidate_vendor = normalize_vendor_identity(candidate.vendor_name)
        if vendor_identity and candidate_vendor and vendor_identity != candidate_vendor:
            continue
        # A known amount/date difference is retained as a possible business duplicate;
        # invoice identity is still strong, and these differences need human review.
        return candidate
    return None


def apply_invoice_extraction(
    db: Session,
    document: Document,
    extracted: dict,
    user_id: int,
    audit_action: str,
) -> None:
    """Apply extracted invoice fields and determine the review state."""
    document.vendor_name = extracted.get("vendor_name")
    document.invoice_number = extracted.get("invoice_number")
    document.invoice_date = extracted.get("invoice_date")
    document.due_date = extracted.get("due_date")
    document.subtotal = extracted.get("subtotal")
    document.tax_amount = extracted.get("tax_amount")
    document.total_amount = extracted.get("total_amount")
    document.extracted_invoice_details = extracted.get("invoice_details") or {}
    document.line_items = extracted.get("line_items") or []

    document.validation_status = extracted.get(
        "validation_status",
        "INVALID",
    )
    document.validation_errors = extracted.get(
        "validation_errors",
        [],
    )

    # Extraction confidence (deterministic checks blended with the model's own value).
    score, per_field, _reasons = compute_extraction_confidence(
        extracted,
        document.validation_errors,
        extracted.get("model_confidence"),
    )
    document.extraction_confidence = score
    document.field_confidence = per_field

    # Cheap keyword-based GL suggestion from the owner's own chart of accounts.
    # Never overrides a code a person already accepted or changed.
    if document.coding_status in (None, "NONE", "SUGGESTED"):
        try:
            chart = [
                {"code": a.code, "name": a.name, "type": a.account_type}
                for a in db.scalars(
                    select(LedgerAccount).where(LedgerAccount.owner_id == document.owner_id)
                ).all()
            ]
            hit = suggest_account_by_keywords(
                f"{document.vendor_name or ''} {document.name}", chart
            ) if chart else None
            if hit:
                document.suggested_account_code = hit["code"]
                document.suggested_account_name = hit["name"]
                document.coding_confidence = hit["confidence"]
                document.coding_source = hit["source"]
                document.coding_status = "SUGGESTED"
        except Exception:  # noqa: BLE001 - suggestion is optional
            logger.warning("Coding suggestion skipped", exc_info=True)

    # Recalculate duplicate status on every extraction.
    document.is_duplicate = False

    duplicate = find_duplicate_invoice(
        db,
        document,
        document.owner_id,
    )

    if duplicate is not None:
        match_type = "HASH" if document.duplicate_hash and duplicate.duplicate_hash == document.duplicate_hash else "BUSINESS"
        _set_duplicate_match(document, duplicate, match_type)

    else:
        _set_duplicate_match(document, None)

    if duplicate is None and document.validation_status == "VALID":
        document.review_status = "READY_FOR_REVIEW"
        document.status = "PENDING_REVIEW"

    elif duplicate is None:
        document.review_status = "NEEDS_CORRECTION"
        document.status = "NEEDS_REVIEW"

    # Accounts Receivable / Expense documents need a human decision even when
    # strict invoice validation reports gaps; validation errors stay visible.
    if (
        not document.is_duplicate
        and (document.category or "").strip().lower() in REVIEW_ONLY_CATEGORIES
        and document.review_status == "NEEDS_CORRECTION"
    ):
        document.review_status = "READY_FOR_REVIEW"
        document.status = "PENDING_REVIEW"

    add_audit_event(
        db,
        document.id,
        user_id,
        audit_action,
        {
            "validation_status": document.validation_status,
            "is_duplicate": document.is_duplicate,
            "review_status": document.review_status,
        },
        owner_id=document.owner_id,
    )


def mark_processing_failed(
    db: Session,
    document_id: int,
    user_id: int,
    action: str,
    message: str,
) -> None:
    """Retain the document and persist a truthful processing-failure state."""
    db.rollback()

    document = db.get(Document, document_id)

    if document is None:
        return

    approved_ap_invoice = is_ap_document(document) and document.review_status == "APPROVED"
    document.status = "NEEDS_REVIEW"
    document.validation_status = "ERROR"
    document.validation_errors = [message]
    document.review_status = "APPROVED" if approved_ap_invoice else "NOT_READY"

    add_audit_event(
        db,
        document_id,
        user_id,
        action,
        {"message": message},
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception(
            "Unable to save failure status for document %s",
            document_id,
        )


@router.get("")
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    statement = select(Document).where(
        Document.owner_id.in_(select(User.id).where(User.tenant_id == current_user.tenant_id))
    )

    role = current_user.role_name

    if role == "Finance User":
        statement = statement.where(
            (Document.owner_id == current_user.id)
            | func.lower(func.trim(Document.category)).in_({"accounts payable", "invoice", "invoices", "expense", "expenses"})
        )

    elif role == "Finance Manager":
        pass  # all document categories, but only within the current tenant
    elif role == "Chief Accountant":
        statement = statement.where(
            func.lower(func.trim(Document.category)).in_(AP_DOCUMENT_CATEGORIES | {"accounts receivable", "receivables", "sales invoice", "expense", "expenses"})
        )

    elif role != "Administrator" and not current_user.can_review:
        statement = statement.where(Document.owner_id == current_user.id)

    documents = db.scalars(statement).all()

    serialized = [serialize_document(document) for document in documents]
    for item, document in zip(serialized, documents):
        match_id = document.duplicate_of_id
        if not match_id:
            continue
        match = db.get(Document, match_id)
        if match is None or match.owner is None or match.owner.tenant_id != current_user.tenant_id:
            continue
        # Duplicate details are shown only if this caller is permitted to access the original.
        if not can_access_document(current_user, match):
            continue
        item["duplicateMatch"] = {
            "id": match.id,
            "name": match.name,
            "vendorName": match.vendor_name,
            "invoiceNumber": match.invoice_number,
            "invoiceDate": match.invoice_date.isoformat() if match.invoice_date else None,
            "totalAmount": str(match.total_amount) if match.total_amount is not None else None,
            "status": match.status,
            "isPaid": match.status == "PAID" or match.paid_at is not None,
            "ownerId": match.owner_id,
            "ownerName": match.owner.full_name if match.owner else None,
            "matchType": document.duplicate_match_type,
        }
    return serialized


async def _read_upload_limited(file: UploadFile) -> bytes:
    """Read the upload fully into memory, enforcing the size limit while reading."""
    buffer = bytearray()
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File size must not exceed 10 MB.")
    if not buffer:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    return bytes(buffer)


def _storage_http_error(exc: StorageError) -> HTTPException:
    if isinstance(exc, StorageNotConfigured):
        return HTTPException(status_code=503, detail="File storage is not configured on the server.")
    if isinstance(exc, StorageObjectNotFound):
        return HTTPException(
            status_code=404,
            detail="The stored file is missing from storage. Please re-upload the document.",
        )
    return HTTPException(
        status_code=502,
        detail="File storage is temporarily unavailable. Please try again.",
    )


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    workspace: str = Form(default=""),
    replaces_document_id: int | None = Form(default=None),
    assigned_finance_user_id: int | None = Form(default=None),  # NEW
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    workspace_key = workspace.strip().lower()
    role = current_user.role_name
    is_ap_upload = workspace_key == "accounts-payable"
    is_expense_upload = workspace_key in {"expense", "expense-employee"}
    is_invoice_upload = workspace_key == "invoice-processing"
    is_invoice_workflow_upload = is_ap_upload or is_invoice_upload

    if is_ap_upload and role not in {"Finance User", "Finance Manager", "Chief Accountant"}:
        raise HTTPException(status_code=403, detail="Only Finance User, Finance Manager or Chief Accountant can upload supplier invoices.")
    if is_expense_upload and role != "Employee / Requester":
        raise HTTPException(status_code=403, detail="Expense claims must be submitted from an Employee / Requester account.")
    if is_invoice_upload and role not in {"Employee / Requester", "Finance User", "Finance Manager", "Chief Accountant"}:
        raise HTTPException(status_code=403, detail="Your role cannot upload invoice-processing documents.")

    replaced_document = None
    if replaces_document_id is not None:
        replaced_document = db.scalar(select(Document).where(Document.id == replaces_document_id, Document.owner_id == current_user.id))
        if replaced_document is None or replaced_document.status not in {"REJECTED", "NEEDS_CHANGES", "CHANGES_REQUESTED", "NEEDS_REVIEW"} or not (is_invoice_workflow_upload or is_expense_upload):
            raise HTTPException(status_code=409, detail="Only your own rejected or correction-requested invoice/expense can be resubmitted.")

    selected_finance_user_id = assigned_finance_user_id
    if replaced_document is not None and selected_finance_user_id is None:
        selected_finance_user_id = replaced_document.assigned_finance_user_id
    if is_invoice_workflow_upload and role in {"Finance Manager", "Chief Accountant"} and selected_finance_user_id is None:
        raise HTTPException(status_code=422, detail="Select the Finance User responsible for payment before uploading.")
    if selected_finance_user_id is not None:
        selected = db.scalar(select(User).where(User.id == selected_finance_user_id, User.tenant_id == current_user.tenant_id, User.is_active.is_(True), User.deleted_at.is_(None)))
        if selected is None or selected.role_name != "Finance User":
            raise HTTPException(status_code=422, detail="Selected payer must be an active Finance User in your company.")

    original_name = Path((file.filename or "").replace("\\", "/")).name.strip()
    if not original_name or original_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="A valid filename is required.")
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Supported formats: PDF, CSV, XLS, XLSX and DOCX.")
    try:
        content = await _read_upload_limited(file)
    finally:
        await file.close()

    content_type = file.content_type or MEDIA_TYPES.get(extension)
    object_path, unique_id = build_object_path(DOCUMENTS_PREFIX, current_user.id, original_name)
    try:
        bucket = storage.bucket
        await run_in_threadpool(storage.upload, object_path, content, content_type)
    except StorageError as exc:
        logger.error("Document upload to storage failed for user %s", current_user.id)
        raise _storage_http_error(exc) from exc

    try:
        initial_status = "PENDING_CA_APPROVAL" if is_invoice_workflow_upload and role == "Finance Manager" else ("PENDING_PAYMENT" if is_invoice_workflow_upload and role == "Chief Accountant" else "PENDING_REVIEW")
        document = Document(
            owner_id=current_user.id,
            supersedes_document_id=replaced_document.id if replaced_document else None,
            uploader_role=role,  # NEW: preserve the uploader's role at submission time.
            assigned_finance_user_id=(current_user.id if is_invoice_workflow_upload and role == "Finance User" else selected_finance_user_id),
            name=original_name[:255], stored_filename=f"{unique_id}{extension}", storage_bucket=bucket,
            storage_path=object_path, content_type=content_type, size_bytes=len(content),
            duplicate_hash=sha256_document(content),
            category="Accounts Payable" if is_ap_upload else ("Expense" if is_expense_upload else ("Invoice" if is_invoice_upload else "Uncategorized")),
            status=initial_status if (is_ap_upload or is_expense_upload or is_invoice_upload) else "PENDING",
            review_status=initial_status if (is_ap_upload or is_expense_upload or is_invoice_upload) else "NOT_READY",
        )
        db.add(document)
        db.flush()
        if replaced_document is not None:
            replaced_document.status = replaced_document.review_status = "SUPERSEDED"
            add_audit_event(db, replaced_document.id, current_user.id, "DOCUMENT_SUPERSEDED_BY_RESUBMISSION", {"replacement_document_id": document.id}, owner_id=current_user.id)
        db.commit()
        db.refresh(document)
    except Exception as exc:
        db.rollback()
        logger.exception("Document metadata insert failed; removing orphaned object")
        try:
            await run_in_threadpool(storage.delete, object_path)
        except StorageError:
            logger.error("ORPHANED STORAGE OBJECT (manual cleanup needed): %s/%s", bucket, object_path)
        raise HTTPException(status_code=500, detail="Unable to save the document.") from exc

    try:
        processed = _process_uploaded_document(db, document, current_user, content, extension)
        if is_ap_upload or is_expense_upload or is_invoice_upload:
            document = db.get(Document, document.id)
            if role == "Finance Manager":
                document.status = document.review_status = "PENDING_CA_APPROVAL"
                notify_roles(db, current_user.tenant_id, {"Chief Accountant"}, "INVOICE_CA_REVIEW", "Invoice awaiting Chief Accountant review", f"Invoice '{document.name}' was uploaded by Finance Manager {current_user.full_name}.", "/employees/accounts-payable")
            elif role == "Chief Accountant":
                document.status = document.review_status = "PENDING_PAYMENT"
                notify_user(db, document.assigned_finance_user, "INVOICE_PAYMENT_ASSIGNED", "Invoice assigned for payment", f"Chief Accountant {current_user.full_name} uploaded '{document.name}' and assigned it to you for payment.", "/employees/accounts-payable")
            elif role == "Finance User":
                document.status = document.review_status = "PENDING_REVIEW"
                notify_roles(db, current_user.tenant_id, {"Finance User", "Finance Manager"}, "INVOICE_PEER_REVIEW", "Invoice awaiting independent review", f"Finance User {current_user.full_name} uploaded '{document.name}'. Another Finance User or Finance Manager must review it.", "/employees/accounts-payable")
            elif is_expense_upload:
                document.category = "Expense"
                document.status = document.review_status = "PENDING_REVIEW"
                notify_roles(db, current_user.tenant_id, {"Finance User", "Finance Manager"}, "EXPENSE_REVIEW", "Employee expense awaiting review", f"Employee expense '{document.name}' needs review by Finance User or Finance Manager.", "/employees/expense-employee")
            else:
                document.status = document.review_status = "PENDING_REVIEW"
                notify_roles(db, current_user.tenant_id, {"Finance User", "Finance Manager"}, "EMPLOYEE_INVOICE_REVIEW", "Employee invoice awaiting review", f"Employee invoice '{document.name}' needs review by Finance User or Finance Manager.", "/employees/invoice-processing")
            add_audit_event(db, document.id, current_user.id, "ROLE_ROUTED_UPLOAD", {"uploader_role": role, "assigned_finance_user_id": document.assigned_finance_user_id, "status": document.status}, owner_id=document.owner_id)
            db.commit()
            db.refresh(document)
            return serialize_document(document)
        return processed
    finally:
        del content

def _process_uploaded_document(
    db: Session,
    document: Document,
    current_user: User,
    content: bytes,
    extension: str,
) -> dict:
    original_name = document.name
    document_id = document.id

    add_audit_event(
        db,
        document_id,
        current_user.id,
        "UPLOADED",
        {"filename": original_name},
    )
    db.commit()

    # Detect structurally valid reconciliation workbooks without relying on AI classification.
    if is_reconciliation_workbook(content, extension):
        document = db.get(Document, document_id)
        if document is None:
            raise HTTPException(
                status_code=500,
                detail="Uploaded document could not be reloaded.",
            )
        document.category = "Reconciliation"
        document.status = "PROCESSED"
        document.validation_status = "NOT_APPLICABLE"
        document.validation_errors = []
        document.review_status = "NOT_READY"
        document.is_duplicate = False
        add_audit_event(
            db,
            document_id,
            current_user.id,
            "RECONCILIATION_WORKBOOK_DETECTED",
            {"category": "Reconciliation", "sheets": ["Company Cashbook", "Bank Statement"]},
        )
        db.commit()
        db.refresh(document)
        return serialize_document(document)

    # Structured AP registers have explicit columns and should not depend on
    # Gemini guessing the spreadsheet's table structure.
    try:
        structured_invoice = extract_structured_invoice_spreadsheet(content, extension)
    except Exception:
        logger.exception(
            "Structured spreadsheet inspection failed for document %s",
            document_id,
        )
        structured_invoice = None

    if structured_invoice is not None:
        document = db.get(Document, document_id)
        if document is None:
            raise HTTPException(
                status_code=500,
                detail="Uploaded document could not be reloaded.",
            )

        document.category = "Accounts Payable"
        apply_invoice_extraction(
            db,
            document,
            structured_invoice,
            current_user.id,
            "STRUCTURED_AP_REGISTER_EXTRACTED",
        )
        db.commit()
        db.refresh(document)
        return serialize_document(document)

    # Classify the saved file.
    try:
        structured_invoice = extract_structured_invoice_spreadsheet(content, extension)
        if structured_invoice is not None:
            document.category = "Accounts Payable"
            apply_invoice_extraction(
                db,
                document,
                structured_invoice,
                current_user.id,
                "STRUCTURED_AP_REGISTER_REPROCESSED",
            )
            db.commit()
            db.refresh(document)
            return serialize_document(document)

        result = classify_document(content, extension)

        document = db.get(Document, document_id)

        if document is None:
            raise RuntimeError(
                "Uploaded document could not be reloaded."
            )

        document.category = result["category"]

        add_audit_event(
            db,
            document_id,
            current_user.id,
            "CLASSIFIED",
            {
                "category": result["category"],
                "confidence": result.get("confidence"),
            },
        )

        db.commit()
        db.refresh(document)

    except Exception as exc:
        logger.exception(
            "AI classification failed for document %s",
            document_id,
        )

        mark_processing_failed(
            db,
            document_id,
            current_user.id,
            "CLASSIFICATION_FAILED",
            "AI classification failed. Retry processing later.",
        )

        document = db.get(Document, document_id)

        if document is None:
            raise HTTPException(
                status_code=500,
                detail="Uploaded document could not be reloaded.",
            ) from exc

        return serialize_document(document)

    is_invoice = is_invoice_category(document.category)

    if (
        not is_invoice
        and (document.category or "").strip().lower()
        == "uncategorized"
    ):
        try:
            if detect_invoice_fallback(content, extension):
                document.category = "Invoice"
                is_invoice = True

                add_audit_event(
                    db,
                    document_id,
                    current_user.id,
                    "INVOICE_FALLBACK_DETECTED",
                    {
                        "reason": (
                            "Invoice indicators found in document text"
                        )
                    },
                )

                db.commit()

        except Exception as exc:
            logger.exception(
                "Invoice fallback detection failed for document %s",
                document_id,
            )

            mark_processing_failed(
                db,
                document_id,
                current_user.id,
                "FALLBACK_DETECTION_FAILED",
                "Document inspection failed. Retry processing later.",
            )

            document = db.get(Document, document_id)

            if document is None:
                raise HTTPException(
                    status_code=500,
                    detail="Document could not be reloaded.",
                ) from exc

            return serialize_document(document)

    if is_invoice:
        try:
            extracted = extract_invoice(content, extension)

            document = db.get(Document, document_id)

            if document is None:
                raise RuntimeError(
                    "Uploaded document could not be reloaded."
                )

            apply_invoice_extraction(
                db,
                document,
                extracted,
                current_user.id,
                "INVOICE_EXTRACTED",
            )

            db.commit()

        except Exception as exc:
            logger.exception(
                "Invoice extraction failed for document %s",
                document_id,
            )

            mark_processing_failed(
                db,
                document_id,
                current_user.id,
                "EXTRACTION_FAILED",
                "Invoice extraction failed. Review or retry is required.",
            )

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=500,
            detail="Document could not be reloaded.",
        )

    return serialize_document(document)


class InvoiceRejectionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/{document_id}/reprocess")
def reprocess_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Re-run classification and invoice extraction for a saved document."""
    document = db.get(Document, document_id)

    if document is None or not can_access_document(current_user, document):
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    approved_ap_invoice = is_ap_document(document) and document.review_status == "APPROVED"
    content = _load_document_bytes(document)
    extension = _document_extension(document)

    if is_reconciliation_workbook(content, extension):
        document.category = "Reconciliation"
        document.status = "PROCESSED"
        document.validation_status = "NOT_APPLICABLE"
        document.validation_errors = []
        document.review_status = "NOT_READY"
        document.is_duplicate = False
        add_audit_event(
            db,
            document_id,
            current_user.id,
            "RECONCILIATION_WORKBOOK_REPROCESSED",
            {"category": "Reconciliation", "sheets": ["Company Cashbook", "Bank Statement"]},
        )
        db.commit()
        db.refresh(document)
        return serialize_document(document)

    try:
        result = classify_document(content, extension)

        document = db.get(Document, document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        document.category = result["category"]

        is_invoice = is_invoice_category(document.category)

        if (
            not is_invoice
            and (document.category or "").strip().lower()
            == "uncategorized"
        ):
            is_invoice = detect_invoice_fallback(content, extension)

            if is_invoice:
                document.category = "Invoice"

        add_audit_event(
            db,
            document_id,
            current_user.id,
            "DOCUMENT_REPROCESSED",
            {
                "category": document.category,
                "confidence": result.get("confidence"),
            },
        )

        if not is_invoice:
            # Classification succeeded, but invoice validation does not apply.
            document.status = "PROCESSED"
            document.validation_status = "NOT_APPLICABLE"
            document.validation_errors = []
            document.review_status = "NOT_READY"
            document.is_duplicate = False

            add_audit_event(
                db,
                document_id,
                current_user.id,
                "DOCUMENT_PROCESSING_COMPLETED",
                {
                    "category": document.category,
                    "validation": "NOT_APPLICABLE",
                },
            )

            db.commit()
            db.refresh(document)

            logger.info(
                "Document %s reprocessed successfully as %s",
                document.id,
                document.category,
            )

            return serialize_document(document)

        extracted = extract_invoice(content, extension)

        document = db.get(Document, document_id)

        if document is None:
            raise HTTPException(
                status_code=404,
                detail="Document not found.",
            )

        apply_invoice_extraction(
            db,
            document,
            extracted,
            current_user.id,
            "INVOICE_REPROCESSED",
        )
        if approved_ap_invoice:
            # Reprocessing happens only after the AP approval chain is complete.
            # Preserve that approval while still blocking payment for invalid/duplicate data.
            document.review_status = "APPROVED"
            document.status = "APPROVED" if document.validation_status == "VALID" and not document.is_duplicate else "NEEDS_REVIEW"

        db.commit()
        db.refresh(document)

        return serialize_document(document)

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        logger.exception(
            "Reprocessing failed for document %s",
            document_id,
        )

        mark_processing_failed(
            db,
            document_id,
            current_user.id,
            "REPROCESSING_FAILED",
            "Reprocessing failed. Retry processing later.",
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Document processing is temporarily unavailable. "
                "The document was retained. Please retry later."
            ),
        ) from exc


@router.post("/{document_id}/approve")
def approve_invoice(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """NEW: uploader-role-aware approval routing."""
    # NEW: lock the source invoice to prevent two concurrent payment attempts.
    document = db.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None or not can_access_document(current_user, document):
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.owner_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot approve your own submission.")
    if document.status == "ON_HOLD":
        raise HTTPException(status_code=409, detail="This invoice is on hold pending fraud investigation.")
    role = current_user.role_name
    uploader_role = document.uploader_role or (document.owner.role_name if document.owner else None)
    category = (document.category or "").strip().lower()
    if role not in {"Finance User", "Finance Manager", "Chief Accountant"}:
        raise HTTPException(status_code=403, detail="Only Finance User, Finance Manager or Chief Accountant can approve this document.")
    if category not in REVIEW_ONLY_CATEGORIES:
        duplicate = find_duplicate_invoice(db, document, document.owner_id)
        if duplicate is not None:
            _set_duplicate_match(document, duplicate, "HASH" if document.duplicate_hash and duplicate.duplicate_hash == document.duplicate_hash else "BUSINESS")
            db.commit()
            raise HTTPException(status_code=409, detail="Duplicate invoice detected. Approval is blocked.")
        _set_duplicate_match(document, None)
    if category not in REVIEW_ONLY_CATEGORIES and document.is_duplicate:
        raise HTTPException(status_code=409, detail="Duplicate invoices cannot be approved.")
    if category not in REVIEW_ONLY_CATEGORIES and document.validation_status not in {"VALID", "NOT_RUN"}:
        raise HTTPException(status_code=409, detail="Invoice extraction or validation must be completed before approval.")

    now = datetime.now(timezone.utc)
    previous_status = document.status
    if uploader_role == "Employee / Requester":
        if role not in {"Finance User", "Finance Manager"} or previous_status not in {"PENDING_REVIEW", "PENDING_MANAGER_APPROVAL", "PENDING_FINANCE_USER_VERIFICATION"}:
            raise HTTPException(status_code=403, detail="Employee documents can only be approved by Finance User or Finance Manager while awaiting review.")
        document.first_reviewed_by, document.first_reviewed_at, document.first_review_action = current_user.id, now, "APPROVED"
        document.reviewed_by, document.reviewed_at = current_user.id, now
        document.approved_by, document.approved_at = current_user.id, now  # CHANGED: persist the explicit approver.
        document.status = document.review_status = "PENDING_PAYMENT"
        next_step, action = "FINANCE_USER_PAYMENT", "EMPLOYEE_DOCUMENT_APPROVED"
        notify_roles(db, current_user.tenant_id, {"Finance User"}, "EMPLOYEE_DOCUMENT_PAYMENT", "Approved employee document ready for payment", f"Employee document '{document.name}' was approved by {current_user.full_name} and is ready for Finance User payment.", "/employees/accounts-payable")
    elif uploader_role == "Finance User":
        if role not in {"Finance User", "Finance Manager"} or previous_status not in {"PENDING_REVIEW", "PENDING_MANAGER_APPROVAL", "READY_FOR_REVIEW"}:
            raise HTTPException(status_code=403, detail="A Finance User upload must be reviewed by another Finance User or Finance Manager at its first stage.")
        document.first_reviewed_by, document.first_reviewed_at, document.first_review_action = current_user.id, now, "APPROVED"
        document.reviewed_by, document.reviewed_at = current_user.id, now
        document.approved_by, document.approved_at = current_user.id, now  # CHANGED: persist the independent reviewer.
        document.status = document.review_status = "PENDING_CA_APPROVAL"
        next_step, action = "CHIEF_ACCOUNTANT_APPROVAL", "INDEPENDENT_FINANCE_REVIEW_APPROVED"
        notify_roles(db, current_user.tenant_id, {"Chief Accountant"}, "INVOICE_CA_REVIEW", "Invoice awaiting Chief Accountant approval", f"Invoice '{document.name}' uploaded by {document.owner.full_name if document.owner else 'Finance User'} was approved by {current_user.full_name}.", "/employees/accounts-payable")
    elif uploader_role in {"Finance Manager", "Finance User"} and role == "Chief Accountant" and previous_status == "PENDING_CA_APPROVAL":
        # CHANGED: B5 now allows CA approval for a Finance User upload after its independent first review.
        # Finance Manager uploads use the same CA verification stage.
        document.chief_accountant_approved_by, document.chief_accountant_approved_at = current_user.id, now
        document.verified_by, document.verified_at = current_user.id, now
        document.approved_by, document.approved_at = current_user.id, now
        document.reviewed_by, document.reviewed_at = current_user.id, now
        document.status = document.review_status = "PENDING_PAYMENT"
        next_step, action = "ASSIGNED_FINANCE_USER_PAYMENT", "CHIEF_ACCOUNTANT_APPROVED_UPLOAD"
        payer = document.assigned_finance_user
        if uploader_role == "Finance User":
            # CHANGED: preserve original Finance User as the payment owner after CA approval.
            payer = document.owner
            document.assigned_finance_user_id = document.owner_id
        if payer:
            notify_user(db, payer, "INVOICE_PAYMENT_ASSIGNED", "Invoice assigned for payment", f"Chief Accountant approved '{document.name}'. You are assigned to pay it.", "/employees/accounts-payable")
    else:
        raise HTTPException(status_code=409, detail="Chief Accountant uploads do not require approval; this document has no further approval stage.")

    document.rejection_reason = None
    add_audit_event(db, document.id, current_user.id, action, {"from_status": previous_status, "to_status": document.status, "uploader_role": uploader_role, "uploaded_by": document.owner_id, "approved_by": current_user.id, "next_step": next_step}, owner_id=document.owner_id)
    db.commit()
    db.refresh(document)
    return serialize_document(document)


@router.post("/{document_id}/reject")
def reject_invoice(document_id: int, payload: InvoiceRejectionRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A rejection reason is required.")
    document = db.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None or not can_access_document(current_user, document):
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.owner_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot reject your own submission.")
    role = current_user.role_name
    uploader_role = document.uploader_role or (document.owner.role_name if document.owner else None)
    stage1 = {"PENDING_REVIEW", "PENDING_MANAGER_APPROVAL", "PENDING_FINANCE_USER_VERIFICATION", "READY_FOR_REVIEW"}
    allowed = (uploader_role == "Employee / Requester" and role in {"Finance User", "Finance Manager"} and document.status in stage1)
    allowed = allowed or (uploader_role == "Finance User" and role in {"Finance User", "Finance Manager"} and document.status in stage1)
    allowed = allowed or (uploader_role == "Finance User" and role == "Chief Accountant" and document.status == "PENDING_CA_APPROVAL")
    allowed = allowed or (uploader_role == "Finance Manager" and role == "Chief Accountant" and document.status == "PENDING_CA_APPROVAL")
    if not allowed:
        raise HTTPException(status_code=403, detail="Your role cannot reject this document at its current workflow stage.")
    previous_status = document.status
    document.status = document.review_status = "REJECTED"
    document.reviewed_by, document.reviewed_at = current_user.id, datetime.now(timezone.utc)
    document.rejected_by, document.rejected_at = current_user.id, document.reviewed_at  # NEW: explicit rejection audit.
    document.rejection_reason = reason
    add_audit_event(db, document.id, current_user.id, "REJECTED", {"from_status": previous_status, "to_status": "REJECTED", "uploader_role": uploader_role}, reason=reason, owner_id=document.owner_id)
    notify_user(db, document.owner, "DOCUMENT_REJECTED", "Document rejected", f"Your document '{document.name}' was rejected. Reason: {reason}", "/employees/invoice-processing")
    db.commit()
    db.refresh(document)
    return serialize_document(document)


class RequestChangesBody(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


@router.post("/{document_id}/request-changes")
def request_invoice_changes(document_id: int, payload: RequestChangesBody, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = db.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None or not can_access_document(current_user, document):
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.owner_id == current_user.id:
        raise HTTPException(status_code=403, detail="You cannot request changes on your own submission.")
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="A reason is required when requesting changes.")
    role = current_user.role_name
    uploader_role = document.uploader_role or (document.owner.role_name if document.owner else None)
    stage1 = {"PENDING_REVIEW", "PENDING_MANAGER_APPROVAL", "PENDING_FINANCE_USER_VERIFICATION", "READY_FOR_REVIEW"}
    allowed = (uploader_role == "Employee / Requester" and role in {"Finance User", "Finance Manager"} and document.status in stage1)
    allowed = allowed or (uploader_role == "Finance User" and role in {"Finance User", "Finance Manager"} and document.status in stage1)
    allowed = allowed or (uploader_role == "Finance User" and role == "Chief Accountant" and document.status == "PENDING_CA_APPROVAL")
    allowed = allowed or (uploader_role == "Finance Manager" and role == "Chief Accountant" and document.status == "PENDING_CA_APPROVAL")
    if not allowed:
        raise HTTPException(status_code=403, detail="Your role cannot request changes at this workflow stage.")
    previous_status = document.status
    document.status, document.review_status = "NEEDS_CHANGES", "CHANGES_REQUESTED"
    document.reviewed_by, document.reviewed_at = current_user.id, datetime.now(timezone.utc)
    document.verified_by, document.verified_at = current_user.id, document.reviewed_at  # NEW: record the reviewer requesting correction.
    document.rejection_reason = reason
    add_audit_event(db, document.id, current_user.id, "CHANGES_REQUESTED", {"from_status": previous_status, "to_status": "NEEDS_CHANGES", "uploader_role": uploader_role}, reason=reason, owner_id=document.owner_id)
    notify_user(db, document.owner, "DOCUMENT_CHANGES_REQUESTED", "Changes required", f"Please correct '{document.name}' and re-upload it. Remarks: {reason}", "/employees/invoice-processing")
    db.commit()
    db.refresh(document)
    return serialize_document(document)


class ExtractedFieldsUpdate(BaseModel):
    fields: dict
    reason: str | None = Field(default=None, max_length=500)


@router.patch("/{document_id}/extracted-fields")
def update_extracted_fields(document_id: int, payload: ExtractedFieldsUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Audited manual correction of extracted invoice fields (before approval only)."""
    document = db.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None or not can_access_document(current_user, document):
        raise HTTPException(status_code=404, detail="Document not found.")
    role = current_user.role_name
    is_owner = document.owner_id == current_user.id
    if not is_owner and role not in invoice_edit.REVIEWER_EDIT_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot edit extracted invoice data.")
    if document.status not in invoice_edit.EDITABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Extracted data can only be corrected before approval; it is locked at this stage.")
    try:
        edits = invoice_edit.normalise_edits(payload.fields)
    except invoice_edit.FieldEditError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    before = {k: getattr(document, k) for k in invoice_edit.EDITABLE_FIELDS}
    changes = invoice_edit.diff_fields(before, edits)
    if not changes:
        return serialize_document(document)
    # Preserve the original extraction values the first time anyone edits.
    first_edit = db.scalar(select(DocumentAuditEvent.id).where(DocumentAuditEvent.document_id == document.id, DocumentAuditEvent.action == "EXTRACTED_FIELDS_EDITED").limit(1)) is None
    for key, value in edits.items():
        setattr(document, key, value)
    merged = {k: getattr(document, k) for k in invoice_edit.EDITABLE_FIELDS}
    errors = invoice_edit.validate_fields(merged)
    document.validation_errors = errors
    duplicate = find_duplicate_invoice(db, document, document.owner_id)
    _set_duplicate_match(document, duplicate, "HASH" if duplicate and document.duplicate_hash and duplicate.duplicate_hash == document.duplicate_hash else ("BUSINESS" if duplicate else None))
    if document.is_duplicate:
        document.validation_status = "DUPLICATE"
    else:
        document.validation_status = "VALID" if not errors else "INVALID"
    if document.status == "NEEDS_REVIEW" and document.validation_status == "VALID":
        document.review_status, document.status = "READY_FOR_REVIEW", "PENDING_REVIEW"
    details = {"changes": changes, "validation_status": document.validation_status, "is_duplicate": document.is_duplicate, "edited_by_role": role}
    if first_edit:
        details["original_values"] = {k: (None if before[k] is None else str(before[k])) for k in changes}
    add_audit_event(db, document.id, current_user.id, "EXTRACTED_FIELDS_EDITED", details, reason=(payload.reason or None), owner_id=document.owner_id)
    db.commit()
    db.refresh(document)
    return serialize_document(document)


@router.get("/{document_id}/history")
def get_document_history(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = db.get(Document, document_id)

    if document is None or not can_access_document(current_user, document):
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    events = db.scalars(
        select(DocumentAuditEvent)
        .where(
            DocumentAuditEvent.document_id == document_id,
            DocumentAuditEvent.owner_id == document.owner_id,
        )
        .order_by(
            DocumentAuditEvent.created_at.desc(),
            DocumentAuditEvent.id.desc(),
        )
    ).all()

    return [
        {
            "id": event.id,
            "action": event.action,
            "reason": event.reason,
            "details": event.details or {},
            "actorId": event.actor_id,
            "actorName": db.get(User, event.actor_id).full_name if event.actor_id and db.get(User, event.actor_id) else None,
            "actorRole": db.get(User, event.actor_id).role_name if event.actor_id and db.get(User, event.actor_id) else None,
            "createdAt": (
                event.created_at.isoformat()
                if event.created_at else None
            ),
        }
        for event in events
    ]


class InvoicePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    transfer_reference: str = Field(min_length=4, max_length=120)
    bank_name: str | None = Field(default=None, max_length=120)
    payment_date: date


@router.post("/{document_id}/pay")
def pay_invoice(document_id: int, payload: InvoicePaymentRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """NEW: Finance User-only final manual payment with atomic ledger posting."""
    if current_user.role_name != "Finance User":
        raise HTTPException(status_code=403, detail="Only a Finance User can make the final supplier payment.")
    # Row lock: two concurrent pay requests cannot both pass the status check.
    document = db.scalar(select(Document).where(Document.id == document_id).with_for_update())
    if document is None or not can_access_document(current_user, document):
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status != "PENDING_PAYMENT":
        raise HTTPException(status_code=409, detail="Only an approved invoice awaiting payment can be paid.")
    duplicate = find_duplicate_invoice(db, document, document.owner_id)
    if duplicate is not None:
        _set_duplicate_match(document, duplicate, "HASH" if document.duplicate_hash and duplicate.duplicate_hash == document.duplicate_hash else "BUSINESS")
        add_audit_event(db, document.id, current_user.id, "DUPLICATE_PAYMENT_BLOCKED", {"duplicate_of_id": duplicate.id, "match_type": document.duplicate_match_type}, owner_id=document.owner_id)
        db.commit()
        raise HTTPException(status_code=409, detail="Payment blocked: this invoice matches an existing invoice in your company.")
    if document.status != "PENDING_PAYMENT" or document.validation_status not in {"VALID", "NOT_RUN"}:
        raise HTTPException(status_code=409, detail="Invoice must remain approved and valid after duplicate revalidation before payment.")
    if document.assigned_finance_user_id not in {None, current_user.id}:
        raise HTTPException(status_code=403, detail="This invoice is assigned to another Finance User.")
    if document.total_amount is None or Decimal(str(document.total_amount)) != payload.amount:
        raise HTTPException(status_code=422, detail="Payment amount must exactly match the invoice total.")
    if document.paid_at is not None or document.status == "PAID":
        raise HTTPException(status_code=409, detail="This invoice has already been paid.")
    if not document.storage_path:
        raise HTTPException(status_code=409, detail="The original invoice file is missing; upload it again before payment.")
    if document.assigned_finance_user_id is None:
        document.assigned_finance_user_id = current_user.id
    previous_status = document.status
    try:
        voucher = post_ap_payment(db, current_user.id, document.id, payload.payment_date, payload.amount, document.vendor_name)
        now = datetime.now(timezone.utc)
        document.status = document.review_status = "PAID"
        document.paid_by, document.paid_at = current_user.id, now
        document.payment_amount = payload.amount
        document.payment_reference = payload.transfer_reference.strip()
        document.payment_bank_name = payload.bank_name.strip() if payload.bank_name else None
        document.payment_date = payload.payment_date
        document.ledger_voucher_no = voucher
        add_audit_event(db, document.id, current_user.id, "INVOICE_PAID_AND_POSTED", {"from_status": previous_status, "to_status": "PAID", "amount": str(payload.amount), "payment_reference": document.payment_reference, "bank_name": document.payment_bank_name, "payment_date": payload.payment_date.isoformat(), "ledger_voucher_no": voucher, "ledger_source_document_id": document.id}, owner_id=document.owner_id)
        notify_user(db, document.owner, "INVOICE_PAID", "Invoice payment completed", f"Invoice '{document.name}' was paid by {current_user.full_name}. Ledger voucher: {voucher}.", "/employees/accounts-payable")
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Invoice payment/ledger posting failed for document %s", document_id)
        raise
    db.refresh(document)
    return serialize_document(document)


MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".csv": "text/csv",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsm": "application/vnd.ms-excel.sheet.macroEnabled.12",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
PREVIEW_MAX_ROWS = 100
PREVIEW_MAX_COLS = 20


def _document_extension(document: Document) -> str:
    return Path(document.name).suffix.lower()


def _load_document_bytes(document: Document) -> bytes:
    """Fetch the file bytes from Supabase Storage (never from local disk)."""
    if not document.storage_path or not document.storage_bucket:
        raise HTTPException(
            status_code=404,
            detail="This document has no file in storage. Please re-upload it.",
        )
    if document.storage_bucket != settings.supabase_storage_bucket:
        logger.error(
            "Document %s references bucket %r but the configured bucket is %r",
            document.id, document.storage_bucket, settings.supabase_storage_bucket,
        )
        raise HTTPException(status_code=409, detail="The document is stored in a different bucket.")
    try:
        return storage.download(document.storage_path)
    except StorageError as exc:
        raise _storage_http_error(exc) from exc


def _get_accessible_document(db: Session, user: User, document_id: int) -> Document:
    document = db.get(Document, document_id)

    if document is None or not can_access_document(user, document):
        raise HTTPException(status_code=404, detail="Document not found.")

    return document


def _content_disposition(filename: str, attachment: bool) -> str:
    from urllib.parse import quote

    ascii_name = filename.encode("ascii", "ignore").decode().replace('"', "") or "download"
    kind = "attachment" if attachment else "inline"
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8\'\'{quote(filename, safe='')}"


@router.get("/{document_id}/file")
def get_document_file(
    document_id: int,
    download: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream the original file from Supabase Storage after an access check.

    Inline for viewing, attachment for download (original filename + extension).
    """
    document = _get_accessible_document(db, current_user, document_id)
    extension = _document_extension(document)
    content = _load_document_bytes(document)

    add_audit_event(
        db,
        document.id,
        current_user.id,
        "DOWNLOADED" if download else "PREVIEWED",
        {"filename": document.name},
        owner_id=document.owner_id,
    )
    db.commit()

    return Response(
        content=content,
        media_type=MEDIA_TYPES.get(extension, "application/octet-stream"),
        headers={
            "Content-Disposition": _content_disposition(document.name, download),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{document_id}/signed-url")
def get_document_signed_url(
    document_id: int,
    download: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Optional: a 60-second Supabase signed URL, issued only to authorised users."""
    document = _get_accessible_document(db, current_user, document_id)
    if not document.storage_path or document.storage_bucket != settings.supabase_storage_bucket:
        raise HTTPException(status_code=404, detail="This document has no file in storage.")
    try:
        url = storage.create_signed_url(
            document.storage_path,
            expires_in=60,
            download_name=document.name if download else None,
        )
    except StorageError as exc:
        raise _storage_http_error(exc) from exc
    return {"url": url, "expiresInSeconds": 60, "filename": document.name}


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete the Storage object, then the database record (and its dependants).

    Only the uploader or an Administrator may delete. Storage goes first: if it
    fails the record is kept, so a retry is always possible; if the DB step then
    fails the record stays and a retry treats the missing object as already gone.
    """
    document = db.get(Document, document_id)

    if document is None or not can_access_document(current_user, document):
        raise HTTPException(status_code=404, detail="Document not found.")

    if document.owner_id != current_user.id and current_user.role_name != "Administrator":
        raise HTTPException(status_code=403, detail="You do not have permission to delete this document.")

    if document.storage_path:
        # Never delete anything outside the uploader's own documents folder.
        if (
            document.storage_bucket != settings.supabase_storage_bucket
            or not path_belongs_to(DOCUMENTS_PREFIX, document.owner_id, document.storage_path)
        ):
            logger.error("Refusing to delete suspicious storage path for document %s", document.id)
            raise HTTPException(status_code=409, detail="The stored file reference is invalid; deletion was refused.")
        try:
            storage.delete(document.storage_path)
        except StorageError as exc:
            raise _storage_http_error(exc) from exc

    try:
        db.delete(document)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Database delete failed for document %s", document_id)
        raise HTTPException(
            status_code=500,
            detail="The file was removed but the record could not be deleted. Please retry.",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _cell(value) -> str:
    return "" if value is None else str(value)


@router.get("/{document_id}/preview")
def preview_document(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a safe, bounded preview. PDFs are viewed through /file."""
    document = _get_accessible_document(db, current_user, document_id)
    extension = _document_extension(document)
    base = {"id": document.id, "name": document.name, "extension": extension}

    if extension == ".pdf":
        # Existence check so a missing object is reported before the viewer opens it.
        _load_document_bytes(document)
        return {**base, "kind": "pdf"}

    content = _load_document_bytes(document)

    try:
        if extension == ".csv":
            rows, truncated = [], False
            handle = StringIO(content.decode("utf-8-sig", errors="replace"), newline="")
            for index, row in enumerate(csv.reader(handle)):
                if index >= PREVIEW_MAX_ROWS:
                    truncated = True
                    break
                rows.append([_cell(c) for c in row[:PREVIEW_MAX_COLS]])
            return {**base, "kind": "table", "sheets": [{"name": "CSV", "rows": rows, "truncated": truncated}]}

        if extension in {".xlsx", ".xlsm"}:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
            try:
                sheets = []
                for sheet in workbook.worksheets[:5]:
                    rows, truncated = [], False
                    for index, row in enumerate(sheet.iter_rows(values_only=True)):
                        if index >= PREVIEW_MAX_ROWS:
                            truncated = True
                            break
                        rows.append([_cell(c) for c in row[:PREVIEW_MAX_COLS]])
                    sheets.append({"name": sheet.title, "rows": rows, "truncated": truncated})
            finally:
                workbook.close()
            return {**base, "kind": "table", "sheets": sheets}

        if extension == ".docx":
            from docx import Document as DocxDocument

            doc = DocxDocument(BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs)
            return {**base, "kind": "text", "text": text[:20000], "truncated": len(text) > 20000}
    except Exception:
        logger.exception("Preview failed for document %s", document_id)
        return {
            **base,
            "kind": "unsupported",
            "message": "This file could not be previewed. You can still download it.",
        }

    return {
        **base,
        "kind": "unsupported",
        "message": "Preview is not available for this file type. You can download it instead.",
    }
