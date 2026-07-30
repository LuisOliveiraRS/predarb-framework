from fastapi import APIRouter, Query

from app.real_markets.opportunity_radar import (
    RadarConfiguration,
    real_opportunity_radar,
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
):
    return await real_opportunity_radar.scan(
        RadarConfiguration(
            limit_per_connector=limit_per_connector,
            fee_buffer=fee_buffer,
            near_threshold=near_threshold,
        )
    )
