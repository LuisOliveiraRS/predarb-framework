from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
HTML = (
    BACKEND
    / "app"
    / "dashboard"
    / "templates"
    / "dashboard.html"
).read_text(encoding="utf-8")

JS = (
    BACKEND
    / "app"
    / "dashboard"
    / "static"
    / "js"
    / "dashboard.js"
).read_text(encoding="utf-8")

CSS = (
    BACKEND
    / "app"
    / "dashboard"
    / "static"
    / "css"
    / "dashboard.css"
).read_text(encoding="utf-8")


def test_opportunities_view_exists():
    assert 'href="#opportunities-panel"' in HTML
    assert 'id="opportunities-panel"' in HTML
    assert 'id="opportunities-body"' in HTML
    assert 'id="opportunities-count"' in HTML


def test_opportunities_are_rendered():
    assert "function renderOpportunities(" in JS
    assert "renderOpportunities(snapshot);" in JS
    assert "Nenhuma oportunidade detectada" in JS


def test_hash_navigation_is_enabled():
    assert "function activateDashboardView()" in JS
    assert '"hashchange"' in JS
    assert "window.location.hash" in JS
    assert "DASHBOARD_VIEWS" in JS


def test_hidden_views_are_removed_from_layout():
    assert ".main-content > section[hidden]" in CSS
    assert "display: none !important" in CSS


def test_paper_tables_follow_paper_view():
    assert 'data-dashboard-group="paper"' in HTML
    assert 'data-dashboard-group="paper"' in JS
