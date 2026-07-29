from __future__ import annotations

import logging

from collections import deque
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
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
    return str(value)


class TradingExecutionLogger:
    """Logger estruturado com histórico em memória e API legada."""

    def __init__(
        self,
        *,
        name: str = "TradingPipeline",
        history_size: int = 1_000,
        logger: logging.Logger | None = None,
    ) -> None:
        if isinstance(history_size, bool):
            raise TypeError("history_size não pode ser booleano.")
        history_size = int(history_size)
        if history_size <= 0:
            raise ValueError("history_size deve ser maior que zero.")

        self.logger = logger or logging.getLogger(name)
        if not self.logger.handlers:
            self.logger.addHandler(logging.NullHandler())
        self._history: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._lock = RLock()

    @staticmethod
    def _level(level: str) -> str:
        normalized = str(level or "INFO").strip().upper()
        return normalized if normalized in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"

    def log(
        self,
        level: str,
        message: Any,
        *,
        event: str = "MESSAGE",
        context: Any = None,
        metadata: Mapping[str, Any] | None = None,
        error: Any = None,
    ) -> dict[str, Any]:
        resolved_level = self._level(level)
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": resolved_level,
            "event": str(event or "MESSAGE").strip().upper(),
            "message": str(message),
            "order_id": str(getattr(context, "order_id", "") or "") if context is not None else "",
            "venue": str(getattr(context, "venue_name", "") or "") if context is not None else "",
            "error": None if error is None else str(error),
            "metadata": _serialize(dict(metadata or {})),
        }

        with self._lock:
            self._history.append(dict(record))

        self.logger.log(getattr(logging, resolved_level), record["message"])
        return dict(record)

    def info(self, message: Any, **kwargs: Any) -> dict[str, Any]:
        return self.log("INFO", message, **kwargs)

    def warning(self, message: Any, **kwargs: Any) -> dict[str, Any]:
        return self.log("WARNING", message, **kwargs)

    warn = warning

    def error(self, message: Any, **kwargs: Any) -> dict[str, Any]:
        return self.log("ERROR", message, **kwargs)

    def execution(
        self,
        value: Any,
        *,
        context: Any = None,
        event: str = "EXECUTION",
    ) -> dict[str, Any]:
        if isinstance(value, Mapping):
            success = bool(value.get("success", False))
            status = str(value.get("status", "SUCCESS" if success else "FAILED")).upper()
            error = value.get("error")
            metadata = dict(value)
        else:
            success = bool(getattr(value, "success", False))
            status = str(getattr(value, "status", "SUCCESS" if success else "FAILED")).upper()
            error = getattr(value, "error", None)
            to_dict = getattr(value, "to_dict", None)
            metadata = to_dict() if callable(to_dict) else {"value": str(value)}
            context = context or getattr(value, "context", None)

        level = "INFO" if success else "WARNING"
        order_id = str(getattr(context, "order_id", "") or "") if context is not None else ""
        venue = str(getattr(context, "venue_name", "") or "") if context is not None else ""
        prefix = " ".join(item for item in (f"[{order_id}]" if order_id else "", venue) if item)
        message = f"{prefix} {status}".strip()

        return self.log(
            level,
            message,
            event=event,
            context=context,
            metadata=metadata if isinstance(metadata, Mapping) else {"value": metadata},
            error=error,
        )

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._history]

    @property
    def last_record(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._history[-1]) if self._history else None

    def clear(self) -> None:
        with self._lock:
            self._history.clear()

    reset = clear

    def status(self) -> dict[str, Any]:
        history = self.all()
        levels: dict[str, int] = {}
        for item in history:
            level = str(item.get("level", "INFO"))
            levels[level] = levels.get(level, 0) + 1
        return {
            "records": len(history),
            "levels": dict(sorted(levels.items())),
            "last_record": self.last_record,
        }


ExecutionLogger = TradingExecutionLogger
execution_logger = TradingExecutionLogger()
