"""Book local mantido por aplicação de deltas.

Seção 14 do CLAUDE.md: obter snapshot, abrir stream, aplicar
deltas em ordem, validar sequence, detectar gaps e refazer
snapshot.

Cada venue numera seus updates de um jeito. Em vez de um parser
por venue espalhado pela lógica de book, este módulo define um
`BookUpdate` neutro e um `SequenceMode` que descreve *como*
validar a continuidade. Os conectores traduzem seus campos para
esse formato; a lógica de livro é uma só.

O módulo é deliberadamente pessimista: qualquer descontinuidade,
book cruzado ou delta antes do snapshot interrompe a aplicação e
marca o livro para resync. Corrigir localmente um book divergente
é pior do que admitir que ele não é mais confiável.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Iterable

from app.crypto_arbitrage.domain.enums import ConnectorState
from app.crypto_arbitrage.domain.errors import (
    BookNotReadyError,
    CorruptedBookError,
    DomainValidationError,
    SequenceGapError,
)
from app.crypto_arbitrage.domain.models import (
    OrderBookLevel,
    OrderBookSnapshot,
)
from app.crypto_arbitrage.domain.money import (
    ZERO,
    ensure_non_negative,
    ensure_positive,
)


class SequenceMode(str, Enum):
    """Como validar a continuidade entre updates.

    `STRICT_INCREMENT` — o próximo update deve ser exatamente o
    último aplicado mais um.

    `RANGE` — o update declara um intervalo `[first, final]` e é
    válido quando cobre `último + 1`. Modelo usado por venues que
    agregam vários updates numa mensagem.

    `PREVIOUS_MATCH` — o update declara qual sequência ele
    sucede, e ela deve bater com a última aplicada.

    `MONOTONIC` — exige apenas que a sequência avance. Aceita
    saltos, então **não detecta gap**. É o modo honesto para
    venues que numeram updates mas não documentam continuidade:
    presumir incremento de 1 nesses casos produziria alarme falso
    em operação normal. A integridade fica por conta de outros
    sinais, como snapshot novo ou book cruzado.

    `NONE` — sem validação alguma, aceita até retrocesso. Só
    aceitável para venues que realmente não publicam sequência.
    Evitar.
    """

    STRICT_INCREMENT = "STRICT_INCREMENT"
    RANGE = "RANGE"
    PREVIOUS_MATCH = "PREVIOUS_MATCH"
    MONOTONIC = "MONOTONIC"
    NONE = "NONE"


@dataclass(frozen=True, slots=True)
class BookLevelChange:
    """Alteração de um nível. Quantidade zero remove o nível."""

    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "price",
            ensure_positive(
                self.price,
                field_name="price",
            ),
        )

        object.__setattr__(
            self,
            "quantity",
            ensure_non_negative(
                self.quantity,
                field_name="quantity",
            ),
        )

    @property
    def is_removal(self) -> bool:
        return self.quantity == ZERO


@dataclass(frozen=True, slots=True)
class BookUpdate:
    """Delta neutro, independente do formato da venue."""

    bids: tuple[BookLevelChange, ...] = ()
    asks: tuple[BookLevelChange, ...] = ()
    final_update_id: int | None = None
    first_update_id: int | None = None
    previous_update_id: int | None = None
    exchange_timestamp: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "bids", tuple(self.bids))
        object.__setattr__(self, "asks", tuple(self.asks))


@dataclass
class BookStats:
    """Contadores observáveis do livro."""

    applied_updates: int = 0
    gap_count: int = 0
    resync_count: int = 0
    ignored_stale_updates: int = 0
    last_update_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied_updates": self.applied_updates,
            "gap_count": self.gap_count,
            "resync_count": self.resync_count,
            "ignored_stale_updates": (
                self.ignored_stale_updates
            ),
            "last_update_id": self.last_update_id,
        }


class LocalOrderBook:
    """Livro local de uma venue e instrumento."""

    def __init__(
        self,
        venue_id: str,
        instrument_id: str,
        *,
        sequence_mode: SequenceMode = (
            SequenceMode.STRICT_INCREMENT
        ),
        max_depth: int = 200,
    ) -> None:
        self.venue_id = str(venue_id or "").strip().upper()
        self.instrument_id = str(
            instrument_id or ""
        ).strip().upper()

        if not self.venue_id or not self.instrument_id:
            raise DomainValidationError(
                "venue_id e instrument_id são obrigatórios."
            )

        if int(max_depth) <= 0:
            raise DomainValidationError(
                "max_depth deve ser maior que zero."
            )

        self.sequence_mode = sequence_mode
        self.max_depth = int(max_depth)

        self._bids: dict[Decimal, Decimal] = {}
        self._asks: dict[Decimal, Decimal] = {}
        self._ready = False
        self._needs_resync = False
        self._exchange_timestamp: datetime | None = None
        self._received_timestamp: datetime | None = None
        self.resync_reason = ""

        self.stats = BookStats()

    @property
    def is_ready(self) -> bool:
        """Pronto significa: tem snapshot e não perdeu delta."""

        return self._ready and not self._needs_resync

    @property
    def needs_resync(self) -> bool:
        return self._needs_resync

    @property
    def state(self) -> ConnectorState:
        if self._needs_resync:
            return ConnectorState.DEGRADED

        if not self._ready:
            return ConnectorState.CONNECTING

        return ConnectorState.READY

    def apply_snapshot(
        self,
        bids: Iterable[BookLevelChange],
        asks: Iterable[BookLevelChange],
        *,
        update_id: int | None = None,
        exchange_timestamp: datetime | None = None,
        received_timestamp: datetime | None = None,
    ) -> None:
        """Substitui o livro inteiro e limpa o pedido de resync."""

        self._bids = {}
        self._asks = {}

        for change in bids:
            if not change.is_removal:
                self._bids[change.price] = change.quantity

        for change in asks:
            if not change.is_removal:
                self._asks[change.price] = change.quantity

        self._ready = True

        if self._needs_resync:
            self.stats.resync_count += 1

        self._needs_resync = False
        self.resync_reason = ""
        self.stats.last_update_id = update_id
        self._exchange_timestamp = exchange_timestamp
        self._received_timestamp = received_timestamp

        self._assert_not_crossed()

    def apply_update(
        self,
        update: BookUpdate,
        *,
        received_timestamp: datetime | None = None,
    ) -> bool:
        """Aplica um delta. Devolve `False` se foi ignorado.

        Ignorado é diferente de rejeitado: updates anteriores ao
        snapshot são esperados durante a sincronização inicial e
        apenas descartados. Já um gap levanta erro.
        """

        if not self._ready:
            raise BookNotReadyError(
                f"Book de {self.venue_id}/"
                f"{self.instrument_id} recebeu delta antes "
                "do snapshot inicial."
            )

        if self._needs_resync:
            raise SequenceGapError(
                f"Book de {self.venue_id}/"
                f"{self.instrument_id} aguarda resync e não "
                "aceita deltas."
            )

        if not self._check_sequence(update):
            self.stats.ignored_stale_updates += 1
            return False

        for change in update.bids:
            self._apply_change(self._bids, change)

        for change in update.asks:
            self._apply_change(self._asks, change)

        if update.final_update_id is not None:
            self.stats.last_update_id = (
                update.final_update_id
            )

        self.stats.applied_updates += 1

        if update.exchange_timestamp is not None:
            self._exchange_timestamp = (
                update.exchange_timestamp
            )

        if received_timestamp is not None:
            self._received_timestamp = received_timestamp

        self._assert_not_crossed()

        return True

    def _check_sequence(self, update: BookUpdate) -> bool:
        """Valida continuidade. Levanta em gap, `False` se velho."""

        if self.sequence_mode is SequenceMode.NONE:
            return True

        last = self.stats.last_update_id

        if last is None:
            return True

        if self.sequence_mode is SequenceMode.PREVIOUS_MATCH:
            previous = update.previous_update_id

            if previous is None:
                raise SequenceGapError(
                    "Update sem previous_update_id em modo "
                    "PREVIOUS_MATCH."
                )

            if previous == last:
                return True

            if (
                update.final_update_id is not None
                and update.final_update_id <= last
            ):
                return False

            self._flag_gap(
                f"previous_update_id {previous} não sucede "
                f"{last}."
            )

        final = update.final_update_id

        if final is None:
            raise SequenceGapError(
                "Update sem final_update_id em modo "
                f"{self.sequence_mode.value}."
            )

        if final <= last:
            return False

        if self.sequence_mode is SequenceMode.MONOTONIC:
            return True

        if self.sequence_mode is SequenceMode.STRICT_INCREMENT:
            if final == last + 1:
                return True

            self._flag_gap(
                f"esperado {last + 1}, recebido {final}."
            )

        first = update.first_update_id

        if first is None:
            raise SequenceGapError(
                "Update sem first_update_id em modo RANGE."
            )

        if first <= last + 1 <= final:
            return True

        self._flag_gap(
            f"intervalo [{first}, {final}] não cobre "
            f"{last + 1}."
        )

        return False

    def _flag_gap(self, detail: str) -> None:
        self._needs_resync = True
        self.stats.gap_count += 1

        raise SequenceGapError(
            f"Gap em {self.venue_id}/{self.instrument_id}: "
            f"{detail} Resync obrigatório."
        )

    @staticmethod
    def _apply_change(
        side: dict[Decimal, Decimal],
        change: BookLevelChange,
    ) -> None:
        if change.is_removal:
            side.pop(change.price, None)
            return

        side[change.price] = change.quantity

    def _assert_not_crossed(self) -> None:
        if not self._bids or not self._asks:
            return

        if max(self._bids) >= min(self._asks):
            self._needs_resync = True

            raise CorruptedBookError(
                f"Book de {self.venue_id}/"
                f"{self.instrument_id} cruzado: melhor bid "
                f"{max(self._bids)} >= melhor ask "
                f"{min(self._asks)}. Resync obrigatório."
            )

    def mark_for_resync(self, reason: str = "") -> None:
        """Invalida o livro por decisão externa.

        Usado por reconexão, timeout de heartbeat ou checksum
        divergente, que este módulo não observa diretamente.
        """

        self._needs_resync = True
        self.resync_reason = str(reason or "").strip()

    def best_bid(self) -> Decimal | None:
        return max(self._bids) if self._bids else None

    def best_ask(self) -> Decimal | None:
        return min(self._asks) if self._asks else None

    def depth(self) -> tuple[int, int]:
        return (len(self._bids), len(self._asks))

    def to_snapshot(
        self,
        *,
        received_timestamp: datetime | None = None,
        exchange_timestamp: datetime | None = None,
        depth: int | None = None,
    ) -> OrderBookSnapshot:
        """Converte o estado atual em snapshot do domínio.

        Só produz snapshot de livro pronto: um book incompleto ou
        aguardando resync não pode alimentar cálculo de
        oportunidade.
        """

        if not self.is_ready:
            raise BookNotReadyError(
                f"Book de {self.venue_id}/"
                f"{self.instrument_id} não está pronto "
                f"(estado {self.state.value})."
            )

        received = (
            received_timestamp
            or self._received_timestamp
        )

        if received is None:
            raise DomainValidationError(
                "received_timestamp é obrigatório para "
                "gerar snapshot."
            )

        exchange = (
            exchange_timestamp
            or self._exchange_timestamp
            or received
        )

        limit = int(depth or self.max_depth)

        if limit <= 0:
            raise DomainValidationError(
                "depth deve ser maior que zero."
            )

        bids = tuple(
            OrderBookLevel(
                price=price,
                quantity=self._bids[price],
            )
            for price in sorted(
                self._bids,
                reverse=True,
            )[:limit]
        )

        asks = tuple(
            OrderBookLevel(
                price=price,
                quantity=self._asks[price],
            )
            for price in sorted(self._asks)[:limit]
        )

        return OrderBookSnapshot(
            venue_id=self.venue_id,
            instrument_id=self.instrument_id,
            bids=bids,
            asks=asks,
            exchange_timestamp=exchange,
            received_timestamp=received,
            sequence=self.stats.last_update_id,
            is_snapshot=False,
        )

    def status(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "state": self.state.value,
            "is_ready": self.is_ready,
            "needs_resync": self.needs_resync,
            "resync_reason": self.resync_reason or None,
            "sequence_mode": self.sequence_mode.value,
            "bid_levels": len(self._bids),
            "ask_levels": len(self._asks),
            "stats": self.stats.to_dict(),
        }
