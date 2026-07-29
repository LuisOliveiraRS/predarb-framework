from __future__ import annotations

import asyncio
from threading import RLock
from typing import Any

from app.dashboard.router_publisher import RouterPublisher, router_publisher
from app.dashboard.services.dashboard_updater import DashboardUpdater, dashboard_updater


class RouterStream:
    """Gerencia clientes WebSocket e transmite snapshots do AI Router."""

    def __init__(
        self,
        *,
        publisher: RouterPublisher | None = None,
        updater: DashboardUpdater | None = None,
        interval: float = 1.0,
    ) -> None:
        if interval <= 0:
            raise ValueError("interval deve ser maior que zero.")

        self.publisher = publisher or router_publisher
        self.updater = updater or dashboard_updater
        self.interval = float(interval)
        self._clients: set[Any] = set()
        self._lock = RLock()
        self._stop_event = asyncio.Event()
        self._running = False
        self.last_report: dict[str, Any] = {}

    @property
    def clients(self) -> list[Any]:
        with self._lock:
            return list(self._clients)

    @property
    def running(self) -> bool:
        return self._running

    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def _update_connections(self) -> int:
        count = self.client_count()
        try:
            self.updater.connection(count)
        except Exception:
            pass
        return count

    async def register(
        self,
        websocket: Any,
        *,
        accept: bool = True,
        send_initial: bool = True,
    ) -> int:
        if websocket is None:
            raise ValueError("websocket não pode ser None.")

        if accept:
            accept_method = getattr(websocket, "accept", None)
            if callable(accept_method):
                await accept_method()

        with self._lock:
            self._clients.add(websocket)

        count = self._update_connections()

        if send_initial:
            try:
                await websocket.send_json(
                    self.publisher.publish(refresh=True)
                )
            except Exception:
                await self.unregister(websocket)
                raise

        self.last_report = {
            "event": "REGISTER",
            "clients": count,
            "running": self.running,
        }
        return count

    async def unregister(self, websocket: Any) -> int:
        with self._lock:
            self._clients.discard(websocket)

        count = self._update_connections()
        self.last_report = {
            "event": "UNREGISTER",
            "clients": count,
            "running": self.running,
        }
        return count

    async def broadcast(
        self,
        snapshot: dict[str, Any] | None = None,
    ) -> int:
        clients = self.clients
        if not clients:
            self.last_report = {
                "event": "BROADCAST",
                "clients": 0,
                "sent": 0,
                "disconnected": 0,
                "running": self.running,
            }
            return 0

        payload = snapshot or self.publisher.publish(refresh=True)
        disconnected: list[Any] = []
        sent = 0

        for websocket in clients:
            try:
                await websocket.send_json(payload)
                sent += 1
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            await self.unregister(websocket)

        self.last_report = {
            "event": "BROADCAST",
            "clients": self.client_count(),
            "sent": sent,
            "disconnected": len(disconnected),
            "running": self.running,
            "updated_at": payload.get("updated_at"),
        }
        return sent

    async def run(self, *, interval: float | None = None) -> None:
        resolved_interval = self.interval if interval is None else float(interval)
        if resolved_interval <= 0:
            raise ValueError("interval deve ser maior que zero.")

        self._stop_event.clear()
        self._running = True

        try:
            while not self._stop_event.is_set():
                await self.broadcast()

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=resolved_interval,
                    )
                except TimeoutError:
                    continue
        finally:
            self._running = False
            self.last_report = {
                **self.last_report,
                "event": "STOPPED",
                "running": False,
                "clients": self.client_count(),
            }

    def request_stop(self) -> None:
        self._stop_event.set()

    async def close_clients(self, *, code: int = 1001) -> int:
        clients = self.clients
        closed = 0

        for websocket in clients:
            close_method = getattr(websocket, "close", None)
            if callable(close_method):
                try:
                    await close_method(code=code)
                    closed += 1
                except Exception:
                    pass
            await self.unregister(websocket)

        return closed

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "clients": self.client_count(),
            "interval": self.interval,
            "last_report": dict(self.last_report),
        }


router_stream = RouterStream()
