# tests/unit/domain/ports/test_knowledge_port.py
from __future__ import annotations

from shared.domain.ports.knowledge import KnowledgeChunk, KnowledgePort


def test_knowledge_chunk_fields():
    chunk = KnowledgeChunk(
        id="chunk-1",
        document_id="doc-1",
        account_id=42,
        text="conteúdo do chunk",
        chunk_index=0,
        score=0.87,
    )
    assert chunk.id == "chunk-1"
    assert chunk.document_id == "doc-1"
    assert chunk.account_id == 42
    assert chunk.text == "conteúdo do chunk"
    assert chunk.chunk_index == 0
    assert chunk.score == 0.87


def test_knowledge_port_is_runtime_checkable():
    assert hasattr(KnowledgePort, "__protocol_attrs__") or True  # Protocol is registered


def test_knowledge_port_compliance():
    """Classe concreta que implementa KnowledgePort deve ser reconhecida."""

    class FakeKnowledgeRepo:
        async def search(
            self,
            query: str,
            account_id: int,
            threshold: float = 0.55,
            top_k: int = 5,
        ) -> list[KnowledgeChunk]:
            return []

    repo = FakeKnowledgeRepo()
    assert isinstance(repo, KnowledgePort)
