from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

from app.real_markets.opportunity_radar import (
    RadarConfiguration,
    real_opportunity_radar,
)


class RealOpportunityMonitor:
    """Tracks read-only opportunity changes between radar scans."""

    def __init__(
        self,
        *,
        radar: Any = real_opportunity_radar,
        max_points_per_market: int = 60,
        stable_epsilon: float = 0.000001,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.radar = radar
        self.max_points_per_market = max(
            2,
            min(int(max_points_per_market), 1440),
        )
        self.stable_epsilon = max(
            0.0,
            float(stable_epsilon),
        )
        self.clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

        self._history: dict[
            str,
            deque[dict[str, Any]],
        ] = {}
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

        timestamp_text = timestamp.astimezone(
            timezone.utc
        ).isoformat()

        best_markets = payload.get("best_markets", [])

        if not isinstance(best_markets, list):
            best_markets = []

        markets = payload.get("monitoring_markets")

        if not isinstance(markets, list):
            markets = best_markets

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

                history = self._history.get(market_key)

                if history is None:
                    history = deque(
                        maxlen=self.max_points_per_market,
                    )
                    self._history[market_key] = history

                previous = history[-1] if history else None

                gross_edge = self._number(
                    item.get("gross_edge")
                )
                conservative_edge = self._number(
                    item.get("conservative_edge")
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
                    and previous_status != "PROFITABLE"
                )

                point = {
                    "observed_at": timestamp_text,
                    "gross_edge": gross_edge,
                    "conservative_edge": conservative_edge,
                    "total_cost": total_cost,
                    "status": current_status,
                }

                history.append(point)

                item.update({
                    "observed_at": timestamp_text,
                    "is_new": is_new,
                    "previous_gross_edge": previous_edge,
                    "edge_change": edge_change,
                    "trend": trend,
                    "became_profitable": became_profitable,
                    "history_points": len(history),
                })

                enriched_by_key[market_key] = item

                counter_name = {
                    "NEW": "new_count",
                    "IMPROVING": "improving_count",
                    "WORSENING": "worsening_count",
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
                        "observed_at": timestamp_text,
                        "market_data_only": True,
                        "read_only": True,
                        "execution_authorized": False,
                        "financial_execution": False,
                    })

            total_history_points = sum(
                len(points)
                for points in self._history.values()
            )

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
        result["alerts"] = alerts
        result["market_data_only"] = True
        result["read_only"] = True
        result["automatic_execution_authorized"] = False
        result["execution_authorized"] = False
        result["financial_execution"] = False
        result["order_submission_available"] = False

        return result

    async def get_history(
        self,
        connector_id: str,
        market_id: str,
        *,
        limit: int = 60,
    ) -> dict[str, Any]:
        market_key = (
            f"{connector_id.strip()}:{market_id.strip()}"
        )
        safe_limit = max(1, min(int(limit), 1440))

        async with self._lock:
            points = list(
                self._history.get(market_key, ())
            )[-safe_limit:]

        return {
            "connector_id": connector_id,
            "market_id": market_id,
            "points": points,
            "count": len(points),
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


real_opportunity_monitor = RealOpportunityMonitor()
