from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import KnowledgeDocumentModel
from shared.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument


class DocumentRepository:
    """Session lifecycle managed by caller (Unit of Work). Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, doc: KnowledgeDocument) -> None:
        model = KnowledgeDocumentModel(
            id=doc.id,
            account_id=doc.account_id,
            filename=doc.filename,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            status=doc.status.value,
            chunk_count=doc.chunk_count,
            tags=list(doc.tags),
            error_message=doc.error_message,
            created_by=doc.created_by,
        )
        self._session.add(model)
        await self._session.flush()

    async def get(self, doc_id: str, account_id: int) -> KnowledgeDocument | None:
        result = await self._session.execute(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == doc_id)
            .where(KnowledgeDocumentModel.account_id == account_id)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)

    async def list_by_account(
        self, account_id: int, offset: int = 0, limit: int = 20
    ) -> list[KnowledgeDocument]:
        result = await self._session.execute(
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.account_id == account_id)
            .order_by(KnowledgeDocumentModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    async def update_status(
        self, doc_id: str, status: DocumentStatus, error: str | None = None
    ) -> None:
        model = await self._session.get(KnowledgeDocumentModel, doc_id)
        if model is None:
            raise ValueError(f"KnowledgeDocument {doc_id} not found")
        model.status = status.value
        model.error_message = error
        await self._session.flush()

    async def update_chunk_count(self, doc_id: str, count: int) -> None:
        model = await self._session.get(KnowledgeDocumentModel, doc_id)
        if model is None:
            raise ValueError(f"KnowledgeDocument {doc_id} not found")
        model.chunk_count = count
        await self._session.flush()

    async def delete(self, doc_id: str, account_id: int) -> None:
        await self._session.execute(
            delete(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == doc_id)
            .where(KnowledgeDocumentModel.account_id == account_id)
        )
        await self._session.flush()

    def _to_entity(self, model: KnowledgeDocumentModel) -> KnowledgeDocument:
        return KnowledgeDocument(
            id=str(model.id),
            account_id=model.account_id,
            filename=model.filename,
            mime_type=model.mime_type,
            file_size_bytes=model.file_size_bytes,
            status=DocumentStatus(model.status),
            chunk_count=model.chunk_count,
            tags=list(model.tags or []),
            error_message=model.error_message,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
