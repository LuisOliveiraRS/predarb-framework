"""Consulta segura do perfil usando o token do proprio usuario."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import httpx

from app.auth.errors import (
    InvalidAccessTokenError,
    InvalidProfileError,
    ProfileLookupError,
)
from app.auth.models import AuthPrincipal
from app.auth.profile import AppRole, UserProfile
from app.core.settings import Settings


class SupabaseProfileClient:
    """Consulta public.profiles respeitando as politicas RLS."""

    def __init__(
        self,
        configured_settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = configured_settings
        self._http_client = http_client
        self._profiles_url = (
            f"{configured_settings.SUPABASE_URL}"
            "/rest/v1/profiles"
        )

    async def get_profile(
        self,
        *,
        access_token: str,
        principal: AuthPrincipal,
    ) -> UserProfile:
        token = str(access_token or "").strip()

        if not token:
            raise InvalidAccessTokenError(
                "Token de acesso ausente."
            )

        headers = {
            "apikey": (
                self._settings.SUPABASE_PUBLISHABLE_KEY
            ),
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

        params = {
            "select": (
                "id,email,display_name,role,"
                "is_active,mfa_required"
            ),
            "id": f"eq.{principal.user_id}",
            "limit": "1",
        }

        try:
            response = await self._get(
                headers=headers,
                params=params,
            )
        except httpx.TimeoutException as exc:
            raise ProfileLookupError(
                "Tempo esgotado ao consultar o perfil."
            ) from exc
        except httpx.RequestError as exc:
            raise ProfileLookupError(
                "Falha de comunicacao com o Supabase."
            ) from exc

        if response.status_code in {401, 403}:
            raise InvalidAccessTokenError(
                "Token recusado pelo Supabase."
            )

        if response.status_code >= 400:
            raise ProfileLookupError(
                "Supabase recusou a consulta do perfil."
            )

        try:
            records: Any = response.json()
        except ValueError as exc:
            raise InvalidProfileError(
                "Resposta de perfil invalida."
            ) from exc

        if not isinstance(records, list):
            raise InvalidProfileError(
                "Formato de perfil invalido."
            )

        if len(records) != 1:
            raise InvalidProfileError(
                "Perfil do usuario nao encontrado."
            )

        return self._parse_profile(
            records[0],
            principal=principal,
        )

    async def _get(
        self,
        *,
        headers: dict[str, str],
        params: dict[str, str],
    ) -> httpx.Response:
        if self._http_client is not None:
            return await self._http_client.get(
                self._profiles_url,
                headers=headers,
                params=params,
                timeout=5.0,
            )

        async with httpx.AsyncClient() as client:
            return await client.get(
                self._profiles_url,
                headers=headers,
                params=params,
                timeout=5.0,
            )

    @staticmethod
    def _parse_profile(
        record: Any,
        *,
        principal: AuthPrincipal,
    ) -> UserProfile:
        if not isinstance(record, dict):
            raise InvalidProfileError(
                "Registro de perfil invalido."
            )

        try:
            profile_user_id = UUID(str(record["id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidProfileError(
                "Identificador do perfil invalido."
            ) from exc

        if profile_user_id != principal.user_id:
            raise InvalidProfileError(
                "Perfil nao pertence ao usuario autenticado."
            )

        try:
            role = AppRole(str(record["role"]))
        except (KeyError, ValueError) as exc:
            raise InvalidProfileError(
                "Papel do perfil invalido."
            ) from exc

        is_active = record.get("is_active")
        mfa_required = record.get("mfa_required")

        if not isinstance(is_active, bool):
            raise InvalidProfileError(
                "Estado do perfil invalido."
            )

        if not isinstance(mfa_required, bool):
            raise InvalidProfileError(
                "Configuracao MFA invalida."
            )

        email_value = record.get("email")
        display_name_value = record.get("display_name")

        profile = UserProfile(
            user_id=profile_user_id,
            email=(
                str(email_value).strip().lower()
                if email_value
                else None
            ),
            display_name=(
                str(display_name_value).strip()
                if display_name_value
                else None
            ),
            role=role,
            is_active=is_active,
            mfa_required=mfa_required,
        )

        profile.require_active()
        return profile
