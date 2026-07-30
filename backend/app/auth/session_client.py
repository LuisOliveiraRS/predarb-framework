"""Login, renovacao e encerramento de sessoes Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.auth.errors import (
    AuthProviderError,
    InvalidCredentialsError,
    SessionRefreshError,
)
from app.core.settings import Settings


@dataclass(frozen=True, slots=True)
class SupabaseSessionTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str


class SupabaseSessionClient:
    """Cliente Auth sem service_role e sem persistencia local."""

    def __init__(
        self,
        configured_settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = configured_settings
        self._http_client = http_client
        self._token_url = (
            f"{configured_settings.SUPABASE_URL}"
            "/auth/v1/token"
        )
        self._logout_url = (
            f"{configured_settings.SUPABASE_URL}"
            "/auth/v1/logout"
        )

    async def password_login(
        self,
        *,
        email: str,
        password: str,
    ) -> SupabaseSessionTokens:
        response = await self._post(
            self._token_url,
            params={"grant_type": "password"},
            headers=self._public_headers(),
            json={
                "email": email,
                "password": password,
            },
        )

        if response.status_code in {400, 401, 403}:
            raise InvalidCredentialsError(
                "E-mail ou senha invalidos."
            )

        if response.status_code >= 400:
            raise AuthProviderError(
                "Falha temporaria no Supabase Auth."
            )

        return self._parse_tokens(response)

    async def refresh_session(
        self,
        refresh_token: str,
    ) -> SupabaseSessionTokens:
        token = str(refresh_token or "").strip()

        if not token:
            raise SessionRefreshError(
                "Token de renovacao ausente."
            )

        response = await self._post(
            self._token_url,
            params={"grant_type": "refresh_token"},
            headers=self._public_headers(),
            json={
                "refresh_token": token,
            },
        )

        if response.status_code in {400, 401, 403}:
            raise SessionRefreshError(
                "Sessao expirada ou revogada."
            )

        if response.status_code >= 400:
            raise AuthProviderError(
                "Falha temporaria ao renovar a sessao."
            )

        return self._parse_tokens(response)

    async def logout(
        self,
        access_token: str,
    ) -> None:
        token = str(access_token or "").strip()

        if not token:
            return

        response = await self._post(
            self._logout_url,
            headers={
                **self._public_headers(),
                "Authorization": f"Bearer {token}",
            },
        )

        if response.status_code >= 500:
            raise AuthProviderError(
                "Falha temporaria ao encerrar a sessao."
            )

    def _public_headers(self) -> dict[str, str]:
        publishable_key = (
            self._settings.SUPABASE_PUBLISHABLE_KEY
        )

        return {
            "apikey": publishable_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _post(
        self,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            if self._http_client is not None:
                return await self._http_client.post(
                    url,
                    timeout=8.0,
                    **kwargs,
                )

            async with httpx.AsyncClient() as client:
                return await client.post(
                    url,
                    timeout=8.0,
                    **kwargs,
                )

        except httpx.TimeoutException as exc:
            raise AuthProviderError(
                "Tempo esgotado no Supabase Auth."
            ) from exc

        except httpx.RequestError as exc:
            raise AuthProviderError(
                "Falha de comunicacao com o Supabase Auth."
            ) from exc

    @staticmethod
    def _parse_tokens(
        response: httpx.Response,
    ) -> SupabaseSessionTokens:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthProviderError(
                "Resposta invalida do Supabase Auth."
            ) from exc

        if not isinstance(payload, dict):
            raise AuthProviderError(
                "Formato de sessao invalido."
            )

        access_token = str(
            payload.get("access_token") or ""
        ).strip()

        refresh_token = str(
            payload.get("refresh_token") or ""
        ).strip()

        token_type = str(
            payload.get("token_type") or "bearer"
        ).strip().lower()

        try:
            expires_in = int(payload.get("expires_in"))
        except (TypeError, ValueError) as exc:
            raise AuthProviderError(
                "Expiracao da sessao invalida."
            ) from exc

        if (
            not access_token
            or not refresh_token
            or expires_in <= 0
            or token_type != "bearer"
        ):
            raise AuthProviderError(
                "Dados da sessao incompletos."
            )

        return SupabaseSessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
        )
