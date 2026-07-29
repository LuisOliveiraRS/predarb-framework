from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.real_markets.connectors import (
    MockReadOnlyPredictionConnector,
)
from app.real_markets.polymarket import (
    build_polymarket_connector_from_env,
)
from app.real_markets.models import (
    MarketSnapshot,
    NormalizedMarket,
)
from app.real_markets.registry import (
    RealMarketConnectorRegistry,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RealMarketDataService:
    """Gateway consolidado e somente leitura para dados de mercado."""

    def __init__(
        self,
        *,
        registry: RealMarketConnectorRegistry,
        cache_ttl_seconds: float = 30.0,
    ) -> None:
        self.registry = registry
        self.cache_ttl_seconds = max(
            0.0,
            min(
                float(cache_ttl_seconds),
                3600.0,
            ),
        )

        self._snapshot_cache: dict[
            str,
            tuple[float, MarketSnapshot],
        ] = {}

        self._lock = threading.RLock()

        self.refresh_count = 0
        self.refresh_successes = 0
        self.refresh_failures = 0
        self.last_refresh_at: str | None = None
        self.last_refresh_error: str | None = None

    @staticmethod
    def _safe_flags() -> dict[str, Any]:
        return {
            "market_data_only": True,
            "read_only": True,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
        }

    async def connector_health(
        self,
    ) -> list[dict[str, Any]]:
        connectors = self.registry.list()

        if not connectors:
            return []

        results = await asyncio.gather(
            *[
                connector.health()
                for connector in connectors
            ],
            return_exceptions=True,
        )

        payload: list[dict[str, Any]] = []

        for connector, result in zip(
            connectors,
            results,
            strict=True,
        ):
            if isinstance(
                result,
                Exception,
            ):
                payload.append(
                    {
                        "connector_id": (
                            connector.connector_id
                        ),
                        "name": connector.name,
                        "healthy": False,
                        "message": str(result),
                        "checked_at": _utc_now(),
                        "read_only": True,
                        "capabilities": list(
                            connector.capabilities
                        ),
                        "metadata": {},
                    }
                )
            else:
                payload.append(
                    result.to_dict()
                )

        return payload

    async def list_markets(
        self,
        *,
        connector_id: str | None = None,
        limit: int = 100,
    ) -> list[NormalizedMarket]:
        normalized_limit = max(
            1,
            min(int(limit), 1000),
        )

        connectors = (
            [
                self.registry.get(
                    connector_id
                )
            ]
            if connector_id
            else self.registry.list()
        )

        if not connectors:
            return []

        results = await asyncio.gather(
            *[
                connector.list_markets(
                    limit=normalized_limit
                )
                for connector in connectors
            ],
            return_exceptions=True,
        )

        markets: list[NormalizedMarket] = []

        for result in results:
            if isinstance(result, Exception):
                continue

            markets.extend(result)

        markets.sort(
            key=lambda item: (
                item.connector_id,
                item.market_id,
            )
        )

        return markets[:normalized_limit]

    def _cached(
        self,
        key: str,
    ) -> MarketSnapshot | None:
        with self._lock:
            cached = self._snapshot_cache.get(
                key
            )

        if cached is None:
            return None

        cached_at, snapshot = cached

        if (
            time.monotonic() - cached_at
            > self.cache_ttl_seconds
        ):
            with self._lock:
                self._snapshot_cache.pop(
                    key,
                    None,
                )

            return None

        return snapshot

    def _store(
        self,
        snapshot: MarketSnapshot,
    ) -> None:
        with self._lock:
            self._snapshot_cache[
                snapshot.key
            ] = (
                time.monotonic(),
                snapshot,
            )

    async def get_snapshot(
        self,
        *,
        connector_id: str,
        market_id: str,
        force_refresh: bool = False,
    ) -> MarketSnapshot:
        key = (
            f"{connector_id}:"
            f"{market_id}"
        )

        if not force_refresh:
            cached = self._cached(key)

            if cached is not None:
                return cached

        connector = self.registry.get(
            connector_id
        )

        snapshot = await connector.get_snapshot(
            market_id
        )

        if (
            snapshot.market.connector_id
            != connector_id
        ):
            raise RuntimeError(
                "Snapshot retornou connector_id divergente."
            )

        if (
            snapshot.market.market_id
            != market_id
        ):
            raise RuntimeError(
                "Snapshot retornou market_id divergente."
            )

        self._store(snapshot)
        return snapshot

    def latest_snapshots(
        self,
    ) -> list[dict[str, Any]]:
        now = time.monotonic()

        with self._lock:
            items = list(
                self._snapshot_cache.items()
            )

        payload = []

        for key, (
            cached_at,
            snapshot,
        ) in items:
            age_seconds = max(
                0.0,
                now - cached_at,
            )

            payload.append(
                {
                    **snapshot.to_dict(),
                    "cache_age_seconds": round(
                        age_seconds,
                        6,
                    ),
                    "stale": (
                        age_seconds
                        > self.cache_ttl_seconds
                    ),
                }
            )

        payload.sort(
            key=lambda item: item["key"]
        )

        return payload

    async def refresh(
        self,
        *,
        connector_id: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        self.refresh_count += 1
        self.last_refresh_at = _utc_now()
        self.last_refresh_error = None

        try:
            markets = await self.list_markets(
                connector_id=connector_id,
                limit=limit,
            )

            results = await asyncio.gather(
                *[
                    self.get_snapshot(
                        connector_id=(
                            market.connector_id
                        ),
                        market_id=(
                            market.market_id
                        ),
                        force_refresh=True,
                    )
                    for market in markets
                ],
                return_exceptions=True,
            )

            snapshots = []
            failures = []

            for market, result in zip(
                markets,
                results,
                strict=True,
            ):
                if isinstance(
                    result,
                    Exception,
                ):
                    failures.append(
                        {
                            "key": market.key,
                            "error": str(result),
                        }
                    )
                else:
                    snapshots.append(
                        result.to_dict()
                    )

            if failures:
                self.refresh_failures += 1
                self.last_refresh_error = (
                    f"{len(failures)} falha(s)"
                )
            else:
                self.refresh_successes += 1

            return {
                "status": (
                    "SUCCESS"
                    if not failures
                    else "PARTIAL"
                ),
                "refreshed_at": (
                    self.last_refresh_at
                ),
                "requested_markets": len(
                    markets
                ),
                "captured_snapshots": len(
                    snapshots
                ),
                "failures": failures,
                "snapshots": snapshots,
                **self._safe_flags(),
            }

        except Exception as exc:
            self.refresh_failures += 1
            self.last_refresh_error = str(exc)
            raise

    async def health(
        self,
    ) -> dict[str, Any]:
        connector_health = await self.connector_health()

        healthy_count = sum(
            1
            for item in connector_health
            if item.get("healthy") is True
        )

        return {
            "status": (
                "healthy"
                if (
                    connector_health
                    and healthy_count
                    == len(connector_health)
                )
                else (
                    "degraded"
                    if connector_health
                    else "no_connectors"
                )
            ),
            "registered_connectors": len(
                connector_health
            ),
            "healthy_connectors": (
                healthy_count
            ),
            "cached_snapshots": len(
                self.latest_snapshots()
            ),
            "cache_ttl_seconds": (
                self.cache_ttl_seconds
            ),
            "refresh_count": (
                self.refresh_count
            ),
            "refresh_successes": (
                self.refresh_successes
            ),
            "refresh_failures": (
                self.refresh_failures
            ),
            "last_refresh_at": (
                self.last_refresh_at
            ),
            "last_refresh_error": (
                self.last_refresh_error
            ),
            "connectors": connector_health,
            "manual_refresh_required": True,
            **self._safe_flags(),
        }


real_market_registry = (
    RealMarketConnectorRegistry()
)

real_market_registry.register(
    MockReadOnlyPredictionConnector()
)

_polymarket_connector = (
    build_polymarket_connector_from_env()
)

if _polymarket_connector is not None:
    real_market_registry.register(
        _polymarket_connector
    )

real_market_data_service = (
    RealMarketDataService(
        registry=real_market_registry,
        cache_ttl_seconds=30.0,
    )
)
