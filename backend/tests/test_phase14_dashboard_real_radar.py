from pathlib import Path

from fastapi.testclient import TestClient

from app.core.application import create_app


HTML = Path(
    "app/dashboard/templates/dashboard.html"
).read_text(encoding="utf-8")

JS = Path(
    "app/dashboard/static/js/dashboard.js"
).read_text(encoding="utf-8")


def test_dashboard_contains_real_radar_panel():
    assert 'id="real-radar-panel"' in HTML
    assert 'id="real-radar-body"' in HTML
    assert 'id="real-radar-profitable"' in HTML
    assert 'href="#real-radar-panel"' in HTML


def test_dashboard_fetches_real_radar_endpoint():
    assert (
        "/real-markets/radar/snapshot"
        in JS
    )
    assert "refreshRealOpportunityRadar" in JS
    assert "setInterval" in JS


def test_dashboard_page_renders_radar_markup():
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/dashboard")

    assert response.status_code == 200
    assert 'id="real-radar-panel"' in response.text


def test_real_radar_has_no_mojibake():
    combined = HTML + JS

    invalid_fragments = (
        "P?BLICOS",
        "p?blicos",
        "ap?s",
        "Pr?xima",
        "pr?ximos",
        "pre?os",
        "l?quida",
        "est?o",
    )

    for fragment in invalid_fragments:
        assert fragment not in combined
