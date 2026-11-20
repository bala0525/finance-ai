from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status

from app.dependencies.auth import get_current_user
from app.models.user import User


def require_roles(*allowed_roles: str) -> Callable:
    allowed_roles_set = set(allowed_roles)

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        role_name = current_user.role.name

        if role_name not in allowed_roles_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return current_user

    return role_checker


def require_role(role_name: str) -> Callable:
    return require_roles(role_name)


AGENT_ROLE_ACCESS = {
    "accounts-payable": {"Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
    "accounts-receivable": {"Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
    "invoice-processing": {"Employee / Requester", "Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
    "reconciliation": {"Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
    "finance-analyst": {"Finance Manager", "Chief Accountant", "Administrator"},
    "expense": {"Employee / Requester", "Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
    "financial-reporting": {"Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
    "fraud-detection": {"Finance Manager", "Chief Accountant", "Administrator"},
    "expense": {"Employee / Requester", "Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
    "expense-employee": {"Employee / Requester", "Finance User", "Finance Manager", "Chief Accountant", "Administrator"},
}

def require_agent_workspace_access(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> User:
    """Enforce workspace role access for /agents routers at the API boundary.

    The UI uses the same map for navigation, but this dependency prevents direct
    API calls from bypassing the role-based menu.
    """
    parts = [part for part in request.url.path.strip("/").split("/") if part]
    if len(parts) < 2 or parts[0] != "agents":
        return current_user
    workspace = parts[1]
    allowed = AGENT_ROLE_ACCESS.get(workspace)
    if allowed and current_user.role.name not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not have access to this finance workspace.",
        )
    return current_user
