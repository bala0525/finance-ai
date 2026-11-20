from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.role import Role
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.auth import SignupRequest


class AuthService:
    DEFAULT_ROLE = "Employee / Requester"

    @staticmethod
    def get_user_by_email(
        db: Session,
        email: str,
    ) -> User | None:
        statement = select(User).where(
            User.email == email.lower()
        )

        return db.scalar(statement)

    @staticmethod
    def get_default_role(
        db: Session,
    ) -> Role:
        statement = select(Role).where(
            Role.name == AuthService.DEFAULT_ROLE
        )

        role = db.scalar(statement)

        if role is None:
            raise ValueError(
                "Default user role is not configured."
            )

        return role

    @staticmethod
    def create_user(
        db: Session,
        signup_data: SignupRequest,
    ) -> User:
        email = signup_data.email.lower()

        existing_user = AuthService.get_user_by_email(
            db,
            email,
        )

        if existing_user is not None:
            raise ValueError(
                "A user with this email already exists."
            )

        role = AuthService.get_default_role(db)

        # Public signup joins the deployment's default organisation. The caller
        # cannot choose a tenant or privileged role during public registration.
        tenant = db.scalar(select(Tenant).order_by(Tenant.id.asc()))
        if tenant is None:
            tenant = Tenant(name="Default organisation")
            db.add(tenant)
            db.flush()

        user = User(
            email=email,
            password_hash=hash_password(
                signup_data.password
            ),
            full_name=signup_data.full_name,
            is_active=True,
            is_verified=True,
            role_id=role.id,
            tenant_id=tenant.id,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def authenticate_user(
        db: Session,
        email: str,
        password: str,
    ) -> User | None:
        user = AuthService.get_user_by_email(
            db,
            email.lower(),
        )

        if user is None:
            return None

        if not verify_password(
            password,
            user.password_hash,
        ):
            return None

        if not user.is_active or user.deleted_at is not None:
            return None
        return user
