"""Assign a role to an existing user.

Usage (from the backend directory):
    python -m app.set_role someone@company.com "Finance Manager"

Valid roles: Administrator, Finance Manager, Finance User
New sign-ups are "Finance User" by default, so the first person who needs to
approve invoices must be promoted with this command.
"""

import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Role, User


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2

    email, role_name = sys.argv[1].strip().lower(), sys.argv[2].strip()
    db = SessionLocal()

    try:
        role = db.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            names = ", ".join(r.name for r in db.scalars(select(Role)).all())
            print(f"Unknown role '{role_name}'. Available: {names}")
            return 1

        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email '{email}'.")
            return 1

        user.role_id = role.id
        db.commit()
        print(f"{user.email} is now '{role.name}'.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
