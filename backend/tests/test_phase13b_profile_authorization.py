from uuid import uuid4

import httpx
import pytest

from app.auth.errors import (
    InactiveUserError,
    InsufficientRoleError,
    InvalidAccessTokenError,
    InvalidProfileError,
    MFARequiredError,
)
from app.auth.models import AuthPrincipal
from app.auth.profile import AppRole
from app.auth.profile_client import SupabaseProfileClient
from app.auth.service import SupabaseAuthService
from app.core.settings import Settings


def make_settings():
    return Settings(
        _env_file=None,
        DEBUG=False,
        AUTH_ENABLED=True,
        AUTH_REQUIRED_FOR_DASHBOARD=True,
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_PUBLISHABLE_KEY="sb_publishable_test",
        SUPABASE_JWT_AUDIENCE="authenticated",
        SUPABASE_JWT_ALGORITHMS="RS256",
        SUPABASE_JWKS_CACHE_TTL_SECONDS=600,
    )


def make_principal(*, aal="aal2"):
    return AuthPrincipal.create(
        user_id=uuid4(),
        email="admin@example.com",
        token_role="authenticated",
        aal=aal,
        session_id=uuid4(),
        claims={"role": "authenticated"},
    )


def profile_payload(principal, **overrides):
    payload = {
        "id": str(principal.user_id),
        "email": "admin@example.com",
        "display_name": "PredArb Admin",
        "role": "admin",
        "is_active": True,
        "mfa_required": True,
    }
    payload.update(overrides)
    return payload


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport)


@pytest.mark.asyncio
async def test_active_admin_profile_is_loaded():
    principal = make_principal()

    def handler(request):
        assert request.headers["apikey"] == (
            "sb_publishable_test"
        )
        assert request.headers["authorization"] == (
            "Bearer valid-token"
        )
        assert "service_role" not in request.headers
        assert request.url.params["id"] == (
            f"eq.{principal.user_id}"
        )

        return httpx.Response(
            200,
            json=[profile_payload(principal)],
        )

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        profile = await client.get_profile(
            access_token="valid-token",
            principal=principal,
        )

    assert profile.role is AppRole.ADMIN
    assert profile.is_active is True
    assert profile.mfa_required is True


@pytest.mark.asyncio
async def test_missing_profile_is_rejected():
    principal = make_principal()

    def handler(request):
        return httpx.Response(200, json=[])

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        with pytest.raises(
            InvalidProfileError,
            match="nao encontrado",
        ):
            await client.get_profile(
                access_token="valid-token",
                principal=principal,
            )


@pytest.mark.asyncio
async def test_inactive_profile_is_rejected():
    principal = make_principal()

    def handler(request):
        return httpx.Response(
            200,
            json=[
                profile_payload(
                    principal,
                    is_active=False,
                )
            ],
        )

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        with pytest.raises(
            InactiveUserError,
            match="desativado",
        ):
            await client.get_profile(
                access_token="valid-token",
                principal=principal,
            )


@pytest.mark.asyncio
async def test_invalid_role_is_rejected():
    principal = make_principal()

    def handler(request):
        return httpx.Response(
            200,
            json=[
                profile_payload(
                    principal,
                    role="superuser",
                )
            ],
        )

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        with pytest.raises(
            InvalidProfileError,
            match="Papel",
        ):
            await client.get_profile(
                access_token="valid-token",
                principal=principal,
            )


@pytest.mark.asyncio
async def test_profile_id_mismatch_is_rejected():
    principal = make_principal()

    def handler(request):
        return httpx.Response(
            200,
            json=[
                profile_payload(
                    principal,
                    id=str(uuid4()),
                )
            ],
        )

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        with pytest.raises(
            InvalidProfileError,
            match="nao pertence",
        ):
            await client.get_profile(
                access_token="valid-token",
                principal=principal,
            )


@pytest.mark.asyncio
async def test_supabase_unauthorized_response_is_rejected():
    principal = make_principal()

    def handler(request):
        return httpx.Response(
            401,
            json={"message": "JWT expired"},
        )

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        with pytest.raises(
            InvalidAccessTokenError,
            match="recusado",
        ):
            await client.get_profile(
                access_token="expired-token",
                principal=principal,
            )


@pytest.mark.asyncio
async def test_operator_cannot_use_admin_action():
    principal = make_principal()

    def handler(request):
        return httpx.Response(
            200,
            json=[
                profile_payload(
                    principal,
                    role="operator",
                )
            ],
        )

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        profile = await client.get_profile(
            access_token="valid-token",
            principal=principal,
        )

    with pytest.raises(
        InsufficientRoleError,
        match="Papel insuficiente",
    ):
        profile.require_role(AppRole.ADMIN)


@pytest.mark.asyncio
async def test_aal1_user_requires_mfa():
    principal = make_principal(aal="aal1")

    def handler(request):
        return httpx.Response(
            200,
            json=[profile_payload(principal)],
        )

    async with make_client(handler) as http_client:
        client = SupabaseProfileClient(
            make_settings(),
            http_client=http_client,
        )

        profile = await client.get_profile(
            access_token="valid-token",
            principal=principal,
        )

    from app.auth.profile import AuthenticatedUser

    user = AuthenticatedUser(
        principal=principal,
        profile=profile,
    )

    with pytest.raises(
        MFARequiredError,
        match="autenticacao multifator",
    ):
        user.require_mfa()


@pytest.mark.asyncio
async def test_auth_service_combines_jwt_and_profile():
    principal_reference = make_principal()

    class FakeVerifier:
        def verify(self, access_token):
            assert access_token == "valid-token"
            return principal_reference

    class FakeProfileClient:
        async def get_profile(
            self,
            *,
            access_token,
            principal,
        ):
            assert access_token == "valid-token"
            assert principal is principal_reference

            from app.auth.profile import UserProfile

            return UserProfile(
                user_id=principal_reference.user_id,
                email=principal_reference.email,
                display_name="PredArb Admin",
                role=AppRole.ADMIN,
                is_active=True,
                mfa_required=True,
            )

    service = SupabaseAuthService(
        verifier=FakeVerifier(),
        profile_client=FakeProfileClient(),
    )

    user = await service.authenticate("valid-token")

    assert user.user_id == principal_reference.user_id
    assert user.role is AppRole.ADMIN
    assert user.has_mfa is True
