from __future__ import annotations

from enum import Enum
from typing import Any


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"

    @classmethod
    def parse(cls, value: Any) -> "OrderType":
        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise TypeError("order_type deve ser OrderType ou string.")

        normalized = value.strip().upper()
        aliases = {
            "MKT": cls.MARKET,
            "LMT": cls.LIMIT,
        }

        if normalized in aliases:
            return aliases[normalized]

        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Tipo de ordem inválido: {value!r}.") from exc
