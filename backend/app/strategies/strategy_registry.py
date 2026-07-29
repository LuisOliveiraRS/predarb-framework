class StrategyRegistry:

    def __init__(self):

        self._strategies = {}

    def register(self, strategy):

        self._strategies[strategy.name] = strategy

    def all(self):

        return list(self._strategies.values())

    def enabled(self):

        return [

            strategy

            for strategy in self._strategies.values()

            if strategy.enabled()

        ]


strategy_registry = StrategyRegistry()