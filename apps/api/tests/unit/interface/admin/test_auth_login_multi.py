from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.adapters.kb import jwt_handler
from shared.domain.entities.identity import Identity
from shared.domain.entities.user import UserRole


def _app():
    from interface.http.routers.admin.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


def _view(account_id, role, is_owner=False, name="Co"):
    v = MagicMock()
    v.membership_id = str(uuid4())
    v.account_id = account_id
    v.account_name = name
    v.role = role
    v.is_owner = is_owner
    return v


def _patches(identity, member_views):
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    sess.commit = AsyncMock()

    ident_repo = MagicMock()
    ident_repo.get_by_email = AsyncMock(return_value=identity)
    ident_repo.touch_last_login = AsyncMock()

    memb_repo = MagicMock()
    memb_repo.list_active_by_identity = AsyncMock(return_value=member_views)

    return sess, ident_repo, memb_repo


@pytest.mark.asyncio
async def test_login_single_membership_returns_full_token():
    ident = Identity(
        email="a@x.com",
        password_hash=jwt_handler.hash_password("pw"),
        name="A",
        must_change_password=False,
    )
    acc = uuid4()
    views = [_view(acc, UserRole.ADMIN, is_owner=True)]
    sess, ir, mr = _patches(ident, views)

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/login", json={"email": "a@x.com", "password": "pw"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "authenticated"
        assert "access_token" in body
        payload = jwt_handler.verify_token(body["access_token"], secret="s")
        assert payload["account_id"] == str(acc)
        assert payload["membership_id"] == views[0].membership_id


@pytest.mark.asyncio
async def test_login_multi_membership_returns_chooser():
    ident = Identity(
        email="a@x.com",
        password_hash=jwt_handler.hash_password("pw"),
        name="A",
        must_change_password=False,
    )
    views = [
        _view(uuid4(), UserRole.OPERATOR, name="C1"),
        _view(uuid4(), UserRole.ADMIN, name="C2"),
    ]
    sess, ir, mr = _patches(ident, views)

    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/login", json={"email": "a@x.com", "password": "pw"}
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "choose_account"
        assert "pre_auth_token" in body
        assert len(body["accounts"]) == 2
        assert {a["account_name"] for a in body["accounts"]} == {"C1", "C2"}


@pytest.mark.asyncio
async def test_login_no_membership_403():
    ident = Identity(
        email="a@x.com",
        password_hash=jwt_handler.hash_password("pw"),
        name="A",
        must_change_password=False,
    )
    sess, ir, mr = _patches(ident, [])
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/login", json={"email": "a@x.com", "password": "pw"}
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_login_must_change_password_returns_change_status():
    ident = Identity(
        email="a@x.com",
        password_hash=jwt_handler.hash_password("pw"),
        name="A",
        must_change_password=True,
    )
    views = [_view(uuid4(), UserRole.ADMIN)]
    sess, ir, mr = _patches(ident, views)
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/login", json={"email": "a@x.com", "password": "pw"}
        )
        assert r.status_code == 200
        assert r.json()["status"] == "must_change_password"
        assert "pre_auth_token" in r.json()
