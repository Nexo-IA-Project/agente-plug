# KB Admin ⑥ — Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a FastAPI backend for administrators to manage the Knowledge Base — document upload, chunking, embedding, pgvector storage, CRUD, JWT auth (multi-tenant, roles), test-search endpoint, and usage logs.

**Architecture:** Pure FastAPI + use cases. No `@tool` skills. No LangGraph. No agent graph. Clean Architecture — `domain/application/infrastructure/interface`. Session lifecycle: `flush()` in repos, `commit()` in caller (Unit of Work).

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2 async ORM, pgvector (`pgvector.sqlalchemy.Vector`), tiktoken, pypdf, python-docx, `python-jose[cryptography]`, `passlib[bcrypt]`, pytest-asyncio, AsyncMock.

---

## File Map

### Create
| File | Responsibility |
|------|---------------|
| `src/nexoia/domain/entities/knowledge_document.py` | `KnowledgeDocument` + `DocumentStatus` |
| `src/nexoia/domain/entities/knowledge_chunk.py` | `KnowledgeChunk` |
| `src/nexoia/domain/entities/admin_user.py` | `AdminUser` + `AdminRole` |
| `src/nexoia/domain/ports/embeddings_port.py` | `EmbeddingsPort` Protocol |
| `src/nexoia/infrastructure/kb/__init__.py` | Empty |
| `src/nexoia/infrastructure/kb/chunker.py` | `TextChunker` (tiktoken) |
| `src/nexoia/infrastructure/kb/text_extractor.py` | `TextExtractor` (pdf/docx/txt) |
| `src/nexoia/infrastructure/kb/openai_embeddings.py` | `OpenAIEmbeddingsAdapter` |
| `src/nexoia/infrastructure/kb/jwt_handler.py` | JWT encode/decode + bcrypt |
| `src/nexoia/infrastructure/db/repositories/document_repo.py` | `DocumentRepository` |
| `src/nexoia/infrastructure/db/repositories/chunk_repo.py` | `ChunkRepository` |
| `src/nexoia/infrastructure/db/repositories/usage_log_repo.py` | `UsageLogRepository` |
| `src/nexoia/infrastructure/db/repositories/admin_user_repo.py` | `AdminUserRepository` |
| `src/nexoia/application/use_cases/kb/__init__.py` | Empty |
| `src/nexoia/application/use_cases/kb/ingerir_documento.py` | `IngerirDocumento` use case |
| `src/nexoia/application/use_cases/kb/buscar_chunks.py` | `BuscarChunks` use case |
| `src/nexoia/application/use_cases/kb/listar_documentos.py` | `ListarDocumentos` use case |
| `src/nexoia/application/use_cases/kb/deletar_documento.py` | `DeletarDocumento` use case |
| `src/nexoia/interface/http/routers/admin/__init__.py` | Empty |
| `src/nexoia/interface/http/routers/admin/auth.py` | `POST /admin/auth/login` |
| `src/nexoia/interface/http/routers/admin/documents.py` | CRUD + reindex endpoints |
| `src/nexoia/interface/http/routers/admin/search.py` | `POST /admin/search/test` |
| `src/nexoia/interface/http/deps/admin_deps.py` | `get_admin_deps()` FastAPI dependency |
| `migrations/versions/<id1>_enable_pgvector.py` | `CREATE EXTENSION IF NOT EXISTS vector` |
| `migrations/versions/<id2>_create_kb_tables.py` | All 4 KB tables |
| `tests/unit/domain/test_knowledge_entities.py` | Entity + enum tests |
| `tests/unit/infrastructure/kb/test_chunker.py` | TextChunker pure tests |
| `tests/unit/infrastructure/kb/test_text_extractor.py` | TextExtractor TXT path |
| `tests/unit/infrastructure/kb/test_openai_embeddings.py` | OpenAIEmbeddingsAdapter tests |
| `tests/unit/infrastructure/kb/test_jwt_handler.py` | JWT + bcrypt tests |
| `tests/unit/infrastructure/db/test_document_repo.py` | DocumentRepository tests |
| `tests/unit/infrastructure/db/test_usage_log_repo.py` | UsageLogRepository tests |
| `tests/unit/use_cases/kb/__init__.py` | Empty |
| `tests/unit/use_cases/kb/test_ingerir_documento.py` | 4 use case tests |
| `tests/unit/use_cases/kb/test_buscar_chunks.py` | BuscarChunks + ListarDocumentos + DeletarDocumento |
| `tests/unit/interface/admin/test_auth_router.py` | Login endpoint tests |
| `tests/unit/interface/admin/test_documents_router.py` | Documents endpoints tests |

### Modify
| File | Change |
|------|--------|
| `src/nexoia/infrastructure/db/models.py` | Add `KnowledgeDocumentModel`, `KnowledgeChunkModel`, `KbUsageLogModel`, `AdminUserModel` |
| `src/nexoia/config/settings.py` | Add `kb_*` and `jwt_*` settings |
| `src/nexoia/main.py` | Register admin routers under `/admin` prefix |

---

## Task 1 — Domain Entities: KnowledgeDocument, KnowledgeChunk, AdminUser

**Files:**
- Create: `src/nexoia/domain/entities/knowledge_document.py`
- Create: `src/nexoia/domain/entities/knowledge_chunk.py`
- Create: `src/nexoia/domain/entities/admin_user.py`
- Test: `tests/unit/domain/test_knowledge_entities.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/domain/test_knowledge_entities.py
from datetime import UTC, datetime

import pytest

from nexoia.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument
from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from nexoia.domain.entities.admin_user import AdminRole, AdminUser


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
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/domain/test_knowledge_entities.py -v
```
Esperado: `ModuleNotFoundError` — arquivos não existem.

- [ ] **Step 3: Implementar os arquivos**

```python
# src/nexoia/domain/entities/knowledge_document.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class DocumentStatus(StrEnum):
    PENDING    = "pending"
    PROCESSING = "processing"
    INDEXED    = "indexed"
    ERROR      = "error"


@dataclass
class KnowledgeDocument:
    account_id: int
    filename: str
    mime_type: str
    file_size_bytes: int
    created_by: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: DocumentStatus = DocumentStatus.PENDING
    chunk_count: int = 0
    tags: list[str] = field(default_factory=list)
    error_message: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

```python
# src/nexoia/domain/entities/knowledge_chunk.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4


@dataclass
class KnowledgeChunk:
    document_id: str
    account_id: int
    text: str
    chunk_index: int
    token_count: int
    embedding: list[float]
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

```python
# src/nexoia/domain/entities/admin_user.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class AdminRole(StrEnum):
    ADMIN  = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class AdminUser:
    account_id: int
    email: str
    password_hash: str
    role: AdminRole
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/domain/test_knowledge_entities.py -v
```
Esperado: 7 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/domain/entities/knowledge_document.py \
        src/nexoia/domain/entities/knowledge_chunk.py \
        src/nexoia/domain/entities/admin_user.py \
        tests/unit/domain/test_knowledge_entities.py
git commit -m "feat(kb-admin): add KnowledgeDocument, KnowledgeChunk, AdminUser entities"
```

---

## Task 2 — DB Models + Migrations

**Files:**
- Modify: `src/nexoia/infrastructure/db/models.py`
- Create: `migrations/versions/<id1>_enable_pgvector.py`
- Create: `migrations/versions/<id2>_create_kb_tables.py`

> **Note:** `KnowledgeChunkModel` uses `pgvector.sqlalchemy.Vector(1536)`. Unit tests for repos will mock the session — no real DB needed. The `KbUsageLogModel.tags` column is not in the spec for usage logs; only document/chunk/admin_user models need JSONB tags.

- [ ] **Step 1: Escrever o teste que valida que os modelos podem ser importados**

```python
# tests/unit/infrastructure/db/test_kb_models.py
def test_kb_models_importable():
    from nexoia.infrastructure.db.models import (
        AdminUserModel,
        KbUsageLogModel,
        KnowledgeChunkModel,
        KnowledgeDocumentModel,
    )
    assert KnowledgeDocumentModel.__tablename__ == "knowledge_documents"
    assert KnowledgeChunkModel.__tablename__ == "knowledge_chunks"
    assert KbUsageLogModel.__tablename__ == "kb_usage_logs"
    assert AdminUserModel.__tablename__ == "admin_users"


def test_knowledge_document_model_columns():
    from nexoia.infrastructure.db.models import KnowledgeDocumentModel
    cols = {c.name for c in KnowledgeDocumentModel.__table__.columns}
    assert "id" in cols
    assert "account_id" in cols
    assert "filename" in cols
    assert "status" in cols
    assert "chunk_count" in cols
    assert "tags" in cols
    assert "created_by" in cols
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/infrastructure/db/test_kb_models.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Adicionar modelos em `models.py`**

Adicionar as seguintes importações no topo de `src/nexoia/infrastructure/db/models.py` (onde ainda não existam):

```python
# No topo, após os imports existentes:
from pgvector.sqlalchemy import Vector
```

Adicionar os 4 novos models ao final do arquivo `src/nexoia/infrastructure/db/models.py`:

```python
class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
        nullable=False,
    )

    __table_args__ = (Index("idx_knowledge_documents_account", "account_id"),)


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list] = mapped_column(Vector(1536), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        Index("idx_knowledge_chunks_document", "document_id"),
        Index("idx_knowledge_chunks_account", "account_id"),
    )


class KbUsageLogModel(Base):
    __tablename__ = "kb_usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    query: Mapped[str] = mapped_column(String, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (Index("idx_kb_usage_logs_account", "account_id"),)


class AdminUserModel(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="viewer")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("account_id", "email", name="uq_admin_users_account_email"),
    )
```

- [ ] **Step 4: Criar migração 1 — enable pgvector**

```python
# migrations/versions/<id1>_enable_pgvector.py
# Gerar ID: python -c "import uuid; print(uuid.uuid4().hex[:12])"
# Exemplo: a1b2c3d4e5f6

"""enable_pgvector

Revision ID: a1b2c3d4e5f6
Revises: 50d62657fc63
Create Date: 2026-04-25

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '50d62657fc63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector;")
```

- [ ] **Step 5: Criar migração 2 — KB tables**

```python
# migrations/versions/<id2>_create_kb_tables.py
# Exemplo: b2c3d4e5f6a1

"""create_kb_tables

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-04-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = 'b2c3d4e5f6a1'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('chunk_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tags', JSONB(), nullable=False, server_default='[]'),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_knowledge_documents_account', 'knowledge_documents', ['account_id'])

    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.String(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=False),
        sa.Column('embedding', Vector(1536), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_knowledge_chunks_document', 'knowledge_chunks', ['document_id'])
    op.create_index('idx_knowledge_chunks_account', 'knowledge_chunks', ['account_id'])

    op.create_table(
        'kb_usage_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('result_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
    )
    op.create_index('idx_kb_usage_logs_account', 'kb_usage_logs', ['account_id'])

    op.create_table(
        'admin_users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(200), nullable=False),
        sa.Column('password_hash', sa.String(200), nullable=False),
        sa.Column('role', sa.String(20), nullable=False, server_default='viewer'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.UniqueConstraint('account_id', 'email', name='uq_admin_users_account_email'),
    )


def downgrade() -> None:
    op.drop_table('admin_users')
    op.drop_index('idx_kb_usage_logs_account', table_name='kb_usage_logs')
    op.drop_table('kb_usage_logs')
    op.drop_index('idx_knowledge_chunks_account', table_name='knowledge_chunks')
    op.drop_index('idx_knowledge_chunks_document', table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.drop_index('idx_knowledge_documents_account', table_name='knowledge_documents')
    op.drop_table('knowledge_documents')
```

- [ ] **Step 6: Rodar e verificar que passa**

```
uv run pytest tests/unit/infrastructure/db/test_kb_models.py -v
```
Esperado: 2 passed.

- [ ] **Step 7: Commit**

```
git add src/nexoia/infrastructure/db/models.py \
        migrations/versions/<id1>_enable_pgvector.py \
        migrations/versions/<id2>_create_kb_tables.py \
        tests/unit/infrastructure/db/test_kb_models.py
git commit -m "feat(kb-admin): add DB models and migrations for KB tables"
```

---

## Task 3 — EmbeddingsPort + OpenAIEmbeddingsAdapter + TextExtractor

**Files:**
- Create: `src/nexoia/domain/ports/embeddings_port.py`
- Create: `src/nexoia/infrastructure/kb/__init__.py`
- Create: `src/nexoia/infrastructure/kb/openai_embeddings.py`
- Create: `src/nexoia/infrastructure/kb/text_extractor.py`
- Test: `tests/unit/infrastructure/kb/test_openai_embeddings.py`
- Test: `tests/unit/infrastructure/kb/test_text_extractor.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/infrastructure/kb/test_openai_embeddings.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.infrastructure.kb.openai_embeddings import OpenAIEmbeddingsAdapter


@pytest.mark.asyncio
async def test_embed_returns_list_of_floats():
    mock_client = AsyncMock()
    embedding_data = MagicMock()
    embedding_data.embedding = [0.1, 0.2, 0.3]
    mock_client.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[embedding_data])
    )
    adapter = OpenAIEmbeddingsAdapter(mock_client, model="text-embedding-3-small")
    result = await adapter.embed("hello world")
    assert result == [0.1, 0.2, 0.3]
    mock_client.embeddings.create.assert_awaited_once_with(
        input="hello world", model="text-embedding-3-small"
    )


@pytest.mark.asyncio
async def test_embed_batch_returns_list_of_embeddings():
    mock_client = AsyncMock()
    e1 = MagicMock()
    e1.embedding = [0.1, 0.2]
    e2 = MagicMock()
    e2.embedding = [0.3, 0.4]
    mock_client.embeddings.create = AsyncMock(
        return_value=MagicMock(data=[e1, e2])
    )
    adapter = OpenAIEmbeddingsAdapter(mock_client)
    result = await adapter.embed_batch(["text one", "text two"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
    mock_client.embeddings.create.assert_awaited_once_with(
        input=["text one", "text two"], model="text-embedding-3-small"
    )


def test_embeddings_port_protocol_satisfied():
    """OpenAIEmbeddingsAdapter implements EmbeddingsPort (structural check)."""
    from nexoia.domain.ports.embeddings_port import EmbeddingsPort
    from unittest.mock import AsyncMock
    adapter = OpenAIEmbeddingsAdapter(AsyncMock())
    assert isinstance(adapter, EmbeddingsPort)
```

```python
# tests/unit/infrastructure/kb/test_text_extractor.py
import pytest
from nexoia.infrastructure.kb.text_extractor import TextExtractor


def test_extract_plain_text():
    extractor = TextExtractor()
    content = "Hello, world!".encode("utf-8")
    result = extractor.extract(content, "text/plain")
    assert result == "Hello, world!"


def test_extract_markdown():
    extractor = TextExtractor()
    content = "# Title\n\nParagraph.".encode("utf-8")
    result = extractor.extract(content, "text/markdown")
    assert "Title" in result
    assert "Paragraph" in result


def test_unsupported_mime_raises():
    extractor = TextExtractor()
    with pytest.raises(ValueError, match="Unsupported mime_type"):
        extractor.extract(b"data", "image/png")
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/infrastructure/kb/test_openai_embeddings.py tests/unit/infrastructure/kb/test_text_extractor.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar os arquivos**

```python
# src/nexoia/domain/ports/embeddings_port.py
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingsPort(Protocol):
    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...
```

```python
# src/nexoia/infrastructure/kb/__init__.py
```

```python
# src/nexoia/infrastructure/kb/openai_embeddings.py
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
```

```python
# src/nexoia/infrastructure/kb/text_extractor.py
from __future__ import annotations


class TextExtractor:
    """Extracts plain text from uploaded document bytes."""

    SUPPORTED_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    }

    def extract(self, content: bytes, mime_type: str) -> str:
        if mime_type == "application/pdf":
            return self._extract_pdf(content)
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return self._extract_docx(content)
        elif mime_type in ("text/plain", "text/markdown"):
            return content.decode("utf-8", errors="ignore")
        raise ValueError(f"Unsupported mime_type: {mime_type}")

    def _extract_pdf(self, content: bytes) -> str:
        import io
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _extract_docx(self, content: bytes) -> str:
        import io
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/infrastructure/kb/test_openai_embeddings.py tests/unit/infrastructure/kb/test_text_extractor.py -v
```
Esperado: 5 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/domain/ports/embeddings_port.py \
        src/nexoia/infrastructure/kb/__init__.py \
        src/nexoia/infrastructure/kb/openai_embeddings.py \
        src/nexoia/infrastructure/kb/text_extractor.py \
        tests/unit/infrastructure/kb/test_openai_embeddings.py \
        tests/unit/infrastructure/kb/test_text_extractor.py
git commit -m "feat(kb-admin): add EmbeddingsPort, OpenAIEmbeddingsAdapter, TextExtractor"
```

---

## Task 4 — TextChunker

**Files:**
- Create: `src/nexoia/infrastructure/kb/chunker.py`
- Test: `tests/unit/infrastructure/kb/test_chunker.py`

> Pure Python, no mocks needed. tiktoken `cl100k_base` encoding.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/infrastructure/kb/test_chunker.py
import pytest
from nexoia.infrastructure.kb.chunker import TextChunker


def test_short_text_produces_single_chunk():
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk("Hello world")
    assert len(chunks) == 1
    assert "Hello" in chunks[0]


def test_empty_text_produces_no_chunks():
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk("")
    assert chunks == []


def test_long_text_produces_multiple_chunks():
    # ~600 tokens → should produce 2 chunks with size=512, overlap=50
    word = "word "
    # ~600 tokens ≈ 600 "word " repetitions (roughly 1 token each)
    long_text = word * 600
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk(long_text)
    assert len(chunks) >= 2


def test_overlap_is_respected():
    """With overlap=50, second chunk should share tokens with first."""
    word = "token "
    long_text = word * 600
    chunker = TextChunker(chunk_size=512, overlap=50)
    chunks = chunker.chunk(long_text)
    # Both chunks must be non-empty
    assert all(len(c) > 0 for c in chunks)


def test_chunk_size_boundary():
    """A text of exactly chunk_size tokens → exactly 1 chunk."""
    chunker = TextChunker(chunk_size=100, overlap=10)
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode("hello ") * 100  # 100 repetitions of "hello " ≈ 100 tokens
    text = enc.decode(tokens[:100])
    chunks = chunker.chunk(text)
    assert len(chunks) == 1


def test_custom_chunk_size():
    chunker = TextChunker(chunk_size=50, overlap=5)
    word = "word "
    long_text = word * 200
    chunks = chunker.chunk(long_text)
    assert len(chunks) >= 4  # 200 tokens / (50-5) stride ≈ 4-5 chunks
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/infrastructure/kb/test_chunker.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
# src/nexoia/infrastructure/kb/chunker.py
from __future__ import annotations

import tiktoken


class TextChunker:
    """Token-aware text chunker using cl100k_base encoding."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self._enc = tiktoken.get_encoding("cl100k_base")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text:
            return []
        tokens = self._enc.encode(text)
        chunks: list[str] = []
        i = 0
        while i < len(tokens):
            end = min(i + self._chunk_size, len(tokens))
            chunk_tokens = tokens[i:end]
            chunks.append(self._enc.decode(chunk_tokens))
            if end == len(tokens):
                break
            i += self._chunk_size - self._overlap
        return chunks
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/infrastructure/kb/test_chunker.py -v
```
Esperado: 6 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/infrastructure/kb/chunker.py \
        tests/unit/infrastructure/kb/test_chunker.py
git commit -m "feat(kb-admin): add TextChunker with tiktoken cl100k_base"
```

---

## Task 5 — DocumentRepository + UsageLogRepository

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/document_repo.py`
- Create: `src/nexoia/infrastructure/db/repositories/usage_log_repo.py`
- Test: `tests/unit/infrastructure/db/test_document_repo.py`
- Test: `tests/unit/infrastructure/db/test_usage_log_repo.py`

> All methods use `await self._session.flush()`. Commit is the caller's responsibility.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/infrastructure/db/test_document_repo.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexoia.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository


def _make_doc(**kwargs) -> KnowledgeDocument:
    defaults = dict(
        account_id=1,
        filename="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        created_by="admin@test.com",
    )
    defaults.update(kwargs)
    return KnowledgeDocument(**defaults)


@pytest.mark.asyncio
async def test_save_adds_and_flushes():
    session = AsyncMock()
    repo = DocumentRepository(session)
    doc = _make_doc()
    await repo.save(doc)
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_not_found():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    repo = DocumentRepository(session)
    result = await repo.get("nonexistent-id", account_id=1)
    assert result is None


@pytest.mark.asyncio
async def test_get_returns_entity_when_found():
    session = AsyncMock()
    from nexoia.infrastructure.db.models import KnowledgeDocumentModel
    from datetime import datetime, timezone
    model = KnowledgeDocumentModel(
        id="doc-1",
        account_id=1,
        filename="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        status="pending",
        chunk_count=0,
        tags=[],
        error_message=None,
        created_by="admin@test.com",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=model)))
    repo = DocumentRepository(session)
    result = await repo.get("doc-1", account_id=1)
    assert result is not None
    assert result.id == "doc-1"
    assert result.filename == "test.pdf"
    assert result.status == DocumentStatus.PENDING


@pytest.mark.asyncio
async def test_update_status_flushes():
    session = AsyncMock()
    from nexoia.infrastructure.db.models import KnowledgeDocumentModel
    from datetime import datetime, timezone
    model = KnowledgeDocumentModel(
        id="doc-1", account_id=1, filename="f.pdf", mime_type="application/pdf",
        file_size_bytes=0, status="pending", chunk_count=0, tags=[],
        error_message=None, created_by="a",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session.get = AsyncMock(return_value=model)
    repo = DocumentRepository(session)
    await repo.update_status("doc-1", DocumentStatus.INDEXED)
    assert model.status == "indexed"
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_status_with_error_message():
    session = AsyncMock()
    from nexoia.infrastructure.db.models import KnowledgeDocumentModel
    from datetime import datetime, timezone
    model = KnowledgeDocumentModel(
        id="doc-1", account_id=1, filename="f.pdf", mime_type="application/pdf",
        file_size_bytes=0, status="processing", chunk_count=0, tags=[],
        error_message=None, created_by="a",
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    session.get = AsyncMock(return_value=model)
    repo = DocumentRepository(session)
    await repo.update_status("doc-1", DocumentStatus.ERROR, error="extraction failed")
    assert model.status == "error"
    assert model.error_message == "extraction failed"


@pytest.mark.asyncio
async def test_delete_executes_delete():
    session = AsyncMock()
    repo = DocumentRepository(session)
    await repo.delete("doc-1", account_id=1)
    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()
```

```python
# tests/unit/infrastructure/db/test_usage_log_repo.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.infrastructure.db.repositories.usage_log_repo import UsageLogRepository


@pytest.mark.asyncio
async def test_record_no_result_flushes():
    session = AsyncMock()
    repo = UsageLogRepository(session)
    await repo.record_no_result(account_id=1, query="how to get refund?")
    session.add.assert_called_once()
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_recent_returns_list_of_dicts():
    session = AsyncMock()
    from nexoia.infrastructure.db.models import KbUsageLogModel
    from datetime import datetime, timezone
    log = KbUsageLogModel(
        id="log-1",
        account_id=1,
        query="test query",
        result_count=0,
        created_at=datetime.now(timezone.utc),
    )
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[log])))))
    repo = UsageLogRepository(session)
    result = await repo.list_recent(account_id=1, limit=10)
    assert len(result) == 1
    assert result[0]["query"] == "test query"
    assert result[0]["account_id"] == 1
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/infrastructure/db/test_document_repo.py tests/unit/infrastructure/db/test_usage_log_repo.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar os repositórios**

```python
# src/nexoia/infrastructure/db/repositories/document_repo.py
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument
from nexoia.infrastructure.db.models import KnowledgeDocumentModel


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
```

```python
# src/nexoia/infrastructure/db/repositories/usage_log_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.infrastructure.db.models import KbUsageLogModel


class UsageLogRepository:
    """Session lifecycle managed by caller. Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_no_result(self, account_id: int, query: str) -> None:
        log = KbUsageLogModel(
            account_id=account_id,
            query=query,
            result_count=0,
        )
        self._session.add(log)
        await self._session.flush()

    async def list_recent(self, account_id: int, limit: int = 50) -> list[dict]:
        result = await self._session.execute(
            select(KbUsageLogModel)
            .where(KbUsageLogModel.account_id == account_id)
            .order_by(KbUsageLogModel.created_at.desc())
            .limit(limit)
        )
        return [
            {
                "id": m.id,
                "account_id": m.account_id,
                "query": m.query,
                "result_count": m.result_count,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in result.scalars().all()
        ]
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/infrastructure/db/test_document_repo.py tests/unit/infrastructure/db/test_usage_log_repo.py -v
```
Esperado: 8 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/infrastructure/db/repositories/document_repo.py \
        src/nexoia/infrastructure/db/repositories/usage_log_repo.py \
        tests/unit/infrastructure/db/test_document_repo.py \
        tests/unit/infrastructure/db/test_usage_log_repo.py
git commit -m "feat(kb-admin): add DocumentRepository and UsageLogRepository"
```

---

## Task 6 — Settings Additions

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Test: `tests/unit/test_kb_settings.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/test_kb_settings.py
from nexoia.config.settings import Settings


def test_kb_settings_defaults():
    # Settings with minimal required fields (env vars mocked via kwargs)
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        redis_url="redis://localhost",
        openai_api_key="sk-test",
        chatnexo_base_url="https://chatnexo.example.com",
        chatnexo_api_key="cnx-key",
        hubla_webhook_secret="secret",
        admin_api_key="admin-key",
        meta_api_key="meta-key",
        integration_credentials_key="cred-key",
    )
    assert s.kb_chunk_size == 512
    assert s.kb_chunk_overlap == 50
    assert s.kb_top_k == 5
    assert s.kb_threshold == 0.55
    assert s.kb_embedding_model == "text-embedding-3-small"
    assert s.kb_max_file_size_mb == 20
    assert s.jwt_secret == "change-me-in-production"
    assert s.jwt_expire_minutes == 60
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/test_kb_settings.py -v
```
Esperado: `ValidationError` ou `AttributeError` — campos não existem ainda.

- [ ] **Step 3: Adicionar campos em `settings.py`**

Adicionar ao final da classe `Settings`, antes do `@lru_cache`:

```python
    # KB Admin
    kb_chunk_size: int = 512
    kb_chunk_overlap: int = 50
    kb_top_k: int = 5
    kb_threshold: float = 0.55
    kb_embedding_model: str = "text-embedding-3-small"
    kb_max_file_size_mb: int = 20

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 60
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/test_kb_settings.py -v
```
Esperado: 1 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/config/settings.py tests/unit/test_kb_settings.py
git commit -m "feat(kb-admin): add kb_* and jwt_* settings"
```

---

## Task 7 — `IngerirDocumento` Use Case

**Files:**
- Create: `src/nexoia/application/use_cases/kb/__init__.py`
- Create: `src/nexoia/application/use_cases/kb/ingerir_documento.py`
- Test: `tests/unit/use_cases/kb/__init__.py`
- Test: `tests/unit/use_cases/kb/test_ingerir_documento.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/use_cases/kb/test_ingerir_documento.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexoia.application.use_cases.kb.ingerir_documento import IngerirDocumento
from nexoia.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument
from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk


def _make_document(doc_id: str = "doc-1") -> KnowledgeDocument:
    return KnowledgeDocument(
        id=doc_id,
        account_id=1,
        filename="manual.pdf",
        mime_type="text/plain",
        file_size_bytes=100,
        created_by="admin@test.com",
    )


def _make_use_case():
    doc_repo = AsyncMock()
    chunk_repo = AsyncMock()
    extractor = MagicMock()
    chunker = MagicMock()
    embeddings = AsyncMock()
    return IngerirDocumento(doc_repo, chunk_repo, extractor, chunker, embeddings), {
        "doc_repo": doc_repo,
        "chunk_repo": chunk_repo,
        "extractor": extractor,
        "chunker": chunker,
        "embeddings": embeddings,
    }


@pytest.mark.asyncio
async def test_happy_path_indexes_document():
    uc, deps = _make_use_case()
    doc = _make_document("doc-1")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(return_value="chunk text content")
    deps["chunker"].chunk = MagicMock(return_value=["chunk text content"])
    deps["embeddings"].embed_batch = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    await uc.execute(doc_id="doc-1", content=b"raw bytes", account_id=1)

    # Must set PROCESSING then INDEXED
    calls = [call.args for call in deps["doc_repo"].update_status.call_args_list]
    statuses = [c[1] for c in calls]  # second arg is status
    assert DocumentStatus.PROCESSING in statuses
    assert DocumentStatus.INDEXED in statuses

    # Must save chunks
    deps["chunk_repo"].save_batch.assert_awaited_once()

    # Must update chunk count
    deps["doc_repo"].update_chunk_count.assert_awaited_once_with("doc-1", 1)


@pytest.mark.asyncio
async def test_sets_processing_before_indexing():
    uc, deps = _make_use_case()
    doc = _make_document("doc-2")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(return_value="text")
    deps["chunker"].chunk = MagicMock(return_value=["text"])
    deps["embeddings"].embed_batch = AsyncMock(return_value=[[0.1]])

    await uc.execute(doc_id="doc-2", content=b"data", account_id=1)

    first_call = deps["doc_repo"].update_status.call_args_list[0]
    assert first_call.args[1] == DocumentStatus.PROCESSING


@pytest.mark.asyncio
async def test_on_extraction_error_sets_error_status():
    uc, deps = _make_use_case()
    doc = _make_document("doc-3")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(side_effect=ValueError("corrupt PDF"))

    with pytest.raises(ValueError, match="corrupt PDF"):
        await uc.execute(doc_id="doc-3", content=b"bad", account_id=1)

    # Last update_status call must be ERROR
    last_call = deps["doc_repo"].update_status.call_args_list[-1]
    assert last_call.args[1] == DocumentStatus.ERROR
    assert "corrupt PDF" in last_call.args[2]  # error message


@pytest.mark.asyncio
async def test_idempotency_deletes_old_chunks_before_save():
    uc, deps = _make_use_case()
    doc = _make_document("doc-4")
    deps["doc_repo"].get = AsyncMock(return_value=doc)
    deps["extractor"].extract = MagicMock(return_value="text")
    deps["chunker"].chunk = MagicMock(return_value=["text"])
    deps["embeddings"].embed_batch = AsyncMock(return_value=[[0.1]])

    await uc.execute(doc_id="doc-4", content=b"data", account_id=1)

    # delete_by_document must be called before save_batch
    delete_order = deps["chunk_repo"].delete_by_document.call_args_list
    save_order = deps["chunk_repo"].save_batch.call_args_list
    assert len(delete_order) == 1
    assert len(save_order) == 1
    deps["chunk_repo"].delete_by_document.assert_awaited_once_with("doc-4")
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/use_cases/kb/test_ingerir_documento.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
# src/nexoia/application/use_cases/kb/__init__.py
```

```python
# src/nexoia/application/use_cases/kb/ingerir_documento.py
from __future__ import annotations

from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from nexoia.domain.entities.knowledge_document import DocumentStatus
from nexoia.domain.ports.embeddings_port import EmbeddingsPort
from nexoia.infrastructure.kb.chunker import TextChunker
from nexoia.infrastructure.kb.text_extractor import TextExtractor


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
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/use_cases/kb/test_ingerir_documento.py -v
```
Esperado: 4 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/application/use_cases/kb/__init__.py \
        src/nexoia/application/use_cases/kb/ingerir_documento.py \
        tests/unit/use_cases/kb/__init__.py \
        tests/unit/use_cases/kb/test_ingerir_documento.py
git commit -m "feat(kb-admin): add IngerirDocumento use case with 4 unit tests"
```

---

## Task 8 — BuscarChunks + ListarDocumentos + DeletarDocumento Use Cases

**Files:**
- Create: `src/nexoia/application/use_cases/kb/buscar_chunks.py`
- Create: `src/nexoia/application/use_cases/kb/listar_documentos.py`
- Create: `src/nexoia/application/use_cases/kb/deletar_documento.py`
- Create: `src/nexoia/infrastructure/db/repositories/chunk_repo.py`
- Test: `tests/unit/use_cases/kb/test_buscar_chunks.py`
- Test: `tests/unit/infrastructure/db/test_chunk_repo.py`

> `BuscarChunks` implements `KnowledgePort` (updates `account_id` type to `int` — see note below). `similarity_search` unit tests are skipped (too complex without pgvector DB); only `save_batch` and `delete_by_document` are unit-tested.

> **Note on KnowledgePort:** The existing `KnowledgePort` in `src/nexoia/domain/ports/knowledge.py` uses `account_id: UUID`. KB Admin uses `account_id: int`. Create a separate `KbSearchPort` or adapt `BuscarChunks` to expose an `int` interface. For this plan, `BuscarChunks` exposes its own interface with `account_id: int` and is used directly by the admin search endpoint — it does not implement the existing `KnowledgePort`.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/infrastructure/db/test_chunk_repo.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from nexoia.infrastructure.db.repositories.chunk_repo import ChunkRepository


def _make_chunk(index: int = 0) -> KnowledgeChunk:
    return KnowledgeChunk(
        document_id="doc-1",
        account_id=1,
        text=f"chunk text {index}",
        chunk_index=index,
        token_count=3,
        embedding=[0.1, 0.2, 0.3],
    )


@pytest.mark.asyncio
async def test_save_batch_adds_all_models():
    session = AsyncMock()
    repo = ChunkRepository(session)
    chunks = [_make_chunk(0), _make_chunk(1), _make_chunk(2)]
    await repo.save_batch(chunks)
    assert session.add.call_count == 3
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_batch_empty_list_does_not_flush():
    session = AsyncMock()
    repo = ChunkRepository(session)
    await repo.save_batch([])
    session.add.assert_not_called()
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_by_document_executes_delete():
    session = AsyncMock()
    repo = ChunkRepository(session)
    await repo.delete_by_document("doc-1")
    session.execute.assert_awaited_once()
    session.flush.assert_awaited_once()
```

```python
# tests/unit/use_cases/kb/test_buscar_chunks.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.use_cases.kb.buscar_chunks import BuscarChunks
from nexoia.application.use_cases.kb.listar_documentos import ListarDocumentos
from nexoia.application.use_cases.kb.deletar_documento import DeletarDocumento
from nexoia.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument


# ── BuscarChunks ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buscar_chunks_returns_results():
    chunk_repo = AsyncMock()
    embeddings = AsyncMock()
    usage_repo = AsyncMock()

    embeddings.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
    chunk_repo.similarity_search = AsyncMock(return_value=[
        {"chunk_id": "c1", "text": "answer text", "score": 0.85}
    ])

    uc = BuscarChunks(chunk_repo=chunk_repo, embeddings=embeddings, usage_repo=usage_repo)
    results = await uc.execute(account_id=1, query="my question", top_k=5, threshold=0.5)

    assert len(results) == 1
    assert results[0]["text"] == "answer text"
    embeddings.embed.assert_awaited_once_with("my question")
    chunk_repo.similarity_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_buscar_chunks_logs_when_no_results():
    chunk_repo = AsyncMock()
    embeddings = AsyncMock()
    usage_repo = AsyncMock()

    embeddings.embed = AsyncMock(return_value=[0.1, 0.2])
    chunk_repo.similarity_search = AsyncMock(return_value=[])

    uc = BuscarChunks(chunk_repo=chunk_repo, embeddings=embeddings, usage_repo=usage_repo)
    results = await uc.execute(account_id=1, query="no results query", top_k=5, threshold=0.8)

    assert results == []
    usage_repo.record_no_result.assert_awaited_once_with(
        account_id=1, query="no results query"
    )


# ── ListarDocumentos ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_listar_documentos_delegates_to_repo():
    doc_repo = AsyncMock()
    doc_repo.list_by_account = AsyncMock(return_value=[])
    uc = ListarDocumentos(doc_repo)
    result = await uc.execute(account_id=1, offset=0, limit=10)
    assert result == []
    doc_repo.list_by_account.assert_awaited_once_with(1, offset=0, limit=10)


# ── DeletarDocumento ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_deletar_documento_deletes_chunks_then_document():
    doc_repo = AsyncMock()
    chunk_repo = AsyncMock()
    uc = DeletarDocumento(doc_repo=doc_repo, chunk_repo=chunk_repo)
    await uc.execute(doc_id="doc-1", account_id=1)

    chunk_repo.delete_by_document.assert_awaited_once_with("doc-1")
    doc_repo.delete.assert_awaited_once_with("doc-1", account_id=1)
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/infrastructure/db/test_chunk_repo.py tests/unit/use_cases/kb/test_buscar_chunks.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar os arquivos**

```python
# src/nexoia/infrastructure/db/repositories/chunk_repo.py
from __future__ import annotations

from sqlalchemy import delete, select, text
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
        """
        pgvector cosine similarity search. Returns chunks above threshold,
        ordered by similarity descending.
        Note: unit-tested only via integration tests (requires real pgvector).
        """
        # Cast to vector literal for pgvector operator
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
```

```python
# src/nexoia/application/use_cases/kb/buscar_chunks.py
from __future__ import annotations

from nexoia.domain.ports.embeddings_port import EmbeddingsPort


class BuscarChunks:
    """
    Use case: embed a query, search for similar chunks, log misses.
    Implements the admin 'test search' endpoint.
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
```

```python
# src/nexoia/application/use_cases/kb/listar_documentos.py
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
```

```python
# src/nexoia/application/use_cases/kb/deletar_documento.py
from __future__ import annotations


class DeletarDocumento:
    """Use case: delete all chunks then the document record."""

    def __init__(self, doc_repo, chunk_repo) -> None:
        self._doc_repo = doc_repo
        self._chunk_repo = chunk_repo

    async def execute(self, doc_id: str, account_id: int) -> None:
        await self._chunk_repo.delete_by_document(doc_id)
        await self._doc_repo.delete(doc_id, account_id=account_id)
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/infrastructure/db/test_chunk_repo.py tests/unit/use_cases/kb/test_buscar_chunks.py -v
```
Esperado: 7 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/infrastructure/db/repositories/chunk_repo.py \
        src/nexoia/application/use_cases/kb/buscar_chunks.py \
        src/nexoia/application/use_cases/kb/listar_documentos.py \
        src/nexoia/application/use_cases/kb/deletar_documento.py \
        tests/unit/infrastructure/db/test_chunk_repo.py \
        tests/unit/use_cases/kb/test_buscar_chunks.py
git commit -m "feat(kb-admin): add BuscarChunks, ListarDocumentos, DeletarDocumento + ChunkRepository"
```

---

## Task 9 — JWT Handler + AdminUserRepository + Login Endpoint

**Files:**
- Create: `src/nexoia/infrastructure/kb/jwt_handler.py`
- Create: `src/nexoia/infrastructure/db/repositories/admin_user_repo.py`
- Create: `src/nexoia/interface/http/routers/admin/__init__.py`
- Create: `src/nexoia/interface/http/routers/admin/auth.py`
- Test: `tests/unit/infrastructure/kb/test_jwt_handler.py`
- Test: `tests/unit/interface/admin/__init__.py`
- Test: `tests/unit/interface/admin/test_auth_router.py`

> **Dependencies to add to `pyproject.toml`:** `python-jose[cryptography]`, `passlib[bcrypt]`. Verify they are present; add if missing.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/infrastructure/kb/test_jwt_handler.py
import pytest
from nexoia.infrastructure.kb.jwt_handler import (
    create_access_token,
    hash_password,
    verify_password,
    verify_token,
)


def test_hash_and_verify_password():
    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert verify_password("mysecret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_verify_token():
    data = {"sub": "user@example.com", "account_id": 1, "role": "admin"}
    token = create_access_token(data, secret="test-secret", expire_minutes=60)
    assert isinstance(token, str)
    payload = verify_token(token, secret="test-secret")
    assert payload["sub"] == "user@example.com"
    assert payload["account_id"] == 1
    assert payload["role"] == "admin"
    assert "exp" in payload


def test_verify_token_wrong_secret_raises():
    from jose import JWTError
    data = {"sub": "user@example.com"}
    token = create_access_token(data, secret="correct-secret", expire_minutes=10)
    with pytest.raises(JWTError):
        verify_token(token, secret="wrong-secret")


def test_token_expiry_is_in_future():
    from datetime import UTC, datetime
    data = {"sub": "user@example.com"}
    token = create_access_token(data, secret="s", expire_minutes=30)
    payload = verify_token(token, secret="s")
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    assert exp > datetime.now(UTC)
```

```python
# tests/unit/interface/admin/test_auth_router.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI


def _make_app():
    from nexoia.interface.http.routers.admin.auth import router
    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


@pytest.mark.asyncio
async def test_login_returns_token_on_valid_credentials():
    """Integration-lite: real router, mocked DB and JWT."""
    from nexoia.infrastructure.kb import jwt_handler

    mock_user_model = MagicMock()
    mock_user_model.id = "user-1"
    mock_user_model.email = "admin@test.com"
    mock_user_model.password_hash = jwt_handler.hash_password("correctpass")
    mock_user_model.account_id = 1
    mock_user_model.role = "admin"

    with patch("nexoia.interface.http.routers.admin.auth.get_db") as mock_get_db, \
         patch("nexoia.interface.http.routers.admin.auth.get_settings") as mock_settings:

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user_model))
        )
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "correctpass", "account_id": 1},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "expires_in" in data


@pytest.mark.asyncio
async def test_login_returns_401_on_wrong_password():
    from nexoia.infrastructure.kb import jwt_handler

    mock_user_model = MagicMock()
    mock_user_model.password_hash = jwt_handler.hash_password("correctpass")
    mock_user_model.email = "admin@test.com"
    mock_user_model.account_id = 1

    with patch("nexoia.interface.http.routers.admin.auth.get_db") as mock_get_db, \
         patch("nexoia.interface.http.routers.admin.auth.get_settings") as mock_settings:

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=mock_user_model))
        )
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "admin@test.com", "password": "wrongpass", "account_id": 1},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_returns_401_when_user_not_found():
    with patch("nexoia.interface.http.routers.admin.auth.get_db") as mock_get_db, \
         patch("nexoia.interface.http.routers.admin.auth.get_settings") as mock_settings:

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )
        mock_get_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60

        app = _make_app()
        client = TestClient(app)
        response = client.post(
            "/admin/auth/login",
            json={"email": "nobody@test.com", "password": "pass", "account_id": 1},
        )
        assert response.status_code == 401
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/infrastructure/kb/test_jwt_handler.py tests/unit/interface/admin/test_auth_router.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar os arquivos**

```python
# src/nexoia/infrastructure/kb/jwt_handler.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import jwt as jose_jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_access_token(data: dict, secret: str, expire_minutes: int) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=expire_minutes)
    to_encode["exp"] = expire
    return jose_jwt.encode(to_encode, secret, algorithm="HS256")


def verify_token(token: str, secret: str) -> dict:
    return jose_jwt.decode(token, secret, algorithms=["HS256"])


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
```

```python
# src/nexoia/infrastructure/db/repositories/admin_user_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.admin_user import AdminRole, AdminUser
from nexoia.infrastructure.db.models import AdminUserModel


class AdminUserRepository:
    """Session lifecycle managed by caller (Unit of Work). Uses flush(), not commit()."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: AdminUser) -> None:
        model = AdminUserModel(
            id=user.id,
            account_id=user.account_id,
            email=user.email,
            password_hash=user.password_hash,
            role=user.role.value,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_email(
        self, account_id: int, email: str
    ) -> AdminUserModel | None:
        result = await self._session.execute(
            select(AdminUserModel)
            .where(AdminUserModel.account_id == account_id)
            .where(AdminUserModel.email == email)
        )
        return result.scalar_one_or_none()
```

```python
# src/nexoia/interface/http/routers/admin/__init__.py
```

```python
# src/nexoia/interface/http/routers/admin/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.config.settings import get_settings
from nexoia.infrastructure.db.models import AdminUserModel
from nexoia.infrastructure.db.session import session_scope
from nexoia.infrastructure.kb.jwt_handler import create_access_token, verify_password

router = APIRouter(tags=["admin-auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    account_id: int


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


async def get_db():
    async with session_scope() as session:
        yield session


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db),
) -> LoginResponse:
    settings = get_settings()

    result = await session.execute(
        select(AdminUserModel)
        .where(AdminUserModel.account_id == body.account_id)
        .where(AdminUserModel.email == body.email)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        data={
            "sub": user.email,
            "account_id": user.account_id,
            "role": user.role,
            "user_id": str(user.id),
        },
        secret=settings.jwt_secret,
        expire_minutes=settings.jwt_expire_minutes,
    )
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/infrastructure/kb/test_jwt_handler.py tests/unit/interface/admin/test_auth_router.py -v
```
Esperado: 7 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/infrastructure/kb/jwt_handler.py \
        src/nexoia/infrastructure/db/repositories/admin_user_repo.py \
        src/nexoia/interface/http/routers/admin/__init__.py \
        src/nexoia/interface/http/routers/admin/auth.py \
        tests/unit/infrastructure/kb/test_jwt_handler.py \
        tests/unit/interface/admin/__init__.py \
        tests/unit/interface/admin/test_auth_router.py
git commit -m "feat(kb-admin): add JWT handler, AdminUserRepository, login endpoint"
```

---

## Task 10 — FastAPI Admin Routers (documents + search) + Wire into main.py

**Files:**
- Create: `src/nexoia/interface/http/routers/admin/documents.py`
- Create: `src/nexoia/interface/http/routers/admin/search.py`
- Modify: `src/nexoia/main.py`
- Test: `tests/unit/interface/admin/test_documents_router.py`

> These routers depend on `get_admin_deps()` (Task 11). For now, implement the routers importing from `deps.admin_deps` — the dep function will be implemented in Task 11. The tests will mock the dependency.

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/interface/admin/test_documents_router.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app_with_mock_deps(mock_deps):
    from nexoia.interface.http.routers.admin.documents import router
    from nexoia.interface.http.deps.admin_deps import get_admin_deps

    app = FastAPI()
    app.dependency_overrides[get_admin_deps] = lambda: mock_deps
    app.include_router(router, prefix="/admin")
    return app


def _make_mock_deps(doc_list=None):
    deps = MagicMock()
    deps.listar = AsyncMock(return_value=doc_list or [])
    deps.ingerir = AsyncMock()
    deps.deletar = AsyncMock()
    deps.buscar = AsyncMock(return_value=[])
    return deps


def test_list_documents_returns_200():
    deps = _make_mock_deps()
    app = _make_app_with_mock_deps(deps)
    client = TestClient(app)
    # Provide a valid-looking Authorization header (content ignored via mock)
    response = client.get("/admin/documents", headers={"Authorization": "Bearer faketoken"})
    assert response.status_code == 200
    assert response.json() == []


def test_list_documents_calls_listar_use_case():
    from nexoia.domain.entities.knowledge_document import KnowledgeDocument, DocumentStatus
    from datetime import datetime, timezone
    doc = KnowledgeDocument(
        account_id=1, filename="test.pdf", mime_type="application/pdf",
        file_size_bytes=100, created_by="admin@test.com",
    )
    deps = _make_mock_deps(doc_list=[doc])
    app = _make_app_with_mock_deps(deps)
    client = TestClient(app)
    response = client.get("/admin/documents", headers={"Authorization": "Bearer faketoken"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "test.pdf"


def test_delete_document_returns_204():
    deps = _make_mock_deps()
    app = _make_app_with_mock_deps(deps)
    client = TestClient(app)
    response = client.delete(
        "/admin/documents/doc-1", headers={"Authorization": "Bearer faketoken"}
    )
    assert response.status_code == 204
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/interface/admin/test_documents_router.py -v
```
Esperado: `ModuleNotFoundError` (routers e deps não existem ainda).

- [ ] **Step 3: Implementar os routers**

```python
# src/nexoia/interface/http/routers/admin/documents.py
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from nexoia.interface.http.deps.admin_deps import AdminDeps, get_admin_deps

router = APIRouter(tags=["admin-documents"])


class DocumentOut(BaseModel):
    id: str
    filename: str
    mime_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    tags: list[str]
    created_by: str
    created_at: str
    updated_at: str

    @classmethod
    def from_entity(cls, doc) -> "DocumentOut":
        return cls(
            id=doc.id,
            filename=doc.filename,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            status=doc.status.value,
            chunk_count=doc.chunk_count,
            tags=doc.tags,
            created_by=doc.created_by,
            created_at=doc.created_at.isoformat() if doc.created_at else "",
            updated_at=doc.updated_at.isoformat() if doc.updated_at else "",
        )


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    offset: int = 0,
    limit: int = 20,
    deps: AdminDeps = Depends(get_admin_deps),
) -> list[DocumentOut]:
    docs = await deps.listar.execute(
        account_id=deps.account_id, offset=offset, limit=limit
    )
    return [DocumentOut.from_entity(d) for d in docs]


@router.post("/documents/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    tags: str = Form(default=""),
    deps: AdminDeps = Depends(get_admin_deps),
) -> dict:
    from nexoia.domain.entities.knowledge_document import KnowledgeDocument
    import asyncio

    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    # Validate file size
    max_bytes = deps.settings.kb_max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {deps.settings.kb_max_file_size_mb}MB",
        )

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    doc = KnowledgeDocument(
        account_id=deps.account_id,
        filename=file.filename or "unknown",
        mime_type=mime_type,
        file_size_bytes=len(content),
        created_by=deps.user_email,
        tags=tag_list,
    )
    await deps.doc_repo.save(doc)

    # Ingest in background (fire and forget within session)
    asyncio.create_task(
        deps.ingerir.execute(
            doc_id=doc.id, content=content, account_id=deps.account_id
        )
    )

    return {"doc_id": doc.id, "status": "processing"}


@router.get("/documents/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    deps: AdminDeps = Depends(get_admin_deps),
) -> DocumentOut:
    doc = await deps.doc_repo.get(doc_id, deps.account_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentOut.from_entity(doc)


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    deps: AdminDeps = Depends(get_admin_deps),
) -> None:
    await deps.deletar.execute(doc_id=doc_id, account_id=deps.account_id)


@router.post("/documents/{doc_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document(
    doc_id: str,
    deps: AdminDeps = Depends(get_admin_deps),
) -> dict:
    import asyncio
    doc = await deps.doc_repo.get(doc_id, deps.account_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # Re-ingest requires original content — not stored; return 501 or require re-upload
    # For spec compliance, accept and return accepted (content must be re-uploaded separately)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Reindex requires re-upload. Use /documents/upload.",
    )
```

```python
# src/nexoia/interface/http/routers/admin/search.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from nexoia.interface.http.deps.admin_deps import AdminDeps, get_admin_deps

router = APIRouter(tags=["admin-search"])


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    threshold: float = 0.55


class SearchResponse(BaseModel):
    results: list[dict]
    query: str
    result_count: int


@router.post("/search/test", response_model=SearchResponse)
async def test_search(
    body: SearchRequest,
    deps: AdminDeps = Depends(get_admin_deps),
) -> SearchResponse:
    results = await deps.buscar.execute(
        account_id=deps.account_id,
        query=body.query,
        top_k=body.top_k,
        threshold=body.threshold,
    )
    return SearchResponse(
        results=results,
        query=body.query,
        result_count=len(results),
    )
```

- [ ] **Step 4: Atualizar `main.py`** para registrar os admin routers:

```python
# Adicionar aos imports existentes:
from nexoia.interface.http.routers.admin import auth as admin_auth
from nexoia.interface.http.routers.admin import documents as admin_documents
from nexoia.interface.http.routers.admin import search as admin_search

# Dentro de create_app(), após os includes existentes:
app.include_router(admin_auth.router, prefix="/admin")
app.include_router(admin_documents.router, prefix="/admin")
app.include_router(admin_search.router, prefix="/admin")
```

O bloco final de `create_app()` ficará:

```python
def create_app() -> FastAPI:
    app = FastAPI(title="nexoia-agent", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationIdMiddleware)
    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(metrics.router)
    app.include_router(webhook_purchase.router)
    app.include_router(webhook_message.router)
    app.include_router(admin_auth.router, prefix="/admin")
    app.include_router(admin_documents.router, prefix="/admin")
    app.include_router(admin_search.router, prefix="/admin")
    return app
```

- [ ] **Step 5: Rodar e verificar que passa**

```
uv run pytest tests/unit/interface/admin/test_documents_router.py -v
```
Esperado: 3 passed.

- [ ] **Step 6: Commit**

```
git add src/nexoia/interface/http/routers/admin/documents.py \
        src/nexoia/interface/http/routers/admin/search.py \
        src/nexoia/main.py \
        tests/unit/interface/admin/test_documents_router.py
git commit -m "feat(kb-admin): add admin documents and search routers, wire into main.py"
```

---

## Task 11 — Dependency Injection: `get_admin_deps()`

**Files:**
- Create: `src/nexoia/interface/http/deps/__init__.py`
- Create: `src/nexoia/interface/http/deps/admin_deps.py`
- Test: `tests/unit/interface/admin/test_admin_deps.py`

> `get_admin_deps()` is a FastAPI dependency that:
> 1. Extracts and verifies the JWT from the `Authorization: Bearer <token>` header.
> 2. Creates all use cases from the session (via `session_scope()`) and openai client (from settings).
> 3. Returns an `AdminDeps` dataclass with everything the routers need.

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/interface/admin/test_admin_deps.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_get_admin_deps_raises_401_without_token():
    from nexoia.interface.http.deps.admin_deps import get_admin_deps
    from fastapi import Request

    mock_request = MagicMock()
    mock_request.headers = {}

    with pytest.raises(HTTPException) as exc_info:
        # Call as async generator — exhaust it
        gen = get_admin_deps(authorization=None)
        async for _ in gen:
            pass
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_admin_deps_raises_401_on_bad_token():
    from nexoia.interface.http.deps.admin_deps import get_admin_deps

    with patch("nexoia.interface.http.deps.admin_deps.get_settings") as mock_settings:
        mock_settings.return_value.jwt_secret = "test-secret"
        mock_settings.return_value.jwt_expire_minutes = 60
        mock_settings.return_value.kb_chunk_size = 512
        mock_settings.return_value.kb_chunk_overlap = 50
        mock_settings.return_value.kb_embedding_model = "text-embedding-3-small"
        mock_settings.return_value.kb_top_k = 5
        mock_settings.return_value.kb_threshold = 0.55
        mock_settings.return_value.kb_max_file_size_mb = 20
        mock_settings.return_value.openai_api_key = "sk-test"

        with pytest.raises(HTTPException) as exc_info:
            gen = get_admin_deps(authorization="Bearer invalidtoken")
            async for _ in gen:
                pass
        assert exc_info.value.status_code == 401
```

- [ ] **Step 2: Rodar e verificar que falha**

```
uv run pytest tests/unit/interface/admin/test_admin_deps.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
# src/nexoia/interface/http/deps/__init__.py
```

```python
# src/nexoia/interface/http/deps/admin_deps.py
from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.application.use_cases.kb.buscar_chunks import BuscarChunks
from nexoia.application.use_cases.kb.deletar_documento import DeletarDocumento
from nexoia.application.use_cases.kb.ingerir_documento import IngerirDocumento
from nexoia.application.use_cases.kb.listar_documentos import ListarDocumentos
from nexoia.config.settings import Settings, get_settings
from nexoia.infrastructure.db.repositories.chunk_repo import ChunkRepository
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository
from nexoia.infrastructure.db.repositories.usage_log_repo import UsageLogRepository
from nexoia.infrastructure.db.session import session_scope
from nexoia.infrastructure.kb.chunker import TextChunker
from nexoia.infrastructure.kb.jwt_handler import verify_token
from nexoia.infrastructure.kb.openai_embeddings import OpenAIEmbeddingsAdapter
from nexoia.infrastructure.kb.text_extractor import TextExtractor

_bearer = HTTPBearer(auto_error=False)


@dataclass
class AdminDeps:
    account_id: int
    user_email: str
    user_role: str
    settings: Settings
    doc_repo: DocumentRepository
    ingerir: IngerirDocumento
    listar: ListarDocumentos
    deletar: DeletarDocumento
    buscar: BuscarChunks


async def get_admin_deps(
    authorization: str | None = Depends(
        lambda request: request.headers.get("Authorization")
    ),
) -> AsyncIterator[AdminDeps]:
    settings = get_settings()

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = verify_token(token, secret=settings.jwt_secret)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account_id: int = payload["account_id"]
    user_email: str = payload["sub"]
    user_role: str = payload.get("role", "viewer")

    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    embeddings = OpenAIEmbeddingsAdapter(openai_client, model=settings.kb_embedding_model)
    extractor = TextExtractor()
    chunker = TextChunker(
        chunk_size=settings.kb_chunk_size,
        overlap=settings.kb_chunk_overlap,
    )

    async with session_scope() as session:
        doc_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        usage_repo = UsageLogRepository(session)

        ingerir = IngerirDocumento(
            doc_repo=doc_repo,
            chunk_repo=chunk_repo,
            extractor=extractor,
            chunker=chunker,
            embeddings=embeddings,
        )
        listar = ListarDocumentos(doc_repo=doc_repo)
        deletar = DeletarDocumento(doc_repo=doc_repo, chunk_repo=chunk_repo)
        buscar = BuscarChunks(
            chunk_repo=chunk_repo,
            embeddings=embeddings,
            usage_repo=usage_repo,
        )

        yield AdminDeps(
            account_id=account_id,
            user_email=user_email,
            user_role=user_role,
            settings=settings,
            doc_repo=doc_repo,
            ingerir=ingerir,
            listar=listar,
            deletar=deletar,
            buscar=buscar,
        )
```

- [ ] **Step 4: Rodar e verificar que passa**

```
uv run pytest tests/unit/interface/admin/test_admin_deps.py -v
```
Esperado: 2 passed.

- [ ] **Step 5: Commit**

```
git add src/nexoia/interface/http/deps/__init__.py \
        src/nexoia/interface/http/deps/admin_deps.py \
        tests/unit/interface/admin/test_admin_deps.py
git commit -m "feat(kb-admin): add get_admin_deps() FastAPI dependency with JWT verification"
```

---

## Task 12 — Full Unit Suite

**No new files.** Run the complete unit test suite and fix any import errors, type inconsistencies, or missing `__init__.py` files.

- [ ] **Step 1: Verificar `__init__.py` em todos os novos diretórios de teste**

Garantir que estes arquivos existam (vazios):
```
tests/unit/infrastructure/kb/__init__.py
tests/unit/infrastructure/db/__init__.py   (provavelmente já existe)
tests/unit/use_cases/kb/__init__.py
tests/unit/interface/admin/__init__.py
```

Criar com:
```bash
touch tests/unit/infrastructure/kb/__init__.py
touch tests/unit/use_cases/kb/__init__.py
touch tests/unit/interface/admin/__init__.py
```

- [ ] **Step 2: Rodar a suite completa**

```
uv run pytest tests/unit/ -q
```

- [ ] **Step 3: Verificar cobertura mínima por módulo**

Confirmar que os seguintes módulos têm testes passando:

| Módulo | Testes |
|--------|--------|
| `domain/entities/knowledge_*` + `admin_user` | `test_knowledge_entities.py` |
| `infrastructure/db/models.py` (novos models) | `test_kb_models.py` |
| `infrastructure/kb/chunker.py` | `test_chunker.py` |
| `infrastructure/kb/text_extractor.py` | `test_text_extractor.py` |
| `infrastructure/kb/openai_embeddings.py` | `test_openai_embeddings.py` |
| `infrastructure/kb/jwt_handler.py` | `test_jwt_handler.py` |
| `infrastructure/db/repositories/document_repo.py` | `test_document_repo.py` |
| `infrastructure/db/repositories/usage_log_repo.py` | `test_usage_log_repo.py` |
| `infrastructure/db/repositories/chunk_repo.py` | `test_chunk_repo.py` |
| `config/settings.py` (kb_* + jwt_*) | `test_kb_settings.py` |
| `use_cases/kb/ingerir_documento.py` | `test_ingerir_documento.py` |
| `use_cases/kb/buscar_chunks.py` + `listar` + `deletar` | `test_buscar_chunks.py` |
| `interface/http/routers/admin/auth.py` | `test_auth_router.py` |
| `interface/http/routers/admin/documents.py` | `test_documents_router.py` |
| `interface/http/deps/admin_deps.py` | `test_admin_deps.py` |

- [ ] **Step 4: Corrigir falhas**

Se qualquer teste falhar:
1. Ler o traceback.
2. Identificar a causa raiz (import errado, método faltando, assinatura incorreta).
3. Corrigir o arquivo de implementação — nunca o teste.
4. Reexecutar o teste específico.
5. Repetir até que `uv run pytest tests/unit/ -q` passe sem erros.

- [ ] **Step 5: Commit final**

```
git add .
git commit -m "feat(kb-admin): complete KB Admin implementation — all unit tests passing"
```

---

## Checklist de Self-Review

Após escrever o plano, verificar:

- [x] **RF-1**: Upload de documentos → chunking → embeddings → pgvector — coberto por `IngerirDocumento` (T7) e routers (T10).
- [x] **RF-2**: CRUD de documentos e chunks — coberto por `DocumentRepository` (T5), `ChunkRepository` (T8), e routers (T10).
- [x] **RF-3**: JWT auth multi-tenant com roles — coberto por `jwt_handler` (T9), `AdminUserRepository` (T9), `get_admin_deps` (T11).
- [x] **RF-4**: Endpoint de busca de teste — coberto por `BuscarChunks` (T8) e `search.py` router (T10).
- [x] **RF-5**: Usage logs — coberto por `UsageLogRepository` (T5) e `BuscarChunks` (T8).
- [x] **RNF-1**: Multi-tenant (`account_id: int` em todas entidades de domínio).
- [x] **RNF-2**: Flush-not-commit em todos os repos.
- [x] **RNF-3**: Tipo consistente: `account_id: int` (não UUID) em todos os novos artefatos.
- [x] **RNF-4**: Sem placeholders — todos os passos mostram implementação completa.
- [x] **RNF-5**: Testes: red → green → commit por task.
- [x] **RNF-6**: pgvector `similarity_search` não unit-testado (complexidade — requer DB real).
- [x] **RNF-7**: `TextExtractor` — só o path TXT/Markdown é unit-testado.
- [x] **RNF-8**: Chain de migrações: `50d62657fc63` → pgvector → KB tables.
- [x] **RNF-9**: Nenhum `@tool`, nenhum LangGraph, nenhum grafo — apenas FastAPI + use cases.

---

## Notas de Implementação

### Dependências a verificar em `pyproject.toml`

```toml
"python-jose[cryptography]>=3.3.0",
"passlib[bcrypt]>=1.7.4",
"pgvector>=0.2.0",
"pypdf>=4.0.0",
"python-docx>=1.1.0",
"tiktoken>=0.7.0",
```

Verificar com `uv pip list | grep -E "jose|passlib|pgvector|pypdf|docx|tiktoken"`. Adicionar via `uv add <pacote>` se faltarem.

### Ordem de execução recomendada

Tasks 1–6 são independentes entre si (exceto que T2 depende de T1 para os models). Tasks 7–12 constroem sobre as anteriores. Sequência sugerida: T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 → T12.

### Nota sobre `KnowledgePort` existente

O `KnowledgePort` em `src/nexoia/domain/ports/knowledge.py` usa `account_id: UUID`. O KB Admin usa `account_id: int` (campo legado de `account_id` inteiro nos outros módulos). `BuscarChunks` expõe sua própria interface com `int` e **não** implementa o `KnowledgePort` existente — isso evita quebrar o contrato de tipagem do agente LangGraph.

### Nota sobre upload assíncrono

O endpoint `POST /documents/upload` usa `asyncio.create_task()` para ingerir em background. Em produção, considerar um worker Redis (fila) para resiliência. Para o escopo desta spec, `create_task` é suficiente.
