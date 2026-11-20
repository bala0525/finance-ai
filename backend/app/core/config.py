from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRETS = {"", "changeme", "secret", "replace-with-a-long-random-secret"}


class Settings(BaseSettings):
    """Every value below is read from the backend .env file (no hardcoded defaults)."""

    # Application
    app_name: str
    app_env: str  # development | production
    debug: bool

    # Database (Supabase PostgreSQL connection string)
    database_url: str

    # Security
    secret_key: str
    access_token_expire_minutes: int

    # CORS: the only allowed browser origin
    frontend_url: str
    # Optional extra browser origins (comma separated), e.g. a second Amplify branch.
    cors_origins: str = ""

    # Gemini AI
    gemini_api_key: str
    gemini_model: str
    gemini_embedding_model: str

    # Role-based approval limit (INR)
    manager_approval_limit: float

    # Supabase Storage (service-role key is backend-only, never sent to frontend)
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_storage_bucket: str

    # Stripe is optional in development; required only when AR checkout is used.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""
    stripe_currency: str = "inr"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""

    # Internal tuning (not environment-specific, so not in .env)
    db_pool_size: int = 5
    db_max_overflow: int = 10
    storage_timeout_seconds: float = 30.0
    rag_chunk_chars: int = 1200
    rag_chunk_overlap: int = 200
    rag_top_k: int = 8

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_configuration(self) -> "Settings":
        url = self.database_url.strip()
        if not url:
            raise ValueError("DATABASE_URL is empty. Fill it in the .env file.")
        if not self.secret_key.strip():
            raise ValueError("SECRET_KEY is empty. Fill it in the .env file.")

        # Supabase gives "postgres://"; SQLAlchemy needs "postgresql://".
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        # Name the psycopg2 driver explicitly (requirements.txt ships psycopg2).
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        if not url.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string.")
        self.database_url = url

        self.frontend_url = self.frontend_url.strip().rstrip("/")
        self.supabase_url = self.supabase_url.strip().rstrip("/")
        self.supabase_storage_bucket = self.supabase_storage_bucket.strip()

        if self.is_production:
            problems = []
            if not self.supabase_url.startswith("https://"):
                problems.append("SUPABASE_URL must be the https project URL")
            if not self.supabase_service_role_key:
                problems.append("SUPABASE_SERVICE_ROLE_KEY is required")
            if not self.supabase_storage_bucket:
                problems.append("SUPABASE_STORAGE_BUCKET is required")
            if self.secret_key.lower() in INSECURE_SECRETS or len(self.secret_key) < 32:
                problems.append("SECRET_KEY must be random, 32+ characters")
            if "localhost" in self.frontend_url or "127.0.0.1" in self.frontend_url:
                problems.append("FRONTEND_URL must be the deployed frontend URL")
            if "localhost" in url or "127.0.0.1" in url:
                problems.append("DATABASE_URL must not point to localhost")
            if self.debug:
                problems.append("DEBUG must be false")
            if problems:
                raise ValueError("Invalid production configuration: " + "; ".join(problems))
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def allowed_origins(self) -> list[str]:
        extras = [
            origin.strip().rstrip("/")
            for origin in (self.cors_origins or "").split(",")
            if origin.strip() and origin.strip() != "*"
        ]
        return list(dict.fromkeys([self.frontend_url, *extras]))

    @property
    def storage_configured(self) -> bool:
        return bool(
            self.supabase_url
            and self.supabase_service_role_key
            and self.supabase_storage_bucket
        )

    @property
    def show_docs(self) -> bool:
        # /docs only in development
        return not self.is_production


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()