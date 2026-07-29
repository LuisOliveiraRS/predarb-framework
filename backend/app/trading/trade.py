from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any
from uuid import uuid4


_SUCCESS_STATUSES = {
    "SUCCESS",
    "OK",
    "ACCEPTED",
    "PARTIALLY_FILLED",
    "FILLED",
    "COMPLETED",
}


def _read(target: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(target, Mapping):
        return target.get(field_name, default)
    if target is None:
        return default
    return getattr(target, field_name, default)


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return float(default)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    return number if isfinite(number) else float(default)


def _text(value: Any, default: str = "") -> str:
    if isinstance(value, Enum):
        value = value.value
    return str(default if value is None else value).strip()


def _datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


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
class Trade:
    """Registro normalizado de uma tentativa ou confirmação de execução.

    O objeto preserva ``order`` e ``report`` para compatibilidade, mas também
    captura os principais campos no momento da criação. Assim, mudanças futuras
    na ordem não alteram silenciosamente o histórico financeiro do trade.
    """

    id: str
    order: Any
    report: Any
    order_id: str
    platform: str
    market: str
    symbol: str
    side: str
    status: str
    success: bool
    quantity: float
    average_price: float
    fees: float
    external_id: str
    opportunity_id: str
    leg: str
    created_at: datetime
    executed_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        order: Any,
        report: Any,
        *,
        trade_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        created_at: datetime | str | None = None,
    ) -> None:
        if order is None:
            raise ValueError("order não pode ser None.")
        if report is None:
            raise ValueError("report não pode ser None.")

        self.id = str(trade_id or uuid4()).strip()
        self.order = order
        self.report = report
        self.order_id = _text(_read(order, "id", ""))
        self.platform = _text(
            _read(report, "platform", _read(order, "platform", ""))
        )
        self.market = _text(_read(order, "market", ""))
        self.symbol = _text(_read(order, "symbol", self.market))
        self.side = _text(_read(order, "side", "")).upper()

        report_status = _read(report, "status", None)
        order_status = _read(order, "status", "UNKNOWN")
        self.status = _text(
            order_status if report_status in (None, "") else report_status,
            "UNKNOWN",
        ).upper()

        explicit_success = _read(report, "success", None)
        self.success = (
            self.status in _SUCCESS_STATUSES
            if explicit_success is None
            else bool(explicit_success)
        )

        self.quantity = self._first_number(
            report,
            ("executed_quantity", "applied_quantity", "filled_quantity", "quantity"),
            default=_number(_read(order, "filled_quantity", 0.0)),
        )
        self.average_price = self._first_number(
            report,
            ("average_price", "executed_price", "price"),
            default=_number(_read(order, "average_price", 0.0)),
        )
        self.fees = self._first_number(
            report,
            ("fee", "fees", "fees_paid"),
            default=_number(_read(order, "fees_paid", 0.0)),
        )
        self.external_id = _text(
            _read(report, "external_id", _read(order, "external_id", ""))
        )
        self.opportunity_id = _text(_read(order, "opportunity_id", ""))
        self.leg = _text(_read(order, "leg", "")).upper()

        now = datetime.now(timezone.utc)
        self.created_at = _datetime(created_at) or now
        self.executed_at = (
            _datetime(_read(order, "executed_at", None))
            or _datetime(_read(report, "executed_at", None))
            or _datetime(_read(report, "created_at", None))
            or _datetime(_read(report, "timestamp", None))
        )
        self.metadata = dict(metadata or {})

    @staticmethod
    def _first_number(
        target: Any,
        fields: tuple[str, ...],
        *,
        default: float = 0.0,
    ) -> float:
        for field_name in fields:
            value = _read(target, field_name, None)
            if value is not None:
                return max(0.0, _number(value, default))
        return max(0.0, float(default))

    @property
    def notional(self) -> float:
        return round(self.quantity * self.average_price, 8)

    @property
    def completed(self) -> bool:
        return self.status in {"FILLED", "COMPLETED", "SUCCESS"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "platform": self.platform,
            "market": self.market,
            "symbol": self.symbol,
            "side": self.side,
            "status": self.status,
            "success": self.success,
            "quantity": self.quantity,
            "average_price": self.average_price,
            "notional": self.notional,
            "fees": self.fees,
            "external_id": self.external_id,
            "opportunity_id": self.opportunity_id,
            "leg": self.leg,
            "completed": self.completed,
            "report": _serialize(self.report),
            "metadata": _serialize(self.metadata),
            "created_at": self.created_at.isoformat(),
            "executed_at": (
                self.executed_at.isoformat() if self.executed_at else None
            ),
        }
