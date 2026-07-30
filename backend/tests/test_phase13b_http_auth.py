from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import app.auth.dependencies as auth_dependencies
from app.auth.errors import InvalidAccessTokenError
from app.auth.models import AuthPrincipal
from app.auth.profile import (
    AppRole,
    AuthenticatedUser,
    UserProfile,
)
from app.auth.dependencies import require_dashboard_user
from app.core.application import create_app
from app.dashboard.api import router as dashboard_api_router
from app.dashboard.router import router as dashboard_page_router
from app.dashboard.router_api import router as router_api_router


def make_user() -> AuthenticatedUser:
    user_id = uuid4()

    principal = AuthPrincipal.create(
        user_id=user_id,
        email="admin@example.com",
        token_role="authenticated",
        aal="aal2",
        session_id=uuid4(),
        claims={
            "role": "authenticated",
            "aal": "aal2",
        },
    )

    profile = UserProfile(
        user_id=user_id,
        email="admin@example.com",
        display_name="PredArb Admin",
        role=AppRole.ADMIN,
        is_active=True,
        mfa_required=True,
    )

    return AuthenticatedUser(
        principal=principal,
        profile=profile,
    )


def make_test_app() -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def protected(
        user: AuthenticatedUser | None = Depends(
            require_dashboard_user
        ),
    ):
        return {
            "authenticated": user is not None,
            "role": (
                user.role.value
                if user is not None
                else None
            ),
        }

    return app


class FakeAuthService:
    def __init__(
        self,
        *,
        user: AuthenticatedUser | None = None,
        error: Exception | None = None,
    ) -> None:
        self.user = user
        self.error = error
        self.received_token = None

    async def authenticate(
        self,
        access_token: str,
    ) -> AuthenticatedUser:
        self.received_token = access_token

        if self.error is not None:
            raise self.error

        assert self.user is not None
        return self.user


def dependency_calls(route: APIRoute) -> set:
    return {
        dependency.call
        for dependency in route.dependant.dependencies
    }


def test_auth_disabled_preserves_local_dashboard(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_dependencies.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        False,
    )

    def unexpected_service():
        raise AssertionError(
            "Supabase nao deveria ser consultado."
        )

    monkeypatch.setattr(
        auth_dependencies,
        "get_auth_service",
        unexpected_service,
    )

    response = TestClient(
        make_test_app()
    ).get("/protected")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": False,
        "role": None,
    }


def test_required_auth_rejects_missing_token(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_dependencies.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    response = TestClient(
        make_test_app()
    ).get("/protected")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Autenticacao obrigatoria."
    }
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.headers["cache-control"] == "no-store"


def test_invalid_token_is_rejected(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_dependencies.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    service = FakeAuthService(
        error=InvalidAccessTokenError(
            "Token expirado."
        )
    )

    monkeypatch.setattr(
        auth_dependencies,
        "get_auth_service",
        lambda: service,
    )

    response = TestClient(
        make_test_app()
    ).get(
        "/protected",
        headers={
            "Authorization": "Bearer expired-token"
        },
    )

    assert response.status_code == 401
    assert service.received_token == "expired-token"


def test_valid_token_returns_authenticated_user(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_dependencies.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    service = FakeAuthService(
        user=make_user(),
    )

    monkeypatch.setattr(
        auth_dependencies,
        "get_auth_service",
        lambda: service,
    )

    response = TestClient(
        make_test_app()
    ).get(
        "/protected",
        headers={
            "Authorization": "Bearer valid-token"
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "role": "admin",
    }


@pytest.mark.parametrize(
    "router",
    [
        dashboard_api_router,
        router_api_router,
    ],
)
def test_dashboard_api_routers_are_protected(
    router,
):
    routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute)
    ]

    assert routes

    for route in routes:
        assert require_dashboard_user in (
            dependency_calls(route)
        )


def test_dashboard_page_remains_public_for_login_shell():
    routes = [
        route
        for route in dashboard_page_router.routes
        if isinstance(route, APIRoute)
    ]

    assert routes

    for route in routes:
        assert require_dashboard_user not in (
            dependency_calls(route)
        )


def test_root_health_remains_public():
    app = create_app()

    health_route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute)
        and route.path == "/health"
    )

    assert require_dashboard_user not in (
        dependency_calls(health_route)
    )
