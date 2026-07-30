"""Recuperacao segura de senha pelo Supabase Auth."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from app.auth.dependencies import get_auth_service
from app.auth.errors import (
    AuthConfigurationError,
    AuthProviderError,
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidProfileError,
    ProfileLookupError,
)
from app.core.settings import settings


router = APIRouter(
    prefix="/auth/password",
    tags=["authentication"],
)


class PasswordRecoveryRateLimitError(Exception):
    """Muitas solicitacoes de recuperacao em pouco tempo."""


class PasswordUpdateError(Exception):
    """A nova senha foi recusada pelo provedor."""


class PasswordRecoveryRequest(BaseModel):
    email: str = Field(
        min_length=3,
        max_length=320,
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()

        if (
            "@" not in normalized
            or normalized.startswith("@")
            or normalized.endswith("@")
        ):
            raise ValueError("E-mail invalido.")

        return normalized


class PasswordUpdateRequest(BaseModel):
    access_token: str = Field(
        min_length=20,
        max_length=8192,
    )

    new_password: str = Field(
        min_length=12,
        max_length=1024,
    )

    confirm_password: str = Field(
        min_length=12,
        max_length=1024,
    )

    @model_validator(mode="after")
    def validate_passwords(
        self,
    ) -> "PasswordUpdateRequest":
        if self.new_password != self.confirm_password:
            raise ValueError(
                "As senhas informadas nao coincidem."
            )

        categories = (
            any(c.islower() for c in self.new_password),
            any(c.isupper() for c in self.new_password),
            any(c.isdigit() for c in self.new_password),
            any(not c.isalnum() for c in self.new_password),
        )

        if sum(categories) < 3:
            raise ValueError(
                "A senha deve combinar ao menos tres "
                "categorias de caracteres."
            )

        return self


class SupabasePasswordClient:
    """Usa somente a chave publicavel e o token do usuario."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._http_client = http_client

        self._recover_url = (
            f"{settings.SUPABASE_URL}/auth/v1/recover"
        )

        self._user_url = (
            f"{settings.SUPABASE_URL}/auth/v1/user"
        )

    def _public_headers(self) -> dict[str, str]:
        publishable_key = (
            settings.SUPABASE_PUBLISHABLE_KEY
        )

        return {
            "apikey": publishable_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def request_recovery(
        self,
        *,
        email: str,
        redirect_to: str,
    ) -> None:
        response = await self._request(
            "POST",
            self._recover_url,
            params={
                "redirect_to": redirect_to,
            },
            headers=self._public_headers(),
            json={
                "email": email,
            },
        )

        if response.status_code == 429:
            raise PasswordRecoveryRateLimitError(
                "Muitas solicitacoes de recuperacao."
            )

        if response.status_code >= 400:
            raise AuthProviderError(
                "Nao foi possivel solicitar a recuperacao."
            )

    async def update_password(
        self,
        *,
        access_token: str,
        new_password: str,
    ) -> None:
        response = await self._request(
            "PUT",
            self._user_url,
            headers={
                **self._public_headers(),
                "Authorization": (
                    f"Bearer {access_token}"
                ),
            },
            json={
                "password": new_password,
            },
        )

        if response.status_code in {401, 403}:
            raise InvalidAccessTokenError(
                "Token de recuperacao invalido."
            )

        if response.status_code in {400, 422}:
            raise PasswordUpdateError(
                "A nova senha foi recusada."
            )

        if response.status_code >= 400:
            raise AuthProviderError(
                "Falha temporaria ao atualizar a senha."
            )

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
                "Tempo esgotado no Supabase Auth."
            ) from exc

        except httpx.RequestError as exc:
            raise AuthProviderError(
                "Falha de comunicacao com o Supabase Auth."
            ) from exc


@lru_cache(maxsize=1)
def get_password_client() -> SupabasePasswordClient:
    if not settings.AUTH_ENABLED:
        raise AuthConfigurationError(
            "A autenticacao Supabase esta desabilitada."
        )

    return SupabasePasswordClient()


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post(
    "/recovery",
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_password_recovery(
    payload: PasswordRecoveryRequest,
    request: Request,
    response: Response,
):
    redirect_to = (
        f"{str(request.base_url).rstrip('/')}"
        "/redefinir-senha"
    )

    try:
        await get_password_client().request_recovery(
            email=payload.email,
            redirect_to=redirect_to,
        )

    except PasswordRecoveryRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Aguarde antes de solicitar "
                "um novo e-mail."
            ),
            headers={
                "Retry-After": "60",
                "Cache-Control": "no-store",
            },
        ) from exc

    except (
        AuthConfigurationError,
        AuthProviderError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "O servico de recuperacao esta "
                "temporariamente indisponivel."
            ),
            headers={
                "Cache-Control": "no-store",
            },
        ) from exc

    _no_store(response)

    return {
        "accepted": True,
        "message": (
            "Caso o e-mail esteja cadastrado, "
            "um novo link de recuperacao sera enviado."
        ),
    }


@router.post("/update")
async def update_password(
    payload: PasswordUpdateRequest,
    response: Response,
):
    try:
        # Valida assinatura, emissor, audiencia, perfil e atividade.
        await get_auth_service().authenticate(
            payload.access_token
        )

        await get_password_client().update_password(
            access_token=payload.access_token,
            new_password=payload.new_password,
        )

    except (
        InvalidAccessTokenError,
        PasswordUpdateError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "O link de recuperacao e invalido "
                "ou expirou."
            ),
            headers={
                "Cache-Control": "no-store",
            },
        ) from exc

    except (
        InactiveUserError,
        InvalidProfileError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sem acesso ao PredArb.",
            headers={
                "Cache-Control": "no-store",
            },
        ) from exc

    except (
        AuthConfigurationError,
        AuthProviderError,
        ProfileLookupError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "O servico de autenticacao esta "
                "temporariamente indisponivel."
            ),
            headers={
                "Cache-Control": "no-store",
            },
        ) from exc

    _no_store(response)

    return {
        "updated": True,
        "message": "Senha atualizada com sucesso.",
    }
