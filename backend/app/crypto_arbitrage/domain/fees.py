"""Taxas efetivas por venue e instrumento.

Seção 9 do CLAUDE.md: não hardcode taxas. Elas variam por conta,
tier, produto, par, região, maker/taker e descontos.

A tabela é fail-closed por construção: consultar uma taxa ausente
ou expirada levanta `FeeUnknownError` em vez de devolver um valor
default. A invariante 15 da seção 8 exige que taxa desconhecida
invalide a oportunidade, e um default silencioso a violaria.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    FeeUnknownError,
)
from app.crypto_arbitrage.domain.money import (
    DecimalInput,
    ensure_non_negative,
    ensure_rate,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if value.tzinfo is None:
        raise DomainValidationError(
            f"{field_name} deve ter timezone."
        )

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class FeeRate:
    """Taxa efetiva conhecida para um instrumento."""

    venue_id: str
    instrument_id: str
    maker_rate: Decimal
    taker_rate: Decimal
    source: str
    effective_at: datetime
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not str(self.venue_id).strip():
            raise DomainValidationError(
                "venue_id é obrigatório."
            )

        if not str(self.instrument_id).strip():
            raise DomainValidationError(
                "instrument_id é obrigatório."
            )

        if not str(self.source).strip():
            raise DomainValidationError(
                "source da taxa é obrigatório. "
                "Taxa sem origem rastreável não é confiável."
            )

        object.__setattr__(
            self,
            "maker_rate",
            ensure_rate(
                self.maker_rate,
                field_name="maker_rate",
            ),
        )

        object.__setattr__(
            self,
            "taker_rate",
            ensure_rate(
                self.taker_rate,
                field_name="taker_rate",
            ),
        )

        object.__setattr__(
            self,
            "effective_at",
            _require_aware(
                self.effective_at,
                field_name="effective_at",
            ),
        )

        if self.expires_at is not None:
            expires_at = _require_aware(
                self.expires_at,
                field_name="expires_at",
            )

            if expires_at <= self.effective_at:
                raise DomainValidationError(
                    "expires_at deve ser posterior a "
                    "effective_at."
                )

            object.__setattr__(
                self,
                "expires_at",
                expires_at,
            )

    def is_valid_at(self, moment: datetime) -> bool:
        reference = _require_aware(
            moment,
            field_name="moment",
        )

        if reference < self.effective_at:
            return False

        if self.expires_at is None:
            return True

        return reference < self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "maker_rate": str(self.maker_rate),
            "taker_rate": str(self.taker_rate),
            "source": self.source,
            "effective_at": self.effective_at.isoformat(),
            "expires_at": (
                self.expires_at.isoformat()
                if self.expires_at is not None
                else None
            ),
        }


class FeeSchedule:
    """Tabela de taxas conhecidas, sem qualquer default."""

    def __init__(self) -> None:
        self._rates: dict[tuple[str, str], FeeRate] = {}

    @staticmethod
    def _key(
        venue_id: str,
        instrument_id: str,
    ) -> tuple[str, str]:
        return (
            str(venue_id).strip().upper(),
            str(instrument_id).strip().upper(),
        )

    def register(self, rate: FeeRate) -> None:
        self._rates[
            self._key(rate.venue_id, rate.instrument_id)
        ] = rate

    def get(
        self,
        venue_id: str,
        instrument_id: str,
        *,
        moment: datetime | None = None,
    ) -> FeeRate:
        """Devolve a taxa vigente ou levanta erro.

        Nunca devolve valor default: a ausência de taxa é uma
        condição de bloqueio, não um caso a contornar.
        """

        reference = moment or _utc_now()

        rate = self._rates.get(
            self._key(venue_id, instrument_id)
        )

        if rate is None:
            raise FeeUnknownError(
                f"Taxa desconhecida para {venue_id}/"
                f"{instrument_id}. A oportunidade não pode "
                "ser avaliada."
            )

        if not rate.is_valid_at(reference):
            raise FeeUnknownError(
                f"Taxa de {venue_id}/{instrument_id} fora da "
                "janela de validade."
            )

        return rate

    def taker_rate(
        self,
        venue_id: str,
        instrument_id: str,
        *,
        moment: datetime | None = None,
    ) -> Decimal:
        return self.get(
            venue_id,
            instrument_id,
            moment=moment,
        ).taker_rate

    def maker_rate(
        self,
        venue_id: str,
        instrument_id: str,
        *,
        moment: datetime | None = None,
    ) -> Decimal:
        return self.get(
            venue_id,
            instrument_id,
            moment=moment,
        ).maker_rate

    def __len__(self) -> int:
        return len(self._rates)


def apply_fee(
    notional: DecimalInput,
    rate: DecimalInput,
) -> Decimal:
    """Custo absoluto de uma taxa sobre um notional."""

    return ensure_non_negative(
        notional,
        field_name="notional",
    ) * ensure_rate(rate, field_name="rate")
