from app.events.base_event import BaseEvent


class RiskCalculatedEvent(BaseEvent):

    def __init__(self, opportunity):

        super().__init__(

            name="RiskCalculated",

            payload=opportunity

        )