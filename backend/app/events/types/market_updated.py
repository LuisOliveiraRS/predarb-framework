from app.events.base_event import BaseEvent


class MarketUpdatedEvent(BaseEvent):

    def __init__(self, market):

        super().__init__(

            name="MarketUpdated",

            payload=market

        )