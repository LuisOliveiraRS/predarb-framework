from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.orders.ai_router.execution_history import ExecutionHistory, execution_history
from app.orders.ai_router.route_optimizer import RouteOptimizer, route_optimizer
from app.orders.ai_router.route_predictor import RoutePredictor
from app.orders.ai_router.router_dataset import RouterDataset
from app.orders.ai_router.router_feature_builder import RouterFeatureBuilder
from app.orders.venue_selection.venue import Venue


class AdaptiveRouter:
    """Fachada do ranking histórico, sem qualquer capacidade de despacho."""

    def __init__(
        self,
        *,
        optimizer: RouteOptimizer | None = None,
        history: ExecutionHistory | None = None,
    ) -> None:
        self.history = history if history is not None else execution_history
        if optimizer is not None:
            self.optimizer = optimizer
        elif history is not None:
            dataset = RouterDataset(history=self.history)
            features = RouterFeatureBuilder(dataset=dataset)
            self.optimizer = RouteOptimizer(
                predictor=RoutePredictor(feature_builder=features)
            )
        else:
            self.optimizer = route_optimizer
        self.last_report: dict[str, Any] = {}

    def rank(
        self,
        venues: Iterable[Any],
        order: Any = None,
        *,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> list[tuple[float, Venue]]:
        ranking = self.optimizer.rank(venues, order, features=features)
        self.last_report = {
            **self.optimizer.last_report,
            "history_reports": self.history.total_reports(),
            "mode": "ADAPTIVE",
            "live_execution": False,
        }
        return ranking

    def route(
        self,
        venues: Iterable[Any],
        order: Any = None,
        *,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> Venue | None:
        ranking = self.rank(venues, order, features=features)
        return ranking[0][1] if ranking else None

    select = route

    def record_execution(self, venue: Any, report: Any | None = None) -> Any:
        return self.history.add(venue, report)

    record = record_execution

    def status(self) -> dict[str, Any]:
        return {
            "mode": "ADAPTIVE",
            "history": self.history.status(),
            "last_report": dict(self.last_report),
            "live_execution": False,
        }


adaptive_router = AdaptiveRouter()
