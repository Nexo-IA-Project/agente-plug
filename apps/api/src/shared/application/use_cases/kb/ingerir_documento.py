from __future__ import annotations

from shared.adapters.kb.chunker import TextChunker
from shared.adapters.kb.text_extractor import TextExtractor
from shared.domain.entities.knowledge_chunk import KnowledgeChunk
from shared.domain.entities.knowledge_document import DocumentStatus
from shared.domain.ports.embeddings_port import EmbeddingsPort


class IngerirDocumento:
    """
    Use case: extract text from uploaded content, chunk it, embed, and store.
    Idempotent: deletes existing chunks before re-indexing.
    """

    def __init__(
        self,
        doc_repo,
        chunk_repo,
        extractor: TextExtractor,
        chunker: TextChunker,
        embeddings: EmbeddingsPort,
    ) -> None:
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo
        self._extractor = extractor
        self._chunker = chunker
        self._embeddings = embeddings

    async def execute(self, doc_id: str, content: bytes, account_id: int) -> None:
        await self._doc_repo.update_status(doc_id, DocumentStatus.PROCESSING)
        try:
            doc = await self._doc_repo.get(doc_id, account_id)
            text = self._extractor.extract(content, doc.mime_type)
            chunks = self._chunker.chunk(text)
            embeddings = await self._embeddings.embed_batch(chunks)
            chunk_entities = [
                KnowledgeChunk(
                    document_id=doc_id,
                    account_id=account_id,
                    text=chunks[i],
                    chunk_index=i,
                    token_count=len(chunks[i].split()),
                    embedding=embeddings[i],
                )
                for i in range(len(chunks))
            ]
            await self._chunk_repo.delete_by_document(doc_id)  # idempotency
            await self._chunk_repo.save_batch(chunk_entities)
            await self._doc_repo.update_chunk_count(doc_id, len(chunks))
            await self._doc_repo.update_status(doc_id, DocumentStatus.INDEXED)
        except Exception as e:
            await self._doc_repo.update_status(doc_id, DocumentStatus.ERROR, str(e))
            raise
