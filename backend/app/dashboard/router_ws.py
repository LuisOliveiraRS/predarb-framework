from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.dashboard.router_stream import router_stream


router = APIRouter()


@router.websocket("/ws/router")
async def router_socket(websocket: WebSocket) -> None:
    await router_stream.register(
        websocket,
        accept=True,
        send_initial=True,
    )

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await router_stream.unregister(websocket)
