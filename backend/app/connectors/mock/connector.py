from __future__ import annotations

from datetime import datetime, timezone
from random import Random
from typing import Any

from app.connectors.base.connector import (
    BaseConnector,
)
from app.connectors.models.status import (
    ConnectorStatus,
)


class MockConnector(BaseConnector):
    """
    Conector de simulação para desenvolvimento,
    testes do comparador e paper trading.

    Ele continua retornando dicionários para
    preservar compatibilidade com o fluxo atual.
    """

    name = "mock"

    QUESTION = (
        "Bitcoin acima de US$ 150 mil em 2026?"
    )

    BASE_PRICES = {
        "Hyperliquid Mock": 0.44,
        "Opinion Mock": 0.48,
        "Limitless Mock": 0.53,
        "Triad Mock": 0.56,
        "GateDEX Mock": 0.50,
    }

    def __init__(
        self,
        *,
        seed: int | None = None,
    ) -> None:
        self._random = Random(seed)

        self.connected = False
        self.last_update = None
        self.market_count = 0

        self._last_error: str | None = None

    async def connect(
        self,
    ) -> bool:
        """
        Ativa o conector simulado.
        """

        self.mark_connected(
            True
        )

        return True

    async def disconnect(
        self,
    ) -> bool:
        """
        Desativa o conector simulado.
        """

        self.mark_connected(
            False
        )

        return True

    async def health(
        self,
    ) -> ConnectorStatus:
        """
        Retorna o estado do simulador.
        """

        status = self.get_status()

        status.details = {
            "mode": "simulation",
            "platforms": len(
                self.BASE_PRICES
            ),
        }

        return status

    def _build_market(
        self,
        platform: str,
        base_yes: float,
        created_at: str,
    ) -> dict[str, Any]:
        """
        Constrói um mercado simulado coerente.

        O preço No é complementar ao preço Yes.
        """

        jitter = self._random.uniform(
            -0.008,
            0.008,
        )

        yes_price = round(
            min(
                0.99,
                max(
                    0.01,
                    base_yes + jitter,
                ),
            ),
            3,
        )

        no_price = round(
            1.0 - yes_price,
            3,
        )

        liquidity = round(
            self._random.uniform(
                500.0,
                5_000.0,
            ),
            2,
        )

        volume = round(
            self._random.uniform(
                1_000.0,
                25_000.0,
            ),
            2,
        )

        platform_id = (
            platform
            .lower()
            .replace(" ", "-")
        )

        return {
            "platform": platform,
            "connector": self.name,
            "question": self.QUESTION,
            "yes": yes_price,
            "no": no_price,
            "liquidity": liquidity,
            "volume": volume,
            "fee": 0.0,
            "market_id": (
                f"mock:{platform_id}"
            ),
            "category": "crypto",
            "asset": "BTC",
            "event_type": "price_binary",
            "status": "open",
            "created_at": created_at,
            "metadata": {
                "simulated": True,
            },
        }

    async def get_markets(
        self,
    ) -> list[dict[str, Any]]:
        """
        Gera mercados simulados.
        """

        if not self.connected:
            await self.connect()

        created_at = datetime.now(
            timezone.utc,
        ).isoformat()

        markets = [
            self._build_market(
                platform,
                base_yes,
                created_at,
            )
            for platform, base_yes
            in self.BASE_PRICES.items()
        ]

        self.mark_updated(
            len(markets)
        )

        return markets