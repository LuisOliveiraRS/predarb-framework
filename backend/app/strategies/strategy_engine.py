from app.strategies.strategy_registry import strategy_registry


class StrategyEngine:
    """
    Executa todas as estratégias registradas.
    """

    def execute(self, opportunities):

        result = []

        for strategy in strategy_registry.enabled():

            result.extend(

                strategy.analyze(

                    opportunities

                )

            )

        return result


strategy_engine = StrategyEngine()