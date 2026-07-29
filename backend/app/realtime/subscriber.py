class Subscriber:

    def subscribe(

        self,

        channel

    ):

        return {

            "channel": channel,

            "status": "subscribed"

        }


subscriber = Subscriber()