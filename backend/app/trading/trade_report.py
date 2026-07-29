from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.trading.trade import Trade


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


class TradeReport:
    """Representação serializável de um ``Trade``."""

    def __init__(self, trade: Trade) -> None:
        if not isinstance(trade, Trade):
            raise TypeError("trade deve ser uma instância de Trade.")
        self.trade = trade

    @property
    def success(self) -> bool:
        return self.trade.success

    @property
    def status(self) -> str:
        return self.trade.status

    def to_dict(self) -> dict[str, Any]:
        data = self.trade.to_dict()
        return {
            "trade_id": data["id"],
            "order_id": data["order_id"],
            "platform": data["platform"],
            "market": data["market"],
            "symbol": data["symbol"],
            "side": data["side"],
            "status": data["status"],
            "success": data["success"],
            "quantity": data["quantity"],
            "average_price": data["average_price"],
            "notional": data["notional"],
            "fees": data["fees"],
            "external_id": data["external_id"],
            "opportunity_id": data["opportunity_id"],
            "leg": data["leg"],
            "completed": data["completed"],
            "execution": _serialize(self.trade.report),
            "metadata": _serialize(self.trade.metadata),
            "created_at": data["created_at"],
            "executed_at": data["executed_at"],
        }
