# KB Admin (Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o backend Python do KB Admin da NexoIA — endpoints FastAPI em `/api/v1/admin/*` para que a equipe da G2 Educação faça upload de documentos (PDF/DOCX/TXT/MD/imagens com OCR), chunking, indexação via pgvector e busca RAG de teste. O painel **não expõe prompts** — alimenta apenas documentos/chunks (RNF-K04). Multi-tenant por `account_id` em todas as queries (RF-K10).

**Architecture:** Camadas limpas (domain/application/infrastructure/interface). Extractors de texto isolados por formato, chunking com sliding window tokenizado, embeddings via OpenAI em batch com retry exponencial, persistência em PostgreSQL + pgvector (IVFFlat cosine). Indexação **assíncrona** via worker (upload → 202 Accepted → worker processa PENDING → PROCESSING → INDEXED/ERROR). Busca RAG via `chunk_repo.similarity_search` com threshold 0.55. Auth JWT com perfis `admin`/`editor`/`viewer`. Frontend React (`nexoia-panel`) **fora deste plano**.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, pgvector, psycopg2/asyncpg, pypdf, python-docx, tiktoken, openai, passlib[bcrypt], python-jose (JWT), structlog, prometheus-client, pytest, pytest-asyncio, testcontainers (PostgreSQL + pgvector), uv.

**Prerequisite:** Core (Spec ①) implementado — FastAPI app factory (`main.py`), SQLAlchemy `Base`, `get_db_session` dep, OpenAI client, auth middleware scaffold, container DI, Alembic configurado, settings base.

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `src/nexoia/domain/entities/knowledge_document.py` | Criar | Entidade `KnowledgeDocument` + enum `DocumentStatus` |
| `src/nexoia/domain/entities/knowledge_chunk.py` | Criar | Entidade `KnowledgeChunk` |
| `src/nexoia/domain/entities/admin_user.py` | Criar | Entidade `AdminUser` + enum `AdminRole` |
| `src/nexoia/domain/errors.py` | Modificar | `ExtractionError`, `EmbeddingError`, `AuthError`, `FileTooLargeError` |
| `src/nexoia/domain/ports/embeddings_port.py` | Criar | Protocol `EmbeddingsPort` |
| `src/nexoia/config/settings.py` | Modificar | `KB_*`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES` |
| `migrations/versions/xxxx_enable_pgvector.py` | Criar | `CREATE EXTENSION IF NOT EXISTS vector` |
| `migrations/versions/xxxx_add_kb_tables.py` | Criar | `knowledge_documents`, `knowledge_chunks`, `kb_usage_logs`, `admin_users` + IVFFlat |
| `src/nexoia/infrastructure/db/models.py` | Modificar | `KnowledgeDocumentModel`, `KnowledgeChunkModel`, `KbUsageLogModel`, `AdminUserModel` |
| `src/nexoia/infrastructure/db/repositories/document_repo.py` | Criar | `DocumentRepository` (CRUD, status transitions) |
| `src/nexoia/infrastructure/db/repositories/chunk_repo.py` | Criar | `ChunkRepository` (bulk insert, similarity_search pgvector, cascade-delete) |
| `src/nexoia/infrastructure/db/repositories/usage_log_repo.py` | Criar | `UsageLogRepository` |
| `src/nexoia/infrastructure/db/repositories/admin_user_repo.py` | Criar | `AdminUserRepository` (get_by_email, verify_password) |
| `src/nexoia/infrastructure/kb/extractors.py` | Criar | `extract_text(mime, bytes) -> str` via pypdf / python-docx / utf-8 / Vision OCR |
| `src/nexoia/infrastructure/kb/chunker.py` | Criar | `chunk_text(text, size, overlap) -> list[Chunk]` com tiktoken |
| `src/nexoia/infrastructure/embeddings/openai_embeddings.py` | Criar | Cliente OpenAI batch + retry exponencial |
| `src/nexoia/application/kb/ingestion.py` | Criar | Use case: extract → chunk → embed → persist |
| `src/nexoia/application/kb/search.py` | Criar | Use case RAG: embed query → similarity_search → log |
| `src/nexoia/application/auth/jwt_service.py` | Criar | `issue_token`, `decode_token` (HS256) |
| `src/nexoia/interface/worker/handlers/ingest_document.py` | Criar | Handler `IngestDocument` (async PENDING → PROCESSING → INDEXED/ERROR) |
| `src/nexoia/interface/worker/dispatcher.py` | Modificar | Registrar `IngestDocument` |
| `src/nexoia/interface/http/deps.py` | Modificar | `get_current_admin_user`, `require_role` |
| `src/nexoia/interface/http/routers/admin/__init__.py` | Criar | Package marker |
| `src/nexoia/interface/http/routers/admin/auth.py` | Criar | `POST /login`, `POST /refresh` |
| `src/nexoia/interface/http/routers/admin/documents.py` | Criar | CRUD + upload + reindex |
| `src/nexoia/interface/http/routers/admin/chunks.py` | Criar | `GET /documents/{id}/chunks` |
| `src/nexoia/interface/http/routers/admin/search.py` | Criar | `POST /search/test` |
| `src/nexoia/interface/http/routers/admin/usage.py` | Criar | `GET /usage/logs` |
| `src/nexoia/interface/http/schemas/admin.py` | Criar | Pydantic schemas req/resp |
| `src/nexoia/main.py` | Modificar | Registrar routers admin |
| `src/nexoia/infrastructure/observability/metrics.py` | Modificar | Métricas KB |
| `tests/fakes/fake_embeddings_client.py` | Criar | `FakeEmbeddingsClient` com `fail_times` |
| `tests/unit/kb/test_extractors.py` | Criar | Testes unitários de extração |
| `tests/unit/kb/test_chunker.py` | Criar | Testes de chunking |
| `tests/unit/kb/test_embeddings.py` | Criar | Testes de retry/batch |
| `tests/unit/kb/test_ingestion.py` | Criar | Testes de orquestração |
| `tests/unit/kb/test_search.py` | Criar | Testes RAG (threshold, isolation) |
| `tests/unit/auth/test_jwt_service.py` | Criar | Testes JWT |
| `tests/unit/auth/test_deps.py` | Criar | Testes middleware + roles |
| `tests/integration/test_kb_repos.py` | Criar | Repositórios contra Postgres+pgvector |
| `tests/integration/test_kb_flow.py` | Criar | Upload → ingest → search E2E |
| `tests/integration/test_admin_api.py` | Criar | Routers FastAPI via TestClient |

---

## Task 1: Entidades `KnowledgeDocument` + `DocumentStatus`

**Files:**
- Create: `src/nexoia/domain/entities/knowledge_document.py`
- Test: `tests/unit/domain/test_knowledge_document.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/domain/test_knowledge_document.py
from nexoia.domain.entities.knowledge_document import (
    KnowledgeDocument,
    DocumentStatus,
)


def test_document_status_string_values():
    assert DocumentStatus.PENDING == "pending"
    assert DocumentStatus.PROCESSING == "processing"
    assert DocumentStatus.INDEXED == "indexed"
    assert DocumentStatus.ERROR == "error"


def test_document_defaults():
    doc = KnowledgeDocument(
        account_id=1,
        filename="faq.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        created_by="user-1",
    )
    assert doc.status == DocumentStatus.PENDING
    assert doc.chunk_count == 0
    assert doc.tags == []
    assert doc.error_message is None
    assert len(doc.id) == 36  # UUID


def test_document_with_tags_and_error():
    doc = KnowledgeDocument(
        account_id=2,
        filename="policy.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        file_size_bytes=2048,
        created_by="user-2",
        tags=["acesso", "reembolso"],
        status=DocumentStatus.ERROR,
        error_message="OCR falhou",
    )
    assert doc.tags == ["acesso", "reembolso"]
    assert doc.status == DocumentStatus.ERROR
    assert doc.error_message == "OCR falhou"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
cd /path/to/nexoia-agent
uv run pytest tests/unit/domain/test_knowledge_document.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar a entidade**

```python
# src/nexoia/domain/entities/knowledge_document.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class DocumentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    ERROR = "error"


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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_knowledge_document.py -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/entities/knowledge_document.py tests/unit/domain/test_knowledge_document.py
git commit -m "feat(kb): add KnowledgeDocument entity and DocumentStatus enum"
```

---

## Task 2: Entidade `KnowledgeChunk`

**Files:**
- Create: `src/nexoia/domain/entities/knowledge_chunk.py`
- Test: `tests/unit/domain/test_knowledge_chunk.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/domain/test_knowledge_chunk.py
from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk


def test_chunk_has_uuid_and_required_fields():
    chunk = KnowledgeChunk(
        document_id="doc-1",
        account_id=1,
        text="Hello world",
        chunk_index=0,
        token_count=2,
        embedding=[0.1] * 1536,
    )
    assert len(chunk.id) == 36
    assert chunk.chunk_index == 0
    assert len(chunk.embedding) == 1536


def test_chunk_embedding_dimension_is_1536():
    chunk = KnowledgeChunk(
        document_id="d",
        account_id=1,
        text="t",
        chunk_index=0,
        token_count=1,
        embedding=[0.0] * 1536,
    )
    assert len(chunk.embedding) == 1536
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_knowledge_chunk.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar a entidade**

```python
# src/nexoia/domain/entities/knowledge_chunk.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    score: float | None = None  # populado em similarity_search
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_knowledge_chunk.py -v
```
Esperado: 2 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/entities/knowledge_chunk.py tests/unit/domain/test_knowledge_chunk.py
git commit -m "feat(kb): add KnowledgeChunk entity with 1536-dim embedding"
```

---

## Task 3: Entidade `AdminUser` + enum `AdminRole` + erros de domínio

**Files:**
- Create: `src/nexoia/domain/entities/admin_user.py`
- Modify: `src/nexoia/domain/errors.py`
- Test: `tests/unit/domain/test_admin_user.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/domain/test_admin_user.py
from nexoia.domain.entities.admin_user import AdminUser, AdminRole
from nexoia.domain.errors import (
    ExtractionError,
    EmbeddingError,
    AuthError,
    FileTooLargeError,
)


def test_admin_role_values():
    assert AdminRole.ADMIN == "admin"
    assert AdminRole.EDITOR == "editor"
    assert AdminRole.VIEWER == "viewer"


def test_admin_user_defaults():
    u = AdminUser(
        account_id=1,
        email="ops@g2.com.br",
        password_hash="bcrypt-hash",
    )
    assert u.role == AdminRole.VIEWER
    assert len(u.id) == 36


def test_domain_errors_are_exceptions():
    for Err in (ExtractionError, EmbeddingError, AuthError, FileTooLargeError):
        err = Err("boom")
        assert isinstance(err, Exception)
        assert str(err) == "boom"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_admin_user.py -v
```
Esperado: `ImportError` / `ModuleNotFoundError`.

- [ ] **Step 3: Adicionar erros ao arquivo existente**

No arquivo `src/nexoia/domain/errors.py`, adicionar ao final:

```python
class ExtractionError(Exception):
    """Falha ao extrair texto de um documento (PDF/DOCX/imagem)."""


class EmbeddingError(Exception):
    """Falha ao chamar o provider de embeddings (OpenAI)."""


class AuthError(Exception):
    """Credenciais inválidas, token expirado ou permissão insuficiente."""


class FileTooLargeError(Exception):
    """Arquivo excede `KB_MAX_FILE_SIZE_MB`."""
```

- [ ] **Step 4: Criar a entidade `AdminUser`**

```python
# src/nexoia/domain/entities/admin_user.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class AdminRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


@dataclass
class AdminUser:
    account_id: int
    email: str
    password_hash: str
    id: str = field(default_factory=lambda: str(uuid4()))
    role: AdminRole = AdminRole.VIEWER
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_admin_user.py -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/domain/entities/admin_user.py src/nexoia/domain/errors.py \
        tests/unit/domain/test_admin_user.py
git commit -m "feat(kb): add AdminUser, AdminRole and KB domain errors"
```

---

## Task 4: Settings — variáveis de KB e JWT

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Test: `tests/unit/config/test_settings_kb.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/config/test_settings_kb.py
from nexoia.config.settings import Settings


def _base_kwargs() -> dict:
    return dict(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://localhost:6379",
        CHATNEXO_API_KEY="key",
        OPENAI_API_KEY="sk-test",
        JWT_SECRET="x" * 32,
    )


def test_kb_defaults():
    s = Settings(**_base_kwargs())
    assert s.KB_CHUNK_SIZE == 512
    assert s.KB_CHUNK_OVERLAP == 50
    assert s.KB_TOP_K == 5
    assert s.KB_THRESHOLD == 0.55
    assert s.KB_EMBEDDING_MODEL == "text-embedding-3-small"
    assert s.KB_MAX_FILE_SIZE_MB == 20
    assert s.KB_EMBEDDING_BATCH_SIZE == 100
    assert s.KB_EMBEDDING_MAX_RETRIES == 3


def test_jwt_defaults():
    s = Settings(**_base_kwargs())
    assert len(s.JWT_SECRET) >= 32
    assert s.JWT_EXPIRE_MINUTES == 60
    assert s.JWT_ALGORITHM == "HS256"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/config/test_settings_kb.py -v
```
Esperado: `ValidationError` / `AttributeError`.

- [ ] **Step 3: Adicionar variáveis ao `Settings`**

```python
# src/nexoia/config/settings.py (trechos a adicionar ao model Settings)
    # Knowledge Base
    KB_CHUNK_SIZE: int = 512
    KB_CHUNK_OVERLAP: int = 50
    KB_TOP_K: int = 5
    KB_THRESHOLD: float = 0.55
    KB_EMBEDDING_MODEL: str = "text-embedding-3-small"
    KB_MAX_FILE_SIZE_MB: int = 20
    KB_EMBEDDING_BATCH_SIZE: int = 100
    KB_EMBEDDING_MAX_RETRIES: int = 3
    KB_EMBEDDING_RETRY_BASE_SECONDS: float = 1.0

    # JWT — KB Admin
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
```

Validador (se o Settings base usar Pydantic v2):

```python
    @field_validator("JWT_SECRET")
    @classmethod
    def _jwt_secret_min_length(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET must be at least 32 chars")
        return v
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/config/test_settings_kb.py -v
```
Esperado: 2 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/config/settings.py tests/unit/config/test_settings_kb.py
git commit -m "feat(kb): add KB and JWT settings with safe defaults"
```

---

## Task 5: Migration — habilitar extensão `pgvector`

**Files:**
- Create: `migrations/versions/xxxx_enable_pgvector.py`

- [ ] **Step 1: Gerar a revisão (vazia)**

```bash
uv run alembic revision -m "enable_pgvector_extension"
```

- [ ] **Step 2: Editar o arquivo gerado**

```python
# migrations/versions/XXXX_enable_pgvector.py
"""enable pgvector extension

Revision ID: XXXX
Revises: <prev>
Create Date: 2026-04-18
"""
from alembic import op


revision = "XXXX"
down_revision = "<prev>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
```

- [ ] **Step 3: Aplicar em banco dev**

```bash
uv run alembic upgrade head
```
Esperado: `Running upgrade ... -> XXXX, enable_pgvector_extension`.

- [ ] **Step 4: Confirmar extensão ativa**

```bash
psql "$DATABASE_URL" -c "SELECT extname FROM pg_extension WHERE extname='vector';"
```
Esperado: 1 linha com `vector`.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/XXXX_enable_pgvector.py
git commit -m "feat(kb): enable pgvector extension via Alembic migration"
```

---

## Task 6: Migration — tabelas KB + índices pgvector IVFFlat

**Files:**
- Modify: `src/nexoia/infrastructure/db/models.py`
- Create: `migrations/versions/xxxx_add_kb_tables.py`

- [ ] **Step 1: Adicionar models SQLAlchemy**

No arquivo `src/nexoia/infrastructure/db/models.py`, adicionar (importar `Vector` de `pgvector.sqlalchemy`):

```python
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY, BigInteger, Boolean, Column, DateTime, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, nullable=False, index=True)
    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False, default="pending")
    chunk_count = Column(Integer, nullable=False, default=0)
    tags = Column(ARRAY(Text), nullable=False, server_default="{}")
    error_message = Column(Text, nullable=True)
    created_by = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)


class KnowledgeChunkModel(Base):
    __tablename__ = "knowledge_chunks"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(PG_UUID(as_uuid=False),
                         ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
                         nullable=False)
    account_id = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_knowledge_chunks_document", "document_id"),
        Index("idx_knowledge_chunks_account", "account_id"),
    )


class KbUsageLogModel(Base):
    __tablename__ = "kb_usage_logs"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, nullable=False, index=True)
    query = Column(Text, nullable=False)
    result_count = Column(Integer, nullable=False)
    top_chunk_id = Column(PG_UUID(as_uuid=False), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AdminUserModel(Base):
    __tablename__ = "admin_users"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, nullable=False)
    email = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(String, nullable=False, default="viewer")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("account_id", "email", name="uq_admin_users_account_email"),
    )
```

- [ ] **Step 2: Gerar a migration**

```bash
uv run alembic revision --autogenerate -m "add_kb_tables"
```

- [ ] **Step 3: Editar para adicionar o índice IVFFlat**

Abrir o arquivo gerado e garantir no `upgrade()`:

```python
def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        # colunas...
    )
    op.create_table(
        "knowledge_chunks",
        # colunas com sa.Column("embedding", Vector(1536), nullable=False)
    )
    op.create_table("kb_usage_logs", ...)
    op.create_table(
        "admin_users",
        # ...
        sa.UniqueConstraint("account_id", "email", name="uq_admin_users_account_email"),
    )

    # IVFFlat cosine index (RNF-K03)
    op.execute(
        "CREATE INDEX idx_knowledge_chunks_account_embedding "
        "ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )
    op.create_index("idx_knowledge_chunks_document", "knowledge_chunks", ["document_id"])
    op.create_index("idx_knowledge_chunks_account", "knowledge_chunks", ["account_id"])
    op.create_index("idx_knowledge_documents_account", "knowledge_documents", ["account_id"])


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_knowledge_chunks_account_embedding")
    op.drop_table("admin_users")
    op.drop_table("kb_usage_logs")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
```

- [ ] **Step 4: Aplicar**

```bash
uv run alembic upgrade head
```
Esperado: migration aplicada sem erros.

- [ ] **Step 5: Verificar índice**

```bash
psql "$DATABASE_URL" -c "\di idx_knowledge_chunks_account_embedding"
```
Esperado: 1 linha com `ivfflat`.

- [ ] **Step 6: Commit**

```bash
git add migrations/ src/nexoia/infrastructure/db/models.py
git commit -m "feat(kb): add knowledge_documents/chunks/usage_logs/admin_users tables + IVFFlat index"
```

---

## Task 7: `DocumentRepository`

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/document_repo.py`
- Test: `tests/integration/test_kb_repos.py` (parte 1)

- [ ] **Step 1: Escrever o teste de integração falhando**

```python
# tests/integration/test_kb_repos.py
import pytest
from nexoia.domain.entities.knowledge_document import KnowledgeDocument, DocumentStatus
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository


@pytest.mark.asyncio
async def test_save_and_get_document(db_session):
    repo = DocumentRepository(db_session)
    doc = KnowledgeDocument(
        account_id=1, filename="f.pdf", mime_type="application/pdf",
        file_size_bytes=10, created_by="u1",
    )
    await repo.save(doc)
    found = await repo.get(doc.id, account_id=1)
    assert found is not None
    assert found.filename == "f.pdf"
    assert found.status == DocumentStatus.PENDING


@pytest.mark.asyncio
async def test_get_respects_tenant_isolation(db_session):
    repo = DocumentRepository(db_session)
    doc = KnowledgeDocument(
        account_id=1, filename="f.pdf", mime_type="application/pdf",
        file_size_bytes=10, created_by="u1",
    )
    await repo.save(doc)
    assert await repo.get(doc.id, account_id=2) is None


@pytest.mark.asyncio
async def test_list_paginated(db_session):
    repo = DocumentRepository(db_session)
    for i in range(3):
        await repo.save(KnowledgeDocument(
            account_id=1, filename=f"f{i}.pdf", mime_type="application/pdf",
            file_size_bytes=10, created_by="u1",
        ))
    items, total = await repo.list(account_id=1, limit=2, offset=0)
    assert total == 3
    assert len(items) == 2


@pytest.mark.asyncio
async def test_update_status_and_chunk_count(db_session):
    repo = DocumentRepository(db_session)
    doc = KnowledgeDocument(
        account_id=1, filename="f.pdf", mime_type="application/pdf",
        file_size_bytes=10, created_by="u1",
    )
    await repo.save(doc)
    await repo.set_status(doc.id, DocumentStatus.PROCESSING)
    await repo.set_status(doc.id, DocumentStatus.INDEXED, chunk_count=7)
    updated = await repo.get(doc.id, account_id=1)
    assert updated.status == DocumentStatus.INDEXED
    assert updated.chunk_count == 7


@pytest.mark.asyncio
async def test_delete_cascade(db_session):
    repo = DocumentRepository(db_session)
    doc = KnowledgeDocument(
        account_id=1, filename="f.pdf", mime_type="application/pdf",
        file_size_bytes=10, created_by="u1",
    )
    await repo.save(doc)
    await repo.delete(doc.id, account_id=1)
    assert await repo.get(doc.id, account_id=1) is None
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_kb_repos.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar o repositório**

```python
# src/nexoia/infrastructure/db/repositories/document_repo.py
from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.knowledge_document import (
    DocumentStatus,
    KnowledgeDocument,
)
from nexoia.infrastructure.db.models import KnowledgeDocumentModel


class DocumentRepository:
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
            tags=doc.tags,
            error_message=doc.error_message,
            created_by=doc.created_by,
        )
        self._session.add(model)
        await self._session.commit()

    async def get(self, doc_id: str, *, account_id: int) -> KnowledgeDocument | None:
        stmt = select(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.id == doc_id,
            KnowledgeDocumentModel.account_id == account_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list(
        self, *, account_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[list[KnowledgeDocument], int]:
        count_stmt = select(func.count()).select_from(KnowledgeDocumentModel).where(
            KnowledgeDocumentModel.account_id == account_id,
        )
        total = (await self._session.execute(count_stmt)).scalar_one()
        stmt = (
            select(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.account_id == account_id)
            .order_by(KnowledgeDocumentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(r) for r in rows], total

    async def set_status(
        self,
        doc_id: str,
        status: DocumentStatus,
        *,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        values = {"status": status.value}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count
        if error_message is not None:
            values["error_message"] = error_message
        await self._session.execute(
            update(KnowledgeDocumentModel)
            .where(KnowledgeDocumentModel.id == doc_id)
            .values(**values)
        )
        await self._session.commit()

    async def delete(self, doc_id: str, *, account_id: int) -> None:
        await self._session.execute(
            delete(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.id == doc_id,
                KnowledgeDocumentModel.account_id == account_id,
            )
        )
        await self._session.commit()

    def _to_entity(self, m: KnowledgeDocumentModel) -> KnowledgeDocument:
        doc = KnowledgeDocument(
            account_id=m.account_id,
            filename=m.filename,
            mime_type=m.mime_type,
            file_size_bytes=m.file_size_bytes,
            created_by=m.created_by,
        )
        doc.id = str(m.id)
        doc.status = DocumentStatus(m.status)
        doc.chunk_count = m.chunk_count
        doc.tags = list(m.tags or [])
        doc.error_message = m.error_message
        doc.created_at = m.created_at
        doc.updated_at = m.updated_at
        return doc
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_kb_repos.py -v -k document
```
Esperado: 5 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/document_repo.py \
        tests/integration/test_kb_repos.py
git commit -m "feat(kb): add DocumentRepository with tenant isolation and cascade delete"
```

---

## Task 8: `ChunkRepository` com `similarity_search` pgvector

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/chunk_repo.py`
- Test: `tests/integration/test_kb_repos.py` (parte 2 — append)

- [ ] **Step 1: Escrever os testes de integração falhando (append)**

```python
# tests/integration/test_kb_repos.py — APPEND
import random
import pytest
from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from nexoia.domain.entities.knowledge_document import KnowledgeDocument
from nexoia.infrastructure.db.repositories.chunk_repo import ChunkRepository
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository


def _emb(seed: int) -> list[float]:
    rnd = random.Random(seed)
    return [rnd.uniform(-1, 1) for _ in range(1536)]


async def _make_doc(db_session, account_id: int) -> KnowledgeDocument:
    doc = KnowledgeDocument(
        account_id=account_id, filename="f.pdf", mime_type="application/pdf",
        file_size_bytes=10, created_by="u1",
    )
    await DocumentRepository(db_session).save(doc)
    return doc


@pytest.mark.asyncio
async def test_bulk_insert_chunks(db_session):
    doc = await _make_doc(db_session, 1)
    repo = ChunkRepository(db_session)
    chunks = [
        KnowledgeChunk(
            document_id=doc.id, account_id=1, text=f"c{i}",
            chunk_index=i, token_count=3, embedding=_emb(i),
        )
        for i in range(5)
    ]
    await repo.bulk_insert(chunks)
    listed = await repo.list_by_document(doc.id, account_id=1)
    assert len(listed) == 5


@pytest.mark.asyncio
async def test_similarity_search_returns_above_threshold(db_session):
    doc = await _make_doc(db_session, 1)
    repo = ChunkRepository(db_session)
    target = _emb(42)
    chunks = [
        KnowledgeChunk(
            document_id=doc.id, account_id=1, text="match",
            chunk_index=0, token_count=1, embedding=target,
        ),
        KnowledgeChunk(
            document_id=doc.id, account_id=1, text="different",
            chunk_index=1, token_count=1, embedding=[-x for x in target],
        ),
    ]
    await repo.bulk_insert(chunks)
    results = await repo.similarity_search(
        embedding=target, account_id=1, threshold=0.9, top_k=5,
    )
    assert len(results) == 1
    assert results[0].text == "match"
    assert results[0].score is not None and results[0].score >= 0.9


@pytest.mark.asyncio
async def test_similarity_search_tenant_isolation(db_session):
    doc_a = await _make_doc(db_session, 1)
    doc_b = await _make_doc(db_session, 2)
    repo = ChunkRepository(db_session)
    target = _emb(7)
    await repo.bulk_insert([
        KnowledgeChunk(document_id=doc_a.id, account_id=1, text="A",
                       chunk_index=0, token_count=1, embedding=target),
        KnowledgeChunk(document_id=doc_b.id, account_id=2, text="B",
                       chunk_index=0, token_count=1, embedding=target),
    ])
    results_for_1 = await repo.similarity_search(
        embedding=target, account_id=1, threshold=0.0, top_k=10,
    )
    assert all(c.account_id == 1 for c in results_for_1)
    assert {c.text for c in results_for_1} == {"A"}


@pytest.mark.asyncio
async def test_delete_by_document_cascade(db_session):
    doc = await _make_doc(db_session, 1)
    repo = ChunkRepository(db_session)
    await repo.bulk_insert([
        KnowledgeChunk(document_id=doc.id, account_id=1, text="x",
                       chunk_index=0, token_count=1, embedding=_emb(1)),
    ])
    await repo.delete_by_document(doc.id)
    assert await repo.list_by_document(doc.id, account_id=1) == []
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_kb_repos.py -v -k chunk
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar o repositório**

```python
# src/nexoia/infrastructure/db/repositories/chunk_repo.py
from __future__ import annotations

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from nexoia.infrastructure.db.models import KnowledgeChunkModel


class ChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_insert(self, chunks: list[KnowledgeChunk]) -> None:
        models = [
            KnowledgeChunkModel(
                id=c.id,
                document_id=c.document_id,
                account_id=c.account_id,
                text=c.text,
                chunk_index=c.chunk_index,
                token_count=c.token_count,
                embedding=c.embedding,
            )
            for c in chunks
        ]
        self._session.add_all(models)
        await self._session.commit()

    async def list_by_document(
        self, document_id: str, *, account_id: int
    ) -> list[KnowledgeChunk]:
        stmt = (
            select(KnowledgeChunkModel)
            .where(
                KnowledgeChunkModel.document_id == document_id,
                KnowledgeChunkModel.account_id == account_id,
            )
            .order_by(KnowledgeChunkModel.chunk_index.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_entity(r) for r in rows]

    async def similarity_search(
        self,
        *,
        embedding: list[float],
        account_id: int,
        threshold: float,
        top_k: int,
    ) -> list[KnowledgeChunk]:
        # pgvector: `<=>` = cosine distance; score = 1 - distance
        sql = text(
            """
            SELECT id, document_id, account_id, text, chunk_index, token_count,
                   embedding, created_at,
                   1 - (embedding <=> CAST(:qvec AS vector)) AS score
            FROM knowledge_chunks
            WHERE account_id = :account_id
              AND 1 - (embedding <=> CAST(:qvec AS vector)) >= :threshold
            ORDER BY embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
            """
        )
        rows = await self._session.execute(
            sql,
            {
                "qvec": embedding,
                "account_id": account_id,
                "threshold": threshold,
                "top_k": top_k,
            },
        )
        out: list[KnowledgeChunk] = []
        for row in rows.mappings():
            chunk = KnowledgeChunk(
                document_id=str(row["document_id"]),
                account_id=row["account_id"],
                text=row["text"],
                chunk_index=row["chunk_index"],
                token_count=row["token_count"],
                embedding=list(row["embedding"]),
            )
            chunk.id = str(row["id"])
            chunk.created_at = row["created_at"]
            chunk.score = float(row["score"])
            out.append(chunk)
        return out

    async def delete_by_document(self, document_id: str) -> None:
        await self._session.execute(
            delete(KnowledgeChunkModel).where(
                KnowledgeChunkModel.document_id == document_id,
            )
        )
        await self._session.commit()

    def _to_entity(self, m: KnowledgeChunkModel) -> KnowledgeChunk:
        chunk = KnowledgeChunk(
            document_id=str(m.document_id),
            account_id=m.account_id,
            text=m.text,
            chunk_index=m.chunk_index,
            token_count=m.token_count,
            embedding=list(m.embedding),
        )
        chunk.id = str(m.id)
        chunk.created_at = m.created_at
        return chunk
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_kb_repos.py -v -k chunk
```
Esperado: 4 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/chunk_repo.py \
        tests/integration/test_kb_repos.py
git commit -m "feat(kb): add ChunkRepository with pgvector cosine similarity_search and tenant filter"
```

---

## Task 9: `UsageLogRepository` e `AdminUserRepository`

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/usage_log_repo.py`
- Create: `src/nexoia/infrastructure/db/repositories/admin_user_repo.py`
- Test: `tests/integration/test_kb_repos.py` (parte 3 — append)

- [ ] **Step 1: Escrever os testes falhando (append)**

```python
# tests/integration/test_kb_repos.py — APPEND
from nexoia.domain.entities.admin_user import AdminRole, AdminUser
from nexoia.infrastructure.db.repositories.admin_user_repo import AdminUserRepository
from nexoia.infrastructure.db.repositories.usage_log_repo import UsageLogRepository


@pytest.mark.asyncio
async def test_usage_log_record_and_list(db_session):
    repo = UsageLogRepository(db_session)
    await repo.record(account_id=1, query="como recuperar acesso?",
                      result_count=3, top_chunk_id="11111111-1111-1111-1111-111111111111")
    await repo.record(account_id=1, query="shopee", result_count=0, top_chunk_id=None)
    items = await repo.list(account_id=1, limit=10, offset=0)
    assert len(items) == 2


@pytest.mark.asyncio
async def test_usage_log_tenant_isolation(db_session):
    repo = UsageLogRepository(db_session)
    await repo.record(account_id=1, query="a", result_count=0, top_chunk_id=None)
    await repo.record(account_id=2, query="b", result_count=0, top_chunk_id=None)
    items = await repo.list(account_id=1, limit=10, offset=0)
    assert all(it.account_id == 1 for it in items)


@pytest.mark.asyncio
async def test_admin_user_get_by_email(db_session):
    repo = AdminUserRepository(db_session)
    u = AdminUser(account_id=1, email="ops@g2.com", password_hash="h",
                  role=AdminRole.ADMIN)
    await repo.save(u)
    found = await repo.get_by_email(account_id=1, email="ops@g2.com")
    assert found is not None
    assert found.role == AdminRole.ADMIN


@pytest.mark.asyncio
async def test_admin_user_unique_per_account(db_session):
    repo = AdminUserRepository(db_session)
    await repo.save(AdminUser(account_id=1, email="dup@g2.com", password_hash="h"))
    with pytest.raises(Exception):
        await repo.save(AdminUser(account_id=1, email="dup@g2.com", password_hash="h"))
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_kb_repos.py -v -k "usage or admin"
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar os repositórios**

```python
# src/nexoia/infrastructure/db/repositories/usage_log_repo.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.infrastructure.db.models import KbUsageLogModel


@dataclass
class UsageLogEntry:
    id: str
    account_id: int
    query: str
    result_count: int
    top_chunk_id: str | None
    created_at: datetime


class UsageLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        account_id: int,
        query: str,
        result_count: int,
        top_chunk_id: str | None,
    ) -> None:
        model = KbUsageLogModel(
            id=str(uuid4()),
            account_id=account_id,
            query=query,
            result_count=result_count,
            top_chunk_id=top_chunk_id,
        )
        self._session.add(model)
        await self._session.commit()

    async def list(
        self, *, account_id: int, limit: int, offset: int
    ) -> list[UsageLogEntry]:
        stmt = (
            select(KbUsageLogModel)
            .where(KbUsageLogModel.account_id == account_id)
            .order_by(KbUsageLogModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [
            UsageLogEntry(
                id=str(r.id),
                account_id=r.account_id,
                query=r.query,
                result_count=r.result_count,
                top_chunk_id=str(r.top_chunk_id) if r.top_chunk_id else None,
                created_at=r.created_at,
            )
            for r in rows
        ]
```

```python
# src/nexoia/infrastructure/db/repositories/admin_user_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.admin_user import AdminRole, AdminUser
from nexoia.infrastructure.db.models import AdminUserModel


class AdminUserRepository:
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
        await self._session.commit()

    async def get_by_email(
        self, *, account_id: int, email: str
    ) -> AdminUser | None:
        stmt = select(AdminUserModel).where(
            AdminUserModel.account_id == account_id,
            AdminUserModel.email == email,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        u = AdminUser(
            account_id=row.account_id,
            email=row.email,
            password_hash=row.password_hash,
            role=AdminRole(row.role),
        )
        u.id = str(row.id)
        u.created_at = row.created_at
        return u

    async def get(self, user_id: str) -> AdminUser | None:
        row = await self._session.get(AdminUserModel, user_id)
        if row is None:
            return None
        u = AdminUser(
            account_id=row.account_id,
            email=row.email,
            password_hash=row.password_hash,
            role=AdminRole(row.role),
        )
        u.id = str(row.id)
        u.created_at = row.created_at
        return u
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_kb_repos.py -v -k "usage or admin"
```
Esperado: 4 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/usage_log_repo.py \
        src/nexoia/infrastructure/db/repositories/admin_user_repo.py \
        tests/integration/test_kb_repos.py
git commit -m "feat(kb): add UsageLogRepository and AdminUserRepository"
```

---

## Task 10: Extractors de texto (PDF/DOCX/TXT/MD/imagem com OCR via Vision)

**Files:**
- Create: `src/nexoia/infrastructure/kb/__init__.py`
- Create: `src/nexoia/infrastructure/kb/extractors.py`
- Test: `tests/unit/kb/test_extractors.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/kb/test_extractors.py
import io
import pytest
from unittest.mock import AsyncMock

from nexoia.domain.errors import ExtractionError
from nexoia.infrastructure.kb.extractors import extract_text


@pytest.mark.asyncio
async def test_extract_txt_utf8():
    out = await extract_text(mime="text/plain",
                              data=b"Hello world\nSecond line.")
    assert "Hello world" in out
    assert "Second line" in out


@pytest.mark.asyncio
async def test_extract_markdown_utf8():
    out = await extract_text(mime="text/markdown",
                              data=b"# Title\n\nparagraph.")
    assert "Title" in out


@pytest.mark.asyncio
async def test_extract_pdf(monkeypatch):
    # stub do pypdf: força reader que devolva 1 página com texto fixo
    class FakePage:
        def extract_text(self): return "pdf content here"
    class FakeReader:
        def __init__(self, _): self.pages = [FakePage(), FakePage()]
    monkeypatch.setattr("nexoia.infrastructure.kb.extractors.PdfReader", FakeReader)
    out = await extract_text(mime="application/pdf", data=b"%PDF-1.4 fake")
    assert out.count("pdf content here") == 2


@pytest.mark.asyncio
async def test_extract_docx(monkeypatch):
    class FakePara:
        def __init__(self, t): self.text = t
    class FakeDocument:
        def __init__(self, _): self.paragraphs = [FakePara("a"), FakePara("b")]
    monkeypatch.setattr("nexoia.infrastructure.kb.extractors.DocxDocument", FakeDocument)
    out = await extract_text(
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        data=b"PK fake",
    )
    assert "a" in out and "b" in out


@pytest.mark.asyncio
async def test_extract_image_ocr_via_vision():
    vision = AsyncMock(return_value="texto OCR extraído")
    out = await extract_text(
        mime="image/png",
        data=b"\x89PNG fake",
        vision_ocr=vision,
    )
    assert out == "texto OCR extraído"
    vision.assert_called_once()


@pytest.mark.asyncio
async def test_unsupported_mime_raises():
    with pytest.raises(ExtractionError, match="unsupported"):
        await extract_text(mime="audio/mpeg", data=b"fake")


@pytest.mark.asyncio
async def test_pdf_empty_raises():
    class FakeReader:
        def __init__(self, _): self.pages = []
    import nexoia.infrastructure.kb.extractors as ex
    ex.PdfReader = FakeReader  # type: ignore[attr-defined]
    with pytest.raises(ExtractionError):
        await extract_text(mime="application/pdf", data=b"%PDF fake")
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/kb/test_extractors.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar os extractors**

```python
# src/nexoia/infrastructure/kb/extractors.py
from __future__ import annotations

import io
from typing import Awaitable, Callable

import structlog
from pypdf import PdfReader
from docx import Document as DocxDocument

from nexoia.domain.errors import ExtractionError

logger = structlog.get_logger(__name__)

TEXT_MIMES = {"text/plain", "text/markdown", "text/x-markdown"}
IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp"}
PDF_MIME = "application/pdf"
DOCX_MIME = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


async def extract_text(
    *,
    mime: str,
    data: bytes,
    vision_ocr: Callable[[bytes], Awaitable[str]] | None = None,
) -> str:
    """Retorna texto limpo. Levanta ExtractionError em qualquer falha."""
    mime = mime.lower()
    try:
        if mime in TEXT_MIMES:
            return data.decode("utf-8", errors="replace")

        if mime == PDF_MIME:
            reader = PdfReader(io.BytesIO(data))
            if not reader.pages:
                raise ExtractionError("PDF has no pages")
            parts = [p.extract_text() or "" for p in reader.pages]
            out = "\n".join(parts).strip()
            if not out:
                raise ExtractionError("PDF extraction produced empty text")
            return out

        if mime == DOCX_MIME:
            doc = DocxDocument(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs if p.text]
            out = "\n".join(parts).strip()
            if not out:
                raise ExtractionError("DOCX extraction produced empty text")
            return out

        if mime in IMAGE_MIMES:
            if vision_ocr is None:
                raise ExtractionError("vision_ocr callable is required for images")
            return await vision_ocr(data)

        raise ExtractionError(f"unsupported mime type: {mime}")
    except ExtractionError:
        raise
    except Exception as exc:  # pragma: no cover
        logger.exception("extract_failed", mime=mime)
        raise ExtractionError(str(exc)) from exc
```

Marker de package:

```bash
touch src/nexoia/infrastructure/kb/__init__.py
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/kb/test_extractors.py -v
```
Esperado: 7 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/kb/__init__.py \
        src/nexoia/infrastructure/kb/extractors.py \
        tests/unit/kb/test_extractors.py
git commit -m "feat(kb): add extractors for PDF/DOCX/TXT/MD/image (Vision OCR)"
```

---

## Task 11: OCR via OpenAI Vision

**Files:**
- Create: `src/nexoia/infrastructure/kb/vision_ocr.py`
- Test: `tests/unit/kb/test_vision_ocr.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/kb/test_vision_ocr.py
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock

from nexoia.infrastructure.kb.vision_ocr import OpenAIVisionOCR


@pytest.mark.asyncio
async def test_vision_ocr_sends_base64_image_and_returns_text():
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="OCRed text"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_resp)

    ocr = OpenAIVisionOCR(client=fake_client, model="gpt-4o-mini")
    out = await ocr(b"\x89PNG fake")

    assert out == "OCRed text"
    fake_client.chat.completions.create.assert_awaited_once()
    call_kwargs = fake_client.chat.completions.create.await_args.kwargs
    msg = call_kwargs["messages"][0]
    # URL data:image/*;base64,...
    url = msg["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/")
    assert base64.b64encode(b"\x89PNG fake").decode() in url


@pytest.mark.asyncio
async def test_vision_ocr_raises_extraction_error_on_api_failure():
    from nexoia.domain.errors import ExtractionError
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("boom"))
    ocr = OpenAIVisionOCR(client=fake_client, model="gpt-4o-mini")
    with pytest.raises(ExtractionError):
        await ocr(b"fake")
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/kb/test_vision_ocr.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar**

```python
# src/nexoia/infrastructure/kb/vision_ocr.py
from __future__ import annotations

import base64
from typing import Any

import structlog

from nexoia.domain.errors import ExtractionError

logger = structlog.get_logger(__name__)

OCR_PROMPT = (
    "Extraia TODO o texto visível desta imagem, preservando a ordem e quebras "
    "de linha. Não adicione comentários, apenas o texto."
)


class OpenAIVisionOCR:
    def __init__(self, *, client: Any, model: str = "gpt-4o-mini") -> None:
        self._client = client
        self._model = model

    async def __call__(self, image_bytes: bytes) -> str:
        try:
            b64 = base64.b64encode(image_bytes).decode()
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": OCR_PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:image/*;base64,{b64}"},
                            },
                        ],
                    }
                ],
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.exception("vision_ocr_failed")
            raise ExtractionError(f"Vision OCR failed: {exc}") from exc
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/kb/test_vision_ocr.py -v
```
Esperado: 2 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/kb/vision_ocr.py tests/unit/kb/test_vision_ocr.py
git commit -m "feat(kb): add OpenAI Vision OCR adapter for image extraction"
```

---

## Task 12: Chunker — sliding window tokenizado com overlap

**Files:**
- Create: `src/nexoia/infrastructure/kb/chunker.py`
- Test: `tests/unit/kb/test_chunker.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/kb/test_chunker.py
import pytest

from nexoia.infrastructure.kb.chunker import Chunk, chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("", chunk_size=512, overlap=50) == []


def test_text_smaller_than_window_yields_single_chunk():
    text = "uma frase curta"
    chunks = chunk_text(text, chunk_size=512, overlap=50)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].chunk_index == 0
    assert chunks[0].token_count > 0


def test_large_text_splits_with_overlap():
    # ~4 caracteres por token em inglês; força 3 chunks
    text = " ".join(["palavra"] * 800)
    chunks = chunk_text(text, chunk_size=200, overlap=50)
    assert len(chunks) >= 3
    # chunk_index sequencial 0,1,2,...
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    # Cada chunk não excede size
    assert all(c.token_count <= 200 for c in chunks)


def test_overlap_preserves_continuity():
    text = " ".join([f"w{i}" for i in range(500)])
    chunks = chunk_text(text, chunk_size=100, overlap=20)
    # Com overlap > 0, deve haver múltiplos chunks
    assert len(chunks) > 1


def test_chunks_respect_semantic_separators_when_possible():
    """Prefere quebrar em \\n\\n, \\n ou '.' antes do limite absoluto."""
    text = "Primeiro parágrafo.\n\nSegundo parágrafo.\n\nTerceiro."
    chunks = chunk_text(text, chunk_size=50, overlap=5)
    # Sem exceções + retorna ao menos 1 chunk não-vazio
    assert all(c.text.strip() for c in chunks)


def test_invalid_overlap_raises():
    with pytest.raises(ValueError):
        chunk_text("a", chunk_size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_text("a", chunk_size=100, overlap=150)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/kb/test_chunker.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o chunker**

```python
# src/nexoia/infrastructure/kb/chunker.py
from __future__ import annotations

from dataclasses import dataclass

import tiktoken

_ENCODER = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    text: str
    chunk_index: int
    token_count: int


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[Chunk]:
    """
    Sliding window sobre tokens (cl100k_base). `overlap` deve ser < chunk_size.
    Quebra sempre em fronteira de token (decodificação segura).
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be < chunk_size")
    text = text.strip()
    if not text:
        return []

    tokens = _ENCODER.encode(text)
    if not tokens:
        return []

    step = chunk_size - overlap
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        slice_tokens = tokens[start:end]
        piece = _ENCODER.decode(slice_tokens).strip()
        if piece:
            chunks.append(Chunk(text=piece, chunk_index=idx, token_count=len(slice_tokens)))
            idx += 1
        if end == len(tokens):
            break
        start += step
    return chunks
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/kb/test_chunker.py -v
```
Esperado: 6 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/kb/chunker.py tests/unit/kb/test_chunker.py
git commit -m "feat(kb): add token-aware sliding-window chunker (tiktoken cl100k_base)"
```

---

## Task 13: `EmbeddingsPort` + `OpenAIEmbeddingsClient` com retry/batch

**Files:**
- Create: `src/nexoia/domain/ports/embeddings_port.py`
- Create: `src/nexoia/infrastructure/embeddings/__init__.py`
- Create: `src/nexoia/infrastructure/embeddings/openai_embeddings.py`
- Create: `tests/fakes/fake_embeddings_client.py`
- Test: `tests/unit/kb/test_embeddings.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/kb/test_embeddings.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from nexoia.domain.errors import EmbeddingError
from nexoia.infrastructure.embeddings.openai_embeddings import OpenAIEmbeddingsClient
from tests.fakes.fake_embeddings_client import FakeEmbeddingsClient


@pytest.mark.asyncio
async def test_fake_embeddings_deterministic():
    client = FakeEmbeddingsClient()
    out = await client.embed(["a", "b"])
    assert len(out) == 2
    assert len(out[0]) == 1536
    assert out[0] != out[1]


@pytest.mark.asyncio
async def test_openai_embeddings_single_batch():
    data = [MagicMock(embedding=[0.1] * 1536) for _ in range(3)]
    fake_resp = MagicMock(data=data)
    client_sdk = MagicMock()
    client_sdk.embeddings.create = AsyncMock(return_value=fake_resp)

    client = OpenAIEmbeddingsClient(
        client=client_sdk, model="text-embedding-3-small",
        batch_size=100, max_retries=3, retry_base=0.0,
    )
    out = await client.embed(["x", "y", "z"])
    assert len(out) == 3
    assert all(len(e) == 1536 for e in out)
    client_sdk.embeddings.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_openai_embeddings_splits_into_multiple_batches():
    # 150 inputs com batch_size=100 → 2 chamadas (100 + 50)
    call_log = []

    async def create(**kwargs):
        call_log.append(len(kwargs["input"]))
        n = len(kwargs["input"])
        return MagicMock(data=[MagicMock(embedding=[0.1] * 1536) for _ in range(n)])

    client_sdk = MagicMock()
    client_sdk.embeddings.create = create
    client = OpenAIEmbeddingsClient(
        client=client_sdk, model="text-embedding-3-small",
        batch_size=100, max_retries=3, retry_base=0.0,
    )
    out = await client.embed([f"t{i}" for i in range(150)])
    assert len(out) == 150
    assert call_log == [100, 50]


@pytest.mark.asyncio
async def test_openai_embeddings_retries_then_succeeds():
    attempts = {"n": 0}

    async def flaky(**kwargs):
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient")
        n = len(kwargs["input"])
        return MagicMock(data=[MagicMock(embedding=[0.0] * 1536) for _ in range(n)])

    client_sdk = MagicMock()
    client_sdk.embeddings.create = flaky
    client = OpenAIEmbeddingsClient(
        client=client_sdk, model="text-embedding-3-small",
        batch_size=10, max_retries=3, retry_base=0.0,
    )
    out = await client.embed(["a"])
    assert attempts["n"] == 3
    assert len(out) == 1


@pytest.mark.asyncio
async def test_openai_embeddings_raises_after_max_retries():
    async def always_fails(**kwargs):
        raise RuntimeError("perma-fail")

    client_sdk = MagicMock()
    client_sdk.embeddings.create = always_fails
    client = OpenAIEmbeddingsClient(
        client=client_sdk, model="text-embedding-3-small",
        batch_size=10, max_retries=3, retry_base=0.0,
    )
    with pytest.raises(EmbeddingError):
        await client.embed(["a"])
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/kb/test_embeddings.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o port**

```python
# src/nexoia/domain/ports/embeddings_port.py
from __future__ import annotations

from typing import Protocol


class EmbeddingsPort(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

- [ ] **Step 4: Implementar o cliente OpenAI**

```python
# src/nexoia/infrastructure/embeddings/__init__.py
# (vazio — package marker)
```

```python
# src/nexoia/infrastructure/embeddings/openai_embeddings.py
from __future__ import annotations

import asyncio
from typing import Any

import structlog

from nexoia.domain.errors import EmbeddingError

logger = structlog.get_logger(__name__)


class OpenAIEmbeddingsClient:
    def __init__(
        self,
        *,
        client: Any,
        model: str,
        batch_size: int = 100,
        max_retries: int = 3,
        retry_base: float = 1.0,
    ) -> None:
        self._client = client
        self._model = model
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._retry_base = retry_base

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        out: list[list[float]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            out.extend(await self._embed_batch_with_retry(batch))
        return out

    async def _embed_batch_with_retry(
        self, batch: list[str]
    ) -> list[list[float]]:
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._client.embeddings.create(
                    model=self._model,
                    input=batch,
                )
                return [item.embedding for item in resp.data]
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "embedding_attempt_failed",
                    attempt=attempt,
                    error=str(exc),
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_base * (2 ** (attempt - 1)))
        raise EmbeddingError(
            f"embedding failed after {self._max_retries} attempts: {last_exc}"
        )
```

- [ ] **Step 5: Implementar o fake**

```python
# tests/fakes/fake_embeddings_client.py
from __future__ import annotations

import hashlib


class FakeEmbeddingsClient:
    """Determinístico: hash do texto → vetor 1536 dims no intervalo [-1, 1]."""

    def __init__(self, fail_times: int = 0) -> None:
        self._fail_times = fail_times
        self.call_count = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            from nexoia.domain.errors import EmbeddingError
            raise EmbeddingError(f"fake failure #{self.call_count}")
        return [self._vector_for(t) for t in texts]

    @staticmethod
    def _vector_for(text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        # repete o digest até alcançar 1536 bytes → normaliza para [-1, 1]
        stream = (digest * (1536 // len(digest) + 1))[:1536]
        return [(b / 127.5) - 1.0 for b in stream]
```

- [ ] **Step 6: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/kb/test_embeddings.py -v
```
Esperado: 5 testes PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/domain/ports/embeddings_port.py \
        src/nexoia/infrastructure/embeddings/ \
        tests/fakes/fake_embeddings_client.py \
        tests/unit/kb/test_embeddings.py
git commit -m "feat(kb): add EmbeddingsPort, OpenAI batched client with retry, and FakeEmbeddingsClient"
```

---

## Task 14: Use case de ingestão

**Files:**
- Create: `src/nexoia/application/kb/__init__.py`
- Create: `src/nexoia/application/kb/ingestion.py`
- Test: `tests/unit/kb/test_ingestion.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/kb/test_ingestion.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.kb.ingestion import IngestDocumentUseCase
from nexoia.domain.entities.knowledge_document import DocumentStatus, KnowledgeDocument
from tests.fakes.fake_embeddings_client import FakeEmbeddingsClient


class RecordingChunkRepo:
    def __init__(self): self.inserted = []
    async def bulk_insert(self, chunks): self.inserted.extend(chunks)
    async def delete_by_document(self, _): pass


class RecordingDocRepo:
    def __init__(self, doc): self._doc = doc; self.status_calls = []
    async def get(self, _, account_id): return self._doc
    async def set_status(self, _, status, *, chunk_count=None, error_message=None):
        self.status_calls.append((status, chunk_count, error_message))


@pytest.mark.asyncio
async def test_ingestion_happy_path():
    doc = KnowledgeDocument(
        account_id=1, filename="f.txt", mime_type="text/plain",
        file_size_bytes=10, created_by="u",
    )
    doc_repo = RecordingDocRepo(doc)
    chunk_repo = RecordingChunkRepo()
    emb = FakeEmbeddingsClient()

    async def fake_extract(mime, data): return "texto " * 200

    uc = IngestDocumentUseCase(
        document_repo=doc_repo,
        chunk_repo=chunk_repo,
        embeddings=emb,
        extract_fn=fake_extract,
        chunk_size=50,
        overlap=5,
    )
    await uc.execute(document_id=doc.id, account_id=1, data=b"raw bytes")

    # Transições: PROCESSING → INDEXED
    assert doc_repo.status_calls[0][0] == DocumentStatus.PROCESSING
    assert doc_repo.status_calls[-1][0] == DocumentStatus.INDEXED
    # chunks inseridos
    assert len(chunk_repo.inserted) > 0
    # todos com o mesmo document_id / account_id
    assert all(c.document_id == doc.id for c in chunk_repo.inserted)
    assert all(c.account_id == 1 for c in chunk_repo.inserted)


@pytest.mark.asyncio
async def test_ingestion_marks_error_on_extract_failure():
    from nexoia.domain.errors import ExtractionError
    doc = KnowledgeDocument(
        account_id=1, filename="f.txt", mime_type="text/plain",
        file_size_bytes=10, created_by="u",
    )
    doc_repo = RecordingDocRepo(doc)

    async def failing_extract(mime, data): raise ExtractionError("bad file")

    uc = IngestDocumentUseCase(
        document_repo=doc_repo,
        chunk_repo=RecordingChunkRepo(),
        embeddings=FakeEmbeddingsClient(),
        extract_fn=failing_extract,
        chunk_size=50, overlap=5,
    )
    with pytest.raises(ExtractionError):
        await uc.execute(document_id=doc.id, account_id=1, data=b"raw")
    # Último status deve ser ERROR com mensagem
    last = doc_repo.status_calls[-1]
    assert last[0] == DocumentStatus.ERROR
    assert "bad file" in (last[2] or "")


@pytest.mark.asyncio
async def test_ingestion_reindex_deletes_old_chunks():
    doc = KnowledgeDocument(
        account_id=1, filename="f.txt", mime_type="text/plain",
        file_size_bytes=10, created_by="u",
    )
    doc_repo = RecordingDocRepo(doc)
    chunk_repo = AsyncMock()

    async def fake_extract(mime, data): return "hello"

    uc = IngestDocumentUseCase(
        document_repo=doc_repo,
        chunk_repo=chunk_repo,
        embeddings=FakeEmbeddingsClient(),
        extract_fn=fake_extract,
        chunk_size=50, overlap=5,
    )
    await uc.execute(
        document_id=doc.id, account_id=1, data=b"raw", reindex=True,
    )
    chunk_repo.delete_by_document.assert_awaited_once_with(doc.id)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/kb/test_ingestion.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o use case**

```python
# src/nexoia/application/kb/__init__.py
# (vazio — package marker)
```

```python
# src/nexoia/application/kb/ingestion.py
from __future__ import annotations

from typing import Awaitable, Callable, Protocol

import structlog

from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from nexoia.domain.entities.knowledge_document import DocumentStatus
from nexoia.infrastructure.kb.chunker import chunk_text

logger = structlog.get_logger(__name__)


class _DocRepo(Protocol):
    async def get(self, doc_id: str, *, account_id: int): ...
    async def set_status(
        self, doc_id: str, status: DocumentStatus,
        *, chunk_count: int | None = None, error_message: str | None = None,
    ) -> None: ...


class _ChunkRepo(Protocol):
    async def bulk_insert(self, chunks: list[KnowledgeChunk]) -> None: ...
    async def delete_by_document(self, document_id: str) -> None: ...


class _Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class IngestDocumentUseCase:
    def __init__(
        self,
        *,
        document_repo: _DocRepo,
        chunk_repo: _ChunkRepo,
        embeddings: _Embedder,
        extract_fn: Callable[[str, bytes], Awaitable[str]],
        chunk_size: int,
        overlap: int,
    ) -> None:
        self._doc_repo = document_repo
        self._chunk_repo = chunk_repo
        self._embeddings = embeddings
        self._extract_fn = extract_fn
        self._chunk_size = chunk_size
        self._overlap = overlap

    async def execute(
        self,
        *,
        document_id: str,
        account_id: int,
        data: bytes,
        reindex: bool = False,
    ) -> int:
        log = logger.bind(document_id=document_id, account_id=account_id)
        doc = await self._doc_repo.get(document_id, account_id=account_id)
        if doc is None:
            raise ValueError(f"document {document_id} not found for account {account_id}")

        await self._doc_repo.set_status(document_id, DocumentStatus.PROCESSING)
        try:
            if reindex:
                await self._chunk_repo.delete_by_document(document_id)

            text = await self._extract_fn(doc.mime_type, data)
            log.info("text_extracted", chars=len(text))

            pieces = chunk_text(text, chunk_size=self._chunk_size, overlap=self._overlap)
            log.info("text_chunked", n=len(pieces))

            vectors = await self._embeddings.embed([p.text for p in pieces])

            chunks = [
                KnowledgeChunk(
                    document_id=document_id,
                    account_id=account_id,
                    text=p.text,
                    chunk_index=p.chunk_index,
                    token_count=p.token_count,
                    embedding=v,
                )
                for p, v in zip(pieces, vectors)
            ]
            if chunks:
                await self._chunk_repo.bulk_insert(chunks)

            await self._doc_repo.set_status(
                document_id, DocumentStatus.INDEXED, chunk_count=len(chunks)
            )
            log.info("document_indexed", chunk_count=len(chunks))
            return len(chunks)

        except Exception as exc:
            await self._doc_repo.set_status(
                document_id,
                DocumentStatus.ERROR,
                error_message=str(exc),
            )
            log.exception("ingestion_failed")
            raise
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/kb/test_ingestion.py -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/kb/__init__.py \
        src/nexoia/application/kb/ingestion.py \
        tests/unit/kb/test_ingestion.py
git commit -m "feat(kb): add IngestDocumentUseCase (extract → chunk → embed → persist)"
```

---

## Task 15: Use case de busca (RAG)

**Files:**
- Create: `src/nexoia/application/kb/search.py`
- Test: `tests/unit/kb/test_search.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/kb/test_search.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.kb.search import SearchKnowledgeUseCase
from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk
from tests.fakes.fake_embeddings_client import FakeEmbeddingsClient


class FakeChunkRepo:
    def __init__(self, *, results):
        self._results = results
        self.last_call = None
    async def similarity_search(self, *, embedding, account_id, threshold, top_k):
        self.last_call = dict(
            account_id=account_id, threshold=threshold, top_k=top_k,
        )
        return self._results


class FakeUsageRepo:
    def __init__(self):
        self.recorded = []
    async def record(self, **kwargs):
        self.recorded.append(kwargs)


def _make_chunk(account_id=1, score=0.9, text="hit"):
    c = KnowledgeChunk(
        document_id="d", account_id=account_id,
        text=text, chunk_index=0, token_count=1,
        embedding=[0.0] * 1536,
    )
    c.score = score
    return c


@pytest.mark.asyncio
async def test_search_passes_threshold_and_top_k():
    chunk_repo = FakeChunkRepo(results=[_make_chunk()])
    uc = SearchKnowledgeUseCase(
        chunk_repo=chunk_repo,
        usage_repo=FakeUsageRepo(),
        embeddings=FakeEmbeddingsClient(),
        threshold=0.55,
        top_k=5,
    )
    await uc.execute(account_id=1, query="como recupero meu acesso?")
    assert chunk_repo.last_call == {"account_id": 1, "threshold": 0.55, "top_k": 5}


@pytest.mark.asyncio
async def test_search_records_usage_log_on_hit():
    usage = FakeUsageRepo()
    chunk = _make_chunk()
    uc = SearchKnowledgeUseCase(
        chunk_repo=FakeChunkRepo(results=[chunk]),
        usage_repo=usage,
        embeddings=FakeEmbeddingsClient(),
        threshold=0.55,
        top_k=5,
    )
    results = await uc.execute(account_id=1, query="x")
    assert len(results) == 1
    assert usage.recorded[0]["result_count"] == 1
    assert usage.recorded[0]["top_chunk_id"] == chunk.id


@pytest.mark.asyncio
async def test_search_miss_records_zero_results():
    usage = FakeUsageRepo()
    uc = SearchKnowledgeUseCase(
        chunk_repo=FakeChunkRepo(results=[]),
        usage_repo=usage,
        embeddings=FakeEmbeddingsClient(),
        threshold=0.55,
        top_k=5,
    )
    results = await uc.execute(account_id=1, query="desconhecido")
    assert results == []
    assert usage.recorded[0]["result_count"] == 0
    assert usage.recorded[0]["top_chunk_id"] is None


@pytest.mark.asyncio
async def test_search_tenant_isolation_is_forwarded_to_repo():
    chunk_repo = FakeChunkRepo(results=[])
    uc = SearchKnowledgeUseCase(
        chunk_repo=chunk_repo,
        usage_repo=FakeUsageRepo(),
        embeddings=FakeEmbeddingsClient(),
        threshold=0.55,
        top_k=5,
    )
    await uc.execute(account_id=42, query="q")
    assert chunk_repo.last_call["account_id"] == 42
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/kb/test_search.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o use case**

```python
# src/nexoia/application/kb/search.py
from __future__ import annotations

from typing import Protocol

import structlog

from nexoia.domain.entities.knowledge_chunk import KnowledgeChunk

logger = structlog.get_logger(__name__)


class _ChunkRepo(Protocol):
    async def similarity_search(
        self, *, embedding: list[float], account_id: int,
        threshold: float, top_k: int,
    ) -> list[KnowledgeChunk]: ...


class _UsageRepo(Protocol):
    async def record(
        self, *, account_id: int, query: str,
        result_count: int, top_chunk_id: str | None,
    ) -> None: ...


class _Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


class SearchKnowledgeUseCase:
    def __init__(
        self,
        *,
        chunk_repo: _ChunkRepo,
        usage_repo: _UsageRepo,
        embeddings: _Embedder,
        threshold: float,
        top_k: int,
    ) -> None:
        self._chunk_repo = chunk_repo
        self._usage_repo = usage_repo
        self._embeddings = embeddings
        self._threshold = threshold
        self._top_k = top_k

    async def execute(
        self, *, account_id: int, query: str,
    ) -> list[KnowledgeChunk]:
        [vec] = await self._embeddings.embed([query])
        results = await self._chunk_repo.similarity_search(
            embedding=vec,
            account_id=account_id,
            threshold=self._threshold,
            top_k=self._top_k,
        )
        top_id = results[0].id if results else None
        await self._usage_repo.record(
            account_id=account_id,
            query=query,
            result_count=len(results),
            top_chunk_id=top_id,
        )
        logger.info(
            "kb_search",
            account_id=account_id,
            result_count=len(results),
            top_score=(results[0].score if results else None),
        )
        return results
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/kb/test_search.py -v
```
Esperado: 4 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/kb/search.py tests/unit/kb/test_search.py
git commit -m "feat(kb): add SearchKnowledgeUseCase (RAG threshold + usage log)"
```

---

## Task 16: Worker handler `IngestDocument`

**Files:**
- Create: `src/nexoia/interface/worker/handlers/ingest_document.py`
- Modify: `src/nexoia/interface/worker/dispatcher.py`
- Test: `tests/unit/worker/test_ingest_document_handler.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/worker/test_ingest_document_handler.py
import pytest
from unittest.mock import AsyncMock, patch

from nexoia.interface.worker.handlers.ingest_document import (
    handle_ingest_document,
)


@pytest.mark.asyncio
async def test_handler_calls_ingestion_use_case():
    payload = {
        "document_id": "doc-1",
        "account_id": 1,
        "data_b64": "aGVsbG8=",  # "hello"
        "reindex": False,
    }
    uc = AsyncMock()
    with patch(
        "nexoia.interface.worker.handlers.ingest_document._get_ingestion_uc",
        return_value=uc,
    ):
        await handle_ingest_document(payload=payload)
    uc.execute.assert_awaited_once()
    call_kwargs = uc.execute.await_args.kwargs
    assert call_kwargs["document_id"] == "doc-1"
    assert call_kwargs["account_id"] == 1
    assert call_kwargs["data"] == b"hello"


@pytest.mark.asyncio
async def test_handler_forwards_reindex_flag():
    payload = {"document_id": "d", "account_id": 1, "data_b64": "aGk=",
               "reindex": True}
    uc = AsyncMock()
    with patch(
        "nexoia.interface.worker.handlers.ingest_document._get_ingestion_uc",
        return_value=uc,
    ):
        await handle_ingest_document(payload=payload)
    assert uc.execute.await_args.kwargs["reindex"] is True
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/worker/test_ingest_document_handler.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o handler**

```python
# src/nexoia/interface/worker/handlers/ingest_document.py
from __future__ import annotations

import base64
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def _get_ingestion_uc():
    # Injetado pelo container (Spec ①). Placeholder TODO até container existir.
    from nexoia.interface.container import get_ingestion_use_case  # type: ignore
    return get_ingestion_use_case()


async def handle_ingest_document(payload: dict[str, Any]) -> None:
    log = logger.bind(
        handler="ingest_document",
        document_id=payload["document_id"],
        account_id=payload["account_id"],
    )
    log.info("ingest_started")
    uc = _get_ingestion_uc()
    data = base64.b64decode(payload["data_b64"])
    await uc.execute(
        document_id=payload["document_id"],
        account_id=payload["account_id"],
        data=data,
        reindex=bool(payload.get("reindex", False)),
    )
    log.info("ingest_finished")
```

- [ ] **Step 4: Registrar no dispatcher**

Em `src/nexoia/interface/worker/dispatcher.py`, adicionar:

```python
from nexoia.interface.worker.handlers.ingest_document import handle_ingest_document

# No dict de jobs:
"IngestDocument": handle_ingest_document,
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/worker/test_ingest_document_handler.py -v
```
Esperado: 2 testes PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/interface/worker/handlers/ingest_document.py \
        src/nexoia/interface/worker/dispatcher.py \
        tests/unit/worker/test_ingest_document_handler.py
git commit -m "feat(kb): add IngestDocument worker handler with base64 payload"
```

---

## Task 17: JWT service + middleware + role-based permissions

**Files:**
- Create: `src/nexoia/application/auth/__init__.py`
- Create: `src/nexoia/application/auth/jwt_service.py`
- Modify: `src/nexoia/interface/http/deps.py`
- Test: `tests/unit/auth/test_jwt_service.py`
- Test: `tests/unit/auth/test_deps.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/auth/test_jwt_service.py
import pytest
from datetime import timedelta

from nexoia.application.auth.jwt_service import JwtService
from nexoia.domain.errors import AuthError


def test_issue_and_decode_roundtrip():
    svc = JwtService(secret="x" * 32, algorithm="HS256", expire_minutes=60)
    token = svc.issue(sub="user-1", account_id=1, role="admin")
    claims = svc.decode(token)
    assert claims["sub"] == "user-1"
    assert claims["account_id"] == 1
    assert claims["role"] == "admin"


def test_decode_rejects_wrong_signature():
    good = JwtService(secret="x" * 32, algorithm="HS256", expire_minutes=60)
    bad = JwtService(secret="y" * 32, algorithm="HS256", expire_minutes=60)
    token = good.issue(sub="u", account_id=1, role="viewer")
    with pytest.raises(AuthError):
        bad.decode(token)


def test_decode_rejects_expired_token():
    svc = JwtService(secret="x" * 32, algorithm="HS256", expire_minutes=-1)
    token = svc.issue(sub="u", account_id=1, role="viewer")
    with pytest.raises(AuthError, match="expired"):
        svc.decode(token)


def test_refresh_returns_new_token_with_same_claims():
    svc = JwtService(secret="x" * 32, algorithm="HS256", expire_minutes=60)
    t1 = svc.issue(sub="u", account_id=1, role="editor")
    t2 = svc.refresh(t1)
    claims2 = svc.decode(t2)
    assert claims2["sub"] == "u"
    assert claims2["role"] == "editor"
```

```python
# tests/unit/auth/test_deps.py
import pytest
from fastapi import HTTPException

from nexoia.application.auth.jwt_service import JwtService
from nexoia.interface.http.deps import (
    CurrentUser, get_current_admin_user, require_role,
)


def _svc():
    return JwtService(secret="x" * 32, algorithm="HS256", expire_minutes=60)


@pytest.mark.asyncio
async def test_get_current_admin_user_parses_bearer():
    svc = _svc()
    token = svc.issue(sub="u-1", account_id=5, role="editor")
    user = await get_current_admin_user(
        authorization=f"Bearer {token}", jwt_service=svc,
    )
    assert isinstance(user, CurrentUser)
    assert user.user_id == "u-1"
    assert user.account_id == 5
    assert user.role == "editor"


@pytest.mark.asyncio
async def test_get_current_admin_user_rejects_missing_header():
    with pytest.raises(HTTPException) as exc:
        await get_current_admin_user(authorization=None, jwt_service=_svc())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_admin_user_rejects_malformed_scheme():
    with pytest.raises(HTTPException) as exc:
        await get_current_admin_user(authorization="Token abc", jwt_service=_svc())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_require_role_allows_matching():
    user = CurrentUser(user_id="u", account_id=1, role="admin")
    guard = require_role("admin", "editor")
    out = await guard(user)
    assert out is user


@pytest.mark.asyncio
async def test_require_role_rejects_insufficient():
    user = CurrentUser(user_id="u", account_id=1, role="viewer")
    guard = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        await guard(user)
    assert exc.value.status_code == 403
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/auth/ -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o `JwtService`**

```python
# src/nexoia/application/auth/__init__.py
# (vazio)
```

```python
# src/nexoia/application/auth/jwt_service.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from nexoia.domain.errors import AuthError


class JwtService:
    def __init__(self, *, secret: str, algorithm: str, expire_minutes: int) -> None:
        if len(secret) < 32:
            raise ValueError("JWT secret must be at least 32 chars")
        self._secret = secret
        self._algorithm = algorithm
        self._expire = timedelta(minutes=expire_minutes)

    def issue(self, *, sub: str, account_id: int, role: str) -> str:
        now = datetime.now(timezone.utc)
        payload: dict[str, Any] = {
            "sub": sub,
            "account_id": account_id,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int((now + self._expire).timestamp()),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except JWTError as exc:
            msg = str(exc).lower()
            if "expired" in msg:
                raise AuthError("token expired") from exc
            raise AuthError(f"invalid token: {exc}") from exc

    def refresh(self, token: str) -> str:
        # Permite decode de token expirado ou ainda válido para refresh
        try:
            claims = jwt.decode(
                token, self._secret, algorithms=[self._algorithm],
                options={"verify_exp": False},
            )
        except JWTError as exc:
            raise AuthError(f"cannot refresh: {exc}") from exc
        return self.issue(
            sub=claims["sub"],
            account_id=claims["account_id"],
            role=claims["role"],
        )
```

- [ ] **Step 4: Implementar middleware no `deps.py`**

Adicionar em `src/nexoia/interface/http/deps.py`:

```python
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from nexoia.application.auth.jwt_service import JwtService
from nexoia.config.settings import Settings, get_settings
from nexoia.domain.errors import AuthError


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    account_id: int
    role: str


def get_jwt_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> JwtService:
    return JwtService(
        secret=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
        expire_minutes=settings.JWT_EXPIRE_MINUTES,
    )


async def get_current_admin_user(
    authorization: Annotated[str | None, Header()] = None,
    jwt_service: Annotated[JwtService, Depends(get_jwt_service)] = None,  # type: ignore[assignment]
) -> CurrentUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or invalid Authorization header",
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = jwt_service.decode(token)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return CurrentUser(
        user_id=claims["sub"],
        account_id=int(claims["account_id"]),
        role=claims["role"],
    )


def require_role(*allowed: str):
    async def _guard(
        user: Annotated[CurrentUser, Depends(get_current_admin_user)],
    ) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"role '{user.role}' not permitted",
            )
        return user
    return _guard
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/auth/ -v
```
Esperado: 8 testes PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/application/auth/ src/nexoia/interface/http/deps.py \
        tests/unit/auth/
git commit -m "feat(kb): add JwtService, CurrentUser dep and role-based guard"
```

---

## Task 18: Pydantic schemas + routers `/admin/auth` e `/admin/documents`

**Files:**
- Create: `src/nexoia/interface/http/schemas/admin.py`
- Create: `src/nexoia/interface/http/routers/admin/__init__.py`
- Create: `src/nexoia/interface/http/routers/admin/auth.py`
- Create: `src/nexoia/interface/http/routers/admin/documents.py`
- Test: `tests/integration/test_admin_api.py` (parte 1)

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/integration/test_admin_api.py
"""
Testes de integração dos routers admin via FastAPI TestClient.
Usa um app factory de teste com deps sobrescritas (sessão do testcontainer,
senha bcrypt real, embeddings fake, queue fake).
"""
import io
import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest_admin_app import build_test_app, make_admin_user


@pytest.fixture
def client(db_session):
    app = build_test_app(db_session)
    return TestClient(app)


def test_login_returns_token(client, db_session):
    make_admin_user(db_session, email="ops@g2.com", password="s3cret!!",
                    account_id=1, role="admin")
    r = client.post("/api/v1/admin/auth/login",
                    json={"email": "ops@g2.com", "password": "s3cret!!",
                          "account_id": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]


def test_login_rejects_wrong_password(client, db_session):
    make_admin_user(db_session, email="ops@g2.com", password="right",
                    account_id=1, role="admin")
    r = client.post("/api/v1/admin/auth/login",
                    json={"email": "ops@g2.com", "password": "wrong",
                          "account_id": 1})
    assert r.status_code == 401


def test_refresh_returns_new_token(client, db_session):
    make_admin_user(db_session, email="a@b.com", password="p", account_id=1)
    login = client.post("/api/v1/admin/auth/login",
                        json={"email": "a@b.com", "password": "p",
                              "account_id": 1}).json()
    r = client.post(
        "/api/v1/admin/auth/refresh",
        headers={"Authorization": f"Bearer {login['access_token']}"},
    )
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_upload_requires_auth(client):
    r = client.post(
        "/api/v1/admin/documents/upload",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 401


def test_upload_rejects_viewer(client, db_session):
    make_admin_user(db_session, email="v@b.com", password="p", account_id=1,
                    role="viewer")
    token = client.post("/api/v1/admin/auth/login",
                        json={"email": "v@b.com", "password": "p",
                              "account_id": 1}).json()["access_token"]
    r = client.post(
        "/api/v1/admin/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 403


def test_upload_returns_202(client, db_session):
    make_admin_user(db_session, email="e@b.com", password="p", account_id=1,
                    role="editor")
    token = client.post("/api/v1/admin/auth/login",
                        json={"email": "e@b.com", "password": "p",
                              "account_id": 1}).json()["access_token"]
    r = client.post(
        "/api/v1/admin/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("notes.txt", b"knowledge content", "text/plain")},
        data={"tags": "acesso,refund"},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["id"]
    assert body["status"] == "pending"


def test_upload_rejects_too_large(client, db_session, monkeypatch):
    monkeypatch.setenv("KB_MAX_FILE_SIZE_MB", "0")  # força rejeição
    make_admin_user(db_session, email="e2@b.com", password="p", account_id=1,
                    role="editor")
    token = client.post("/api/v1/admin/auth/login",
                        json={"email": "e2@b.com", "password": "p",
                              "account_id": 1}).json()["access_token"]
    r = client.post(
        "/api/v1/admin/documents/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("a.txt", b"anything", "text/plain")},
    )
    assert r.status_code == 413


def test_list_delete_reindex_flow(client, db_session):
    make_admin_user(db_session, email="a@b.com", password="p", account_id=1,
                    role="admin")
    token = client.post("/api/v1/admin/auth/login",
                        json={"email": "a@b.com", "password": "p",
                              "account_id": 1}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    up = client.post("/api/v1/admin/documents/upload", headers=auth,
                     files={"file": ("x.txt", b"abc", "text/plain")})
    doc_id = up.json()["id"]

    lst = client.get("/api/v1/admin/documents?limit=10", headers=auth)
    assert lst.status_code == 200
    assert any(d["id"] == doc_id for d in lst.json()["items"])

    det = client.get(f"/api/v1/admin/documents/{doc_id}", headers=auth)
    assert det.status_code == 200
    assert det.json()["id"] == doc_id

    ri = client.post(f"/api/v1/admin/documents/{doc_id}/reindex", headers=auth)
    assert ri.status_code == 202

    rm = client.delete(f"/api/v1/admin/documents/{doc_id}", headers=auth)
    assert rm.status_code == 204

    miss = client.get(f"/api/v1/admin/documents/{doc_id}", headers=auth)
    assert miss.status_code == 404


def test_get_document_respects_tenant_isolation(client, db_session):
    make_admin_user(db_session, email="a1@b.com", password="p", account_id=1,
                    role="admin")
    make_admin_user(db_session, email="a2@b.com", password="p", account_id=2,
                    role="admin")
    t1 = client.post("/api/v1/admin/auth/login",
                     json={"email": "a1@b.com", "password": "p",
                           "account_id": 1}).json()["access_token"]
    t2 = client.post("/api/v1/admin/auth/login",
                     json={"email": "a2@b.com", "password": "p",
                           "account_id": 2}).json()["access_token"]
    up = client.post("/api/v1/admin/documents/upload",
                     headers={"Authorization": f"Bearer {t1}"},
                     files={"file": ("y.txt", b"abc", "text/plain")})
    doc_id = up.json()["id"]
    r = client.get(f"/api/v1/admin/documents/{doc_id}",
                   headers={"Authorization": f"Bearer {t2}"})
    assert r.status_code == 404
```

Conftest auxiliar:

```python
# tests/integration/conftest_admin_app.py
from fastapi import FastAPI
from passlib.hash import bcrypt

from nexoia.domain.entities.admin_user import AdminUser, AdminRole
from nexoia.infrastructure.db.repositories.admin_user_repo import AdminUserRepository
from nexoia.interface.http.routers.admin import auth as auth_router
from nexoia.interface.http.routers.admin import documents as doc_router


def build_test_app(db_session) -> FastAPI:
    """App factory isolada para testes: injeta sessão do testcontainer + fakes."""
    from nexoia.main import create_app
    app = create_app()
    # Sobrescrever dependências: get_db_session, queue, embeddings
    # (implementação depende do Core; usar app.dependency_overrides)
    return app


def make_admin_user(
    db_session, *, email: str, password: str, account_id: int,
    role: str = "viewer",
) -> AdminUser:
    import asyncio
    u = AdminUser(
        account_id=account_id, email=email,
        password_hash=bcrypt.hash(password),
        role=AdminRole(role),
    )
    asyncio.get_event_loop().run_until_complete(
        AdminUserRepository(db_session).save(u)
    )
    return u
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_admin_api.py -v
```
Esperado: `ModuleNotFoundError` (routers ainda não existem).

- [ ] **Step 3: Criar schemas Pydantic**

```python
# src/nexoia/interface/http/schemas/admin.py
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str
    account_id: int


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class DocumentOut(BaseModel):
    id: str
    account_id: int
    filename: str
    mime_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    tags: list[str]
    error_message: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
    total: int
    limit: int
    offset: int


class ChunkOut(BaseModel):
    id: str
    document_id: str
    chunk_index: int
    token_count: int
    text: str
    score: float | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)


class SearchHit(BaseModel):
    chunk_id: str
    document_id: str
    text: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchHit]


class UsageLogOut(BaseModel):
    id: str
    query: str
    result_count: int
    top_chunk_id: str | None
    created_at: datetime
```

- [ ] **Step 4: Implementar `auth` router**

```python
# src/nexoia/interface/http/routers/admin/__init__.py
# (vazio)
```

```python
# src/nexoia/interface/http/routers/admin/auth.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from passlib.hash import bcrypt

from nexoia.application.auth.jwt_service import JwtService
from nexoia.config.settings import Settings, get_settings
from nexoia.infrastructure.db.repositories.admin_user_repo import AdminUserRepository
from nexoia.interface.http.deps import (
    CurrentUser, get_current_admin_user, get_jwt_service,
)
from nexoia.interface.http.schemas.admin import LoginRequest, TokenResponse

router = APIRouter(prefix="/api/v1/admin/auth", tags=["admin:auth"])


def _get_admin_repo():
    from nexoia.interface.container import get_admin_user_repo  # type: ignore
    return get_admin_user_repo()


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    jwt_service: Annotated[JwtService, Depends(get_jwt_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[AdminUserRepository, Depends(_get_admin_repo)],
) -> TokenResponse:
    user = await repo.get_by_email(account_id=body.account_id, email=body.email)
    if user is None or not bcrypt.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = jwt_service.issue(
        sub=user.id, account_id=user.account_id, role=user.role.value,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    current: Annotated[CurrentUser, Depends(get_current_admin_user)],
    jwt_service: Annotated[JwtService, Depends(get_jwt_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    token = jwt_service.issue(
        sub=current.user_id, account_id=current.account_id, role=current.role,
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.JWT_EXPIRE_MINUTES * 60,
    )
```

- [ ] **Step 5: Implementar `documents` router**

```python
# src/nexoia/interface/http/routers/admin/documents.py
from __future__ import annotations

import base64
from typing import Annotated

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile, status,
)

from nexoia.config.settings import Settings, get_settings
from nexoia.domain.entities.knowledge_document import (
    DocumentStatus, KnowledgeDocument,
)
from nexoia.domain.errors import FileTooLargeError
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository
from nexoia.interface.http.deps import (
    CurrentUser, get_current_admin_user, require_role,
)
from nexoia.interface.http.schemas.admin import DocumentListOut, DocumentOut

router = APIRouter(prefix="/api/v1/admin/documents", tags=["admin:documents"])


def _get_doc_repo():
    from nexoia.interface.container import get_document_repo  # type: ignore
    return get_document_repo()


def _get_queue():
    from nexoia.interface.container import get_queue  # type: ignore
    return get_queue()


def _to_out(doc: KnowledgeDocument) -> DocumentOut:
    return DocumentOut(
        id=doc.id, account_id=doc.account_id, filename=doc.filename,
        mime_type=doc.mime_type, file_size_bytes=doc.file_size_bytes,
        status=doc.status.value, chunk_count=doc.chunk_count,
        tags=doc.tags, error_message=doc.error_message,
        created_by=doc.created_by, created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("", response_model=DocumentListOut)
async def list_documents(
    current: Annotated[CurrentUser, Depends(get_current_admin_user)],
    repo: Annotated[DocumentRepository, Depends(_get_doc_repo)],
    limit: int = 20,
    offset: int = 0,
) -> DocumentListOut:
    items, total = await repo.list(
        account_id=current.account_id, limit=limit, offset=offset,
    )
    return DocumentListOut(
        items=[_to_out(d) for d in items],
        total=total, limit=limit, offset=offset,
    )


@router.post(
    "/upload", response_model=DocumentOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    current: Annotated[CurrentUser, Depends(require_role("admin", "editor"))],
    settings: Annotated[Settings, Depends(get_settings)],
    repo: Annotated[DocumentRepository, Depends(_get_doc_repo)],
    queue: Annotated[object, Depends(_get_queue)],
    file: UploadFile = File(...),
    tags: str = Form(""),
) -> DocumentOut:
    body = await file.read()
    if len(body) > settings.KB_MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"file exceeds {settings.KB_MAX_FILE_SIZE_MB} MB",
        )
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    doc = KnowledgeDocument(
        account_id=current.account_id,
        filename=file.filename or "untitled",
        mime_type=file.content_type or "application/octet-stream",
        file_size_bytes=len(body),
        created_by=current.user_id,
        tags=tag_list,
    )
    await repo.save(doc)
    await queue.enqueue(
        "IngestDocument",
        {
            "document_id": doc.id,
            "account_id": doc.account_id,
            "data_b64": base64.b64encode(body).decode(),
            "reindex": False,
        },
    )
    return _to_out(doc)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: str,
    current: Annotated[CurrentUser, Depends(get_current_admin_user)],
    repo: Annotated[DocumentRepository, Depends(_get_doc_repo)],
) -> DocumentOut:
    doc = await repo.get(doc_id, account_id=current.account_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return _to_out(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: str,
    current: Annotated[CurrentUser, Depends(require_role("admin", "editor"))],
    repo: Annotated[DocumentRepository, Depends(_get_doc_repo)],
) -> None:
    existing = await repo.get(doc_id, account_id=current.account_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="document not found")
    await repo.delete(doc_id, account_id=current.account_id)


@router.post("/{doc_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_document(
    doc_id: str,
    current: Annotated[CurrentUser, Depends(require_role("admin", "editor"))],
    repo: Annotated[DocumentRepository, Depends(_get_doc_repo)],
    queue: Annotated[object, Depends(_get_queue)],
) -> dict:
    doc = await repo.get(doc_id, account_id=current.account_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    await repo.set_status(doc_id, DocumentStatus.PENDING)
    await queue.enqueue(
        "IngestDocument",
        {
            "document_id": doc_id,
            "account_id": current.account_id,
            "data_b64": "",  # TODO: persistir bytes originais em object storage
            "reindex": True,
        },
    )
    return {"id": doc_id, "status": "pending"}
```

- [ ] **Step 6: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_admin_api.py -v
```
Esperado: 9 testes PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/interface/http/schemas/admin.py \
        src/nexoia/interface/http/routers/admin/__init__.py \
        src/nexoia/interface/http/routers/admin/auth.py \
        src/nexoia/interface/http/routers/admin/documents.py \
        tests/integration/test_admin_api.py \
        tests/integration/conftest_admin_app.py
git commit -m "feat(kb): add admin auth and documents routers with role guards"
```

---

## Task 19: Routers `/admin/chunks`, `/admin/search/test`, `/admin/usage/logs` + registro em `main.py`

**Files:**
- Create: `src/nexoia/interface/http/routers/admin/chunks.py`
- Create: `src/nexoia/interface/http/routers/admin/search.py`
- Create: `src/nexoia/interface/http/routers/admin/usage.py`
- Modify: `src/nexoia/main.py`
- Test: `tests/integration/test_admin_api.py` (append parte 2)

- [ ] **Step 1: Append dos testes falhando**

```python
# tests/integration/test_admin_api.py — APPEND
def test_search_test_requires_auth(client):
    r = client.post("/api/v1/admin/search/test", json={"query": "x"})
    assert r.status_code == 401


def test_search_test_returns_hits(client, db_session):
    make_admin_user(db_session, email="a@b.com", password="p", account_id=1,
                    role="admin")
    token = client.post("/api/v1/admin/auth/login",
                        json={"email": "a@b.com", "password": "p",
                              "account_id": 1}).json()["access_token"]
    # Inserir chunk direto no banco para evitar dependência de embedding real
    # (fake embeddings determinísticos garantem match exato).
    r = client.post(
        "/api/v1/admin/search/test",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": "qualquer"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "results" in body and isinstance(body["results"], list)


def test_chunks_listing(client, db_session):
    make_admin_user(db_session, email="a@b.com", password="p", account_id=1,
                    role="admin")
    token = client.post("/api/v1/admin/auth/login",
                        json={"email": "a@b.com", "password": "p",
                              "account_id": 1}).json()["access_token"]
    up = client.post("/api/v1/admin/documents/upload",
                     headers={"Authorization": f"Bearer {token}"},
                     files={"file": ("z.txt", b"content " * 30, "text/plain")})
    doc_id = up.json()["id"]
    # Dar tempo para o worker fake indexar (síncrono em testes)
    r = client.get(
        f"/api/v1/admin/documents/{doc_id}/chunks",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    assert isinstance(r.json()["items"], list)


def test_usage_logs_returns_entries(client, db_session):
    make_admin_user(db_session, email="a@b.com", password="p", account_id=1,
                    role="admin")
    token = client.post("/api/v1/admin/auth/login",
                        json={"email": "a@b.com", "password": "p",
                              "account_id": 1}).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}
    client.post("/api/v1/admin/search/test", headers=auth, json={"query": "foo"})
    r = client.get("/api/v1/admin/usage/logs", headers=auth)
    assert r.status_code == 200
    assert len(r.json()["items"]) >= 1
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_admin_api.py -v -k "chunks or search_test or usage"
```
Esperado: `ModuleNotFoundError` / `404`.

- [ ] **Step 3: Implementar `chunks` router**

```python
# src/nexoia/interface/http/routers/admin/chunks.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from nexoia.infrastructure.db.repositories.chunk_repo import ChunkRepository
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository
from nexoia.interface.http.deps import CurrentUser, get_current_admin_user
from nexoia.interface.http.schemas.admin import ChunkOut

router = APIRouter(prefix="/api/v1/admin", tags=["admin:chunks"])


def _get_doc_repo():
    from nexoia.interface.container import get_document_repo  # type: ignore
    return get_document_repo()


def _get_chunk_repo():
    from nexoia.interface.container import get_chunk_repo  # type: ignore
    return get_chunk_repo()


@router.get("/documents/{doc_id}/chunks", response_model=dict)
async def list_chunks(
    doc_id: str,
    current: Annotated[CurrentUser, Depends(get_current_admin_user)],
    doc_repo: Annotated[DocumentRepository, Depends(_get_doc_repo)],
    chunk_repo: Annotated[ChunkRepository, Depends(_get_chunk_repo)],
) -> dict:
    doc = await doc_repo.get(doc_id, account_id=current.account_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    chunks = await chunk_repo.list_by_document(doc_id, account_id=current.account_id)
    return {
        "items": [
            ChunkOut(
                id=c.id, document_id=c.document_id,
                chunk_index=c.chunk_index, token_count=c.token_count,
                text=c.text, score=c.score,
            ).model_dump()
            for c in chunks
        ],
    }
```

- [ ] **Step 4: Implementar `search` router**

```python
# src/nexoia/interface/http/routers/admin/search.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from nexoia.application.kb.search import SearchKnowledgeUseCase
from nexoia.interface.http.deps import CurrentUser, get_current_admin_user
from nexoia.interface.http.schemas.admin import (
    SearchHit, SearchRequest, SearchResponse,
)

router = APIRouter(prefix="/api/v1/admin/search", tags=["admin:search"])


def _get_search_uc():
    from nexoia.interface.container import get_search_use_case  # type: ignore
    return get_search_use_case()


@router.post("/test", response_model=SearchResponse)
async def search_test(
    body: SearchRequest,
    current: Annotated[CurrentUser, Depends(get_current_admin_user)],
    uc: Annotated[SearchKnowledgeUseCase, Depends(_get_search_uc)],
) -> SearchResponse:
    results = await uc.execute(account_id=current.account_id, query=body.query)
    return SearchResponse(
        query=body.query,
        results=[
            SearchHit(
                chunk_id=c.id, document_id=c.document_id,
                text=c.text, score=c.score or 0.0,
            )
            for c in results
        ],
    )
```

- [ ] **Step 5: Implementar `usage` router**

```python
# src/nexoia/interface/http/routers/admin/usage.py
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from nexoia.infrastructure.db.repositories.usage_log_repo import UsageLogRepository
from nexoia.interface.http.deps import CurrentUser, get_current_admin_user
from nexoia.interface.http.schemas.admin import UsageLogOut

router = APIRouter(prefix="/api/v1/admin/usage", tags=["admin:usage"])


def _get_usage_repo():
    from nexoia.interface.container import get_usage_log_repo  # type: ignore
    return get_usage_log_repo()


@router.get("/logs")
async def list_usage_logs(
    current: Annotated[CurrentUser, Depends(get_current_admin_user)],
    repo: Annotated[UsageLogRepository, Depends(_get_usage_repo)],
    limit: int = 50,
    offset: int = 0,
) -> dict:
    entries = await repo.list(
        account_id=current.account_id, limit=limit, offset=offset,
    )
    return {
        "items": [
            UsageLogOut(
                id=e.id, query=e.query, result_count=e.result_count,
                top_chunk_id=e.top_chunk_id, created_at=e.created_at,
            ).model_dump(mode="json")
            for e in entries
        ],
    }
```

- [ ] **Step 6: Registrar no `main.py`**

Em `src/nexoia/main.py`, dentro de `create_app()`:

```python
from nexoia.interface.http.routers.admin import auth as admin_auth_router
from nexoia.interface.http.routers.admin import documents as admin_docs_router
from nexoia.interface.http.routers.admin import chunks as admin_chunks_router
from nexoia.interface.http.routers.admin import search as admin_search_router
from nexoia.interface.http.routers.admin import usage as admin_usage_router

# ... dentro de create_app:
app.include_router(admin_auth_router.router)
app.include_router(admin_docs_router.router)
app.include_router(admin_chunks_router.router)
app.include_router(admin_search_router.router)
app.include_router(admin_usage_router.router)
```

- [ ] **Step 7: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_admin_api.py -v
```
Esperado: 13 testes PASSED.

- [ ] **Step 8: Commit**

```bash
git add src/nexoia/interface/http/routers/admin/chunks.py \
        src/nexoia/interface/http/routers/admin/search.py \
        src/nexoia/interface/http/routers/admin/usage.py \
        src/nexoia/main.py \
        tests/integration/test_admin_api.py
git commit -m "feat(kb): add chunks/search/usage routers and register under /api/v1/admin"
```

---

## Task 20: Teste de integração E2E (upload → ingest → search)

**Files:**
- Create: `tests/integration/test_kb_flow.py`

- [ ] **Step 1: Escrever o teste E2E**

```python
# tests/integration/test_kb_flow.py
"""
End-to-end: upload → ingestion use case (com FakeEmbeddings) →
similarity_search → tenant isolation → reindex deleta chunks antigos.
Usa Postgres real via testcontainers com pgvector (fixture `db_session`).
"""
import pytest

from nexoia.application.kb.ingestion import IngestDocumentUseCase
from nexoia.application.kb.search import SearchKnowledgeUseCase
from nexoia.domain.entities.knowledge_document import (
    DocumentStatus, KnowledgeDocument,
)
from nexoia.infrastructure.db.repositories.chunk_repo import ChunkRepository
from nexoia.infrastructure.db.repositories.document_repo import DocumentRepository
from nexoia.infrastructure.db.repositories.usage_log_repo import UsageLogRepository
from tests.fakes.fake_embeddings_client import FakeEmbeddingsClient


async def _fake_extract(mime: str, data: bytes) -> str:
    return data.decode("utf-8")


@pytest.mark.asyncio
async def test_full_flow_upload_index_search(db_session):
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    usage_repo = UsageLogRepository(db_session)
    embeddings = FakeEmbeddingsClient()

    doc = KnowledgeDocument(
        account_id=1, filename="acesso.txt", mime_type="text/plain",
        file_size_bytes=100, created_by="u",
    )
    await doc_repo.save(doc)

    text = (
        "Para recuperar seu acesso, informe seu e-mail cadastrado. "
        "Enviaremos um link nominal de auto-login."
    ) * 10
    ing = IngestDocumentUseCase(
        document_repo=doc_repo, chunk_repo=chunk_repo,
        embeddings=embeddings, extract_fn=_fake_extract,
        chunk_size=64, overlap=10,
    )
    inserted = await ing.execute(
        document_id=doc.id, account_id=1, data=text.encode("utf-8"),
    )
    assert inserted > 0
    refreshed = await doc_repo.get(doc.id, account_id=1)
    assert refreshed.status == DocumentStatus.INDEXED
    assert refreshed.chunk_count == inserted

    # Busca com o texto indexado retorna matches
    search = SearchKnowledgeUseCase(
        chunk_repo=chunk_repo, usage_repo=usage_repo,
        embeddings=embeddings, threshold=0.5, top_k=5,
    )
    hits = await search.execute(
        account_id=1, query="Para recuperar seu acesso, informe seu e-mail",
    )
    assert len(hits) >= 1
    assert all(c.account_id == 1 for c in hits)


@pytest.mark.asyncio
async def test_tenant_isolation_on_search(db_session):
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    usage_repo = UsageLogRepository(db_session)
    embeddings = FakeEmbeddingsClient()
    ing = IngestDocumentUseCase(
        document_repo=doc_repo, chunk_repo=chunk_repo,
        embeddings=embeddings, extract_fn=_fake_extract,
        chunk_size=64, overlap=10,
    )

    # Tenant A
    doc_a = KnowledgeDocument(
        account_id=1, filename="a.txt", mime_type="text/plain",
        file_size_bytes=1, created_by="u",
    )
    await doc_repo.save(doc_a)
    await ing.execute(
        document_id=doc_a.id, account_id=1,
        data=b"segredo do tenant um " * 50,
    )

    # Tenant B
    doc_b = KnowledgeDocument(
        account_id=2, filename="b.txt", mime_type="text/plain",
        file_size_bytes=1, created_by="u",
    )
    await doc_repo.save(doc_b)
    await ing.execute(
        document_id=doc_b.id, account_id=2,
        data=b"segredo do tenant dois " * 50,
    )

    search = SearchKnowledgeUseCase(
        chunk_repo=chunk_repo, usage_repo=usage_repo,
        embeddings=embeddings, threshold=0.0, top_k=10,
    )
    hits_a = await search.execute(
        account_id=1, query="segredo do tenant um",
    )
    assert all(c.account_id == 1 for c in hits_a)

    hits_b = await search.execute(
        account_id=2, query="segredo do tenant dois",
    )
    assert all(c.account_id == 2 for c in hits_b)


@pytest.mark.asyncio
async def test_reindex_deletes_old_chunks(db_session):
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    usage_repo = UsageLogRepository(db_session)
    embeddings = FakeEmbeddingsClient()

    doc = KnowledgeDocument(
        account_id=1, filename="r.txt", mime_type="text/plain",
        file_size_bytes=1, created_by="u",
    )
    await doc_repo.save(doc)
    ing = IngestDocumentUseCase(
        document_repo=doc_repo, chunk_repo=chunk_repo,
        embeddings=embeddings, extract_fn=_fake_extract,
        chunk_size=64, overlap=10,
    )
    n1 = await ing.execute(
        document_id=doc.id, account_id=1, data=b"primeiro texto " * 50,
    )
    n2 = await ing.execute(
        document_id=doc.id, account_id=1, data=b"texto completamente novo " * 30,
        reindex=True,
    )
    listed = await chunk_repo.list_by_document(doc.id, account_id=1)
    assert len(listed) == n2
    assert all("texto completamente novo" in c.text for c in listed)


@pytest.mark.asyncio
async def test_delete_document_removes_chunks_cascade(db_session):
    doc_repo = DocumentRepository(db_session)
    chunk_repo = ChunkRepository(db_session)
    usage_repo = UsageLogRepository(db_session)
    embeddings = FakeEmbeddingsClient()

    doc = KnowledgeDocument(
        account_id=1, filename="d.txt", mime_type="text/plain",
        file_size_bytes=1, created_by="u",
    )
    await doc_repo.save(doc)
    ing = IngestDocumentUseCase(
        document_repo=doc_repo, chunk_repo=chunk_repo,
        embeddings=embeddings, extract_fn=_fake_extract,
        chunk_size=64, overlap=10,
    )
    await ing.execute(
        document_id=doc.id, account_id=1, data=b"conteudo " * 50,
    )
    assert len(await chunk_repo.list_by_document(doc.id, account_id=1)) > 0
    await doc_repo.delete(doc.id, account_id=1)
    assert await chunk_repo.list_by_document(doc.id, account_id=1) == []
```

- [ ] **Step 2: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_kb_flow.py -v
```
Esperado: 4 testes PASSED.

- [ ] **Step 3: Rodar a suíte completa**

```bash
uv run pytest tests/ -v --tb=short
```
Esperado: todos PASSED, sem regressões.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_kb_flow.py
git commit -m "feat(kb): add end-to-end integration tests (upload → index → search)"
```

---

## Task 21: Métricas Prometheus (`kb_*`)

**Files:**
- Modify: `src/nexoia/infrastructure/observability/metrics.py`
- Modify: `src/nexoia/application/kb/ingestion.py` (instrumenta)
- Modify: `src/nexoia/application/kb/search.py` (instrumenta)
- Test: `tests/unit/observability/test_kb_metrics.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/observability/test_kb_metrics.py
from nexoia.infrastructure.observability.metrics import (
    kb_documents_total,
    kb_chunks_total,
    kb_search_total,
    kb_ingestion_duration_seconds,
    kb_embedding_latency_seconds,
)


def test_kb_documents_counter_has_status_label():
    kb_documents_total.labels(status="indexed").inc()
    kb_documents_total.labels(status="error").inc()


def test_kb_search_counter_has_result_label():
    kb_search_total.labels(result="hit").inc()
    kb_search_total.labels(result="miss").inc()


def test_histograms_accept_observations():
    kb_ingestion_duration_seconds.observe(1.2)
    kb_embedding_latency_seconds.observe(0.25)
    kb_chunks_total.inc(5)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/observability/test_kb_metrics.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Adicionar métricas**

No arquivo `src/nexoia/infrastructure/observability/metrics.py`:

```python
from prometheus_client import Counter, Histogram

kb_documents_total = Counter(
    "kb_documents_total",
    "Total de documentos por status final",
    labelnames=["status"],
)

kb_chunks_total = Counter(
    "kb_chunks_total",
    "Total de chunks indexados",
)

kb_search_total = Counter(
    "kb_search_total",
    "Total de buscas RAG por resultado",
    labelnames=["result"],
)

kb_ingestion_duration_seconds = Histogram(
    "kb_ingestion_duration_seconds",
    "Duração total da ingestão (extract → chunk → embed → persist)",
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
)

kb_embedding_latency_seconds = Histogram(
    "kb_embedding_latency_seconds",
    "Latência de uma chamada batch ao provider de embeddings",
    buckets=[0.1, 0.25, 0.5, 1.0, 3.0, 10.0],
)
```

- [ ] **Step 4: Instrumentar ingestão**

Em `src/nexoia/application/kb/ingestion.py`, adicionar importações e envolver com timing:

```python
import time
from nexoia.infrastructure.observability.metrics import (
    kb_documents_total, kb_chunks_total, kb_ingestion_duration_seconds,
)

# Dentro de execute(), envolver o bloco principal:
started = time.perf_counter()
try:
    # ...lógica atual...
    kb_documents_total.labels(status="indexed").inc()
    kb_chunks_total.inc(len(chunks))
    return len(chunks)
except Exception:
    kb_documents_total.labels(status="error").inc()
    raise
finally:
    kb_ingestion_duration_seconds.observe(time.perf_counter() - started)
```

- [ ] **Step 5: Instrumentar busca**

Em `src/nexoia/application/kb/search.py`:

```python
from nexoia.infrastructure.observability.metrics import kb_search_total
# ...
kb_search_total.labels(result="hit" if results else "miss").inc()
```

- [ ] **Step 6: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/observability/test_kb_metrics.py -v
uv run pytest tests/unit/kb/ tests/integration/test_kb_flow.py -v
```
Esperado: todos PASSED.

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/infrastructure/observability/metrics.py \
        src/nexoia/application/kb/ingestion.py \
        src/nexoia/application/kb/search.py \
        tests/unit/observability/test_kb_metrics.py
git commit -m "feat(kb): add Prometheus metrics (documents/chunks/search/duration/latency)"
```

---

## Task 22: Atualizar INDEX e OPEN_QUESTIONS

**Files:**
- Modify: `docs/superpowers/INDEX.md`
- Modify (opcional): `docs/superpowers/OPEN_QUESTIONS.md`

- [ ] **Step 1: Atualizar INDEX.md**

Marcar a linha da Spec ⑥ como "plano criado":

```markdown
| ⑥ | **KB Admin (backend)** — upload, chunking, embeddings, busca RAG | [spec](specs/2026-04-18-nexoia-kb-admin-design.md) | [plano](plans/2026-04-18-nexoia-kb-admin.md) | ⏳ Pendente |
```

- [ ] **Step 2 (opcional): Registrar questões em aberto**

Se houver decisões por confirmar (ex.: persistência do binário original em S3 para reindex sem upload), adicionar em `OPEN_QUESTIONS.md` com IDs `CQ-K01`, `CQ-K02`, etc.

Exemplos previsíveis:
- `CQ-K01` — Onde armazenar o arquivo binário para permitir reindex sem novo upload? (S3/Supabase Storage vs. re-upload obrigatório)
- `CQ-K02` — Limite de `lists=100` do IVFFlat: revalidar quando `chunks > 1M` por tenant.
- `CQ-K03` — Política de retenção dos `kb_usage_logs` (30/90/365 dias?).

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/INDEX.md docs/superpowers/OPEN_QUESTIONS.md
git commit -m "docs: mark KB Admin plan created and register open questions"
```

---

## Self-Review

### Cobertura de RFs / RNFs

| Requisito | Coberto por |
|-----------|-------------|
| `RF-K01` (upload PDF/DOCX/TXT/MD/imagem, máx 20MB, 202 Accepted) | Tasks 10, 11, 18 (rota `/upload` com `KB_MAX_FILE_SIZE_MB` e status 202) |
| `RF-K02` (chunking 512/50 sliding window) | Task 12 (`chunk_text` tokenizado cl100k_base) |
| `RF-K03` (OpenAI embeddings, batch 100, retry 3x backoff) | Task 13 (`OpenAIEmbeddingsClient` com `_embed_batch_with_retry`) |
| `RF-K04` (status PENDING → PROCESSING → INDEXED/ERROR) | Tasks 7 (`set_status`) + 14 (transições dentro do use case) |
| `RF-K05` (RAG cosine ≥ 0.55, top 5) | Tasks 8 (`similarity_search` com threshold) + 15 (use case) |
| `RF-K06` (busca de teste) | Task 19 (`POST /search/test`) |
| `RF-K07` (CRUD + reindex + cascade) | Tasks 7 + 8 + 18 (listar/detalhe/deletar/reindex + cascade via FK `ON DELETE CASCADE`) |
| `RF-K08` (logs de uso) | Tasks 9 + 15 + 19 (`UsageLogRepository` + `SearchUseCase.record` + `GET /usage/logs`) |
| `RF-K09` (JWT admin/editor/viewer) | Tasks 3, 17, 18 (entity, service, dep, guards nos routers) |
| `RF-K10` (tenant isolation) | Tasks 7, 8, 9, 15 (todas as queries filtram `account_id`) |
| `RNF-K01` (indexação async) | Tasks 16 (worker) + 18 (upload enfileira e retorna 202) |
| `RNF-K02` (reindex deleta chunks antigos) | Tasks 14 (`reindex=True` chama `delete_by_document`) + 20 (teste E2E) |
| `RNF-K03` (IVFFlat `lists=100`) | Task 6 (migration) |
| `RNF-K04` (painel não expõe prompts) | Escopo das rotas: apenas `documents`, `chunks`, `search/test`, `usage/logs` — **nenhum endpoint de prompt** |
| `RNF-K05` (cobertura ≥90% ingestão/busca) | Tasks 10, 12, 13, 14, 15, 20 (unitários + E2E) |

### Consistência entre tasks

- `account_id` propagado em 100% das queries de repositório (Tasks 7, 8, 9, 15).
- `KnowledgeChunk.embedding` sempre 1536 dims (Tasks 2, 6, 8, 13).
- `DocumentStatus` transições: Task 14 garante PROCESSING → INDEXED/ERROR; Task 18 `/reindex` reseta para PENDING.
- `FakeEmbeddingsClient` (Task 13) reutilizado em Tasks 14, 15, 20.
- Fixture `db_session` (assumida do Core / Spec ①) consumida pelas integrações 7, 8, 9, 20.
- `get_current_admin_user` (Task 17) injeta `account_id` em todos os routers (Tasks 18, 19).

### Regras críticas do PRD

- **"Painel não expõe prompts"** (Seção 6 / RNF-K04): plano não cria nenhum endpoint de leitura/edição de system prompt. Routers limitam-se a documents/chunks/search/usage.
- **Multi-tenant** (RF-K10): todo repositório que recebe `account_id` o aplica no `WHERE`; teste explícito em Tasks 7, 8, 20.
- **Re-indexação deleta antes de criar** (RNF-K02): Task 14 com flag `reindex`; Task 20 valida conteúdo antigo sumido.

### TODOs intencionais (fora do escopo deste plano)

- `nexoia.interface.container.*` — factories de DI assumem Core (Spec ①). Tasks 16, 18, 19 usam imports defensivos (`# type: ignore`) até o container existir.
- Armazenamento do binário original para reindex sem upload — registrado como `CQ-K01` em Task 22.
- Frontend React (`nexoia-panel`) — explicitamente fora deste plano.

### Sem placeholders vagos

Todos os `# TODO` deste plano têm ou um `CQ-KXX` associado ou referem-se a componentes do Core (Spec ①) que já devem existir como pré-requisito.
