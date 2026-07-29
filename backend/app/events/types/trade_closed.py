from app.events.base_event import BaseEvent


class TradeClosedEvent(BaseEvent):

    def __init__(self, trade):

        super().__init__(

            name="TradeClosed",

            payload=trade

        )