from __future__ import annotations

import base64
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth, require_admin


def _auth(role="admin", membership_id=None):
    return AdminAuth(
        account_id=uuid.uuid4(),
        user_email="x@x.com",
        user_role=role,
        user_id="uid",
        identity_id="uid",
        membership_id=membership_id,
        user_name="",
        must_change_password=False,
    )


def _make_app(auth):
    from interface.http.routers.admin.me import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    app.dependency_overrides[require_admin] = lambda: auth
    return app


def _fake_identity(profile_id=None):
    ident = MagicMock()
    ident.id = "uid"
    ident.name = "Fabio"
    ident.email = "f@x.com"
    ident.must_change_password = False
    ident.avatar = None
    return ident


def test_get_me_returns_identity():
    with patch("interface.http.routers.admin.me.session_scope") as mock_scope:
        s = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=s)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("interface.http.routers.admin.me.IdentityRepository") as MockRepo,
            patch(
                "interface.http.routers.admin.me.resolve_membership_permissions",
                AsyncMock(return_value=set()),
            ),
        ):
            instance = MagicMock()
            instance.get_by_id = AsyncMock(return_value=_fake_identity())
            MockRepo.return_value = instance

            app = _make_app(_auth())
            client = TestClient(app)
            r = client.get("/admin/me")
            assert r.status_code == 200
            assert r.json()["name"] == "Fabio"
            assert r.json()["permissions"] == []


def test_get_me_includes_profile_when_assigned():
    pid = uuid.uuid4()
    membership = MagicMock()
    membership.profile_id = pid

    with patch("interface.http.routers.admin.me.session_scope") as mock_scope:
        s = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=s)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("interface.http.routers.admin.me.IdentityRepository") as MockRepo,
            patch("interface.http.routers.admin.me.MembershipRepository") as MockMembershipRepo,
            patch("interface.http.routers.admin.me.ProfileRepository") as MockProfileRepo,
            patch(
                "interface.http.routers.admin.me.resolve_membership_permissions",
                AsyncMock(return_value=set()),
            ),
        ):
            instance = MagicMock()
            instance.get_by_id = AsyncMock(return_value=_fake_identity())
            MockRepo.return_value = instance
            membership_repo = MagicMock()
            membership_repo.get_by_id = AsyncMock(return_value=membership)
            MockMembershipRepo.return_value = membership_repo
            prof = MagicMock()
            prof.name_map = AsyncMock(return_value={pid: "Gerente"})
            MockProfileRepo.return_value = prof

            app = _make_app(_auth(membership_id="m1"))
            client = TestClient(app)
            r = client.get("/admin/me")
            assert r.status_code == 200
            body = r.json()
            assert body["profile_id"] == str(pid)
            assert body["profile_name"] == "Gerente"


def _get_me_with_permissions(perms):
    with patch("interface.http.routers.admin.me.session_scope") as mock_scope:
        s = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=s)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("interface.http.routers.admin.me.IdentityRepository") as MockRepo,
            patch(
                "interface.http.routers.admin.me.resolve_membership_permissions",
                AsyncMock(return_value=perms),
            ),
        ):
            instance = MagicMock()
            instance.get_by_id = AsyncMock(return_value=_fake_identity())
            MockRepo.return_value = instance

            app = _make_app(_auth())
            client = TestClient(app)
            r = client.get("/admin/me")
            assert r.status_code == 200
            return r.json()


def test_get_me_admin_has_all_permissions():
    from shared.domain.permissions.catalog import all_permission_keys

    body = _get_me_with_permissions(set(all_permission_keys()))
    assert len(body["permissions"]) == len(all_permission_keys())


def test_get_me_operator_permissions():
    body = _get_me_with_permissions({"leads.view", "dashboard.view"})
    assert body["permissions"] == ["dashboard.view", "leads.view"]


def test_update_avatar_rejects_oversized():
    big = b"x" * (250 * 1024)
    payload = base64.b64encode(big).decode()
    app = _make_app(_auth())
    client = TestClient(app)
    r = client.put("/admin/me/avatar", json={"data": payload})
    assert r.status_code == 413


def test_update_avatar_rejects_invalid_base64():
    app = _make_app(_auth())
    client = TestClient(app)
    r = client.put("/admin/me/avatar", json={"data": "not!!!base64!!!"})
    assert r.status_code == 422


# ── /me/memberships ──────────────────────────────────────────────────────────

def _fake_member_view(account_id, account_name, role="admin", is_owner=False):
    v = MagicMock()
    v.account_id = account_id
    v.account_name = account_name
    v.role = MagicMock()
    v.role.value = role
    v.is_owner = is_owner
    return v


def test_list_my_memberships_marks_is_current_correctly():
    current_account_id = uuid.uuid4()
    other_account_id = uuid.uuid4()

    view_current = _fake_member_view(current_account_id, "Empresa Atual", role="admin", is_owner=True)
    view_other = _fake_member_view(other_account_id, "Outra Empresa", role="operator", is_owner=False)

    auth = AdminAuth(
        account_id=current_account_id,
        user_email="x@x.com",
        user_role="admin",
        user_id="uid",
        identity_id="uid",
        membership_id="m1",
        user_name="",
        must_change_password=False,
    )

    with patch("interface.http.routers.admin.me.session_scope") as mock_scope:
        s = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=s)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.me.MembershipRepository") as MockMembershipRepo:
            membership_repo = MagicMock()
            membership_repo.list_active_by_identity = AsyncMock(
                return_value=[view_current, view_other]
            )
            MockMembershipRepo.return_value = membership_repo

            app = _make_app(auth)
            client = TestClient(app)
            r = client.get("/admin/me/memberships")

    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2

    current_item = next(i for i in items if i["account_id"] == str(current_account_id))
    other_item = next(i for i in items if i["account_id"] == str(other_account_id))

    assert current_item["is_current"] is True
    assert current_item["account_name"] == "Empresa Atual"
    assert current_item["role"] == "admin"
    assert current_item["is_owner"] is True

    assert other_item["is_current"] is False
    assert other_item["account_name"] == "Outra Empresa"
    assert other_item["role"] == "operator"
    assert other_item["is_owner"] is False
