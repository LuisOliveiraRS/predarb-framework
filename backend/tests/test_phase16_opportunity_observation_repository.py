from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.real_markets.opportunity_database import ObservationBase
from app.real_markets.opportunity_observation_repository import (
    RealOpportunityObservationRepository,
)


def build_repository():
    engine = create_engine(
        "sqlite://",
        connect_args={
            "check_same_thread": False,
        },
        poolclass=StaticPool,
    )

    ObservationBase.metadata.create_all(bind=engine)

    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    return RealOpportunityObservationRepository(
        session_factory=factory,
    )


def observation(
    market_id,
    *,
    gross_edge,
):
    return {
        "connector_id": "fake",
        "market_id": market_id,
        "title": f"Market {market_id}",
        "source_url": "https://example.test",
        "yes_ask": 0.49,
        "no_ask": 0.50,
        "total_cost": 1.0 - gross_edge,
        "gross_edge": gross_edge,
        "conservative_edge": (
            gross_edge - 0.02
        ),
        "status": "NEAR_OPPORTUNITY",
    }


def test_repository_persists_observations():
    repository = build_repository()

    observed_at = datetime(
        2026,
        7,
        31,
        3,
        30,
        tzinfo=timezone.utc,
    )

    result = repository.persist_observations(
        [
            observation(
                "market-1",
                gross_edge=-0.01,
            ),
            observation(
                "market-2",
                gross_edge=-0.02,
            ),
        ],
        observed_at=observed_at,
    )

    assert result["persisted"] is True
    assert result["attempted"] == 2
    assert result["inserted"] == 2
    assert result["skipped"] == 0
    assert result["read_only"] is True
    assert result["execution_authorized"] is False
    assert result["financial_execution"] is False


def test_repository_is_idempotent_per_timestamp():
    repository = build_repository()

    observed_at = datetime(
        2026,
        7,
        31,
        3,
        31,
        tzinfo=timezone.utc,
    )

    items = [
        observation(
            "market-1",
            gross_edge=-0.01,
        )
    ]

    first = repository.persist_observations(
        items,
        observed_at=observed_at,
    )

    second = repository.persist_observations(
        items,
        observed_at=observed_at,
    )

    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["skipped"] == 1


def test_repository_loads_ordered_history():
    repository = build_repository()

    first_time = datetime(
        2026,
        7,
        31,
        3,
        32,
        tzinfo=timezone.utc,
    )

    second_time = first_time + timedelta(
        minutes=1,
    )

    repository.persist_observations(
        [
            observation(
                "market-1",
                gross_edge=-0.02,
            )
        ],
        observed_at=first_time,
    )

    repository.persist_observations(
        [
            observation(
                "market-1",
                gross_edge=-0.01,
            )
        ],
        observed_at=second_time,
    )

    history = repository.load_history(
        "fake",
        "market-1",
        limit=10,
    )

    assert history["count"] == 2
    assert history["points"][0][
        "gross_edge"
    ] == -0.02
    assert history["points"][1][
        "gross_edge"
    ] == -0.01
    assert history["persistence_available"] is True
    assert history["read_only"] is True
    assert history["financial_execution"] is False
