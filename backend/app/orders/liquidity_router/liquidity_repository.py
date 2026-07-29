from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Any

from app.orders.liquidity_router.liquidity_level import LiquidityLevel
from app.orders.liquidity_router.liquidity_snapshot import LiquiditySnapshot


class LiquidityRepository:
    """Armazena snapshots reais injetados; não cria liquidez fictícia."""

    def __init__(self, levels: Iterable[Any] | None = None) -> None:
        self._levels: list[LiquidityLevel] = []
        self._lock = RLock()
        if levels is not None:
            self.replace(levels)

    def add(self, level: Any) -> LiquidityLevel:
        resolved = LiquidityLevel.from_value(level)
        with self._lock:
            self._levels.append(resolved)
        return resolved

    def add_many(self, levels: Iterable[Any]) -> list[LiquidityLevel]:
        return [self.add(level) for level in levels]

    def replace(self, levels: Iterable[Any]) -> list[LiquidityLevel]:
        resolved = [LiquidityLevel.from_value(level) for level in levels]
        with self._lock:
            self._levels = resolved
        return list(resolved)

    set_snapshot = replace

    def snapshot(self) -> list[LiquidityLevel]:
        with self._lock:
            return list(self._levels)

    all = snapshot

    def as_snapshot(self) -> LiquiditySnapshot:
        return LiquiditySnapshot(self.snapshot())

    def clear(self) -> None:
        with self._lock:
            self._levels.clear()


liquidity_repository = LiquidityRepository()
