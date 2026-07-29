from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.orders.order_status import OrderStatus


_FAILURE_STATUSES = {
    "FAILED",
    "ERROR",
    "REJECTED",
    "CANCELLED",
    "CANCELED",
    "EXPIRED",
    "DISABLED",
}

_SUCCESS_STATUSES = {
    "SUCCESS",
    "OK",
    "ACCEPTED",
    "ACKNOWLEDGED",
    "SUBMITTED",
    "OPEN",
    "PARTIALLY_FILLED",
    "PARTIAL_FILL",
    "FILLED",
    "COMPLETED",
}


def _read(target: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(target, Mapping):
        return target.get(field_name, default)
    if target is None:
        return default
    return getattr(target, field_name, default)


def _status_text(value: Any) -> str:
    if isinstance(value, Enum):
        value = value.value
    return str(value or "").strip().upper()


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


@dataclass(init=False, slots=True)
class OrderResponse:
    """Resposta normalizada do envio de uma ordem ao conector.

    ``OrderResponse(order, broker_response)`` continua válido. O sucesso não
    é mais inferido apenas pela existência de um objeto: respostas com status
    de erro, rejeição ou cancelamento são corretamente marcadas como falha.
    """

    order_id: str
    platform: str
    status: str
    success: bool
    accepted: bool
    response: Any
    message: str
    error: str | None
    external_id: str
    metadata: dict[str, Any]
    created_at: datetime

    def __init__(
        self,
        order: Any,
        broker_response: Any = None,
        *,
        success: bool | None = None,
        accepted: bool | None = None,
        message: str = "",
        error: str | None = None,
        external_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if order is None:
            raise ValueError("order não pode ser None.")

        self.order_id = str(getattr(order, "id", "") or "").strip()
        self.platform = str(getattr(order, "platform", "") or "").strip()
        order_status = getattr(order, "status", OrderStatus.CREATED)
        self.status = _status_text(order_status)
        self.response = broker_response

        response_status = _status_text(
            _read(broker_response, "status", _read(broker_response, "state", ""))
        )
        explicit_success = _read(
            broker_response,
            "success",
            _read(broker_response, "ok", None),
        )
        explicit_accepted = _read(
            broker_response,
            "accepted",
            _read(broker_response, "acknowledged", None),
        )

        if success is None:
            if broker_response is None:
                resolved_success = False
            elif explicit_success is not None:
                resolved_success = bool(explicit_success)
            elif response_status in _FAILURE_STATUSES:
                resolved_success = False
            elif response_status in _SUCCESS_STATUSES:
                resolved_success = True
            else:
                resolved_success = True
        else:
            resolved_success = bool(success)

        if accepted is None:
            if explicit_accepted is not None:
                resolved_accepted = bool(explicit_accepted)
            else:
                resolved_accepted = resolved_success and (
                    not response_status or response_status in _SUCCESS_STATUSES
                )
        else:
            resolved_accepted = bool(accepted)

        inferred_error = _read(
            broker_response,
            "error",
            _read(broker_response, "reason", None),
        )
        inferred_message = _read(
            broker_response,
            "message",
            _read(broker_response, "detail", ""),
        )
        inferred_external_id = _read(
            broker_response,
            "external_id",
            _read(
                broker_response,
                "order_id",
                _read(broker_response, "id", ""),
            ),
        )

        self.success = resolved_success
        self.accepted = resolved_accepted
        self.message = str(message or inferred_message or "").strip()
        self.error = (
            None
            if error is None and inferred_error is None
            else str(error if error is not None else inferred_error)
        )
        self.external_id = str(external_id or inferred_external_id or "").strip()
        self.metadata = dict(metadata or {})
        if response_status:
            self.metadata.setdefault("broker_status", response_status)
        self.created_at = datetime.now(timezone.utc)

    @classmethod
    def failure(
        cls,
        order: Any,
        error: Any,
        *,
        response: Any = None,
        message: str = "",
    ) -> "OrderResponse":
        return cls(
            order,
            response,
            success=False,
            accepted=False,
            message=message,
            error=str(error),
        )

    @classmethod
    def disabled(cls, order: Any) -> "OrderResponse":
        return cls(
            order,
            None,
            success=False,
            accepted=False,
            message="Despacho real desabilitado.",
            error="ORDER_DISPATCH_DISABLED",
            metadata={"status": "DISABLED"},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "platform": self.platform,
            "status": self.status,
            "success": self.success,
            "accepted": self.accepted,
            "message": self.message,
            "error": self.error,
            "external_id": self.external_id,
            "response": _serialize(self.response),
            "metadata": _serialize(self.metadata),
            "created_at": self.created_at.isoformat(),
        }
