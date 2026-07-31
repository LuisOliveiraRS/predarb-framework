import pytest
from sqlalchemy import text

from app.core.settings import Settings
from app.database.models.real_market_observation_model import (
    RealMarketObservationModel,
)
from app.database.session import Base as CoreBase
from app.real_markets.opportunity_database import (
    ObservationBase,
    build_observation_session_factory,
)
from app.real_markets.opportunity_observation_repository import (
    RealOpportunityObservationRepository,
)


def test_observation_metadata_is_isolated():
    assert RealMarketObservationModel.__tablename__ == (
        "real_market_observations"
    )

    assert (
        "real_market_observations"
        in ObservationBase.metadata.tables
    )

    assert (
        "real_market_observations"
        not in CoreBase.metadata.tables
    )


def test_empty_dedicated_url_creates_no_session():
    assert (
        build_observation_session_factory("")
        is None
    )


def test_dedicated_sqlite_session_works():
    factory = build_observation_session_factory(
        "sqlite://"
    )

    assert factory is not None

    session = factory()

    try:
        assert (
            session.execute(
                text("select 1")
            ).scalar_one()
            == 1
        )
    finally:
        engine = session.get_bind()
        session.close()
        engine.dispose()


def test_repository_fails_safe_without_database():
    repository = (
        RealOpportunityObservationRepository(
            session_factory=None
        )
    )

    result = repository.persist_observations(
        [{
            "connector_id": "fake",
            "market_id": "market-1",
        }],
        observed_at=(
            "2026-07-31T00:00:00+00:00"
        ),
    )

    assert result["status"] == "DEGRADED"
    assert result["persisted"] is False
    assert result["error"] == (
        "PersistenceNotConfigured"
    )
    assert result["read_only"] is True
    assert result["financial_execution"] is False
    assert (
        result["order_submission_available"]
        is False
    )


def test_persistence_requires_dedicated_url():
    with pytest.raises(
        ValueError,
        match=(
            "exige "
            "REAL_OPPORTUNITY_DATABASE_URL"
        ),
    ):
        Settings(
            _env_file=None,
            DATABASE_URL=(
                "sqlite:///core-database.db"
            ),
            REAL_OPPORTUNITY_PERSISTENCE_ENABLED=True,
            REAL_OPPORTUNITY_DATABASE_URL="",
        )
