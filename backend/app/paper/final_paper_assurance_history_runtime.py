from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.paper.final_paper_operational_assurance import (
    final_paper_operational_assurance,
)
from app.paper.final_paper_operational_assurance_history import (
    FinalPaperOperationalAssuranceHistory,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


class FinalPaperAssuranceHistoryRuntime:
    """Runtime manual para capturar a Garantia Operacional Final Paper."""

    def __init__(
        self,
        *,
        assurance_provider: Any = final_paper_operational_assurance,
        history_factory: Callable[
            [],
            FinalPaperOperationalAssuranceHistory,
        ] = FinalPaperOperationalAssuranceHistory,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
        minimum_interval_seconds: float = 30.0,
    ) -> None:
        self.assurance_provider = assurance_provider
        self.history_factory = history_factory

        self.enabled = (
            _env_bool(
                "PAPER_FINAL_ASSURANCE_HISTORY_RUNTIME_ENABLED",
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
                "PAPER_FINAL_ASSURANCE_HISTORY_RUNTIME_INTERVAL_SECONDS",
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

        self.assured_cycles = 0
        self.warning_cycles = 0
        self.blocked_cycles = 0
        self.no_data_cycles = 0
        self.unknown_cycles = 0

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
    def running(
        self,
    ) -> bool:
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
            "next_step_authorized": False,
        }

    @classmethod
    def _validate_safe_payload(
        cls,
        name: str,
        payload: dict[str, Any],
        *,
        require_read_only: bool = True,
    ) -> None:
        for field in cls._safe_flags():
            if payload.get(field) is not False:
                raise RuntimeError(
                    f"{name}: {field} não está explicitamente bloqueado."
                )

        if (
            require_read_only
            and payload.get("read_only") is not True
        ):
            raise RuntimeError(
                f"{name}: payload não está marcado como somente leitura."
            )

    def status(
        self,
    ) -> dict[str, Any]:
        return {
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
            "assured_cycles": self.assured_cycles,
            "warning_cycles": self.warning_cycles,
            "blocked_cycles": self.blocked_cycles,
            "no_data_cycles": self.no_data_cycles,
            "unknown_cycles": self.unknown_cycles,
            "manual_start_required": True,
            "read_only_monitoring": True,
            **self._safe_flags(),
        }

    def _capture_sync(
        self,
    ) -> dict[str, Any]:
        report = (
            self.assurance_provider
            .evaluate()
        )

        if not isinstance(
            report,
            dict,
        ):
            raise RuntimeError(
                "A Garantia Operacional Final não retornou um objeto."
            )

        self._validate_safe_payload(
            "final_paper_assurance",
            report,
        )

        if (
            report.get("scope")
            != "PAPER_ASSURANCE_ONLY"
        ):
            raise RuntimeError(
                "Escopo da garantia final inválido."
            )

        captured = (
            self.history_factory()
            .capture(report)
        )

        if not isinstance(
            captured,
            dict,
        ):
            raise RuntimeError(
                "O histórico da garantia final não retornou um objeto."
            )

        self._validate_safe_payload(
            "final_paper_assurance_history",
            captured,
        )

        return {
            "report": report,
            "captured": captured,
        }

    def _count_status(
        self,
        status: str,
    ) -> None:
        normalized = str(
            status or "UNKNOWN"
        ).upper()

        if normalized == "ASSURED":
            self.assured_cycles += 1

        elif normalized == "WARNING":
            self.warning_cycles += 1

        elif normalized == "BLOCKED":
            self.blocked_cycles += 1

        elif normalized == "NO_DATA":
            self.no_data_cycles += 1

        else:
            self.unknown_cycles += 1

    async def capture_once(
        self,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime do histórico da garantia final está desabilitado."
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

                report = payload["report"]
                captured = payload["captured"]

                assurance_status = str(
                    report.get("status")
                    or "UNKNOWN"
                ).upper()

                self._count_status(
                    assurance_status
                )

                entry = (
                    captured.get("entry")
                    or {}
                )

                summary = (
                    captured.get("summary")
                    or {}
                )

                result = {
                    "status": "SUCCESS",
                    "captured_at": captured_at,
                    "elapsed_ms": round(
                        (
                            time.perf_counter()
                            - started
                        )
                        * 1000,
                        3,
                    ),
                    "assurance_status": assurance_status,
                    "assurance_score": report.get(
                        "assurance_score"
                    ),
                    "entry_id": entry.get("id"),
                    "history_entries": summary.get(
                        "total_entries"
                    ),
                    "active_incidents": (
                        (
                            report.get("summary")
                            or {}
                        ).get("active_incidents")
                    ),
                    "active_critical_incidents": (
                        (
                            report.get("summary")
                            or {}
                        ).get(
                            "active_critical_incidents"
                        )
                    ),
                    "total_runtime_failures": (
                        (
                            report.get("summary")
                            or {}
                        ).get(
                            "total_runtime_failures"
                        )
                    ),
                    **self._safe_flags(),
                }

                self.successful_cycles += 1
                self.last_success_at = captured_at
                self.last_error = None
                self.last_result = result

                return result

            except Exception as exc:
                self.failed_cycles += 1
                self.last_error_at = captured_at
                self.last_error = str(exc)

                self.last_result = {
                    "status": "FAILED",
                    "captured_at": captured_at,
                    "elapsed_ms": round(
                        (
                            time.perf_counter()
                            - started
                        )
                        * 1000,
                        3,
                    ),
                    "error": str(exc),
                    **self._safe_flags(),
                }

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
                "O runtime do histórico da garantia final está desabilitado."
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
                    "predarb-final-paper-"
                    "assurance-history-runtime"
                ),
            )

            return self.status()

    async def stop(
        self,
    ) -> dict[str, Any]:
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

        self.assured_cycles = 0
        self.warning_cycles = 0
        self.blocked_cycles = 0
        self.no_data_cycles = 0
        self.unknown_cycles = 0

        return self.status()


final_paper_assurance_history_runtime = (
    FinalPaperAssuranceHistoryRuntime()
)
