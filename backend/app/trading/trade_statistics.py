from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from math import isfinite
from typing import Any

from app.trading.trade import Trade
from app.trading.trade_repository import TradeRepository, trade_repository


class TradeStatistics:
    """Agregação financeira e operacional dos trades registrados."""

    def __init__(self, repository: TradeRepository | None = None) -> None:
        self.repository = repository or trade_repository
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _number(value: Any) -> float:
        if value is None or isinstance(value, bool):
            return 0.0
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.0
        return number if isfinite(number) else 0.0

    @staticmethod
    def _as_list(trades: Iterable[Trade] | None, repository: TradeRepository) -> list[Trade]:
        if trades is None:
            return repository.all()
        if isinstance(trades, (str, bytes)):
            raise TypeError("trades deve ser uma coleção de Trade.")
        resolved = list(trades)
        if any(not isinstance(trade, Trade) for trade in resolved):
            raise TypeError("Todos os itens devem ser instâncias de Trade.")
        return resolved

    def summary(self, trades: Iterable[Trade] | None = None) -> dict[str, Any]:
        items = self._as_list(trades, self.repository)
        statuses = Counter(trade.status for trade in items)
        platforms = Counter(trade.platform or "UNKNOWN" for trade in items)
        legs = Counter(trade.leg or "UNSPECIFIED" for trade in items)

        quantities = [max(0.0, self._number(trade.quantity)) for trade in items]
        notionals = [max(0.0, self._number(trade.notional)) for trade in items]
        fees = [max(0.0, self._number(trade.fees)) for trade in items]

        total_quantity = sum(quantities)
        total_notional = sum(notionals)
        average_price = total_notional / total_quantity if total_quantity > 0 else 0.0
        successful = sum(1 for trade in items if trade.success)
        failed = len(items) - successful
        completed = sum(1 for trade in items if trade.completed)
        partial = statuses.get("PARTIALLY_FILLED", 0)
        success_rate = successful / len(items) if items else 0.0

        opportunity_totals: dict[str, dict[str, float | int]] = defaultdict(
            lambda: {"trades": 0, "quantity": 0.0, "notional": 0.0, "fees": 0.0}
        )
        for trade in items:
            if not trade.opportunity_id:
                continue
            group = opportunity_totals[trade.opportunity_id]
            group["trades"] += 1
            group["quantity"] += max(0.0, self._number(trade.quantity))
            group["notional"] += max(0.0, self._number(trade.notional))
            group["fees"] += max(0.0, self._number(trade.fees))

        report = {
            "total_trades": len(items),
            "successful": successful,
            "failed": failed,
            "completed": completed,
            "partial": partial,
            "success_rate": round(success_rate, 6),
            "success_rate_percentage": round(success_rate * 100, 2),
            "total_quantity": round(total_quantity, 8),
            "total_notional": round(total_notional, 8),
            "total_fees": round(sum(fees), 8),
            "average_price": round(average_price, 10),
            "statuses": dict(sorted(statuses.items())),
            "platforms": dict(sorted(platforms.items())),
            "legs": dict(sorted(legs.items())),
            "opportunities": {
                key: {
                    "trades": int(value["trades"]),
                    "quantity": round(float(value["quantity"]), 8),
                    "notional": round(float(value["notional"]), 8),
                    "fees": round(float(value["fees"]), 8),
                }
                for key, value in sorted(opportunity_totals.items())
            },
        }
        self.last_report = report
        return dict(report)

    calculate = summary
    snapshot = summary

    def clear(self) -> None:
        self.repository.clear()
        self.last_report = {}

    reset = clear

    def status(self) -> dict[str, Any]:
        return {
            "repository": self.repository.status(),
            "last_report": dict(self.last_report),
        }


trade_statistics = TradeStatistics()
