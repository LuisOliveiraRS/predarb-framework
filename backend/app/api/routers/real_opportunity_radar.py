from fastapi import APIRouter
from fastapi import Query

from app.real_markets.opportunity_background_collector import (
    real_opportunity_background_collector,
)
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


def _configuration(
    limit_per_connector: int,
    fee_buffer: float,
    near_threshold: float,
) -> RadarConfiguration:
    return RadarConfiguration(
        limit_per_connector=limit_per_connector,
        fee_buffer=fee_buffer,
        near_threshold=near_threshold,
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
        _configuration(
            limit_per_connector,
            fee_buffer,
            near_threshold,
        ),
        force_refresh=force_refresh,
    )


def _snapshot_configuration(
    limit_per_connector: int | None,
    fee_buffer: float | None,
    near_threshold: float | None,
) -> RadarConfiguration:
    """
    Resolve a configuracao pedida ao snapshot.

    Sem parametros explicitos, o snapshot usa a mesma
    configuracao do coletor automatico. Isso evita que
    uma mudanca de ambiente no coletor produza consulta
    a uma chave de cache que nunca sera preenchida.
    """

    collected = (
        real_opportunity_background_collector
        .configuration()
    )

    return RadarConfiguration(
        limit_per_connector=(
            collected.limit_per_connector
            if limit_per_connector is None
            else limit_per_connector
        ),
        fee_buffer=(
            collected.fee_buffer
            if fee_buffer is None
            else fee_buffer
        ),
        near_threshold=(
            collected.near_threshold
            if near_threshold is None
            else near_threshold
        ),
        concurrency=collected.concurrency,
    )


@router.get("/snapshot")
async def radar_snapshot(
    limit_per_connector: int | None = Query(
        None,
        ge=1,
        le=100,
    ),
    fee_buffer: float | None = Query(
        None,
        ge=0,
        le=0.25,
    ),
    near_threshold: float | None = Query(
        None,
        ge=0,
        le=0.25,
    ),
):
    return real_opportunity_scan_service.latest_snapshot(
        _snapshot_configuration(
            limit_per_connector,
            fee_buffer,
            near_threshold,
        )
    )


@router.get("/collector/status")
async def radar_collector_status():
    return (
        real_opportunity_background_collector
        .status()
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
