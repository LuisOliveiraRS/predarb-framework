from fastapi import APIRouter
from fastapi import WebSocket
from fastapi import WebSocketDisconnect

from app.realtime.connection_manager import connection_manager

router = APIRouter(
    prefix="/ws",
    tags=["Realtime"]
)


@router.websocket("/live")
async def websocket_endpoint(websocket: WebSocket):

    await connection_manager.connect(websocket)

    await websocket.send_json({

        "type": "connected",

        "message": "PredArb WebSocket Online"

    })

    try:

        while True:

            message = await websocket.receive_text()

            await websocket.send_json({

                "type": "echo",

                "message": message

            })

    except WebSocketDisconnect:

        connection_manager.disconnect(websocket)