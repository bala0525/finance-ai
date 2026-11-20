from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.notification import Notification
from app.models.user import User
from app.models.user_setting import UserSetting
from app.services.email_delivery import send_email
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def notify_user(db: Session, user: User | None, event_key: str, title: str, message: str, link: str | None = None) -> None:
    if user is None or not user.is_active or user.deleted_at is not None:
        return
    db.add(Notification(tenant_id=user.tenant_id, user_id=user.id, event_key=event_key,
                        title=title[:180], message=message, link=link))
    # Email is best-effort; the in-app notification remains available even if SMTP is down.
    prefs = db.get(UserSetting, user.id)
    email_enabled = prefs.email_notifications if prefs else True
    if email_enabled and all((settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from_email)):
        try:
            send_email(user.email, title[:180], message + (f"\n\nOpen Azentmart Finance AI: {settings.frontend_url}{link}" if link else ""))
        except Exception:
            logger.warning("Notification email delivery failed for user_id=%s event=%s", user.id, event_key, exc_info=True)


def notify_roles(db: Session, tenant_id: int, roles: set[str], event_key: str, title: str,
                 message: str, link: str | None = None, exclude_user_id: int | None = None) -> None:
    users = db.scalars(select(User).where(User.tenant_id == tenant_id, User.is_active.is_(True), User.deleted_at.is_(None))).all()
    for user in users:
        if user.role_name in roles and user.id != exclude_user_id:
            notify_user(db, user, event_key, title, message, link)


def mark_read(db: Session, notification: Notification) -> None:
    notification.read_at = datetime.now(timezone.utc)
