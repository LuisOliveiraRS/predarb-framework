"""Protocolos dos conectores cripto.

Seção 12 do CLAUDE.md. São apenas contratos: esta fase não
implementa nenhum conector real, nem registra adapter capaz de
enviar ordem.

A separação entre `PublicCexConnector`, `PrivateAccountReader` e
`TradingAdapter` é intencional e reflete a invariante 8 da seção
8: chaves de leitura e execução devem ser separadas. Um conector
público não deve sequer conhecer credencial.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from app.crypto_arbitrage.domain.fees import FeeRate
from app.crypto_arbitrage.domain.models import (
    Balance,
    ConnectorHealth,
    Fill,
    Instrument,
    OrderBookSnapshot,
)


@runtime_checkable
class PublicCexConnector(Protocol):
    """Dados públicos de uma CEX. Não usa credencial."""

    venue_id: str

    async def list_instruments(
        self,
    ) -> list[Instrument]: ...

    async def get_order_book(
        self,
        instrument_id: str,
        depth: int,
    ) -> OrderBookSnapshot: ...

    async def stream_order_books(
        self,
        instruments: list[str],
    ) -> AsyncIterator[OrderBookSnapshot]: ...

    async def get_server_time(self) -> int: ...

    async def health(self) -> ConnectorHealth: ...


@runtime_checkable
class PrivateAccountReader(Protocol):
    """Leitura de conta com chave sem permissão de trade."""

    venue_id: str

    async def balances(self) -> list[Balance]: ...

    async def fills(self) -> list[Fill]: ...

    async def fee_schedule(self) -> list[FeeRate]: ...


@runtime_checkable
class DexQuoteConnector(Protocol):
    """Cotação em DEX. Não assina nem transmite transação."""

    venue_id: str
    chain_id: str

    async def quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        slippage_bps: int,
    ) -> object: ...


@runtime_checkable
class TradingAdapter(Protocol):
    """Contrato de execução, declarado e nunca implementado.

    Existe para que o desenho do domínio fique completo e
    revisável. Nenhuma implementação pode ser registrada antes
    das fases read-only e testnet, e o registry recusa qualquer
    objeto que satisfaça este protocolo.
    """

    venue_id: str

    async def submit_order(
        self,
        intent: object,
        authorization: object,
    ) -> object: ...

    async def cancel_order(
        self,
        order_id: str,
    ) -> object: ...
