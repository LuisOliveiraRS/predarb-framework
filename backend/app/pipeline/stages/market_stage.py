
from app.services.market_listener import market_listener

class MarketStage:

    def execute(

        self,

        context

    ):

        context.market_snapshot = (

            market_listener.snapshot()

        )

        return context