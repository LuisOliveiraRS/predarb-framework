from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any


class SlippageExceededError(ValueError):
    """Erro lançado quando o slippage adverso excede o limite configurado."""


class SlippageGuard:
    """Avalia slippage direcional sem modificar a ordem ou aplicar fills."""

    MAX_SLIPPAGE = 0.02

    def __init__(self, *, max_slippage: float = MAX_SLIPPAGE) -> None:
        self.max_slippage = self._rate(max_slippage, "max_slippage", allow_zero=True)
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _number(value: Any, field_name: str, *, positive: bool = False) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{field_name} deve ser numérico.") from exc
        if not isfinite(number):
            raise ValueError(f"{field_name} deve ser finito.")
        if positive and number <= 0:
            raise ValueError(f"{field_name} deve ser maior que zero.")
        return number

    @classmethod
    def _rate(cls, value: Any, field_name: str, *, allow_zero: bool = False) -> float:
        number = cls._number(value, field_name)
        if number < 0 or (number == 0 and not allow_zero):
            comparator = "maior ou igual a zero" if allow_zero else "maior que zero"
            raise ValueError(f"{field_name} deve ser {comparator}.")
        return number

    @staticmethod
    def _side(value: Any) -> str:
        raw = getattr(value, "value", value)
        side = str(raw or "BUY").strip().upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side deve ser BUY ou SELL.")
        return side

    @staticmethod
    def _context_metadata(context: Any) -> dict[str, Any] | None:
        metadata = getattr(context, "metadata", None)
        return metadata if isinstance(metadata, dict) else None

    def evaluate(
        self,
        expected: Any,
        executed: Any,
        *,
        side: Any = "BUY",
        quantity: Any = 0.0,
        max_slippage: Any = None,
        context: Any = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        expected_price = self._number(expected, "expected", positive=True)
        executed_price = self._number(executed, "executed", positive=True)
        resolved_side = self._side(side)
        resolved_quantity = self._number(quantity, "quantity")
        if resolved_quantity < 0:
            raise ValueError("quantity deve ser maior ou igual a zero.")

        limit = (
            self.max_slippage
            if max_slippage is None
            else self._rate(max_slippage, "max_slippage", allow_zero=True)
        )

        raw_rate = (executed_price - expected_price) / expected_price
        adverse_rate = raw_rate if resolved_side == "BUY" else -raw_rate
        favorable = adverse_rate < 0
        adverse_only_rate = max(0.0, adverse_rate)
        price_difference = executed_price - expected_price
        amount = (
            price_difference * resolved_quantity
            if resolved_side == "BUY"
            else -price_difference * resolved_quantity
        )
        within_limit = adverse_only_rate <= limit

        report = {
            "valid": within_limit,
            "within_limit": within_limit,
            "side": resolved_side,
            "expected_price": round(expected_price, 10),
            "executed_price": round(executed_price, 10),
            "price_difference": round(price_difference, 10),
            "signed_rate": round(adverse_rate, 10),
            "adverse_rate": round(adverse_only_rate, 10),
            "absolute_rate": round(abs(raw_rate), 10),
            "percentage": round(adverse_rate * 100, 8),
            "amount": round(amount, 8),
            "quantity": round(resolved_quantity, 8),
            "favorable": favorable,
            "max_slippage": round(limit, 10),
            "reason": "OK" if within_limit else "SLIPPAGE_LIMIT_EXCEEDED",
            "metadata": dict(metadata or {}),
        }

        if context is not None:
            report["order_id"] = str(getattr(context, "order_id", "") or "")
            report["venue"] = str(getattr(context, "venue_name", "") or "")
            context_metadata = self._context_metadata(context)
            if context_metadata is not None:
                context_metadata["slippage"] = dict(report)

        self.last_report = dict(report)
        return report

    def validate(
        self,
        expected: Any,
        executed: Any,
        *,
        side: Any = "BUY",
        quantity: Any = 0.0,
        max_slippage: Any = None,
        context: Any = None,
    ) -> bool:
        return bool(
            self.evaluate(
                expected,
                executed,
                side=side,
                quantity=quantity,
                max_slippage=max_slippage,
                context=context,
            )["within_limit"]
        )

    def enforce(self, expected: Any, executed: Any, **kwargs: Any) -> dict[str, Any]:
        report = self.evaluate(expected, executed, **kwargs)
        if not report["within_limit"]:
            raise SlippageExceededError(
                "Slippage adverso excedeu o limite: "
                f"{report['adverse_rate']:.6f} > {report['max_slippage']:.6f}."
            )
        return report


slippage_guard = SlippageGuard()
