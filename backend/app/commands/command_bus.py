from app.commands.command_registry import command_registry


class CommandBus:

    """
    Executa Commands.
    """

    def dispatch(self, command):

        handler = command_registry.handler(

            command.name

        )

        if handler is None:

            return None

        return handler(command)


command_bus = CommandBus()