from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect

import app.dashboard.router_ws as router_ws_module
from app.auth.errors import (
    InactiveUserError,
    InvalidAccessTokenError,
    ProfileLookupError,
)
from app.dashboard.router_ws import (
    WS_FORBIDDEN,
    WS_TRY_AGAIN_LATER,
    WS_UNAUTHORIZED,
    router_socket,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
STATIC_JS = (
    BACKEND_ROOT
    / "app"
    / "dashboard"
    / "static"
    / "js"
)


class FakeWebSocket:
    def __init__(self, *, cookies=None):
        self.cookies = cookies or {}
        self.state = SimpleNamespace()
        self.accepted = False
        self.closed_code = None
        self.closed_reason = None

    async def accept(self):
        self.accepted = True

    async def close(self, *, code=1000, reason=None):
        self.closed_code = code
        self.closed_reason = reason

    async def receive_text(self):
        raise WebSocketDisconnect(code=1000)


class FakeRouterStream:
    def __init__(self):
        self.registered = []
        self.unregistered = []

    async def register(
        self,
        websocket,
        *,
        accept,
        send_initial,
    ):
        self.registered.append(
            {
                "websocket": websocket,
                "accept": accept,
                "send_initial": send_initial,
            }
        )

    async def unregister(self, websocket):
        self.unregistered.append(websocket)


class FakeAuthService:
    def __init__(self, *, user=None, error=None):
        self.user = user
        self.error = error
        self.tokens = []

    async def authenticate(self, access_token):
        self.tokens.append(access_token)

        if self.error is not None:
            raise self.error

        return self.user


def configure_required_auth(monkeypatch):
    monkeypatch.setattr(
        router_ws_module.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    monkeypatch.setattr(
        router_ws_module.settings,
        "AUTH_ACCESS_COOKIE_NAME",
        "predarb_access_token",
    )


@pytest.mark.asyncio
async def test_auth_disabled_preserves_websocket(
    monkeypatch,
):
    stream = FakeRouterStream()
    websocket = FakeWebSocket()

    monkeypatch.setattr(
        router_ws_module.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        False,
    )

    monkeypatch.setattr(
        router_ws_module,
        "router_stream",
        stream,
    )

    await router_socket(websocket)

    assert len(stream.registered) == 1
    assert stream.registered[0]["accept"] is True
    assert stream.registered[0]["send_initial"] is True
    assert stream.unregistered == [websocket]


@pytest.mark.asyncio
async def test_missing_cookie_is_rejected(
    monkeypatch,
):
    configure_required_auth(monkeypatch)

    stream = FakeRouterStream()
    websocket = FakeWebSocket()

    monkeypatch.setattr(
        router_ws_module,
        "router_stream",
        stream,
    )

    await router_socket(websocket)

    assert websocket.accepted is True
    assert websocket.closed_code == WS_UNAUTHORIZED
    assert stream.registered == []


@pytest.mark.asyncio
async def test_valid_cookie_authenticates_socket(
    monkeypatch,
):
    configure_required_auth(monkeypatch)

    stream = FakeRouterStream()
    websocket = FakeWebSocket(
        cookies={
            "predarb_access_token": "valid-token"
        }
    )

    user = SimpleNamespace(user_id=uuid4())
    service = FakeAuthService(user=user)

    monkeypatch.setattr(
        router_ws_module,
        "get_auth_service",
        lambda: service,
    )

    monkeypatch.setattr(
        router_ws_module,
        "router_stream",
        stream,
    )

    await router_socket(websocket)

    assert service.tokens == ["valid-token"]
    assert websocket.state.authenticated_user is user
    assert len(stream.registered) == 1
    assert stream.unregistered == [websocket]


@pytest.mark.asyncio
async def test_expired_token_closes_with_4401(
    monkeypatch,
):
    configure_required_auth(monkeypatch)

    websocket = FakeWebSocket(
        cookies={
            "predarb_access_token": "expired-token"
        }
    )

    service = FakeAuthService(
        error=InvalidAccessTokenError("expired")
    )

    monkeypatch.setattr(
        router_ws_module,
        "get_auth_service",
        lambda: service,
    )

    await router_socket(websocket)

    assert websocket.closed_code == WS_UNAUTHORIZED


@pytest.mark.asyncio
async def test_inactive_user_closes_with_4403(
    monkeypatch,
):
    configure_required_auth(monkeypatch)

    websocket = FakeWebSocket(
        cookies={
            "predarb_access_token": "inactive-token"
        }
    )

    service = FakeAuthService(
        error=InactiveUserError("inactive")
    )

    monkeypatch.setattr(
        router_ws_module,
        "get_auth_service",
        lambda: service,
    )

    await router_socket(websocket)

    assert websocket.closed_code == WS_FORBIDDEN


@pytest.mark.asyncio
async def test_provider_failure_uses_retry_code(
    monkeypatch,
):
    configure_required_auth(monkeypatch)

    websocket = FakeWebSocket(
        cookies={
            "predarb_access_token": "valid-token"
        }
    )

    service = FakeAuthService(
        error=ProfileLookupError(
            "provider unavailable"
        )
    )

    monkeypatch.setattr(
        router_ws_module,
        "get_auth_service",
        lambda: service,
    )

    await router_socket(websocket)

    assert websocket.closed_code == WS_TRY_AGAIN_LATER


def test_frontend_refreshes_session_after_4401():
    content = (
        STATIC_JS
        / "websocket.js"
    ).read_text(encoding="utf-8")

    assert "WS_UNAUTHORIZED = 4401" in content
    assert '"/auth/refresh"' in content
    assert 'credentials: "same-origin"' in content
    assert "refreshAuthentication" in content
    assert "redirectToLogin" in content
    assert "localStorage" not in content
    assert "sessionStorage" not in content


def test_dashboard_has_auth_websocket_states():
    content = (
        STATIC_JS
        / "dashboard.js"
    ).read_text(encoding="utf-8")

    assert '"auth-refreshing"' in content
    assert '"auth-restored"' in content
    assert '"auth-required"' in content
