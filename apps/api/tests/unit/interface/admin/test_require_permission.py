from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

# Ensure the module is imported so patch paths resolve correctly.
import interface.http.deps.permissions  # noqa: F401
from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.deps.permissions import require_permission, resolve_user_permissions
from shared.domain.permissions.catalog import (
    ADMIN_ONLY_KEYS,
    all_permission_keys,
)


def _auth(role: str) -> AdminAuth:
    return AdminAuth(
        account_id=uuid.uuid4(),
        user_email="a@x.com",
        user_role=role,
        user_id="user-1",
        user_name="",
        must_change_password=False,
    )


def _make_app(role: str) -> FastAPI:
    app = FastAPI()

    @app.get("/protected")
    async def _protected(auth: AdminAuth = Depends(require_permission("x.y"))) -> dict:
        return {"ok": True}

    app.dependency_overrides[require_admin] = lambda: _auth(role)
    return app


def test_require_permission_admin_passes_without_touching_db():
    # Admin short-circuits; if it touched session_scope this would raise.
    with patch(
        "interface.http.deps.permissions.session_scope",
        side_effect=AssertionError("admin must not query the DB"),
    ):
        client = TestClient(_make_app("admin"))
        r = client.get("/protected")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


def test_require_permission_operator_with_key_passes():
    with patch(
        "interface.http.deps.permissions.resolve_user_permissions",
        new=AsyncMock(return_value={"x.y"}),
    ):
        client = TestClient(_make_app("operator"))
        r = client.get("/protected")
        assert r.status_code == 200
        assert r.json() == {"ok": True}


def test_require_permission_operator_without_key_403():
    with patch(
        "interface.http.deps.permissions.resolve_user_permissions",
        new=AsyncMock(return_value={"other.perm"}),
    ):
        client = TestClient(_make_app("operator"))
        r = client.get("/protected")
        assert r.status_code == 403
        assert r.json()["detail"] == "Permissão insuficiente"


@pytest.mark.asyncio
async def test_resolve_user_permissions_admin_returns_all():
    session = AsyncMock()
    perms = await resolve_user_permissions(session, user_id="x", role="admin")
    assert perms == set(all_permission_keys())
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_user_permissions_operator_without_profile_empty():
    session = AsyncMock()
    profile_result = AsyncMock()
    profile_result.scalar_one_or_none = lambda: None
    session.execute = AsyncMock(return_value=profile_result)

    perms = await resolve_user_permissions(session, user_id="x", role="operator")
    assert perms == set()


@pytest.mark.asyncio
async def test_resolve_user_permissions_operator_with_profile():
    profile_id = uuid.uuid4()
    session = AsyncMock()

    profile_result = AsyncMock()
    profile_result.scalar_one_or_none = lambda: profile_id

    perm_scalars = AsyncMock()
    perm_scalars.all = lambda: ["x.y", "z.w"]
    perm_result = AsyncMock()
    perm_result.scalars = lambda: perm_scalars

    session.execute = AsyncMock(side_effect=[profile_result, perm_result])

    perms = await resolve_user_permissions(session, user_id="x", role="operator")
    assert perms == {"x.y", "z.w"}


def test_profiles_keys_in_catalog():
    keys = all_permission_keys()
    assert "profiles.view" in keys
    assert "profiles.manage" in keys


def test_profiles_keys_admin_only():
    assert "profiles.view" in ADMIN_ONLY_KEYS
    assert "profiles.manage" in ADMIN_ONLY_KEYS
