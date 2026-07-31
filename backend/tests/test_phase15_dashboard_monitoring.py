from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

HTML = (
    ROOT
    / "app"
    / "dashboard"
    / "templates"
    / "dashboard.html"
).read_text(encoding="utf-8")

CSS = (
    ROOT
    / "app"
    / "dashboard"
    / "static"
    / "css"
    / "dashboard.css"
).read_text(encoding="utf-8")

JS = (
    ROOT
    / "app"
    / "dashboard"
    / "static"
    / "js"
    / "dashboard.js"
).read_text(encoding="utf-8")


def test_dashboard_has_monitoring_indicators():
    expected_ids = (
        'id="real-radar-new"',
        'id="real-radar-improving"',
        'id="real-radar-worsening"',
        'id="real-radar-history-points"',
        'id="real-radar-alerts"',
    )

    for expected_id in expected_ids:
        assert expected_id in HTML

    assert "Varia&ccedil;&atilde;o" in HTML
    assert "Tend&ecirc;ncia" in HTML


def test_dashboard_renders_monitoring_payload():
    expected_fragments = (
        "payload.monitoring",
        "monitoring.new_count",
        "monitoring.improving_count",
        "monitoring.worsening_count",
        "monitoring.history_points",
        "item.edge_change",
        "item.trend",
        "item.became_profitable",
        "payload.alerts",
    )

    for fragment in expected_fragments:
        assert fragment in JS


def test_dashboard_monitoring_uses_safe_dom():
    start = JS.index("const realRadarState")
    end = JS.index(
        "initializeRealOpportunityRadar();",
        start,
    )

    radar_block = JS[start:end]

    assert "innerHTML" not in radar_block
    assert "textContent" in radar_block
    assert "createElement" in radar_block


def test_dashboard_has_monitoring_styles():
    expected_styles = (
        ".real-radar-monitoring-grid",
        ".real-radar-monitoring-card",
        ".real-radar-alerts",
        ".real-radar-trend-badge",
        ".real-radar-trend-improving",
        ".real-radar-trend-worsening",
        ".real-radar-row-profitable",
    )

    for expected_style in expected_styles:
        assert expected_style in CSS
