from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.kb import jwt_handler
from shared.domain.entities.identity import Identity


def _pre_auth_token(identity_id: str, *, must_change: bool = False) -> str:
    return jwt_handler.create_access_token(
        data={
            "sub": "a@x.com",
            "identity_id": identity_id,
            "user_id": identity_id,
            "scope": "pre_auth",
            "must_change_password": must_change,
        },
        secret="s",
        expire_minutes=10,
    )


def _auth_app():
    from interface.http.routers.admin.auth import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


# ── pre_auth REJEITADO por switch-account (que usa require_admin) ────────────


@pytest.mark.asyncio
async def test_pre_auth_token_rejected_by_switch_account():
    ident = Identity(email="a@x.com", password_hash="h", name="A", must_change_password=False)
    pre = _pre_auth_token(ident.id)

    with patch("interface.http.deps.admin_auth.get_settings") as ms2:
        ms2.return_value.jwt_secret = "s"
        r = TestClient(_auth_app()).post(
            "/admin/auth/switch-account",
            json={"account_id": str(uuid4())},
            headers={"Authorization": f"Bearer {pre}"},
        )
    assert r.status_code == 403


# ── pre_auth REJEITADO por qualquer endpoint protegido por require_admin ─────


@pytest.mark.asyncio
async def test_pre_auth_token_rejected_by_require_admin_endpoint():
    app = FastAPI()

    @app.get("/protected")
    async def protected(auth: AdminAuth = Depends(require_admin)) -> dict[str, str]:
        return {"ok": "yes"}

    pre = _pre_auth_token("uid")
    with patch("interface.http.deps.admin_auth.get_settings") as ms2:
        ms2.return_value.jwt_secret = "s"
        r = TestClient(app).get("/protected", headers={"Authorization": f"Bearer {pre}"})
    assert r.status_code == 403


# ── full token continua sendo ACEITO por require_admin ───────────────────────


@pytest.mark.asyncio
async def test_full_token_accepted_by_require_admin_endpoint():
    app = FastAPI()

    @app.get("/protected")
    async def protected(auth: AdminAuth = Depends(require_admin)) -> dict[str, str]:
        return {"ok": "yes"}

    full = jwt_handler.create_access_token(
        data={
            "sub": "a@x.com",
            "identity_id": "uid",
            "user_id": "uid",
            "account_id": str(uuid4()),
            "membership_id": "m",
            "role": "admin",
        },
        secret="s",
        expire_minutes=60,
    )
    with patch("interface.http.deps.admin_auth.get_settings") as ms2:
        ms2.return_value.jwt_secret = "s"
        r = TestClient(app).get("/protected", headers={"Authorization": f"Bearer {full}"})
    assert r.status_code == 200
