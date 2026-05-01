import uuid
from unittest.mock import AsyncMock

from shared.memory.long_term import LongTermMemory


async def test_long_term_memory_merges_on_update() -> None:
    repo = AsyncMock()
    repo.get_facts = AsyncMock(return_value={"name": "Ana"})
    repo.update_facts = AsyncMock()

    mem = LongTermMemory(repo=repo)
    await mem.update(account_id=uuid.uuid4(), contact_id=uuid.uuid4(), facts={"email": "a@b.com"})

    saved = repo.update_facts.await_args.kwargs["facts"]
    assert saved == {"name": "Ana", "email": "a@b.com"}


async def test_long_term_memory_get_returns_empty_dict_when_no_facts() -> None:
    repo = AsyncMock()
    repo.get_facts = AsyncMock(return_value={})
    mem = LongTermMemory(repo=repo)
    result = await mem.get(account_id=uuid.uuid4(), contact_id=uuid.uuid4())
    assert result == {}
