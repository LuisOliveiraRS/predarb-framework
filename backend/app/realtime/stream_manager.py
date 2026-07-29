class StreamManager:

    def __init__(self):

        self.channels = {

            "markets": [],

            "opportunities": [],

            "orders": [],

            "portfolio": [],

            "signals": [],

            "ai": []

        }

    def publish(

        self,

        channel,

        data

    ):

        if channel in self.channels:

            self.channels[channel].append(data)


stream_manager = StreamManager()