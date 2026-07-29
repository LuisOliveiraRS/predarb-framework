from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from typing import Any

from app.dashboard.dashboard_service import DashboardService, dashboard_service
from app.dashboard.services.dashboard_updater import DashboardUpdater, dashboard_updater


class DashboardEventListener:
    """Traduz eventos do domínio em atualizações do painel.

    Não há qualquer atualização no momento da importação do módulo.
    """

    def __init__(
        self,
        *,
        service: DashboardService | None = None,
        updater: DashboardUpdater | None = None,
        realtime_publisher: Any = None,
    ) -> None:
        self.service = service or dashboard_service
        self.updater = updater or dashboard_updater
        self.realtime_publisher = realtime_publisher
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _payload(event: Any) -> Any:
        if isinstance(event, Mapping):
            return event.get("payload", event)
        return getattr(event, "payload", event)

    @staticmethod
    def _question(opportunity: Any) -> str:
        if isinstance(opportunity, Mapping):
            value = opportunity.get("question")
        else:
            value = getattr(opportunity, "question", None)
        return str(value or "Oportunidade sem descrição")

    def _publisher(self) -> Any:
        if self.realtime_publisher is not None:
            return self.realtime_publisher

        try:
            from app.realtime.publisher import publisher

            return publisher
        except Exception:
            return None

    @staticmethod
    def _schedule(result: Any) -> None:
        if not inspect.isawaitable(result):
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        loop.create_task(result)

    def opportunity_found(self, event: Any) -> dict[str, Any]:
        opportunity = self._payload(event)
        total = self.updater.opportunity()
        stored_event = self.service.add_event(
            f"Opportunity: {self._question(opportunity)}",
            event_type="opportunity",
            payload=opportunity,
        )

        published = False
        publisher = self._publisher()
        method = getattr(publisher, "publish_opportunity", None)

        if callable(method):
            try:
                result = method(opportunity)
                self._schedule(result)
                published = True
            except Exception:
                published = False

        self.last_report = {
            "event": "OpportunityFound",
            "opportunities": total,
            "realtime_published": published,
            "dashboard_event_id": stored_event["id"],
        }
        return dict(self.last_report)


dashboard_event_listener = DashboardEventListener()
