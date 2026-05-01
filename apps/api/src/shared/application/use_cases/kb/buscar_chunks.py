from __future__ import annotations

from shared.domain.ports.embeddings_port import EmbeddingsPort


class BuscarChunks:
    """
    Use case: embed a query, search for similar chunks, log misses.
    """

    def __init__(self, chunk_repo, embeddings: EmbeddingsPort, usage_repo) -> None:
        self._chunk_repo = chunk_repo
        self._embeddings = embeddings
        self._usage_repo = usage_repo

    async def execute(
        self,
        account_id: int,
        query: str,
        top_k: int = 5,
        threshold: float = 0.55,
    ) -> list[dict]:
        embedding = await self._embeddings.embed(query)
        results = await self._chunk_repo.similarity_search(
            account_id=account_id,
            embedding=embedding,
            top_k=top_k,
            threshold=threshold,
        )
        if not results:
            await self._usage_repo.record_no_result(account_id=account_id, query=query)
        return results
