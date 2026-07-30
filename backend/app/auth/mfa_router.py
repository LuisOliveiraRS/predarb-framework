"""Rotas seguras para MFA/TOTP do PredArb."""

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

from app.auth import dependencies as auth_dependencies
from app.auth.dependencies import require_authenticated_user
from app.auth.errors import (
    AuthConfigurationError,
    AuthProviderError,
    InactiveUserError,
    InvalidAccessTokenError,
    InvalidProfileError,
    ProfileLookupError,
)
from app.auth.mfa_client import (
    MFAInvalidCodeError,
    MFARateLimitError,
    SupabaseMFAClient,
)
from app.auth.profile import AuthenticatedUser
from app.auth.router import (
    _safe_user_payload,
    _set_session_cookies,
)
from app.core.settings import settings


router = APIRouter(
    prefix="/auth/mfa",
    tags=["authentication"],
)


class MFAEnrollmentRequest(BaseModel):
    friendly_name: str = Field(
        default="PredArb Authenticator",
        min_length=1,
        max_length=64,
    )

    @field_validator("friendly_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = str(value or "").strip()

        if not normalized:
            return "PredArb Authenticator"

        return normalized


class MFAChallengeRequest(BaseModel):
    factor_id: str = Field(
        min_length=1,
        max_length=256,
    )


class MFAVerificationRequest(BaseModel):
    factor_id: str = Field(
        min_length=1,
        max_length=256,
    )
    challenge_id: str = Field(
        min_length=1,
        max_length=256,
    )
    code: str = Field(
        min_length=6,
        max_length=6,
    )

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        normalized = str(value or "").strip()

        if (
            len(normalized) != 6
            or not normalized.isdigit()
        ):
            raise ValueError(
                "O codigo TOTP deve conter seis digitos."
            )

        return normalized


@lru_cache(maxsize=1)
def get_mfa_client() -> SupabaseMFAClient:
    if not settings.AUTH_ENABLED:
        raise AuthConfigurationError(
            "A autenticacao Supabase esta desabilitada."
        )

    return SupabaseMFAClient(settings)


def clear_mfa_client_cache() -> None:
    get_mfa_client.cache_clear()


def _extract_access_token(request: Request) -> str:
    authorization = str(
        request.headers.get("Authorization") or ""
    ).strip()

    if authorization:
        scheme, _, token = authorization.partition(" ")

        if (
            scheme.lower() == "bearer"
            and token.strip()
        ):
            return token.strip()

    cookie_token = str(
        request.cookies.get(
            settings.AUTH_ACCESS_COOKIE_NAME,
            "",
        )
        or ""
    ).strip()

    if cookie_token:
        return cookie_token

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Sessao autenticada ausente.",
        headers={
            "WWW-Authenticate": "Bearer",
            "Cache-Control": "no-store",
        },
    )


def _translate_mfa_error(
    exc: Exception,
) -> HTTPException:
    if isinstance(
        exc,
        (
            InvalidAccessTokenError,
        ),
    ):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessao invalida ou expirada.",
            headers={
                "WWW-Authenticate": "Bearer",
                "Cache-Control": "no-store",
            },
        )

    if isinstance(exc, MFAInvalidCodeError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Codigo TOTP invalido ou expirado.",
            headers={"Cache-Control": "no-store"},
        )

    if isinstance(exc, MFARateLimitError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Aguarde antes de tentar novamente."
            ),
            headers={
                "Retry-After": "60",
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
            "O servico MFA esta temporariamente "
            "indisponivel."
        ),
        headers={"Cache-Control": "no-store"},
    )




@router.get("/status")
async def mfa_status(
    request: Request,
    user: AuthenticatedUser = Depends(
        require_authenticated_user
    ),
):
    access_token = _extract_access_token(request)

    try:
        factors = await get_mfa_client().list_factors(
            access_token=access_token,
        )

    except (
        AuthConfigurationError,
        AuthProviderError,
        InvalidAccessTokenError,
        MFARateLimitError,
    ) as exc:
        raise _translate_mfa_error(exc) from exc

    verified_factors = [
        {
            "factor_id": factor.factor_id,
            "factor_type": factor.factor_type,
            "friendly_name": factor.friendly_name,
        }
        for factor in factors
        if (
            factor.status == "verified"
            and factor.factor_type in {"", "totp"}
        )
    ]

    return {
        "current_aal": user.principal.aal,
        "has_mfa": user.has_mfa,
        "mfa_required": user.profile.mfa_required,
        "verified_factors": verified_factors,
        "can_enroll": not verified_factors,
    }

@router.post(
    "/enroll",
    status_code=status.HTTP_201_CREATED,
)
async def enroll_totp(
    payload: MFAEnrollmentRequest,
    request: Request,
    user: AuthenticatedUser = Depends(
        require_authenticated_user
    ),
):
    del user

    access_token = _extract_access_token(request)

    try:
        mfa_client = get_mfa_client()

        await mfa_client.cleanup_unverified_factors(
            access_token=access_token,
        )

        enrollment = await mfa_client.enroll_totp(
            access_token=access_token,
            friendly_name=payload.friendly_name,
        )

    except (
        AuthConfigurationError,
        AuthProviderError,
        InvalidAccessTokenError,
        MFARateLimitError,
    ) as exc:
        raise _translate_mfa_error(exc) from exc

    return {
        "factor_id": enrollment.factor_id,
        "factor_type": "totp",
        "friendly_name": enrollment.friendly_name,
        "qr_code": enrollment.qr_code,
        "secret": enrollment.secret,
        "uri": enrollment.uri,
    }


@router.post("/challenge")
async def create_totp_challenge(
    payload: MFAChallengeRequest,
    request: Request,
    user: AuthenticatedUser = Depends(
        require_authenticated_user
    ),
):
    del user

    access_token = _extract_access_token(request)

    try:
        challenge = await (
            get_mfa_client().create_challenge(
                access_token=access_token,
                factor_id=payload.factor_id,
            )
        )

    except (
        AuthConfigurationError,
        AuthProviderError,
        InvalidAccessTokenError,
        MFARateLimitError,
    ) as exc:
        raise _translate_mfa_error(exc) from exc

    return {
        "factor_id": payload.factor_id,
        "challenge_id": challenge.challenge_id,
    }


@router.post("/verify")
async def verify_totp(
    payload: MFAVerificationRequest,
    request: Request,
    response: Response,
    user: AuthenticatedUser = Depends(
        require_authenticated_user
    ),
):
    del user

    access_token = _extract_access_token(request)

    try:
        tokens = await get_mfa_client().verify_totp(
            access_token=access_token,
            factor_id=payload.factor_id,
            challenge_id=payload.challenge_id,
            code=payload.code,
        )

        authenticated_user = await (
            auth_dependencies
            .get_auth_service()
            .authenticate(tokens.access_token)
        )

        if not authenticated_user.has_mfa:
            raise AuthProviderError(
                "A sessao nao foi elevada para AAL2."
            )

    except (
        AuthConfigurationError,
        AuthProviderError,
        InactiveUserError,
        InvalidAccessTokenError,
        InvalidProfileError,
        MFAInvalidCodeError,
        MFARateLimitError,
        ProfileLookupError,
    ) as exc:
        raise _translate_mfa_error(exc) from exc

    _set_session_cookies(response, tokens)

    return {
        "verified": True,
        "factor_id": payload.factor_id,
        **_safe_user_payload(authenticated_user),
    }
