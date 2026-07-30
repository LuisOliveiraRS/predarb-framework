from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_authenticated_user
from app.auth.mfa_client import (
    MFAChallenge,
    MFAFactor,
    TOTPEnrollment,
)
from app.auth.mfa_router import router
from app.auth.session_client import SupabaseSessionTokens
from app.core.settings import settings


def make_user(*, aal: str = "aal1"):
    return SimpleNamespace(
        user_id=uuid4(),
        profile=SimpleNamespace(
            email="admin@example.com",
            display_name="Administrador",
            mfa_required=True,
        ),
        role=SimpleNamespace(value="admin"),
        principal=SimpleNamespace(aal=aal),
        has_mfa=(aal == "aal2"),
    )


def make_app(user):
    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[
        require_authenticated_user
    ] = lambda: user

    return app


def test_enroll_route_returns_totp_setup(monkeypatch):
    user = make_user()

    calls = []

    class FakeMFAClient:
        async def cleanup_unverified_factors(
            self,
            *,
            access_token,
        ):
            assert access_token == "access-aal1"
            calls.append("cleanup")
            return ["factor-abandoned"]

        async def enroll_totp(
            self,
            *,
            access_token,
            friendly_name,
        ):
            calls.append("enroll")
            assert access_token == "access-aal1"
            assert friendly_name == (
                "PredArb Authenticator"
            )

            return TOTPEnrollment(
                factor_id="factor-123",
                qr_code="<svg>qr</svg>",
                secret="SECRET123",
                uri="otpauth://totp/predarb",
                friendly_name=friendly_name,
            )

    monkeypatch.setattr(
        "app.auth.mfa_router.get_mfa_client",
        lambda: FakeMFAClient(),
    )

    client = TestClient(make_app(user))
    client.cookies.set(
        settings.AUTH_ACCESS_COOKIE_NAME,
        "access-aal1",
    )

    response = client.post(
        "/auth/mfa/enroll",
        json={
            "friendly_name": (
                "PredArb Authenticator"
            ),
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["factor_id"] == "factor-123"
    assert payload["secret"] == "SECRET123"
    assert payload["qr_code"] == "<svg>qr</svg>"
    assert calls == ["cleanup", "enroll"]


def test_challenge_route_returns_challenge_id(
    monkeypatch,
):
    user = make_user()

    class FakeMFAClient:
        async def create_challenge(
            self,
            *,
            access_token,
            factor_id,
        ):
            assert access_token == "access-aal1"
            assert factor_id == "factor-123"

            return MFAChallenge(
                challenge_id="challenge-456"
            )

    monkeypatch.setattr(
        "app.auth.mfa_router.get_mfa_client",
        lambda: FakeMFAClient(),
    )

    client = TestClient(make_app(user))
    client.cookies.set(
        settings.AUTH_ACCESS_COOKIE_NAME,
        "access-aal1",
    )

    response = client.post(
        "/auth/mfa/challenge",
        json={"factor_id": "factor-123"},
    )

    assert response.status_code == 200
    assert response.json()["challenge_id"] == (
        "challenge-456"
    )


def test_verify_route_replaces_session_with_aal2(
    monkeypatch,
):
    user_aal1 = make_user(aal="aal1")
    user_aal2 = make_user(aal="aal2")

    class FakeMFAClient:
        async def verify_totp(
            self,
            *,
            access_token,
            factor_id,
            challenge_id,
            code,
        ):
            assert access_token == "access-aal1"
            assert factor_id == "factor-123"
            assert challenge_id == "challenge-456"
            assert code == "123456"

            return SupabaseSessionTokens(
                access_token="access-aal2",
                refresh_token="refresh-aal2",
                expires_in=3600,
                token_type="bearer",
            )

    class FakeAuthService:
        async def authenticate(self, access_token):
            assert access_token == "access-aal2"
            return user_aal2

    monkeypatch.setattr(
        "app.auth.mfa_router.get_mfa_client",
        lambda: FakeMFAClient(),
    )

    monkeypatch.setattr(
        "app.auth.mfa_router."
        "auth_dependencies.get_auth_service",
        lambda: FakeAuthService(),
    )

    client = TestClient(make_app(user_aal1))
    client.cookies.set(
        settings.AUTH_ACCESS_COOKIE_NAME,
        "access-aal1",
    )

    response = client.post(
        "/auth/mfa/verify",
        json={
            "factor_id": "factor-123",
            "challenge_id": "challenge-456",
            "code": "123456",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["verified"] is True
    assert payload["user"]["aal"] == "aal2"
    assert payload["user"]["has_mfa"] is True

    cookies = response.headers.get_list("set-cookie")
    joined = "\n".join(cookies)

    assert settings.AUTH_ACCESS_COOKIE_NAME in joined
    assert settings.AUTH_REFRESH_COOKIE_NAME in joined
    assert "access-aal2" in joined

def test_status_route_returns_only_verified_totp(
    monkeypatch,
):
    user = make_user(aal="aal1")

    class FakeMFAClient:
        async def list_factors(
            self,
            *,
            access_token,
        ):
            assert access_token == "access-aal1"

            return [
                MFAFactor(
                    factor_id="factor-verified",
                    factor_type="totp",
                    status="verified",
                    friendly_name="PredArb",
                ),
                MFAFactor(
                    factor_id="factor-pending",
                    factor_type="totp",
                    status="unverified",
                    friendly_name="Pendente",
                ),
            ]

    monkeypatch.setattr(
        "app.auth.mfa_router.get_mfa_client",
        lambda: FakeMFAClient(),
    )

    client = TestClient(make_app(user))
    client.cookies.set(
        settings.AUTH_ACCESS_COOKIE_NAME,
        "access-aal1",
    )

    response = client.get("/auth/mfa/status")

    assert response.status_code == 200

    payload = response.json()

    assert payload["current_aal"] == "aal1"
    assert payload["can_enroll"] is False
    assert payload["verified_factors"] == [
        {
            "factor_id": "factor-verified",
            "factor_type": "totp",
            "friendly_name": "PredArb",
        }
    ]
