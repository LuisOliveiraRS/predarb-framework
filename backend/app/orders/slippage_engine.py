from __future__ import annotations

from math import isfinite
from typing import Any

from app.orders.order_side import OrderSide


class SlippageEngine:
    """Calcula desvio de preço sem executar ou modificar ordens.

    ``calculate()`` preserva o retorno legado em percentual. Métodos novos
    também expõem a taxa decimal e o impacto financeiro da diferença.
    """

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

    @staticmethod
    def _side(value: Any) -> OrderSide:
        return OrderSide.parse(value or OrderSide.BUY)

    def rate(
        self,
        expected_price: Any,
        executed_price: Any,
        side: OrderSide | str = OrderSide.BUY,
    ) -> float:
        expected = self._number(expected_price, "expected_price")
        executed = self._number(executed_price, "executed_price")
        if expected < 0 or executed < 0:
            raise ValueError("Os preços não podem ser negativos.")
        if expected == 0:
            return 0.0

        resolved_side = self._side(side)
        difference = (
            executed - expected
            if resolved_side is OrderSide.BUY
            else expected - executed
        )
        return round(difference / expected, 10)

    def calculate(
        self,
        expected_price: Any,
        executed_price: Any,
        side: OrderSide | str = OrderSide.BUY,
    ) -> float:
        """Retorna o slippage percentual, preservando a interface antiga."""

        return round(
            self.rate(expected_price, executed_price, side) * 100,
            8,
        )

    def amount(
        self,
        expected_price: Any,
        executed_price: Any,
        quantity: Any,
        side: OrderSide | str = OrderSide.BUY,
    ) -> float:
        expected = self._number(expected_price, "expected_price")
        executed = self._number(executed_price, "executed_price")
        resolved_quantity = self._number(quantity, "quantity")
        if resolved_quantity < 0:
            raise ValueError("quantity não pode ser negativa.")

        resolved_side = self._side(side)
        difference = (
            executed - expected
            if resolved_side is OrderSide.BUY
            else expected - executed
        )
        return round(difference * resolved_quantity, 8)

    def analyze(
        self,
        expected_price: Any,
        executed_price: Any,
        quantity: Any = 0.0,
        side: OrderSide | str = OrderSide.BUY,
    ) -> dict[str, Any]:
        expected = self._number(expected_price, "expected_price")
        executed = self._number(executed_price, "executed_price")
        resolved_quantity = self._number(quantity, "quantity")
        resolved_side = self._side(side)
        rate = self.rate(expected, executed, resolved_side)
        return {
            "expected_price": expected,
            "executed_price": executed,
            "quantity": resolved_quantity,
            "side": resolved_side.value,
            "rate": rate,
            "percentage": round(rate * 100, 8),
            "amount": self.amount(
                expected,
                executed,
                resolved_quantity,
                resolved_side,
            ),
            "favorable": rate < 0,
            "neutral": rate == 0,
        }


slippage_engine = SlippageEngine()
