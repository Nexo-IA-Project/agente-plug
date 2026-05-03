"""EmbeddingsKnowledgeAdapter — adapts ChunkRepository + OpenAI embeddings to KnowledgePort."""

from __future__ import annotations

from openai import AsyncOpenAI

from shared.adapters.db.repositories.chunk_repo import ChunkRepository
from shared.domain.ports.knowledge import KnowledgeChunk


class EmbeddingsKnowledgeAdapter:
    """Implements KnowledgePort using pgvector similarity search + OpenAI embeddings."""

    def __init__(
        self,
        chunk_repo: ChunkRepository,
        openai_client: AsyncOpenAI,
        embedding_model: str = "text-embedding-3-small",
    ) -> None:
        self._repo = chunk_repo
        self._client = openai_client
        self._model = embedding_model

    async def search(
        self,
        query: str,
        account_id: int,
        threshold: float = 0.55,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]:
        resp = await self._client.embeddings.create(input=query, model=self._model)
        embedding = resp.data[0].embedding
        rows = await self._repo.similarity_search(
            account_id=account_id,
            embedding=embedding,
            top_k=top_k,
            threshold=threshold,
        )
        return [
            KnowledgeChunk(
                id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                account_id=account_id,
                text=str(row["text"]),
                chunk_index=int(row["chunk_index"]),
                score=float(row["score"]),
            )
            for row in rows
        ]
