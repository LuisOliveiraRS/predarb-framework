from pathlib import Path


BASE = Path(__file__).resolve().parents[1]

AUTH_SCRIPT = (
    BASE
    / "app"
    / "dashboard"
    / "static"
    / "js"
    / "auth.js"
)

SESSION_SCRIPT = (
    BASE
    / "app"
    / "dashboard"
    / "static"
    / "js"
    / "session.js"
)


def test_login_detects_mfa_required_aal1_session():
    content = AUTH_SCRIPT.read_text(
        encoding="utf-8"
    )

    assert "function requiresMfa(user)" in content
    assert "user.mfa_required === true" in content
    assert "user.has_mfa !== true" in content
    assert 'user.aal !== "aal2"' in content
    assert "requiresMfa(payload?.user)" in content


def test_login_redirects_aal1_to_mfa():
    content = AUTH_SCRIPT.read_text(
        encoding="utf-8"
    )

    assert "function mfaRedirectPath(nextPath)" in content
    assert '"/mfa?next="' in content
    assert "encodeURIComponent(destination)" in content
    assert "mfaRedirectPath(nextPath)" in content


def test_existing_login_session_is_also_checked():
    content = AUTH_SCRIPT.read_text(
        encoding="utf-8"
    )

    existing_session = content.index(
        "async function checkExistingSession"
    )

    mfa_check = content.index(
        "requiresMfa(payload?.user)",
        existing_session,
    )

    assert mfa_check > existing_session


def test_dashboard_redirects_aal1_before_reveal():
    content = SESSION_SCRIPT.read_text(
        encoding="utf-8"
    )

    assert "function redirectToMfa()" in content
    assert "target.searchParams.set(" in content
    assert '"next"' in content
    assert "if (requiresMfa(user))" in content

    mfa_check = content.index(
        "if (requiresMfa(user))"
    )

    reveal_after_check = content.index(
        "revealDashboard();",
        mfa_check,
    )

    assert mfa_check < reveal_after_check


def test_aal2_session_is_not_classified_as_pending_mfa():
    for script in (
        AUTH_SCRIPT,
        SESSION_SCRIPT,
    ):
        content = script.read_text(
            encoding="utf-8"
        )

        assert 'user.aal !== "aal2"' in content


def test_frontend_does_not_store_session_or_mfa_data():
    for script in (
        AUTH_SCRIPT,
        SESSION_SCRIPT,
    ):
        content = script.read_text(
            encoding="utf-8"
        )

        assert "localStorage" not in content
        assert "sessionStorage" not in content
        assert "access_token" not in content
        assert "refresh_token" not in content
