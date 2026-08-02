"""Rate limiting local por token bucket.

Seção 14 do CLAUDE.md: respeitar rate limits e expor
`connector_rate_limit_total`.

O limitador é local e preventivo. Ele não substitui o limite da
venue — apenas evita chegar nele. Ser bloqueado pela exchange
custa muito mais do que esperar aqui: costuma vir com banimento
temporário de IP, e nesse intervalo o book inteiro fica sem
atualização.

O relógio é injetado. Um limitador que só pode ser testado
esperando de verdade não é testado.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
)
from app.crypto_arbitrage.domain.money import (
    ZERO,
    DecimalInput,
    ensure_positive,
    to_decimal,
)


Clock = Callable[[], Decimal]


class TokenBucketRateLimiter:
    """Balde de tokens com reposição contínua."""

    def __init__(
        self,
        *,
        capacity: DecimalInput = "10",
        refill_per_second: DecimalInput = "5",
        clock: Clock | None = None,
        label: str = "rate_limit",
    ) -> None:
        self.capacity = ensure_positive(
            capacity,
            field_name="capacity",
        )

        self.refill_per_second = ensure_positive(
            refill_per_second,
            field_name="refill_per_second",
        )

        self.label = str(label or "rate_limit").strip()
        self._clock = clock or _default_clock
        self._tokens = self.capacity
        self._last_refill = self._now()

        self.allowed_total = 0
        self.rejected_total = 0

    def _now(self) -> Decimal:
        value = self._clock()

        return to_decimal(
            value,
            field_name="clock",
        )

    def _refill(self) -> None:
        now = self._now()
        elapsed = now - self._last_refill

        if elapsed < ZERO:
            # Relogio andou para tras. Nao repoe, mas tambem nao
            # castiga: apenas realinha a referencia.
            self._last_refill = now
            return

        self._tokens = min(
            self.capacity,
            self._tokens + elapsed * self.refill_per_second,
        )

        self._last_refill = now

    @property
    def available_tokens(self) -> Decimal:
        self._refill()

        return self._tokens

    def try_acquire(
        self,
        tokens: DecimalInput = "1",
    ) -> bool:
        """Consome tokens se houver. Nunca bloqueia."""

        requested = ensure_positive(
            tokens,
            field_name="tokens",
        )

        if requested > self.capacity:
            raise DomainValidationError(
                "Requisição maior que a capacidade do balde "
                "nunca seria atendida."
            )

        self._refill()

        if self._tokens < requested:
            self.rejected_total += 1
            return False

        self._tokens -= requested
        self.allowed_total += 1

        return True

    def seconds_until_available(
        self,
        tokens: DecimalInput = "1",
    ) -> Decimal:
        """Espera necessária para o próximo `try_acquire` passar."""

        requested = ensure_positive(
            tokens,
            field_name="tokens",
        )

        self._refill()

        missing = requested - self._tokens

        if missing <= ZERO:
            return ZERO

        return missing / self.refill_per_second

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "capacity": str(self.capacity),
            "refill_per_second": str(
                self.refill_per_second
            ),
            "available_tokens": str(self.available_tokens),
            "allowed_total": self.allowed_total,
            "rejected_total": self.rejected_total,
        }


def _default_clock() -> Decimal:
    from time import monotonic

    return to_decimal(
        str(monotonic()),
        field_name="monotonic",
    )
