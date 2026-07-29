from __future__ import annotations

from enum import Enum
from typing import Any


class TimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    DAY = "DAY"

    @classmethod
    def parse(cls, value: Any) -> "TimeInForce":
        if isinstance(value, cls):
            return value

        if not isinstance(value, str):
            raise TypeError("time_in_force deve ser TimeInForce ou string.")

        normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "GOOD_TILL_CANCELLED": cls.GTC,
            "GOOD_TIL_CANCELLED": cls.GTC,
            "IMMEDIATE_OR_CANCEL": cls.IOC,
            "FILL_OR_KILL": cls.FOK,
        }

        if normalized in aliases:
            return aliases[normalized]

        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Time in force inválido: {value!r}.") from exc
