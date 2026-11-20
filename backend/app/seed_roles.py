from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.role import Role


DEFAULT_ROLES = [
    {
        "name": "Administrator",
        "description": "Full access to platform administration and configuration.",
    },
    {
        "name": "Finance Manager",
        "description": "Access to finance operations, reporting, analytics and management features.",
    },
    {
        "name": "Finance User",
        "description": "Processes approved supplier payments, reimbursements and authorized receivables operations.",
    },
    {
        "name": "Employee / Requester",
        "description": "Submits invoices, documents and expenses; can view and correct own submissions.",
    },
    {
        "name": "Chief Accountant",
        "description": "Central finance monitoring and exception oversight without automatic approval authority.",
    },
]


def seed_roles() -> None:
    db = SessionLocal()

    try:
        for role_data in DEFAULT_ROLES:
            existing_role = db.scalar(
                select(Role).where(
                    Role.name == role_data["name"]
                )
            )

            if existing_role is None:
                db.add(
                    Role(
                        name=role_data["name"],
                        description=role_data["description"],
                    )
                )

        db.commit()

        print("DEFAULT ROLES SEEDED SUCCESSFULLY")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    seed_roles()
