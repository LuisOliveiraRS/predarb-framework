from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.auth.router as auth_router_module
from app.auth.router import router as auth_router
from app.dashboard.router import router as dashboard_router


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = (
    BACKEND_ROOT
    / "app"
    / "dashboard"
    / "templates"
)
STATIC_ROOT = (
    BACKEND_ROOT
    / "app"
    / "dashboard"
    / "static"
)


def test_login_page_is_public_and_no_store():
    app = FastAPI()
    app.include_router(dashboard_router)

    response = TestClient(app).get("/login")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert 'id="login-form"' in response.text
    assert 'type="password"' in response.text


def test_login_template_does_not_expose_supabase_keys():
    content = (
        TEMPLATE_ROOT
        / "login.html"
    ).read_text(encoding="utf-8")

    assert "SUPABASE_URL" not in content
    assert "SUPABASE_PUBLISHABLE_KEY" not in content
    assert "service_role" not in content
    assert "refresh_token" not in content


def test_auth_config_exposes_only_safe_values(
    monkeypatch,
):
    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_ENABLED",
        True,
    )
    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )
    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_LOGIN_PATH",
        "/login",
    )
    monkeypatch.setattr(
        auth_router_module.settings,
        "AUTH_AFTER_LOGIN_PATH",
        "/dashboard",
    )

    app = FastAPI()
    app.include_router(auth_router)

    response = TestClient(app).get("/auth/config")

    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "dashboard_required": True,
        "login_path": "/login",
        "after_login_path": "/dashboard",
    }

    assert "SUPABASE" not in response.text
    assert "publishable" not in response.text.lower()


def test_dashboard_waits_for_session_before_starting():
    dashboard_html = (
        TEMPLATE_ROOT
        / "dashboard.html"
    ).read_text(encoding="utf-8")

    dashboard_js = (
        STATIC_ROOT
        / "js"
        / "dashboard.js"
    ).read_text(encoding="utf-8")

    assert "auth-pending" in dashboard_html
    assert "ensureDashboardSession" in dashboard_js
    assert (
        dashboard_js.index("ensureDashboardSession")
        < 250
    )


def test_session_script_refreshes_expired_access_token():
    content = (
        STATIC_ROOT
        / "js"
        / "session.js"
    ).read_text(encoding="utf-8")

    assert '"/auth/me"' in content
    assert '"/auth/refresh"' in content
    assert '"/auth/logout"' in content
    assert 'credentials: "same-origin"' in content
    assert "redirectToLogin" in content


def test_login_script_uses_backend_session_endpoint():
    content = (
        STATIC_ROOT
        / "js"
        / "auth.js"
    ).read_text(encoding="utf-8")

    assert '"/auth/login"' in content
    assert '"/auth/config"' in content
    assert "localStorage" not in content
    assert "sessionStorage" not in content
    assert "SUPABASE" not in content


def test_auth_styles_hide_dashboard_until_validation():
    content = (
        STATIC_ROOT
        / "css"
        / "auth.css"
    ).read_text(encoding="utf-8")

    assert ".auth-pending" in content
    assert "visibility: hidden" in content
    assert ".predarb-session-button" in content
