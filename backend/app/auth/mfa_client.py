"""Cliente Supabase MFA/TOTP sem armazenamento local de segredos."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.auth.errors import (
    AuthProviderError,
    InvalidAccessTokenError,
)
from app.auth.session_client import SupabaseSessionTokens
from app.core.settings import Settings


class MFAInvalidCodeError(Exception):
    """O codigo TOTP informado foi recusado."""


class MFARateLimitError(Exception):
    """Limite temporario de desafios MFA atingido."""


@dataclass(frozen=True, slots=True)
class TOTPEnrollment:
    factor_id: str
    qr_code: str
    secret: str
    uri: str
    friendly_name: str | None = None


@dataclass(frozen=True, slots=True)
class MFAChallenge:
    challenge_id: str


@dataclass(frozen=True, slots=True)
class MFAFactor:
    factor_id: str
    factor_type: str
    status: str
    friendly_name: str | None = None


class SupabaseMFAClient:
    """Cliente MFA usando somente publishable key e JWT do usuario."""

    def __init__(
        self,
        configured_settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = configured_settings
        self._http_client = http_client
        self._factors_url = (
            f"{configured_settings.SUPABASE_URL}"
            "/auth/v1/factors"
        )
        self._user_url = (
            f"{configured_settings.SUPABASE_URL}"
            "/auth/v1/user"
        )

    async def enroll_totp(
        self,
        *,
        access_token: str,
        friendly_name: str = "PredArb Authenticator",
    ) -> TOTPEnrollment:
        response = await self._request(
            "POST",
            self._factors_url,
            headers=self._auth_headers(access_token),
            json={
                "factor_type": "totp",
                "friendly_name": friendly_name,
            },
        )

        self._raise_for_status(response)

        payload = self._json_object(response)
        totp = payload.get("totp")

        if not isinstance(totp, dict):
            raise AuthProviderError(
                "Resposta de cadastro TOTP invalida."
            )

        factor_id = str(payload.get("id") or "").strip()
        qr_code = str(totp.get("qr_code") or "").strip()
        secret = str(totp.get("secret") or "").strip()
        uri = str(totp.get("uri") or "").strip()

        if not factor_id or not qr_code or not secret or not uri:
            raise AuthProviderError(
                "Dados incompletos no cadastro TOTP."
            )

        returned_name = payload.get("friendly_name")

        return TOTPEnrollment(
            factor_id=factor_id,
            qr_code=qr_code,
            secret=secret,
            uri=uri,
            friendly_name=(
                str(returned_name)
                if returned_name is not None
                else None
            ),
        )

    async def list_factors(
        self,
        *,
        access_token: str,
    ) -> list[MFAFactor]:
        """Lista fatores sem expor segredos TOTP."""

        response = await self._request(
            "GET",
            self._user_url,
            headers=self._auth_headers(access_token),
        )

        self._raise_for_status(response)

        payload = self._json_object(response)
        raw_factors = payload.get("factors") or []

        if not isinstance(raw_factors, list):
            raise AuthProviderError(
                "Lista de fatores MFA invalida."
            )

        factors: list[MFAFactor] = []

        for raw_factor in raw_factors:
            if not isinstance(raw_factor, dict):
                continue

            factor_id = str(
                raw_factor.get("id") or ""
            ).strip()

            factor_type = str(
                raw_factor.get("factor_type")
                or raw_factor.get("type")
                or ""
            ).strip().lower()

            factor_status = str(
                raw_factor.get("status") or ""
            ).strip().lower()

            if not factor_id or not factor_status:
                continue

            friendly_name = raw_factor.get(
                "friendly_name"
            )

            factors.append(
                MFAFactor(
                    factor_id=factor_id,
                    factor_type=factor_type,
                    status=factor_status,
                    friendly_name=(
                        str(friendly_name).strip()
                        if friendly_name is not None
                        else None
                    ),
                )
            )

        return factors

    async def cleanup_unverified_factors(
        self,
        *,
        access_token: str,
    ) -> list[str]:
        """Remove somente fatores MFA ainda nao verificados."""

        response = await self._request(
            "GET",
            self._user_url,
            headers=self._auth_headers(access_token),
        )

        self._raise_for_status(response)

        payload = self._json_object(response)
        raw_factors = payload.get("factors") or []

        if not isinstance(raw_factors, list):
            raise AuthProviderError(
                "Lista de fatores MFA invalida."
            )

        removed: list[str] = []

        for raw_factor in raw_factors:
            if not isinstance(raw_factor, dict):
                continue

            factor_id = str(
                raw_factor.get("id") or ""
            ).strip()

            factor_status = str(
                raw_factor.get("status") or ""
            ).strip().lower()

            if (
                not factor_id
                or factor_status != "unverified"
            ):
                continue

            await self.unenroll_factor(
                access_token=access_token,
                factor_id=factor_id,
            )

            removed.append(factor_id)

        return removed

    async def unenroll_factor(
        self,
        *,
        access_token: str,
        factor_id: str,
    ) -> None:
        normalized_factor = self._required(
            factor_id,
            "Fator MFA ausente.",
        )

        response = await self._request(
            "DELETE",
            (
                f"{self._factors_url}/"
                f"{normalized_factor}"
            ),
            headers=self._auth_headers(access_token),
        )

        self._raise_for_status(response)

    async def create_challenge(
        self,
        *,
        access_token: str,
        factor_id: str,
    ) -> MFAChallenge:
        normalized_factor = self._required(
            factor_id,
            "Fator MFA ausente.",
        )

        response = await self._request(
            "POST",
            (
                f"{self._factors_url}/"
                f"{normalized_factor}/challenge"
            ),
            headers=self._auth_headers(access_token),
            json={},
        )

        self._raise_for_status(response)

        payload = self._json_object(response)
        challenge_id = str(payload.get("id") or "").strip()

        if not challenge_id:
            raise AuthProviderError(
                "Identificador do desafio MFA ausente."
            )

        return MFAChallenge(challenge_id=challenge_id)

    async def verify_totp(
        self,
        *,
        access_token: str,
        factor_id: str,
        challenge_id: str,
        code: str,
    ) -> SupabaseSessionTokens:
        normalized_factor = self._required(
            factor_id,
            "Fator MFA ausente.",
        )
        normalized_challenge = self._required(
            challenge_id,
            "Desafio MFA ausente.",
        )
        normalized_code = str(code or "").strip()

        if (
            len(normalized_code) != 6
            or not normalized_code.isdigit()
        ):
            raise MFAInvalidCodeError(
                "O codigo TOTP deve conter seis digitos."
            )

        response = await self._request(
            "POST",
            (
                f"{self._factors_url}/"
                f"{normalized_factor}/verify"
            ),
            headers=self._auth_headers(access_token),
            json={
                "challenge_id": normalized_challenge,
                "code": normalized_code,
            },
        )

        self._raise_for_status(
            response,
            verification=True,
        )

        return self._parse_session(response)

    def _auth_headers(
        self,
        access_token: str,
    ) -> dict[str, str]:
        token = self._required(
            access_token,
            "Token de acesso ausente.",
        )

        return {
            "apikey": (
                self._settings.SUPABASE_PUBLISHABLE_KEY
            ),
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            if self._http_client is not None:
                return await self._http_client.request(
                    method,
                    url,
                    timeout=10.0,
                    **kwargs,
                )

            async with httpx.AsyncClient() as client:
                return await client.request(
                    method,
                    url,
                    timeout=10.0,
                    **kwargs,
                )

        except httpx.TimeoutException as exc:
            raise AuthProviderError(
                "Tempo esgotado no Supabase MFA."
            ) from exc

        except httpx.RequestError as exc:
            raise AuthProviderError(
                "Falha de comunicacao com o Supabase MFA."
            ) from exc

    @staticmethod
    def _raise_for_status(
        response: httpx.Response,
        *,
        verification: bool = False,
    ) -> None:
        if response.status_code in {401, 403}:
            raise InvalidAccessTokenError(
                "Sessao invalida para MFA."
            )

        if response.status_code == 429:
            raise MFARateLimitError(
                "Limite temporario de MFA atingido."
            )

        if (
            verification
            and response.status_code in {400, 422}
        ):
            raise MFAInvalidCodeError(
                "Codigo TOTP invalido ou expirado."
            )

        if response.status_code >= 400:
            raise AuthProviderError(
                "O Supabase recusou a operacao MFA."
            )

    @staticmethod
    def _json_object(
        response: httpx.Response,
    ) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthProviderError(
                "Resposta MFA invalida."
            ) from exc

        if not isinstance(payload, dict):
            raise AuthProviderError(
                "Formato de resposta MFA invalido."
            )

        return payload

    @classmethod
    def _parse_session(
        cls,
        response: httpx.Response,
    ) -> SupabaseSessionTokens:
        payload = cls._json_object(response)

        access_token = str(
            payload.get("access_token") or ""
        ).strip()

        refresh_token = str(
            payload.get("refresh_token") or ""
        ).strip()

        token_type = str(
            payload.get("token_type") or ""
        ).strip().lower()

        try:
            expires_in = int(payload.get("expires_in"))
        except (TypeError, ValueError) as exc:
            raise AuthProviderError(
                "Expiracao da sessao MFA invalida."
            ) from exc

        if (
            not access_token
            or not refresh_token
            or token_type != "bearer"
            or expires_in <= 0
        ):
            raise AuthProviderError(
                "Sessao MFA incompleta."
            )

        return SupabaseSessionTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            token_type=token_type,
        )

    @staticmethod
    def _required(
        value: str,
        message: str,
    ) -> str:
        normalized = str(value or "").strip()

        if not normalized:
            raise InvalidAccessTokenError(message)

        return normalized
