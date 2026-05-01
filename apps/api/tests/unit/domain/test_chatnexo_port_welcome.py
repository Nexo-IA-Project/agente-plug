import pytest

from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


@pytest.mark.asyncio
async def test_get_open_conversation_returns_id_when_exists():
    client = FakeChatNexoClient(open_conversation_id="conv-999")
    result = await client.get_open_conversation(account_id=1, contact_phone="+5511999999999")
    assert result == "conv-999"


@pytest.mark.asyncio
async def test_get_open_conversation_returns_none_when_not_exists():
    client = FakeChatNexoClient(open_conversation_id=None)
    result = await client.get_open_conversation(account_id=1, contact_phone="+5511999999999")
    assert result is None


@pytest.mark.asyncio
async def test_create_conversation_returns_new_id():
    client = FakeChatNexoClient(new_conversation_id="conv-new-001")
    result = await client.create_conversation(account_id=1, contact_phone="+5511999999999")
    assert result == "conv-new-001"
