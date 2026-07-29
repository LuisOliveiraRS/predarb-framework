from app.commands.base_command import BaseCommand


class CreateOrderCommand(BaseCommand):

    def __init__(self, order):

        super().__init__(

            name="CreateOrder",

            payload=order

        )