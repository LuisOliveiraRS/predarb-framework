from app.events.base_event import BaseEvent


class OrderExecutedEvent(BaseEvent):

    def __init__(self, order):

        super().__init__(

            name="OrderExecuted",

            payload=order

        )