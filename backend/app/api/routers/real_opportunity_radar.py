from fastapi import APIRouter, Query

from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)
from app.real_markets.opportunity_scan_service import (
    real_opportunity_scan_service,
)


router = APIRouter(
    prefix="/real-markets/radar",
    tags=["Real Opportunity Radar"],
)


@router.get("/opportunities")
async def radar_opportunities(
    limit_per_connector: int = Query(
        40,
        ge=1,
        le=100,
    ),
    fee_buffer: float = Query(
        0.02,
        ge=0,
        le=0.25,
    ),
    near_threshold: float = Query(
        0.04,
        ge=0,
        le=0.25,
    ),
    force_refresh: bool = Query(False),
):
    return await real_opportunity_scan_service.scan(
        RadarConfiguration(
            limit_per_connector=limit_per_connector,
            fee_buffer=fee_buffer,
            near_threshold=near_threshold,
        ),
        force_refresh=force_refresh,
    )


@router.get("/history")
async def radar_market_history(
    connector_id: str = Query(
        ...,
        min_length=1,
        max_length=120,
    ),
    market_id: str = Query(
        ...,
        min_length=1,
        max_length=500,
    ),
    limit: int = Query(
        60,
        ge=1,
        le=1440,
    ),
):
    return (
        await real_opportunity_scan_service.get_history(
            connector_id,
            market_id,
            limit=limit,
        )
    )
