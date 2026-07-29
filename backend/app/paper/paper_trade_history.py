from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any, Iterable, Mapping

from app.paper.paper_models import PaperTrade


class PaperTradeHistory:
    def __init__(self) -> None:
        self._lock = RLock()
        self.history: list[PaperTrade] = []

    def add(self, trade: PaperTrade | Mapping[str, Any]) -> PaperTrade:
        resolved = trade if isinstance(trade, PaperTrade) else PaperTrade.from_dict(trade)
        with self._lock:
            if resolved.order_id and self.contains_order(resolved.order_id):
                raise ValueError(f"Ordem paper já registrada: {resolved.order_id}")
            self.history.append(deepcopy(resolved))
        return deepcopy(resolved)

    def contains_order(self, order_id: str) -> bool:
        normalized = str(order_id or "").strip()
        if not normalized:
            return False
        with self._lock:
            return any(item.order_id == normalized for item in self.history)

    def all(self) -> list[PaperTrade]:
        with self._lock:
            return deepcopy(self.history)

    def dictionaries(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.all()]

    def count(self) -> int:
        with self._lock:
            return len(self.history)

    def clear(self) -> None:
        with self._lock:
            self.history.clear()

    def restore(self, items: Iterable[Mapping[str, Any]]) -> None:
        restored = [PaperTrade.from_dict(item) for item in items]
        order_ids = [item.order_id for item in restored if item.order_id]
        if len(order_ids) != len(set(order_ids)):
            raise ValueError("Histórico paper contém order_id duplicado.")
        with self._lock:
            self.history = restored

    def snapshot(self) -> list[dict[str, Any]]:
        return self.dictionaries()


paper_trade_history = PaperTradeHistory()
