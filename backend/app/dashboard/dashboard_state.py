from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from threading import RLock
from typing import Any


class DashboardState:
    """Estado leve e thread-safe para contadores em tempo real.

    O estado não substitui repositórios do OMS. Ele mantém apenas valores
    transitórios necessários para eventos e conexões do painel.
    """

    COUNTERS = {
        "markets",
        "opportunities",
        "orders",
        "positions",
        "connections",
    }

    VALUES = {
        "portfolio",
        "pnl",
        "ai_confidence",
    }

    DEFAULTS: dict[str, int | float] = {
        "markets": 0,
        "opportunities": 0,
        "orders": 0,
        "positions": 0,
        "connections": 0,
        "portfolio": 10_000.0,
        "pnl": 0.0,
        "ai_confidence": 0.0,
    }

    def __init__(self) -> None:
        self._lock = RLock()
        self._data: dict[str, int | float] = {}
        self._updated_at = datetime.now(timezone.utc)
        self.reset()

    @staticmethod
    def _number(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")

        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{field_name} deve ser numérico.") from exc

        if not isfinite(number):
            raise ValueError(f"{field_name} deve ser finito.")

        return number

    def reset(self) -> None:
        with self._lock:
            self._data = dict(self.DEFAULTS)
            self._updated_at = datetime.now(timezone.utc)

    def increment(self, field_name: str, amount: int = 1) -> int:
        field = str(field_name or "").strip()
        if field not in self.COUNTERS:
            raise KeyError(f"Contador desconhecido: {field!r}.")
        if isinstance(amount, bool):
            raise TypeError("amount não pode ser booleano.")

        try:
            increment = int(amount)
        except (TypeError, ValueError) as exc:
            raise TypeError("amount deve ser inteiro.") from exc

        with self._lock:
            current = int(self._data[field])
            self._data[field] = max(0, current + increment)
            self._updated_at = datetime.now(timezone.utc)
            return int(self._data[field])

    def set(self, field_name: str, value: Any) -> int | float:
        field = str(field_name or "").strip()
        if field not in self.DEFAULTS:
            raise KeyError(f"Campo desconhecido: {field!r}.")

        number = self._number(value, field)
        resolved: int | float

        if field in self.COUNTERS:
            resolved = max(0, int(number))
        else:
            resolved = float(number)

        with self._lock:
            self._data[field] = resolved
            self._updated_at = datetime.now(timezone.utc)

        return resolved

    def update(self, values: dict[str, Any], *, ignore_unknown: bool = False) -> dict[str, Any]:
        if not isinstance(values, dict):
            raise TypeError("values deve ser um dicionário.")

        updated: dict[str, Any] = {}
        for field_name, value in values.items():
            if field_name not in self.DEFAULTS:
                if ignore_unknown:
                    continue
                raise KeyError(f"Campo desconhecido: {field_name!r}.")
            updated[field_name] = self.set(field_name, value)
        return updated

    def get(self, field_name: str, default: Any = None) -> Any:
        field = str(field_name or "").strip()
        with self._lock:
            return self._data.get(field, default)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                **self._data,
                "updated_at": self._updated_at.isoformat(),
            }

    def __getattr__(self, field_name: str) -> Any:
        if field_name in self.DEFAULTS:
            return self.get(field_name)
        raise AttributeError(field_name)

    def __setattr__(self, field_name: str, value: Any) -> None:
        if field_name.startswith("_") or field_name not in self.DEFAULTS:
            object.__setattr__(self, field_name, value)
            return
        self.set(field_name, value)


dashboard_state = DashboardState()
