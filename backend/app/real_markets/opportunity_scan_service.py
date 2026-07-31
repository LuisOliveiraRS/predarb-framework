from __future__ import annotations

import asyncio
from concurrent.futures import Future
from copy import deepcopy
from threading import RLock
from time import monotonic
from typing import Any
from typing import Callable

from app.core.settings import settings
from app.real_markets.opportunity_monitor import (
    real_opportunity_monitor,
)
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)


ConfigurationKey = tuple[
    int,
    float,
    float,
    int,
]


class RealOpportunityScanService:
    """Cache e coleta unica entre threads e event loops."""

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
            ConfigurationKey,
            tuple[
                float,
                int,
                dict[str, Any],
            ],
        ] = {}

        self._latest_entry: tuple[
            float,
            int,
            ConfigurationKey,
            dict[str, Any],
        ] | None = None

        self._inflight: dict[
            ConfigurationKey,
            Future,
        ] = {}

        self._cache_generation = 0
        self._state_lock = RLock()

    @staticmethod
    def _configuration_key(
        configuration: RadarConfiguration,
    ) -> ConfigurationKey:
        return (
            max(
                1,
                min(
                    int(
                        configuration.limit_per_connector
                    ),
                    100,
                ),
            ),
            round(
                max(
                    0.0,
                    min(
                        float(
                            configuration.fee_buffer
                        ),
                        0.25,
                    ),
                ),
                10,
            ),
            round(
                max(
                    0.0,
                    min(
                        float(
                            configuration.near_threshold
                        ),
                        0.25,
                    ),
                ),
                10,
            ),
            max(
                1,
                min(
                    int(configuration.concurrency),
                    20,
                ),
            ),
        )

    @staticmethod
    def _describe_key(
        key: ConfigurationKey | None,
    ) -> dict[str, Any] | None:
        if key is None:
            return None

        (
            limit_per_connector,
            fee_buffer,
            near_threshold,
            concurrency,
        ) = key

        return {
            "limit_per_connector": limit_per_connector,
            "fee_buffer": fee_buffer,
            "near_threshold": near_threshold,
            "concurrency": concurrency,
        }

    def _snapshot_max_age_seconds(self) -> float:
        """
        Idade maxima aceita para um snapshot.

        Quando o coletor automatico esta ativo, a
        referencia e o intervalo do coletor. Sem ele,
        a referencia e o TTL do cache, porque o
        snapshot so e renovado por coletas explicitas.
        """

        multiplier = max(
            1,
            min(
                int(
                    settings
                    .REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER
                ),
                10,
            ),
        )

        if (
            settings
            .REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED
        ):
            base = float(
                settings
                .REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS
            )
        else:
            base = float(self.cache_ttl_seconds)

        return max(1.0, base) * multiplier

    def _cached_payload_locked(
        self,
        key: ConfigurationKey,
        *,
        now: float,
    ) -> dict[str, Any] | None:
        entry = self._cache.get(key)

        if entry is None:
            return None

        created_at, _, source_payload = entry

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
            "shared_scan": False,
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

    @staticmethod
    def _warming_up_payload() -> dict[str, Any]:
        return {
            "status": "WARMING_UP",
            "markets_priced": 0,
            "profitable_count": 0,
            "near_opportunity_count": 0,
            "best_markets": [],
            "alerts": [],
            "monitoring": {
                "snapshot_available": False,
                "served_from_snapshot": True,
                "snapshot_is_stale": False,
                "snapshot_configuration_match": True,
                "snapshot_configuration": None,
                "requested_configuration": None,
                "cache_hit": False,
                "history_points": 0,
                "tracked_markets": 0,
            },
            "persistence": {
                "enabled": bool(
                    settings
                    .REAL_OPPORTUNITY_PERSISTENCE_ENABLED
                ),
                "available": False,
                "persisted": False,
            },
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }

    def scan(
        self,
        configuration: RadarConfiguration | None = None,
        *,
        force_refresh: bool = False,
    ) -> Any:
        """
        Cria a requisicao de coleta.

        A geracao atual e capturada sincronamente,
        antes da criacao ou execucao do event loop.
        Isso permite agrupar force refresh iniciados
        simultaneamente em threads diferentes.
        """

        config = configuration or RadarConfiguration()
        key = self._configuration_key(config)

        with self._state_lock:
            existing_entry = self._cache.get(key)

            starting_generation = (
                existing_entry[1]
                if existing_entry is not None
                else 0
            )

        return self._execute_scan(
            config,
            key,
            force_refresh=force_refresh,
            starting_generation=starting_generation,
        )

    async def _execute_scan(
        self,
        config: RadarConfiguration,
        key: ConfigurationKey,
        *,
        force_refresh: bool,
        starting_generation: int,
    ) -> dict[str, Any]:
        with self._state_lock:
            now = self.clock()

            if not force_refresh:
                cached = self._cached_payload_locked(
                    key,
                    now=now,
                )

                if cached is not None:
                    return cached

            else:
                current_entry = self._cache.get(key)

                generation_advanced = (
                    current_entry is not None
                    and current_entry[1]
                    > starting_generation
                )

                if generation_advanced:
                    cached = self._cached_payload_locked(
                        key,
                        now=now,
                    )

                    if cached is not None:
                        monitoring = dict(
                            cached.get("monitoring") or {}
                        )

                        monitoring.update({
                            "cache_hit": True,
                            "shared_scan": True,
                        })

                        cached["monitoring"] = monitoring
                        return cached

            future = self._inflight.get(key)
            owner = future is None

            if owner:
                future = Future()
                self._inflight[key] = future

        if not owner:
            shared = await asyncio.wrap_future(
                future
            )

            result = deepcopy(shared)
            monitoring = dict(
                result.get("monitoring") or {}
            )

            monitoring.update({
                "cache_hit": True,
                "shared_scan": True,
                "cache_age_seconds": 0.0,
                "cache_ttl_seconds": (
                    self.cache_ttl_seconds
                ),
            })

            result["monitoring"] = monitoring
            return result

        try:
            payload = await self.monitor.scan(config)
            completed_at = self.clock()

            result = deepcopy(payload)
            monitoring = dict(
                result.get("monitoring") or {}
            )

            monitoring.update({
                "cache_hit": False,
                "shared_scan": False,
                "cache_age_seconds": 0.0,
                "cache_ttl_seconds": (
                    self.cache_ttl_seconds
                ),
            })

            result["monitoring"] = monitoring

            with self._state_lock:
                self._cache_generation += 1
                generation = self._cache_generation
                stored = deepcopy(result)

                self._cache[key] = (
                    completed_at,
                    generation,
                    stored,
                )

                self._latest_entry = (
                    completed_at,
                    generation,
                    key,
                    stored,
                )

                self._inflight.pop(key, None)

                if not future.done():
                    future.set_result(
                        deepcopy(result)
                    )

            return result

        except BaseException as exc:
            with self._state_lock:
                self._inflight.pop(key, None)

                if not future.done():
                    future.set_exception(exc)

            raise

    def latest_snapshot(
        self,
        configuration: RadarConfiguration | None = None,
    ) -> dict[str, Any]:
        """
        Devolve o ultimo payload coletado sem coletar.

        O snapshot nunca e apresentado como valido de
        forma implicita: idade e configuracao de origem
        sao sempre explicitadas, e o status e rebaixado
        quando os dados estao velhos ou vieram de uma
        configuracao diferente da solicitada.
        """

        key = (
            self._configuration_key(configuration)
            if configuration is not None
            else None
        )

        now = self.clock()
        max_age_seconds = self._snapshot_max_age_seconds()

        with self._state_lock:
            entry = (
                self._cache.get(key)
                if key is not None
                else None
            )

            if entry is not None:
                created_at, _, payload = entry
                snapshot_key = key
            elif self._latest_entry is not None:
                (
                    created_at,
                    _,
                    snapshot_key,
                    payload,
                ) = self._latest_entry
            else:
                return self._warming_up_payload()

            result = deepcopy(payload)

        snapshot_age = max(
            0.0,
            now - created_at,
        )

        is_stale = snapshot_age > max_age_seconds

        configuration_match = (
            key is None
            or snapshot_key == key
        )

        monitoring = dict(
            result.get("monitoring") or {}
        )

        monitoring.update({
            "snapshot_available": True,
            "served_from_snapshot": True,
            "snapshot_age_seconds": round(
                snapshot_age,
                3,
            ),
            "snapshot_max_age_seconds": round(
                max_age_seconds,
                3,
            ),
            "snapshot_is_stale": is_stale,
            "snapshot_configuration_match": (
                configuration_match
            ),
            "snapshot_configuration": (
                self._describe_key(snapshot_key)
            ),
            "requested_configuration": (
                self._describe_key(key)
            ),
            "collected_status": result.get("status"),
            "cache_hit": True,
            "shared_scan": False,
        })

        result["monitoring"] = monitoring

        if is_stale:
            result["status"] = "STALE"
        elif not configuration_match:
            result["status"] = (
                "CONFIGURATION_MISMATCH"
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
        with self._state_lock:
            self._cache.clear()
            self._latest_entry = None


real_opportunity_scan_service = (
    RealOpportunityScanService()
)
