from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from math import isfinite
from threading import RLock
from typing import Any


class ExecutionMetrics:
    """Métricas thread-safe da camada Trading, sem alterar ordens."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.clear()

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    def _register(
        self,
        *,
        success: bool,
        status: str,
        latency_ms: Any = None,
        slippage_rate: Any = None,
        retries: Any = 0,
        rolled_back: bool = False,
    ) -> dict[str, Any]:
        latency = self._number(latency_ms)
        slippage = self._number(slippage_rate)
        retry_count = self._number(retries) or 0.0

        with self._lock:
            self.executions += 1
            if success:
                self.success += 1
            else:
                self.failed += 1
            if rolled_back:
                self.rollback += 1
            self.retries += max(0, int(retry_count))
            self.statuses[str(status or "UNKNOWN").strip().upper()] += 1
            if latency is not None and latency >= 0:
                self._latencies_ms.append(latency)
            if slippage is not None:
                self._slippage_rates.append(slippage)

        return self.stats()

    def register_success(
        self,
        *,
        latency_ms: Any = None,
        slippage_rate: Any = None,
        retries: Any = 0,
        rolled_back: bool = False,
        status: str = "SUCCESS",
    ) -> dict[str, Any]:
        return self._register(
            success=True,
            status=status,
            latency_ms=latency_ms,
            slippage_rate=slippage_rate,
            retries=retries,
            rolled_back=rolled_back,
        )

    def register_failure(
        self,
        *,
        latency_ms: Any = None,
        slippage_rate: Any = None,
        retries: Any = 0,
        rolled_back: bool = False,
        status: str = "FAILED",
    ) -> dict[str, Any]:
        return self._register(
            success=False,
            status=status,
            latency_ms=latency_ms,
            slippage_rate=slippage_rate,
            retries=retries,
            rolled_back=rolled_back,
        )

    def register_rollback(self) -> dict[str, Any]:
        with self._lock:
            self.rollback += 1
        return self.stats()

    def record(self, value: Any) -> dict[str, Any]:
        context = self._read(value, "context", None)
        success = bool(self._read(value, "success", False))
        status = str(self._read(value, "status", "SUCCESS" if success else "FAILED"))

        latency_ms = self._read(value, "latency_ms", None)
        if latency_ms is None and context is not None:
            latency_ms = self._read(context, "duration_ms", None)

        slippage_rate = self._read(value, "slippage_rate", None)
        if slippage_rate is None:
            metadata = self._read(value, "metadata", {})
            if isinstance(metadata, Mapping):
                slippage = metadata.get("slippage", {})
                if isinstance(slippage, Mapping):
                    slippage_rate = slippage.get("adverse_rate", slippage.get("signed_rate"))

        retries = self._read(value, "retries", None)
        if retries is None and context is not None:
            retries = self._read(context, "retries", 0)

        rolled_back = bool(
            self._read(value, "rollback", False)
            or (context is not None and self._read(context, "rollback", False))
        )

        return self._register(
            success=success,
            status=status,
            latency_ms=latency_ms,
            slippage_rate=slippage_rate,
            retries=retries,
            rolled_back=rolled_back,
        )

    update = record

    def clear(self) -> None:
        with getattr(self, "_lock", RLock()):
            self.executions = 0
            self.success = 0
            self.failed = 0
            self.rollback = 0
            self.retries = 0
            self.statuses: Counter[str] = Counter()
            self._latencies_ms: list[float] = []
            self._slippage_rates: list[float] = []

    reset = clear

    def stats(self) -> dict[str, Any]:
        with self._lock:
            average_latency = (
                sum(self._latencies_ms) / len(self._latencies_ms)
                if self._latencies_ms
                else 0.0
            )
            average_slippage = (
                sum(self._slippage_rates) / len(self._slippage_rates)
                if self._slippage_rates
                else 0.0
            )
            success_rate = self.success / self.executions if self.executions else 0.0
            return {
                "executions": self.executions,
                "success": self.success,
                "successful": self.success,
                "failed": self.failed,
                "rollback": self.rollback,
                "retries": self.retries,
                "success_rate": round(success_rate, 6),
                "success_rate_percentage": round(success_rate * 100, 2),
                "average_latency_ms": round(average_latency, 3),
                "maximum_latency_ms": round(max(self._latencies_ms), 3)
                if self._latencies_ms
                else 0.0,
                "average_slippage_rate": round(average_slippage, 10),
                "statuses": dict(sorted(self.statuses.items())),
            }

    summary = stats
    snapshot = stats


execution_metrics = ExecutionMetrics()
