from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.connectors.manager.connector_manager import (
    connector_manager,
)
from app.events.event import Event
from app.events.event_bus import event_bus
from app.repositories.market_repository import (
    market_repository,
)


logger = logging.getLogger(__name__)


MARKET_UPDATED_EVENT = "market.updated"


def _synchronization_status(
    connector_statuses: dict[str, dict[str, Any]],
) -> str:
    """
    Classifica a sincronização usando o estado
    conhecido dos conectores.
    """

    if not connector_statuses:
        return "empty"

    errors = [
        status
        for status in connector_statuses.values()
        if status.get("error")
    ]

    if not errors:
        return "success"

    if len(errors) == len(
        connector_statuses
    ):
        return "error"

    return "partial"


async def update_markets_async() -> list[Any]:
    """
    Atualiza os mercados e publica o evento
    market.updated.

    O ConnectorManager é o único componente que
    persiste dados no MarketRepository.
    """

    markets = await connector_manager.update_markets(
        persist=True,
        raise_on_error=False,
    )

    connector_statuses = (
        connector_manager.statuses()
    )

    status = _synchronization_status(
        connector_statuses,
    )

    event_bus.publish(
        Event(
            name=MARKET_UPDATED_EVENT,
            payload={
                "status": status,
                "markets": markets,
                "count": len(markets),
                "repository_count": (
                    market_repository.count()
                ),
                "connectors": connector_statuses,
            },
        )
    )

    return markets


def market_update_task() -> dict[str, Any]:
    """
    Job síncrono executado pelo APScheduler.

    Como o BackgroundScheduler executa o job
    em uma thread própria, asyncio.run() cria
    um event loop exclusivo para esta execução.
    """

    logger.info(
        "Iniciando sincronização de mercados."
    )

    try:
        markets = asyncio.run(
            update_markets_async()
        )

        connector_statuses = (
            connector_manager.statuses()
        )

        status = _synchronization_status(
            connector_statuses,
        )

        result = {
            "status": status,
            "markets": len(markets),
            "repository": (
                market_repository.count()
            ),
            "connectors": connector_statuses,
        }

        logger.info(
            "Sincronização concluída: "
            "%s mercados; status=%s.",
            len(markets),
            status,
        )

        return result

    except Exception:
        logger.exception(
            "Falha durante a sincronização "
            "de mercados."
        )

        raise