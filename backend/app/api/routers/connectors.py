from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.connectors.manager.connector_manager import (
    connector_manager,
)
from app.repositories.market_repository import (
    market_repository,
)
from app.scheduler.tasks import (
    update_markets_async,
)
from app.services.market_listener import (
    market_listener,
)


router = APIRouter(
    prefix="/connectors",
    tags=["Connectors"],
)


@router.get("/")
async def connectors() -> list[str]:
    """
    Lista os conectores registrados.

    Preserva o formato original do endpoint.
    """

    return connector_manager.names()


@router.get("/status")
async def connectors_status() -> dict[str, Any]:
    """
    Retorna o último estado conhecido,
    sem executar requisições externas.
    """

    return {
        "connectors": (
            connector_manager.statuses()
        ),
        "repository": (
            market_repository.status()
        ),
        "listener": (
            market_listener.status()
        ),
    }


@router.get("/health")
async def health() -> dict[str, Any]:
    """
    Executa o health check real de todos
    os conectores.
    """

    statuses = await connector_manager.health()

    online = sum(
        1
        for status in statuses.values()
        if status.get("connected")
    )

    errors = sum(
        1
        for status in statuses.values()
        if status.get("error")
    )

    return {
        "status": (
            "healthy"
            if online == len(statuses)
            else "degraded"
        ),
        "registered": len(statuses),
        "online": online,
        "errors": errors,
        "connectors": statuses,
    }


@router.post("/refresh")
async def refresh_markets() -> dict[str, Any]:
    """
    Solicita uma atualização imediata
    dos mercados.
    """

    try:
        markets = await update_markets_async()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível atualizar "
                f"os mercados: {exc}"
            ),
        ) from exc

    return {
        "status": "completed",
        "markets": len(markets),
        "repository": (
            market_repository.status()
        ),
        "connectors": (
            connector_manager.statuses()
        ),
    }


@router.get("/{connector_name}")
async def connector_status(
    connector_name: str,
) -> dict[str, Any]:
    """
    Retorna o estado conhecido de um
    conector específico.
    """

    if not connector_manager.exists(
        connector_name
    ):
        raise HTTPException(
            status_code=404,
            detail=(
                "Conector não registrado: "
                f"{connector_name}"
            ),
        )

    return connector_manager.status(
        connector_name
    )