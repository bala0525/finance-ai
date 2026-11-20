from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _item(n: Notification) -> dict:
    return {"id": n.id, "eventKey": n.event_key, "title": n.title, "message": n.message,
            "link": n.link, "read": n.read_at is not None, "createdAt": n.created_at.isoformat() if n.created_at else None}

@router.get("")
def list_notifications(unread_only: bool = False, limit: int = 50, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    limit = max(1, min(limit, 100))
    q = select(Notification).where(Notification.user_id == user.id, Notification.tenant_id == user.tenant_id)
    if unread_only:
        q = q.where(Notification.read_at.is_(None))
    rows = db.scalars(q.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(limit)).all()
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.tenant_id == user.tenant_id, Notification.read_at.is_(None))) or 0
    return {"items": [_item(n) for n in rows], "unreadCount": unread}

@router.post("/{notification_id}/read")
def read_notification(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id, Notification.tenant_id == user.tenant_id))
    if n is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if n.read_at is None:
        n.read_at = datetime.now(timezone.utc)
        db.commit()
    return _item(n)

@router.post("/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id, Notification.tenant_id == user.tenant_id, Notification.read_at.is_(None))).all()
    now = datetime.now(timezone.utc)
    for n in rows:
        n.read_at = now
    db.commit()
    return {"updated": len(rows)}
