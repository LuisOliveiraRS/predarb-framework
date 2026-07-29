from __future__ import annotations

from enum import Enum
from typing import Any


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

    @classmethod
    def parse(cls, value: Any) -> "OrderSide":
        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise TypeError("side deve ser OrderSide ou string.")

        normalized = value.strip().upper()
        aliases = {
            "B": cls.BUY,
            "LONG": cls.BUY,
            "S": cls.SELL,
            "SHORT": cls.SELL,
        }

        if normalized in aliases:
            return aliases[normalized]

        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Side inválido: {value!r}.") from exc

    @property
    def opposite(self) -> "OrderSide":
        return self.SELL if self is self.BUY else self.BUY
