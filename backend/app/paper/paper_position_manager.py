from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any, Iterable, Mapping

from app.paper.paper_models import PaperPosition, PaperTrade


class PaperPositionManager:
    def __init__(self) -> None:
        self._lock = RLock()
        self._positions: dict[str, PaperPosition] = {}

    def apply_trade(self, trade: PaperTrade) -> PaperPosition:
        with self._lock:
            position = self._positions.get(trade.position_key)
            if position is None:
                if trade.side == "SELL":
                    raise ValueError("Não existe posição paper para venda.")
                position = PaperPosition(
                    key=trade.position_key,
                    platform=trade.platform,
                    symbol=trade.symbol,
                    market=trade.market,
                    leg=trade.leg,
                    mark_price=trade.price,
                )
                self._positions[position.key] = position

            if trade.side == "BUY":
                position.apply_buy(trade)
            else:
                position.apply_sell(trade)

            return deepcopy(position)

    def get(self, identifier: str) -> PaperPosition | None:
        normalized = str(identifier or "").strip()
        with self._lock:
            position = self._positions.get(normalized)
            if position is None:
                position = next(
                    (item for item in self._positions.values() if item.id == normalized),
                    None,
                )
            return deepcopy(position) if position is not None else None

    def require(self, identifier: str) -> PaperPosition:
        position = self.get(identifier)
        if position is None:
            raise LookupError(f"Posição paper não encontrada: {identifier}")
        return position

    def mark(self, identifier: str, price: Any) -> PaperPosition:
        normalized = str(identifier or "").strip()
        with self._lock:
            position = self._positions.get(normalized)
            if position is None:
                position = next(
                    (item for item in self._positions.values() if item.id == normalized),
                    None,
                )
            if position is None:
                raise LookupError(f"Posição paper não encontrada: {identifier}")
            position.mark(price)
            return deepcopy(position)

    def all(self, *, include_closed: bool = True) -> list[PaperPosition]:
        with self._lock:
            values = list(self._positions.values())
            if not include_closed:
                values = [item for item in values if item.open]
            return deepcopy(values)

    def open_positions(self) -> list[PaperPosition]:
        return self.all(include_closed=False)

    def clear(self) -> None:
        with self._lock:
            self._positions.clear()

    def restore(self, items: Iterable[Mapping[str, Any]]) -> None:
        restored = [PaperPosition.from_dict(item) for item in items]
        keys = [item.key for item in restored]
        ids = [item.id for item in restored]
        if len(keys) != len(set(keys)) or len(ids) != len(set(ids)):
            raise ValueError("Posições paper duplicadas no estado persistido.")
        with self._lock:
            self._positions = {item.key: item for item in restored}

    def snapshot(self, *, include_closed: bool = True) -> list[dict[str, Any]]:
        return [
            item.to_dict()
            for item in self.all(include_closed=include_closed)
        ]

    # Compatibilidade com a implementação antiga.
    def update(self, positions):
        return positions


paper_position_manager = PaperPositionManager()
