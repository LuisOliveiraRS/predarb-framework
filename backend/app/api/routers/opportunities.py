from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.engine.arbitrage_engine import (
    arbitrage_engine,
)


router = APIRouter(
    prefix="/opportunities",
    tags=["Opportunities"],
)


@router.get("/")
async def opportunities() -> list[Any]:
    """
    Retorna oportunidades aprovadas pelo
    Pipeline oficial de análise.

    A consulta não publica eventos para evitar
    duplicidade no Dashboard.
    """

    return arbitrage_engine.scan(
        publish=False,
    )


@router.get("/pipeline")
async def pipeline_status() -> dict[str, Any]:
    """
    Retorna a configuração e as métricas
    dos Pipelines.
    """

    return arbitrage_engine.pipeline_status()