"""Métricas observáveis por conector de dados.

Nomes alinhados à seção 14 do CLAUDE.md:

```text
market_data_messages_total
market_data_gap_total
market_data_reconnect_total
orderbook_age_ms
exchange_to_receive_latency_ms
local_processing_latency_ms
connector_error_total
connector_rate_limit_total
```

Contadores separam causas em vez de agregar num "erro". Depois de
um incidente, a diferença entre gap de sequência, book corrompido
e falha de transporte é exatamente o que decide onde olhar.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.crypto_arbitrage.domain.enums import ConnectorState
from app.crypto_arbitrage.market_data.latency import (
    LatencyTracker,
)
from app.crypto_arbitrage.domain.money import (
    DecimalInput,
    to_decimal,
)


class ConnectorMetrics:
    """Contadores e latências de um conector."""

    def __init__(
        self,
        venue_id: str,
        *,
        latency_window: int = 256,
    ) -> None:
        self.venue_id = str(venue_id or "").strip().upper()

        self.messages_total = 0
        self.snapshots_total = 0
        self.deltas_applied_total = 0
        self.deltas_ignored_total = 0
        self.gap_total = 0
        self.corrupted_total = 0
        self.reconnect_total = 0
        self.error_total = 0
        self.rate_limit_total = 0

        self.exchange_to_receive = LatencyTracker(
            window=latency_window,
            label="exchange_to_receive",
        )

        self.local_processing = LatencyTracker(
            window=latency_window,
            label="local_processing",
        )

        self.last_orderbook_age_ms: Decimal | None = None
        self.last_message_at: datetime | None = None
        self.last_error: str | None = None
        self.state = ConnectorState.DISCONNECTED

    def record_message(
        self,
        *,
        received_at: datetime | None = None,
    ) -> None:
        self.messages_total += 1

        if received_at is not None:
            self.last_message_at = received_at

    def record_snapshot(self) -> None:
        self.snapshots_total += 1

    def record_delta_applied(self) -> None:
        self.deltas_applied_total += 1

    def record_delta_ignored(self) -> None:
        self.deltas_ignored_total += 1

    def record_gap(self, detail: str = "") -> None:
        self.gap_total += 1
        self.state = ConnectorState.DEGRADED

        if detail:
            self.last_error = detail

    def record_corrupted(self, detail: str = "") -> None:
        self.corrupted_total += 1
        self.state = ConnectorState.DEGRADED

        if detail:
            self.last_error = detail

    def record_reconnect(self) -> None:
        self.reconnect_total += 1

    def record_error(self, detail: str = "") -> None:
        self.error_total += 1

        if detail:
            self.last_error = detail

    def record_rate_limit(self) -> None:
        self.rate_limit_total += 1

    def record_exchange_latency(
        self,
        value_ms: DecimalInput,
    ) -> None:
        self.exchange_to_receive.record(value_ms)

    def record_processing_latency(
        self,
        value_ms: DecimalInput,
    ) -> None:
        self.local_processing.record(value_ms)

    def record_orderbook_age(
        self,
        value_ms: DecimalInput,
    ) -> None:
        self.last_orderbook_age_ms = to_decimal(
            value_ms,
            field_name="orderbook_age_ms",
        )

    def set_state(self, state: ConnectorState) -> None:
        self.state = state

    @property
    def is_healthy(self) -> bool:
        """Saudável exige estado utilizável e nenhum resync aberto.

        Contadores acumulados não derrubam a saúde: um gap
        resolvido por resync há uma hora não deve manter o
        conector marcado como doente para sempre. O estado atual
        é que decide.
        """

        return self.state.is_usable

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "state": self.state.value,
            "is_healthy": self.is_healthy,
            "market_data_messages_total": (
                self.messages_total
            ),
            "market_data_snapshots_total": (
                self.snapshots_total
            ),
            "market_data_deltas_applied_total": (
                self.deltas_applied_total
            ),
            "market_data_deltas_ignored_total": (
                self.deltas_ignored_total
            ),
            "market_data_gap_total": self.gap_total,
            "market_data_corrupted_total": (
                self.corrupted_total
            ),
            "market_data_reconnect_total": (
                self.reconnect_total
            ),
            "connector_error_total": self.error_total,
            "connector_rate_limit_total": (
                self.rate_limit_total
            ),
            "orderbook_age_ms": (
                str(self.last_orderbook_age_ms)
                if self.last_orderbook_age_ms is not None
                else None
            ),
            "exchange_to_receive_latency_ms": (
                self.exchange_to_receive.to_dict()
            ),
            "local_processing_latency_ms": (
                self.local_processing.to_dict()
            ),
            "last_message_at": (
                self.last_message_at.isoformat()
                if self.last_message_at is not None
                else None
            ),
            "last_error": self.last_error,
            "market_data_only": True,
            "read_only": True,
        }
