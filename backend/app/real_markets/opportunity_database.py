from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from app.core.settings import settings
from app.database.database import normalize_database_url


ObservationBase = declarative_base()


def build_observation_session_factory(
    database_url: str,
) -> sessionmaker | None:
    normalized_url = normalize_database_url(
        database_url
    )

    if not normalized_url:
        return None

    engine_options: dict[str, Any] = {
        "future": True,
        "echo": settings.DATABASE_ECHO,
        "pool_pre_ping": True,
    }

    if normalized_url.startswith("sqlite"):
        engine_options["connect_args"] = {
            "check_same_thread": False,
        }

    engine = create_engine(
        normalized_url,
        **engine_options,
    )

    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )


real_opportunity_session_factory = (
    build_observation_session_factory(
        settings.REAL_OPPORTUNITY_DATABASE_URL
    )
)
