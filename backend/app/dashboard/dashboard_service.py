from __future__ import annotations

from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from threading import RLock
from typing import Any
from uuid import uuid4

from app.dashboard.builder import DashboardBuilder, dashboard_builder
from app.dashboard.cache import DashboardCache, dashboard_cache
from app.dashboard.dashboard_state import DashboardState, dashboard_state


Provider = Callable[[], Any]


def _empty_list() -> list[Any]:
    return []


def _empty_dict() -> dict[str, Any]:
    return {}


def _default_markets() -> list[Any]:
    from app.repositories.market_repository import market_repository

    return market_repository.all()


def _default_orders() -> list[Any]:
    from app.orders.order_repository import order_repository

    return order_repository.all()


def _default_positions() -> list[Any]:
    from app.positions.position_manager import position_manager

    return position_manager.all()


def _default_trades() -> list[Any]:
    from app.trading.trade_repository import trade_repository

    return trade_repository.all()


def _default_portfolio() -> dict[str, Any]:
    """Resumo financeiro alinhado ? conta Paper oficial."""

    try:
        from app.paper.paper_runtime import paper_account_runtime

        if paper_account_runtime.enabled:
            account = paper_account_runtime.account.snapshot(
                include_trades=False
            )
            wallet = account.get("wallet", {}) or {}

            total = float(
                account.get(
                    "equity",
                    wallet.get("balance", 0.0),
                )
                or 0.0
            )
            available = float(
                wallet.get(
                    "available",
                    wallet.get("cash", 0.0),
                )
                or 0.0
            )
            locked = float(wallet.get("locked", 0.0) or 0.0)

            return {
                "total": total,
                "equity": total,
                "available": available,
                "locked": locked,
                "utilization": (
                    locked / total
                    if total > 0
                    else 0.0
                ),
                "source": "paper_account",
            }
    except Exception:
        pass

    try:
        from app.portfolio.bankroll import bankroll

        return {
            "total": float(
                getattr(bankroll, "total", 0.0)
                or 0.0
            ),
            "available": float(
                getattr(bankroll, "available", 0.0)
                or 0.0
            ),
            "locked": float(
                getattr(bankroll, "locked", 0.0)
                or 0.0
            ),
            "utilization": float(
                getattr(bankroll, "utilization", 0.0)
                or 0.0
            ),
            "source": "bankroll",
        }
    except Exception:
        return {}


def _default_statistics() -> dict[str, Any]:
    try:
        from app.trading.trade_statistics import trade_statistics

        return trade_statistics.summary()
    except Exception:
        return {}




def _default_paper() -> dict[str, Any]:
    try:
        from app.paper.paper_runtime import paper_account_runtime

        runtime = paper_account_runtime.status()
        if not paper_account_runtime.enabled:
            return {
                "status": "DISABLED",
                "enabled": False,
                "execution_authorized": False,
                "live_execution": False,
                "runtime": runtime,
            }
        account = paper_account_runtime.account.snapshot(include_trades=True)
        return {
            **account,
            "enabled": True,
            "runtime": runtime,
        }
    except Exception:
        return {}

def _default_router() -> dict[str, Any]:
    try:
        from app.dashboard.router_dashboard import router_dashboard

        return router_dashboard.snapshot(refresh=True)
    except Exception:
        return {}


@dataclass(slots=True)
class DashboardSources:
    """Adaptadores injetáveis usados pelo Dashboard.

    A camada Dashboard conhece apenas funções provedoras. Os singletons do
    domínio ficam encapsulados nestes adaptadores e podem ser substituídos em
    testes ou em uma futura implementação persistente.
    """

    markets: Provider = _default_markets
    orders: Provider = _default_orders
    positions: Provider = _default_positions
    trades: Provider = _default_trades
    portfolio: Provider = _default_portfolio
    statistics: Provider = _default_statistics
    router: Provider = _default_router
    paper: Provider = _default_paper
    notifications: Provider = _empty_list


class DashboardService:
    """Serviço oficial de snapshots e eventos do Dashboard."""

    def __init__(
        self,
        *,
        state: DashboardState | None = None,
        cache: DashboardCache | None = None,
        builder: DashboardBuilder | None = None,
        sources: DashboardSources | None = None,
        event_limit: int = 300,
    ) -> None:
        if event_limit <= 0:
            raise ValueError("event_limit deve ser maior que zero.")

        self.state = state or dashboard_state
        self.cache = cache or dashboard_cache
        self.builder = builder or dashboard_builder
        self.sources = sources or DashboardSources()
        self._events: deque[dict[str, Any]] = deque(maxlen=int(event_limit))
        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        if value is None or isinstance(value, bool):
            return default
        try:
            number = float(value)
        except (TypeError, ValueError):
            return default
        return number if isfinite(number) else default

    @staticmethod
    def _count(value: Any) -> int:
        if value is None:
            return 0
        if isinstance(value, Mapping):
            return len(value)
        try:
            return len(value)
        except TypeError:
            return 0

    @classmethod
    def _portfolio_value(cls, portfolio: Any, fallback: float) -> float:
        if isinstance(portfolio, Mapping):
            for key in ("total", "equity", "value", "available", "bankroll"):
                if key in portfolio:
                    return cls._number(portfolio.get(key), fallback)
            return fallback
        return cls._number(portfolio, fallback)

    @classmethod
    def _router_confidence(cls, router: Any, fallback: float) -> float:
        if not isinstance(router, Mapping):
            return fallback

        summary = router.get("summary", router)
        if not isinstance(summary, Mapping):
            return fallback

        for key in ("confidence", "average_confidence", "ai_confidence"):
            if key in summary:
                return cls._number(summary.get(key), fallback)
        return fallback

    @classmethod
    def _pnl_value(cls, statistics: Any, positions: Any, fallback: float) -> float:
        if isinstance(statistics, Mapping):
            for key in (
                "pnl",
                "total_pnl",
                "realized_pnl",
                "total_profit",
                "total_realized_profit",
            ):
                if key in statistics:
                    return cls._number(statistics.get(key), fallback)

        total = 0.0
        found = False
        for position in positions or []:
            value = (
                position.get("pnl")
                if isinstance(position, Mapping)
                else getattr(position, "pnl", None)
            )
            if value is None:
                continue
            total += cls._number(value)
            found = True
        return total if found else fallback

    @staticmethod
    def _provider(name: str, provider: Provider, default: Any, errors: dict[str, str]) -> Any:
        try:
            value = provider()
            return default if value is None else value
        except Exception as exc:
            errors[name] = str(exc)
            return default

    def add_event(
        self,
        text: str,
        *,
        event_type: str = "info",
        payload: Any = None,
    ) -> dict[str, Any]:
        normalized = str(text or "").strip()
        if not normalized:
            raise ValueError("text não pode ser vazio.")

        created_at = datetime.now(timezone.utc)
        event = {
            "id": str(uuid4()),
            "type": str(event_type or "info").strip().lower(),
            "text": normalized,
            "time": created_at.astimezone().strftime("%H:%M:%S"),
            "created_at": created_at.isoformat(),
            "payload": self.builder.serialize(payload),
        }

        with self._lock:
            self._events.appendleft(event)

        return dict(event)

    def latest_events(self, limit: int | None = None) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._events)

        if limit is None:
            return [dict(event) for event in events]
        return [dict(event) for event in events[: max(0, int(limit))]]

    events = latest_events

    def clear_events(self) -> None:
        with self._lock:
            self._events.clear()

    def collect(self) -> dict[str, Any]:
        errors: dict[str, str] = {}
        state = self.state.snapshot()

        markets = self._provider("markets", self.sources.markets, [], errors)
        orders = self._provider("orders", self.sources.orders, [], errors)
        positions = self._provider("positions", self.sources.positions, [], errors)
        trades = self._provider("trades", self.sources.trades, [], errors)
        portfolio = self._provider("portfolio", self.sources.portfolio, {}, errors)
        statistics = self._provider("statistics", self.sources.statistics, {}, errors)
        router = self._provider("router", self.sources.router, {}, errors)
        paper = self._provider("paper", self.sources.paper, {}, errors)
        notifications = self._provider(
            "notifications", self.sources.notifications, [], errors
        )

        market_count = self._count(markets)
        order_count = self._count(orders)
        position_count = self._count(positions)

        self.state.update(
            {
                "markets": market_count,
                "orders": order_count,
                "positions": position_count,
            }
        )

        portfolio_value = self._portfolio_value(
            portfolio,
            self._number(state.get("portfolio"), 10_000.0),
        )
        pnl_value = self._pnl_value(
            statistics,
            positions,
            self._number(state.get("pnl"), 0.0),
        )

        ai_confidence = self._router_confidence(
            router,
            self._number(state.get("ai_confidence"), 0.0),
        )

        self.state.update(
            {
                "portfolio": portfolio_value,
                "pnl": pnl_value,
                "ai_confidence": ai_confidence,
            }
        )
        state = self.state.snapshot()

        collected = {
            "status": "DEGRADED" if errors else "ONLINE",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "state": state,
            "markets": market_count,
            "opportunities": int(state["opportunities"]),
            "orders": order_count,
            "positions": position_count,
            "connections": int(state["connections"]),
            "portfolio": portfolio_value,
            "pnl": pnl_value,
            "ai_confidence": float(state["ai_confidence"]),
            "events": self.latest_events(),
            "data": {
                "markets": markets,
                "orders": orders,
                "positions": positions,
                "trades": trades,
                "portfolio": portfolio,
                "router": router,
                "paper": paper,
                "notifications": notifications,
            },
            "statistics": statistics,
            "diagnostics": {
                "errors": errors,
                "sources": {
                    "markets": market_count,
                    "orders": order_count,
                    "positions": position_count,
                    "trades": self._count(trades),
                    "paper_positions": self._count(paper.get("positions", [])) if isinstance(paper, Mapping) else 0,
                    "paper_trades": self._count(paper.get("trades", [])) if isinstance(paper, Mapping) else 0,
                },
            },
        }

        self.last_report = {
            "status": collected["status"],
            "updated_at": collected["updated_at"],
            "errors": dict(errors),
            "counts": dict(collected["diagnostics"]["sources"]),
        }
        return collected

    def snapshot(self, *, refresh: bool = True) -> dict[str, Any]:
        if not refresh:
            cached = self.cache.get("snapshot")
            if isinstance(cached, dict):
                return cached

        snapshot = self.builder.build(self.collect())
        self.cache.set("snapshot", snapshot)
        return snapshot

    load = snapshot

    def metrics(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            "markets": snapshot["markets"],
            "opportunities": snapshot["opportunities"],
            "orders": snapshot["orders"],
            "positions": snapshot["positions"],
            "connections": snapshot["connections"],
            "portfolio": snapshot["portfolio"],
            "pnl": snapshot["pnl"],
            "ai": snapshot["ai_confidence"],
            "ai_confidence": snapshot["ai_confidence"],
        }

    def cards(self) -> list[dict[str, Any]]:
        return list(self.snapshot()["cards"])

    def orders(self) -> list[Any]:
        return list(self.snapshot()["data"]["orders"])

    def positions(self) -> list[Any]:
        return list(self.snapshot()["data"]["positions"])

    def portfolio(self) -> Any:
        return self.snapshot()["data"]["portfolio"]

    def statistics(self) -> dict[str, Any]:
        return dict(self.snapshot()["statistics"])

    def paper(self) -> dict[str, Any]:
        value = self.snapshot()["data"].get("paper", {})
        return dict(value) if isinstance(value, Mapping) else {}

    def notifications(self) -> list[Any]:
        return list(self.snapshot()["data"]["notifications"])

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state.snapshot(),
            "cache": self.cache.status(),
            "events": len(self.latest_events()),
            "last_report": dict(self.last_report),
        }


dashboard_service = DashboardService()
