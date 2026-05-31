from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.adapters.kb import jwt_handler
from shared.domain.entities.identity import Identity
from shared.domain.entities.user import UserRole


def _full_token(identity_id: str, account_id: str) -> str:
    return jwt_handler.create_access_token(
        data={
            "sub": "a@x.com",
            "identity_id": identity_id,
            "user_id": identity_id,
            "account_id": account_id,
            "membership_id": "m",
            "role": "admin",
        },
        secret="s",
        expire_minutes=60,
    )


def _app():
    from interface.http.routers.admin.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


@pytest.mark.asyncio
async def test_select_account_emits_full_token():
    acc = uuid4()
    ident = Identity(email="a@x.com", password_hash="h", name="A", must_change_password=False)
    view = MagicMock(
        membership_id=str(uuid4()),
        account_id=acc,
        account_name="C",
        role=UserRole.ADMIN,
        is_owner=True,
    )

    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    ir = MagicMock(get_by_id=AsyncMock(return_value=ident))
    mr = MagicMock(list_active_by_identity=AsyncMock(return_value=[view]))

    pre = jwt_handler.create_access_token(
        data={"sub": "a@x.com", "identity_id": ident.id, "scope": "pre_auth"},
        secret="s",
        expire_minutes=10,
    )
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/select-account",
            json={"account_id": str(acc)},
            headers={"Authorization": f"Bearer {pre}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "authenticated"


@pytest.mark.asyncio
async def test_select_account_rejects_unlinked_account():
    ident = Identity(email="a@x.com", password_hash="h", name="A", must_change_password=False)
    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    ir = MagicMock(get_by_id=AsyncMock(return_value=ident))
    mr = MagicMock(list_active_by_identity=AsyncMock(return_value=[]))
    pre = jwt_handler.create_access_token(
        data={"sub": "a@x.com", "identity_id": ident.id, "scope": "pre_auth"},
        secret="s",
        expire_minutes=10,
    )
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        r = TestClient(_app()).post(
            "/admin/auth/select-account",
            json={"account_id": str(uuid4())},
            headers={"Authorization": f"Bearer {pre}"},
        )
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_switch_account_emits_full_token():
    acc = uuid4()
    ident = Identity(email="a@x.com", password_hash="h", name="A", must_change_password=False)
    view = MagicMock(
        membership_id=str(uuid4()),
        account_id=acc,
        account_name="C",
        role=UserRole.ADMIN,
        is_owner=True,
    )

    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    ir = MagicMock(get_by_id=AsyncMock(return_value=ident))
    mr = MagicMock(list_active_by_identity=AsyncMock(return_value=[view]))

    token = _full_token(ident.id, str(acc))
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
        patch("interface.http.deps.admin_auth.get_settings") as ms2,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        ms2.return_value.jwt_secret = "s"
        r = TestClient(_app()).post(
            "/admin/auth/switch-account",
            json={"account_id": str(acc)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "authenticated"


@pytest.mark.asyncio
async def test_switch_account_rejects_unlinked_account():
    acc = uuid4()
    other_acc = uuid4()
    ident = Identity(email="a@x.com", password_hash="h", name="A", must_change_password=False)

    sess = AsyncMock()
    sess.__aenter__ = AsyncMock(return_value=sess)
    sess.__aexit__ = AsyncMock(return_value=False)
    ir = MagicMock(get_by_id=AsyncMock(return_value=ident))
    mr = MagicMock(list_active_by_identity=AsyncMock(return_value=[]))

    token = _full_token(ident.id, str(acc))
    with (
        patch("interface.http.routers.admin.auth.get_db", return_value=sess),
        patch("interface.http.routers.admin.auth.IdentityRepository", return_value=ir),
        patch("interface.http.routers.admin.auth.MembershipRepository", return_value=mr),
        patch("interface.http.routers.admin.auth.get_settings") as ms,
        patch("interface.http.deps.admin_auth.get_settings") as ms2,
    ):
        ms.return_value.jwt_secret = "s"
        ms.return_value.jwt_expire_minutes = 60
        ms2.return_value.jwt_secret = "s"
        r = TestClient(_app()).post(
            "/admin/auth/switch-account",
            json={"account_id": str(other_acc)},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 403
