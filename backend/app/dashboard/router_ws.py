"""WebSocket autenticado do dashboard em tempo real."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.auth.dependencies import get_auth_service
from app.auth.errors import (
    AuthConfigurationError,
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidProfileError,
    ProfileLookupError,
)
from app.core.settings import settings
from app.dashboard.router_stream import router_stream


router = APIRouter()

WS_UNAUTHORIZED = 4401
WS_FORBIDDEN = 4403
WS_TRY_AGAIN_LATER = 1013


async def _reject_socket(
    websocket: WebSocket,
    *,
    code: int,
    reason: str,
) -> None:
    """
    Aceita apenas o handshake necess?rio para entregar ao cliente
    um c?digo WebSocket expl?cito. Nenhum dado operacional ? enviado.
    """

    await websocket.accept()
    await websocket.close(
        code=code,
        reason=reason,
    )


async def _authorize_socket(
    websocket: WebSocket,
) -> bool:
    if not settings.AUTH_REQUIRED_FOR_DASHBOARD:
        return True

    access_token = str(
        websocket.cookies.get(
            settings.AUTH_ACCESS_COOKIE_NAME,
            "",
        )
        or ""
    ).strip()

    if not access_token:
        await _reject_socket(
            websocket,
            code=WS_UNAUTHORIZED,
            reason="Authentication required",
        )
        return False

    try:
        user = await (
            get_auth_service()
            .authenticate(access_token)
        )

    except InvalidAccessTokenError:
        await _reject_socket(
            websocket,
            code=WS_UNAUTHORIZED,
            reason="Session expired",
        )
        return False

    except (
        InactiveUserError,
        InvalidProfileError,
    ):
        await _reject_socket(
            websocket,
            code=WS_FORBIDDEN,
            reason="Access forbidden",
        )
        return False

    except (
        AuthConfigurationError,
        ProfileLookupError,
    ):
        await _reject_socket(
            websocket,
            code=WS_TRY_AGAIN_LATER,
            reason="Authentication unavailable",
        )
        return False

    websocket.state.authenticated_user = user
    return True


@router.websocket("/ws/router")
async def router_socket(
    websocket: WebSocket,
) -> None:
    authorized = await _authorize_socket(websocket)

    if not authorized:
        return

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
