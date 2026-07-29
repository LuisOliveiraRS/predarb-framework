from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.positions.position_status import PositionStatus
from app.utils.time import utc_now


@dataclass
class Position:
    """Posição oficial do módulo ``app.positions``.

    O modelo consolida os campos das duas definições antigas que coexistiam
    neste arquivo. Os atributos legados permanecem disponíveis para os
    factories, serializadores e publishers existentes.
    """

    id: str = field(default_factory=lambda: str(uuid4()))
    platform: str = ""
    question: str = ""
    side: str = ""
    quantity: float = 0.0
    average_price: float = 0.0
    created_at: datetime = field(default_factory=utc_now)
    closed_at: datetime | None = None
    status: PositionStatus = PositionStatus.OPEN
    pnl: float = 0.0
    roi: float = 0.0
    fees: float = 0.0
    strategy: str = ""
    execution_id: str | None = None

    # Compatibilidade com o primeiro contrato histórico.
    yes_price: float = 0.0
    no_price: float = 0.0
    expected_profit: float = 0.0
    exchange_latency: float = 0.0
    orders: list[Any] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def closed(self) -> bool:
        return self.status == PositionStatus.CLOSED

    @closed.setter
    def closed(self, value: bool) -> None:
        self.status = (
            PositionStatus.CLOSED
            if bool(value)
            else PositionStatus.OPEN
        )
        if value and self.closed_at is None:
            self.closed_at = utc_now()
        elif not value:
            self.closed_at = None
