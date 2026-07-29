from fastapi import WebSocket


class ConnectionManager:
    """
    Gerencia todas as conexões WebSocket
    ativas do Dashboard.
    """

    def __init__(self):

        self.connections = []

    async def connect(self, websocket: WebSocket):

        await websocket.accept()

        self.connections.append(websocket)

        print(
            f"Cliente conectado ({len(self.connections)})"
        )

    def disconnect(self, websocket: WebSocket):

        if websocket in self.connections:

            self.connections.remove(websocket)

            print(
                f"Cliente desconectado ({len(self.connections)})"
            )

    async def broadcast(self, message: dict):

        disconnected = []

        for websocket in self.connections:

            try:

                await websocket.send_json(message)

            except Exception:

                disconnected.append(websocket)

        for websocket in disconnected:

            self.disconnect(websocket)

    def total_connections(self):

        return len(self.connections)


connection_manager = ConnectionManager()