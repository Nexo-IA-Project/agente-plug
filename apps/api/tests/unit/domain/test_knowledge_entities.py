# tests/unit/domain/test_knowledge_entities.py
from datetime import datetime

from shared.domain.entities.admin_user import AdminRole, AdminUser
from shared.domain.entities.knowledge_chunk import KnowledgeChunk
from shared.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument

# ── KnowledgeDocument ─────────────────────────────────────────────────────────


def test_knowledge_document_defaults():
    doc = KnowledgeDocument(
        account_id=1,
        filename="lecture.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        created_by="admin@example.com",
    )
    assert doc.status == DocumentStatus.PENDING
    assert doc.chunk_count == 0
    assert doc.tags == []
    assert doc.error_message is None
    assert doc.id is not None
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)


def test_document_status_values():
    assert DocumentStatus.PENDING == "pending"
    assert DocumentStatus.PROCESSING == "processing"
    assert DocumentStatus.INDEXED == "indexed"
    assert DocumentStatus.ERROR == "error"


def test_knowledge_document_with_tags():
    doc = KnowledgeDocument(
        account_id=2,
        filename="faq.txt",
        mime_type="text/plain",
        file_size_bytes=512,
        created_by="editor@example.com",
        tags=["faq", "support"],
    )
    assert doc.tags == ["faq", "support"]


# ── KnowledgeChunk ────────────────────────────────────────────────────────────


def test_knowledge_chunk_defaults():
    chunk = KnowledgeChunk(
        document_id="doc-123",
        account_id=1,
        text="This is a chunk of text.",
        chunk_index=0,
        token_count=6,
        embedding=[0.1, 0.2, 0.3],
    )
    assert chunk.id is not None
    assert isinstance(chunk.created_at, datetime)
    assert chunk.document_id == "doc-123"
    assert chunk.embedding == [0.1, 0.2, 0.3]


# ── AdminUser ─────────────────────────────────────────────────────────────────


def test_admin_user_defaults():
    user = AdminUser(
        account_id=1,
        email="admin@example.com",
        password_hash="$2b$12$...",
        role=AdminRole.ADMIN,
    )
    assert user.id is not None
    assert isinstance(user.created_at, datetime)


def test_admin_role_values():
    assert AdminRole.ADMIN == "admin"
    assert AdminRole.EDITOR == "editor"
    assert AdminRole.VIEWER == "viewer"


def test_admin_user_editor_role():
    user = AdminUser(
        account_id=1,
        email="editor@example.com",
        password_hash="hash",
        role=AdminRole.EDITOR,
    )
    assert user.role == AdminRole.EDITOR
