"""Alembic environment — uses DATABASE_URL from the environment."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool


def _normalize_pg_url(url: str) -> str:
    """Force SQLAlchemy to use the psycopg (v3) driver since we ship psycopg, not psycopg2."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_env_url = os.getenv("DATABASE_URL")
_current_url = _env_url if _env_url is not None else config.get_main_option("sqlalchemy.url")
if _current_url is not None:
    config.set_main_option("sqlalchemy.url", _normalize_pg_url(_current_url))

target_metadata = None  # We hand-write SQL; no autogenerate.


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
