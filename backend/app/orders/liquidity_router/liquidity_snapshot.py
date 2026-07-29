from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime, timezone
from typing import Any

from app.orders.liquidity_router.liquidity_level import LiquidityLevel


class LiquiditySnapshot:
    def __init__(self, levels: Iterable[Any] | None = None) -> None:
        self.levels: list[LiquidityLevel] = []
        self.created_at = datetime.now(timezone.utc)
        if levels is not None:
            self.add_many(levels)

    def add(self, level: Any) -> LiquidityLevel:
        resolved = LiquidityLevel.from_value(level)
        self.levels.append(resolved)
        return resolved

    def add_many(self, levels: Iterable[Any]) -> list[LiquidityLevel]:
        return [self.add(level) for level in levels]

    def all(self) -> list[LiquidityLevel]:
        return list(self.levels)

    def by_exchange(self, exchange: Any) -> list[LiquidityLevel]:
        normalized = str(exchange or "").strip().casefold()
        return [level for level in self.levels if level.exchange.casefold() == normalized]

    def total_liquidity(self) -> float:
        return round(sum(level.quantity for level in self.levels if level.available), 8)

    def to_dict(self) -> dict[str, Any]:
        return {
            "levels": [level.to_dict() for level in self.levels],
            "total_liquidity": self.total_liquidity(),
            "created_at": self.created_at.isoformat(),
        }

    def __iter__(self) -> Iterator[LiquidityLevel]:
        return iter(self.all())

    def __len__(self) -> int:
        return len(self.levels)
