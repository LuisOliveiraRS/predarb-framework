from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.dashboard.router_cache import router_cache
from app.dashboard.router_dashboard import router_dashboard
from app.dashboard.router_service import router_service


router = APIRouter(
    prefix="/router",
    tags=["AI Router Dashboard"],
)


@router.get("/summary")
def summary(
    refresh: bool = Query(True),
) -> dict[str, Any]:
    return router_dashboard.summary(refresh=refresh)


@router.get("/venues")
def venues(
    refresh: bool = Query(True),
) -> dict[str, Any]:
    return router_dashboard.venue_table(refresh=refresh)


@router.get("/snapshot")
def snapshot(
    refresh: bool = Query(True),
) -> dict[str, Any]:
    return router_dashboard.snapshot(refresh=refresh)


@router.get("/cache")
def cache() -> dict[str, Any]:
    return router_cache.get()


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "dashboard": router_dashboard.status(),
        "service": router_service.status(),
    }
