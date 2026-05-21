# tests/unit/interface/admin/test_admin_deps.py
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException


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
