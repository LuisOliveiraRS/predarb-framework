from app.strategies.strategy_registry import strategy_registry

from app.strategies.implementations.arbitrage_strategy import arbitrage_strategy
from app.strategies.implementations.liquidity_strategy import liquidity_strategy
from app.strategies.implementations.momentum_strategy import momentum_strategy
from app.strategies.implementations.mean_reversion_strategy import mean_reversion_strategy


class StrategyManager:

    def initialize(self):

        strategy_registry.register(
            arbitrage_strategy
        )

        strategy_registry.register(
            liquidity_strategy
        )

        strategy_registry.register(
            momentum_strategy
        )

        strategy_registry.register(
            mean_reversion_strategy
        )


strategy_manager = StrategyManager()