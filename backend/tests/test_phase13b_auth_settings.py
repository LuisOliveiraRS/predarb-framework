import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def make_settings(**overrides):
    values = {
        "DEBUG": False,
        "AUTH_ENABLED": False,
        "AUTH_REQUIRED_FOR_DASHBOARD": False,
        "SUPABASE_URL": "",
        "SUPABASE_PUBLISHABLE_KEY": "",
        "SUPABASE_JWT_AUDIENCE": "authenticated",
        "SUPABASE_JWT_ALGORITHMS": "ES256,RS256",
        "SUPABASE_JWKS_CACHE_TTL_SECONDS": 600,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_authentication_is_disabled_by_default():
    configured = make_settings()

    assert configured.AUTH_ENABLED is False
    assert configured.AUTH_REQUIRED_FOR_DASHBOARD is False
    assert configured.AUTH_REQUIRE_MFA_FOR_OPERATIONS is True


def test_dashboard_auth_requires_authentication_enabled():
    with pytest.raises(
        ValidationError,
        match="AUTH_REQUIRED_FOR_DASHBOARD exige AUTH_ENABLED",
    ):
        make_settings(
            AUTH_REQUIRED_FOR_DASHBOARD=True,
        )


def test_enabled_auth_requires_supabase_url():
    with pytest.raises(
        ValidationError,
        match="AUTH_ENABLED exige SUPABASE_URL",
    ):
        make_settings(
            AUTH_ENABLED=True,
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
        )


def test_enabled_auth_requires_publishable_key():
    with pytest.raises(
        ValidationError,
        match="SUPABASE_PUBLISHABLE_KEY",
    ):
        make_settings(
            AUTH_ENABLED=True,
            SUPABASE_URL="https://example.supabase.co",
        )


def test_production_auth_rejects_plain_http():
    with pytest.raises(
        ValidationError,
        match="deve utilizar HTTPS",
    ):
        make_settings(
            AUTH_ENABLED=True,
            SUPABASE_URL="http://example.supabase.co",
            SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
        )


def test_symmetric_jwt_algorithm_is_rejected():
    with pytest.raises(
        ValidationError,
        match="Algoritmos JWT nao autorizados",
    ):
        make_settings(
            SUPABASE_JWT_ALGORITHMS="HS256",
        )


def test_auth_configuration_is_normalized():
    configured = make_settings(
        AUTH_ENABLED=True,
        AUTH_REQUIRED_FOR_DASHBOARD=True,
        SUPABASE_URL=" https://example.supabase.co/ ",
        SUPABASE_PUBLISHABLE_KEY=" sb_publishable_test ",
        SUPABASE_JWT_ALGORITHMS=" ES256,RS256 ",
    )

    assert configured.SUPABASE_URL == (
        "https://example.supabase.co"
    )
    assert configured.SUPABASE_PUBLISHABLE_KEY == (
        "sb_publishable_test"
    )
    assert configured.SUPABASE_JWT_ALGORITHMS == "ES256,RS256"


def test_jwks_cache_cannot_exceed_ten_minutes():
    with pytest.raises(
        ValidationError,
        match="deve ficar entre 60 e 600",
    ):
        make_settings(
            SUPABASE_JWKS_CACHE_TTL_SECONDS=601,
        )
