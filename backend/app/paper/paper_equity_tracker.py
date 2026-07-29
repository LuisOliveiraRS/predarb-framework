from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite
from threading import RLock
from typing import Any

from app.paper.paper_models import text, utc_iso


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return default
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        return default
    return resolved if isfinite(resolved) else default


@dataclass(slots=True)
class PaperEquityPoint:
    timestamp: str = field(default_factory=utc_iso)
    sequence: int = 0
    reason: str = "SNAPSHOT"
    equity: float = 0.0
    cash: float = 0.0
    market_value: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_pnl: float = 0.0
    return_rate: float = 0.0
    open_positions: int = 0
    trade_count: int = 0

    def __post_init__(self) -> None:
        self.timestamp = text(self.timestamp) or utc_iso()
        self.sequence = max(0, int(self.sequence))
        self.reason = text(self.reason, "SNAPSHOT").upper()
        for name in (
            "equity",
            "cash",
            "market_value",
            "realized_pnl",
            "unrealized_pnl",
            "total_pnl",
            "return_rate",
        ):
            setattr(self, name, round(_number(getattr(self, name)), 8))
        self.open_positions = max(0, int(self.open_positions))
        self.trade_count = max(0, int(self.trade_count))

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "reason": self.reason,
            "equity": self.equity,
            "cash": self.cash,
            "market_value": self.market_value,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "return_rate": self.return_rate,
            "open_positions": self.open_positions,
            "trade_count": self.trade_count,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PaperEquityPoint":
        allowed = {
            "timestamp",
            "sequence",
            "reason",
            "equity",
            "cash",
            "market_value",
            "realized_pnl",
            "unrealized_pnl",
            "total_pnl",
            "return_rate",
            "open_positions",
            "trade_count",
        }
        return cls(**{key: value for key, value in data.items() if key in allowed})


class PaperEquityTracker:
    """Histórico limitado e thread-safe da curva de equity da conta paper."""

    def __init__(self, *, max_points: int = 2_000) -> None:
        if int(max_points) <= 1:
            raise ValueError("max_points deve ser maior que um.")
        self.max_points = int(max_points)
        self._lock = RLock()
        self._points: deque[PaperEquityPoint] = deque(maxlen=self.max_points)
        self._sequence = 0

    def record(
        self,
        snapshot: Mapping[str, Any],
        *,
        reason: str = "SNAPSHOT",
        timestamp: str | None = None,
        force: bool = False,
    ) -> PaperEquityPoint:
        wallet = snapshot.get("wallet") if isinstance(snapshot, Mapping) else {}
        wallet = wallet if isinstance(wallet, Mapping) else {}
        data = {
            "timestamp": timestamp or snapshot.get("updated_at") or utc_iso(),
            "sequence": 0,
            "reason": reason,
            "equity": snapshot.get("equity", 0.0),
            "cash": wallet.get("balance", wallet.get("cash", 0.0)),
            "market_value": snapshot.get("market_value", 0.0),
            "realized_pnl": snapshot.get("realized_pnl", 0.0),
            "unrealized_pnl": snapshot.get("unrealized_pnl", 0.0),
            "total_pnl": snapshot.get("total_pnl", 0.0),
            "return_rate": snapshot.get("return_rate", 0.0),
            "open_positions": snapshot.get("open_positions", 0),
            "trade_count": snapshot.get("trade_count", 0),
        }

        with self._lock:
            if self._points and not force:
                previous = self._points[-1]
                comparable = (
                    round(_number(data["equity"]), 8),
                    round(_number(data["cash"]), 8),
                    round(_number(data["market_value"]), 8),
                    round(_number(data["realized_pnl"]), 8),
                    round(_number(data["unrealized_pnl"]), 8),
                    int(data["open_positions"] or 0),
                    int(data["trade_count"] or 0),
                )
                prior = (
                    previous.equity,
                    previous.cash,
                    previous.market_value,
                    previous.realized_pnl,
                    previous.unrealized_pnl,
                    previous.open_positions,
                    previous.trade_count,
                )
                if comparable == prior and previous.reason == text(reason).upper():
                    return deepcopy(previous)

            self._sequence += 1
            data["sequence"] = self._sequence
            point = PaperEquityPoint(**data)
            self._points.append(point)
            return deepcopy(point)

    def all(self, *, limit: int | None = None) -> list[PaperEquityPoint]:
        with self._lock:
            values = list(self._points)
        if limit is not None:
            values = values[-max(0, int(limit)) :]
        return deepcopy(values)

    def snapshot(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.all(limit=limit)]

    def restore(self, items: Iterable[Mapping[str, Any]]) -> None:
        restored = [PaperEquityPoint.from_dict(item) for item in (items or [])]
        restored.sort(key=lambda item: (item.sequence, item.timestamp))
        with self._lock:
            self._points = deque(restored[-self.max_points :], maxlen=self.max_points)
            self._sequence = max((item.sequence for item in self._points), default=0)

    def clear(self) -> None:
        with self._lock:
            self._points.clear()
            self._sequence = 0

    def analytics(self) -> dict[str, Any]:
        points = self.all()
        if not points:
            return {
                "points": 0,
                "start_equity": 0.0,
                "current_equity": 0.0,
                "peak_equity": 0.0,
                "minimum_equity": 0.0,
                "max_drawdown": 0.0,
                "max_drawdown_rate": 0.0,
                "return_rate": 0.0,
            }

        peak = points[0].equity
        maximum = peak
        minimum = peak
        max_drawdown = 0.0
        max_drawdown_rate = 0.0

        for point in points:
            peak = max(peak, point.equity)
            maximum = max(maximum, point.equity)
            minimum = min(minimum, point.equity)
            drawdown = max(0.0, peak - point.equity)
            drawdown_rate = drawdown / peak if peak > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            if drawdown_rate > max_drawdown_rate:
                max_drawdown_rate = drawdown_rate

        first = points[0]
        last = points[-1]
        return {
            "points": len(points),
            "start_equity": round(first.equity, 8),
            "current_equity": round(last.equity, 8),
            "peak_equity": round(maximum, 8),
            "minimum_equity": round(minimum, 8),
            "max_drawdown": round(max_drawdown, 8),
            "max_drawdown_rate": round(max_drawdown_rate, 8),
            "return_rate": round(last.return_rate, 8),
            "last_reason": last.reason,
            "last_timestamp": last.timestamp,
        }

    def status(self) -> dict[str, Any]:
        analytics = self.analytics()
        return {
            "max_points": self.max_points,
            **analytics,
        }


paper_equity_tracker = PaperEquityTracker()
