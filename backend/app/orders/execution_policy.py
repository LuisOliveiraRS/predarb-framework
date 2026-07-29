from __future__ import annotations

from enum import Enum
from typing import Any


class ExecutionPolicy(str, Enum):
    """Políticas reconhecidas pelo planejador de execução do OMS.

    As políticas descrevem *como* uma ordem deve ser planejada. Elas não
    autorizam o envio para uma exchange e não executam conectores.
    """

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "POST_ONLY"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "ICEBERG"
    SPLIT = "SPLIT"
    PARALLEL = "PARALLEL"
    SMART = "SMART"
    ADAPTIVE = "ADAPTIVE"

    @classmethod
    def parse(cls, value: Any) -> "ExecutionPolicy":
        if isinstance(value, cls):
            return value
        if not isinstance(value, str):
            raise TypeError("execution_policy deve ser ExecutionPolicy ou string.")

        normalized = (
            value.strip()
            .upper()
            .replace("-", "_")
            .replace(" ", "_")
        )
        aliases = {
            "MKT": cls.MARKET,
            "LMT": cls.LIMIT,
            "IMMEDIATE_OR_CANCEL": cls.IOC,
            "FILL_OR_KILL": cls.FOK,
            "POSTONLY": cls.POST_ONLY,
            "TIME_WEIGHTED_AVERAGE_PRICE": cls.TWAP,
            "VOLUME_WEIGHTED_AVERAGE_PRICE": cls.VWAP,
            "MULTI_EXCHANGE": cls.PARALLEL,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return cls(normalized)
        except ValueError as exc:
            raise ValueError(f"Política de execução inválida: {value!r}.") from exc

    @property
    def scheduled(self) -> bool:
        return self in {self.TWAP, self.VWAP, self.ICEBERG}

    @property
    def sliced(self) -> bool:
        return self in {
            self.TWAP,
            self.VWAP,
            self.ICEBERG,
            self.SPLIT,
            self.PARALLEL,
        }

    @property
    def requires_external_router(self) -> bool:
        return self in {self.SMART, self.ADAPTIVE}
