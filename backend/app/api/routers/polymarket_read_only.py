from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.real_markets.polymarket import (
    PolymarketReadOnlyConnector,
)
from app.real_markets.service import (
    real_market_registry,
)


router = APIRouter(
    prefix="/real-markets/polymarket",
    tags=[
        "real-market-polymarket-read-only"
    ],
)


def _safe_flags() -> dict:
    return {
        "market_data_only": True,
        "read_only": True,
        "authentication_required": False,
        "trading_endpoints_enabled": False,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


def _connector() -> PolymarketReadOnlyConnector:
    try:
        connector = real_market_registry.get(
            "polymarket"
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Conector Polymarket somente leitura "
                "não está habilitado."
            ),
        ) from exc

    if not isinstance(
        connector,
        PolymarketReadOnlyConnector,
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "O identificador polymarket está "
                "associado a um conector incompatível."
            ),
        )

    return connector


@router.get("/configuration")
async def polymarket_configuration():
    connector = _connector()

    return {
        "connector": connector.descriptor(),
        "external_network_required": True,
        "automatic_background_refresh": False,
        "public_endpoints_only": True,
        "supported_sources": [
            "Gamma API",
            "CLOB public orderbook",
        ],
        **_safe_flags(),
    }


@router.get("/health")
async def polymarket_health():
    health = await _connector().health()

    return {
        "health": health.to_dict(),
        **_safe_flags(),
    }


@router.get("/markets")
async def polymarket_markets(
    limit: int = Query(
        default=50,
        ge=1,
        le=250,
    ),
):
    try:
        markets = await _connector().list_markets(
            limit=limit
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return {
        "count": len(markets),
        "markets": [
            item.to_dict()
            for item in markets
        ],
        **_safe_flags(),
    }


@router.get(
    "/markets/{market_id}/snapshot"
)
async def polymarket_snapshot(
    market_id: str,
):
    try:
        snapshot = await _connector().get_snapshot(
            market_id
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return {
        "snapshot": snapshot.to_dict(),
        **_safe_flags(),
    }


@router.get("/architecture")
async def polymarket_architecture():
    connector = _connector()

    return {
        "phase": "9B",
        "name": (
            "Polymarket Read-Only Connector"
        ),
        "connector": connector.descriptor(),
        "data_flow": [
            (
                "Gamma API -> eventos e "
                "metadados de mercados"
            ),
            (
                "CLOB public /book -> "
                "bid, ask, tamanho e último preço"
            ),
            (
                "Normalização -> "
                "NormalizedMarket e MarketSnapshot"
            ),
            (
                "RealMarketDataService -> "
                "cache e API consolidada"
            ),
        ],
        "explicitly_excluded": [
            "private_keys",
            "api_credentials",
            "order_creation",
            "order_cancellation",
            "wallet_signing",
            "balance_movement",
            "background_runtime",
        ],
        **_safe_flags(),
    }
