from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.auth.password_recovery as recovery_module
from app.auth.password_recovery import (
    SupabasePasswordClient,
    router as recovery_router,
)
from app.dashboard.router import router as dashboard_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
STATIC_JS = (
    BACKEND_ROOT
    / "app"
    / "dashboard"
    / "static"
    / "js"
)
TEMPLATES = (
    BACKEND_ROOT
    / "app"
    / "dashboard"
    / "templates"
)


@pytest.mark.asyncio
async def test_recovery_client_uses_redirect_and_public_key(
    monkeypatch,
):
    monkeypatch.setattr(
        recovery_module.settings,
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setattr(
        recovery_module.settings,
        "SUPABASE_PUBLISHABLE_KEY",
        "sb_publishable_test",
    )

    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/recover"
        assert request.url.params["redirect_to"] == (
            "http://127.0.0.1:8001/redefinir-senha"
        )
        assert request.headers["apikey"] == (
            "sb_publishable_test"
        )
        assert "authorization" not in request.headers
        assert "service_role" not in request.content.decode()
        return httpx.Response(200, json={})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = SupabasePasswordClient(
            http_client=http_client
        )

        await client.request_recovery(
            email="admin@example.com",
            redirect_to=(
                "http://127.0.0.1:8001/redefinir-senha"
            ),
        )


@pytest.mark.asyncio
async def test_password_update_uses_recovery_bearer(
    monkeypatch,
):
    monkeypatch.setattr(
        recovery_module.settings,
        "SUPABASE_URL",
        "https://example.supabase.co",
    )
    monkeypatch.setattr(
        recovery_module.settings,
        "SUPABASE_PUBLISHABLE_KEY",
        "sb_publishable_test",
    )

    def handler(request):
        assert request.method == "PUT"
        assert request.url.path == "/auth/v1/user"
        assert request.headers["authorization"] == (
            "Bearer recovery-access-token"
        )
        assert "New-Strong-Password-123!" in (
            request.content.decode()
        )
        return httpx.Response(200, json={"id": "user"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as http_client:
        client = SupabasePasswordClient(
            http_client=http_client
        )

        await client.update_password(
            access_token="recovery-access-token",
            new_password="New-Strong-Password-123!",
        )


def test_recovery_endpoint_uses_current_origin(
    monkeypatch,
):
    class FakePasswordClient:
        def __init__(self):
            self.redirect_to = None

        async def request_recovery(
            self,
            *,
            email,
            redirect_to,
        ):
            self.redirect_to = redirect_to

    fake = FakePasswordClient()

    monkeypatch.setattr(
        recovery_module,
        "get_password_client",
        lambda: fake,
    )

    app = FastAPI()
    app.include_router(recovery_router)

    response = TestClient(
        app,
        base_url="http://127.0.0.1:8001",
    ).post(
        "/auth/password/recovery",
        json={
            "email": "admin@example.com",
        },
    )

    assert response.status_code == 202
    assert fake.redirect_to == (
        "http://127.0.0.1:8001/redefinir-senha"
    )
    assert response.headers["cache-control"] == "no-store"


def test_recovery_pages_are_public_and_no_store():
    app = FastAPI()
    app.include_router(dashboard_router)

    client = TestClient(app)

    forgot = client.get("/esqueci-senha")
    reset = client.get("/redefinir-senha")

    assert forgot.status_code == 200
    assert reset.status_code == 200
    assert forgot.headers["cache-control"] == "no-store"
    assert reset.headers["cache-control"] == "no-store"
    assert 'id="recovery-form"' in forgot.text
    assert 'id="reset-form"' in reset.text


def test_reset_script_reads_fragment_without_storage():
    content = (
        STATIC_JS
        / "reset_password.js"
    ).read_text(encoding="utf-8")

    assert 'fragment.get("access_token")' in content
    assert 'fragment.get("type")' in content
    assert 'fragment.get("error_code")' in content
    assert '"/auth/password/update"' in content
    assert "history.replaceState" in content
    assert "localStorage" not in content
    assert "sessionStorage" not in content


def test_recovery_script_calls_backend_only():
    content = (
        STATIC_JS
        / "forgot_password.js"
    ).read_text(encoding="utf-8")

    assert '"/auth/password/recovery"' in content
    assert "SUPABASE_URL" not in content
    assert "service_role" not in content
    assert "localStorage" not in content


def test_login_contains_password_recovery_link():
    content = (
        TEMPLATES
        / "login.html"
    ).read_text(encoding="utf-8")

    assert 'href="/esqueci-senha"' in content
