from app.plugins.base import BasePlugin


class MockMarketPlugin(BasePlugin):

    name = "mock_market"
    version = "1.0.0"


    def start(self):

        print(
            "Mock Market iniciado"
        )


    def stop(self):

        print(
            "Mock Market encerrado"
        )


    def health(self):

        return {
            "plugin": self.name,
            "status": "running"
        }


    def markets(self):

        return [
            {
                "question":
                "Bitcoin acima de 150k em 2026?",

                "yes": 0.62,

                "no": 0.38
            }
        ]