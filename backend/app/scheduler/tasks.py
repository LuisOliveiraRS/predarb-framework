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
from app.core.settings import settings
from app.paper.shadow_execution_runtime import (
    shadow_execution_runtime,
)
from app.real_markets.opportunity_background_collector import (
    real_opportunity_background_collector,
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


async def shadow_runtime_cycle_async(
) -> dict[str, Any]:
    """
    Executa um ?nico ciclo Shadow configurado.

    A fun??o permanece fail-closed:
    - n?o confirma matches;
    - n?o altera a conta Paper;
    - n?o envia ordens;
    - n?o habilita persist?ncia automaticamente.
    """

    if not settings.SHADOW_RUNTIME_ENABLED:
        status = shadow_execution_runtime.status()

        return {
            "status": "DISABLED",
            "phase": "9F",
            "scheduler_connected": (
                status["scheduler_connected"]
            ),
            "persistence_requested": False,
            "paper_account_mutation": False,
            "market_data_only": True,
            "read_only_market_access": True,
            "shadow_execution": True,
            "simulation_only": True,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
            "automatic_execution_authorized": False,
            "order_submission_available": False,
        }

    return await shadow_execution_runtime.run_cycle(
        force_refresh=(
            settings.SHADOW_RUNTIME_FORCE_REFRESH
        ),
        persist=(
            settings.SHADOW_RUNTIME_PERSIST_AUDIT
        ),
        max_opportunities=(
            settings
            .SHADOW_RUNTIME_MAX_OPPORTUNITIES_PER_CYCLE
        ),
    )


def shadow_runtime_task() -> dict[str, Any]:
    """
    Adaptador s?ncrono do APScheduler para a Fase 9F.

    O BackgroundScheduler executa este job em
    thread pr?pria; asyncio.run() cria um event
    loop exclusivo para o ciclo Shadow.
    """

    logger.info(
        "Iniciando ciclo do Shadow Runtime."
    )

    try:
        result = asyncio.run(
            shadow_runtime_cycle_async()
        )

        logger.info(
            "Ciclo Shadow conclu?do: status=%s; "
            "simulated=%s; rejected=%s; errors=%s.",
            result.get("status"),
            result.get("simulated", 0),
            result.get("rejected", 0),
            result.get("errors_count", 0),
        )

        return result

    except Exception:
        logger.exception(
            "Falha durante o ciclo do "
            "Shadow Runtime."
        )

        raise


def real_opportunity_background_task(
) -> dict[str, Any]:
    """Executa um ciclo automatico do Radar Real."""

    logger.info(
        "Iniciando coleta automatica do Radar Real."
    )

    result = (
        real_opportunity_background_collector
        .run_task()
    )

    logger.info(
        "Coleta automatica concluida: "
        "status=%s; markets=%s.",
        result.get("status"),
        result.get("last_markets_priced", 0),
    )

    return result


def crypto_scanner_background_task() -> dict[str, Any]:
    """Executa um ciclo do scanner cripto CEX-CEX.

    Somente leitura. O servico e construido sob demanda para que
    a importacao deste modulo nao abra cliente HTTP.
    """

    from app.crypto_arbitrage.services.factory import (
        get_scanner_service,
    )

    logger.info("Iniciando ciclo do scanner cripto.")

    result = get_scanner_service().run_task()

    logger.info(
        "Ciclo do scanner cripto concluido: status=%s; "
        "venues=%s; oportunidades=%s.",
        result.get("last_status"),
        result.get("last_venues_collected", 0),
        result.get("last_opportunities", 0),
    )

    return result
