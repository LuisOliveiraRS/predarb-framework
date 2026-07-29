from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.market_engine.cache import market_cache
from app.market_engine.collector import market_collector
from app.market_engine.deduplicator import market_deduplicator
from app.market_engine.normalizer import market_normalizer
from app.market_engine.publisher import market_publisher
from app.market_engine.validator import market_validator


class MarketEngine:
    """Pipeline legado compatível para processamento de mercados.

    A persistência oficial continua sendo responsabilidade do
    ``ConnectorManager`` e do ``MarketRepository``. Este engine somente
    normaliza, valida, deduplica, armazena em cache e publica snapshots.
    """

    @staticmethod
    def _process(markets: list[Any]) -> list[Any]:
        processed = market_normalizer.normalize(markets)
        processed = market_validator.validate(processed)
        processed = market_deduplicator.process(processed)
        market_cache.update(processed)
        market_publisher.publish_markets(processed)
        return processed

    def update(self, connectors: Iterable[Any]) -> list[Any]:
        return self._process(market_collector.collect(connectors))

    async def update_async(self, connectors: Iterable[Any]) -> list[Any]:
        return self._process(await market_collector.collect_async(connectors))


market_engine = MarketEngine()
