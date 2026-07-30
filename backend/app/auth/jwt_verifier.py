"""Validacao local dos JWTs emitidos pelo Supabase Auth."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWTError

from app.auth.errors import (
    AuthConfigurationError,
    InvalidAccessTokenError,
)
from app.auth.models import AuthPrincipal
from app.core.settings import Settings


class SupabaseJWTVerifier:
    """Valida tokens Supabase usando somente chaves publicas JWKS."""

    def __init__(
        self,
        configured_settings: Settings,
        *,
        jwks_client: Any | None = None,
    ) -> None:
        if not configured_settings.AUTH_ENABLED:
            raise AuthConfigurationError(
                "A autenticacao Supabase esta desabilitada."
            )

        self._settings = configured_settings
        self._issuer = (
            f"{configured_settings.SUPABASE_URL}/auth/v1"
        )
        self._audience = (
            configured_settings.SUPABASE_JWT_AUDIENCE
        )
        self._algorithms = tuple(
            algorithm.strip()
            for algorithm in (
                configured_settings.SUPABASE_JWT_ALGORITHMS
            ).split(",")
            if algorithm.strip()
        )

        self._jwks_url = (
            f"{self._issuer}/.well-known/jwks.json"
        )

        self._jwks_client = jwks_client or PyJWKClient(
            self._jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=float(
                configured_settings
                .SUPABASE_JWKS_CACHE_TTL_SECONDS
            ),
            timeout=5.0,
        )

    @property
    def jwks_url(self) -> str:
        return self._jwks_url

    def verify(self, access_token: str) -> AuthPrincipal:
        token = str(access_token or "").strip()

        if not token:
            raise InvalidAccessTokenError(
                "Token de acesso ausente."
            )

        try:
            header = jwt.get_unverified_header(token)
        except PyJWTError as exc:
            raise InvalidAccessTokenError(
                "Token de acesso invalido."
            ) from exc

        algorithm = str(header.get("alg") or "").strip()

        if algorithm not in self._algorithms:
            raise InvalidAccessTokenError(
                "Algoritmo JWT nao autorizado."
            )

        try:
            signing_key = (
                self._jwks_client
                .get_signing_key_from_jwt(token)
            )

            claims = jwt.decode(
                token,
                key=signing_key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={
                    "require": [
                        "exp",
                        "iat",
                        "iss",
                        "sub",
                        "aud",
                    ],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_iss": True,
                    "verify_aud": True,
                },
            )
        except PyJWTError as exc:
            raise InvalidAccessTokenError(
                "Token de acesso invalido ou expirado."
            ) from exc
        except Exception as exc:
            raise InvalidAccessTokenError(
                "Nao foi possivel validar o token."
            ) from exc

        return self._build_principal(claims)

    @staticmethod
    def _build_principal(
        claims: dict[str, Any],
    ) -> AuthPrincipal:
        try:
            user_id = UUID(str(claims["sub"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidAccessTokenError(
                "Identificador de usuario invalido."
            ) from exc

        token_role = str(
            claims.get("role") or ""
        ).strip()

        if token_role != "authenticated":
            raise InvalidAccessTokenError(
                "Token nao pertence a um usuario autenticado."
            )

        if claims.get("is_anonymous") is True:
            raise InvalidAccessTokenError(
                "Usuarios anonimos nao sao autorizados."
            )

        aal = str(
            claims.get("aal") or "aal1"
        ).strip().lower()

        if aal not in {"aal1", "aal2"}:
            raise InvalidAccessTokenError(
                "Nivel de autenticacao invalido."
            )

        session_id = None
        raw_session_id = claims.get("session_id")

        if raw_session_id:
            try:
                session_id = UUID(str(raw_session_id))
            except (TypeError, ValueError) as exc:
                raise InvalidAccessTokenError(
                    "Identificador de sessao invalido."
                ) from exc

        email_value = claims.get("email")
        email = (
            str(email_value).strip().lower()
            if email_value
            else None
        )

        return AuthPrincipal.create(
            user_id=user_id,
            email=email,
            token_role=token_role,
            aal=aal,
            session_id=session_id,
            claims=claims,
        )
