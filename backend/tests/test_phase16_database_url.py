from app.database.database import (
    normalize_database_url,
)


def test_sqlite_url_is_not_changed():
    url = "sqlite:///predarb.db"

    assert normalize_database_url(url) == url


def test_postgres_legacy_url_uses_psycopg():
    normalized = normalize_database_url(
        "postgres://user:password@host/database"
    )

    assert normalized == (
        "postgresql+psycopg://"
        "user:password@host/database"
    )


def test_postgresql_url_uses_psycopg():
    normalized = normalize_database_url(
        "postgresql://user:password@host/database"
    )

    assert normalized == (
        "postgresql+psycopg://"
        "user:password@host/database"
    )


def test_explicit_psycopg_url_is_not_changed():
    url = (
        "postgresql+psycopg://"
        "user:password@host/database"
    )

    assert normalize_database_url(url) == url


def test_empty_url_remains_empty():
    assert normalize_database_url("") == ""
