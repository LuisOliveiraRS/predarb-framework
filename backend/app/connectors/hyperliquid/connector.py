from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.connectors.base.connector import (
    BaseConnector,
)
from app.connectors.models.status import (
    ConnectorStatus,
)
from app.parsers.hyperliquid import (
    HyperliquidParser,
    hyperliquid_parser,
)
from app.providers.hyperliquid_provider import (
    HyperliquidProvider,
    hyperliquid_provider,
)


class HyperliquidConnector(BaseConnector):
    """
    Conector oficial para mercados HIP-4
    da Hyperliquid.
    """

    name = "hyperliquid"

    def __init__(
        self,
        *,
        provider: HyperliquidProvider | None = None,
        parser: HyperliquidParser | None = None,
    ) -> None:
        self.provider = (
            provider
            or hyperliquid_provider
        )

        self.parser = (
            parser
            or hyperliquid_parser
        )

        self.connected = False
        self.last_update = None
        self.market_count = 0

        self._last_error: str | None = None
        self._last_details: dict[str, Any] = {}

    @staticmethod
    def _is_connected(
        health_result: Any,
    ) -> bool:
        """
        Interpreta respostas distintas de health.
        """

        if isinstance(
            health_result,
            ConnectorStatus,
        ):
            return health_result.connected

        if isinstance(
            health_result,
            Mapping,
        ):
            connected = health_result.get(
                "connected"
            )

            if isinstance(
                connected,
                bool,
            ):
                return connected

            status = str(
                health_result.get(
                    "status",
                    "",
                )
            ).strip().lower()

            return status in {
                "online",
                "healthy",
                "connected",
                "ok",
            }

        return bool(health_result)

    async def connect(
        self,
    ) -> bool:
        """
        Valida conectividade com a API.
        """

        health_result = (
            await self.provider.health()
        )

        connected = self._is_connected(
            health_result
        )

        self.mark_connected(
            connected
        )

        if isinstance(
            health_result,
            Mapping,
        ):
            self._last_details = dict(
                health_result
            )

            error = health_result.get(
                "error"
            )

            if error:
                self.mark_error(
                    str(error)
                )

        if not connected and not self._last_error:
            self.mark_error(
                "A Hyperliquid não respondeu "
                "ao health check."
            )

        return connected

    async def disconnect(
        self,
    ) -> bool:
        """
        Libera recursos externos.
        """

        try:
            await self.provider.close()

        finally:
            self.mark_connected(
                False
            )

        return True

    async def health(
        self,
    ) -> ConnectorStatus:
        """
        Retorna um diagnóstico padronizado.
        """

        result = await self.provider.health()

        connected = self._is_connected(
            result
        )

        self.mark_connected(
            connected
        )

        status = self.get_status()

        if isinstance(
            result,
            Mapping,
        ):
            details = dict(result)
            details.update(
                self._last_details
            )

            status.details = details

            raw_error = result.get(
                "error"
            )

            status.error = (
                str(raw_error)
                if raw_error
                else self._last_error
            )

            raw_latency = result.get(
                "latency",
                0.0,
            )

            try:
                status.latency = float(
                    raw_latency
                )

            except (
                TypeError,
                ValueError,
            ):
                status.latency = 0.0

        return status

    async def get_markets(
        self,
    ) -> list[dict[str, Any]]:
        """
        Coleta e normaliza mercados HIP-4.
        """

        try:
            snapshot = (
                await self.provider.get_all_markets()
            )

            markets = self.parser.parse(
                snapshot
            )

        except Exception as exc:
            self.mark_error(
                exc
            )

            raise

        self.mark_connected(
            True
        )

        self.mark_updated(
            len(markets)
        )

        metadata = snapshot.get(
            "metadata",
            {},
        )

        mids = snapshot.get(
            "mids",
            {},
        )

        outcomes = (
            metadata.get(
                "outcomes",
                [],
            )
            if isinstance(
                metadata,
                Mapping,
            )
            else []
        )

        self._last_details = {
            "outcomes_discovered": (
                len(outcomes)
                if isinstance(outcomes, list)
                else 0
            ),
            "assets_with_mids": (
                len(mids)
                if isinstance(mids, Mapping)
                else 0
            ),
            "markets_parsed": len(markets),
            "metadata_error": snapshot.get(
                "metadata_error"
            ),
        }

        return markets