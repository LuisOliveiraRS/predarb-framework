from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _serialize(to_dict())
    return value


class ExecutionContext:
    """Estado único e observável de uma execução da camada Trading."""

    __slots__ = (
        "order",
        "venue",
        "report",
        "result",
        "trade",
        "start_time",
        "end_time",
        "metadata",
        "success",
        "finished",
        "retries",
        "rollback",
        "error",
        "live_enabled",
    )

    def __init__(
        self,
        order: Any,
        venue: Any = None,
        *,
        metadata: Mapping[str, Any] | None = None,
        live_enabled: bool = False,
    ) -> None:
        if order is None:
            raise ValueError("order não pode ser None.")

        self.order = order
        self.venue = venue
        self.report = None
        self.result = None
        self.trade = None
        self.start_time = datetime.now(timezone.utc)
        self.end_time: datetime | None = None
        self.metadata = dict(metadata or {})
        self.success = False
        self.finished = False
        self.retries = 0
        self.rollback = False
        self.error: str | None = None
        self.live_enabled = bool(live_enabled)

    @property
    def order_id(self) -> str:
        return str(getattr(self.order, "id", "") or "")

    @property
    def venue_name(self) -> str:
        if isinstance(self.venue, str):
            return self.venue
        if isinstance(self.venue, Mapping):
            return str(
                self.venue.get("name")
                or self.venue.get("platform")
                or self.venue.get("exchange")
                or ""
            )
        return str(
            getattr(self.venue, "name", None)
            or getattr(self.venue, "platform", None)
            or getattr(self.venue, "exchange", None)
            or ""
        )

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or datetime.now(timezone.utc)
        return round(max(0.0, (end - self.start_time).total_seconds()), 6)

    @property
    def duration_ms(self) -> float:
        return round(self.duration_seconds * 1000, 3)

    def increment_retry(self) -> int:
        self.retries += 1
        return self.retries

    retry = increment_retry

    def finish(
        self,
        *,
        success: bool = True,
        report: Any = None,
        result: Any = None,
        trade: Any = None,
        error: Any = None,
    ) -> "ExecutionContext":
        if report is not None:
            self.report = report
        if result is not None:
            self.result = result
        if trade is not None:
            self.trade = trade

        self.success = bool(success)
        self.error = None if error is None else str(error)
        self.finished = True
        self.end_time = datetime.now(timezone.utc)
        return self

    def fail(
        self,
        error: Any,
        *,
        report: Any = None,
        result: Any = None,
    ) -> "ExecutionContext":
        return self.finish(
            success=False,
            report=report,
            result=result,
            error=error,
        )

    def mark_rollback(self, value: bool = True) -> None:
        self.rollback = bool(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "venue": self.venue_name,
            "success": self.success,
            "finished": self.finished,
            "retries": self.retries,
            "rollback": self.rollback,
            "error": self.error,
            "live_enabled": self.live_enabled,
            "duration_seconds": self.duration_seconds,
            "duration_ms": self.duration_ms,
            "report": _serialize(self.report),
            "result": _serialize(self.result),
            "trade": _serialize(self.trade),
            "metadata": _serialize(self.metadata),
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }
