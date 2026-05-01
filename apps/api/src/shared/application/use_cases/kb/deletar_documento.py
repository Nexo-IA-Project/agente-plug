from __future__ import annotations


class DeletarDocumento:
    """Use case: delete all chunks then the document record."""

    def __init__(self, doc_repo, chunk_repo) -> None:
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo

    async def execute(self, doc_id: str, account_id: int) -> None:
        await self._chunk_repo.delete_by_document(doc_id)
        await self._doc_repo.delete(doc_id, account_id=account_id)
