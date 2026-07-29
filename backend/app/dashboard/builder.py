from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from math import isfinite
from typing import Any, Mapping

from app.dashboard.schemas import DashboardCard


class DashboardBuilder:
    """Converte dados internos em uma resposta JSON estável."""

    @classmethod
    def serialize(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Enum):
            return cls.serialize(value.value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Mapping):
            return {
                str(key): cls.serialize(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [cls.serialize(item) for item in value]
        if hasattr(value, "model_dump") and callable(value.model_dump):
            return cls.serialize(value.model_dump())
        if hasattr(value, "to_dict") and callable(value.to_dict):
            return cls.serialize(value.to_dict())
        if is_dataclass(value):
            return cls.serialize(asdict(value))
        if hasattr(value, "__dict__"):
            return cls.serialize(
                {
                    key: item
                    for key, item in vars(value).items()
                    if not key.startswith("_")
                }
            )
        return str(value)

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        if value is None or isinstance(value, bool):
            return default
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if isfinite(number) else default

    def cards(self, data: Mapping[str, Any]) -> list[dict[str, Any]]:
        values = {
            "markets": int(self._number(data.get("markets"))),
            "opportunities": int(self._number(data.get("opportunities"))),
            "orders": int(self._number(data.get("orders"))),
            "positions": int(self._number(data.get("positions"))),
            "portfolio": round(self._number(data.get("portfolio")), 2),
            "pnl": round(self._number(data.get("pnl")), 2),
            "connections": int(self._number(data.get("connections"))),
            "ai_confidence": round(self._number(data.get("ai_confidence")), 4),
        }

        definitions = [
            ("Markets", "markets", "blue", None),
            ("Opportunities", "opportunities", "green", None),
            ("Orders", "orders", "purple", None),
            ("Positions", "positions", "orange", None),
            ("Portfolio", "portfolio", "blue", None),
            ("PnL", "pnl", "green" if values["pnl"] >= 0 else "red", None),
            ("Connections", "connections", "blue", None),
            ("AI Confidence", "ai_confidence", "purple", None),
        ]

        return [
            DashboardCard(
                title=title,
                value=values[key],
                color=color,
                key=key,
                unit=unit,
            ).model_dump()
            for title, key, color, unit in definitions
        ]

    def build(self, data: Mapping[str, Any]) -> dict[str, Any]:
        state = dict(data.get("state") or {})
        payload = dict(data)

        for key in (
            "markets",
            "opportunities",
            "orders",
            "positions",
            "connections",
            "portfolio",
            "pnl",
            "ai_confidence",
            "updated_at",
        ):
            payload.setdefault(key, state.get(key))

        payload["cards"] = self.cards(payload)
        return self.serialize(payload)


dashboard_builder = DashboardBuilder()
