from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.auth import dependencies
from app.auth.errors import MFARequiredError


class UserStub:
    def __init__(
        self,
        *,
        mfa_required: bool,
    ) -> None:
        self.mfa_required = mfa_required

    def require_mfa(self) -> None:
        if self.mfa_required:
            raise MFARequiredError(
                "Sessao AAL2 obrigatoria."
            )


@pytest.mark.asyncio
async def test_dashboard_rejects_aal1_when_mfa_required(
    monkeypatch,
):
    user = UserStub(mfa_required=True)

    authenticate = AsyncMock(
        return_value=user,
    )

    monkeypatch.setattr(
        dependencies.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    monkeypatch.setattr(
        dependencies,
        "_authenticate_request",
        authenticate,
    )

    with pytest.raises(HTTPException) as captured:
        await dependencies.require_dashboard_user(
            SimpleNamespace(),
            None,
        )

    assert captured.value.status_code == 403
    assert captured.value.detail == (
        "Autenticacao em duas etapas obrigatoria."
    )

    authenticate.assert_awaited_once()


@pytest.mark.asyncio
async def test_dashboard_accepts_aal2_session(
    monkeypatch,
):
    user = UserStub(mfa_required=False)

    monkeypatch.setattr(
        dependencies.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    monkeypatch.setattr(
        dependencies,
        "_authenticate_request",
        AsyncMock(return_value=user),
    )

    result = await dependencies.require_dashboard_user(
        SimpleNamespace(),
        None,
    )

    assert result is user


@pytest.mark.asyncio
async def test_dashboard_auth_disabled_returns_none(
    monkeypatch,
):
    authenticate = AsyncMock()

    monkeypatch.setattr(
        dependencies.settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        False,
    )

    monkeypatch.setattr(
        dependencies,
        "_authenticate_request",
        authenticate,
    )

    result = await dependencies.require_dashboard_user(
        SimpleNamespace(),
        None,
    )

    assert result is None
    authenticate.assert_not_awaited()
