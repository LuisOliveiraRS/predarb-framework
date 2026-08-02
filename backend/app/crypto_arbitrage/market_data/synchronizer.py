"""Sincronização inicial entre snapshot REST e stream.

Este é o ponto onde books locais silenciosamente divergem, e o
motivo é sempre o mesmo: quem só busca o snapshot e depois abre o
stream perde tudo o que aconteceu entre as duas coisas, e o livro
nasce errado sem nenhum sinal.

O procedimento correto, que a Binance documenta e as outras
venues seguem em espírito, é o inverso:

```text
1. abrir o stream e BUFFERIZAR os deltas
2. so entao buscar o snapshot REST
3. conferir se o snapshot alcanca o primeiro delta bufferizado
4. aplicar o snapshot
5. reproduzir o buffer, descartando o que ja estava contido
6. passar para modo ao vivo
```

O passo 3 é o que a maioria das implementações esquece. Um
snapshot antigo demais deixa um vão entre ele e o buffer, e esse
vão nunca mais é preenchido.

A fila é limitada de propósito. Buffer sem teto num processo de
vida longa é vazamento de memória, e um buffer gigante é sinal de
que a sincronização travou — melhor falhar e refazer do que
acumular.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from app.crypto_arbitrage.connectors.venue_adapter import (
    SnapshotPayload,
    StreamMessageKind,
)
from app.crypto_arbitrage.domain.errors import (
    CryptoArbitrageError,
    SynchronizationError,
)
from app.crypto_arbitrage.market_data.stream_manager import (
    BookStreamManager,
    StreamOutcome,
    StreamResult,
)


class SyncState(str, Enum):
    """Fase da sincronização."""

    BUFFERING = "BUFFERING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


@dataclass
class BufferedMessage:
    payload: Any
    received_timestamp: datetime


@dataclass
class SyncStats:
    buffered_total: int = 0
    replayed_total: int = 0
    discarded_total: int = 0
    dropped_overflow_total: int = 0
    snapshot_attempts: int = 0
    snapshot_rejected_total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "buffered_total": self.buffered_total,
            "replayed_total": self.replayed_total,
            "discarded_total": self.discarded_total,
            "dropped_overflow_total": (
                self.dropped_overflow_total
            ),
            "snapshot_attempts": self.snapshot_attempts,
            "snapshot_rejected_total": (
                self.snapshot_rejected_total
            ),
        }


class BookSynchronizer:
    """Conduz um livro do zero até o modo ao vivo."""

    def __init__(
        self,
        adapter: Any,
        manager: BookStreamManager,
        *,
        max_buffer: int = 2000,
    ) -> None:
        if int(max_buffer) <= 0:
            raise SynchronizationError(
                "max_buffer deve ser maior que zero."
            )

        self.adapter = adapter
        self.manager = manager
        self.max_buffer = int(max_buffer)

        self.state = SyncState.BUFFERING
        self.stats = SyncStats()
        self._buffer: list[BufferedMessage] = []
        self._first_buffered_update_id: int | None = None
        self.failure_reason: str | None = None

    @property
    def book(self):
        return self.manager.book

    @property
    def first_buffered_update_id(self) -> int | None:
        """`U` do primeiro delta bufferizado, quando existir.

        É o valor que o passo 3 do procedimento compara com o
        snapshot.
        """

        return self._first_buffered_update_id

    def observe(
        self,
        payload: Any,
        *,
        received_timestamp: datetime,
    ) -> StreamResult:
        """Recebe uma mensagem do stream.

        Em `SYNCED`, delega ao manager. Em `BUFFERING`, guarda os
        deltas e aplica snapshots que a própria venue empurrar.
        """

        if self.state is SyncState.SYNCED:
            result = self.manager.handle_message(
                payload,
                received_timestamp=received_timestamp,
            )

            if result.needs_resync:
                self._enter_buffering(
                    result.detail or "Resync exigido."
                )

            return result

        return self._buffer_message(
            payload,
            received_timestamp=received_timestamp,
        )

    def _buffer_message(
        self,
        payload: Any,
        *,
        received_timestamp: datetime,
    ) -> StreamResult:
        try:
            message = self.adapter.parse_stream_message(
                payload
            )
        except CryptoArbitrageError as exc:
            self.manager.metrics.record_error(str(exc))

            return StreamResult(
                outcome=StreamOutcome.ERROR,
                detail=str(exc),
            )

        if message.kind is StreamMessageKind.IGNORED:
            return StreamResult(
                outcome=StreamOutcome.MESSAGE_IGNORED,
                detail=message.detail,
                instrument_id=message.instrument_id,
            )

        if message.kind is StreamMessageKind.SNAPSHOT:
            # Venues que empurram snapshot na inscricao
            # dispensam o snapshot REST inteiro.
            result = self.manager.handle_message(
                payload,
                received_timestamp=received_timestamp,
            )

            if (
                result.outcome
                is StreamOutcome.SNAPSHOT_APPLIED
            ):
                self._enter_synced()

            return result

        if len(self._buffer) >= self.max_buffer:
            self.stats.dropped_overflow_total += 1
            self._fail(
                "Buffer de sincronização estourou "
                f"({self.max_buffer} mensagens). O snapshot "
                "demorou demais e o livro precisa recomeçar."
            )

            return StreamResult(
                outcome=StreamOutcome.RESYNC_REQUIRED,
                detail=self.failure_reason,
                instrument_id=message.instrument_id,
            )

        self._buffer.append(
            BufferedMessage(
                payload=payload,
                received_timestamp=received_timestamp,
            )
        )

        self.stats.buffered_total += 1

        if (
            self._first_buffered_update_id is None
            and message.update is not None
        ):
            self._first_buffered_update_id = (
                message.update.first_update_id
                if message.update.first_update_id
                is not None
                else message.update.final_update_id
            )

        return StreamResult(
            outcome=StreamOutcome.MESSAGE_IGNORED,
            detail="Bufferizado durante a sincronização.",
            instrument_id=message.instrument_id,
        )

    def apply_rest_snapshot(
        self,
        snapshot: SnapshotPayload,
        *,
        received_timestamp: datetime,
    ) -> StreamResult:
        """Aplica o snapshot REST e reproduz o buffer.

        Recusa snapshot velho demais em vez de aplicá-lo: um
        livro que nasce com vão é pior do que um livro que ainda
        não existe, porque parece pronto.
        """

        self.stats.snapshot_attempts += 1

        if not self._snapshot_reaches_buffer(snapshot):
            self.stats.snapshot_rejected_total += 1

            return StreamResult(
                outcome=StreamOutcome.RESYNC_REQUIRED,
                detail=(
                    "Snapshot anterior ao primeiro delta "
                    f"bufferizado ({snapshot.update_id} < "
                    f"{self._first_buffered_update_id}). "
                    "Busque outro snapshot."
                ),
                instrument_id=snapshot.instrument_id,
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
        except CryptoArbitrageError as exc:
            self._fail(str(exc))

            return StreamResult(
                outcome=StreamOutcome.RESYNC_REQUIRED,
                detail=str(exc),
                instrument_id=snapshot.instrument_id,
            )

        self.manager.metrics.record_snapshot()

        return self._replay(snapshot.instrument_id)

    def _snapshot_reaches_buffer(
        self,
        snapshot: SnapshotPayload,
    ) -> bool:
        checker = getattr(
            self.adapter,
            "is_snapshot_usable",
            None,
        )

        if callable(checker):
            return bool(
                checker(
                    snapshot,
                    self._first_buffered_update_id,
                )
            )

        if self._first_buffered_update_id is None:
            return True

        if snapshot.update_id is None:
            return False

        return (
            snapshot.update_id
            >= self._first_buffered_update_id
        )

    def _replay(
        self,
        instrument_id: str | None,
    ) -> StreamResult:
        pending = list(self._buffer)
        self._buffer.clear()

        for buffered in pending:
            result = self.manager.handle_message(
                buffered.payload,
                received_timestamp=(
                    buffered.received_timestamp
                ),
            )

            if result.outcome is StreamOutcome.DELTA_APPLIED:
                self.stats.replayed_total += 1
                continue

            if result.outcome is StreamOutcome.DELTA_IGNORED:
                self.stats.discarded_total += 1
                continue

            if result.needs_resync:
                self._fail(
                    result.detail
                    or "Falha ao reproduzir o buffer."
                )

                return result

        self._enter_synced()

        return StreamResult(
            outcome=StreamOutcome.SNAPSHOT_APPLIED,
            detail=(
                f"Sincronizado. {self.stats.replayed_total} "
                f"deltas reproduzidos, "
                f"{self.stats.discarded_total} descartados."
            ),
            instrument_id=instrument_id,
        )

    def _enter_synced(self) -> None:
        self.state = SyncState.SYNCED
        self.failure_reason = None
        self._buffer.clear()
        self._first_buffered_update_id = None

    def _enter_buffering(self, reason: str) -> None:
        self.state = SyncState.BUFFERING
        self.failure_reason = reason
        self._buffer.clear()
        self._first_buffered_update_id = None

    def _fail(self, reason: str) -> None:
        self.state = SyncState.FAILED
        self.failure_reason = reason
        self._buffer.clear()
        self._first_buffered_update_id = None

    def restart(self, reason: str = "") -> None:
        """Recomeça a sincronização do zero."""

        self.manager.mark_disconnected(
            reason or "Sincronização reiniciada."
        )

        self._enter_buffering(
            reason or "Sincronização reiniciada."
        )

    @property
    def buffered_count(self) -> int:
        return len(self._buffer)

    def status(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "buffered_count": self.buffered_count,
            "first_buffered_update_id": (
                self._first_buffered_update_id
            ),
            "failure_reason": self.failure_reason,
            "max_buffer": self.max_buffer,
            "stats": self.stats.to_dict(),
            "manager": self.manager.status(),
        }
