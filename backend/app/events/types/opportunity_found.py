from app.events.base_event import BaseEvent


class OpportunityFoundEvent(BaseEvent):

    def __init__(self, opportunity):

        super().__init__(

            name="OpportunityFound",

            payload=opportunity

        )