# tests/unit/interface/admin/test_admin_deps.py
from __future__ import annotations

from unittest.mock import patch
from uuid import UUID

import pytest
from fastapi import HTTPException

_ACC = UUID("47418057-77cc-469e-8263-d7311fe64155")


@pytest.mark.asyncio
async def test_get_admin_deps_raises_401_without_token():
    from interface.http.deps.admin_deps import get_admin_deps

    with pytest.raises(HTTPException) as exc_info:
        gen = get_admin_deps(authorization=None, nexoia_token=None)
        async for _ in gen:
            pass
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_admin_deps_raises_401_on_bad_token():
    from interface.http.deps.admin_deps import get_admin_deps

    with patch("interface.http.deps.admin_deps.get_settings") as mock_settings:
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60
        mock_settings.return_value.kb_chunk_size = 512
        mock_settings.return_value.kb_chunk_overlap = 50
        mock_settings.return_value.kb_embedding_model = "text-embedding-3-small"
        mock_settings.return_value.kb_top_k = 5
        mock_settings.return_value.kb_threshold = 0.55
        mock_settings.return_value.kb_max_file_size_mb = 20
        mock_settings.return_value.openai_api_key = "sk-test"

        with pytest.raises(HTTPException) as exc_info:
            gen = get_admin_deps(authorization="Bearer invalidtoken", nexoia_token=None)
            async for _ in gen:
                pass
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_admin_role_passes_for_admin():
    from interface.http.deps.admin_auth import AdminAuth, require_admin_role

    auth = AdminAuth(
        account_id=_ACC,
        user_email="a@x.com",
        user_role="admin",
        user_id="u1",
        identity_id="u1",
        membership_id=None,
        user_name="",
        must_change_password=False,
    )
    result = await require_admin_role(auth=auth)
    assert result is auth


@pytest.mark.asyncio
async def test_require_admin_role_blocks_operator():
    from fastapi import HTTPException

    from interface.http.deps.admin_auth import AdminAuth, require_admin_role

    auth = AdminAuth(
        account_id=_ACC,
        user_email="a@x.com",
        user_role="operator",
        user_id="u1",
        identity_id="u1",
        membership_id=None,
        user_name="",
        must_change_password=False,
    )
    with pytest.raises(HTTPException) as exc:
        await require_admin_role(auth=auth)
    assert exc.value.status_code == 403


def _decode_with_payload(payload: dict):
    """Helper: chama _decode com um verify_token mockado retornando o payload dado."""
    from interface.http.deps import admin_auth

    with (
        patch.object(admin_auth, "verify_token", return_value=payload),
        patch.object(admin_auth, "get_settings") as mock_settings,
    ):
        mock_settings.return_value.jwt_secret = "test-secret"
        return admin_auth._decode("fake-token")


def test_decode_parses_uuid_account_id():
    auth = _decode_with_payload(
        {
            "account_id": str(_ACC),
            "sub": "a@x.com",
            "role": "admin",
            "user_id": "u1",
            "must_change_password": False,
        }
    )
    assert auth.account_id == _ACC
    assert isinstance(auth.account_id, UUID)


def test_decode_tolerates_legacy_int_account_id():
    # Token legado emitido antes da migração: account_id é inteiro.
    auth = _decode_with_payload(
        {
            "account_id": 1,
            "sub": "a@x.com",
            "role": "operator",
            "user_id": "u1",
            "must_change_password": False,
        }
    )
    # Não derruba o login — apenas resolve para None.
    assert auth.account_id is None
    assert auth.user_email == "a@x.com"
    assert auth.user_role == "operator"


def test_decode_handles_missing_account_id():
    auth = _decode_with_payload(
        {
            "sub": "a@x.com",
            "role": "admin",
            "user_id": "u1",
            "must_change_password": False,
        }
    )
    assert auth.account_id is None
