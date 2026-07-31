from __future__ import annotations

import asyncio
from datetime import datetime
from datetime import timezone
from threading import Lock
from threading import RLock
from typing import Any

from app.core.settings import settings
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)
from app.real_markets.opportunity_scan_service import (
    real_opportunity_scan_service,
)


class RealOpportunityBackgroundCollector:
    """Executa coletas periodicas somente leitura."""

    def __init__(
        self,
        *,
        scan_service: Any = (
            real_opportunity_scan_service
        ),
        enabled: bool | None = None,
    ) -> None:
        self.scan_service = scan_service
        self.enabled = (
            settings
            .REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED
            if enabled is None
            else bool(enabled)
        )

        self._cycle_lock = Lock()
        self._state_lock = RLock()

        self._state: dict[str, Any] = {
            "cycles": 0,
            "successes": 0,
            "failures": 0,
            "skipped": 0,
            "last_started_at": None,
            "last_completed_at": None,
            "last_error": None,
            "last_status": "IDLE",
            "last_markets_priced": 0,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(
            timezone.utc
        ).isoformat()

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

    @staticmethod
    def configuration() -> RadarConfiguration:
        return RadarConfiguration(
            limit_per_connector=(
                settings
                .REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR
            ),
            fee_buffer=(
                settings
                .REAL_OPPORTUNITY_BACKGROUND_FEE_BUFFER
            ),
            near_threshold=(
                settings
                .REAL_OPPORTUNITY_BACKGROUND_NEAR_THRESHOLD
            ),
            concurrency=(
                settings
                .REAL_OPPORTUNITY_BACKGROUND_CONCURRENCY
            ),
        )

    async def run_cycle(
        self,
    ) -> dict[str, Any]:
        if not self.enabled:
            return {
                "status": "DISABLED",
                **self.status(),
                **self._safety_flags(),
            }

        if not self._cycle_lock.acquire(
            blocking=False
        ):
            with self._state_lock:
                self._state["skipped"] += 1

            return {
                "status": "SKIPPED",
                "reason": "CYCLE_ALREADY_RUNNING",
                **self.status(),
                **self._safety_flags(),
            }

        started_at = self._now()

        with self._state_lock:
            self._state["cycles"] += 1
            self._state["last_started_at"] = (
                started_at
            )
            self._state["last_status"] = "RUNNING"
            self._state["last_error"] = None

        try:
            payload = await self.scan_service.scan(
                self.configuration(),
                force_refresh=True,
            )

            with self._state_lock:
                self._state["successes"] += 1
                self._state["last_status"] = (
                    payload.get("status")
                    or "READY"
                )
                self._state[
                    "last_markets_priced"
                ] = int(
                    payload.get(
                        "markets_priced",
                        0,
                    )
                    or 0
                )

            return {
                "status": "READY",
                "snapshot": payload,
                **self.status(),
                **self._safety_flags(),
            }

        except Exception as exc:
            with self._state_lock:
                self._state["failures"] += 1
                self._state["last_status"] = (
                    "DEGRADED"
                )
                self._state["last_error"] = (
                    type(exc).__name__
                )

            return {
                "status": "DEGRADED",
                "error": type(exc).__name__,
                **self.status(),
                **self._safety_flags(),
            }

        finally:
            with self._state_lock:
                self._state[
                    "last_completed_at"
                ] = self._now()

            self._cycle_lock.release()

    def run_task(
        self,
    ) -> dict[str, Any]:
        return asyncio.run(
            self.run_cycle()
        )

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            state = dict(self._state)

        return {
            "enabled": self.enabled,
            "interval_seconds": (
                settings
                .REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS
            ),
            **state,
            **self._safety_flags(),
        }


real_opportunity_background_collector = (
    RealOpportunityBackgroundCollector()
)
