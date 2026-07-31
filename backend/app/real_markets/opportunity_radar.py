from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.real_markets.kalshi import (
    build_kalshi_connector_from_env,
)
from app.real_markets.polymarket import (
    build_polymarket_connector_from_env,
)


@dataclass(frozen=True, slots=True)
class RadarConfiguration:
    limit_per_connector: int = 40
    fee_buffer: float = 0.02
    near_threshold: float = 0.04
    concurrency: int = 8


class RealOpportunityRadar:
    """Radar somente leitura de ineficiencias YES + NO."""

    def __init__(
        self,
        *,
        connectors: list[Any] | None = None,
    ) -> None:
        if connectors is None:
            connectors = [
                build_polymarket_connector_from_env(),
                build_kalshi_connector_from_env(),
            ]

        self.connectors = [
            connector
            for connector in connectors
            if connector is not None
        ]

    @staticmethod
    def _quote(snapshot: Any, outcome_id: str) -> Any | None:
        target = outcome_id.strip().upper()

        for quote in snapshot.quotes:
            if quote.outcome_id.strip().upper() == target:
                return quote

        return None

    async def _scan_market(
        self,
        connector: Any,
        market: Any,
        *,
        semaphore: asyncio.Semaphore,
        fee_buffer: float,
        near_threshold: float,
    ) -> dict[str, Any] | None:
        async with semaphore:
            try:
                snapshot = await connector.get_snapshot(
                    market.market_id
                )
            except Exception:
                return None

        yes = self._quote(snapshot, "YES")
        no = self._quote(snapshot, "NO")

        if yes is None or no is None:
            return None

        if yes.ask is None or no.ask is None:
            return None

        total_cost = round(
            float(yes.ask) + float(no.ask),
            10,
        )

        gross_edge = round(1.0 - total_cost, 10)
        conservative_edge = round(
            gross_edge - fee_buffer,
            10,
        )

        if conservative_edge > 0:
            status = "PROFITABLE"
        elif gross_edge >= -near_threshold:
            status = "NEAR_OPPORTUNITY"
        else:
            status = "NORMAL"

        return {
            "connector_id": connector.connector_id,
            "market_id": market.market_id,
            "title": market.title,
            "source_url": market.source_url,
            "close_time": market.close_time,
            "yes_ask": yes.ask,
            "no_ask": no.ask,
            "total_cost": total_cost,
            "gross_edge": gross_edge,
            "fee_buffer": fee_buffer,
            "conservative_edge": conservative_edge,
            "status": status,
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }

    async def scan(
        self,
        configuration: RadarConfiguration | None = None,
    ) -> dict[str, Any]:
        config = configuration or RadarConfiguration()

        limit = max(
            1,
            min(int(config.limit_per_connector), 100),
        )

        fee_buffer = max(
            0.0,
            min(float(config.fee_buffer), 0.25),
        )

        near_threshold = max(
            0.0,
            min(float(config.near_threshold), 0.25),
        )

        semaphore = asyncio.Semaphore(
            max(1, min(int(config.concurrency), 20))
        )

        connector_results: list[dict[str, Any]] = []
        all_results: list[dict[str, Any]] = []

        for connector in self.connectors:
            try:
                markets = await connector.list_markets(
                    limit=limit
                )
            except Exception as exc:
                connector_results.append({
                    "connector_id": connector.connector_id,
                    "markets_loaded": 0,
                    "markets_priced": 0,
                    "error": str(exc),
                })
                continue

            tasks = [
                self._scan_market(
                    connector,
                    market,
                    semaphore=semaphore,
                    fee_buffer=fee_buffer,
                    near_threshold=near_threshold,
                )
                for market in markets
            ]

            scanned = await asyncio.gather(*tasks)

            valid = [
                item
                for item in scanned
                if item is not None
            ]

            all_results.extend(valid)

            connector_results.append({
                "connector_id": connector.connector_id,
                "markets_loaded": len(markets),
                "markets_priced": len(valid),
                "error": None,
            })

        all_results.sort(
            key=lambda item: item["gross_edge"],
            reverse=True,
        )

        profitable = [
            item
            for item in all_results
            if item["status"] == "PROFITABLE"
        ]

        near = [
            item
            for item in all_results
            if item["status"] == "NEAR_OPPORTUNITY"
        ]

        return {
            "status": "READY",
            "connectors": connector_results,
            "markets_priced": len(all_results),
            "profitable_count": len(profitable),
            "near_opportunity_count": len(near),
            "profitable": profitable,
            "near_opportunities": near[:30],
            "best_markets": all_results[:30],
            "monitoring_markets": all_results,
            "configuration": {
                "limit_per_connector": limit,
                "fee_buffer": fee_buffer,
                "near_threshold": near_threshold,
            },
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


real_opportunity_radar = RealOpportunityRadar()
