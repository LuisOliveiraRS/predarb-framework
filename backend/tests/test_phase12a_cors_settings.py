import pytest

from app.core.settings import Settings


def configured(**changes):
    values = {
        "PUBLIC_CORS_ENABLED": False,
        "PUBLIC_CORS_ALLOWED_ORIGINS": "",
        "PUBLIC_CORS_ALLOW_CREDENTIALS": False,
    }
    values.update(changes)
    return Settings(_env_file=None, **values)


def test_cors_is_disabled_by_default():
    settings = configured()

    assert settings.PUBLIC_CORS_ENABLED is False
    assert settings.PUBLIC_CORS_ALLOWED_ORIGINS == ""
    assert settings.PUBLIC_CORS_ALLOW_CREDENTIALS is False


def test_enabled_cors_requires_origin():
    with pytest.raises(ValueError):
        configured(PUBLIC_CORS_ENABLED=True)


def test_cors_wildcard_is_rejected():
    with pytest.raises(ValueError):
        configured(
            PUBLIC_CORS_ENABLED=True,
            PUBLIC_CORS_ALLOWED_ORIGINS="*",
        )


def test_cors_credentials_are_rejected():
    with pytest.raises(ValueError):
        configured(
            PUBLIC_CORS_ALLOW_CREDENTIALS=True,
        )


def test_invalid_origin_is_rejected():
    with pytest.raises(ValueError):
        configured(
            PUBLIC_CORS_ENABLED=True,
            PUBLIC_CORS_ALLOWED_ORIGINS="panel.example.com",
        )


def test_explicit_origins_are_accepted():
    settings = configured(
        PUBLIC_CORS_ENABLED=True,
        PUBLIC_CORS_ALLOWED_ORIGINS=(
            "https://painel.example.com/, "
            "http://localhost:5173/"
        ),
    )

    assert settings.PUBLIC_CORS_ALLOWED_ORIGINS == (
        "https://painel.example.com,"
        "http://localhost:5173"
    )
