from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import Callable

from app.core.settings import settings
from app.real_markets.opportunity_observation_repository import (
    real_opportunity_observation_repository,
)
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
    real_opportunity_radar,
)


class RealOpportunityMonitor:
    """Tracks read-only opportunity changes between scans."""

    def __init__(
        self,
        *,
        radar: Any = real_opportunity_radar,
        max_points_per_market: int | None = None,
        stable_epsilon: float = 0.000001,
        clock: Callable[[], datetime] | None = None,
        repository: Any = (
            real_opportunity_observation_repository
        ),
        persistence_enabled: bool | None = None,
    ) -> None:
        configured_limit = (
            settings
            .REAL_OPPORTUNITY_PERSISTENCE_HISTORY_LIMIT
            if max_points_per_market is None
            else max_points_per_market
        )

        self.radar = radar
        self.max_points_per_market = max(
            2,
            min(int(configured_limit), 1440),
        )
        self.stable_epsilon = max(
            0.0,
            float(stable_epsilon),
        )
        self.clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self.repository = repository
        self.persistence_enabled = (
            settings.REAL_OPPORTUNITY_PERSISTENCE_ENABLED
            if persistence_enabled is None
            else bool(persistence_enabled)
        )

        self._history: dict[
            str,
            deque[dict[str, Any]],
        ] = {}

        self._hydrated_keys: set[str] = set()
        self._lock = asyncio.Lock()

    @staticmethod
    def _market_key(item: dict[str, Any]) -> str:
        connector_id = str(
            item.get("connector_id") or ""
        ).strip()

        market_id = str(
            item.get("market_id") or ""
        ).strip()

        return f"{connector_id}:{market_id}"

    @staticmethod
    def _number(
        value: Any,
        default: float = 0.0,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _trend(
        self,
        edge_change: float | None,
    ) -> str:
        if edge_change is None:
            return "NEW"

        if edge_change > self.stable_epsilon:
            return "IMPROVING"

        if edge_change < -self.stable_epsilon:
            return "WORSENING"

        return "STABLE"

    async def _hydrate_histories(
        self,
        markets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        state = {
            "enabled": self.persistence_enabled,
            "available": False,
            "markets_requested": 0,
            "markets_loaded": 0,
            "error": None,
        }

        if (
            not self.persistence_enabled
            or self.repository is None
        ):
            return state

        pairs: list[tuple[str, str]] = []

        for item in markets:
            if not isinstance(item, dict):
                continue

            connector_id = str(
                item.get("connector_id") or ""
            ).strip()

            market_id = str(
                item.get("market_id") or ""
            ).strip()

            market_key = (
                f"{connector_id}:{market_id}"
            )

            if (
                connector_id
                and market_id
                and market_key
                not in self._hydrated_keys
            ):
                pairs.append(
                    (
                        connector_id,
                        market_id,
                    )
                )

        if not pairs:
            state["available"] = True
            return state

        try:
            loaded = await asyncio.to_thread(
                self.repository.load_histories,
                pairs,
                limit_per_market=(
                    self.max_points_per_market
                ),
            )
        except Exception as exc:
            state["error"] = type(exc).__name__
            return state

        state.update({
            "available": bool(
                loaded.get(
                    "persistence_available",
                    False,
                )
            ),
            "markets_requested": int(
                loaded.get(
                    "markets_requested",
                    len(pairs),
                )
                or 0
            ),
            "markets_loaded": int(
                loaded.get(
                    "markets_loaded",
                    0,
                )
                or 0
            ),
            "error": loaded.get("error"),
        })

        if not state["available"]:
            return state

        histories = loaded.get("histories") or {}

        async with self._lock:
            for connector_id, market_id in pairs:
                market_key = (
                    f"{connector_id}:{market_id}"
                )

                persisted_points = histories.get(
                    market_key,
                    [],
                )

                if (
                    market_key not in self._history
                    and isinstance(
                        persisted_points,
                        list,
                    )
                ):
                    self._history[market_key] = deque(
                        (
                            dict(point)
                            for point in persisted_points
                            if isinstance(point, dict)
                        ),
                        maxlen=(
                            self.max_points_per_market
                        ),
                    )

                self._hydrated_keys.add(
                    market_key
                )

        return state

    async def scan(
        self,
        configuration: RadarConfiguration | None = None,
    ) -> dict[str, Any]:
        payload = await self.radar.scan(configuration)
        return await self.record(payload)

    async def record(
        self,
        payload: dict[str, Any],
        *,
        observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        timestamp = observed_at or self.clock()

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc,
            )

        timestamp = timestamp.astimezone(
            timezone.utc
        )
        timestamp_text = timestamp.isoformat()

        best_markets = payload.get(
            "best_markets",
            [],
        )

        if not isinstance(best_markets, list):
            best_markets = []

        markets = payload.get(
            "monitoring_markets"
        )

        if not isinstance(markets, list):
            markets = best_markets

        hydration = await self._hydrate_histories(
            markets
        )

        enriched_by_key: dict[
            str,
            dict[str, Any],
        ] = {}

        alerts: list[dict[str, Any]] = []

        counters = {
            "new_count": 0,
            "improving_count": 0,
            "worsening_count": 0,
            "stable_count": 0,
            "became_profitable_count": 0,
        }

        async with self._lock:
            for source_item in markets:
                if not isinstance(source_item, dict):
                    continue

                item = dict(source_item)
                market_key = self._market_key(item)

                if market_key == ":":
                    continue

                history = self._history.get(
                    market_key
                )

                if history is None:
                    history = deque(
                        maxlen=(
                            self.max_points_per_market
                        ),
                    )
                    self._history[market_key] = (
                        history
                    )

                previous = (
                    history[-1]
                    if history
                    else None
                )

                gross_edge = self._number(
                    item.get("gross_edge")
                )
                conservative_edge = self._number(
                    item.get(
                        "conservative_edge"
                    )
                )
                total_cost = self._number(
                    item.get("total_cost")
                )
                current_status = str(
                    item.get("status") or "NORMAL"
                )

                previous_edge = (
                    previous["gross_edge"]
                    if previous is not None
                    else None
                )

                edge_change = (
                    round(
                        gross_edge - previous_edge,
                        10,
                    )
                    if previous_edge is not None
                    else None
                )

                trend = self._trend(edge_change)
                is_new = previous is None

                previous_status = (
                    previous["status"]
                    if previous is not None
                    else None
                )

                became_profitable = (
                    current_status == "PROFITABLE"
                    and previous_status
                    != "PROFITABLE"
                )

                point = {
                    "observed_at": timestamp_text,
                    "gross_edge": gross_edge,
                    "conservative_edge": (
                        conservative_edge
                    ),
                    "total_cost": total_cost,
                    "status": current_status,
                }

                history.append(point)

                item.update({
                    "observed_at": timestamp_text,
                    "is_new": is_new,
                    "previous_gross_edge": (
                        previous_edge
                    ),
                    "edge_change": edge_change,
                    "trend": trend,
                    "became_profitable": (
                        became_profitable
                    ),
                    "history_points": len(history),
                })

                enriched_by_key[
                    market_key
                ] = item

                counter_name = {
                    "NEW": "new_count",
                    "IMPROVING": (
                        "improving_count"
                    ),
                    "WORSENING": (
                        "worsening_count"
                    ),
                    "STABLE": "stable_count",
                }[trend]

                counters[counter_name] += 1

                if became_profitable:
                    counters[
                        "became_profitable_count"
                    ] += 1

                    alerts.append({
                        "type": "BECAME_PROFITABLE",
                        "connector_id": item.get(
                            "connector_id"
                        ),
                        "market_id": item.get(
                            "market_id"
                        ),
                        "title": item.get("title"),
                        "gross_edge": gross_edge,
                        "conservative_edge": (
                            conservative_edge
                        ),
                        "observed_at": (
                            timestamp_text
                        ),
                        "market_data_only": True,
                        "read_only": True,
                        "execution_authorized": False,
                        "financial_execution": False,
                    })

            total_history_points = sum(
                len(points)
                for points in self._history.values()
            )

        persistence = {
            "enabled": self.persistence_enabled,
            "available": hydration["available"],
            "persisted": False,
            "attempted": 0,
            "inserted": 0,
            "skipped": 0,
            "hydrated_markets": hydration[
                "markets_loaded"
            ],
            "error": hydration["error"],
        }

        if (
            self.persistence_enabled
            and self.repository is not None
        ):
            try:
                persisted = await asyncio.to_thread(
                    self.repository.persist_observations,
                    list(
                        enriched_by_key.values()
                    ),
                    observed_at=timestamp,
                )

                persistence.update({
                    "available": bool(
                        persisted.get(
                            "persisted",
                            False,
                        )
                    ),
                    "persisted": bool(
                        persisted.get(
                            "persisted",
                            False,
                        )
                    ),
                    "attempted": int(
                        persisted.get(
                            "attempted",
                            0,
                        )
                        or 0
                    ),
                    "inserted": int(
                        persisted.get(
                            "inserted",
                            0,
                        )
                        or 0
                    ),
                    "skipped": int(
                        persisted.get(
                            "skipped",
                            0,
                        )
                        or 0
                    ),
                    "error": persisted.get(
                        "error"
                    ),
                })

            except Exception as exc:
                persistence.update({
                    "available": False,
                    "persisted": False,
                    "error": type(exc).__name__,
                })

        enriched_best_markets: list[
            dict[str, Any]
        ] = []

        for source_item in best_markets:
            if not isinstance(source_item, dict):
                continue

            market_key = self._market_key(
                source_item
            )

            enriched = enriched_by_key.get(
                market_key
            )

            if enriched is not None:
                enriched_best_markets.append(
                    dict(enriched)
                )

        result = dict(payload)
        result.pop("monitoring_markets", None)
        result["best_markets"] = (
            enriched_best_markets
        )

        result["monitoring"] = {
            "observed_at": timestamp_text,
            "markets_observed": len(
                enriched_by_key
            ),
            "tracked_markets": len(
                self._history
            ),
            "history_points": (
                total_history_points
            ),
            **counters,
        }

        result["persistence"] = persistence
        result["alerts"] = alerts
        result["market_data_only"] = True
        result["read_only"] = True
        result[
            "automatic_execution_authorized"
        ] = False
        result["execution_authorized"] = False
        result["financial_execution"] = False
        result[
            "order_submission_available"
        ] = False

        return result

    async def get_history(
        self,
        connector_id: str,
        market_id: str,
        *,
        limit: int = 60,
    ) -> dict[str, Any]:
        safe_limit = max(
            1,
            min(int(limit), 1440),
        )

        if (
            self.persistence_enabled
            and self.repository is not None
        ):
            try:
                persistent = await asyncio.to_thread(
                    self.repository.load_history,
                    connector_id,
                    market_id,
                    limit=safe_limit,
                )

                if (
                    persistent.get(
                        "persistence_available"
                    )
                    and persistent.get("count", 0)
                    > 0
                ):
                    persistent["source"] = (
                        "persistent"
                    )
                    return persistent

            except Exception:
                pass

        market_key = (
            f"{connector_id.strip()}:"
            f"{market_id.strip()}"
        )

        async with self._lock:
            points = list(
                self._history.get(
                    market_key,
                    (),
                )
            )[-safe_limit:]

        return {
            "connector_id": connector_id,
            "market_id": market_id,
            "points": points,
            "count": len(points),
            "source": "memory",
            "persistence_available": False,
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


real_opportunity_monitor = RealOpportunityMonitor()
