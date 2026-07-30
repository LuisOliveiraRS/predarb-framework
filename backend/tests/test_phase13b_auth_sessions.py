from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.auth.dependencies as auth_dependencies
import app.auth.router as auth_router_module
from app.auth.errors import (
    AuthProviderError,
    InvalidCredentialsError,
)
from app.auth.models import AuthPrincipal
from app.auth.profile import (
    AppRole,
    AuthenticatedUser,
    UserProfile,
)
from app.auth.router import router as auth_router
from app.auth.session_client import (
    SupabaseSessionClient,
    SupabaseSessionTokens,
)
from app.core.settings import Settings


def make_settings(**overrides):
    values = {
        "DEBUG": False,
        "AUTH_ENABLED": True,
        "AUTH_REQUIRED_FOR_DASHBOARD": True,
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_PUBLISHABLE_KEY": "sb_publishable_test",
        "SUPABASE_JWT_AUDIENCE": "authenticated",
        "SUPABASE_JWT_ALGORITHMS": "RS256",
        "SUPABASE_JWKS_CACHE_TTL_SECONDS": 600,
        "AUTH_COOKIE_SECURE": True,
        "AUTH_COOKIE_SAMESITE": "strict",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def make_user() -> AuthenticatedUser:
    user_id = uuid4()

    principal = AuthPrincipal.create(
        user_id=user_id,
        email="admin@example.com",
        token_role="authenticated",
        aal="aal2",
        session_id=uuid4(),
        claims={"role": "authenticated"},
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


def token_payload():
    return {
        "access_token": "access-token-value",
        "refresh_token": "refresh-token-value",
        "expires_in": 3600,
        "token_type": "bearer",
    }


def make_http_client(handler):
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_password_login_uses_publishable_key():
    def handler(request):
        assert request.url.params["grant_type"] == "password"
        assert request.headers["apikey"] == (
            "sb_publishable_test"
        )
        assert "authorization" not in request.headers

        payload = request.content.decode()
        assert "admin@example.com" in payload
        assert "service_role" not in payload

        return httpx.Response(200, json=token_payload())

    async with make_http_client(handler) as client:
        session_client = SupabaseSessionClient(
            make_settings(),
            http_client=client,
        )

        tokens = await session_client.password_login(
            email="admin@example.com",
            password="strong-password",
        )

    assert tokens.access_token == "access-token-value"
    assert tokens.refresh_token == "refresh-token-value"
    assert tokens.expires_in == 3600


@pytest.mark.asyncio
async def test_invalid_password_is_rejected():
    def handler(request):
        return httpx.Response(
            400,
            json={"error": "invalid_grant"},
        )

    async with make_http_client(handler) as client:
        session_client = SupabaseSessionClient(
            make_settings(),
            http_client=client,
        )

        with pytest.raises(
            InvalidCredentialsError,
            match="E-mail ou senha",
        ):
            await session_client.password_login(
                email="admin@example.com",
                password="wrong-password",
            )


@pytest.mark.asyncio
async def test_refresh_uses_refresh_token():
    def handler(request):
        assert (
            request.url.params["grant_type"]
            == "refresh_token"
        )
        assert "refresh-token-input" in (
            request.content.decode()
        )
        return httpx.Response(200, json=token_payload())

    async with make_http_client(handler) as client:
        session_client = SupabaseSessionClient(
            make_settings(),
            http_client=client,
        )

        tokens = await session_client.refresh_session(
            "refresh-token-input"
        )

    assert tokens.access_token == "access-token-value"


@pytest.mark.asyncio
async def test_malformed_session_is_rejected():
    def handler(request):
        return httpx.Response(
            200,
            json={"access_token": "incomplete"},
        )

    async with make_http_client(handler) as client:
        session_client = SupabaseSessionClient(
            make_settings(),
            http_client=client,
        )

        with pytest.raises(AuthProviderError):
            await session_client.password_login(
                email="admin@example.com",
                password="strong-password",
            )


class FakeSessionClient:
    def __init__(self):
        self.login_email = None
        self.login_password = None
        self.refresh_token = None
        self.logout_token = None

    async def password_login(self, *, email, password):
        self.login_email = email
        self.login_password = password
        return SupabaseSessionTokens(
            access_token="access-token-value",
            refresh_token="refresh-token-value",
            expires_in=3600,
            token_type="bearer",
        )

    async def refresh_session(self, refresh_token):
        self.refresh_token = refresh_token
        return SupabaseSessionTokens(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            expires_in=3600,
            token_type="bearer",
        )

    async def logout(self, access_token):
        self.logout_token = access_token


class FakeAuthService:
    def __init__(self, user):
        self.user = user
        self.tokens = []

    async def authenticate(self, access_token):
        self.tokens.append(access_token)
        return self.user


def make_app():
    app = FastAPI()
    app.include_router(auth_router)
    return app


def prepare_auth_mocks(monkeypatch):
    session_client = FakeSessionClient()
    auth_service = FakeAuthService(make_user())

    monkeypatch.setattr(
        auth_router_module,
        "get_session_client",
        lambda: session_client,
    )

    monkeypatch.setattr(
        auth_dependencies,
        "get_auth_service",
        lambda: auth_service,
    )

    monkeypatch.setattr(
        auth_dependencies.settings,
        "AUTH_ENABLED",
        True,
    )

    monkeypatch.setattr(
        auth_dependencies.settings,
        "AUTH_ACCESS_COOKIE_NAME",
        "predarb_access_token",
    )

    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_ACCESS_COOKIE_NAME",
        "predarb_access_token",
    )

    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_REFRESH_COOKIE_NAME",
        "predarb_refresh_token",
    )

    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_COOKIE_SECURE",
        True,
    )

    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_COOKIE_SAMESITE",
        "strict",
    )

    return session_client, auth_service


def test_login_sets_secure_http_only_cookies(
    monkeypatch,
):
    session_client, auth_service = prepare_auth_mocks(
        monkeypatch
    )

    client = TestClient(
        make_app(),
        base_url="https://testserver",
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "ADMIN@example.com",
            "password": "strong-password",
        },
    )

    assert response.status_code == 200
    assert session_client.login_email == (
        "admin@example.com"
    )
    assert auth_service.tokens == [
        "access-token-value"
    ]

    cookie_headers = ", ".join(
        response.headers.get_list("set-cookie")
    ).lower()

    assert "httponly" in cookie_headers
    assert "secure" in cookie_headers
    assert "samesite=strict" in cookie_headers
    assert "access-token-value" not in response.text
    assert "refresh-token-value" not in response.text


def test_me_uses_access_cookie(monkeypatch):
    _, auth_service = prepare_auth_mocks(monkeypatch)

    client = TestClient(
        make_app(),
        base_url="https://testserver",
    )

    client.cookies.set(
        "predarb_access_token",
        "cookie-access-token",
    )

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert auth_service.tokens == [
        "cookie-access-token"
    ]
    assert response.json()["user"]["role"] == "admin"


def test_bearer_header_precedes_cookie(monkeypatch):
    _, auth_service = prepare_auth_mocks(monkeypatch)

    client = TestClient(
        make_app(),
        base_url="https://testserver",
    )

    client.cookies.set(
        "predarb_access_token",
        "cookie-access-token",
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer header-access-token"
        },
    )

    assert response.status_code == 200
    assert auth_service.tokens == [
        "header-access-token"
    ]


def test_me_rejects_missing_session(monkeypatch):
    prepare_auth_mocks(monkeypatch)

    response = TestClient(
        make_app(),
        base_url="https://testserver",
    ).get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Autenticacao obrigatoria."
    }


def test_refresh_rotates_both_cookies(monkeypatch):
    session_client, auth_service = prepare_auth_mocks(
        monkeypatch
    )

    client = TestClient(
        make_app(),
        base_url="https://testserver",
    )

    client.cookies.set(
        "predarb_refresh_token",
        "old-refresh-token",
    )

    response = client.post("/auth/refresh")

    assert response.status_code == 200
    assert session_client.refresh_token == (
        "old-refresh-token"
    )
    assert auth_service.tokens == [
        "new-access-token"
    ]

    cookie_headers = ", ".join(
        response.headers.get_list("set-cookie")
    )

    assert "new-access-token" in cookie_headers
    assert "new-refresh-token" in cookie_headers


def test_logout_clears_session_cookies(monkeypatch):
    session_client, _ = prepare_auth_mocks(monkeypatch)

    client = TestClient(
        make_app(),
        base_url="https://testserver",
    )

    client.cookies.set(
        "predarb_access_token",
        "active-access-token",
    )

    response = client.post("/auth/logout")

    assert response.status_code == 204
    assert session_client.logout_token == (
        "active-access-token"
    )

    cookie_headers = ", ".join(
        response.headers.get_list("set-cookie")
    ).lower()

    assert "max-age=0" in cookie_headers
    assert "predarb_access_token" in cookie_headers
    assert "predarb_refresh_token" in cookie_headers
