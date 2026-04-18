# Spec ⑥ — KB Admin

**Data:** 2026-04-18
**Fase:** 1
**Repositório alvo:** `nexoia-agent` (backend) + `nexoia-panel` (frontend React — embutido no ChatNexo)
**Depende de:** Spec ① (Core — auth, multi-tenancy, pgvector)
**Status:** Design aprovado — aguardando plano de implementação

---

## 1. Contexto e Objetivo

O KB Admin é o painel que permite à equipe da G2 Educação alimentar a base de conhecimento da IA sem editar prompts ou código. Upload de documentos → chunking → indexação pgvector → busca RAG.

**Regra crítica:** o painel **não expõe prompts**. O operador alimenta conhecimento (documentos, FAQs, políticas). As regras de negócio são código Python — nunca instrução no LLM.

**Resumo do fluxo:**
```
Operador faz upload de documento
  → Backend chunka + gera embeddings (OpenAI)
    → Armazena chunks em PostgreSQL + pgvector
      → Operador pode buscar ("o que a IA responderia para X?")
        → Knowledge Capability usa esses chunks via RAG
```

---

## 2. Escopo

### O que faz (backend — `nexoia-agent`)

- Endpoints FastAPI em `/api/v1/admin/*` protegidos por JWT
- Upload: PDF, DOCX, TXT, MD, imagens (OCR via Vision API)
- Chunking: fragmenta documentos em chunks com overlap configurável
- Embedding: gera vetores via OpenAI `text-embedding-3-small`
- Armazena chunks em `knowledge_chunks` (PostgreSQL + pgvector)
- CRUD: listar, visualizar chunks, deletar, re-indexar documentos
- Status de indexação: PENDING / PROCESSING / INDEXED / ERROR
- Busca de teste: endpoint que simula a query RAG e retorna top-K chunks
- Logs de uso: quais chunks foram consultados, frequência, queries sem resultado
- Multi-tenant: cada `account_id` tem sua própria KB isolada

### O que faz (frontend — `nexoia-panel`)

- Interface React embutida no ChatNexo
- Login/JWT com perfis: `admin`, `editor`, `viewer`
- Upload drag-and-drop ou em lote
- Visualização de chunks com status de indexação
- Campo de busca de teste
- Tela de logs de uso

### O que NÃO faz

- Não expõe prompts do sistema ao operador
- Não altera regras de negócio das capabilities (isso é código)
- Não processa áudio/vídeo (apenas PDF, DOCX, TXT, MD, imagens)

---

## 3. Arquivos

### Novos (backend)
```
src/nexoia/interface/http/routers/admin/
    documents.py        # CRUD de documentos
    chunks.py           # visualização de chunks
    search.py           # busca de teste
    auth.py             # login JWT
src/nexoia/application/kb/
    ingestion.py        # chunking + embedding + persistência
    search.py           # RAG query (usado pela Knowledge Capability)
src/nexoia/domain/entities/
    knowledge_document.py
    knowledge_chunk.py
src/nexoia/infrastructure/
    embeddings/openai_embeddings.py
    db/repositories/
        document_repo.py
        chunk_repo.py
        usage_log_repo.py
migrations/xxxx_add_kb_tables.py
tests/unit/kb/test_ingestion.py
tests/integration/test_kb_flow.py
```

### Modificados
```
src/nexoia/config/settings.py       # + KB_CHUNK_SIZE, KB_CHUNK_OVERLAP, KB_TOP_K, KB_THRESHOLD
src/nexoia/main.py                  # + registra routers admin
```

---

## 4. Endpoints FastAPI

Todos em `/api/v1/admin/` — autenticados por JWT (`Authorization: Bearer <token>`).

### Auth
```
POST   /api/v1/admin/auth/login          → {access_token, expires_in}
POST   /api/v1/admin/auth/refresh        → novo access_token
```

### Documentos
```
GET    /api/v1/admin/documents           → lista documentos do tenant (paginado)
POST   /api/v1/admin/documents/upload    → upload de arquivo → inicia indexação async
GET    /api/v1/admin/documents/{id}      → detalhes + status de indexação + chunks
DELETE /api/v1/admin/documents/{id}      → remove documento e todos os seus chunks
POST   /api/v1/admin/documents/{id}/reindex → re-indexa documento (re-chunking + embedding)
```

### Chunks
```
GET    /api/v1/admin/documents/{id}/chunks → lista chunks com texto + embedding status
```

### Busca de teste
```
POST   /api/v1/admin/search/test         → {query: str} → retorna top-K chunks com score
```

### Logs de uso
```
GET    /api/v1/admin/usage/logs          → queries recentes, chunks usados, queries sem resultado
```

---

## 5. Fluxo de Ingestão

```
Upload (POST /documents/upload)
  │
  ▼
Extração de texto
  ├── PDF   → pypdf
  ├── DOCX  → python-docx
  ├── TXT/MD → leitura direta
  └── Imagem → OpenAI Vision API (OCR)
  │
  ▼
Chunking
  ├── Tamanho: KB_CHUNK_SIZE (padrão 512 tokens)
  ├── Overlap: KB_CHUNK_OVERLAP (padrão 50 tokens)
  └── Estratégia: sliding window com separadores semânticos (\n\n, \n, .)
  │
  ▼
Embedding (OpenAI text-embedding-3-small)
  ├── Batch de até 100 chunks por request
  └── Retry 3x com backoff exponencial
  │
  ▼
Persistência
  ├── knowledge_documents: metadados do arquivo
  └── knowledge_chunks: texto + vetor pgvector
  │
  ▼
Status → INDEXED
```

Processamento assíncrono: upload retorna `202 Accepted` com `document_id`. Worker processa em background. Status consultável via `GET /documents/{id}`.

---

## 6. Fluxo RAG (usado pela Knowledge Capability)

```python
async def search(query: str, account_id: int, top_k: int = 5) -> list[KnowledgeChunk]:
    embedding = await openai.embed(query)
    chunks = await chunk_repo.similarity_search(
        embedding=embedding,
        account_id=account_id,
        threshold=KB_THRESHOLD,    # padrão 0.55 (PRD 7.4)
        top_k=top_k
    )
    return chunks
```

Query pgvector:
```sql
SELECT id, document_id, text, 1 - (embedding <=> $1) AS score
FROM knowledge_chunks
WHERE account_id = $2
  AND 1 - (embedding <=> $1) >= $3
ORDER BY embedding <=> $1
LIMIT $4;
```

---

## 7. Modelo de Dados

### `KnowledgeDocument`

```python
@dataclass
class KnowledgeDocument:
    id: str                       # UUID
    account_id: int
    filename: str
    mime_type: str
    file_size_bytes: int
    status: DocumentStatus        # PENDING/PROCESSING/INDEXED/ERROR
    chunk_count: int
    tags: list[str]               # para organização por categoria
    error_message: str | None
    created_by: str               # user_id do operador
    created_at: datetime
    updated_at: datetime
```

### `KnowledgeChunk`

```python
@dataclass
class KnowledgeChunk:
    id: str                       # UUID
    document_id: str
    account_id: int
    text: str
    chunk_index: int              # ordem no documento
    token_count: int
    embedding: list[float]        # vetor pgvector (1536 dims)
    created_at: datetime
```

### Tabelas

```sql
CREATE TABLE knowledge_documents (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   INTEGER NOT NULL,
    filename     TEXT NOT NULL,
    mime_type    TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    chunk_count  INTEGER NOT NULL DEFAULT 0,
    tags         TEXT[] NOT NULL DEFAULT '{}',
    error_message TEXT,
    created_by   TEXT NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE knowledge_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    account_id   INTEGER NOT NULL,
    text         TEXT NOT NULL,
    chunk_index  INTEGER NOT NULL,
    token_count  INTEGER NOT NULL,
    embedding    vector(1536) NOT NULL,   -- pgvector
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_knowledge_chunks_account_embedding
    ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX idx_knowledge_documents_account ON knowledge_documents(account_id);
CREATE INDEX idx_knowledge_chunks_document ON knowledge_chunks(document_id);

CREATE TABLE kb_usage_logs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   INTEGER NOT NULL,
    query        TEXT NOT NULL,
    result_count INTEGER NOT NULL,
    top_chunk_id UUID,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 8. Autenticação JWT

- `POST /api/v1/admin/auth/login` com `{email, password}` → valida contra tabela `admin_users`
- JWT com `sub=user_id`, `account_id`, `role` (admin/editor/viewer), `exp`
- Middleware `deps.py`: extrai JWT do header `Authorization: Bearer`, valida, injeta `current_user`
- Permissões:
  - `admin`: CRUD completo + logs
  - `editor`: upload + delete + re-index + busca de teste
  - `viewer`: leitura + busca de teste

### Tabela `admin_users`

```sql
CREATE TABLE admin_users (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   INTEGER NOT NULL,
    email        TEXT NOT NULL,
    password_hash TEXT NOT NULL,  -- bcrypt
    role         TEXT NOT NULL DEFAULT 'viewer',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_admin_users_email ON admin_users(account_id, email);
```

---

## 9. Configuração

```python
KB_CHUNK_SIZE: int = 512           # tokens por chunk
KB_CHUNK_OVERLAP: int = 50         # tokens de overlap entre chunks
KB_TOP_K: int = 5                  # chunks retornados por query
KB_THRESHOLD: float = 0.55         # score mínimo de similaridade (PRD 7.4)
KB_EMBEDDING_MODEL: str = "text-embedding-3-small"
KB_MAX_FILE_SIZE_MB: int = 20
JWT_SECRET: str                    # mínimo 32 chars
JWT_EXPIRE_MINUTES: int = 60
```

---

## 10. Observabilidade

### Logs estruturados

- Upload iniciado → `level=INFO`, `document_id`, `filename`, `account_id`
- Chunking concluído → `level=INFO`, `chunk_count`, `document_id`
- Embedding falhou → `level=ERROR`, `attempt`, `document_id`
- Busca RAG → `level=INFO`, `query_hash`, `result_count`, `top_score`
- Query sem resultado → `level=WARNING`, `query_hash`, `account_id`

### Métricas Prometheus

```
kb_documents_total{status="indexed"|"error"}
kb_chunks_total
kb_search_total{result="hit"|"miss"}
kb_ingestion_duration_seconds (histogram)
kb_embedding_latency_seconds (histogram)
```

---

## 11. Testes

### Unitários (`tests/unit/kb/test_ingestion.py`)

| Teste | Cenário |
|-------|---------|
| `test_pdf_chunking` | PDF → chunks com tamanho e overlap corretos |
| `test_docx_extraction` | DOCX → texto extraído corretamente |
| `test_embedding_retry` | Falha OpenAI → retry 3x → sucesso |
| `test_search_above_threshold` | Query → chunks com score ≥ 0.55 retornados |
| `test_search_below_threshold` | Score < 0.55 → não retorna |
| `test_tenant_isolation` | account A não vê chunks do account B |

### Integração (`tests/integration/test_kb_flow.py`)

- Upload → chunking → embedding → busca end-to-end (testcontainers com pgvector)
- Valida tenant isolation na busca
- Valida deleção em cascata (documento deletado → chunks deletados)

---

## 12. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-K01` | Upload: PDF, DOCX, TXT, MD, imagens (OCR). Máx 20MB. Retorna 202 Accepted + document_id. |
| `RF-K02` | Chunking: sliding window com `KB_CHUNK_SIZE=512` tokens e `KB_CHUNK_OVERLAP=50`. |
| `RF-K03` | Embedding: OpenAI `text-embedding-3-small`. Batch de 100 chunks. Retry 3x backoff. |
| `RF-K04` | Status: PENDING → PROCESSING → INDEXED / ERROR. Consultável via GET /documents/{id}. |
| `RF-K05` | Busca RAG: `cosine similarity >= KB_THRESHOLD (0.55)`. Retorna top `KB_TOP_K (5)` chunks. |
| `RF-K06` | Busca de teste: operador simula query e vê chunks que a IA retornaria. |
| `RF-K07` | CRUD: listar, visualizar chunks, deletar (cascade), re-indexar documentos. |
| `RF-K08` | Logs de uso: queries, chunks consultados, queries sem resultado. |
| `RF-K09` | JWT auth multi-tenant. Perfis: admin, editor, viewer. |
| `RF-K10` | Tenant isolation: toda query filtra por `account_id`. |

## 13. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| `RNF-K01` | Indexação assíncrona: upload retorna 202 imediatamente; worker processa em background. |
| `RNF-K02` | Re-indexação: ao re-indexar, deleta chunks antigos antes de criar novos. |
| `RNF-K03` | pgvector IVFFlat index com `lists=100` para performance em buscas. |
| `RNF-K04` | Prompts não expostos: painel mostra apenas documentos e chunks, nunca system prompts. |
| `RNF-K05` | Cobertura de testes: ≥90% nas linhas de ingestão e busca. |
