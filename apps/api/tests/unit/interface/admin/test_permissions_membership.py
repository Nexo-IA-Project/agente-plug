from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from interface.http.deps.admin_auth import AdminAuth
from interface.http.deps.permissions import _check_permission


def _auth(role: str, membership_id: str | None = "m-1") -> AdminAuth:
    return AdminAuth(
        account_id=None,
        user_email="a@x.com",
        user_role=role,
        user_id="id-1",
        identity_id="id-1",
        membership_id=membership_id,
        user_name="A",
        must_change_password=False,
    )


@pytest.mark.asyncio
async def test_admin_bypasses_permission_check():
    out = await _check_permission(_auth("admin"), "users.manage")
    assert out.user_role == "admin"


@pytest.mark.asyncio
async def test_operator_denied_when_missing_permission():
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    with (
        patch("interface.http.deps.permissions.session_scope", return_value=sess),
        patch(
            "interface.http.deps.permissions.resolve_membership_permissions",
            new=AsyncMock(return_value=set()),
        ),
    ):
        with pytest.raises(Exception) as exc:
            await _check_permission(_auth("operator"), "users.manage")
        assert "403" in str(exc.value) or "Permiss" in str(exc.value)
