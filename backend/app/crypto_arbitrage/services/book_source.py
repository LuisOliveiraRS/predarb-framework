"""Obtenção de books por REST.

Escolha deliberada: o coletor de produção usa REST periódico, não
WebSocket, apesar de o WebSocket estar implementado e testado.

O motivo é a hospedagem. A seção 4 registra que o processo no
Render Free dorme e reinicia. Socket persistente em processo que
hiberna significa reconexão constante, e cada reconexão obriga
resync completo — o livro nunca alcança estado estável.

A seção 14 afirma que REST periódico não serve como hot path de
arbitragem, e isso continua verdade **para execução**. A Fase 20 é
Paper: o objetivo é descobrir se existe ineficiência líquida, não
capturá-la. Latência de polling não impede essa resposta, e
nenhuma decisão de execução depende dela.

Quando houver hospedagem que não hiberne, o `BookSynchronizer` e
o `WebsocketsTransport` já estão prontos para assumir.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.crypto_arbitrage.connectors.venue_adapter import (
    SnapshotPayload,
)
from app.crypto_arbitrage.domain.errors import (
    CryptoArbitrageError,
)
from app.crypto_arbitrage.domain.models import (
    OrderBookSnapshot,
)
from app.crypto_arbitrage.domain.symbols import SymbolPair
from app.crypto_arbitrage.market_data.local_book import (
    LocalOrderBook,
)


class RestBookSource:
    """Busca e normaliza o book de uma venue."""

    def __init__(
        self,
        adapter: Any,
        transport: Any,
        *,
        depth: int = 50,
    ) -> None:
        self.adapter = adapter
        self.transport = transport
        self.depth = int(depth)

        if self.depth <= 0:
            raise CryptoArbitrageError(
                "depth deve ser maior que zero."
            )

    @property
    def venue_id(self) -> str:
        return self.adapter.venue_id

    def instrument_id_for(self, pair: SymbolPair) -> str:
        return self.adapter.instrument_id_for(pair)

    async def fetch_snapshot(
        self,
        pair: SymbolPair,
        *,
        received_timestamp: datetime | None = None,
    ) -> OrderBookSnapshot:
        """Devolve um book normalizado e já validado.

        Passa pelo `LocalOrderBook` de propósito, em vez de montar
        o snapshot direto: assim o book de REST recebe as mesmas
        validações do book de stream — ordenação, mercado cruzado
        e níveis positivos.
        """

        instrument_id = self.instrument_id_for(pair)

        url, params = self.adapter.depth_request(
            instrument_id,
            self.depth,
        )

        payload = await self.transport.get_json(
            url,
            params=params,
        )

        snapshot: SnapshotPayload = (
            self.adapter.parse_rest_snapshot(
                payload,
                instrument_id=instrument_id,
            )
        )

        received = received_timestamp or datetime.now(
            timezone.utc
        )

        book = LocalOrderBook(
            self.venue_id,
            instrument_id,
            sequence_mode=self.adapter.sequence_mode,
        )

        book.apply_snapshot(
            bids=snapshot.bids,
            asks=snapshot.asks,
            update_id=snapshot.update_id,
            exchange_timestamp=(
                snapshot.exchange_timestamp
            ),
            received_timestamp=received,
        )

        return book.to_snapshot(
            received_timestamp=received,
        )
