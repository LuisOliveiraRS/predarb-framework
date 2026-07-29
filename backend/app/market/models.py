from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Market:
    """
    Modelo unificado de um mercado preditivo.

    Toda a aplicação trabalha exclusivamente
    com objetos desta classe.
    """

    platform: str

    question: str

    yes: float

    no: float

    created_at: datetime

    connector: str

    liquidity: float = 0.0

    volume: float = 0.0

    fee: float = 0.0

    market_id: str = ""

    category: str = ""

    asset: str = ""

    event_type: str = ""

    expires_at: datetime | None = None

    status: str = "open"

    metadata: dict[str, Any] = field(default_factory=dict)