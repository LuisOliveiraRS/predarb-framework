import json

import httpx
import pytest

from app.auth.mfa_client import (
    MFAInvalidCodeError,
    SupabaseMFAClient,
)
from app.core.settings import Settings


def make_settings() -> Settings:
    return Settings(
        AUTH_ENABLED=True,
        SUPABASE_URL="https://project.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
    )


@pytest.mark.asyncio
async def test_enroll_totp_returns_qr_secret_and_factor():
    async def handler(request: httpx.Request):
        assert request.method == "POST"
        assert request.url.path == "/auth/v1/factors"
        assert request.headers["apikey"] == (
            "sb_publishable_test"
        )
        assert request.headers["authorization"] == (
            "Bearer access-aal1"
        )

        payload = json.loads(request.content)

        assert payload == {
            "factor_type": "totp",
            "friendly_name": "PredArb Authenticator",
        }

        return httpx.Response(
            200,
            json={
                "id": "factor-123",
                "type": "totp",
                "friendly_name": "PredArb Authenticator",
                "totp": {
                    "qr_code": "<svg>qr</svg>",
                    "secret": "SECRET123",
                    "uri": "otpauth://totp/predarb",
                },
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SupabaseMFAClient(
            make_settings(),
            http_client=http_client,
        )

        enrollment = await client.enroll_totp(
            access_token="access-aal1",
        )

    assert enrollment.factor_id == "factor-123"
    assert enrollment.qr_code == "<svg>qr</svg>"
    assert enrollment.secret == "SECRET123"
    assert enrollment.uri.startswith("otpauth://")


@pytest.mark.asyncio
async def test_challenge_and_verify_return_new_session():
    requests = []

    async def handler(request: httpx.Request):
        requests.append(request.url.path)

        if request.url.path.endswith("/challenge"):
            return httpx.Response(
                200,
                json={"id": "challenge-456"},
            )

        payload = json.loads(request.content)

        assert payload == {
            "challenge_id": "challenge-456",
            "code": "123456",
        }

        return httpx.Response(
            200,
            json={
                "access_token": "access-aal2",
                "refresh_token": "refresh-aal2",
                "expires_in": 3600,
                "token_type": "bearer",
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SupabaseMFAClient(
            make_settings(),
            http_client=http_client,
        )

        challenge = await client.create_challenge(
            access_token="access-aal1",
            factor_id="factor-123",
        )

        tokens = await client.verify_totp(
            access_token="access-aal1",
            factor_id="factor-123",
            challenge_id=challenge.challenge_id,
            code="123456",
        )

    assert requests == [
        "/auth/v1/factors/factor-123/challenge",
        "/auth/v1/factors/factor-123/verify",
    ]
    assert tokens.access_token == "access-aal2"
    assert tokens.refresh_token == "refresh-aal2"


@pytest.mark.asyncio
async def test_invalid_local_totp_code_is_rejected():
    client = SupabaseMFAClient(make_settings())

    with pytest.raises(
        MFAInvalidCodeError,
        match="seis digitos",
    ):
        await client.verify_totp(
            access_token="access-aal1",
            factor_id="factor-123",
            challenge_id="challenge-456",
            code="12AB",
        )

@pytest.mark.asyncio
async def test_cleanup_removes_only_unverified_factors():
    requests = []

    async def handler(request: httpx.Request):
        requests.append(
            (request.method, request.url.path)
        )

        assert request.headers["authorization"] == (
            "Bearer access-aal1"
        )

        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "id": "user-123",
                    "factors": [
                        {
                            "id": "factor-exposed",
                            "factor_type": "totp",
                            "status": "unverified",
                        },
                        {
                            "id": "factor-active",
                            "factor_type": "totp",
                            "status": "verified",
                        },
                    ],
                },
            )

        assert request.method == "DELETE"
        assert request.url.path == (
            "/auth/v1/factors/factor-exposed"
        )

        return httpx.Response(
            200,
            json={"id": "factor-exposed"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SupabaseMFAClient(
            make_settings(),
            http_client=http_client,
        )

        removed = await (
            client.cleanup_unverified_factors(
                access_token="access-aal1",
            )
        )

    assert removed == ["factor-exposed"]

    assert requests == [
        ("GET", "/auth/v1/user"),
        (
            "DELETE",
            "/auth/v1/factors/factor-exposed",
        ),
    ]

@pytest.mark.asyncio
async def test_list_factors_returns_verified_totp_without_secret():
    async def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path == "/auth/v1/user"

        return httpx.Response(
            200,
            json={
                "id": "user-123",
                "factors": [
                    {
                        "id": "factor-verified",
                        "factor_type": "totp",
                        "status": "verified",
                        "friendly_name": "PredArb",
                    },
                ],
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
    ) as http_client:
        client = SupabaseMFAClient(
            make_settings(),
            http_client=http_client,
        )

        factors = await client.list_factors(
            access_token="access-aal1",
        )

    assert len(factors) == 1
    assert factors[0].factor_id == "factor-verified"
    assert factors[0].status == "verified"
    assert not hasattr(factors[0], "secret")
