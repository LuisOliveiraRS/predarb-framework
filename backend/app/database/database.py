from __future__ import annotations

from sqlalchemy import create_engine

from app.core.settings import settings


engine_options: dict[str, object] = {
    "future": True,
    "echo": settings.DATABASE_ECHO,
    "pool_pre_ping": True,
}

if settings.DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    **engine_options,
)
