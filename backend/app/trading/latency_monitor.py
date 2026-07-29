from __future__ import annotations

import time

from collections import deque
from collections.abc import Mapping
from math import isfinite
from threading import RLock
from typing import Any, Callable


class LatencyMonitor:
    """Mede latência com relógio monotônico e mantém histórico limitado."""

    def __init__(self, *, history_size: int = 1_000) -> None:
        if isinstance(history_size, bool):
            raise TypeError("history_size não pode ser booleano.")
        history_size = int(history_size)
        if history_size <= 0:
            raise ValueError("history_size deve ser maior que zero.")

        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _started_value(started: Any) -> float:
        if isinstance(started, bool):
            raise TypeError("started não pode ser booleano.")
        try:
            value = float(started)
        except (TypeError, ValueError) as exc:
            raise TypeError("started deve ser o valor retornado por start().") from exc
        if not isfinite(value) or value <= 0:
            raise ValueError("started deve ser um valor monotônico válido.")
        return value

    @staticmethod
    def _context_metadata(context: Any) -> dict[str, Any] | None:
        metadata = getattr(context, "metadata", None)
        return metadata if isinstance(metadata, dict) else None

    def start(self) -> float:
        """Retorna um marcador monotônico compatível com a API legada."""
        return time.perf_counter()

    def stop(
        self,
        started: Any,
        *,
        label: str = "execution",
        context: Any = None,
        metadata: Mapping[str, Any] | None = None,
        record: bool = True,
    ) -> float:
        """Finaliza a medição e retorna segundos, como na implementação antiga."""
        started_value = self._started_value(started)
        seconds = max(0.0, time.perf_counter() - started_value)
        milliseconds = seconds * 1_000

        report = {
            "label": str(label or "execution").strip() or "execution",
            "seconds": round(seconds, 6),
            "milliseconds": round(milliseconds, 3),
            "metadata": dict(metadata or {}),
        }

        if context is not None:
            report["order_id"] = str(getattr(context, "order_id", "") or "")
            report["venue"] = str(getattr(context, "venue_name", "") or "")
            context_metadata = self._context_metadata(context)
            if context_metadata is not None:
                context_metadata["latency"] = dict(report)

        if record:
            with self._lock:
                self._history.append(dict(report))

        self.last_report = dict(report)
        return report["seconds"]

    def measure(
        self,
        operation: Callable[..., Any],
        *args: Any,
        label: str = "execution",
        context: Any = None,
        metadata: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> tuple[Any, dict[str, Any]]:
        if not callable(operation):
            raise TypeError("operation deve ser chamável.")

        started = self.start()
        try:
            result = operation(*args, **kwargs)
        finally:
            self.stop(
                started,
                label=label,
                context=context,
                metadata=metadata,
            )

        return result, dict(self.last_report)

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._history]

    def clear(self) -> None:
        with self._lock:
            self._history.clear()
        self.last_report = {}

    reset = clear

    def summary(self) -> dict[str, Any]:
        history = self.all()
        values = [float(item["milliseconds"]) for item in history]

        if not values:
            return {
                "measurements": 0,
                "average_ms": 0.0,
                "minimum_ms": 0.0,
                "maximum_ms": 0.0,
                "total_ms": 0.0,
                "last_report": dict(self.last_report),
            }

        return {
            "measurements": len(values),
            "average_ms": round(sum(values) / len(values), 3),
            "minimum_ms": round(min(values), 3),
            "maximum_ms": round(max(values), 3),
            "total_ms": round(sum(values), 3),
            "last_report": dict(self.last_report),
        }

    stats = summary


latency_monitor = LatencyMonitor()
