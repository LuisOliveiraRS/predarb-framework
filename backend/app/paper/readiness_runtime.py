from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.paper.readiness import (
    PaperReadinessGate,
)
from app.paper.readiness_history import (
    PaperReadinessHistory,
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return bool(default)

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


class PaperReadinessRuntime:
    """Avaliação periódica e controlada do Readiness Gate."""

    def __init__(
        self,
        *,
        gate_factory: Callable[
            [],
            PaperReadinessGate,
        ] = PaperReadinessGate,
        history_factory: Callable[
            [],
            PaperReadinessHistory,
        ] = PaperReadinessHistory,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
        minimum_interval_seconds: float = 30.0,
    ) -> None:
        self.gate_factory = gate_factory
        self.history_factory = (
            history_factory
        )

        self.enabled = (
            _env_bool(
                "PAPER_READINESS_RUNTIME_ENABLED",
                True,
            )
            if enabled is None
            else bool(enabled)
        )

        self.minimum_interval_seconds = max(
            0.01,
            float(
                minimum_interval_seconds
            ),
        )

        configured_interval = (
            _env_float(
                "PAPER_READINESS_RUNTIME_INTERVAL_SECONDS",
                300.0,
            )
            if interval_seconds is None
            else float(interval_seconds)
        )

        self.interval_seconds = (
            self._normalize_interval(
                configured_interval
            )
        )

        self._task: (
            asyncio.Task[None] | None
        ) = None

        self._stop_event: (
            asyncio.Event | None
        ) = None

        self._state_lock = asyncio.Lock()
        self._cycle_lock = asyncio.Lock()

        self.started_at: str | None = None
        self.stopped_at: str | None = None
        self.last_cycle_at: str | None = None
        self.last_success_at: str | None = None
        self.last_error_at: str | None = None
        self.last_error: str | None = None
        self.last_result: (
            dict[str, Any] | None
        ) = None

        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.ready_cycles = 0
        self.not_ready_cycles = 0
        self.insufficient_data_cycles = 0

    def _normalize_interval(
        self,
        value: float,
    ) -> float:
        return max(
            self.minimum_interval_seconds,
            min(
                float(value),
                86400.0,
            ),
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
            "last_cycle_at": (
                self.last_cycle_at
            ),
            "last_success_at": (
                self.last_success_at
            ),
            "last_error_at": (
                self.last_error_at
            ),
            "last_error": self.last_error,
            "total_cycles": self.total_cycles,
            "successful_cycles": (
                self.successful_cycles
            ),
            "failed_cycles": (
                self.failed_cycles
            ),
            "ready_cycles": (
                self.ready_cycles
            ),
            "not_ready_cycles": (
                self.not_ready_cycles
            ),
            "insufficient_data_cycles": (
                self.insufficient_data_cycles
            ),
            "last_result": (
                self.last_result
            ),
            "manual_start_required": True,
            "read_only_evaluation": True,
        }

        result.update(
            self._safe_flags()
        )

        return result

    def _capture_sync(
        self,
    ) -> dict[str, Any]:
        report = (
            self.gate_factory().evaluate()
        )

        if (
            report.get(
                "execution_authorized"
            )
            is not False
            or report.get(
                "live_execution"
            )
            is not False
            or report.get(
                "financial_execution"
            )
            is not False
            or report.get(
                "read_only"
            )
            is not True
        ):
            raise RuntimeError(
                "O Readiness Gate retornou "
                "guardas de segurança inválidas."
            )

        captured = (
            self.history_factory().capture(
                report
            )
        )

        if (
            captured.get(
                "execution_authorized"
            )
            is not False
            or captured.get(
                "live_execution"
            )
            is not False
            or captured.get(
                "financial_execution"
            )
            is not False
        ):
            raise RuntimeError(
                "O histórico retornou guardas "
                "de segurança inválidas."
            )

        return {
            "readiness": report,
            "history": captured,
        }

    def _register_readiness_status(
        self,
        readiness_status: str,
    ) -> None:
        normalized = str(
            readiness_status
        ).upper()

        if normalized == "READY":
            self.ready_cycles += 1

        elif normalized == "NOT_READY":
            self.not_ready_cycles += 1

        elif (
            normalized
            == "INSUFFICIENT_DATA"
        ):
            self.insufficient_data_cycles += 1

    async def capture_once(
        self,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime de readiness "
                "está desabilitado."
            )

        async with self._cycle_lock:
            started = time.perf_counter()
            captured_at = _utc_now()

            self.total_cycles += 1
            self.last_cycle_at = (
                captured_at
            )

            try:
                payload = (
                    await asyncio.to_thread(
                        self._capture_sync
                    )
                )

                elapsed_ms = round(
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000,
                    3,
                )

                readiness_status = str(
                    payload[
                        "readiness"
                    ].get("status")
                    or "UNKNOWN"
                ).upper()

                self._register_readiness_status(
                    readiness_status
                )

                result = {
                    "status": "SUCCESS",
                    "captured_at": (
                        captured_at
                    ),
                    "elapsed_ms": (
                        elapsed_ms
                    ),
                    "readiness_status": (
                        readiness_status
                    ),
                    "readiness_score": (
                        payload[
                            "readiness"
                        ].get(
                            "readiness_score"
                        )
                    ),
                    "history_entry_id": (
                        payload[
                            "history"
                        ]["entry"].get("id")
                    ),
                    "readiness": (
                        payload["readiness"]
                    ),
                    "history": (
                        payload["history"]
                    ),
                    **self._safe_flags(),
                }

                self.successful_cycles += 1
                self.last_success_at = (
                    captured_at
                )
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
                self.last_error_at = (
                    captured_at
                )
                self.last_error = str(exc)

                result = {
                    "status": "FAILED",
                    "captured_at": (
                        captured_at
                    ),
                    "elapsed_ms": (
                        elapsed_ms
                    ),
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
                        timeout=(
                            self.interval_seconds
                        ),
                    )
                    break

                except asyncio.TimeoutError:
                    try:
                        await self.capture_once()
                    except Exception:
                        continue

        except asyncio.CancelledError:
            raise

        finally:
            self.stopped_at = _utc_now()

    async def start(
        self,
        *,
        interval_seconds: (
            float | None
        ) = None,
        run_immediately: bool = True,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime de readiness "
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

            self._stop_event = (
                asyncio.Event()
            )
            self.started_at = _utc_now()
            self.stopped_at = None

            self._task = (
                asyncio.create_task(
                    self._run_loop(
                        run_immediately=(
                            run_immediately
                        )
                    ),
                    name=(
                        "predarb-paper-"
                        "readiness-runtime"
                    ),
                )
            )

            return self.status()

    async def stop(
        self,
    ) -> dict[str, Any]:
        async with self._state_lock:
            task = self._task
            stop_event = (
                self._stop_event
            )

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
                    self._stop_event = (
                        None
                    )

                self.stopped_at = (
                    _utc_now()
                )

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
        self.ready_cycles = 0
        self.not_ready_cycles = 0
        self.insufficient_data_cycles = 0

        return self.status()


paper_readiness_runtime = (
    PaperReadinessRuntime()
)
