from __future__ import annotations

import json
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
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _serialize(to_dict())
        except Exception:
            pass
    return str(value)


class ExecutionLogger:
    """Logger estruturado e tolerante aos vários relatórios do OMS."""

    def __init__(
        self,
        name: str = "PredArb.Orders.Execution",
        *,
        history_size: int = 500,
    ) -> None:
        self.logger = logging.getLogger(name)
        self.logger.addHandler(logging.NullHandler())
        self._records: deque[dict[str, Any]] = deque(
            maxlen=max(1, int(history_size))
        )
        self._lock = RLock()
        self.last_record: dict[str, Any] = {}

    def configure(
        self,
        *,
        level: int | str | None = None,
        handler: logging.Handler | None = None,
        propagate: bool | None = None,
    ) -> "ExecutionLogger":
        if level is not None:
            self.logger.setLevel(level)
        if handler is not None and handler not in self.logger.handlers:
            self.logger.addHandler(handler)
        if propagate is not None:
            self.logger.propagate = bool(propagate)
        return self

    def _emit(
        self,
        level: int,
        event: str,
        message: str,
        **context: Any,
    ) -> dict[str, Any]:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": str(event or "message").strip().upper(),
            "level": logging.getLevelName(level),
            "message": str(message or "").strip(),
            "context": _serialize(context),
        }
        with self._lock:
            self._records.append(record)
            self.last_record = dict(record)

        self.logger.log(
            level,
            "%s",
            json.dumps(record, ensure_ascii=False, default=str),
        )
        return record

    def info(self, message: str, **context: Any) -> dict[str, Any]:
        return self._emit(logging.INFO, "INFO", message, **context)

    def warning(self, message: str, **context: Any) -> dict[str, Any]:
        return self._emit(logging.WARNING, "WARNING", message, **context)

    def error(self, message: str, **context: Any) -> dict[str, Any]:
        return self._emit(logging.ERROR, "ERROR", message, **context)

    def exception(self, message: str, **context: Any) -> dict[str, Any]:
        return self._emit(logging.ERROR, "EXCEPTION", message, **context)

    def execution(self, report: Any) -> dict[str, Any]:
        data = _serialize(report)
        if not isinstance(data, Mapping):
            data = {"report": data}

        order_id = str(data.get("order_id", "") or "").strip()
        platform = str(data.get("platform", "") or "").strip()
        status = str(data.get("status", "UNKNOWN") or "UNKNOWN").strip().upper()
        success = data.get("success")

        message = " ".join(
            part
            for part in (
                f"[{order_id}]" if order_id else "",
                platform,
                status,
            )
            if part
        ) or "Execution report"

        level = logging.INFO if success is not False else logging.WARNING
        return self._emit(
            level,
            "EXECUTION",
            message,
            report=data,
        )

    def retry(self, report: Any) -> dict[str, Any]:
        data = _serialize(report)
        return self._emit(
            logging.WARNING,
            "RETRY",
            "Tentativa de execução registrada.",
            report=data,
        )

    def task(self, task: Any) -> dict[str, Any]:
        data = _serialize(task)
        status = (
            data.get("status", "UNKNOWN")
            if isinstance(data, Mapping)
            else "UNKNOWN"
        )
        return self._emit(
            logging.INFO,
            "TASK",
            f"Tarefa de execução: {status}",
            task=data,
        )

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(record) for record in self._records]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
            self.last_record = {}

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "logger": self.logger.name,
                "level": logging.getLevelName(self.logger.level),
                "records": len(self._records),
                "last_record": dict(self.last_record),
            }


execution_logger = ExecutionLogger()
