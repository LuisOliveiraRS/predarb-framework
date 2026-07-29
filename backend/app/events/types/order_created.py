from app.events.base_event import BaseEvent


class OrderCreatedEvent(BaseEvent):

    def __init__(self, order):

        super().__init__(

            name="OrderCreated",

            payload=order

        )