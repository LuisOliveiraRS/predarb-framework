from app.strategies.strategy_manager import (
    strategy_manager
)


class SignalStage:

    def execute(

        self,

        context

    ):

        context.signal = (

            strategy_manager.generate_signal(

                context.market_snapshot

            )

        )

        return context