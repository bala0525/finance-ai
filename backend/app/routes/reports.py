import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.document import Document
from app.models.report import Report
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.report_builder import build_report_data, build_report_xlsx
from app.services.storage import (
    REPORTS_PREFIX,
    StorageError,
    StorageNotConfigured,
    StorageObjectNotFound,
    build_object_path,
    storage,
)


router = APIRouter(prefix="/reports", tags=["Reports"])
logger = logging.getLogger(__name__)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def create_financial_report(
    db: Session, user: User, name: str, period: str | None, category: str = "Financial Report"
) -> tuple[Report, dict]:
    """Generate the report data + XLSX file and persist the Report row."""
    statement = select(Document).order_by(Document.created_at.desc(), Document.id.desc())
    if not user.can_review:
        statement = statement.where(Document.owner_id == user.id)
    docs = db.scalars(statement).all()

    profile = db.get(UserProfile, user.id)
    data = build_report_data(
        docs,
        name=name,
        period=period,
        generated_by=user.full_name or user.email,
        timezone_name=profile.timezone if profile else "Asia/Kolkata",
    )
    content = build_report_xlsx(data)
    object_path, unique_id = build_object_path(REPORTS_PREFIX, user.id, f"{name}.xlsx")

    try:
        bucket = storage.bucket
        storage.upload(object_path, content, XLSX_MIME)
    except StorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail="File storage is not configured on the server.") from exc
    except StorageError as exc:
        logger.error("Report upload to storage failed for user %s", user.id)
        raise HTTPException(status_code=502, detail="File storage is temporarily unavailable. Please try again.") from exc

    try:
        report = Report(
            owner_id=user.id,
            name=name,
            category=category,
            period=period,
            format="XLSX",
            status="COMPLETED",
            stored_filename=f"{unique_id}.xlsx",
            storage_bucket=bucket,
            storage_path=object_path,
            file_size=len(content),
            summary=data,
            limitations=data["limitations"],
        )
        db.add(report)
        db.commit()
        db.refresh(report)
    except Exception:
        db.rollback()
        try:
            storage.delete(object_path)
        except StorageError:
            logger.error("ORPHANED STORAGE OBJECT (manual cleanup needed): %s/%s", bucket, object_path)
        logger.exception("Report generation failed")
        raise HTTPException(status_code=500, detail="Report generation failed. Please try again.")

    return report, data


def _owned_report(db: Session, user: User, report_id: int) -> Report:
    report = db.get(Report, report_id)
    if report is None or (report.owner_id != user.id and user.role_name != "Administrator"):
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


class ReportRequest(BaseModel):
    name: str = Field(
        default="New Financial Report",
        min_length=1,
        max_length=255,
    )
    category: str = Field(
        default="Financial Report",
        min_length=1,
        max_length=100,
    )
    period: str | None = Field(
        default=None,
        max_length=100,
    )


def serialize_report(report: Report) -> dict:
    return {
        "id": report.id,
        "name": report.name,
        "category": report.category,
        "period": report.period,
        "format": report.format,
        "status": report.status,
        "fileAvailable": bool(report.storage_path),
        "fileSize": report.file_size,
        "createdAt": (
            report.created_at.isoformat()
            if report.created_at
            else None
        ),
    }


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports = db.scalars(
        select(Report)
        .where(Report.owner_id == current_user.id)
        .order_by(Report.created_at.desc(), Report.id.desc())
    ).all()

    now = datetime.now(timezone.utc)
    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    generated_this_month = sum(
        1
        for report in reports
        if report.created_at
        and report.created_at >= month_start
        and report.status == "COMPLETED"
    )

    return {
        "overview": {
            "totalReports": len(reports),
            "generatedThisMonth": generated_this_month,
            "scheduledReports": 0,
        },
        "reports": [
            serialize_report(report)
            for report in reports
        ],
    }


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def request_report(
    request: ReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = request.name.strip()
    category = request.category.strip()

    if not name or not category:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Report name and category cannot be blank.",
        )

    report, _ = create_financial_report(
        db, current_user, name, request.period.strip() if request.period else None, category
    )
    return serialize_report(report)


@router.get("/{report_id}/preview")
def preview_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _owned_report(db, current_user, report_id)
    if not report.summary:
        raise HTTPException(status_code=404, detail="This report has no stored content. Please regenerate it.")
    return {"report": serialize_report(report), "data": report.summary}


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = _owned_report(db, current_user, report_id)
    if (
        not report.storage_path
        or report.storage_bucket != settings.supabase_storage_bucket
    ):
        raise HTTPException(status_code=404, detail="The report file is not available. Please regenerate the report.")
    try:
        content = storage.download(report.storage_path)
    except StorageObjectNotFound as exc:
        raise HTTPException(status_code=404, detail="The report file is missing from storage. Please regenerate the report.") from exc
    except StorageNotConfigured as exc:
        raise HTTPException(status_code=503, detail="File storage is not configured on the server.") from exc
    except StorageError as exc:
        raise HTTPException(status_code=502, detail="File storage is temporarily unavailable. Please try again.") from exc
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in report.name).strip() or "report"
    return Response(
        content=content,
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": f'attachment; filename="{safe}.xlsx"',
            "Cache-Control": "private, no-store",
        },
    )
