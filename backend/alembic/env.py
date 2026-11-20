from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from app.core.config import settings
from app.core.database import Base
from app.models import DocumentChunk, Report, Role, User, ReconciliationRun  # noqa: F401


# Alembic Config object
config = context.config


# Configure Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# SQLAlchemy metadata used by Alembic
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Get the database URL from application settings.

    The actual DATABASE_URL is loaded from .env
    through app.core.config.Settings.
    """
    return settings.database_url


def run_migrations_offline() -> None:
    """
    Run migrations without creating a database connection.
    """

    database_url = get_database_url()

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations using an active database connection.
    """

    configuration = config.get_section(
        config.config_ini_section,
        {},
    )

    # Use DATABASE_URL from .env instead of hardcoding
    # credentials inside alembic.ini.
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()