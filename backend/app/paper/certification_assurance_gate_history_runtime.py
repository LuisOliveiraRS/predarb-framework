from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.paper.certification_assurance_gate import (
    PaperAssuranceQualificationGate,
)
from app.paper.certification_assurance_gate_history import (
    PaperAssuranceQualificationHistory,
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


class PaperAssuranceGateHistoryRuntime:
    """Runtime manual para persistir avaliações do gate de qualificação."""

    def __init__(
        self,
        *,
        gate_factory: Callable[
            [],
            PaperAssuranceQualificationGate,
        ] = PaperAssuranceQualificationGate,
        history_factory: Callable[
            [],
            PaperAssuranceQualificationHistory,
        ] = PaperAssuranceQualificationHistory,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
        minimum_interval_seconds: float = 30.0,
    ) -> None:
        self.gate_factory = gate_factory
        self.history_factory = history_factory

        self.enabled = (
            _env_bool(
                "PAPER_ASSURANCE_GATE_HISTORY_RUNTIME_ENABLED",
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
                "PAPER_ASSURANCE_GATE_HISTORY_RUNTIME_INTERVAL_SECONDS",
                300.0,
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

        self.qualified_cycles = 0
        self.not_qualified_cycles = 0
        self.insufficient_data_cycles = 0
        self.unknown_cycles = 0

    def _normalize_interval(
        self,
        value: float,
    ) -> float:
        return max(
            self.minimum_interval_seconds,
            min(float(value), 86400.0),
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
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
        }

    def status(self) -> dict[str, Any]:
        payload = {
            "status": (
                "RUNNING"
                if self.running
                else "STOPPED"
            ),
            "enabled": self.enabled,
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_cycle_at": self.last_cycle_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
            "last_result": self.last_result,
            "total_cycles": self.total_cycles,
            "successful_cycles": self.successful_cycles,
            "failed_cycles": self.failed_cycles,
            "qualified_cycles": self.qualified_cycles,
            "not_qualified_cycles": self.not_qualified_cycles,
            "insufficient_data_cycles": self.insufficient_data_cycles,
            "unknown_cycles": self.unknown_cycles,
            "manual_start_required": True,
            "read_only_monitoring": True,
        }

        payload.update(self._safe_flags())
        return payload

    @staticmethod
    def _validate_safe_payload(
        name: str,
        payload: dict[str, Any],
    ) -> None:
        required_false = (
            "paper_execution_authorized",
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
        )

        for field in required_false:
            if payload.get(field) is not False:
                raise RuntimeError(
                    f"{name}: {field} não está explicitamente bloqueado."
                )

        if payload.get("read_only") is not True:
            raise RuntimeError(
                f"{name}: payload não está marcado como somente leitura."
            )

    def _capture_sync(self) -> dict[str, Any]:
        report = self.gate_factory().evaluate()

        self._validate_safe_payload(
            "gate",
            report,
        )

        captured = self.history_factory().capture(
            report
        )

        self._validate_safe_payload(
            "history",
            captured,
        )

        return {
            "gate": report,
            "history": captured,
        }

    def _count_status(
        self,
        status: str,
    ) -> None:
        normalized = str(
            status or "UNKNOWN"
        ).upper()

        if normalized == "QUALIFIED":
            self.qualified_cycles += 1

        elif normalized == "NOT_QUALIFIED":
            self.not_qualified_cycles += 1

        elif normalized == "INSUFFICIENT_DATA":
            self.insufficient_data_cycles += 1

        else:
            self.unknown_cycles += 1

    async def capture_once(self) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime do histórico do gate está desabilitado."
            )

        async with self._cycle_lock:
            started = time.perf_counter()
            captured_at = _utc_now()

            self.total_cycles += 1
            self.last_cycle_at = captured_at

            try:
                payload = await asyncio.to_thread(
                    self._capture_sync
                )

                report = payload["gate"]
                history = payload["history"]

                gate_status = str(
                    report.get("status")
                    or "UNKNOWN"
                ).upper()

                self._count_status(
                    gate_status
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
                    "gate_status": gate_status,
                    "qualified": (
                        report.get("qualified")
                        is True
                    ),
                    "qualification_score": (
                        report.get(
                            "qualification_score"
                        )
                    ),
                    "history_entry_id": (
                        (
                            history.get("entry")
                            or {}
                        ).get("id")
                    ),
                    "history_total_entries": (
                        (
                            history.get("summary")
                            or {}
                        ).get("total_entries")
                    ),
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
                "O runtime do histórico do gate está desabilitado."
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
                    "predarb-paper-assurance-"
                    "gate-history-runtime"
                ),
            )

            return self.status()

    async def stop(self) -> dict[str, Any]:
        async with self._state_lock:
            task = self._task
            stop_event = self._stop_event

            if task is None or task.done():
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
                "Pare o runtime antes de resetar as estatísticas."
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

        self.qualified_cycles = 0
        self.not_qualified_cycles = 0
        self.insufficient_data_cycles = 0
        self.unknown_cycles = 0

        return self.status()


paper_assurance_gate_history_runtime = (
    PaperAssuranceGateHistoryRuntime()
)
