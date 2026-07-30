"""Autenticacao e autorizacao do PredArb."""

from app.auth.dependencies import (
    clear_auth_service_cache,
    get_auth_service,
    require_dashboard_admin,
    require_dashboard_operator,
    require_dashboard_user,
    require_operational_mfa,
)
from app.auth.errors import (
    AuthConfigurationError,
    AuthenticationError,
    InactiveUserError,
    InsufficientRoleError,
    InvalidAccessTokenError,
    InvalidProfileError,
    MFARequiredError,
    ProfileLookupError,
)
from app.auth.jwt_verifier import SupabaseJWTVerifier
from app.auth.models import AuthPrincipal
from app.auth.profile import (
    AppRole,
    AuthenticatedUser,
    UserProfile,
)
from app.auth.profile_client import SupabaseProfileClient
from app.auth.service import SupabaseAuthService

__all__ = [
    "require_operational_mfa",
    "require_dashboard_user",
    "require_dashboard_operator",
    "require_dashboard_admin",
    "get_auth_service",
    "clear_auth_service_cache",
    "AppRole",
    "AuthenticatedUser",
    "AuthConfigurationError",
    "AuthenticationError",
    "AuthPrincipal",
    "InactiveUserError",
    "InsufficientRoleError",
    "InvalidAccessTokenError",
    "InvalidProfileError",
    "MFARequiredError",
    "ProfileLookupError",
    "SupabaseAuthService",
    "SupabaseJWTVerifier",
    "SupabaseProfileClient",
    "UserProfile",
]
