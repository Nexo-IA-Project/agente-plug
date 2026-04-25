from __future__ import annotations

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from nexoia.infrastructure.db.models import KnowledgeChunkModel


class ChunkRepository:
    """Session lifecycle managed by caller (Unit of Work). Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_batch(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        for chunk in chunks:
            model = KnowledgeChunkModel(
                id=chunk.id,
                document_id=chunk.document_id,
                account_id=chunk.account_id,
                text=chunk.text,
                chunk_index=chunk.chunk_index,
                token_count=chunk.token_count,
                embedding=chunk.embedding,
            )
            self._session.add(model)
        await self._session.flush()

    async def delete_by_document(self, document_id: str) -> None:
        await self._session.execute(
            delete(KnowledgeChunkModel).where(
                KnowledgeChunkModel.document_id == document_id
            )
        )
        await self._session.flush()

    async def similarity_search(
        self,
        account_id: int,
        embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.55,
    ) -> list[dict]:
        embedding_literal = f"[{','.join(str(v) for v in embedding)}]"
        stmt = text("""
            SELECT id, document_id, text, chunk_index,
                   1 - (embedding <=> :emb::vector) AS score
            FROM knowledge_chunks
            WHERE account_id = :account_id
              AND 1 - (embedding <=> :emb::vector) >= :threshold
            ORDER BY score DESC
            LIMIT :top_k
        """)
        result = await self._session.execute(
            stmt,
            {
                "emb": embedding_literal,
                "account_id": account_id,
                "threshold": threshold,
                "top_k": top_k,
            },
        )
        return [
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "text": row.text,
                "chunk_index": row.chunk_index,
                "score": float(row.score),
            }
            for row in result.fetchall()
        ]
