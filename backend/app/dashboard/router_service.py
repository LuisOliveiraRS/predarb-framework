from __future__ import annotations

import asyncio
from typing import Any

from app.dashboard.router_stream import RouterStream, router_stream


class RouterService:
    """Controla o ciclo de vida do stream do AI Router Dashboard."""

    def __init__(
        self,
        *,
        stream: RouterStream | None = None,
        interval: float = 1.0,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval deve ser maior que zero.")

        self.stream = stream or router_stream
        self.interval = float(interval)
        self.task: asyncio.Task[Any] | None = None
        self.last_report: dict[str, Any] = {}

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    async def start(self) -> asyncio.Task[Any]:
        if self.running:
            return self.task  # type: ignore[return-value]

        self.task = asyncio.create_task(
            self.stream.run(interval=self.interval),
            name="predarb-router-dashboard-stream",
        )
        await asyncio.sleep(0)

        self.last_report = {
            "status": "RUNNING",
            "interval": self.interval,
            "task_name": self.task.get_name(),
        }
        return self.task

    async def stop(
        self,
        *,
        timeout: float = 2.0,
        close_clients: bool = False,
    ) -> None:
        task = self.task
        if task is None:
            self.stream.request_stop()
            self.last_report = {
                "status": "STOPPED",
                "already_stopped": True,
            }
            return

        self.stream.request_stop()

        try:
            await asyncio.wait_for(task, timeout=max(0.0, float(timeout)))
        except TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        except asyncio.CancelledError:
            pass
        finally:
            self.task = None

        closed = 0
        if close_clients:
            closed = await self.stream.close_clients()

        self.last_report = {
            "status": "STOPPED",
            "closed_clients": closed,
            "stream": self.stream.status(),
        }

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "interval": self.interval,
            "task": self.task.get_name() if self.running and self.task else None,
            "stream": self.stream.status(),
            "last_report": dict(self.last_report),
        }


router_service = RouterService()
