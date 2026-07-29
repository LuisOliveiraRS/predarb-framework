import asyncio
import websockets


async def test():

    uri = "ws://127.0.0.1:8000/ws/live"

    async with websockets.connect(uri) as websocket:

        print("Conectado!")

        await websocket.send("hello")

        while True:

            await asyncio.sleep(1)


asyncio.run(test())