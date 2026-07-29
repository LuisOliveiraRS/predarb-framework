from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Any

from app.trading.trade import Trade


class TradeRepository:
    """Repositório em memória, thread-safe, dos trades normalizados."""

    def __init__(self) -> None:
        self._trades: dict[str, Trade] = {}
        self._lock = RLock()

    @property
    def trades(self) -> dict[str, Trade]:
        """Cópia legada do armazenamento interno."""
        with self._lock:
            return dict(self._trades)

    def add(self, trade: Trade, *, replace: bool = False) -> Trade:
        if not isinstance(trade, Trade):
            raise TypeError("trade deve ser uma instância de Trade.")
        if not trade.id:
            raise ValueError("trade.id não pode ser vazio.")

        with self._lock:
            existing = self._trades.get(trade.id)
            if existing is not None and not replace:
                return existing
            self._trades[trade.id] = trade
        return trade

    save = add

    def add_many(self, trades: Iterable[Trade], *, replace: bool = False) -> list[Trade]:
        if isinstance(trades, (str, bytes)):
            raise TypeError("trades deve ser uma coleção de Trade.")
        return [self.add(trade, replace=replace) for trade in trades]

    def get(self, trade_id: str) -> Trade | None:
        with self._lock:
            return self._trades.get(str(trade_id))

    def require(self, trade_id: str) -> Trade:
        trade = self.get(trade_id)
        if trade is None:
            raise KeyError(f"Trade não encontrado: {trade_id!r}.")
        return trade

    def all(self) -> list[Trade]:
        with self._lock:
            return list(self._trades.values())

    list = all

    def by_order(self, order_id: str) -> list[Trade]:
        target = str(order_id)
        return [trade for trade in self.all() if trade.order_id == target]

    def by_platform(self, platform: str) -> list[Trade]:
        target = str(platform).strip().lower()
        return [
            trade
            for trade in self.all()
            if trade.platform.strip().lower() == target
        ]

    def successful(self) -> list[Trade]:
        return [trade for trade in self.all() if trade.success]

    def failed(self) -> list[Trade]:
        return [trade for trade in self.all() if not trade.success]

    def remove(self, trade_id: str) -> Trade | None:
        with self._lock:
            return self._trades.pop(str(trade_id), None)

    delete = remove

    def clear(self) -> None:
        with self._lock:
            self._trades.clear()

    def count(self) -> int:
        with self._lock:
            return len(self._trades)

    def status(self) -> dict[str, Any]:
        trades = self.all()
        successful = sum(1 for trade in trades if trade.success)
        return {
            "total": len(trades),
            "successful": successful,
            "failed": len(trades) - successful,
            "platforms": sorted({trade.platform for trade in trades if trade.platform}),
        }


trade_repository = TradeRepository()
