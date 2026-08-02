"""Tipos comuns de tradução entre venue e domínio.

Um adaptador de venue não faz rede. Ele recebe payload já
decodificado e devolve os tipos do domínio. Essa separação é
deliberada: o risco de um conector está no parsing, não no
encanamento HTTP, e parsing puro é testável por fixture sem
depender de internet, como a seção 28 do CLAUDE.md exige.

Os formatos foram confirmados na documentação oficial em
02/08/2026. A seção 29 manda revalidar antes de cada
implementação, e cada adaptador registra o que foi confirmado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, Sequence, runtime_checkable

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
)
from app.crypto_arbitrage.domain.models import Instrument
from app.crypto_arbitrage.market_data.local_book import (
    BookLevelChange,
    BookUpdate,
    SequenceMode,
)


class StreamMessageKind(str, Enum):
    """Natureza de uma mensagem de stream já interpretada."""

    SNAPSHOT = "SNAPSHOT"
    DELTA = "DELTA"
    IGNORED = "IGNORED"


@dataclass(frozen=True, slots=True)
class SnapshotPayload:
    """Snapshot pronto para `LocalOrderBook.apply_snapshot`."""

    instrument_id: str
    bids: tuple[BookLevelChange, ...]
    asks: tuple[BookLevelChange, ...]
    update_id: int | None = None
    exchange_timestamp: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "bid_levels": len(self.bids),
            "ask_levels": len(self.asks),
            "update_id": self.update_id,
            "exchange_timestamp": (
                self.exchange_timestamp.isoformat()
                if self.exchange_timestamp is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class StreamMessage:
    """Mensagem de stream traduzida.

    `IGNORED` cobre confirmação de inscrição, ping e qualquer
    coisa que não altere livro. Devolver um tipo explícito em vez
    de `None` obriga quem consome a decidir o que fazer, em vez
    de tratar ausência como sucesso.
    """

    kind: StreamMessageKind
    instrument_id: str | None = None
    snapshot: SnapshotPayload | None = None
    update: BookUpdate | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "instrument_id": self.instrument_id,
            "has_snapshot": self.snapshot is not None,
            "has_update": self.update is not None,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class SkippedInstrument:
    """Instrumento descartado, com o motivo preservado."""

    raw_symbol: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_symbol": self.raw_symbol,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class InstrumentParseResult:
    """Instrumentos aceitos e descartados, lado a lado.

    Um símbolo malformado não deve derrubar a lista inteira, mas
    também não pode sumir em silêncio: descarte sem registro
    viraria "a venue não lista esse par" na investigação
    seguinte.
    """

    instruments: tuple[Instrument, ...]
    skipped: tuple[SkippedInstrument, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": len(self.instruments),
            "skipped": [
                item.to_dict() for item in self.skipped
            ],
        }


@runtime_checkable
class VenueAdapter(Protocol):
    """Tradutor entre o formato de uma venue e o domínio."""

    venue_id: str
    sequence_mode: SequenceMode

    def parse_instruments(
        self,
        payload: Any,
    ) -> InstrumentParseResult: ...

    def parse_rest_snapshot(
        self,
        payload: Any,
        *,
        instrument_id: str,
    ) -> SnapshotPayload: ...

    def parse_stream_message(
        self,
        payload: Any,
    ) -> StreamMessage: ...


def require_mapping(
    payload: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise DomainValidationError(
            f"{field_name} deve ser um objeto JSON."
        )

    return payload


def require_sequence(
    payload: Any,
    *,
    field_name: str,
) -> Sequence[Any]:
    if isinstance(payload, (str, bytes)) or not isinstance(
        payload,
        (list, tuple),
    ):
        raise DomainValidationError(
            f"{field_name} deve ser uma lista."
        )

    return payload


def parse_levels(
    raw_levels: Any,
    *,
    field_name: str,
) -> tuple[BookLevelChange, ...]:
    """Converte `[["100.5", "2"], ...]` em níveis do domínio.

    Elementos além de preço e quantidade são ignorados de
    propósito: a OKX publica quatro campos por nível, e os dois
    últimos não interessam ao livro. Ler por posição fixa mantém
    o mesmo parser válido para as três venues.
    """

    levels: list[BookLevelChange] = []

    for index, entry in enumerate(
        require_sequence(raw_levels, field_name=field_name)
    ):
        row = require_sequence(
            entry,
            field_name=f"{field_name}[{index}]",
        )

        if len(row) < 2:
            raise DomainValidationError(
                f"{field_name}[{index}] precisa de preço e "
                "quantidade."
            )

        levels.append(
            BookLevelChange(
                price=str(row[0]),
                quantity=str(row[1]),
            )
        )

    return tuple(levels)


def milliseconds_to_datetime(
    value: Any,
    *,
    field_name: str,
) -> datetime | None:
    """Converte epoch em milissegundos para datetime aware."""

    if value is None or value == "":
        return None

    try:
        milliseconds = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise DomainValidationError(
            f"{field_name} não é um epoch válido: {value!r}."
        ) from exc

    return datetime.fromtimestamp(
        milliseconds / 1000,
        tz=timezone.utc,
    )


def coerce_int(
    value: Any,
    *,
    field_name: str,
) -> int | None:
    if value is None or value == "":
        return None

    try:
        return int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise DomainValidationError(
            f"{field_name} não é um inteiro válido: "
            f"{value!r}."
        ) from exc


__all__ = [
    "InstrumentParseResult",
    "SkippedInstrument",
    "SnapshotPayload",
    "StreamMessage",
    "StreamMessageKind",
    "VenueAdapter",
    "coerce_int",
    "milliseconds_to_datetime",
    "parse_levels",
    "require_mapping",
    "require_sequence",
]
