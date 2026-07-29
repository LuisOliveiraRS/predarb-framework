class CommandRegistry:

    def __init__(self):

        self.handlers = {}

    def register(

        self,

        command_name,

        handler

    ):

        self.handlers[command_name] = handler

    def handler(self, command_name):

        return self.handlers.get(command_name)


command_registry = CommandRegistry()