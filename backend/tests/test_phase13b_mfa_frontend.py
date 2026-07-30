from pathlib import Path

from app.dashboard.router import router


BASE = Path(__file__).resolve().parents[1]

TEMPLATE = (
    BASE
    / "app"
    / "dashboard"
    / "templates"
    / "mfa.html"
)

SCRIPT = (
    BASE
    / "app"
    / "dashboard"
    / "static"
    / "js"
    / "mfa.js"
)

STYLE = (
    BASE
    / "app"
    / "dashboard"
    / "static"
    / "css"
    / "mfa.css"
)


def test_mfa_visual_route_is_registered():
    paths = {
        route.path
        for route in router.routes
    }

    assert "/mfa" in paths


def test_mfa_template_contains_secure_flow():
    content = TEMPLATE.read_text(encoding="utf-8")

    assert 'id="mfa-qr-image"' in content
    assert 'id="mfa-secret"' in content
    assert 'id="mfa-code"' in content
    assert 'autocomplete="one-time-code"' in content
    assert "mfa.js" in content


def test_mfa_frontend_calls_protected_backend_routes():
    content = SCRIPT.read_text(encoding="utf-8")

    assert '"/auth/me"' in content
    assert '"/auth/mfa/enroll"' in content
    assert '"/auth/mfa/challenge"' in content
    assert '"/auth/mfa/verify"' in content
    assert 'credentials: "same-origin"' in content


def test_mfa_frontend_does_not_persist_tokens_or_secret():
    content = SCRIPT.read_text(encoding="utf-8")

    assert "localStorage" not in content
    assert "sessionStorage" not in content
    assert ".innerHTML" not in content
    assert "access_token" not in content
    assert "refresh_token" not in content


def test_mfa_style_exists():
    assert STYLE.is_file()

def test_mfa_frontend_accepts_raw_svg_and_xml_header():
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'indexOf("<svg")' in content
    assert "encodeURIComponent(svg)" in content
    assert '"data:image/svg+xml;charset=utf-8,"' in content
    assert "qrImage.hidden = true" in content
    assert "crypto.randomUUID()" in content

def test_mfa_frontend_uses_existing_verified_factor():
    content = SCRIPT.read_text(encoding="utf-8")

    assert '"/auth/mfa/status"' in content
    assert "verified_factors" in content
    assert "Confirmar segundo fator" in content
    assert "enrollmentQr.hidden = true" in content
    assert 'safeNextPath("/dashboard")' in content

def test_hidden_enrollment_elements_override_layout_display():
    content = STYLE.read_text(encoding="utf-8")

    assert ".mfa-qr-container[hidden]" in content
    assert ".mfa-manual[hidden]" in content
    assert ".mfa-warning[hidden]" in content
    assert "display: none !important;" in content
