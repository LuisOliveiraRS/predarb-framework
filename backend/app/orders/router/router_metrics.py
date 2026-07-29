from __future__ import annotations

from threading import RLock
from typing import Any

from app.orders.router.execution_route import ExecutionRoute


class RouterMetrics:
    def __init__(self) -> None:
        self.routes_used = 0
        self.total_latency = 0.0
        self.total_fee = 0.0
        self.total_score = 0.0
        self._by_exchange: dict[str, int] = {}
        self._lock = RLock()

    def register(self, route: Any) -> ExecutionRoute:
        resolved = ExecutionRoute.from_value(route)
        with self._lock:
            self.routes_used += 1
            self.total_latency += resolved.latency
            self.total_fee += resolved.fee
            self.total_score += resolved.score
            self._by_exchange[resolved.exchange] = (
                self._by_exchange.get(resolved.exchange, 0) + 1
            )
        return resolved

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "routes_used": self.routes_used,
                "total_latency": round(self.total_latency, 8),
                "total_fee": round(self.total_fee, 8),
                "total_score": round(self.total_score, 8),
                "by_exchange": dict(self._by_exchange),
            }

    def clear(self) -> None:
        with self._lock:
            self.routes_used = 0
            self.total_latency = 0.0
            self.total_fee = 0.0
            self.total_score = 0.0
            self._by_exchange.clear()

    reset = clear


router_metrics = RouterMetrics()
