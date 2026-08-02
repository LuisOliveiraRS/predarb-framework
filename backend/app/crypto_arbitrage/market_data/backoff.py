"""Política de reconexão com backoff exponencial e jitter.

Seção 14 do CLAUDE.md: reconectar com backoff e jitter.

O jitter não é detalhe estético. Sem ele, todos os conectores que
caírem juntos — o caso comum, porque a queda costuma ser da rede
local e não da venue — voltam juntos, e a rajada sincronizada
tende a derrubar de novo ou a estourar rate limit.

A aleatoriedade entra como parâmetro, não como chamada interna a
`random`. Uma política de reconexão que não pode ser reproduzida
num teste é uma política que ninguém consegue auditar depois de
um incidente.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
)
from app.crypto_arbitrage.domain.money import (
    ZERO,
    DecimalInput,
    ensure_positive,
    to_decimal,
)


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    """Cálculo determinístico do atraso entre tentativas."""

    initial_seconds: Decimal
    maximum_seconds: Decimal
    multiplier: Decimal
    jitter_ratio: Decimal

    @classmethod
    def create(
        cls,
        *,
        initial_seconds: DecimalInput = "1",
        maximum_seconds: DecimalInput = "60",
        multiplier: DecimalInput = "2",
        jitter_ratio: DecimalInput = "0.25",
    ) -> "BackoffPolicy":
        initial = ensure_positive(
            initial_seconds,
            field_name="initial_seconds",
        )

        maximum = ensure_positive(
            maximum_seconds,
            field_name="maximum_seconds",
        )

        if maximum < initial:
            raise DomainValidationError(
                "maximum_seconds não pode ser menor que "
                "initial_seconds."
            )

        factor = to_decimal(
            multiplier,
            field_name="multiplier",
        )

        if factor < Decimal("1"):
            raise DomainValidationError(
                "multiplier deve ser pelo menos 1."
            )

        jitter = to_decimal(
            jitter_ratio,
            field_name="jitter_ratio",
        )

        if not ZERO <= jitter <= Decimal("1"):
            raise DomainValidationError(
                "jitter_ratio deve estar entre 0 e 1."
            )

        return cls(
            initial_seconds=initial,
            maximum_seconds=maximum,
            multiplier=factor,
            jitter_ratio=jitter,
        )

    def base_delay(self, attempt: int) -> Decimal:
        """Atraso sem jitter, já limitado pelo teto."""

        index = int(attempt)

        if index < 1:
            raise DomainValidationError(
                "attempt começa em 1."
            )

        delay = self.initial_seconds * (
            self.multiplier ** (index - 1)
        )

        return min(delay, self.maximum_seconds)

    def delay_for(
        self,
        attempt: int,
        *,
        random_value: DecimalInput = "1",
    ) -> Decimal:
        """Atraso final, com jitter aplicado para baixo.

        `random_value` vai de 0 a 1. O jitter só reduz o atraso,
        nunca o aumenta: passar do teto configurado por causa de
        sorteio seria surpresa desnecessária em incidente.
        """

        sample = to_decimal(
            random_value,
            field_name="random_value",
        )

        if not ZERO <= sample <= Decimal("1"):
            raise DomainValidationError(
                "random_value deve estar entre 0 e 1."
            )

        base = self.base_delay(attempt)

        scale = (
            Decimal("1")
            - self.jitter_ratio
            + self.jitter_ratio * sample
        )

        return base * scale


class ReconnectTracker:
    """Contador de tentativas com reinício explícito."""

    def __init__(
        self,
        policy: BackoffPolicy | None = None,
    ) -> None:
        self.policy = policy or BackoffPolicy.create()
        self.attempt = 0
        self.total_reconnects = 0

    def next_delay(
        self,
        *,
        random_value: DecimalInput = "1",
    ) -> Decimal:
        self.attempt += 1
        self.total_reconnects += 1

        return self.policy.delay_for(
            self.attempt,
            random_value=random_value,
        )

    def reset(self) -> None:
        """Zera a escalada após uma conexão saudável.

        Só deve ser chamado depois de a conexão provar que
        funciona — tipicamente após o primeiro snapshot aplicado.
        Zerar ao conectar faria uma queda em laço parecer sempre
        a primeira tentativa.
        """

        self.attempt = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "attempt": self.attempt,
            "total_reconnects": self.total_reconnects,
            "initial_seconds": str(
                self.policy.initial_seconds
            ),
            "maximum_seconds": str(
                self.policy.maximum_seconds
            ),
            "multiplier": str(self.policy.multiplier),
            "jitter_ratio": str(self.policy.jitter_ratio),
        }
