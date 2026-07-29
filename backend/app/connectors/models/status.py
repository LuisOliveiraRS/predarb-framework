from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ConnectorStatus:
    """
    Estado operacional padronizado
    de um conector.
    """

    name: str

    connected: bool = False

    last_update: datetime | str | None = None

    markets: int = 0

    latency: float = 0.0

    error: str | None = None

    details: dict[str, Any] = field(
        default_factory=dict,
    )

    @property
    def status(self) -> str:
        """
        Retorna uma classificação textual estável.
        """

        if self.error:
            return "error"

        if self.connected:
            return "online"

        return "offline"

    def to_dict(
        self,
    ) -> dict[str, Any]:
        """
        Converte o estado para um payload
        serializável pela API.
        """

        if isinstance(
            self.last_update,
            datetime,
        ):
            last_update: str | None = (
                self.last_update.isoformat()
            )

        elif self.last_update is None:
            last_update = None

        else:
            last_update = str(
                self.last_update
            )

        latency = round(
            max(
                0.0,
                float(self.latency),
            ),
            3,
        )

        return {
            "name": self.name,
            "connector": self.name,
            "status": self.status,
            "connected": bool(
                self.connected
            ),
            "last_update": last_update,
            "markets": max(
                0,
                int(self.markets),
            ),
            "latency": latency,
            "latency_ms": latency,
            "error": self.error,
            "details": dict(
                self.details
            ),
        }