from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.paper.final_paper_validation_evidence_incidents import (
    FinalPaperEvidenceIncidentJournal,
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


class FinalPaperEvidenceIncidentRuntime:
    """Runtime manual para atualizar o diário de incidentes finais."""

    def __init__(
        self,
        *,
        journal_factory: Callable[
            [],
            FinalPaperEvidenceIncidentJournal,
        ] = FinalPaperEvidenceIncidentJournal,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
        minimum_interval_seconds: float = 30.0,
    ) -> None:
        self.journal_factory = journal_factory

        self.enabled = (
            _env_bool(
                "PAPER_FINAL_EVIDENCE_INCIDENT_RUNTIME_ENABLED",
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
                "PAPER_FINAL_EVIDENCE_INCIDENT_RUNTIME_INTERVAL_SECONDS",
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

        self.created_incidents = 0
        self.updated_incidents = 0
        self.reactivated_incidents = 0
        self.resolved_incidents = 0

        self.healthy_cycles = 0
        self.warning_cycles = 0
        self.critical_cycles = 0
        self.no_data_cycles = 0
        self.unknown_monitor_cycles = 0

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
    ) -> None:
        for field in cls._safe_flags():
            if payload.get(field) is not False:
                raise RuntimeError(
                    f"{name}: {field} não está explicitamente bloqueado."
                )

        if payload.get("read_only") is not True:
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
            "created_incidents": self.created_incidents,
            "updated_incidents": self.updated_incidents,
            "reactivated_incidents": self.reactivated_incidents,
            "resolved_incidents": self.resolved_incidents,
            "healthy_cycles": self.healthy_cycles,
            "warning_cycles": self.warning_cycles,
            "critical_cycles": self.critical_cycles,
            "no_data_cycles": self.no_data_cycles,
            "unknown_monitor_cycles": self.unknown_monitor_cycles,
            "manual_start_required": True,
            "read_only_monitoring": True,
            **self._safe_flags(),
        }

    def _capture_sync(
        self,
    ) -> dict[str, Any]:
        payload = (
            self.journal_factory()
            .capture()
        )

        self._validate_safe_payload(
            "final_evidence_incident_journal",
            payload,
        )

        monitor = payload.get("monitor")

        if not isinstance(
            monitor,
            dict,
        ):
            raise RuntimeError(
                "Resposta do diário sem snapshot do monitor."
            )

        self._validate_safe_payload(
            "final_evidence_monitor",
            monitor,
        )

        return payload

    def _count_monitor_status(
        self,
        status: str,
    ) -> None:
        normalized = str(
            status or "UNKNOWN"
        ).upper()

        if normalized == "HEALTHY":
            self.healthy_cycles += 1

        elif normalized == "WARNING":
            self.warning_cycles += 1

        elif normalized == "CRITICAL":
            self.critical_cycles += 1

        elif normalized == "NO_DATA":
            self.no_data_cycles += 1

        else:
            self.unknown_monitor_cycles += 1

    async def capture_once(
        self,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime de incidentes das evidências finais está desabilitado."
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

                monitor = payload.get("monitor") or {}
                monitor_status = str(
                    monitor.get("status")
                    or "UNKNOWN"
                ).upper()

                created = payload.get("created") or []
                updated = payload.get("updated") or []
                reactivated = payload.get("reactivated") or []
                resolved = payload.get("resolved") or []

                self.created_incidents += len(created)
                self.updated_incidents += len(updated)
                self.reactivated_incidents += len(
                    reactivated
                )
                self.resolved_incidents += len(resolved)

                self._count_monitor_status(
                    monitor_status
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
                    "monitor_status": monitor_status,
                    "monitor_score": monitor.get("score"),
                    "created_count": len(created),
                    "updated_count": len(updated),
                    "reactivated_count": len(
                        reactivated
                    ),
                    "resolved_count": len(resolved),
                    "active_incidents": (
                        (
                            payload.get("summary")
                            or {}
                        ).get("active_incidents")
                    ),
                    "critical_incidents": (
                        (
                            payload.get("summary")
                            or {}
                        ).get("active_critical")
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
                "O runtime de incidentes das evidências finais está desabilitado."
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
                    "predarb-final-evidence-"
                    "incident-runtime"
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

        self.created_incidents = 0
        self.updated_incidents = 0
        self.reactivated_incidents = 0
        self.resolved_incidents = 0

        self.healthy_cycles = 0
        self.warning_cycles = 0
        self.critical_cycles = 0
        self.no_data_cycles = 0
        self.unknown_monitor_cycles = 0

        return self.status()


final_paper_evidence_incident_runtime = (
    FinalPaperEvidenceIncidentRuntime()
)
