"""Perfil operacional associado ao usuario Supabase."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from app.auth.errors import (
    InactiveUserError,
    InsufficientRoleError,
    MFARequiredError,
)
from app.auth.models import AuthPrincipal


class AppRole(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class UserProfile:
    user_id: UUID
    email: str | None
    display_name: str | None
    role: AppRole
    is_active: bool
    mfa_required: bool

    def require_active(self) -> None:
        if not self.is_active:
            raise InactiveUserError(
                "Usuario desativado no PredArb."
            )

    def require_role(
        self,
        *allowed_roles: AppRole,
    ) -> None:
        self.require_active()

        if self.role not in allowed_roles:
            raise InsufficientRoleError(
                "Papel insuficiente para esta operacao."
            )


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    principal: AuthPrincipal
    profile: UserProfile

    @property
    def user_id(self) -> UUID:
        return self.principal.user_id

    @property
    def role(self) -> AppRole:
        return self.profile.role

    @property
    def has_mfa(self) -> bool:
        return self.principal.has_mfa

    def require_role(
        self,
        *allowed_roles: AppRole,
    ) -> None:
        self.profile.require_role(*allowed_roles)

    def require_mfa(self) -> None:
        self.profile.require_active()

        if (
            self.profile.mfa_required
            and not self.principal.has_mfa
        ):
            raise MFARequiredError(
                "Esta operacao exige autenticacao multifator."
            )
