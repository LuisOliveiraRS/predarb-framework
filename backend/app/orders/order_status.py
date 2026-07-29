from __future__ import annotations

from enum import Enum
from typing import Any


class OrderStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

    # Compatibilidade com implementações antigas.
    PENDING = "CREATED"
    SENT = "SUBMITTED"
    ACKNOWLEDGED = "ACCEPTED"
    PARTIAL_FILL = "PARTIALLY_FILLED"
    CANCELED = "CANCELLED"
    ERROR = "FAILED"

    @classmethod
    def parse(cls, value: Any) -> "OrderStatus":
        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise TypeError("status deve ser OrderStatus ou string.")

        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "PENDING": cls.CREATED,
            "SENT": cls.SUBMITTED,
            "ACKNOWLEDGED": cls.ACCEPTED,
            "PARTIAL_FILL": cls.PARTIALLY_FILLED,
            "PARTIAL": cls.PARTIALLY_FILLED,
            "CANCELED": cls.CANCELLED,
            "ERROR": cls.FAILED,
        }

        if normalized in aliases:
            return aliases[normalized]

        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Status de ordem inválido: {value!r}.") from exc

    @property
    def terminal(self) -> bool:
        return self in {
            self.FILLED,
            self.CANCELLED,
            self.REJECTED,
            self.EXPIRED,
            self.FAILED,
        }

    @property
    def open(self) -> bool:
        return not self.terminal

    @property
    def successful(self) -> bool:
        return self is self.FILLED
