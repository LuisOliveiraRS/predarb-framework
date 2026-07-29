from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.paper.performance_incidents import (
    PaperIncidentJournal,
)
from app.paper.performance_monitor import (
    PaperPerformanceMonitor,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "sim",
    }


def _env_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return float(default)

    try:
        return float(value)
    except ValueError:
        return float(default)


class PaperIncidentRuntime:
    """Captura periódica e controlada do monitor Paper."""

    def __init__(
        self,
        *,
        monitor_factory: Callable[
            [],
            PaperPerformanceMonitor,
        ] = PaperPerformanceMonitor,
        journal_factory: Callable[
            [],
            PaperIncidentJournal,
        ] = PaperIncidentJournal,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
        minimum_interval_seconds: float = 5.0,
    ) -> None:
        self.monitor_factory = monitor_factory
        self.journal_factory = journal_factory

        self.enabled = (
            _env_bool(
                "PAPER_INCIDENT_RUNTIME_ENABLED",
                True,
            )
            if enabled is None
            else bool(enabled)
        )

        self.minimum_interval_seconds = max(
            0.01,
            float(minimum_interval_seconds),
        )

        configured_interval = (
            _env_float(
                "PAPER_INCIDENT_RUNTIME_INTERVAL_SECONDS",
                60.0,
            )
            if interval_seconds is None
            else float(interval_seconds)
        )

        self.interval_seconds = self._normalize_interval(
            configured_interval
        )

        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._state_lock = asyncio.Lock()
        self._cycle_lock = asyncio.Lock()

        self.started_at: str | None = None
        self.stopped_at: str | None = None
        self.last_cycle_at: str | None = None
        self.last_success_at: str | None = None
        self.last_error_at: str | None = None
        self.last_error: str | None = None
        self.last_result: dict[str, Any] | None = None

        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0

    def _normalize_interval(
        self,
        value: float,
    ) -> float:
        return max(
            self.minimum_interval_seconds,
            min(float(value), 3600.0),
        )

    @property
    def running(self) -> bool:
        return (
            self._task is not None
            and not self._task.done()
        )

    @staticmethod
    def _safe_flags() -> dict[str, bool]:
        return {
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
        }

    def status(self) -> dict[str, Any]:
        result = {
            "status": (
                "RUNNING"
                if self.running
                else "STOPPED"
            ),
            "enabled": self.enabled,
            "running": self.running,
            "interval_seconds": (
                self.interval_seconds
            ),
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_cycle_at": self.last_cycle_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
            "total_cycles": self.total_cycles,
            "successful_cycles": (
                self.successful_cycles
            ),
            "failed_cycles": self.failed_cycles,
            "last_result": self.last_result,
            "manual_start_required": True,
            "read_only_monitoring": True,
        }

        result.update(
            self._safe_flags()
        )

        return result

    def _capture_sync(
        self,
    ) -> dict[str, Any]:
        snapshot = (
            self.monitor_factory().snapshot()
        )

        if (
            snapshot.get(
                "execution_authorized"
            )
            is not False
            or snapshot.get("live_execution")
            is not False
            or snapshot.get("read_only")
            is not True
        ):
            raise RuntimeError(
                "O monitor retornou guardas "
                "de segurança inválidas."
            )

        result = self.journal_factory().capture(
            snapshot
        )

        if (
            result.get("execution_authorized")
            is not False
            or result.get("live_execution")
            is not False
        ):
            raise RuntimeError(
                "O journal retornou guardas "
                "de segurança inválidas."
            )

        return result

    async def capture_once(
        self,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime de incidentes "
                "está desabilitado."
            )

        async with self._cycle_lock:
            started = time.perf_counter()
            captured_at = _utc_now()

            self.total_cycles += 1
            self.last_cycle_at = captured_at

            try:
                journal_result = await asyncio.to_thread(
                    self._capture_sync
                )

                elapsed_ms = round(
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000,
                    3,
                )

                result = {
                    "status": "SUCCESS",
                    "captured_at": captured_at,
                    "elapsed_ms": elapsed_ms,
                    "journal": journal_result,
                    **self._safe_flags(),
                }

                self.successful_cycles += 1
                self.last_success_at = captured_at
                self.last_error = None
                self.last_result = result

                return result

            except Exception as exc:
                elapsed_ms = round(
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000,
                    3,
                )

                self.failed_cycles += 1
                self.last_error_at = captured_at
                self.last_error = str(exc)

                result = {
                    "status": "FAILED",
                    "captured_at": captured_at,
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                    **self._safe_flags(),
                }

                self.last_result = result
                raise

    async def _run_loop(
        self,
        *,
        run_immediately: bool,
    ) -> None:
        stop_event = self._stop_event

        if stop_event is None:
            return

        try:
            if run_immediately:
                try:
                    await self.capture_once()
                except Exception:
                    pass

            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self.interval_seconds,
                    )
                    break

                except asyncio.TimeoutError:
                    try:
                        await self.capture_once()
                    except Exception:
                        # A falha é registrada no status;
                        # o runtime continua operando.
                        continue

        except asyncio.CancelledError:
            raise

        finally:
            self.stopped_at = _utc_now()

    async def start(
        self,
        *,
        interval_seconds: float | None = None,
        run_immediately: bool = True,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime de incidentes "
                "está desabilitado."
            )

        async with self._state_lock:
            if self.running:
                return self.status()

            if interval_seconds is not None:
                self.interval_seconds = (
                    self._normalize_interval(
                        interval_seconds
                    )
                )

            self._stop_event = asyncio.Event()
            self.started_at = _utc_now()
            self.stopped_at = None

            self._task = asyncio.create_task(
                self._run_loop(
                    run_immediately=run_immediately
                ),
                name=(
                    "predarb-paper-incident-runtime"
                ),
            )

            return self.status()

    async def stop(
        self,
    ) -> dict[str, Any]:
        async with self._state_lock:
            task = self._task
            stop_event = self._stop_event

            if (
                task is None
                or task.done()
            ):
                self._task = None
                self._stop_event = None
                self.stopped_at = (
                    self.stopped_at
                    or _utc_now()
                )
                return self.status()

            if stop_event is not None:
                stop_event.set()

        try:
            await asyncio.wait_for(
                task,
                timeout=30.0,
            )

        except asyncio.TimeoutError:
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        finally:
            async with self._state_lock:
                if self._task is task:
                    self._task = None
                    self._stop_event = None

                self.stopped_at = _utc_now()

        return self.status()

    async def reset_statistics(
        self,
    ) -> dict[str, Any]:
        if self.running:
            raise RuntimeError(
                "Pare o runtime antes de "
                "resetar as estatísticas."
            )

        self.started_at = None
        self.stopped_at = None
        self.last_cycle_at = None
        self.last_success_at = None
        self.last_error_at = None
        self.last_error = None
        self.last_result = None
        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0

        return self.status()


paper_incident_runtime = PaperIncidentRuntime()
