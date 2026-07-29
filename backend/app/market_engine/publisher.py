from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

from app.realtime.connection_manager import connection_manager
from app.realtime.messages import RealtimeMessage


class Publisher:
    """Publica mensagens no WebSocket sem exigir um loop durante imports."""

    def _publish(self, message: dict[str, Any]) -> bool:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False

        loop.create_task(connection_manager.broadcast(message))
        return True

    def publish_market(self, market: Any) -> bool:
        return self._publish(RealtimeMessage.market(market))

    def publish_markets(self, markets: Iterable[Any]) -> int:
        return sum(1 for market in markets if self.publish_market(market))

    def publish_opportunity(self, opportunity: Any) -> bool:
        return self._publish(RealtimeMessage.opportunity(opportunity))

    def publish_position(self, position: Any) -> bool:
        return self._publish(RealtimeMessage.position(position))


publisher = Publisher()

# Alias de compatibilidade com o MarketEngine histórico.
market_publisher = publisher
