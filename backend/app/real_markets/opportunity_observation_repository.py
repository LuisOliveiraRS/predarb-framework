from __future__ import annotations

from datetime import datetime
from datetime import timezone
from decimal import Decimal
from typing import Any
from typing import Callable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models.real_market_observation_model import (
    RealMarketObservationModel,
)
from app.real_markets.opportunity_database import (
    real_opportunity_session_factory,
)


class RealOpportunityObservationRepository:
    """Persiste somente observacoes publicas de mercado."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session] | None = (
            real_opportunity_session_factory
        ),
    ) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _datetime(value: Any) -> datetime:
        if isinstance(value, datetime):
            resolved = value
        elif isinstance(value, str):
            resolved = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        else:
            resolved = datetime.now(timezone.utc)

        if resolved.tzinfo is None:
            resolved = resolved.replace(
                tzinfo=timezone.utc,
            )

        return resolved.astimezone(timezone.utc)

    @staticmethod
    def _optional_number(
        value: Any,
    ) -> float | None:
        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _required_number(
        value: Any,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _float(
        value: Decimal | float | None,
    ) -> float | None:
        if value is None:
            return None

        return float(value)

    @classmethod
    def _point(
        cls,
        row: RealMarketObservationModel,
    ) -> dict[str, Any]:
        return {
            "observed_at": row.observed_at.isoformat(),
            "yes_ask": cls._float(row.yes_ask),
            "no_ask": cls._float(row.no_ask),
            "total_cost": cls._float(row.total_cost),
            "gross_edge": cls._float(row.gross_edge),
            "conservative_edge": cls._float(
                row.conservative_edge
            ),
            "status": row.status,
        }

    @staticmethod
    def _safety_flags() -> dict[str, bool]:
        return {
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }

    def persist_observations(
        self,
        observations: list[dict[str, Any]],
        *,
        observed_at: datetime | str,
    ) -> dict[str, Any]:
        valid_items = [
            item
            for item in observations
            if isinstance(item, dict)
            and str(
                item.get("connector_id") or ""
            ).strip()
            and str(
                item.get("market_id") or ""
            ).strip()
        ]

        if self.session_factory is None:
            return {
                "status": "DEGRADED",
                "attempted": len(valid_items),
                "inserted": 0,
                "skipped": 0,
                "persisted": False,
                "error": "PersistenceNotConfigured",
                **self._safety_flags(),
            }

        timestamp = self._datetime(observed_at)
        inserted = 0
        skipped = 0
        session: Session | None = None

        try:
            session = self.session_factory()

            for item in valid_items:
                connector_id = str(
                    item.get("connector_id")
                ).strip()

                market_id = str(
                    item.get("market_id")
                ).strip()

                exists = (
                    session.query(
                        RealMarketObservationModel.id
                    )
                    .filter(
                        RealMarketObservationModel.connector_id
                        == connector_id,
                        RealMarketObservationModel.market_id
                        == market_id,
                        RealMarketObservationModel.observed_at
                        == timestamp,
                    )
                    .first()
                )

                if exists is not None:
                    skipped += 1
                    continue

                session.add(
                    RealMarketObservationModel(
                        observed_at=timestamp,
                        connector_id=connector_id,
                        market_id=market_id,
                        title=(
                            str(item.get("title"))
                            if item.get("title") is not None
                            else None
                        ),
                        source_url=(
                            str(item.get("source_url"))
                            if item.get("source_url") is not None
                            else None
                        ),
                        yes_ask=self._optional_number(
                            item.get("yes_ask")
                        ),
                        no_ask=self._optional_number(
                            item.get("no_ask")
                        ),
                        total_cost=self._required_number(
                            item.get("total_cost")
                        ),
                        gross_edge=self._required_number(
                            item.get("gross_edge")
                        ),
                        conservative_edge=(
                            self._required_number(
                                item.get(
                                    "conservative_edge"
                                )
                            )
                        ),
                        status=str(
                            item.get("status") or "NORMAL"
                        ),
                    )
                )

                inserted += 1

            session.commit()

            return {
                "status": "READY",
                "attempted": len(valid_items),
                "inserted": inserted,
                "skipped": skipped,
                "persisted": True,
                "error": None,
                **self._safety_flags(),
            }

        except SQLAlchemyError as exc:
            if session is not None:
                session.rollback()

            return {
                "status": "DEGRADED",
                "attempted": len(valid_items),
                "inserted": 0,
                "skipped": 0,
                "persisted": False,
                "error": type(exc).__name__,
                **self._safety_flags(),
            }

        finally:
            if session is not None:
                session.close()

    def load_histories(
        self,
        market_keys: list[tuple[str, str]],
        *,
        limit_per_market: int = 60,
    ) -> dict[str, Any]:
        safe_limit = max(
            1,
            min(int(limit_per_market), 1440),
        )

        normalized_keys = list(dict.fromkeys(
            (
                str(connector_id).strip(),
                str(market_id).strip(),
            )
            for connector_id, market_id in market_keys
            if str(connector_id).strip()
            and str(market_id).strip()
        ))

        if self.session_factory is None:
            return {
                "histories": {},
                "markets_requested": len(
                    normalized_keys
                ),
                "markets_loaded": 0,
                "persistence_available": False,
                "error": "PersistenceNotConfigured",
                **self._safety_flags(),
            }

        histories: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        session: Session | None = None

        try:
            session = self.session_factory()

            for connector_id, market_id in normalized_keys:
                rows = (
                    session.query(
                        RealMarketObservationModel
                    )
                    .filter(
                        RealMarketObservationModel.connector_id
                        == connector_id,
                        RealMarketObservationModel.market_id
                        == market_id,
                    )
                    .order_by(
                        RealMarketObservationModel.observed_at
                        .desc()
                    )
                    .limit(safe_limit)
                    .all()
                )

                rows.reverse()

                histories[
                    f"{connector_id}:{market_id}"
                ] = [
                    self._point(row)
                    for row in rows
                ]

            return {
                "histories": histories,
                "markets_requested": len(
                    normalized_keys
                ),
                "markets_loaded": sum(
                    1
                    for points in histories.values()
                    if points
                ),
                "persistence_available": True,
                "error": None,
                **self._safety_flags(),
            }

        except SQLAlchemyError as exc:
            if session is not None:
                session.rollback()

            return {
                "histories": {},
                "markets_requested": len(
                    normalized_keys
                ),
                "markets_loaded": 0,
                "persistence_available": False,
                "error": type(exc).__name__,
                **self._safety_flags(),
            }

        finally:
            if session is not None:
                session.close()

    def load_history(
        self,
        connector_id: str,
        market_id: str,
        *,
        limit: int = 60,
    ) -> dict[str, Any]:
        result = self.load_histories(
            [(connector_id, market_id)],
            limit_per_market=limit,
        )

        key = (
            f"{connector_id.strip()}:"
            f"{market_id.strip()}"
        )

        points = result["histories"].get(
            key,
            [],
        )

        return {
            "connector_id": connector_id,
            "market_id": market_id,
            "points": points,
            "count": len(points),
            "persistence_available": result[
                "persistence_available"
            ],
            "error": result["error"],
            **self._safety_flags(),
        }


real_opportunity_observation_repository = (
    RealOpportunityObservationRepository()
)
