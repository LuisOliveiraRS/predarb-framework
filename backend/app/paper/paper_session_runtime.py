from __future__ import annotations

import asyncio
from threading import RLock
from typing import Any

from app.core.settings import settings
from app.paper.paper_session import PaperSessionManager, paper_session_manager


class PaperSessionRuntime:
    """Loop Paper explícito. Nunca inicia automaticamente e nunca envia ordens live."""

    START_CONFIRMATION = "START-PAPER-SESSION"

    def __init__(
        self,
        *,
        manager: PaperSessionManager | None = None,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
    ) -> None:
        self._lock = RLock()
        self.manager = manager or paper_session_manager
        self.enabled = settings.PAPER_SESSION_ENABLED if enabled is None else bool(enabled)
        self.interval_seconds = float(
            settings.PAPER_SESSION_INTERVAL_SECONDS
            if interval_seconds is None
            else interval_seconds
        )
        if self.interval_seconds < 1:
            raise ValueError("PAPER_SESSION_INTERVAL_SECONDS deve ser pelo menos 1.")
        self.task: asyncio.Task | None = None
        self.running = False
        self.started_at: str | None = None
        self.last_report: dict[str, Any] = {}
        self._stop_event: asyncio.Event | None = None

    def startup(self) -> dict[str, Any]:
        loaded = False
        if self.enabled and settings.PAPER_SESSION_AUTO_LOAD_REPORT:
            loaded = self.manager.restore_report()
        self.last_report = {
            "operation": "STARTUP",
            "status": "CONFIGURED" if self.enabled else "DISABLED",
            "auto_start": False,
            "report_loaded": loaded,
            "execution_authorized": False,
            "live_execution": False,
        }
        return self.status()

    async def _loop(self) -> None:
        assert self._stop_event is not None
        try:
            while not self._stop_event.is_set():
                cycle = await asyncio.to_thread(self.manager.run_cycle)
                self.last_report = dict(cycle)
                if cycle.get("status") == "RISK_STOPPED":
                    break
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=self.interval_seconds
                    )
                except asyncio.TimeoutError:
                    pass
        finally:
            with self._lock:
                self.running = False
                self.task = None

    async def start(self, *, confirm: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("A sessão Paper automatizada está desabilitada.")
        if confirm != self.START_CONFIRMATION:
            raise ValueError("Confirmação inválida para iniciar a sessão Paper.")
        with self._lock:
            if self.running and self.task is not None:
                return self.status()
            self._stop_event = asyncio.Event()
            self.running = True
            self.task = asyncio.create_task(self._loop(), name="paper-session-runtime")
        return self.status()

    async def stop(self) -> dict[str, Any]:
        with self._lock:
            event = self._stop_event
            task = self.task
        if event is not None:
            event.set()
        if task is not None and task is not asyncio.current_task():
            try:
                await asyncio.wait_for(task, timeout=max(2.0, self.interval_seconds + 1.0))
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        with self._lock:
            self.running = False
            self.task = None
        return self.status()

    async def run_once(self) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("A sessão Paper automatizada está desabilitada.")
        cycle = await asyncio.to_thread(self.manager.run_cycle)
        self.last_report = dict(cycle)
        return cycle

    def status(self) -> dict[str, Any]:
        return {
            "status": "RUNNING" if self.running else "CONFIGURED" if self.enabled else "DISABLED",
            "enabled": self.enabled,
            "running": self.running,
            "auto_start": False,
            "auto_load_report": settings.PAPER_SESSION_AUTO_LOAD_REPORT,
            "interval_seconds": self.interval_seconds,
            "task_active": bool(self.task and not self.task.done()),
            "last_report": dict(self.last_report),
            "session": self.manager.report(),
            "execution_authorized": False,
            "live_execution": False,
        }


paper_session_runtime = PaperSessionRuntime()
