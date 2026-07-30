"""Orquestracao da autenticacao e autorizacao Supabase."""

from app.auth.jwt_verifier import SupabaseJWTVerifier
from app.auth.profile import AuthenticatedUser
from app.auth.profile_client import SupabaseProfileClient


class SupabaseAuthService:
    def __init__(
        self,
        *,
        verifier: SupabaseJWTVerifier,
        profile_client: SupabaseProfileClient,
    ) -> None:
        self._verifier = verifier
        self._profile_client = profile_client

    async def authenticate(
        self,
        access_token: str,
    ) -> AuthenticatedUser:
        principal = self._verifier.verify(access_token)

        profile = await self._profile_client.get_profile(
            access_token=access_token,
            principal=principal,
        )

        return AuthenticatedUser(
            principal=principal,
            profile=profile,
        )
