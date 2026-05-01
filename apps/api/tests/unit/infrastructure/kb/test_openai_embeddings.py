# tests/unit/infrastructure/kb/test_openai_embeddings.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.adapters.kb.openai_embeddings import OpenAIEmbeddingsAdapter


@pytest.mark.asyncio
async def test_embed_returns_list_of_floats():
    mock_client = AsyncMock()
    embedding_data = MagicMock()
    embedding_data.embedding = [0.1, 0.2, 0.3]
    mock_client.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[embedding_data])
    )
    adapter = OpenAIEmbeddingsAdapter(mock_client, model="text-embedding-3-small")
    result = await adapter.embed("hello world")
    assert result == [0.1, 0.2, 0.3]
    mock_client.embeddings.create.assert_awaited_once_with(
        input="hello world", model="text-embedding-3-small"
    )


@pytest.mark.asyncio
async def test_embed_batch_returns_list_of_embeddings():
    mock_client = AsyncMock()
    e1 = MagicMock()
    e1.embedding = [0.1, 0.2]
    e2 = MagicMock()
    e2.embedding = [0.3, 0.4]
    mock_client.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[e1, e2])
    )
    adapter = OpenAIEmbeddingsAdapter(mock_client)
    result = await adapter.embed_batch(["text one", "text two"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_client.embeddings.create.assert_awaited_once_with(
        input=["text one", "text two"], model="text-embedding-3-small"
    )


def test_embeddings_port_protocol_satisfied():
    """OpenAIEmbeddingsAdapter implements EmbeddingsPort (structural check)."""
    from unittest.mock import AsyncMock

    from shared.domain.ports.embeddings_port import EmbeddingsPort
    adapter = OpenAIEmbeddingsAdapter(AsyncMock())
    assert isinstance(adapter, EmbeddingsPort)
