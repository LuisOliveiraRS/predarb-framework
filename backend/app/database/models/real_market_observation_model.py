from __future__ import annotations

from datetime import datetime
from datetime import timezone

from sqlalchemy import BigInteger
from sqlalchemy import CheckConstraint
from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint

from app.real_markets.opportunity_database import ObservationBase


class RealMarketObservationModel(ObservationBase):
    __tablename__ = "real_market_observations"

    __table_args__ = (
        UniqueConstraint(
            "connector_id",
            "market_id",
            "observed_at",
            name="real_market_observations_unique",
        ),
        CheckConstraint(
            "status in ("
            "'PROFITABLE', "
            "'NEAR_OPPORTUNITY', "
            "'NORMAL'"
            ")",
            name="real_market_observations_status_check",
        ),
        Index(
            "real_market_observations_market_time_idx",
            "connector_id",
            "market_id",
            "observed_at",
        ),
        Index(
            "real_market_observations_time_idx",
            "observed_at",
        ),
        Index(
            "real_market_observations_status_edge_idx",
            "status",
            "gross_edge",
        ),
    )

    id = Column(
        BigInteger().with_variant(
            Integer,
            "sqlite",
        ),
        primary_key=True,
        autoincrement=True,
    )

    observed_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    connector_id = Column(
        String(120),
        nullable=False,
    )

    market_id = Column(
        String(700),
        nullable=False,
    )

    title = Column(
        Text,
        nullable=True,
    )

    source_url = Column(
        String(2000),
        nullable=True,
    )

    yes_ask = Column(
        Numeric(18, 10),
        nullable=True,
    )

    no_ask = Column(
        Numeric(18, 10),
        nullable=True,
    )

    total_cost = Column(
        Numeric(18, 10),
        nullable=False,
    )

    gross_edge = Column(
        Numeric(18, 10),
        nullable=False,
    )

    conservative_edge = Column(
        Numeric(18, 10),
        nullable=False,
    )

    status = Column(
        String(40),
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
