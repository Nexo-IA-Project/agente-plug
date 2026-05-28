# apps/api/tests/unit/email/test_smtp_email_service.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.adapters.email.smtp_email_service import (
    SmtpEmailService,
    SmtpNotConfiguredError,
)


class _StubSmtpConfig:
    host = "smtp.test.com"
    port = 587
    username = "u@test.com"
    encrypted_password = "ENC"
    use_tls = True
    from_name = "NexoIA"
    from_email = "from@test.com"


@pytest.mark.asyncio
async def test_send_email_calls_aiosmtplib():
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=_StubSmtpConfig())
    mock_repo.decrypt_password = MagicMock(return_value="plain-pw")

    with patch(
        "shared.adapters.email.smtp_email_service.aiosmtplib.send", new=AsyncMock()
    ) as mock_send:
        svc = SmtpEmailService(repo=mock_repo)
        await svc.send_email(account_id=1, to="dest@test.com", subject="hi", body_html="<p>hi</p>")

        assert mock_send.await_count == 1
        kwargs = mock_send.await_args.kwargs
        assert kwargs["hostname"] == "smtp.test.com"
        assert kwargs["port"] == 587
        assert kwargs["username"] == "u@test.com"
        assert kwargs["password"] == "plain-pw"
        assert kwargs["use_tls"] is False
        assert kwargs["start_tls"] is True


@pytest.mark.asyncio
async def test_send_email_raises_when_not_configured():
    mock_repo = MagicMock()
    mock_repo.get = AsyncMock(return_value=None)

    svc = SmtpEmailService(repo=mock_repo)
    with pytest.raises(SmtpNotConfiguredError):
        await svc.send_email(account_id=1, to="x@x.com", subject="s", body_html="b")
