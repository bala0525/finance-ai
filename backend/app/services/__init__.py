"""Service package with lazy exports to avoid importing auth dependencies for pure services."""

__all__ = ["AuthService"]


def __getattr__(name: str):
    if name == "AuthService":
        from app.services.auth_service import AuthService
        return AuthService
    raise AttributeError(name)
