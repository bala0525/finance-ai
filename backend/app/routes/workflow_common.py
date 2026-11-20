"""Shared helpers for the workflow routers."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from fastapi import HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.user import User

logger = logging.getLogger(__name__)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
REVIEWER_ROLE_NAMES = ("Administrator", "Finance Manager")

AP_CATEGORIES = {"accounts payable", "invoice", "invoices"}
AR_CATEGORIES = {"accounts receivable"}
EXPENSE_CATEGORIES = {"expense", "expenses"}
INVOICE_LIKE = AP_CATEGORIES | AR_CATEGORIES | EXPENSE_CATEGORIES


def today() -> date:
    return datetime.now(timezone.utc).date()


def visible_docs(db: Session, user: User, categories: set[str] | None = None) -> list[Document]:
    """Own documents; Administrators / Finance Managers see everyone's."""
    statement = select(Document).where(
        Document.owner_id.in_(select(User.id).where(User.tenant_id == user.tenant_id))
    ).order_by(Document.created_at.desc(), Document.id.desc())
    finance_user_workflow_review = user.role_name == "Finance User" and categories is not None and categories <= INVOICE_LIKE
    if user.role_name not in {"Finance Manager", "Chief Accountant", "Administrator"} and not finance_user_workflow_review:
        statement = statement.where(Document.owner_id == user.id)
    docs = db.scalars(statement).all()
    if categories is None:
        return list(docs)
    return [d for d in docs if (d.category or "").strip().lower() in categories]


def get_doc(db: Session, user: User, document_id: int) -> Document:
    doc = db.get(Document, document_id)
    is_expense = (doc.category or "").strip().lower() in EXPENSE_CATEGORIES if doc is not None else False
    category = (doc.category or "").strip().lower() if doc is not None else ""
    can_cross_review = user.role_name in {"Finance Manager", "Chief Accountant", "Administrator"} or (user.role_name == "Finance User" and category in AP_CATEGORIES | EXPENSE_CATEGORIES | {"accounts receivable"})
    if doc is None or doc.owner is None or doc.owner.tenant_id != user.tenant_id or (doc.owner_id != user.id and not can_cross_review):
        raise HTTPException(status_code=404, detail="Document not found.")
    return doc


def is_dup(doc: Document) -> bool:
    """Duplicates are flagged by is_duplicate and/or the DUPLICATE validation status."""
    return bool(doc.is_duplicate) or doc.validation_status == "DUPLICATE"


def amount_of(doc: Document) -> float | None:
    return float(doc.total_amount) if doc.total_amount is not None else None


def doc_date(doc: Document) -> date | None:
    if doc.invoice_date:
        return doc.invoice_date
    return doc.created_at.date() if doc.created_at else None


def xlsx_response(content: bytes, filename: str) -> Response:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in filename).strip() or "export.xlsx"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "Cache-Control": "private, no-store",
        },
    )


def gemini_text(prompt: str) -> str | None:
    """Narrative text from Gemini, or None on any problem. Never used for numbers."""
    try:
        from google import genai

        from app.core.config import settings

        if not settings.gemini_api_key:
            return None
        client = genai.Client(api_key=settings.gemini_api_key)
        response = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        text = (response.text or "").strip()
        return text or None
    except Exception:  # noqa: BLE001 - narrative is optional
        logger.warning("Gemini narrative unavailable", exc_info=True)
        return None


def iso(value) -> str | None:
    return value.isoformat() if value else None
