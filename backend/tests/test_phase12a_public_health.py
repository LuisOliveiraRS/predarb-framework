from fastapi.testclient import TestClient

from app.core.application import create_app
from app.core.settings import settings


def paths(app):
    return {
        getattr(route, "path", "")
        for route in app.routes
    }


def test_public_health_is_minimal(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    app = create_app()
    app.state.startup_completed = True
    app.state.startup_error = None

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "version": settings.APP_VERSION,
    }
    assert "/internal/health" not in paths(app)


def test_public_health_reports_degraded(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    app = create_app()
    app.state.startup_completed = False
    app.state.startup_error = "startup failure"

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_internal_health_exists_only_in_debug(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)

    app = create_app()

    assert "/internal/health" in paths(app)
