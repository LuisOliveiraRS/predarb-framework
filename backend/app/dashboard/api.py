from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response

from app.dashboard.dashboard_service import dashboard_service
from app.dashboard.manager import dashboard_manager


router = APIRouter(
    prefix="/dashboard/api",
    tags=["Dashboard"],
)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"


@router.get("/snapshot")
async def snapshot(
    response: Response,
    refresh: bool = Query(
        True,
        description="Atualiza as fontes antes de retornar o snapshot.",
    ),
) -> dict[str, Any]:
    _no_store(response)
    return dashboard_service.snapshot(refresh=refresh)


@router.get("/status")
async def status(
    response: Response,
    refresh: bool = Query(
        True,
        description="Mantido para compatibilidade com o endpoint antigo.",
    ),
) -> dict[str, Any]:
    """Alias legado do snapshot completo."""

    _no_store(response)
    return dashboard_service.snapshot(refresh=refresh)


@router.get("/health")
async def health(response: Response) -> dict[str, Any]:
    _no_store(response)
    return {
        "dashboard": dashboard_manager.status(),
        "service": dashboard_service.status(),
    }


@router.get("/metrics")
async def metrics(
    response: Response,
    refresh: bool = Query(True),
) -> dict[str, Any]:
    _no_store(response)

    if refresh:
        dashboard_service.snapshot(refresh=True)

    return dashboard_service.metrics()


@router.get("/cards")
async def cards(
    response: Response,
    refresh: bool = Query(True),
) -> list[dict[str, Any]]:
    _no_store(response)

    if refresh:
        dashboard_service.snapshot(refresh=True)

    return dashboard_service.cards()


@router.get("/events")
async def events(
    response: Response,
    limit: int = Query(
        50,
        ge=1,
        le=300,
    ),
) -> list[dict[str, Any]]:
    _no_store(response)
    return dashboard_service.latest_events(limit)
