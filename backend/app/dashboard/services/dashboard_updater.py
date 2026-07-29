from __future__ import annotations

from typing import Any

from app.dashboard.dashboard_state import DashboardState, dashboard_state


class DashboardUpdater:
    """Atualiza apenas o estado transitório do Dashboard."""

    def __init__(self, state: DashboardState | None = None) -> None:
        self.state = state or dashboard_state

    def market(self, amount: int = 1) -> int:
        return self.state.increment("markets", amount)

    def opportunity(self, amount: int = 1) -> int:
        return self.state.increment("opportunities", amount)

    def order(self, amount: int = 1) -> int:
        return self.state.increment("orders", amount)

    def position(self, amount: int = 1) -> int:
        return self.state.increment("positions", amount)

    def connection(self, total: int) -> int:
        return int(self.state.set("connections", total))

    def portfolio(self, value: Any) -> float:
        return float(self.state.set("portfolio", value))

    def pnl(self, value: Any) -> float:
        return float(self.state.set("pnl", value))

    def ai(self, confidence: Any) -> float:
        return float(self.state.set("ai_confidence", confidence))

    def update(self, values: dict[str, Any]) -> dict[str, Any]:
        return self.state.update(values)

    def reset(self) -> None:
        self.state.reset()


dashboard_updater = DashboardUpdater()
