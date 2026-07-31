from __future__ import annotations

from sqlalchemy import create_engine

from app.core.settings import settings


def normalize_database_url(
    database_url: str,
) -> str:
    """Normaliza URLs PostgreSQL para o driver psycopg 3."""

    normalized = str(
        database_url or ""
    ).strip()

    if normalized.startswith("postgres://"):
        return (
            "postgresql+psycopg://"
            + normalized[len("postgres://"):]
        )

    if normalized.startswith("postgresql://"):
        return (
            "postgresql+psycopg://"
            + normalized[len("postgresql://"):]
        )

    return normalized


database_url = normalize_database_url(
    settings.DATABASE_URL
)

engine_options: dict[str, object] = {
    "future": True,
    "echo": settings.DATABASE_ECHO,
    "pool_pre_ping": True,
}

if database_url.startswith("sqlite"):
    engine_options["connect_args"] = {
        "check_same_thread": False,
    }

engine = create_engine(
    database_url,
    **engine_options,
)
