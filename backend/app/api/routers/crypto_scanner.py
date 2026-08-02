"""API do scanner cripto CEX-CEX.

Todos os endpoints **nascem exigindo autenticação**. É uma
decisão deliberada e vale registrar o porquê: o
`/real-markets/radar/opportunities` da Fase 14 nasceu público, e
quando a proteção foi adicionada na Fase 17 ela virou um no-op em
produção, porque a flag que a ativava estava desligada. Fechar
depois provou ser caro; abrir depois é trivial.

Nenhum endpoint aqui dispara coleta. Todos leem o snapshot em
memória produzido pelo coletor, e o serviço é construído sob
demanda para que importar este módulo não abra cliente HTTP.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response

from app.auth.dependencies import require_dashboard_user
from app.core.settings import settings


router = APIRouter(
    prefix="/crypto/scanner",
    tags=["Crypto Arbitrage Scanner"],
    dependencies=[Depends(require_dashboard_user)],
)


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _disabled_payload() -> dict[str, Any]:
    """Resposta quando o coletor está desligado.

    Devolve 200 com estado explícito em vez de erro: desligado é
    uma configuração válida, não uma falha, e quem consome
    precisa distinguir "não configurado" de "configurado e sem
    oportunidade".
    """

    return {
        "status": "DISABLED",
        "snapshot_available": False,
        "detail": (
            "CRYPTO_SCANNER_ENABLED está desligado. "
            "Nenhum ciclo é executado."
        ),
        "market_data_only": True,
        "read_only": True,
        "execution_authorized": False,
        "financial_execution": False,
        "automatic_execution_authorized": False,
        "order_submission_available": False,
    }


def _service() -> Any:
    from app.crypto_arbitrage.services.factory import (
        get_scanner_service,
    )

    return get_scanner_service()


@router.get("/snapshot")
async def crypto_scanner_snapshot(
    response: Response,
) -> dict[str, Any]:
    """Último relatório de varredura. Não dispara coleta."""

    _no_store(response)

    if not settings.CRYPTO_SCANNER_ENABLED:
        return _disabled_payload()

    return _service().snapshot()


@router.get("/status")
async def crypto_scanner_status(
    response: Response,
) -> dict[str, Any]:
    """Estado do coletor: ciclos, falhas e erros por venue."""

    _no_store(response)

    if not settings.CRYPTO_SCANNER_ENABLED:
        payload = _disabled_payload()
        payload["enabled"] = False
        payload["cycles"] = 0

        return payload

    return _service().status()
