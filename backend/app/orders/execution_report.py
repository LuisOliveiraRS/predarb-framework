from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any


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


class ExecutionReport:
    """Relatório agregado de uma ordem executada em uma ou mais venues.

    Preserva o construtor legado com métricas posicionais e também suporta o
    fluxo ``ExecutionReport(order) -> add() -> finalize()``.
    """

    def __init__(
        self,
        order: Any,
        success: bool | None = None,
        executed_quantity: Any = 0.0,
        average_price: Any = 0.0,
        execution_time: Any = 0.0,
        slippage: Any = 0.0,
        fee: Any = 0.0,
        *,
        executions: list[Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if order is None:
            raise ValueError("order não pode ser None.")

        self.order = order
        self.order_id = str(getattr(order, "id", "") or "").strip()
        self.platform = str(getattr(order, "platform", "") or "").strip()
        self.market = str(getattr(order, "market", "") or "").strip()
        status = getattr(order, "status", "UNKNOWN")
        self.status = str(getattr(status, "value", status) or "UNKNOWN").upper()

        self.success = bool(success) if success is not None else False
        self.executed_quantity = _number(executed_quantity)
        self.average_price = _number(average_price)
        self.execution_time = _number(execution_time)
        self.slippage = _number(slippage)
        self.fee = _number(fee)
        self.executions: list[Any] = []
        self.metadata = dict(metadata or {})
        self.finalized = False
        self.timestamp = datetime.now(timezone.utc)

        if success is not None or any(
            value not in (0, 0.0, None)
            for value in (
                executed_quantity,
                average_price,
                execution_time,
                slippage,
                fee,
            )
        ):
            self.executions.append(
                {
                    "success": self.success,
                    "executed_quantity": self.executed_quantity,
                    "average_price": self.average_price,
                    "execution_time": self.execution_time,
                    "slippage": self.slippage,
                    "fee": self.fee,
                    "status": self.status,
                    "source": "legacy_constructor",
                }
            )

        for execution in list(executions or []):
            self.add(execution)

        if self.executions:
            self._recalculate()

    @staticmethod
    def _execution_quantity(execution: Any) -> float:
        for field_name in (
            "executed_quantity",
            "applied_quantity",
            "filled_quantity",
            "quantity",
        ):
            value = _read(execution, field_name, None)
            if value is not None:
                return max(0.0, _number(value))
        return 0.0

    @staticmethod
    def _execution_price(execution: Any) -> float:
        for field_name in ("average_price", "price", "executed_price"):
            value = _read(execution, field_name, None)
            if value is not None:
                return max(0.0, _number(value))
        return 0.0

    @staticmethod
    def _execution_success(execution: Any) -> bool:
        explicit = _read(execution, "success", None)
        if explicit is not None:
            return bool(explicit)
        status = str(_read(execution, "status", "") or "").strip().upper()
        return status in {
            "SUCCESS",
            "OK",
            "ACCEPTED",
            "PARTIALLY_FILLED",
            "FILLED",
            "COMPLETED",
        }

    def _recalculate(self) -> None:
        if not self.executions:
            return

        quantities = [self._execution_quantity(item) for item in self.executions]
        prices = [self._execution_price(item) for item in self.executions]
        successes = [self._execution_success(item) for item in self.executions]

        total_quantity = sum(quantities)
        weighted_value = sum(
            quantity * price
            for quantity, price in zip(quantities, prices)
            if quantity > 0 and price > 0
        )

        self.executed_quantity = round(total_quantity, 8)
        self.average_price = round(
            weighted_value / total_quantity if total_quantity > 0 else 0.0,
            8,
        )
        self.execution_time = round(
            sum(
                _number(
                    _read(item, "execution_time", _read(item, "latency", 0.0))
                )
                for item in self.executions
            ),
            8,
        )
        self.slippage = round(
            (
                sum(
                    _number(
                        _read(item, "slippage", _read(item, "slippage_rate", 0.0))
                    )
                    for item in self.executions
                )
                / len(self.executions)
            ),
            8,
        )
        self.fee = round(
            sum(_number(_read(item, "fee", _read(item, "fees_paid", 0.0))) for item in self.executions),
            8,
        )
        self.success = all(successes)

        if all(successes):
            self.status = "SUCCESS"
        elif any(successes):
            self.status = "PARTIAL"
        else:
            self.status = "FAILED"

    def add(self, execution: Any) -> Any:
        if execution is None:
            raise ValueError("execution não pode ser None.")
        self.executions.append(execution)
        self._recalculate()
        return execution

    def finalize(self) -> "ExecutionReport":
        self._recalculate()
        self.finalized = True
        return self

    @property
    def total_executions(self) -> int:
        return len(self.executions)

    @property
    def successful_executions(self) -> int:
        return sum(1 for item in self.executions if self._execution_success(item))

    @property
    def failed_executions(self) -> int:
        return self.total_executions - self.successful_executions

    @property
    def remaining_quantity(self) -> float:
        quantity = _number(getattr(self.order, "quantity", 0.0))
        return round(max(0.0, quantity - self.executed_quantity), 8)

    @property
    def executed_notional(self) -> float:
        return round(self.executed_quantity * self.average_price, 8)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "platform": self.platform,
            "market": self.market,
            "success": self.success,
            "status": self.status,
            "executed_quantity": self.executed_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_price": self.average_price,
            "executed_notional": self.executed_notional,
            "execution_time": self.execution_time,
            "slippage": self.slippage,
            "fee": self.fee,
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "failed_executions": self.failed_executions,
            "finalized": self.finalized,
            "executions": [_serialize(item) for item in self.executions],
            "metadata": _serialize(self.metadata),
            "timestamp": self.timestamp.isoformat(),
        }
