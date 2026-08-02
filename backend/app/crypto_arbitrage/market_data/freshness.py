"""Política de frescor de dados de mercado.

Invariante 14 da seção 8 do CLAUDE.md: book stale não pode gerar
ordem. Aqui a regra vira objeto, para que a decisão seja a mesma
em todo lugar e possa ser auditada.

A avaliação nunca devolve apenas um booleano: devolve o motivo,
porque "por que esta oportunidade foi descartada" é a pergunta
que se faz depois, e reconstruí-la a partir de um `False` é
impossível.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.crypto_arbitrage.domain.enums import ConnectorState
from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    StaleMarketDataError,
)
from app.crypto_arbitrage.domain.models import (
    OrderBookSnapshot,
)
from app.crypto_arbitrage.domain.money import (
    DecimalInput,
    ensure_positive,
    to_decimal,
)


@dataclass(frozen=True, slots=True)
class FreshnessVerdict:
    """Resultado de uma avaliação de frescor."""

    is_fresh: bool
    age_ms: Decimal
    limit_ms: Decimal
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_fresh": self.is_fresh,
            "age_ms": str(self.age_ms),
            "limit_ms": str(self.limit_ms),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class FreshnessPolicy:
    """Idade máxima tolerada para um book alimentar decisão.

    `max_clock_skew_ms` trata do caso em que o timestamp da venue
    está adiantado em relação ao relógio local. Uma idade
    negativa não é "dado muito novo": é divergência de relógio, e
    além da folga tolerada invalida o dado, porque não se sabe
    mais qual dos dois relógios mentiu.
    """

    max_age_ms: Decimal
    max_clock_skew_ms: Decimal

    @classmethod
    def create(
        cls,
        max_age_ms: DecimalInput = 1000,
        max_clock_skew_ms: DecimalInput = 500,
    ) -> "FreshnessPolicy":
        return cls(
            max_age_ms=ensure_positive(
                max_age_ms,
                field_name="max_age_ms",
            ),
            max_clock_skew_ms=ensure_positive(
                max_clock_skew_ms,
                field_name="max_clock_skew_ms",
            ),
        )

    def evaluate(
        self,
        snapshot: OrderBookSnapshot,
        now: datetime,
    ) -> FreshnessVerdict:
        if now.tzinfo is None:
            raise DomainValidationError(
                "now deve ter timezone."
            )

        age_ms = snapshot.age_ms(now)

        if age_ms < -self.max_clock_skew_ms:
            return FreshnessVerdict(
                is_fresh=False,
                age_ms=age_ms,
                limit_ms=self.max_age_ms,
                reason=(
                    "Timestamp no futuro além da folga de "
                    f"relógio ({self.max_clock_skew_ms}ms)."
                ),
            )

        if age_ms > self.max_age_ms:
            return FreshnessVerdict(
                is_fresh=False,
                age_ms=age_ms,
                limit_ms=self.max_age_ms,
                reason=(
                    f"Book com {age_ms}ms excede o limite "
                    f"de {self.max_age_ms}ms."
                ),
            )

        return FreshnessVerdict(
            is_fresh=True,
            age_ms=age_ms,
            limit_ms=self.max_age_ms,
            reason="Book dentro da janela de frescor.",
        )

    def require_fresh(
        self,
        snapshot: OrderBookSnapshot,
        now: datetime,
    ) -> FreshnessVerdict:
        verdict = self.evaluate(snapshot, now)

        if not verdict.is_fresh:
            raise StaleMarketDataError(
                f"{snapshot.venue_id}/"
                f"{snapshot.instrument_id}: "
                f"{verdict.reason}"
            )

        return verdict


def is_usable_for_pricing(
    snapshot: OrderBookSnapshot,
    state: ConnectorState,
    policy: FreshnessPolicy,
    now: datetime,
) -> FreshnessVerdict:
    """Combina saúde do conector e frescor do dado.

    Um book recente vindo de conector degradado não é utilizável:
    a idade só prova que a última mensagem chegou há pouco, não
    que o livro reflete a venue.
    """

    if not state.is_usable:
        return FreshnessVerdict(
            is_fresh=False,
            age_ms=snapshot.age_ms(now),
            limit_ms=policy.max_age_ms,
            reason=(
                f"Conector em estado {state.value}, "
                "não utilizável para precificação."
            ),
        )

    return policy.evaluate(snapshot, now)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def milliseconds_between(
    start: datetime,
    end: datetime,
) -> Decimal:
    """Diferença em milissegundos, como Decimal."""

    for name, value in (("start", start), ("end", end)):
        if value.tzinfo is None:
            raise DomainValidationError(
                f"{name} deve ter timezone."
            )

    delta = end - start

    return to_decimal(
        str(delta.total_seconds() * 1000),
        field_name="milliseconds",
    )
