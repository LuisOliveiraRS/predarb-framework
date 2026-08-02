"""Medição de latência de dados de mercado.

Seção 14 do CLAUDE.md pede `exchange_to_receive_latency_ms` e
`local_processing_latency_ms` como métricas observáveis.

A janela é limitada de propósito: latência de dez minutos atrás
não ajuda a decidir agora, e acumular amostras indefinidamente
num processo de vida longa é vazamento de memória disfarçado de
observabilidade.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from typing import Any

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
)
from app.crypto_arbitrage.domain.money import (
    DecimalInput,
    to_decimal,
)


class LatencyTracker:
    """Estatísticas de uma janela deslizante de amostras."""

    def __init__(
        self,
        *,
        window: int = 256,
        label: str = "latency",
    ) -> None:
        if int(window) <= 0:
            raise DomainValidationError(
                "window deve ser maior que zero."
            )

        self.window = int(window)
        self.label = str(label or "latency").strip()
        self._samples: deque[Decimal] = deque(
            maxlen=self.window
        )
        self._total_observed = 0

    def record(self, value_ms: DecimalInput) -> Decimal:
        """Registra uma amostra em milissegundos.

        Valores negativos são aceitos e preservados: representam
        divergência de relógio entre venue e host, que é um
        sintoma real e não deve ser escondido por um `max(0, x)`.
        """

        sample = to_decimal(
            value_ms,
            field_name=f"{self.label}_ms",
        )

        self._samples.append(sample)
        self._total_observed += 1

        return sample

    @property
    def count(self) -> int:
        return len(self._samples)

    @property
    def total_observed(self) -> int:
        return self._total_observed

    @property
    def last(self) -> Decimal | None:
        return self._samples[-1] if self._samples else None

    @property
    def minimum(self) -> Decimal | None:
        return min(self._samples) if self._samples else None

    @property
    def maximum(self) -> Decimal | None:
        return max(self._samples) if self._samples else None

    @property
    def average(self) -> Decimal | None:
        if not self._samples:
            return None

        return sum(self._samples) / Decimal(
            len(self._samples)
        )

    def percentile(self, ratio: str) -> Decimal | None:
        """Percentil por posição, sem interpolação.

        `ratio` como string para não introduzir float num módulo
        cuja razão de existir é medir com precisão.
        """

        if not self._samples:
            return None

        fraction = to_decimal(
            ratio,
            field_name="ratio",
        )

        if not Decimal("0") < fraction <= Decimal("1"):
            raise DomainValidationError(
                "ratio deve estar entre 0 (exclusivo) e 1."
            )

        ordered = sorted(self._samples)

        position = int(
            (
                fraction * Decimal(len(ordered))
            ).to_integral_value(rounding="ROUND_CEILING")
        )

        index = max(0, min(position - 1, len(ordered) - 1))

        return ordered[index]

    def reset(self) -> None:
        self._samples.clear()

    def to_dict(self) -> dict[str, Any]:
        def render(value: Decimal | None) -> str | None:
            return str(value) if value is not None else None

        return {
            "label": self.label,
            "window": self.window,
            "count": self.count,
            "total_observed": self.total_observed,
            "last_ms": render(self.last),
            "min_ms": render(self.minimum),
            "max_ms": render(self.maximum),
            "avg_ms": render(self.average),
            "p95_ms": render(self.percentile("0.95")),
        }
