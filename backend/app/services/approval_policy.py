"""Role-based approval policy for invoice review.

Roles (seeded by app/seed_roles.py):
  - Finance User / Finance Manager: can review Employee submissions; a Finance User
                                    cannot review their own upload.
  - Chief Accountant: verifies Finance Manager uploads and provides the final
                      approval stage for Finance User uploads.
  - Administrator: monitoring and administration only; no document approval.

Rejecting never needs an amount limit (it is the conservative action), but it
still needs a reviewer role.
"""

import logging
from decimal import Decimal

from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

ADMIN_ROLE = "Administrator"
MANAGER_ROLE = "Finance Manager"
REVIEWER_ROLES = {"Finance User", MANAGER_ROLE, "Chief Accountant"}


def approval_limit_for(role_name: str | None) -> float | None:
    """None means unlimited (administrator) or not applicable."""
    if role_name == MANAGER_ROLE:
        return float(settings.manager_approval_limit)
    return None


def _format_inr(value) -> str:
    """Indian digit grouping, e.g. 1234567.5 -> 12,34,567.50"""
    amount = Decimal(str(value)).quantize(Decimal("0.01"))
    whole, _, frac = f"{amount:.2f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return f"₹{whole}.{frac}"


def check_review_permission(user, document, action: str) -> None:
    """Raise 403 unless `user` may `action` ("approve" | "reject") `document`."""
    role = user.role.name if user.role else None

    if document.owner_id == user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot review your own upload.")

    if role not in REVIEWER_ROLES:
        logger.warning(
            "User %s (role=%s) denied %s on document %s",
            user.id, role, action, document.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Your role ({role or 'unknown'}) cannot {action} invoices. "
                "Ask a Finance Manager or Administrator."
            ),
        )

    if action != "approve":
        return

    limit = Decimal(str(settings.manager_approval_limit))
    total = document.total_amount

    if total is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "This invoice has no extracted total, so it cannot be approved "
                "within a Finance Manager limit. Ask an Administrator."
            ),
        )

    if Decimal(str(total)) > limit:
        logger.warning(
            "Manager %s denied approve on document %s: %s > limit %s",
            user.id, document.id, total, limit,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Invoice total {_format_inr(total)} exceeds your approval limit "
                f"of {_format_inr(limit)}. An Administrator must approve it."
            ),
        )
