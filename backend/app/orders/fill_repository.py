from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from threading import RLock
from typing import Any

from app.orders.fill import Fill


class FillRepository:
    """Repositório thread-safe dos fills efetivamente aplicados pelo OMS."""

    def __init__(self) -> None:
        self._fills: dict[str, Fill] = {}
        self._order_index: dict[str, list[str]] = {}
        self._lock = RLock()

    @staticmethod
    def _resolve_fill(value: Any) -> Fill:
        if isinstance(value, Fill):
            return value

        candidate = getattr(value, "fill", None)
        if isinstance(candidate, Fill):
            return candidate

        if isinstance(value, dict):
            return Fill.from_dict(value)

        raise TypeError("O repositório aceita Fill, FillReport ou dicionário de fill.")

    def add(self, fill: Any, *, replace: bool = False) -> Fill:
        resolved = self._resolve_fill(fill)

        with self._lock:
            if resolved.id in self._fills and not replace:
                return self._fills[resolved.id]

            previous = self._fills.get(resolved.id)
            if previous is not None and previous.order_id != resolved.order_id:
                old_index = self._order_index.get(previous.order_id, [])
                self._order_index[previous.order_id] = [
                    fill_id for fill_id in old_index if fill_id != resolved.id
                ]

            self._fills[resolved.id] = resolved
            order_ids = self._order_index.setdefault(resolved.order_id, [])
            if resolved.id not in order_ids:
                order_ids.append(resolved.id)

        return resolved

    save = add

    def add_many(self, fills: Iterable[Any], *, replace: bool = False) -> list[Fill]:
        if isinstance(fills, (str, bytes, dict)):
            raise TypeError("fills deve ser uma coleção de fills.")
        return [self.add(fill, replace=replace) for fill in fills]

    save_all = add_many

    def get(self, fill_id: Any, default: Any = None) -> Fill | Any:
        normalized = str(fill_id or "").strip()
        if not normalized:
            return default
        with self._lock:
            return self._fills.get(normalized, default)

    def require(self, fill_id: Any) -> Fill:
        fill = self.get(fill_id)
        if fill is None:
            raise LookupError(f"Fill não encontrado: {fill_id!r}.")
        return fill

    def all(self) -> list[Fill]:
        with self._lock:
            return list(self._fills.values())

    list = all

    @property
    def reports(self) -> list[Fill]:
        """Alias legado; o repositório agora armazena registros Fill."""
        return self.all()

    def by_order(self, order_id: Any) -> list[Fill]:
        normalized = str(order_id or "").strip()
        if not normalized:
            return []
        with self._lock:
            ids = list(self._order_index.get(normalized, []))
            return [self._fills[fill_id] for fill_id in ids if fill_id in self._fills]

    def latest(self, order_id: Any | None = None) -> Fill | None:
        fills = self.by_order(order_id) if order_id is not None else self.all()
        return fills[-1] if fills else None

    def count(self, order_id: Any | None = None) -> int:
        return len(self.by_order(order_id)) if order_id is not None else len(self.all())

    def total_quantity(self, order_id: Any | None = None) -> float:
        fills = self.by_order(order_id) if order_id is not None else self.all()
        return round(sum(fill.quantity for fill in fills), 8)

    def total_fees(self, order_id: Any | None = None) -> float:
        fills = self.by_order(order_id) if order_id is not None else self.all()
        return round(sum(fill.fee for fill in fills), 8)

    def remove(self, fill_id: Any) -> Fill | None:
        normalized = str(fill_id or "").strip()
        if not normalized:
            return None

        with self._lock:
            fill = self._fills.pop(normalized, None)
            if fill is None:
                return None
            ids = self._order_index.get(fill.order_id, [])
            self._order_index[fill.order_id] = [item for item in ids if item != normalized]
            if not self._order_index[fill.order_id]:
                self._order_index.pop(fill.order_id, None)
            return fill

    def clear(self, order_id: Any | None = None) -> None:
        with self._lock:
            if order_id is None:
                self._fills.clear()
                self._order_index.clear()
                return

            normalized = str(order_id or "").strip()
            for fill_id in self._order_index.pop(normalized, []):
                self._fills.pop(fill_id, None)


fill_repository = FillRepository()
