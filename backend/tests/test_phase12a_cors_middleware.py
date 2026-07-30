from fastapi.testclient import TestClient

from app.core.application import create_app
from app.core.settings import settings


def test_cors_disabled_has_no_origin_header(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PUBLIC_CORS_ENABLED",
        False,
    )
    monkeypatch.setattr(
        settings,
        "PUBLIC_CORS_ALLOWED_ORIGINS",
        "",
    )

    client = TestClient(create_app())

    response = client.get(
        "/version",
        headers={
            "Origin": "https://painel.example.com",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_allowed_origin_receives_cors_header(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PUBLIC_CORS_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "PUBLIC_CORS_ALLOWED_ORIGINS",
        "https://painel.example.com",
    )

    client = TestClient(create_app())

    response = client.get(
        "/version",
        headers={
            "Origin": "https://painel.example.com",
        },
    )

    assert response.status_code == 200
    assert response.headers[
        "access-control-allow-origin"
    ] == "https://painel.example.com"

    assert (
        response.headers.get(
            "access-control-allow-credentials"
        )
        is None
    )


def test_unknown_origin_is_not_authorized(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PUBLIC_CORS_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "PUBLIC_CORS_ALLOWED_ORIGINS",
        "https://painel.example.com",
    )

    client = TestClient(create_app())

    response = client.get(
        "/version",
        headers={
            "Origin": "https://site-nao-autorizado.example",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
