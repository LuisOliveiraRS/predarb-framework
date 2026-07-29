from app.commands.command_registry import command_registry


class CommandHandlers:

    def initialize(self):

        #
        # Exemplo
        #

        command_registry.register(

            "CreateOrder",

            self.create_order

        )

    def create_order(self, command):

        print(

            "Executando Ordem:",

            command.payload

        )


command_handlers = CommandHandlers()