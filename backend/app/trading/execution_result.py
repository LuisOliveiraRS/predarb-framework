from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
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


@dataclass(slots=True)
class ExecutionResult:
    """Resultado normalizado produzido pela camada Trading."""

    success: bool
    report: Any = None
    error: str | None = None
    context: Any = None
    trade: Any = None
    status: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        self.success = bool(self.success)
        self.error = None if self.error is None else str(self.error)
        self.status = str(
            self.status or ("SUCCESS" if self.success else "FAILED")
        ).strip().upper()
        self.metadata = dict(self.metadata or {})
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

    @classmethod
    def ok(
        cls,
        *,
        report: Any = None,
        context: Any = None,
        trade: Any = None,
        status: str = "SUCCESS",
        metadata: Mapping[str, Any] | None = None,
    ) -> "ExecutionResult":
        return cls(
            success=True,
            report=report,
            context=context,
            trade=trade,
            status=status,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def failure(
        cls,
        error: Any,
        *,
        report: Any = None,
        context: Any = None,
        trade: Any = None,
        status: str = "FAILED",
        metadata: Mapping[str, Any] | None = None,
    ) -> "ExecutionResult":
        return cls(
            success=False,
            report=report,
            error=str(error),
            context=context,
            trade=trade,
            status=status,
            metadata=dict(metadata or {}),
        )

    @property
    def order_id(self) -> str:
        context_order = getattr(self.context, "order", None)
        trade_order_id = getattr(self.trade, "order_id", None)
        return str(
            getattr(context_order, "id", None)
            or trade_order_id
            or ""
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "order_id": self.order_id,
            "report": _serialize(self.report),
            "error": self.error,
            "context": _serialize(self.context),
            "trade": _serialize(self.trade),
            "metadata": _serialize(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    def __bool__(self) -> bool:
        return self.success
