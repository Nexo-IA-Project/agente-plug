# Webhook Simplification + Bearer Token Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplificar o webhook de mensagens (payload limpo, sem LeadLock, sem mídia), substituir autenticação fixa por Bearer Token gerenciado via banco de dados, e expor endpoints admin para criar/revogar tokens.

**Architecture:** Quatro mudanças independentes em ordem: (1) payload atualizado sem mídia, (2) remoção do LeadLock e código morto, (3) remoção de transcribe_audio do LLM port, (4) Bearer Token auth com tabela `api_tokens` gerenciável via painel. A fila PostgreSQL e o worker assíncrono não são alterados.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, PostgreSQL, Python 3.12, Pydantic v2, pytest-asyncio, hashlib (SHA-256), secrets

---

## Mapa de arquivos

| Arquivo | Ação |
|---|---|
| `src/shared/adapters/chatnexo/schemas.py` | Modificar — novo payload |
| `src/interface/http/routers/webhook_message.py` | Modificar — Bearer Token, refs `message_id` |
| `src/interface/worker/handlers/message.py` | Modificar — remover LeadLock, corrigir campo `phone` |
| `src/shared/adapters/redis/lead_lock.py` | **Deletar** |
| `src/shared/domain/ports/llm.py` | Modificar — remover `transcribe_audio` |
| `src/shared/adapters/llm/openai_client.py` | Modificar — remover `transcribe_audio` + `whisper_model` |
| `src/shared/domain/entities/message.py` | Modificar — remover `media_urls`, `classification_hint` |
| `src/shared/adapters/db/models.py` | Modificar — remover colunas + adicionar `ApiTokenModel` |
| `src/shared/adapters/db/repositories/api_token_repo.py` | **Criar** — CRUD de tokens |
| `src/interface/http/routers/admin/api_tokens.py` | **Criar** — endpoints admin |
| `src/main.py` | Modificar — wiring Bearer Token |
| `migrations/versions/<rev>_clean_messages_add_api_tokens.py` | **Criar** — migration |
| `tests/unit/interface/http/test_webhook_message.py` | Modificar — novo schema + Bearer |
| `tests/unit/worker/test_lead_locking.py` | **Deletar** |
| `tests/unit/interface/http/test_api_tokens_admin.py` | **Criar** — testes do endpoint admin |

---

## Task 1: Atualizar IncomingMessagePayload

**Arquivos:**
- Modify: `src/shared/adapters/chatnexo/schemas.py`
- Modify: `src/interface/http/routers/webhook_message.py` (apenas referências ao campo)
- Modify: `tests/unit/interface/http/test_webhook_message.py`

- [ ] **Step 1: Atualizar o teste existente para refletir o novo schema**

Arquivo: `tests/unit/interface/http/test_webhook_message.py`

```python
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.middleware import CorrelationIdMiddleware
from interface.http.routers import webhook_message


def _make_app(deps, *, token: str = "nxia_test"):
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    webhook_message.configure(
        dedup=deps["dedup"],
        event_repo_factory=lambda: deps["event_repo"],
        queue=deps["queue"],
        token_validator=deps["token_validator"],
    )
    app.include_router(webhook_message.router)
    return app


def _valid_body() -> dict:
    return {
        "account_id": 1,
        "conversation_id": 42,
        "inbox_id": 10,
        "contact_id": 7,
        "contact_phone": "11987654321",
        "message_id": "m-1",
        "text": "preciso de ajuda",
        "occurred_at": "2026-04-17T10:00:00Z",
    }


def test_message_endpoint_enqueues():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
        "token_validator": AsyncMock(return_value=True),
    }
    deps["dedup"].try_mark = AsyncMock(return_value=True)
    deps["event_repo"].insert_if_new = AsyncMock(return_value=object())
    deps["queue"].enqueue = AsyncMock(return_value="j-1")
    client = TestClient(_make_app(deps))

    r = client.post(
        "/webhook/message",
        json=_valid_body(),
        headers={"Authorization": "Bearer nxia_test"},
    )
    assert r.status_code == 202
    deps["queue"].enqueue.assert_awaited_once()


def test_message_endpoint_rejects_invalid_token():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
        "token_validator": AsyncMock(return_value=False),
    }
    client = TestClient(_make_app(deps))
    r = client.post(
        "/webhook/message",
        json=_valid_body(),
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_message_endpoint_rejects_missing_auth():
    deps = {
        "dedup": AsyncMock(),
        "event_repo": AsyncMock(),
        "queue": AsyncMock(),
        "token_validator": AsyncMock(return_value=True),
    }
    client = TestClient(_make_app(deps))
    r = client.post("/webhook/message", json=_valid_body())
    assert r.status_code == 401


def test_payload_rejects_missing_inbox_id():
    from pydantic import ValidationError
    from shared.adapters.chatnexo.schemas import IncomingMessagePayload
    body = _valid_body()
    del body["inbox_id"]
    with pytest.raises(ValidationError):
        IncomingMessagePayload(**body)


def test_payload_has_correct_fields():
    from shared.adapters.chatnexo.schemas import IncomingMessagePayload
    fields = IncomingMessagePayload.model_fields
    assert "inbox_id" in fields
    assert "message_id" in fields
    assert "media_urls" not in fields
    assert "classification_hint" not in fields
    assert "chatnexo_message_id" not in fields
```

Adicionar import em cima:
```python
import pytest
```

- [ ] **Step 2: Rodar testes para confirmar que falham**

```bash
cd apps/api && uv run pytest tests/unit/interface/http/test_webhook_message.py -v
```

Esperado: FAIL com `TypeError` ou `ValidationError` (campos ainda não existem/foram removidos).

- [ ] **Step 3: Atualizar o schema**

Arquivo: `src/shared/adapters/chatnexo/schemas.py`

```python
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IncomingMessagePayload(BaseModel):
    """Payload enviado pelo serviço de processamento para /webhook/message."""

    account_id: int
    conversation_id: int
    inbox_id: int
    contact_id: int
    contact_phone: str
    contact_name: str | None = None
    message_id: str
    text: str
    occurred_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
```

- [ ] **Step 4: Rodar testes e confirmar que passam**

```bash
cd apps/api && uv run pytest tests/unit/interface/http/test_webhook_message.py::test_payload_has_correct_fields tests/unit/interface/http/test_webhook_message.py::test_payload_rejects_missing_inbox_id -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/chatnexo/schemas.py apps/api/tests/unit/interface/http/test_webhook_message.py
git commit -m "feat(webhook): simplify IncomingMessagePayload — add inbox_id, rename to message_id, drop media_urls"
```

---

## Task 2: Remover media_urls e classification_hint da entidade Message e do modelo DB

**Arquivos:**
- Modify: `src/shared/domain/entities/message.py`
- Modify: `src/shared/adapters/db/models.py`

- [ ] **Step 1: Atualizar entidade de domínio**

Arquivo: `src/shared/domain/entities/message.py`

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class MessageDirection(StrEnum):
    IN = "in"
    OUT = "out"


class MessageSource(StrEnum):
    STUDENT = "student"
    AGENT_IA = "agent_ia"
    AGENT_HUMAN = "agent_human"


@dataclass(slots=True)
class Message:
    id: UUID
    conversation_id: UUID
    direction: MessageDirection
    source: MessageSource
    content: str
    correlation_id: str | None = None
    created_at: datetime | None = None
```

- [ ] **Step 2: Atualizar o MessageModel no banco**

No arquivo `src/shared/adapters/db/models.py`, localizar `MessageModel` e remover as colunas `media_urls` e `classification_hint`:

```python
class MessageModel(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = _pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (Index("ix_messages_conv_created", "conversation_id", "created_at"),)
```

- [ ] **Step 3: Verificar que mypy não reclama**

```bash
cd apps/api && uv run mypy src/shared/domain/entities/message.py src/shared/adapters/db/models.py
```

Esperado: sem erros relacionados a `media_urls` ou `classification_hint`.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/domain/entities/message.py apps/api/src/shared/adapters/db/models.py
git commit -m "feat(domain): remove media_urls and classification_hint from Message entity and model"
```

---

## Task 3: Remover transcribe_audio do LLMPort e OpenAIClient

**Arquivos:**
- Modify: `src/shared/domain/ports/llm.py`
- Modify: `src/shared/adapters/llm/openai_client.py`

- [ ] **Step 1: Remover do port**

Arquivo: `src/shared/domain/ports/llm.py`

```python
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LLMPort(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        json_schema: dict[str, Any],
        temperature: float = 0.2,
    ) -> dict[str, Any]: ...

    async def complete_text(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.7,
    ) -> str: ...

    async def embed(self, *, texts: list[str]) -> list[list[float]]: ...
```

- [ ] **Step 2: Remover do adapter OpenAI**

No arquivo `src/shared/adapters/llm/openai_client.py`, remover o campo `whisper_model` do dataclass e o método `transcribe_audio`:

```python
@dataclass
class OpenAIClient:
    client: AsyncOpenAI
    chat_model: str = "gpt-4o-mini"
    embed_model: str = "text-embedding-3-small"

    @classmethod
    def from_settings(cls) -> OpenAIClient:
        return cls(client=AsyncOpenAI(api_key=get_settings().openai_api_key))
```

Deletar completamente o método `transcribe_audio` e remover o campo `whisper_model: str = "whisper-1"`.

- [ ] **Step 3: Verificar que mypy e ruff estão limpos**

```bash
cd apps/api && uv run mypy src/shared/domain/ports/llm.py src/shared/adapters/llm/openai_client.py
cd apps/api && uv run ruff check src/shared/domain/ports/llm.py src/shared/adapters/llm/openai_client.py
```

Esperado: sem erros.

- [ ] **Step 4: Rodar testes unitários para garantir que nada quebrou**

```bash
cd apps/api && uv run pytest tests/unit -v --tb=short -q
```

Esperado: todos passam (nenhum teste deve testar `transcribe_audio` diretamente).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/domain/ports/llm.py apps/api/src/shared/adapters/llm/openai_client.py
git commit -m "feat(llm): remove transcribe_audio from LLMPort and OpenAIClient"
```

---

## Task 4: Remover LeadLock

**Arquivos:**
- Delete: `src/shared/adapters/redis/lead_lock.py`
- Modify: `src/interface/worker/handlers/message.py`
- Delete: `tests/unit/worker/test_lead_locking.py`

- [ ] **Step 1: Deletar arquivo LeadLock**

```bash
rm apps/api/src/shared/adapters/redis/lead_lock.py
rm apps/api/tests/unit/worker/test_lead_locking.py
```

- [ ] **Step 2: Atualizar o handler de mensagens**

Arquivo: `src/interface/worker/handlers/message.py`

Remover o import de `LeadLock`/`LeadLockError`, remover o parâmetro `lead_lock`, corrigir o campo `phone` → `contact_phone`, e simplificar o handler:

```python
from __future__ import annotations

from typing import Any

import structlog
from openai import AsyncOpenAI

from agent.context import AgentContext
from agent.guards import GuardService, LegalMentionGuard, LoopDetectorGuard
from agent.runner import run_agent
from agent.skill_loader import Adapters, build_registry
from shared.adapters.cademi.client import CademiClient
from shared.adapters.chatnexo.client import ChatNexoClient
from shared.adapters.db.repositories.access_case_repo import AccessCaseRepository
from shared.adapters.db.repositories.chunk_repo import ChunkRepository
from shared.adapters.db.repositories.refund_case_repo import RefundCaseRepository
from shared.adapters.db.repositories.usage_log_repo import UsageLogRepository
from shared.adapters.db.session import session_scope
from shared.adapters.hubla.client import HublaClient
from shared.adapters.kb.knowledge_adapter import EmbeddingsKnowledgeAdapter
from shared.adapters.redis.client import get_redis
from shared.adapters.redis.refund_mutex import RedisRefundMutex
from shared.config.settings import get_settings

log = structlog.get_logger(__name__)


class _NullLegalHistory:
    """Stub until a proper DB-backed LegalHistoryPort is implemented."""

    async def has_prior_refund_mention(
        self, *, account_id: int, contact_id: str, purchase_date: Any
    ) -> bool:
        return False


async def handle_message(payload: dict[str, Any]) -> None:
    account_id: str = payload["account_id"]
    phone: str = payload["contact_phone"]
    conversation_id: str = payload["conversation_id"]
    text: str = payload["text"]

    log.info(
        "message_job_started",
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
    )

    await _process_message(
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
        text=text,
    )

    log.info("message_job_done", account_id=account_id, conversation_id=conversation_id)


async def _process_message(
    *,
    account_id: str,
    phone: str,
    conversation_id: str,
    text: str,
) -> None:
    settings = get_settings()
    redis = get_redis()
    openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    chatnexo = ChatNexoClient.from_settings()
    cademi = CademiClient(
        base_url=settings.cademi_api_url,
        api_key=settings.cademi_api_key,
    )
    hubla = HublaClient()
    refund_mutex = RedisRefundMutex(redis, ttl_seconds=settings.refund_mutex_ttl_seconds)

    async with session_scope() as session:
        knowledge_repo = EmbeddingsKnowledgeAdapter(
            chunk_repo=ChunkRepository(session),
            openai_client=openai_client,
            embedding_model=settings.kb_embedding_model,
        )
        adapters = Adapters(
            access_repo=AccessCaseRepository(session),
            cademi=cademi,
            chatnexo=chatnexo,
            refund_repo=RefundCaseRepository(session),
            hubla=hubla,
            legal_history=_NullLegalHistory(),
            refund_mutex=refund_mutex,
            knowledge_repo=knowledge_repo,
            usage_log_repo=UsageLogRepository(session),
        )
        registry = build_registry(adapters)
        guard_service = GuardService([LegalMentionGuard(), LoopDetectorGuard()])

        ctx = AgentContext(
            account_id=account_id,
            phone=phone,
            conversation_id=conversation_id,
            thread_id=f"{account_id}:{phone}",
        )
        reply = await run_agent(
            ctx=ctx,
            user_message=text,
            registry=registry,
            session=session,
            client=openai_client,
            guard_service=guard_service,
        )

    await chatnexo.send_message(
        account_id=UUID(account_id),
        conversation_id=int(conversation_id),
        text=reply,
    )
    log.info("message_reply_sent", account_id=account_id, conversation_id=conversation_id)
```

Adicionar import faltante no topo:
```python
from uuid import UUID
```

- [ ] **Step 3: Verificar que não há mais referências a LeadLock**

```bash
grep -r "lead_lock\|LeadLock\|LeadLockError" apps/api/src/ apps/api/tests/
```

Esperado: nenhuma saída.

- [ ] **Step 4: Rodar testes unitários**

```bash
cd apps/api && uv run pytest tests/unit -v --tb=short -q
```

Esperado: todos passam. O arquivo `test_lead_locking.py` não existe mais.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api/src/shared/adapters/redis/lead_lock.py apps/api/src/interface/worker/handlers/message.py apps/api/tests/unit/worker/test_lead_locking.py
git commit -m "feat(worker): remove LeadLock — messages now process independently without per-lead mutex"
```

---

## Task 5: Criar tabela api_tokens, ApiTokenModel e repositório

**Arquivos:**
- Modify: `src/shared/adapters/db/models.py` (adicionar `ApiTokenModel`)
- Create: `src/shared/adapters/db/repositories/api_token_repo.py`
- Create: `migrations/versions/<rev>_clean_messages_add_api_tokens.py`

- [ ] **Step 1: Adicionar ApiTokenModel em models.py**

No arquivo `src/shared/adapters/db/models.py`, adicionar após os imports existentes de `Boolean` (se não existir, adicionar ao import do sqlalchemy):

```python
# No bloco de imports do sqlalchemy, garantir que Boolean está presente:
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
```

Adicionar a classe no final do arquivo, junto aos outros modelos:

```python
class ApiTokenModel(Base):
    __tablename__ = "api_tokens"
    id: Mapped[uuid.UUID] = _pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
```

- [ ] **Step 2: Criar repositório de tokens**

Arquivo: `src/shared/adapters/db/repositories/api_token_repo.py`

```python
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ApiTokenModel


def generate_token() -> str:
    """Gera token bruto: nxia_<64 hex chars>. Exibir apenas na criação."""
    return "nxia_" + secrets.token_hex(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass
class ApiTokenRepository:
    session: AsyncSession

    async def create(self, *, name: str) -> tuple[ApiTokenModel, str]:
        """Cria token. Retorna (model, token_bruto). token_bruto não é armazenado."""
        raw = generate_token()
        model = ApiTokenModel(
            id=uuid.uuid4(),
            name=name,
            token_hash=hash_token(raw),
        )
        self.session.add(model)
        await self.session.flush()
        return model, raw

    async def validate(self, *, raw_token: str) -> bool:
        """Verifica se o token é válido e ativo. Retorna True se válido."""
        h = hash_token(raw_token)
        result = await self.session.execute(
            select(ApiTokenModel).where(
                ApiTokenModel.token_hash == h,
                ApiTokenModel.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    async def touch(self, *, raw_token: str) -> None:
        """Atualiza last_used_at. Chamar em background após validação."""
        h = hash_token(raw_token)
        await self.session.execute(
            update(ApiTokenModel)
            .where(ApiTokenModel.token_hash == h)
            .values(last_used_at=datetime.now(timezone.utc))
        )

    async def list_all(self) -> list[ApiTokenModel]:
        result = await self.session.execute(
            select(ApiTokenModel).order_by(ApiTokenModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def revoke(self, *, token_id: uuid.UUID) -> bool:
        """Desativa token. Retorna False se não encontrado."""
        result = await self.session.execute(
            select(ApiTokenModel).where(ApiTokenModel.id == token_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        model.is_active = False
        return True
```

- [ ] **Step 3: Criar migration Alembic**

```bash
cd apps/api && uv run alembic revision --autogenerate -m "clean_messages_add_api_tokens"
```

O autogenerate vai detectar as colunas removidas de `messages` e a nova tabela `api_tokens`. Abra o arquivo gerado em `migrations/versions/` e verifique que o `upgrade()` contém:

```python
def upgrade() -> None:
    # api_tokens
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    # messages — remover colunas
    op.drop_column("messages", "media_urls")
    op.drop_column("messages", "classification_hint")


def downgrade() -> None:
    op.add_column("messages", sa.Column("classification_hint", sa.String(50), nullable=True))
    op.add_column("messages", sa.Column("media_urls", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.drop_table("api_tokens")
```

Se o autogenerate não detectar corretamente, edite manualmente para ter exatamente isso.

- [ ] **Step 4: Rodar mypy nos novos arquivos**

```bash
cd apps/api && uv run mypy src/shared/adapters/db/models.py src/shared/adapters/db/repositories/api_token_repo.py
```

Esperado: sem erros.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/models.py apps/api/src/shared/adapters/db/repositories/api_token_repo.py apps/api/migrations/versions/
git commit -m "feat(db): add api_tokens table and ApiTokenRepository; drop media_urls/classification_hint from messages"
```

---

## Task 6: Substituir x-api-key por Bearer Token no webhook

**Arquivos:**
- Modify: `src/interface/http/routers/webhook_message.py`
- Modify: `src/main.py`

- [ ] **Step 1: Escrever testes restantes do webhook (ainda faltam os de 401)**

Os testes já foram escritos na Task 1. Verificar que estão passando:

```bash
cd apps/api && uv run pytest tests/unit/interface/http/test_webhook_message.py -v
```

Esperado: `test_message_endpoint_rejects_invalid_token` e `test_message_endpoint_rejects_missing_auth` ainda falham (FAIL) porque o router ainda usa x-api-key.

- [ ] **Step 2: Atualizar o router webhook_message.py**

Arquivo: `src/interface/http/routers/webhook_message.py`

```python
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException, Request, status

from shared.adapters.chatnexo.schemas import IncomingMessagePayload
from shared.adapters.observability.logger import get_logger
from shared.adapters.observability.metrics import WEBHOOK_RECEIVED
from shared.domain.entities.webhook_event import WebhookSource

router = APIRouter(tags=["webhook"])
log = get_logger(__name__)


@dataclass
class _Config:
    dedup: object | None = None
    event_repo_factory: Callable[[], object] | None = None
    queue: object | None = None
    token_validator: Callable[[str], Awaitable[bool]] | None = None


_cfg = _Config()


def configure(
    *,
    dedup,
    event_repo_factory: Callable[[], object],
    queue,
    token_validator: Callable[[str], Awaitable[bool]],
) -> None:
    _cfg.dedup = dedup
    _cfg.event_repo_factory = event_repo_factory
    _cfg.queue = queue
    _cfg.token_validator = token_validator


async def _verify_bearer_token(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="401").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth.removeprefix("Bearer ").strip()
    if _cfg.token_validator is None or not await _cfg.token_validator(token):
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="401").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/webhook/message",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_verify_bearer_token)],
)
async def receive(
    payload: IncomingMessagePayload,
) -> dict:
    if _cfg.dedup is None or _cfg.event_repo_factory is None or _cfg.queue is None:
        raise RuntimeError("webhook_message router not configured; call configure() before serving")
    first = await _cfg.dedup.try_mark(
        key=f"message:{payload.message_id}", ttl_seconds=3600
    )
    if not first:
        WEBHOOK_RECEIVED.labels(source="chatnexo", status="202-dup").inc()
        return {"accepted": True, "duplicate": True}

    repo = _cfg.event_repo_factory()
    await repo.insert_if_new(
        source=WebhookSource.CHATNEXO,
        external_id=payload.message_id,
        payload=payload.model_dump(),
    )

    job_id = await _cfg.queue.enqueue({"kind": "message", "payload": payload.model_dump()})
    WEBHOOK_RECEIVED.labels(source="chatnexo", status="202").inc()
    log.info(
        "message_webhook_enqueued",
        message_id=payload.message_id,
        job_id=job_id,
    )
    return {"accepted": True, "duplicate": False, "job_id": job_id}
```

- [ ] **Step 3: Atualizar main.py para usar token_validator**

No arquivo `src/main.py`, dentro de `lifespan`:

Substituir o trecho de `webhook_message.configure(...)`:

```python
    # Token validator: consulta o banco a cada requisição
    sessionmaker = get_sessionmaker()

    async def _validate_token(raw_token: str) -> bool:
        from shared.adapters.db.repositories.api_token_repo import ApiTokenRepository
        async with sessionmaker() as session:
            repo = ApiTokenRepository(session)
            return await repo.validate(raw_token=raw_token)

    webhook_message.configure(
        dedup=dedup,
        event_repo_factory=_event_repo_factory,
        queue=queue,
        token_validator=_validate_token,
    )
```

Remover também a linha que passava `expected_api_key=settings.chatnexo_api_key`.

- [ ] **Step 4: Rodar todos os testes do webhook**

```bash
cd apps/api && uv run pytest tests/unit/interface/http/test_webhook_message.py -v
```

Esperado: todos passam.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/interface/http/routers/webhook_message.py apps/api/src/main.py
git commit -m "feat(webhook): replace x-api-key with Bearer Token auth validated against api_tokens table"
```

---

## Task 7: Endpoints admin para gerenciar tokens

**Arquivos:**
- Create: `src/interface/http/routers/admin/api_tokens.py`
- Create: `tests/unit/interface/http/test_api_tokens_admin.py`
- Modify: `src/main.py`

- [ ] **Step 1: Escrever testes do endpoint admin**

Arquivo: `tests/unit/interface/http/test_api_tokens_admin.py`

```python
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from interface.http.routers.admin import api_tokens as tokens_router
from shared.adapters.db.models import ApiTokenModel


def _make_app():
    app = FastAPI()
    app.include_router(tokens_router.router, prefix="/admin")
    return app


def _auth_header() -> dict:
    return {"Authorization": "Bearer valid-jwt"}


def _mock_admin_auth(account_id: int = 1, role: str = "admin"):
    from interface.http.routers.admin.api_tokens import AdminAuth, require_admin_auth
    mock = AsyncMock(return_value=AdminAuth(account_id=account_id, user_email="admin@test.com", user_role=role))
    return mock


def _fake_token_model(name: str = "prod") -> ApiTokenModel:
    m = MagicMock(spec=ApiTokenModel)
    m.id = uuid.uuid4()
    m.name = name
    m.is_active = True
    m.created_at = None
    m.last_used_at = None
    return m


@pytest.mark.asyncio
async def test_create_token_returns_token_value():
    client = TestClient(_make_app())
    with (
        patch("interface.http.routers.admin.api_tokens.require_admin_auth", _mock_admin_auth()),
        patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope,
    ):
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        fake_model = _fake_token_model("prod")
        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.create = AsyncMock(return_value=(fake_model, "nxia_abc123"))
            MockRepo.return_value = repo_instance

            r = client.post("/admin/api-tokens", json={"name": "prod"}, headers=_auth_header())

    assert r.status_code == 201
    data = r.json()
    assert data["token"] == "nxia_abc123"
    assert data["name"] == "prod"


@pytest.mark.asyncio
async def test_list_tokens_masks_value():
    client = TestClient(_make_app())
    with (
        patch("interface.http.routers.admin.api_tokens.require_admin_auth", _mock_admin_auth()),
        patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope,
    ):
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.list_all = AsyncMock(return_value=[_fake_token_model("prod")])
            MockRepo.return_value = repo_instance

            r = client.get("/admin/api-tokens", headers=_auth_header())

    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert "token" not in items[0]
    assert items[0]["name"] == "prod"


@pytest.mark.asyncio
async def test_revoke_token_returns_204():
    client = TestClient(_make_app())
    token_id = str(uuid.uuid4())
    with (
        patch("interface.http.routers.admin.api_tokens.require_admin_auth", _mock_admin_auth()),
        patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope,
    ):
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.revoke = AsyncMock(return_value=True)
            MockRepo.return_value = repo_instance

            r = client.delete(f"/admin/api-tokens/{token_id}", headers=_auth_header())

    assert r.status_code == 204


@pytest.mark.asyncio
async def test_revoke_token_returns_404_if_not_found():
    client = TestClient(_make_app())
    token_id = str(uuid.uuid4())
    with (
        patch("interface.http.routers.admin.api_tokens.require_admin_auth", _mock_admin_auth()),
        patch("interface.http.routers.admin.api_tokens.session_scope") as mock_scope,
    ):
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch("interface.http.routers.admin.api_tokens.ApiTokenRepository") as MockRepo:
            repo_instance = AsyncMock()
            repo_instance.revoke = AsyncMock(return_value=False)
            MockRepo.return_value = repo_instance

            r = client.delete(f"/admin/api-tokens/{token_id}", headers=_auth_header())

    assert r.status_code == 404
```

- [ ] **Step 2: Rodar testes para confirmar que falham**

```bash
cd apps/api && uv run pytest tests/unit/interface/http/test_api_tokens_admin.py -v
```

Esperado: ImportError (módulo não existe ainda).

- [ ] **Step 3: Criar o router de admin tokens**

Arquivo: `src/interface/http/routers/admin/api_tokens.py`

```python
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from pydantic import BaseModel

from shared.adapters.db.repositories.api_token_repo import ApiTokenRepository
from shared.adapters.db.session import session_scope
from shared.adapters.kb.jwt_handler import verify_token
from shared.config.settings import get_settings

router = APIRouter(tags=["admin-api-tokens"])


@dataclass
class AdminAuth:
    account_id: int
    user_email: str
    user_role: str


async def require_admin_auth(
    authorization: str | None = None,
) -> AdminAuth:
    from fastapi import Header
    # FastAPI injeta via Depends — recebemos o header aqui
    settings = get_settings()
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = verify_token(token, secret=settings.jwt_secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return AdminAuth(
        account_id=payload["account_id"],
        user_email=payload["sub"],
        user_role=payload.get("role", "viewer"),
    )


class CreateTokenRequest(BaseModel):
    name: str


class TokenCreatedResponse(BaseModel):
    id: uuid.UUID
    name: str
    token: str
    is_active: bool
    created_at: datetime | None


class TokenListItem(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime | None
    last_used_at: datetime | None


from fastapi import Header as _Header


async def _auth(authorization: str | None = _Header(default=None)) -> AdminAuth:
    return await require_admin_auth(authorization)


@router.post("/api-tokens", response_model=TokenCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_token(
    body: CreateTokenRequest,
    auth: AdminAuth = Depends(_auth),
) -> TokenCreatedResponse:
    async with session_scope() as session:
        repo = ApiTokenRepository(session)
        model, raw_token = await repo.create(name=body.name)
        await session.commit()
    return TokenCreatedResponse(
        id=model.id,
        name=model.name,
        token=raw_token,
        is_active=model.is_active,
        created_at=model.created_at,
    )


@router.get("/api-tokens", response_model=list[TokenListItem])
async def list_tokens(
    auth: AdminAuth = Depends(_auth),
) -> list[TokenListItem]:
    async with session_scope() as session:
        repo = ApiTokenRepository(session)
        tokens = await repo.list_all()
    return [
        TokenListItem(
            id=t.id,
            name=t.name,
            is_active=t.is_active,
            created_at=t.created_at,
            last_used_at=t.last_used_at,
        )
        for t in tokens
    ]


@router.delete("/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_token(
    token_id: uuid.UUID,
    auth: AdminAuth = Depends(_auth),
) -> None:
    async with session_scope() as session:
        repo = ApiTokenRepository(session)
        found = await repo.revoke(token_id=token_id)
        if not found:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="token not found")
        await session.commit()
```

- [ ] **Step 4: Registrar o router em main.py**

No arquivo `src/main.py`, adicionar o import e o `include_router`:

```python
from interface.http.routers.admin import api_tokens as admin_api_tokens
```

E em `create_app()`:

```python
app.include_router(admin_api_tokens.router, prefix="/admin")
```

- [ ] **Step 5: Rodar todos os testes**

```bash
cd apps/api && uv run pytest tests/unit -v --tb=short -q
```

Esperado: todos passam.

- [ ] **Step 6: Verificar linting e tipos**

```bash
cd apps/api && uv run ruff check src/ tests/ && uv run ruff format src/ tests/ && uv run mypy src/
```

Esperado: sem erros críticos. Corrigir qualquer problema de formatação que aparecer.

- [ ] **Step 7: Rodar migration (se ambiente de dev estiver rodando)**

```bash
cd apps/api && uv run alembic upgrade head
```

Esperado: migration aplicada com sucesso.

- [ ] **Step 8: Commit final**

```bash
git add apps/api/src/interface/http/routers/admin/api_tokens.py apps/api/src/main.py apps/api/tests/unit/interface/http/test_api_tokens_admin.py
git commit -m "feat(admin): add Bearer Token management endpoints — create, list, revoke api_tokens"
```

---

## Checklist de verificação final

- [ ] `grep -r "chatnexo_message_id\|media_urls\|classification_hint\|transcribe_audio\|LeadLock\|lead_lock\|x-api-key\|expected_api_key" apps/api/src/` → resultado vazio
- [ ] `uv run pytest tests/unit -q` → todos passam
- [ ] `uv run mypy src/` → sem erros nos arquivos modificados
- [ ] `uv run ruff check src/ tests/` → sem problemas
- [ ] `uv run alembic upgrade head` → migration aplicada
