import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.document_audit_event import DocumentAuditEvent
from app.models.reconciliation_run import ReconciliationRun
from app.models.user import User
from app.routes.documents import _load_document_bytes
from app.services.reconciliation_engine import reconcile_workbook

router = APIRouter(prefix="/documents", tags=["Reconciliation"])
logger = logging.getLogger(__name__)


def _get_owned_document(
    db: Session,
    document_id: int,
    user_id: int,
) -> Document:
    document = db.scalars(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == user_id,
        )
    ).first()

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return document


@router.post("/{document_id}/reconcile")
def run_reconciliation(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_owned_document(
        db, document_id, current_user.id
    )

    if Path(document.name).suffix.lower() not in {".xlsx", ".xlsm"}:
        raise HTTPException(
            status_code=415,
            detail="Reconciliation currently supports XLSX and XLSM files.",
        )

    # Raises 404/502/503 itself when the object is missing or Storage is down.
    content = _load_document_bytes(document)

    try:
        report = reconcile_workbook(content, Path(document.name).suffix.lower())

        run = ReconciliationRun(
            document_id=document.id,
            owner_id=current_user.id,
            status=report["summary"]["status"],
            summary=report["summary"],
            results=report["results"],
        )
        db.add(run)
        db.flush()

        db.add(
            DocumentAuditEvent(
                document_id=document.id,
                owner_id=current_user.id,
                actor_id=current_user.id,
                action="RECONCILIATION_COMPLETED",
                details={
                    "reconciliationRunId": run.id,
                    "summary": report["summary"],
                },
            )
        )

        db.commit()
        db.refresh(run)

        return {
            "runId": run.id,
            "documentId": document.id,
            "documentName": document.name,
            "status": run.status,
            "summary": run.summary,
            "results": run.results,
            "createdAt": (
                run.created_at.isoformat()
                if run.created_at else None
            ),
        }

    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        logger.exception(
            "Reconciliation failed for document %s", document_id
        )
        raise HTTPException(
            status_code=500,
            detail="Reconciliation failed. Check backend logs.",
        ) from exc


@router.get("/{document_id}/reconciliation")
def get_latest_reconciliation(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _get_owned_document(
        db, document_id, current_user.id
    )

    run = db.scalars(
        select(ReconciliationRun)
        .where(
            ReconciliationRun.document_id == document.id,
            ReconciliationRun.owner_id == current_user.id,
        )
        .order_by(ReconciliationRun.created_at.desc())
    ).first()

    if run is None:
        raise HTTPException(
            status_code=404,
            detail="No reconciliation run exists for this document yet.",
        )

    return {
        "runId": run.id,
        "documentId": document.id,
        "documentName": document.name,
        "status": run.status,
        "summary": run.summary,
        "results": run.results,
        "createdAt": (
            run.created_at.isoformat() if run.created_at else None
        ),
    }
