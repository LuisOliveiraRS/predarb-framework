from __future__ import annotations

from enum import Enum
from typing import Any

from app.orders.order_status import OrderStatus


class OrderEvent(str, Enum):
    """Eventos canônicos do ciclo de vida de uma ordem.

    Os valores permanecem em minúsculas para preservar compatibilidade
    com o histórico e integrações antigas do OMS.
    """

    CREATED = "created"
    VALIDATED = "validated"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    FAILED = "failed"
    RETRYING = "retrying"

    # Aliases legados.
    PENDING = "created"
    SENT = "submitted"
    ACKNOWLEDGED = "accepted"
    PARTIAL_FILL = "partially_filled"
    CANCELED = "cancelled"
    ERROR = "failed"

    @classmethod
    def parse(cls, value: Any) -> "OrderEvent":
        if isinstance(value, cls):
            return value

        if isinstance(value, OrderStatus):
            return cls.from_status(value)

        if not isinstance(value, str):
            raise TypeError("event deve ser OrderEvent, OrderStatus ou string.")

        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "pending": cls.CREATED,
            "sent": cls.SUBMITTED,
            "acknowledged": cls.ACCEPTED,
            "partial_fill": cls.PARTIALLY_FILLED,
            "partial": cls.PARTIALLY_FILLED,
            "canceled": cls.CANCELLED,
            "error": cls.FAILED,
        }

        if normalized in aliases:
            return aliases[normalized]

        try:
            return cls(normalized)
        except ValueError as exc:
            # Também aceita nomes/valores de OrderStatus.
            try:
                return cls.from_status(OrderStatus.parse(value))
            except (TypeError, ValueError):
                raise ValueError(f"Evento de ordem inválido: {value!r}.") from exc

    @classmethod
    def from_status(cls, status: OrderStatus | str) -> "OrderEvent":
        resolved = OrderStatus.parse(status)
        mapping = {
            OrderStatus.CREATED: cls.CREATED,
            OrderStatus.VALIDATED: cls.VALIDATED,
            OrderStatus.SUBMITTED: cls.SUBMITTED,
            OrderStatus.ACCEPTED: cls.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED: cls.PARTIALLY_FILLED,
            OrderStatus.FILLED: cls.FILLED,
            OrderStatus.CANCELLED: cls.CANCELLED,
            OrderStatus.REJECTED: cls.REJECTED,
            OrderStatus.EXPIRED: cls.EXPIRED,
            OrderStatus.FAILED: cls.FAILED,
            OrderStatus.RETRYING: cls.RETRYING,
        }
        return mapping[resolved]

    @property
    def status(self) -> OrderStatus:
        mapping = {
            self.CREATED: OrderStatus.CREATED,
            self.VALIDATED: OrderStatus.VALIDATED,
            self.SUBMITTED: OrderStatus.SUBMITTED,
            self.ACCEPTED: OrderStatus.ACCEPTED,
            self.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
            self.FILLED: OrderStatus.FILLED,
            self.CANCELLED: OrderStatus.CANCELLED,
            self.REJECTED: OrderStatus.REJECTED,
            self.EXPIRED: OrderStatus.EXPIRED,
            self.FAILED: OrderStatus.FAILED,
            self.RETRYING: OrderStatus.RETRYING,
        }
        return mapping[self]
