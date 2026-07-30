"""Dependencias HTTP de autenticacao e autorizacao."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.auth.errors import (
    AuthConfigurationError,
    InactiveUserError,
    InsufficientRoleError,
    InvalidAccessTokenError,
    InvalidProfileError,
    MFARequiredError,
    ProfileLookupError,
)
from app.auth.jwt_verifier import SupabaseJWTVerifier
from app.auth.profile import AppRole, AuthenticatedUser
from app.auth.profile_client import SupabaseProfileClient
from app.auth.service import SupabaseAuthService
from app.core.settings import settings


_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_auth_service() -> SupabaseAuthService:
    if not settings.AUTH_ENABLED:
        raise AuthConfigurationError(
            "A autenticacao Supabase esta desabilitada."
        )

    return SupabaseAuthService(
        verifier=SupabaseJWTVerifier(settings),
        profile_client=SupabaseProfileClient(settings),
    )


def clear_auth_service_cache() -> None:
    get_auth_service.cache_clear()


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticacao obrigatoria.",
        headers={
            "WWW-Authenticate": "Bearer",
            "Cache-Control": "no-store",
        },
    )


def _forbidden(
    detail: str = "Acesso nao autorizado.",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
        headers={"Cache-Control": "no-store"},
    )


def _service_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "O servico de autenticacao esta "
            "temporariamente indisponivel."
        ),
        headers={"Cache-Control": "no-store"},
    )


def _extract_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str:
    if credentials is not None:
        if credentials.scheme.lower() != "bearer":
            raise _unauthorized()

        bearer_token = str(
            credentials.credentials or ""
        ).strip()

        if bearer_token:
            return bearer_token

    cookie_token = str(
        request.cookies.get(
            settings.AUTH_ACCESS_COOKIE_NAME,
            "",
        )
        or ""
    ).strip()

    if cookie_token:
        return cookie_token

    raise _unauthorized()


async def _authenticate_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> AuthenticatedUser:
    access_token = _extract_access_token(
        request,
        credentials,
    )

    try:
        service = get_auth_service()
        return await service.authenticate(access_token)

    except InvalidAccessTokenError as exc:
        raise _unauthorized() from exc

    except (
        InactiveUserError,
        InvalidProfileError,
    ) as exc:
        raise _forbidden() from exc

    except (
        AuthConfigurationError,
        ProfileLookupError,
    ) as exc:
        raise _service_unavailable() from exc


async def require_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme
    ),
) -> AuthenticatedUser:
    return await _authenticate_request(
        request,
        credentials,
    )


async def require_dashboard_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme
    ),
) -> AuthenticatedUser | None:
    if not settings.AUTH_REQUIRED_FOR_DASHBOARD:
        return None

    user = await _authenticate_request(
        request,
        credentials,
    )

    try:
        user.require_mfa()
    except MFARequiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Autenticacao em duas etapas obrigatoria."
            ),
            headers={
                "Cache-Control": "no-store",
            },
        ) from exc

    return user


async def require_dashboard_operator(
    user: AuthenticatedUser | None = Depends(
        require_dashboard_user
    ),
) -> AuthenticatedUser | None:
    if user is None:
        return None

    try:
        user.require_role(
            AppRole.OPERATOR,
            AppRole.ADMIN,
        )
    except (
        InactiveUserError,
        InsufficientRoleError,
    ) as exc:
        raise _forbidden(
            "Esta operacao exige perfil operator ou admin."
        ) from exc

    return user


async def require_dashboard_admin(
    user: AuthenticatedUser | None = Depends(
        require_dashboard_user
    ),
) -> AuthenticatedUser | None:
    if user is None:
        return None

    try:
        user.require_role(AppRole.ADMIN)
    except (
        InactiveUserError,
        InsufficientRoleError,
    ) as exc:
        raise _forbidden(
            "Esta operacao exige perfil admin."
        ) from exc

    return user


async def require_operational_mfa(
    user: AuthenticatedUser | None = Depends(
        require_dashboard_operator
    ),
) -> AuthenticatedUser | None:
    if user is None:
        return None

    if not settings.AUTH_REQUIRE_MFA_FOR_OPERATIONS:
        return user

    try:
        user.require_mfa()
    except MFARequiredError as exc:
        raise _forbidden(
            "Esta operacao exige autenticacao multifator."
        ) from exc

    return user
