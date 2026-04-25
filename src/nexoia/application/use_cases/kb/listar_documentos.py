from __future__ import annotations

from nexoia.domain.entities.knowledge_document import KnowledgeDocument


class ListarDocumentos:
    """Use case: paginated list of documents for an account."""

    def __init__(self, doc_repo) -> None:
        self._doc_repo = doc_repo

    async def execute(
        self, account_id: int, offset: int = 0, limit: int = 20
    ) -> list[KnowledgeDocument]:
        return await self._doc_repo.list_by_account(account_id, offset=offset, limit=limit)
