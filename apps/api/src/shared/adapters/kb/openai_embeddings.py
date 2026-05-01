from __future__ import annotations


class OpenAIEmbeddingsAdapter:
    """Adapts the async OpenAI client to EmbeddingsPort."""

    def __init__(self, client, model: str = "text-embedding-3-small") -> None:
        self._client = client
        self._model = model

    async def embed(self, text: str) -> list[float]:
        result = await self._client.embeddings.create(input=text, model=self._model)
        return result.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        result = await self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in result.data]
