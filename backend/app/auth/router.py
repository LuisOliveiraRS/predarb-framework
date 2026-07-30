"""Endpoints de login e sessao do dashboard."""

from __future__ import annotations

from functools import lru_cache

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field, field_validator

import app.auth.dependencies as auth_dependencies
from app.auth.dependencies import require_authenticated_user
from app.auth.errors import (
    AuthConfigurationError,
    AuthProviderError,
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidProfileError,
    ProfileLookupError,
    SessionRefreshError,
)
from app.auth.profile import AuthenticatedUser
from app.auth.session_client import (
    SupabaseSessionClient,
    SupabaseSessionTokens,
)
from app.core.settings import settings


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=1024)

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


@lru_cache(maxsize=1)
def get_session_client() -> SupabaseSessionClient:
    if not settings.AUTH_ENABLED:
        raise AuthConfigurationError(
            "A autenticacao Supabase esta desabilitada."
        )

    return SupabaseSessionClient(settings)


def clear_session_client_cache() -> None:
    get_session_client.cache_clear()


def _set_session_cookies(
    response: Response,
    tokens: SupabaseSessionTokens,
) -> None:
    common = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
    }

    response.set_cookie(
        key=settings.AUTH_ACCESS_COOKIE_NAME,
        value=tokens.access_token,
        max_age=tokens.expires_in,
        **common,
    )

    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        max_age=(
            settings.AUTH_REFRESH_COOKIE_MAX_AGE_SECONDS
        ),
        **common,
    )

    response.headers["Cache-Control"] = "no-store"


def _clear_session_cookies(response: Response) -> None:
    common = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": "/",
    }

    response.delete_cookie(
        settings.AUTH_ACCESS_COOKIE_NAME,
        **common,
    )

    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        **common,
    )

    response.headers["Cache-Control"] = "no-store"


def _safe_user_payload(
    user: AuthenticatedUser,
) -> dict[str, object]:
    return {
        "authenticated": True,
        "user": {
            "id": str(user.user_id),
            "email": user.profile.email,
            "display_name": user.profile.display_name,
            "role": user.role.value,
            "aal": user.principal.aal,
            "has_mfa": user.has_mfa,
            "mfa_required": user.profile.mfa_required,
        },
    }


def _translate_auth_error(exc: Exception) -> HTTPException:
    if isinstance(
        exc,
        (
            InvalidCredentialsError,
            InvalidAccessTokenError,
            SessionRefreshError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais ou sessao invalidas.",
            headers={
                "WWW-Authenticate": "Bearer",
                "Cache-Control": "no-store",
            },
        )

    if isinstance(
        exc,
        (
            InactiveUserError,
            InvalidProfileError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sem acesso ao PredArb.",
            headers={"Cache-Control": "no-store"},
        )

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "O servico de autenticacao esta "
            "temporariamente indisponivel."
        ),
        headers={"Cache-Control": "no-store"},
    )


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
):
    try:
        tokens = await get_session_client().password_login(
            email=payload.email,
            password=payload.password,
        )

        user = await (
            auth_dependencies
            .get_auth_service()
            .authenticate(tokens.access_token)
        )

    except (
        AuthConfigurationError,
        AuthProviderError,
        InactiveUserError,
        InvalidAccessTokenError,
        InvalidCredentialsError,
        InvalidProfileError,
        ProfileLookupError,
    ) as exc:
        raise _translate_auth_error(exc) from exc

    _set_session_cookies(response, tokens)
    return _safe_user_payload(user)


@router.post("/refresh")
async def refresh_session(
    request: Request,
    response: Response,
):
    refresh_token = str(
        request.cookies.get(
            settings.AUTH_REFRESH_COOKIE_NAME,
            "",
        )
        or ""
    ).strip()

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessao de renovacao ausente.",
            headers={"Cache-Control": "no-store"},
        )

    try:
        tokens = await (
            get_session_client()
            .refresh_session(refresh_token)
        )

        user = await (
            auth_dependencies
            .get_auth_service()
            .authenticate(tokens.access_token)
        )

    except (
        AuthConfigurationError,
        AuthProviderError,
        InactiveUserError,
        InvalidAccessTokenError,
        InvalidProfileError,
        ProfileLookupError,
        SessionRefreshError,
    ) as exc:
        _clear_session_cookies(response)
        raise _translate_auth_error(exc) from exc

    _set_session_cookies(response, tokens)
    return _safe_user_payload(user)


@router.get("/me")
async def current_user(
    user: AuthenticatedUser = Depends(
        require_authenticated_user
    ),
):
    return _safe_user_payload(user)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    request: Request,
    response: Response,
):
    access_token = str(
        request.cookies.get(
            settings.AUTH_ACCESS_COOKIE_NAME,
            "",
        )
        or ""
    ).strip()

    try:
        await get_session_client().logout(access_token)
    except (
        AuthConfigurationError,
        AuthProviderError,
    ):
        pass

    _clear_session_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/config", include_in_schema=False)
async def auth_config():
    """Configura??o p?blica m?nima para a interface de login."""

    return {
        "enabled": settings.AUTH_ENABLED,
        "dashboard_required": (
            settings.AUTH_REQUIRED_FOR_DASHBOARD
        ),
        "login_path": settings.AUTH_LOGIN_PATH,
        "after_login_path": (
            settings.AUTH_AFTER_LOGIN_PATH
        ),
    }
