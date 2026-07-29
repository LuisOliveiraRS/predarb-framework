from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.orders.order_batch import OrderBatch


def _read(target: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(target, Mapping):
        return target.get(field_name, default)
    if target is None:
        return default
    return getattr(target, field_name, default)


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "isoformat") and callable(value.isoformat):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _serialize(to_dict())
    return value


class OrderBatchReport:
    """Resultado agregado do envio coordenado de um lote de ordens."""

    def __init__(
        self,
        responses: list[Any] | tuple[Any, ...] | None = None,
        *,
        batch: OrderBatch | None = None,
        compensation: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.batch = batch
        self.batch_id = batch.id if batch is not None else ""
        self.responses = list(responses or [])
        self.compensation = dict(compensation or {})
        self.metadata = dict(metadata or {})
        self.created_at = datetime.now(timezone.utc)

    @staticmethod
    def _status(response: Any) -> str:
        status = _read(response, "status", "UNKNOWN")
        value = getattr(status, "value", status)
        return str(value or "UNKNOWN").strip().upper()

    @staticmethod
    def _success(response: Any) -> bool:
        return bool(_read(response, "success", False))

    @staticmethod
    def _accepted(response: Any) -> bool:
        accepted = _read(response, "accepted", None)
        return bool(_read(response, "success", False) if accepted is None else accepted)

    @property
    def total(self) -> int:
        return len(self.responses)

    @property
    def successful(self) -> int:
        return sum(1 for response in self.responses if self._success(response))

    @property
    def failed(self) -> int:
        return self.total - self.successful

    @property
    def accepted(self) -> int:
        return sum(1 for response in self.responses if self._accepted(response))

    @property
    def success(self) -> bool:
        return self.total > 0 and self.failed == 0

    @property
    def partial(self) -> bool:
        return self.successful > 0 and self.failed > 0

    @property
    def compensation_required(self) -> bool:
        if "required" in self.compensation:
            return bool(self.compensation["required"])
        return self.partial and self.accepted > 0

    @property
    def status(self) -> str:
        if self.total == 0:
            return "EMPTY"

        statuses = [self._status(response) for response in self.responses]
        if all(status == "DISABLED" for status in statuses):
            return "DISABLED"
        if self.success:
            return "SUCCESS"
        if self.partial:
            return "PARTIAL"
        return "FAILED"

    @property
    def errors(self) -> list[str]:
        errors: list[str] = []
        for response in self.responses:
            error = _read(response, "error", None)
            if error not in (None, ""):
                errors.append(str(error))
        return errors

    def to_list(self) -> list[Any]:
        return list(self.responses)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "status": self.status,
            "success": self.success,
            "partial": self.partial,
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "accepted": self.accepted,
            "compensation_required": self.compensation_required,
            "compensation": _serialize(self.compensation),
            "errors": self.errors,
            "responses": [_serialize(response) for response in self.responses],
            "metadata": _serialize(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    def __iter__(self) -> Iterator[Any]:
        return iter(self.responses)

    def __len__(self) -> int:
        return self.total

    def __getitem__(self, index: int) -> Any:
        return self.responses[index]

    def __bool__(self) -> bool:
        return self.success
