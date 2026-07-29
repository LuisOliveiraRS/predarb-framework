from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from app.orders.order_side import OrderSide
from app.orders.order_status import OrderStatus
from app.orders.order_type import OrderType
from app.orders.time_in_force import TimeInForce


class OrderValidator:
    """Valida ordens antes do registro ou envio ao conector."""

    def __init__(
        self,
        *,
        require_platform: bool = True,
        prediction_price_range: bool = True,
    ) -> None:
        self.require_platform = bool(require_platform)
        self.prediction_price_range = bool(prediction_price_range)
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    def evaluate(self, order: Any) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        values: dict[str, Any] = {}

        if order is None:
            report = {
                "valid": False,
                "errors": ["ORDER_MISSING"],
                "warnings": [],
                "values": {},
            }
            self.last_report = report
            return report

        platform = str(self._read(order, "platform", "") or "").strip()
        market = str(self._read(order, "market", "") or "").strip()
        symbol = str(self._read(order, "symbol", "") or "").strip()

        values.update(platform=platform, market=market, symbol=symbol)

        if self.require_platform and not platform:
            errors.append("PLATFORM_MISSING")
        if not market and not symbol:
            errors.append("MARKET_OR_SYMBOL_MISSING")

        quantity = self._number(self._read(order, "quantity", None))
        values["quantity"] = quantity
        if quantity is None or quantity <= 0:
            errors.append("QUANTITY_INVALID")

        filled_quantity = self._number(
            self._read(order, "filled_quantity", 0.0)
        )
        values["filled_quantity"] = filled_quantity
        if filled_quantity is None or filled_quantity < 0:
            errors.append("FILLED_QUANTITY_INVALID")
        elif quantity is not None and filled_quantity > quantity:
            errors.append("FILLED_QUANTITY_EXCEEDS_ORDER")

        try:
            side = OrderSide.parse(self._read(order, "side", None))
            values["side"] = side.value
        except (TypeError, ValueError):
            errors.append("SIDE_INVALID")
            side = None

        try:
            order_type = OrderType.parse(self._read(order, "order_type", None))
            values["order_type"] = order_type.value
        except (TypeError, ValueError):
            errors.append("ORDER_TYPE_INVALID")
            order_type = None

        try:
            time_in_force = TimeInForce.parse(
                self._read(order, "time_in_force", TimeInForce.GTC)
            )
            values["time_in_force"] = time_in_force.value
        except (TypeError, ValueError):
            errors.append("TIME_IN_FORCE_INVALID")

        try:
            status = OrderStatus.parse(
                self._read(order, "status", OrderStatus.CREATED)
            )
            values["status"] = status.value
        except (TypeError, ValueError):
            errors.append("STATUS_INVALID")
            status = None

        price = self._number(self._read(order, "price", None))
        values["price"] = price

        if price is None or price < 0:
            errors.append("PRICE_INVALID")
        elif order_type is OrderType.LIMIT and price <= 0:
            errors.append("LIMIT_PRICE_REQUIRED")
        elif self.prediction_price_range and price > 1:
            errors.append("PRICE_OUT_OF_RANGE")

        if status is not None and status.terminal:
            warnings.append("ORDER_ALREADY_TERMINAL")

        errors = list(dict.fromkeys(errors))
        warnings = list(dict.fromkeys(warnings))

        report = {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "values": values,
        }
        self.last_report = report
        return report

    def validate(self, order: Any) -> bool:
        return bool(self.evaluate(order)["valid"])

    def validate_or_raise(self, order: Any) -> Any:
        report = self.evaluate(order)
        if not report["valid"]:
            raise ValueError(
                "Ordem inválida: " + ", ".join(report["errors"])
            )
        return order

    require_valid = validate_or_raise


order_validator = OrderValidator()
