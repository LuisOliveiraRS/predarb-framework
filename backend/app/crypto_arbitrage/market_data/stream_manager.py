"""Orquestração de um book alimentado por stream.

Junta as peças das etapas anteriores: o adaptador traduz o
payload da venue, o `LocalOrderBook` mantém o livro e valida
sequência, a `FreshnessPolicy` decide se o dado ainda serve, e
`ConnectorMetrics` registra o que aconteceu.

O manager não faz rede. Ele recebe mensagens já decodificadas e
devolve um resultado explícito para cada uma. Quem lê do socket é
o transporte, na etapa seguinte.

Princípio central: **nenhuma exceção de sequência escapa como
falha genérica**. Gap e corrupção são estados operacionais
previstos, não bugs, e cada um leva a uma ação diferente — por
isso viram `StreamOutcome`, não `try/except` espalhado por quem
chama.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from app.crypto_arbitrage.connectors.venue_adapter import (
    StreamMessageKind,
)
from app.crypto_arbitrage.domain.enums import ConnectorState
from app.crypto_arbitrage.domain.errors import (
    BookNotReadyError,
    CorruptedBookError,
    CryptoArbitrageError,
    SequenceGapError,
)
from app.crypto_arbitrage.domain.models import (
    OrderBookSnapshot,
)
from app.crypto_arbitrage.market_data.freshness import (
    FreshnessPolicy,
    FreshnessVerdict,
    milliseconds_between,
)
from app.crypto_arbitrage.market_data.local_book import (
    LocalOrderBook,
)
from app.crypto_arbitrage.market_data.metrics import (
    ConnectorMetrics,
)


class StreamOutcome(str, Enum):
    """O que aconteceu com uma mensagem."""

    SNAPSHOT_APPLIED = "SNAPSHOT_APPLIED"
    DELTA_APPLIED = "DELTA_APPLIED"
    DELTA_IGNORED = "DELTA_IGNORED"
    MESSAGE_IGNORED = "MESSAGE_IGNORED"
    RESYNC_REQUIRED = "RESYNC_REQUIRED"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class StreamResult:
    """Resultado de processar uma mensagem, com o motivo."""

    outcome: StreamOutcome
    detail: str | None = None
    instrument_id: str | None = None

    @property
    def needs_resync(self) -> bool:
        return self.outcome is StreamOutcome.RESYNC_REQUIRED

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "detail": self.detail,
            "instrument_id": self.instrument_id,
            "needs_resync": self.needs_resync,
        }


class BookStreamManager:
    """Aplica mensagens de uma venue a um book local."""

    def __init__(
        self,
        adapter: Any,
        book: LocalOrderBook,
        *,
        metrics: ConnectorMetrics | None = None,
        freshness: FreshnessPolicy | None = None,
    ) -> None:
        self.adapter = adapter
        self.book = book
        self.metrics = metrics or ConnectorMetrics(
            book.venue_id
        )
        self.freshness = (
            freshness or FreshnessPolicy.create()
        )

    def handle_message(
        self,
        payload: Any,
        *,
        received_timestamp: datetime,
        processed_at: datetime | None = None,
    ) -> StreamResult:
        """Processa uma mensagem já decodificada.

        `processed_at` é o instante em que o processamento
        terminou, medido por quem chama. A diferença para
        `received_timestamp` vira `local_processing_latency_ms`.
        """

        self.metrics.record_message(
            received_at=received_timestamp,
        )

        try:
            message = self.adapter.parse_stream_message(
                payload
            )
        except CryptoArbitrageError as exc:
            self.metrics.record_error(str(exc))

            return StreamResult(
                outcome=StreamOutcome.ERROR,
                detail=str(exc),
            )

        result = self._route(
            message,
            received_timestamp=received_timestamp,
        )

        if processed_at is not None:
            self.metrics.record_processing_latency(
                milliseconds_between(
                    received_timestamp,
                    processed_at,
                )
            )

        self.metrics.set_state(self.book.state)

        return result

    def _route(
        self,
        message: Any,
        *,
        received_timestamp: datetime,
    ) -> StreamResult:
        if message.kind is StreamMessageKind.IGNORED:
            return StreamResult(
                outcome=StreamOutcome.MESSAGE_IGNORED,
                detail=message.detail,
                instrument_id=message.instrument_id,
            )

        if message.kind is StreamMessageKind.SNAPSHOT:
            return self._apply_snapshot(
                message,
                received_timestamp=received_timestamp,
            )

        return self._apply_delta(
            message,
            received_timestamp=received_timestamp,
        )

    def _apply_snapshot(
        self,
        message: Any,
        *,
        received_timestamp: datetime,
    ) -> StreamResult:
        snapshot = message.snapshot

        if snapshot is None:
            self.metrics.record_error(
                "Mensagem SNAPSHOT sem payload."
            )

            return StreamResult(
                outcome=StreamOutcome.ERROR,
                detail="Mensagem SNAPSHOT sem payload.",
                instrument_id=message.instrument_id,
            )

        try:
            self.book.apply_snapshot(
                bids=snapshot.bids,
                asks=snapshot.asks,
                update_id=snapshot.update_id,
                exchange_timestamp=(
                    snapshot.exchange_timestamp
                ),
                received_timestamp=received_timestamp,
            )
        except CorruptedBookError as exc:
            self.metrics.record_corrupted(str(exc))

            return StreamResult(
                outcome=StreamOutcome.RESYNC_REQUIRED,
                detail=str(exc),
                instrument_id=message.instrument_id,
            )

        self.metrics.record_snapshot()

        self._record_exchange_latency(
            snapshot.exchange_timestamp,
            received_timestamp,
        )

        return StreamResult(
            outcome=StreamOutcome.SNAPSHOT_APPLIED,
            detail=message.detail,
            instrument_id=message.instrument_id,
        )

    def _apply_delta(
        self,
        message: Any,
        *,
        received_timestamp: datetime,
    ) -> StreamResult:
        update = message.update

        if update is None:
            self.metrics.record_error(
                "Mensagem DELTA sem payload."
            )

            return StreamResult(
                outcome=StreamOutcome.ERROR,
                detail="Mensagem DELTA sem payload.",
                instrument_id=message.instrument_id,
            )

        try:
            applied = self.book.apply_update(
                update,
                received_timestamp=received_timestamp,
            )
        except SequenceGapError as exc:
            self.metrics.record_gap(str(exc))

            return StreamResult(
                outcome=StreamOutcome.RESYNC_REQUIRED,
                detail=str(exc),
                instrument_id=message.instrument_id,
            )
        except CorruptedBookError as exc:
            self.metrics.record_corrupted(str(exc))

            return StreamResult(
                outcome=StreamOutcome.RESYNC_REQUIRED,
                detail=str(exc),
                instrument_id=message.instrument_id,
            )
        except BookNotReadyError as exc:
            self.metrics.record_error(str(exc))

            return StreamResult(
                outcome=StreamOutcome.RESYNC_REQUIRED,
                detail=str(exc),
                instrument_id=message.instrument_id,
            )

        if not applied:
            self.metrics.record_delta_ignored()

            return StreamResult(
                outcome=StreamOutcome.DELTA_IGNORED,
                detail=(
                    "Update anterior ao estado atual do "
                    "livro."
                ),
                instrument_id=message.instrument_id,
            )

        self.metrics.record_delta_applied()

        self._record_exchange_latency(
            update.exchange_timestamp,
            received_timestamp,
        )

        return StreamResult(
            outcome=StreamOutcome.DELTA_APPLIED,
            instrument_id=message.instrument_id,
        )

    def _record_exchange_latency(
        self,
        exchange_timestamp: datetime | None,
        received_timestamp: datetime,
    ) -> None:
        if exchange_timestamp is None:
            return

        self.metrics.record_exchange_latency(
            milliseconds_between(
                exchange_timestamp,
                received_timestamp,
            )
        )

    def snapshot_for_pricing(
        self,
        now: datetime,
    ) -> tuple[OrderBookSnapshot | None, FreshnessVerdict]:
        """Devolve o book apenas se ele puder precificar.

        Um livro não pronto ou velho demais devolve `None` com o
        motivo. Quem chama não precisa reimplementar a decisão, e
        não tem como esquecer de checá-la: o snapshot só vem
        acompanhado do veredito.
        """

        if not self.book.is_ready:
            verdict = FreshnessVerdict(
                is_fresh=False,
                age_ms=Decimal("0"),
                limit_ms=self.freshness.max_age_ms,
                reason=(
                    f"Livro em estado "
                    f"{self.book.state.value}."
                ),
            )

            return (None, verdict)

        snapshot = self.book.to_snapshot()
        verdict = self.freshness.evaluate(snapshot, now)

        self.metrics.record_orderbook_age(verdict.age_ms)

        if not verdict.is_fresh:
            return (None, verdict)

        return (snapshot, verdict)

    def mark_disconnected(self, reason: str = "") -> None:
        """Registra queda de conexão e invalida o livro.

        Reconexão obriga resync: mensagens perdidas enquanto o
        socket esteve fora não têm como ser recuperadas, e o
        livro local deixou de refletir a venue.
        """

        self.book.mark_for_resync(
            reason or "Conexão perdida."
        )

        self.metrics.record_reconnect()
        self.metrics.set_state(ConnectorState.DISCONNECTED)

    def status(self) -> dict[str, Any]:
        return {
            "book": self.book.status(),
            "metrics": self.metrics.to_dict(),
            "freshness_limit_ms": str(
                self.freshness.max_age_ms
            ),
        }
