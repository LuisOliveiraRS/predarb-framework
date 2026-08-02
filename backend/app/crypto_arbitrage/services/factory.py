"""Montagem do coletor cripto a partir das configurações.

Um único lugar traduz `settings` em objetos de domínio. Espalhar
essa leitura pelos serviços faria cada um interpretar a
configuração à sua maneira, e divergências nesse ponto são
silenciosas.

O serviço é construído sob demanda, não na importação do módulo.
Importar não deve abrir cliente HTTP nem ler configuração: os
testes precisam construir variantes, e o boot precisa falhar por
validação de `settings`, não por efeito colateral de import.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from app.core.settings import Settings, settings as default_settings
from app.crypto_arbitrage.connectors.binance import (
    BinanceSpotAdapter,
)
from app.crypto_arbitrage.connectors.bybit import (
    BybitSpotAdapter,
)
from app.crypto_arbitrage.connectors.http_transport import (
    HttpxRestTransport,
)
from app.crypto_arbitrage.connectors.okx import (
    OkxSpotAdapter,
)
from app.crypto_arbitrage.domain.errors import (
    CryptoArbitrageError,
)
from app.crypto_arbitrage.domain.fees import (
    FeeRate,
    FeeSchedule,
)
from app.crypto_arbitrage.domain.symbols import build_pair
from app.crypto_arbitrage.market_data.freshness import (
    FreshnessPolicy,
    utc_now,
)
from app.crypto_arbitrage.market_data.rate_limiter import (
    TokenBucketRateLimiter,
)
from app.crypto_arbitrage.opportunities.cex_cex import (
    CexCexScanner,
)
from app.crypto_arbitrage.opportunities.profitability import (
    CostModel,
)
from app.crypto_arbitrage.services.book_source import (
    RestBookSource,
)
from app.crypto_arbitrage.services.scanner_service import (
    CryptoScannerService,
)


ADAPTERS: dict[str, Any] = {
    "BINANCE": BinanceSpotAdapter,
    "OKX": OkxSpotAdapter,
    "BYBIT": BybitSpotAdapter,
}


def parse_venues(raw: str) -> list[str]:
    return [
        item.strip().upper()
        for item in str(raw or "").split(",")
        if item.strip()
    ]


def parse_taker_fees(raw: str) -> dict[str, str]:
    fees: dict[str, str] = {}

    for entry in str(raw or "").split(","):
        item = entry.strip()

        if not item or ":" not in item:
            continue

        venue_id, _, rate = item.partition(":")
        fees[venue_id.strip().upper()] = rate.strip()

    return fees


def build_fee_schedule(
    config: Settings,
    *,
    instrument_by_venue: dict[str, str],
) -> FeeSchedule:
    """Tabela de taxas a partir da configuração versionada."""

    schedule = FeeSchedule()
    moment = utc_now()
    fees = parse_taker_fees(config.CRYPTO_SCANNER_TAKER_FEES)

    for venue_id, instrument_id in (
        instrument_by_venue.items()
    ):
        rate = fees.get(venue_id)

        if rate is None:
            # Fail-closed: venue sem taxa configurada nao entra
            # na tabela, e o scanner a rejeitara por
            # FeeUnknownError com motivo registrado.
            continue

        schedule.register(
            FeeRate(
                venue_id=venue_id,
                instrument_id=instrument_id,
                maker_rate=Decimal(rate),
                taker_rate=Decimal(rate),
                source="settings:CRYPTO_SCANNER_TAKER_FEES",
                effective_at=moment,
            )
        )

    return schedule


def build_scanner_service(
    config: Settings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> CryptoScannerService:
    """Constrói o serviço completo pronto para o scheduler."""

    config = config or default_settings

    venues = parse_venues(config.CRYPTO_SCANNER_VENUES)

    unknown = [
        venue for venue in venues if venue not in ADAPTERS
    ]

    if unknown:
        raise CryptoArbitrageError(
            "Venues sem adaptador: "
            f"{', '.join(unknown)}."
        )

    pair = build_pair(
        config.CRYPTO_SCANNER_BASE_ASSET,
        config.CRYPTO_SCANNER_QUOTE_ASSET,
    )

    http_client = client or httpx.AsyncClient(
        timeout=float(
            config.CRYPTO_SCANNER_REQUEST_TIMEOUT_SECONDS
        ),
        headers={"User-Agent": "predarb-scanner/1.0"},
    )

    limiter = TokenBucketRateLimiter(
        capacity=str(
            config.CRYPTO_SCANNER_RATE_LIMIT_CAPACITY
        ),
        refill_per_second=(
            config.CRYPTO_SCANNER_RATE_LIMIT_REFILL_PER_SECOND
        ),
        label="crypto_scanner",
    )

    transport = HttpxRestTransport(
        http_client,
        rate_limiter=limiter,
    )

    sources: dict[str, RestBookSource] = {}
    instrument_by_venue: dict[str, str] = {}

    for venue_id in venues:
        adapter = ADAPTERS[venue_id]()

        source = RestBookSource(
            adapter,
            transport,
            depth=config.CRYPTO_SCANNER_DEPTH,
        )

        sources[venue_id] = source
        instrument_by_venue[venue_id] = (
            source.instrument_id_for(pair)
        )

    scanner = CexCexScanner(
        fee_schedule=build_fee_schedule(
            config,
            instrument_by_venue=instrument_by_venue,
        ),
        cost_model=CostModel.create(
            slippage_ratio=(
                config.CRYPTO_SCANNER_SLIPPAGE_RATIO
            ),
            safety_buffer_ratio=(
                config.CRYPTO_SCANNER_SAFETY_BUFFER_RATIO
            ),
            minimum_net_profit=(
                config.CRYPTO_SCANNER_MINIMUM_NET_PROFIT
            ),
            minimum_roi=(
                config.CRYPTO_SCANNER_MINIMUM_ROI
            ),
        ),
        freshness=FreshnessPolicy.create(
            max_age_ms=str(
                config.CRYPTO_SCANNER_MAX_BOOK_AGE_MS
            ),
        ),
    )

    return CryptoScannerService(
        scanner=scanner,
        sources=sources,
        pair=pair,
        quantity=config.CRYPTO_SCANNER_QUANTITY,
        enabled=config.CRYPTO_SCANNER_ENABLED,
    )


_service: CryptoScannerService | None = None


def get_scanner_service() -> CryptoScannerService:
    """Instância única, criada na primeira chamada."""

    global _service

    if _service is None:
        _service = build_scanner_service()

    return _service


def reset_scanner_service() -> None:
    """Descarta a instância. Usado por testes."""

    global _service

    _service = None
