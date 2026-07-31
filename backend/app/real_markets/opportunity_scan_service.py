from __future__ import annotations

import asyncio
from copy import deepcopy
from time import monotonic
from typing import Any, Callable

from app.core.settings import settings
from app.real_markets.opportunity_monitor import (
    real_opportunity_monitor,
)
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)


class RealOpportunityScanService:
    """Cache e coleta unica para o radar somente leitura."""

    def __init__(
        self,
        *,
        monitor: Any = real_opportunity_monitor,
        cache_ttl_seconds: float | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        configured_ttl = (
            settings.REAL_OPPORTUNITY_CACHE_TTL_SECONDS
            if cache_ttl_seconds is None
            else cache_ttl_seconds
        )

        self.monitor = monitor
        self.cache_ttl_seconds = max(
            0.0,
            float(configured_ttl),
        )
        self.clock = clock

        self._cache: dict[
            tuple[int, float, float, int],
            tuple[
                float,
                int,
                dict[str, Any],
            ],
        ] = {}

        self._cache_generation = 0
        self._scan_lock = asyncio.Lock()

    @staticmethod
    def _configuration_key(
        configuration: RadarConfiguration,
    ) -> tuple[int, float, float, int]:
        limit = max(
            1,
            min(
                int(configuration.limit_per_connector),
                100,
            ),
        )

        fee_buffer = max(
            0.0,
            min(
                float(configuration.fee_buffer),
                0.25,
            ),
        )

        near_threshold = max(
            0.0,
            min(
                float(configuration.near_threshold),
                0.25,
            ),
        )

        concurrency = max(
            1,
            min(
                int(configuration.concurrency),
                20,
            ),
        )

        return (
            limit,
            round(fee_buffer, 10),
            round(near_threshold, 10),
            concurrency,
        )

    def _cached_payload(
        self,
        key: tuple[int, float, float, int],
        *,
        now: float,
        newer_than_generation: int | None = None,
    ) -> dict[str, Any] | None:
        entry = self._cache.get(key)

        if entry is None:
            return None

        (
            created_at,
            generation,
            source_payload,
        ) = entry

        if (
            newer_than_generation is not None
            and generation <= newer_than_generation
        ):
            return None

        cache_age = max(
            0.0,
            now - created_at,
        )

        if cache_age > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None

        payload = deepcopy(source_payload)
        monitoring = dict(
            payload.get("monitoring") or {}
        )

        monitoring.update({
            "cache_hit": True,
            "cache_age_seconds": round(
                cache_age,
                3,
            ),
            "cache_ttl_seconds": (
                self.cache_ttl_seconds
            ),
        })

        payload["monitoring"] = monitoring

        return payload

    async def scan(
        self,
        configuration: RadarConfiguration | None = None,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        config = configuration or RadarConfiguration()
        key = self._configuration_key(config)
        request_started_at = self.clock()

        existing_entry = self._cache.get(key)
        starting_generation = (
            existing_entry[1]
            if existing_entry is not None
            else 0
        )

        if not force_refresh:
            cached = self._cached_payload(
                key,
                now=request_started_at,
            )

            if cached is not None:
                return cached

        async with self._scan_lock:
            now = self.clock()

            cached = self._cached_payload(
                key,
                now=now,
                newer_than_generation=(
                    starting_generation
                    if force_refresh
                    else None
                ),
            )

            if cached is not None:
                return cached

            payload = await self.monitor.scan(config)
            completed_at = self.clock()

            result = deepcopy(payload)
            monitoring = dict(
                result.get("monitoring") or {}
            )

            monitoring.update({
                "cache_hit": False,
                "cache_age_seconds": 0.0,
                "cache_ttl_seconds": (
                    self.cache_ttl_seconds
                ),
            })

            result["monitoring"] = monitoring

            self._cache_generation += 1

            self._cache[key] = (
                completed_at,
                self._cache_generation,
                deepcopy(result),
            )

            return result

    async def get_history(
        self,
        connector_id: str,
        market_id: str,
        *,
        limit: int = 60,
    ) -> dict[str, Any]:
        return await self.monitor.get_history(
            connector_id,
            market_id,
            limit=limit,
        )

    def clear_cache(self) -> None:
        self._cache.clear()


real_opportunity_scan_service = (
    RealOpportunityScanService()
)
