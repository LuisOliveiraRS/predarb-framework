from app.commands.base_command import BaseCommand


class CancelOrderCommand(BaseCommand):

    def __init__(self, order):

        super().__init__(

            name="CancelOrder",

            payload=order

        )