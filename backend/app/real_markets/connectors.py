from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from app.real_markets.models import (
    ConnectorHealth,
    MarketOutcome,
    MarketQuote,
    MarketSnapshot,
    NormalizedMarket,
    utc_now,
)


class ReadOnlyMarketConnector(ABC):
    """Contrato único para conectores de dados de mercado."""

    connector_id: str
    name: str
    kind: str = "prediction_market"
    read_only: bool = True

    @property
    def capabilities(
        self,
    ) -> tuple[str, ...]:
        return (
            "market_data",
            "quotes",
            "snapshots",
        )

    @abstractmethod
    async def health(
        self,
    ) -> ConnectorHealth:
        raise NotImplementedError

    @abstractmethod
    async def list_markets(
        self,
        *,
        limit: int = 100,
    ) -> list[NormalizedMarket]:
        raise NotImplementedError

    @abstractmethod
    async def get_snapshot(
        self,
        market_id: str,
    ) -> MarketSnapshot:
        raise NotImplementedError

    def descriptor(
        self,
    ) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "name": self.name,
            "kind": self.kind,
            "read_only": self.read_only,
            "capabilities": list(
                self.capabilities
            ),
        }


class MockReadOnlyPredictionConnector(
    ReadOnlyMarketConnector
):
    connector_id = "mock-real-market"
    name = "Mock Real Market Data"
    kind = "prediction_market"
    read_only = True

    def __init__(self) -> None:
        self._markets = {
            "btc-100k-2026": NormalizedMarket(
                connector_id=self.connector_id,
                market_id="btc-100k-2026",
                title=(
                    "Bitcoin ficará acima de "
                    "US$ 100 mil no fim de 2026?"
                ),
                status="OPEN",
                outcomes=(
                    MarketOutcome(
                        outcome_id="YES",
                        label="Sim",
                        token_id="mock-yes-1",
                    ),
                    MarketOutcome(
                        outcome_id="NO",
                        label="Não",
                        token_id="mock-no-1",
                    ),
                ),
                close_time=(
                    "2026-12-31T23:59:59+00:00"
                ),
                category="crypto",
                source_url=(
                    "mock://btc-100k-2026"
                ),
                metadata={
                    "fixture": True,
                },
            ),
            "eth-10k-2026": NormalizedMarket(
                connector_id=self.connector_id,
                market_id="eth-10k-2026",
                title=(
                    "Ethereum ficará acima de "
                    "US$ 10 mil no fim de 2026?"
                ),
                status="OPEN",
                outcomes=(
                    MarketOutcome(
                        outcome_id="YES",
                        label="Sim",
                        token_id="mock-yes-2",
                    ),
                    MarketOutcome(
                        outcome_id="NO",
                        label="Não",
                        token_id="mock-no-2",
                    ),
                ),
                close_time=(
                    "2026-12-31T23:59:59+00:00"
                ),
                category="crypto",
                source_url=(
                    "mock://eth-10k-2026"
                ),
                metadata={
                    "fixture": True,
                },
            ),
        }

        self._quotes = {
            "btc-100k-2026": (
                MarketQuote(
                    connector_id=self.connector_id,
                    market_id="btc-100k-2026",
                    outcome_id="YES",
                    bid=0.61,
                    ask=0.63,
                    last=0.62,
                    bid_size=1500,
                    ask_size=1400,
                ),
                MarketQuote(
                    connector_id=self.connector_id,
                    market_id="btc-100k-2026",
                    outcome_id="NO",
                    bid=0.37,
                    ask=0.39,
                    last=0.38,
                    bid_size=1400,
                    ask_size=1500,
                ),
            ),
            "eth-10k-2026": (
                MarketQuote(
                    connector_id=self.connector_id,
                    market_id="eth-10k-2026",
                    outcome_id="YES",
                    bid=0.28,
                    ask=0.31,
                    last=0.30,
                    bid_size=900,
                    ask_size=850,
                ),
                MarketQuote(
                    connector_id=self.connector_id,
                    market_id="eth-10k-2026",
                    outcome_id="NO",
                    bid=0.69,
                    ask=0.72,
                    last=0.70,
                    bid_size=850,
                    ask_size=900,
                ),
            ),
        }

    async def health(
        self,
    ) -> ConnectorHealth:
        await asyncio.sleep(0)

        return ConnectorHealth(
            connector_id=self.connector_id,
            name=self.name,
            healthy=True,
            message=(
                "Conector mock somente leitura disponível."
            ),
            capabilities=self.capabilities,
            metadata={
                "fixture": True,
                "market_count": len(
                    self._markets
                ),
            },
        )

    async def list_markets(
        self,
        *,
        limit: int = 100,
    ) -> list[NormalizedMarket]:
        await asyncio.sleep(0)

        normalized_limit = max(
            1,
            min(int(limit), 1000),
        )

        return list(
            self._markets.values()
        )[:normalized_limit]

    async def get_snapshot(
        self,
        market_id: str,
    ) -> MarketSnapshot:
        await asyncio.sleep(0)

        market = self._markets.get(
            market_id
        )

        if market is None:
            raise KeyError(
                f"Mercado não encontrado: {market_id}"
            )

        quotes = self._quotes[
            market_id
        ]

        return MarketSnapshot(
            market=market,
            quotes=quotes,
            captured_at=utc_now(),
            source_latency_ms=0.1,
            raw_reference=(
                f"mock://{market_id}/snapshot"
            ),
            metadata={
                "fixture": True,
                "read_only": True,
            },
        )
