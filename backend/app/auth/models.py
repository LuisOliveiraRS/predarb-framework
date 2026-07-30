"""Modelos imutaveis da identidade autenticada."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping
from uuid import UUID

from app.auth.errors import MFARequiredError


@dataclass(frozen=True, slots=True)
class AuthPrincipal:
    """Identidade derivada exclusivamente de um JWT verificado."""

    user_id: UUID
    email: str | None
    token_role: str
    aal: str
    session_id: UUID | None
    claims: Mapping[str, Any]

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        email: str | None,
        token_role: str,
        aal: str,
        session_id: UUID | None,
        claims: Mapping[str, Any],
    ) -> "AuthPrincipal":
        return cls(
            user_id=user_id,
            email=email,
            token_role=token_role,
            aal=aal,
            session_id=session_id,
            claims=MappingProxyType(dict(claims)),
        )

    @property
    def has_mfa(self) -> bool:
        return self.aal == "aal2"

    def require_mfa(self) -> None:
        if not self.has_mfa:
            raise MFARequiredError(
                "Esta operacao exige autenticacao multifator."
            )
