import pytest

from app.market_engine.market_engine import MarketEngine


class AsyncConnector:
    name = "async-mock"

    async def get_markets(self):
        return [
            {
                "question": "Bitcoin acima de 150k?",
                "platform": "mock",
                "yes_price": 0.40,
                "no_price": 0.50,
            }
        ]


@pytest.mark.asyncio
async def test_market_engine_accepts_canonical_async_connector():
    engine = MarketEngine()
    markets = await engine.update_async([AsyncConnector()])

    assert len(markets) == 1
    assert markets[0]["question"] == "Bitcoin acima de 150k?"
