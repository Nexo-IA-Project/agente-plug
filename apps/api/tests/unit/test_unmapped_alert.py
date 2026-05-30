from unittest.mock import AsyncMock

import pytest

from shared.application.unmapped_alert import make_unmapped_alert


@pytest.mark.asyncio
async def test_alert_skipped_without_target():
    chatnexo = AsyncMock()
    alert = make_unmapped_alert(chatnexo=chatnexo, account_id="1", inbox_id=1, target="")
    await alert("LE", "offer-1", "Cissa", "+5511")
    chatnexo.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_alert_sends_when_target():
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="55")
    chatnexo.send_message = AsyncMock()
    alert = make_unmapped_alert(
        chatnexo=chatnexo, account_id="1", inbox_id=1, target="+5534999999999"
    )
    await alert("LE", "offer-1", "Cissa", "+5511")
    chatnexo.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_alert_never_raises_on_chatnexo_error():
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation = AsyncMock(side_effect=RuntimeError("boom"))
    alert = make_unmapped_alert(
        chatnexo=chatnexo, account_id="1", inbox_id=1, target="+5534999999999"
    )
    await alert("LE", "offer-1", "Cissa", "+5511")  # não deve levantar
