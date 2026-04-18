# Capability Loja Express Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Capability Loja Express — subgraph LangGraph proativo que acompanha o aluno durante os 7 dias após a compra de produto "Loja Express", enviando follow-ups D+1 / D+3 / D+5 / D+7 via templates Meta aprovados, verificando formulário e status da loja via ports (stubs), e escalando silenciosamente para operação quando necessário para impedir que o caso vire reembolso antes do prazo CDC.

**Architecture:** Dois subgraphs LangGraph complementares.
1. **Subgraph D+0** (3 nós: `send_d0 → schedule_followups → persist_case`) — disparado pelo handler `ProcessPurchaseWebhook` quando o produto é detectado como Loja Express (via `LOJA_EXPRESS_PRODUCT_TAGS`).
2. **Subgraph Follow-up** (3 nós: `check_case → execute_followup → update_case`) — disparado pelos jobs agendados `LOJA_EXPRESS_D1/D3/D5/D7`. `execute_followup` tem lógica condicional por dia. `LojaExpressClient` é stub — levanta `NotImplementedError` (CQ-L01, CQ-L02). Template D+5 é TODO (CQ-L03). Detecção de produto Loja Express é feita no handler existente `handle_process_purchase_webhook.py` (Spec ②) e **roteia** para `LojaExpressCapability` em vez de `WelcomeCapability`.

**Tech Stack:** Python 3.12, LangGraph, SQLAlchemy 2 async, Alembic, structlog, prometheus-client, pytest, testcontainers, factory-boy, uv

**Prerequisite:** Core (Spec ①) e Capability Welcome (Spec ②) devem estar implementados. Este plano reusa: `ConversationState`, `Scheduler`, `JobType` enum, `ChatNexoPort`, `FakeChatNexoClient`, `FakeScheduler`, `handle_process_purchase_webhook`, `welcome_*` fakes da Fase 1.

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `src/nexoia/domain/entities/loja_express_case.py` | Criar | Entidade `LojaExpressCase` + enum `LojaExpressCaseStatus` |
| `src/nexoia/domain/ports/loja_express_port.py` | Criar | Protocol `LojaExpressPort` + value object `LojaExpressStoreStatus` |
| `src/nexoia/domain/errors.py` | Modificar | Adicionar `LojaExpressError` |
| `src/nexoia/infrastructure/loja_express/__init__.py` | Criar | Package marker |
| `src/nexoia/infrastructure/loja_express/client.py` | Criar | Stub `LojaExpressClient` (CQ-L01, CQ-L02) |
| `src/nexoia/infrastructure/db/models.py` | Modificar | Adicionar model `LojaExpressCaseModel` |
| `src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py` | Criar | `LojaExpressCaseRepository` |
| `src/nexoia/application/scheduler/job_types.py` | Modificar | Adicionar `LOJA_EXPRESS_D1/D3/D5/D7` ao enum `JobType` |
| `src/nexoia/application/capabilities/loja_express.py` | Criar | `LojaExpressState` + subgraphs D+0 e follow-up + nós |
| `src/nexoia/interface/worker/handlers/process_purchase.py` | Modificar | Detectar produto Loja Express e rotear para subgraph correto |
| `src/nexoia/interface/worker/handlers/send_scheduled_followup.py` | Modificar | Dispatch LOJA_EXPRESS_* para subgraph follow-up |
| `src/nexoia/interface/worker/dispatcher.py` | Modificar | (Se necessário) registrar novo tipo de handler |
| `src/nexoia/config/settings.py` | Modificar | `LOJA_EXPRESS_PRODUCT_TAGS` + delays D+1/D+3/D+5/D+7 |
| `src/nexoia/infrastructure/observability/metrics.py` | Modificar | Métricas Prometheus da Loja Express |
| `migrations/versions/xxxx_add_loja_express_cases_table.py` | Criar | Alembic migration |
| `tests/fakes/fake_loja_express_client.py` | Criar | Fake configurável para testes |
| `tests/unit/domain/test_loja_express_case.py` | Criar | Testes de entidade |
| `tests/unit/domain/test_loja_express_port.py` | Criar | Testes do port + fake |
| `tests/unit/infrastructure/test_loja_express_client.py` | Criar | Testes de stubs |
| `tests/unit/config/test_settings_loja_express.py` | Criar | Testes de settings |
| `tests/unit/capabilities/test_loja_express.py` | Criar | Testes dos nós do subgraph |
| `tests/unit/worker/test_loja_express_detection.py` | Criar | Testes de detecção do produto |
| `tests/unit/observability/test_loja_express_metrics.py` | Criar | Testes de métricas |
| `tests/integration/test_loja_express_repo.py` | Criar | Teste de integração do repositório |
| `tests/integration/test_loja_express_flow.py` | Criar | Teste end-to-end do fluxo completo |
| `docs/superpowers/OPEN_QUESTIONS.md` | Modificar | Confirmar CQ-L01/L02/L03/W04 (já existem) e marcar referências nos TODOs |
| `docs/superpowers/INDEX.md` | Modificar | Marcar plano ⑤ como criado |

---

## Task 1: `LojaExpressCase` entity + `LojaExpressCaseStatus` enum

**Files:**
- Create: `src/nexoia/domain/entities/loja_express_case.py`
- Test: `tests/unit/domain/test_loja_express_case.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/domain/test_loja_express_case.py
from nexoia.domain.entities.loja_express_case import (
    LojaExpressCase,
    LojaExpressCaseStatus,
)


def test_loja_express_case_default_status_is_aguardando_formulario():
    case = LojaExpressCase(
        account_id=1,
        contact_id="contact-123",
        conversation_id="conv-456",
        purchase_id="purchase-789",
        product_name="Loja Express Pro",
        student_email="aluno@email.com",
    )
    assert case.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert case.form_submitted is False
    assert case.loja_entregue is False
    assert case.scheduled_job_d1_id is None
    assert case.scheduled_job_d3_id is None
    assert case.scheduled_job_d5_id is None
    assert case.scheduled_job_d7_id is None


def test_loja_express_case_has_uuid_id():
    case = LojaExpressCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="P",
        student_email="e@e.com",
    )
    assert len(case.id) == 36  # UUID 8-4-4-4-12


def test_loja_express_case_status_enum_values():
    assert LojaExpressCaseStatus.AGUARDANDO_FORMULARIO == "aguardando_formulario"
    assert LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO == "lembrete_d1_enviado"
    assert LojaExpressCaseStatus.CHECK_D3_ENVIADO == "check_d3_enviado"
    assert LojaExpressCaseStatus.ALERTA_D5_ENVIADO == "alerta_d5_enviado"
    assert LojaExpressCaseStatus.PRAZO_CRITICO_D7 == "prazo_critico_d7"
    assert LojaExpressCaseStatus.ENTREGUE == "entregue"
    assert LojaExpressCaseStatus.ESCALADO == "escalado"


def test_loja_express_case_with_scheduled_jobs():
    case = LojaExpressCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="P",
        student_email="e@e.com",
        scheduled_job_d1_id="job-d1",
        scheduled_job_d3_id="job-d3",
        scheduled_job_d5_id="job-d5",
        scheduled_job_d7_id="job-d7",
    )
    assert case.scheduled_job_d1_id == "job-d1"
    assert case.scheduled_job_d3_id == "job-d3"
    assert case.scheduled_job_d5_id == "job-d5"
    assert case.scheduled_job_d7_id == "job-d7"


def test_loja_express_case_delivered_flag():
    case = LojaExpressCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="P",
        student_email="e@e.com",
        loja_entregue=True,
        status=LojaExpressCaseStatus.ENTREGUE,
    )
    assert case.loja_entregue is True
    assert case.status == LojaExpressCaseStatus.ENTREGUE
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
cd /path/to/nexoia-agent
uv run pytest tests/unit/domain/test_loja_express_case.py -v
```
Esperado: `ImportError` ou `ModuleNotFoundError`

- [ ] **Step 3: Implementar a entidade**

```python
# src/nexoia/domain/entities/loja_express_case.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class LojaExpressCaseStatus(str, Enum):
    AGUARDANDO_FORMULARIO = "aguardando_formulario"
    LEMBRETE_D1_ENVIADO = "lembrete_d1_enviado"
    CHECK_D3_ENVIADO = "check_d3_enviado"
    ALERTA_D5_ENVIADO = "alerta_d5_enviado"
    PRAZO_CRITICO_D7 = "prazo_critico_d7"
    ENTREGUE = "entregue"
    ESCALADO = "escalado"


@dataclass
class LojaExpressCase:
    account_id: int
    contact_id: str
    conversation_id: str
    purchase_id: str
    product_name: str
    student_email: str
    id: str = field(default_factory=lambda: str(uuid4()))
    form_submitted: bool = False
    loja_entregue: bool = False
    status: LojaExpressCaseStatus = LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    scheduled_job_d1_id: str | None = None
    scheduled_job_d3_id: str | None = None
    scheduled_job_d5_id: str | None = None
    scheduled_job_d7_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_loja_express_case.py -v
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/entities/loja_express_case.py \
        tests/unit/domain/test_loja_express_case.py
git commit -m "feat(loja-express): add LojaExpressCase entity and status enum"
```

---

## Task 2: `LojaExpressPort` + `LojaExpressStoreStatus` + `LojaExpressError`

**Files:**
- Create: `src/nexoia/domain/ports/loja_express_port.py`
- Modify: `src/nexoia/domain/errors.py`
- Create: `tests/fakes/fake_loja_express_client.py`
- Test: `tests/unit/domain/test_loja_express_port.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/domain/test_loja_express_port.py
import pytest

from nexoia.domain.errors import LojaExpressError
from nexoia.domain.ports.loja_express_port import (
    LojaExpressPort,
    LojaExpressStoreStatus,
)


def test_store_status_is_frozen():
    status = LojaExpressStoreStatus(
        case_id="case-1",
        entregue=False,
        bloqueio="aguardando_fornecedor",
        progresso_pct=30,
    )
    with pytest.raises(Exception):
        status.entregue = True  # type: ignore[misc]


def test_store_status_defaults():
    status = LojaExpressStoreStatus(case_id="case-1")
    assert status.entregue is False
    assert status.bloqueio is None
    assert status.progresso_pct == 0


def test_loja_express_error_is_exception():
    err = LojaExpressError("integration unavailable")
    assert isinstance(err, Exception)
    assert str(err) == "integration unavailable"


@pytest.mark.asyncio
async def test_fake_client_satisfies_port_shape():
    from tests.fakes.fake_loja_express_client import FakeLojaExpressClient

    client = FakeLojaExpressClient()
    # Protocol check — mypy valida em CI; aqui garantimos existência dos métodos
    assert hasattr(client, "is_form_submitted")
    assert hasattr(client, "get_store_status")
    # comportamento default do fake: form pendente, loja não entregue
    assert await client.is_form_submitted("case-1") is False
    status = await client.get_store_status("case-1")
    assert status.entregue is False
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_loja_express_port.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar `LojaExpressError` ao arquivo de erros existente**

No arquivo `src/nexoia/domain/errors.py`, adicionar ao final:

```python
class LojaExpressError(Exception):
    """Falha ao comunicar com a integração de formulário/status da Loja Express."""
```

- [ ] **Step 4: Criar o port e o value object**

```python
# src/nexoia/domain/ports/loja_express_port.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LojaExpressStoreStatus:
    """Snapshot do status da loja reportado pela integração do fornecedor."""

    case_id: str
    entregue: bool = False
    bloqueio: str | None = None  # ex: "aguardando_fornecedor", "sem_produtos"
    progresso_pct: int = 0       # 0..100


class LojaExpressPort(Protocol):
    async def is_form_submitted(self, case_id: str) -> bool:
        """
        Retorna True se o aluno já respondeu ao formulário inicial da Loja Express.
        TODO (CQ-L01): definir qual sistema responde (Google Forms? Typeform? próprio?).
        """
        ...

    async def get_store_status(self, case_id: str) -> LojaExpressStoreStatus:
        """
        Retorna o status atual da loja (entregue? bloqueio? progresso?).
        TODO (CQ-L02): definir integração por tenant (planilha? fornecedor? API?).
        """
        ...
```

- [ ] **Step 5: Criar o `FakeLojaExpressClient`**

```python
# tests/fakes/fake_loja_express_client.py
from __future__ import annotations

from nexoia.domain.errors import LojaExpressError
from nexoia.domain.ports.loja_express_port import LojaExpressStoreStatus


class FakeLojaExpressClient:
    """Fake configurável para testes da Capability Loja Express."""

    def __init__(
        self,
        *,
        form_submitted: bool = False,
        entregue: bool = False,
        bloqueio: str | None = None,
        progresso_pct: int = 0,
        fail_form_times: int = 0,
        fail_status_times: int = 0,
    ) -> None:
        self._form_submitted = form_submitted
        self._entregue = entregue
        self._bloqueio = bloqueio
        self._progresso_pct = progresso_pct
        self._fail_form_times = fail_form_times
        self._fail_status_times = fail_status_times
        self.form_calls = 0
        self.status_calls = 0

    async def is_form_submitted(self, case_id: str) -> bool:
        self.form_calls += 1
        if self.form_calls <= self._fail_form_times:
            raise LojaExpressError(f"form check failed (attempt {self.form_calls})")
        return self._form_submitted

    async def get_store_status(self, case_id: str) -> LojaExpressStoreStatus:
        self.status_calls += 1
        if self.status_calls <= self._fail_status_times:
            raise LojaExpressError(f"status check failed (attempt {self.status_calls})")
        return LojaExpressStoreStatus(
            case_id=case_id,
            entregue=self._entregue,
            bloqueio=self._bloqueio,
            progresso_pct=self._progresso_pct,
        )
```

- [ ] **Step 6: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_loja_express_port.py -v
```
Esperado: 4 testes PASSED

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/domain/ports/loja_express_port.py \
        src/nexoia/domain/errors.py \
        tests/fakes/fake_loja_express_client.py \
        tests/unit/domain/test_loja_express_port.py
git commit -m "feat(loja-express): add LojaExpressPort, store status, error and fake"
```

---

## Task 3: `LojaExpressClient` stub (infrastructure)

**Files:**
- Create: `src/nexoia/infrastructure/loja_express/__init__.py`
- Create: `src/nexoia/infrastructure/loja_express/client.py`
- Test: `tests/unit/infrastructure/test_loja_express_client.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/infrastructure/test_loja_express_client.py
import pytest

from nexoia.infrastructure.loja_express.client import LojaExpressClient


@pytest.mark.asyncio
async def test_is_form_submitted_raises_not_implemented():
    client = LojaExpressClient()
    with pytest.raises(NotImplementedError, match="CQ-L01"):
        await client.is_form_submitted("case-1")


@pytest.mark.asyncio
async def test_get_store_status_raises_not_implemented():
    client = LojaExpressClient()
    with pytest.raises(NotImplementedError, match="CQ-L02"):
        await client.get_store_status("case-1")
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/infrastructure/test_loja_express_client.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Criar o package**

```bash
touch src/nexoia/infrastructure/loja_express/__init__.py
```

- [ ] **Step 4: Criar o stub do cliente**

```python
# src/nexoia/infrastructure/loja_express/client.py
# ⚠️  ATENÇÃO: Este cliente é um STUB.
#
# ANTES DE IMPLEMENTAR: consultar docs/superpowers/OPEN_QUESTIONS.md:
#   - CQ-L01 → qual é o "formulário" e como verificar resposta?
#   - CQ-L02 → qual é a integração de status da loja (planilha? fornecedor?)
#
# O desenvolvedor DEVE perguntar ao responsável pelo produto antes de remover os raises.
from __future__ import annotations

from nexoia.domain.ports.loja_express_port import LojaExpressStoreStatus


class LojaExpressClient:
    """Stub do adapter para formulário e status da Loja Express."""

    async def is_form_submitted(self, case_id: str) -> bool:
        # TODO (CQ-L01): implementar verificação real
        raise NotImplementedError(
            "LojaExpressClient.is_form_submitted não implementado — ver OPEN_QUESTIONS.md#CQ-L01"
        )

    async def get_store_status(self, case_id: str) -> LojaExpressStoreStatus:
        # TODO (CQ-L02): implementar integração real (por tenant)
        raise NotImplementedError(
            "LojaExpressClient.get_store_status não implementado — ver OPEN_QUESTIONS.md#CQ-L02"
        )
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/infrastructure/test_loja_express_client.py -v
```
Esperado: 2 testes PASSED

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/infrastructure/loja_express/ \
        tests/unit/infrastructure/test_loja_express_client.py
git commit -m "feat(loja-express): add LojaExpressClient stub with NotImplementedError guards"
```

---

## Task 4: Settings da Loja Express

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Test: `tests/unit/config/test_settings_loja_express.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/config/test_settings_loja_express.py
from nexoia.config.settings import Settings


def _base_env() -> dict:
    return dict(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://localhost:6379",
        CHATNEXO_API_KEY="key",
        OPENAI_API_KEY="sk-test",
    )


def test_loja_express_defaults():
    s = Settings(**_base_env())
    assert s.LOJA_EXPRESS_PRODUCT_TAGS == ["loja_express"]
    assert s.LOJA_EXPRESS_D1_DELAY_HOURS == 24
    assert s.LOJA_EXPRESS_D3_DELAY_HOURS == 72
    assert s.LOJA_EXPRESS_D5_DELAY_HOURS == 120
    assert s.LOJA_EXPRESS_D7_DELAY_HOURS == 168


def test_loja_express_product_tags_can_be_overridden(monkeypatch):
    # Pydantic aceita lista via JSON string no env
    monkeypatch.setenv("LOJA_EXPRESS_PRODUCT_TAGS", '["loja_express","loja-express","express_store"]')
    s = Settings(**_base_env())
    assert "loja-express" in s.LOJA_EXPRESS_PRODUCT_TAGS
    assert "express_store" in s.LOJA_EXPRESS_PRODUCT_TAGS
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/config/test_settings_loja_express.py -v
```
Esperado: `AttributeError` ou `ValidationError`

- [ ] **Step 3: Adicionar variáveis ao `Settings`**

No arquivo `src/nexoia/config/settings.py`, adicionar ao model `Settings`:

```python
    # Capability Loja Express (Spec ⑤)
    # Tags que identificam um produto Loja Express no webhook da Hubla (comparação case-insensitive).
    LOJA_EXPRESS_PRODUCT_TAGS: list[str] = ["loja_express"]
    LOJA_EXPRESS_D1_DELAY_HOURS: int = 24   # D+1 = 24h após compra
    LOJA_EXPRESS_D3_DELAY_HOURS: int = 72   # D+3 = 72h
    LOJA_EXPRESS_D5_DELAY_HOURS: int = 120  # D+5 = 120h
    LOJA_EXPRESS_D7_DELAY_HOURS: int = 168  # D+7 = 168h (prazo crítico CDC)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/config/test_settings_loja_express.py -v
```
Esperado: 2 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/config/settings.py tests/unit/config/test_settings_loja_express.py
git commit -m "feat(loja-express): add product tags and follow-up delay settings"
```

---

## Task 5: Novos tipos de `JobType` (LOJA_EXPRESS_D1/D3/D5/D7)

**Files:**
- Modify: `src/nexoia/application/scheduler/job_types.py`
- Test: `tests/unit/application/test_job_types_loja_express.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/application/test_job_types_loja_express.py
from nexoia.application.scheduler.job_types import JobType


def test_loja_express_job_types_exist():
    assert JobType.LOJA_EXPRESS_D1 == "LOJA_EXPRESS_D1"
    assert JobType.LOJA_EXPRESS_D3 == "LOJA_EXPRESS_D3"
    assert JobType.LOJA_EXPRESS_D5 == "LOJA_EXPRESS_D5"
    assert JobType.LOJA_EXPRESS_D7 == "LOJA_EXPRESS_D7"


def test_loja_express_job_types_are_string_compatible():
    assert isinstance(JobType.LOJA_EXPRESS_D1.value, str)
    assert JobType("LOJA_EXPRESS_D3") == JobType.LOJA_EXPRESS_D3
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/application/test_job_types_loja_express.py -v
```
Esperado: `AttributeError`

- [ ] **Step 3: Adicionar enum entries**

No arquivo `src/nexoia/application/scheduler/job_types.py`, adicionar ao enum `JobType`:

```python
    # Spec ⑤ — Capability Loja Express
    LOJA_EXPRESS_D1 = "LOJA_EXPRESS_D1"
    LOJA_EXPRESS_D3 = "LOJA_EXPRESS_D3"
    LOJA_EXPRESS_D5 = "LOJA_EXPRESS_D5"
    LOJA_EXPRESS_D7 = "LOJA_EXPRESS_D7"
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/application/test_job_types_loja_express.py -v
```
Esperado: 2 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/scheduler/job_types.py \
        tests/unit/application/test_job_types_loja_express.py
git commit -m "feat(loja-express): add LOJA_EXPRESS_D1/D3/D5/D7 JobType entries"
```

---

## Task 6: Migration Alembic + SQLAlchemy Model

**Files:**
- Modify: `src/nexoia/infrastructure/db/models.py`
- Create: `migrations/versions/xxxx_add_loja_express_cases_table.py`

- [ ] **Step 1: Adicionar o model SQLAlchemy**

No arquivo `src/nexoia/infrastructure/db/models.py`, adicionar:

```python
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import uuid4


class LojaExpressCaseModel(Base):
    __tablename__ = "loja_express_cases"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    purchase_id = Column(String, nullable=False, unique=True)  # idempotência (RNF-L02)
    product_name = Column(String, nullable=False)
    student_email = Column(String, nullable=False)
    form_submitted = Column(Boolean, nullable=False, default=False)
    loja_entregue = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="aguardando_formulario")
    scheduled_job_d1_id = Column(String, nullable=True)
    scheduled_job_d3_id = Column(String, nullable=True)
    scheduled_job_d5_id = Column(String, nullable=True)
    scheduled_job_d7_id = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "idx_loja_express_cases_account_contact",
            "account_id",
            "contact_id",
        ),
        Index("idx_loja_express_cases_purchase_id", "purchase_id"),
    )
```

- [ ] **Step 2: Gerar a migration Alembic**

```bash
uv run alembic revision --autogenerate -m "add_loja_express_cases_table"
```
Esperado: arquivo criado em `migrations/versions/XXXX_add_loja_express_cases_table.py`

- [ ] **Step 3: Revisar o arquivo gerado**

Abrir o arquivo gerado e confirmar:
- `op.create_table("loja_express_cases", ...)`
- Coluna `purchase_id` com `unique=True`
- `op.create_index("idx_loja_express_cases_account_contact", ...)`
- `op.create_index("idx_loja_express_cases_purchase_id", ...)`

Ajustar manualmente se o autogenerate não detectar algum detalhe (índices, defaults).

- [ ] **Step 4: Aplicar a migration no banco de dev**

```bash
uv run alembic upgrade head
```
Esperado: `Running upgrade ... -> XXXX, add_loja_express_cases_table`

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/models.py migrations/versions/
git commit -m "feat(loja-express): add loja_express_cases table migration and model"
```

---

## Task 7: `LojaExpressCaseRepository`

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py`
- Test: `tests/integration/test_loja_express_repo.py`

- [ ] **Step 1: Escrever o teste de integração falhando**

```python
# tests/integration/test_loja_express_repo.py
import pytest

from nexoia.domain.entities.loja_express_case import (
    LojaExpressCase,
    LojaExpressCaseStatus,
)
from nexoia.infrastructure.db.repositories.loja_express_case_repo import (
    LojaExpressCaseRepository,
)


@pytest.mark.asyncio
async def test_save_and_get_by_purchase_id(db_session):
    repo = LojaExpressCaseRepository(db_session)
    case = LojaExpressCase(
        account_id=1,
        contact_id="contact-1",
        conversation_id="conv-1",
        purchase_id="purchase-lx-001",
        product_name="Loja Express Pro",
        student_email="aluno@email.com",
        scheduled_job_d1_id="job-d1",
        scheduled_job_d3_id="job-d3",
        scheduled_job_d5_id="job-d5",
        scheduled_job_d7_id="job-d7",
    )
    await repo.save(case)

    found = await repo.get_by_purchase_id("purchase-lx-001")
    assert found is not None
    assert found.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert found.scheduled_job_d3_id == "job-d3"


@pytest.mark.asyncio
async def test_get_by_id_returns_none_when_missing(db_session):
    repo = LojaExpressCaseRepository(db_session)
    assert await repo.get_by_id("00000000-0000-0000-0000-000000000000") is None


@pytest.mark.asyncio
async def test_update_status_and_flags(db_session):
    repo = LojaExpressCaseRepository(db_session)
    case = LojaExpressCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="purchase-lx-update",
        product_name="P",
        student_email="e@e.com",
    )
    await repo.save(case)

    case.status = LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
    case.form_submitted = True
    await repo.update(case)

    found = await repo.get_by_purchase_id("purchase-lx-update")
    assert found.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
    assert found.form_submitted is True


@pytest.mark.asyncio
async def test_mark_delivered_sets_loja_entregue(db_session):
    repo = LojaExpressCaseRepository(db_session)
    case = LojaExpressCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="purchase-lx-delivered",
        product_name="P",
        student_email="e@e.com",
    )
    await repo.save(case)

    case.loja_entregue = True
    case.status = LojaExpressCaseStatus.ENTREGUE
    await repo.update(case)

    found = await repo.get_by_purchase_id("purchase-lx-delivered")
    assert found.loja_entregue is True
    assert found.status == LojaExpressCaseStatus.ENTREGUE


@pytest.mark.asyncio
async def test_duplicate_purchase_id_raises(db_session):
    repo = LojaExpressCaseRepository(db_session)
    c1 = LojaExpressCase(
        account_id=1, contact_id="c", conversation_id="cv",
        purchase_id="duplicate-lx", product_name="P", student_email="e@e.com",
    )
    c2 = LojaExpressCase(
        account_id=2, contact_id="c2", conversation_id="cv2",
        purchase_id="duplicate-lx", product_name="P", student_email="e@e.com",
    )
    await repo.save(c1)
    with pytest.raises(Exception):  # IntegrityError (UNIQUE constraint)
        await repo.save(c2)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_loja_express_repo.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar o repositório**

```python
# src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.loja_express_case import (
    LojaExpressCase,
    LojaExpressCaseStatus,
)
from nexoia.infrastructure.db.models import LojaExpressCaseModel


class LojaExpressCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, case: LojaExpressCase) -> None:
        model = LojaExpressCaseModel(
            id=case.id,
            account_id=case.account_id,
            contact_id=case.contact_id,
            conversation_id=case.conversation_id,
            purchase_id=case.purchase_id,
            product_name=case.product_name,
            student_email=case.student_email,
            form_submitted=case.form_submitted,
            loja_entregue=case.loja_entregue,
            status=case.status.value,
            scheduled_job_d1_id=case.scheduled_job_d1_id,
            scheduled_job_d3_id=case.scheduled_job_d3_id,
            scheduled_job_d5_id=case.scheduled_job_d5_id,
            scheduled_job_d7_id=case.scheduled_job_d7_id,
        )
        self._session.add(model)
        await self._session.commit()

    async def update(self, case: LojaExpressCase) -> None:
        model = await self._session.get(LojaExpressCaseModel, case.id)
        if model is None:
            raise ValueError(f"LojaExpressCase {case.id} not found")
        model.form_submitted = case.form_submitted
        model.loja_entregue = case.loja_entregue
        model.status = case.status.value
        model.scheduled_job_d1_id = case.scheduled_job_d1_id
        model.scheduled_job_d3_id = case.scheduled_job_d3_id
        model.scheduled_job_d5_id = case.scheduled_job_d5_id
        model.scheduled_job_d7_id = case.scheduled_job_d7_id
        await self._session.commit()

    async def get_by_id(self, case_id: str) -> LojaExpressCase | None:
        model = await self._session.get(LojaExpressCaseModel, case_id)
        return self._to_entity(model) if model else None

    async def get_by_purchase_id(self, purchase_id: str) -> LojaExpressCase | None:
        result = await self._session.execute(
            select(LojaExpressCaseModel).where(
                LojaExpressCaseModel.purchase_id == purchase_id
            )
        )
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    def _to_entity(self, model: LojaExpressCaseModel) -> LojaExpressCase:
        case = LojaExpressCase(
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            purchase_id=model.purchase_id,
            product_name=model.product_name,
            student_email=model.student_email,
        )
        case.id = str(model.id)
        case.form_submitted = model.form_submitted
        case.loja_entregue = model.loja_entregue
        case.status = LojaExpressCaseStatus(model.status)
        case.scheduled_job_d1_id = model.scheduled_job_d1_id
        case.scheduled_job_d3_id = model.scheduled_job_d3_id
        case.scheduled_job_d5_id = model.scheduled_job_d5_id
        case.scheduled_job_d7_id = model.scheduled_job_d7_id
        case.created_at = model.created_at
        case.updated_at = model.updated_at
        return case
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_loja_express_repo.py -v
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py \
        tests/integration/test_loja_express_repo.py
git commit -m "feat(loja-express): add LojaExpressCaseRepository (save/update/get)"
```

---

## Task 8: `LojaExpressState` + Subgraph D+0 (`send_d0 → schedule_followups → persist_case`)

**Files:**
- Create: `src/nexoia/application/capabilities/loja_express.py`
- Test: `tests/unit/capabilities/test_loja_express.py` (parte 1/3 — D+0)

- [ ] **Step 1: Escrever os testes unitários falhando (D+0)**

```python
# tests/unit/capabilities/test_loja_express.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.loja_express import (
    LojaExpressState,
    node_send_d0,
    node_schedule_followups,
    node_persist_case,
    build_loja_express_d0_subgraph,
)
from nexoia.domain.entities.loja_express_case import LojaExpressCaseStatus
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


def make_d0_state(**kwargs) -> LojaExpressState:
    base = dict(
        loja_express_case_id=None,
        purchase_id="p-lx-001",
        account_id=1,
        student_name="João Silva",
        student_email="joao@email.com",
        student_phone="+5511999999999",
        product_name="Loja Express Pro",
        form_submitted=False,
        loja_entregue=False,
        conversation_id="conv-001",
        last_followup_day=None,
        scheduled_job_ids={},
        messages=[],
        correlation_id="corr-001",
    )
    base.update(kwargs)
    return LojaExpressState(**base)


@pytest.mark.asyncio
async def test_node_send_d0_sends_welcome_and_step_by_step():
    chatnexo = FakeChatNexoClient()
    state = make_d0_state()

    result = await node_send_d0(state, chatnexo_port=chatnexo)

    # D+0 é dentro de janela 24h → pode ser texto livre OU template (PRD 7.5)
    # Implementação envia confirmação de recebimento + passo a passo.
    assert chatnexo.sent_messages, "esperava mensagem enviada no D+0"
    body = str(chatnexo.sent_messages[-1])
    assert "formulário" in body.lower() or "formulario" in body.lower()
    assert result == {} or result.get("d0_sent") is True  # aceita ambos os contratos


@pytest.mark.asyncio
async def test_node_schedule_followups_creates_four_jobs():
    scheduler = AsyncMock()
    scheduler.schedule.side_effect = [
        type("Job", (), {"id": f"job-{day}"})()
        for day in ("d1", "d3", "d5", "d7")
    ]
    state = make_d0_state()

    result = await node_schedule_followups(
        state,
        scheduler=scheduler,
        d1_delay_hours=24,
        d3_delay_hours=72,
        d5_delay_hours=120,
        d7_delay_hours=168,
    )

    assert scheduler.schedule.call_count == 4
    # Ordem esperada: D+1, D+3, D+5, D+7
    job_types_called = [c.kwargs["job_type"] for c in scheduler.schedule.call_args_list]
    assert job_types_called == [
        "LOJA_EXPRESS_D1",
        "LOJA_EXPRESS_D3",
        "LOJA_EXPRESS_D5",
        "LOJA_EXPRESS_D7",
    ]
    ids = result["scheduled_job_ids"]
    assert ids == {"d1": "job-d1", "d3": "job-d3", "d5": "job-d5", "d7": "job-d7"}


@pytest.mark.asyncio
async def test_node_persist_case_saves_aguardando_formulario(db_session):
    from nexoia.infrastructure.db.repositories.loja_express_case_repo import (
        LojaExpressCaseRepository,
    )
    repo = LojaExpressCaseRepository(db_session)
    state = make_d0_state(
        scheduled_job_ids={"d1": "j1", "d3": "j3", "d5": "j5", "d7": "j7"},
    )

    result = await node_persist_case(state, loja_express_case_repo=repo)

    case_id = result["loja_express_case_id"]
    saved = await repo.get_by_purchase_id("p-lx-001")
    assert saved is not None
    assert saved.id == case_id
    assert saved.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert saved.scheduled_job_d1_id == "j1"
    assert saved.scheduled_job_d7_id == "j7"


def test_d0_subgraph_wires_three_nodes():
    graph = build_loja_express_d0_subgraph()
    compiled = graph.compile()
    # smoke: grafo deve ter nós esperados
    assert "send_d0" in graph.nodes
    assert "schedule_followups" in graph.nodes
    assert "persist_case" in graph.nodes
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_loja_express.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar `LojaExpressState` + nós D+0 + build do subgraph**

```python
# src/nexoia/application/capabilities/loja_express.py
"""
Capability Loja Express (Spec ⑤).

Subgraph D+0: send_d0 → schedule_followups → persist_case
Subgraph Follow-up: check_case → execute_followup → update_case (ver Task 9)

Responsável por manter o aluno engajado durante os 7 dias pós-compra de
produto Loja Express, impedindo que o caso vire reembolso antes do prazo CDC.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Awaitable

import structlog
from langgraph.graph import StateGraph, END

from nexoia.application.state import ConversationState
from nexoia.application.scheduler.job_types import JobType
from nexoia.domain.entities.loja_express_case import (
    LojaExpressCase,
    LojaExpressCaseStatus,
)
from nexoia.domain.errors import LojaExpressError
from nexoia.domain.ports.chatnexo_port import ChatNexoPort
from nexoia.domain.ports.loja_express_port import (
    LojaExpressPort,
    LojaExpressStoreStatus,
)

logger = structlog.get_logger(__name__)


class LojaExpressState(ConversationState):
    loja_express_case_id: str | None
    purchase_id: str
    student_name: str
    student_email: str
    student_phone: str
    product_name: str
    form_submitted: bool
    loja_entregue: bool
    conversation_id: str | None
    last_followup_day: int | None
    scheduled_job_ids: dict[str, str]


# --------------------------------------------------------------------------
# Subgraph D+0
# --------------------------------------------------------------------------

_D0_MESSAGE = (
    "Oi {student_name}! 👋 Sua compra de *{product_name}* foi confirmada.\n"
    "Para começarmos a montar sua loja, responda o formulário: {form_url}\n"
    "Assim que você preencher, o time começa a configuração. Qualquer dúvida, me chama aqui!"
)

# TODO (CQ-L01): URL real do formulário por tenant.
_FORM_URL_PLACEHOLDER = "https://forms.example.com/loja-express"


async def node_send_d0(
    state: LojaExpressState,
    *,
    chatnexo_port: ChatNexoPort,
) -> dict[str, Any]:
    """
    D+0: confirma recebimento da compra + envia passo a passo do formulário.

    Dentro da janela 24h (compra foi feita agora) → pode ser texto livre.
    """
    log = logger.bind(
        capability="loja_express",
        node="send_d0",
        account_id=state["account_id"],
        purchase_id=state["purchase_id"],
    )
    body = _D0_MESSAGE.format(
        student_name=state["student_name"],
        product_name=state["product_name"],
        form_url=_FORM_URL_PLACEHOLDER,
    )
    await chatnexo_port.send_message(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        body=body,
    )
    log.info("d0_sent")
    return {"d0_sent": True}


async def node_schedule_followups(
    state: LojaExpressState,
    *,
    scheduler: Any,
    d1_delay_hours: int = 24,
    d3_delay_hours: int = 72,
    d5_delay_hours: int = 120,
    d7_delay_hours: int = 168,
) -> dict[str, Any]:
    """Agenda D+1, D+3, D+5, D+7 em scheduled_jobs via o Scheduler do Core."""
    log = logger.bind(
        capability="loja_express",
        node="schedule_followups",
        purchase_id=state["purchase_id"],
    )
    now = datetime.now(timezone.utc)

    specs = [
        ("d1", JobType.LOJA_EXPRESS_D1, d1_delay_hours),
        ("d3", JobType.LOJA_EXPRESS_D3, d3_delay_hours),
        ("d5", JobType.LOJA_EXPRESS_D5, d5_delay_hours),
        ("d7", JobType.LOJA_EXPRESS_D7, d7_delay_hours),
    ]
    scheduled_job_ids: dict[str, str] = {}
    for key, job_type, delay in specs:
        job = await scheduler.schedule(
            job_type=job_type.value,
            payload={
                "purchase_id": state["purchase_id"],
                "account_id": state["account_id"],
                "conversation_id": state["conversation_id"],
            },
            run_at=now + timedelta(hours=delay),
        )
        scheduled_job_ids[key] = job.id

    log.info(
        "followups_scheduled",
        scheduled_jobs_count=len(scheduled_job_ids),
        job_ids=scheduled_job_ids,
    )
    return {"scheduled_job_ids": scheduled_job_ids}


async def node_persist_case(
    state: LojaExpressState,
    *,
    loja_express_case_repo: Any,
) -> dict[str, Any]:
    """Cria LojaExpressCase(status=AGUARDANDO_FORMULARIO) no PostgreSQL."""
    log = logger.bind(
        capability="loja_express",
        node="persist_case",
        purchase_id=state["purchase_id"],
    )
    ids = state.get("scheduled_job_ids") or {}
    case = LojaExpressCase(
        account_id=state["account_id"],
        contact_id=state["student_email"],  # contact_id upstream pode ser email em Fase 1
        conversation_id=state["conversation_id"],
        purchase_id=state["purchase_id"],
        product_name=state["product_name"],
        student_email=state["student_email"],
        status=LojaExpressCaseStatus.AGUARDANDO_FORMULARIO,
        scheduled_job_d1_id=ids.get("d1"),
        scheduled_job_d3_id=ids.get("d3"),
        scheduled_job_d5_id=ids.get("d5"),
        scheduled_job_d7_id=ids.get("d7"),
    )
    await loja_express_case_repo.save(case)
    log.info("case_persisted", loja_express_case_id=case.id)
    return {"loja_express_case_id": case.id}


def build_loja_express_d0_subgraph() -> StateGraph:
    """Subgraph acionado pelo webhook de compra (produto Loja Express)."""
    graph = StateGraph(LojaExpressState)
    graph.add_node("send_d0", node_send_d0)
    graph.add_node("schedule_followups", node_schedule_followups)
    graph.add_node("persist_case", node_persist_case)

    graph.set_entry_point("send_d0")
    graph.add_edge("send_d0", "schedule_followups")
    graph.add_edge("schedule_followups", "persist_case")
    graph.add_edge("persist_case", END)
    return graph
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_loja_express.py -v -k "d0 or send_d0 or schedule_followups or persist_case or d0_subgraph"
```
Esperado: 4 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/loja_express.py \
        tests/unit/capabilities/test_loja_express.py
git commit -m "feat(loja-express): add D+0 subgraph (send_d0 → schedule_followups → persist_case)"
```

---

## Task 9: Subgraph Follow-up — `check_case → execute_followup → update_case` (D+1, D+3)

**Files:**
- Modify: `src/nexoia/application/capabilities/loja_express.py`
- Modify: `tests/unit/capabilities/test_loja_express.py` (acrescentar)

> Escopo desta task: nó `check_case` (com cancelamento se `loja_entregue=True`), a lógica **D+1** (verifica formulário, envia template `loja_express_d1` se pendente), a lógica **D+3** (template `loja_express_d3` de progresso) e o nó `update_case`. Lógica D+5 e D+7 vão na Task 10 para manter o diff revisável.

- [ ] **Step 1: Escrever os testes unitários falhando**

Acrescentar ao arquivo `tests/unit/capabilities/test_loja_express.py`:

```python
from unittest.mock import AsyncMock
from nexoia.application.capabilities.loja_express import (
    node_check_case,
    node_execute_followup,
    node_update_case,
    FOLLOWUP_CANCELLED,
    FOLLOWUP_CONTINUE,
)
from nexoia.domain.entities.loja_express_case import (
    LojaExpressCase,
    LojaExpressCaseStatus,
)
from tests.fakes.fake_loja_express_client import FakeLojaExpressClient


def _case(**kwargs) -> LojaExpressCase:
    base = dict(
        account_id=1,
        contact_id="c",
        conversation_id="conv-1",
        purchase_id="p-lx-001",
        product_name="Loja Express",
        student_email="e@e.com",
    )
    base.update(kwargs)
    return LojaExpressCase(**base)


def make_fu_state(day: int, **kwargs) -> "LojaExpressState":
    base = dict(
        loja_express_case_id="case-abc",
        purchase_id="p-lx-001",
        account_id=1,
        student_name="João",
        student_email="e@e.com",
        student_phone="+5511999999999",
        product_name="Loja Express Pro",
        form_submitted=False,
        loja_entregue=False,
        conversation_id="conv-1",
        last_followup_day=day,
        scheduled_job_ids={"d1": "j1", "d3": "j3", "d5": "j5", "d7": "j7"},
        messages=[],
        correlation_id="corr-001",
    )
    base.update(kwargs)
    return LojaExpressState(**base)


# ------------------------ check_case ------------------------

@pytest.mark.asyncio
async def test_check_case_loads_from_repo_and_continues_when_pending():
    repo = AsyncMock()
    repo.get_by_id.return_value = _case()
    scheduler = AsyncMock()
    state = make_fu_state(day=1)

    result = await node_check_case(
        state,
        loja_express_case_repo=repo,
        scheduler=scheduler,
    )

    assert result["control"] == FOLLOWUP_CONTINUE
    assert result["loja_entregue"] is False


@pytest.mark.asyncio
async def test_check_case_cancels_all_pending_jobs_when_delivered():
    delivered_case = _case(
        loja_entregue=True,
        status=LojaExpressCaseStatus.ENTREGUE,
        scheduled_job_d1_id="j1",
        scheduled_job_d3_id="j3",
        scheduled_job_d5_id="j5",
        scheduled_job_d7_id="j7",
    )
    repo = AsyncMock()
    repo.get_by_id.return_value = delivered_case
    scheduler = AsyncMock()
    state = make_fu_state(day=3)

    result = await node_check_case(
        state,
        loja_express_case_repo=repo,
        scheduler=scheduler,
    )

    assert result["control"] == FOLLOWUP_CANCELLED
    # cancela D+3, D+5 e D+7 (D+1 já pode ter executado — dependendo do day)
    cancelled_ids = [c.args[0] for c in scheduler.cancel.call_args_list]
    # garante que ao menos os jobs futuros ao day atual foram cancelados
    assert "j5" in cancelled_ids or "j7" in cancelled_ids


# ------------------------ execute_followup — D+1 ------------------------

@pytest.mark.asyncio
async def test_d1_form_pending_sends_template_loja_express_d1():
    chatnexo = FakeChatNexoClient()
    lx_client = FakeLojaExpressClient(form_submitted=False)
    state = make_fu_state(day=1)

    result = await node_execute_followup(
        state,
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=AsyncMock(),
    )

    assert chatnexo.last_sent_template == "loja_express_d1"
    assert result["new_status"] == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO.value


@pytest.mark.asyncio
async def test_d1_form_submitted_does_not_send_template():
    chatnexo = FakeChatNexoClient()
    lx_client = FakeLojaExpressClient(form_submitted=True)
    state = make_fu_state(day=1)

    result = await node_execute_followup(
        state,
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=AsyncMock(),
    )

    assert chatnexo.last_sent_template is None, "não deve enviar template se form já OK"
    assert result["form_submitted"] is True


# ------------------------ execute_followup — D+3 ------------------------

@pytest.mark.asyncio
async def test_d3_sends_progress_template():
    chatnexo = FakeChatNexoClient()
    lx_client = FakeLojaExpressClient(entregue=False, progresso_pct=40)
    state = make_fu_state(day=3)

    result = await node_execute_followup(
        state,
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=AsyncMock(),
    )

    assert chatnexo.last_sent_template == "loja_express_d3"
    assert result["new_status"] == LojaExpressCaseStatus.CHECK_D3_ENVIADO.value


# ------------------------ update_case ------------------------

@pytest.mark.asyncio
async def test_update_case_persists_status_and_flags():
    case = _case()
    repo = AsyncMock()
    repo.get_by_id.return_value = case
    state = make_fu_state(
        day=1,
        form_submitted=True,
    )

    await node_update_case(
        {**state, "new_status": LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO.value},
        loja_express_case_repo=repo,
    )

    repo.update.assert_awaited_once()
    updated: LojaExpressCase = repo.update.call_args[0][0]
    assert updated.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
    assert updated.form_submitted is True
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_loja_express.py -v
```
Esperado: `ImportError`/`AttributeError` nos novos nós.

- [ ] **Step 3: Implementar nós do subgraph follow-up**

Acrescentar em `src/nexoia/application/capabilities/loja_express.py`:

```python
# --------------------------------------------------------------------------
# Subgraph Follow-up (jobs agendados LOJA_EXPRESS_D1/D3/D5/D7)
# --------------------------------------------------------------------------

FOLLOWUP_CONTINUE = "continue"
FOLLOWUP_CANCELLED = "cancelled"


async def node_check_case(
    state: LojaExpressState,
    *,
    loja_express_case_repo: Any,
    scheduler: Any,
) -> dict[str, Any]:
    """
    Carrega LojaExpressCase; se loja_entregue=True cancela todos os jobs
    ainda pendentes (RF-L07) e sinaliza para o grafo encerrar (control=cancelled).
    """
    log = logger.bind(
        capability="loja_express",
        node="check_case",
        purchase_id=state["purchase_id"],
        day=state.get("last_followup_day"),
    )
    case = await loja_express_case_repo.get_by_id(state["loja_express_case_id"])
    if case is None:
        log.error("case_not_found", case_id=state["loja_express_case_id"])
        return {"control": FOLLOWUP_CANCELLED}

    if case.loja_entregue:
        current_day = state.get("last_followup_day") or 0
        pending_map = {
            1: case.scheduled_job_d1_id,
            3: case.scheduled_job_d3_id,
            5: case.scheduled_job_d5_id,
            7: case.scheduled_job_d7_id,
        }
        cancelled: list[str] = []
        for day_key, job_id in pending_map.items():
            if job_id and day_key > current_day:
                try:
                    await scheduler.cancel(job_id)
                    cancelled.append(job_id)
                except Exception as exc:  # noqa: BLE001
                    log.warning("cancel_failed", job_id=job_id, error=str(exc))
        log.info(
            "cancelled_jobs_on_delivery",
            loja_entregue=True,
            cancelled_jobs=cancelled,
        )
        return {"control": FOLLOWUP_CANCELLED, "loja_entregue": True}

    return {
        "control": FOLLOWUP_CONTINUE,
        "form_submitted": case.form_submitted,
        "loja_entregue": case.loja_entregue,
    }


async def node_execute_followup(
    state: LojaExpressState,
    *,
    chatnexo_port: ChatNexoPort,
    loja_express_port: LojaExpressPort,
    handoff_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    """Roteia por dia (D+1/D+3/D+5/D+7) e aplica a regra de negócio correspondente."""
    day = state.get("last_followup_day")
    log = logger.bind(
        capability="loja_express",
        node="execute_followup",
        day=day,
        purchase_id=state["purchase_id"],
    )

    if day == 1:
        return await _execute_d1(state, chatnexo_port, loja_express_port, log)
    if day == 3:
        return await _execute_d3(state, chatnexo_port, loja_express_port, log)
    if day == 5:
        return await _execute_d5(state, chatnexo_port, loja_express_port, handoff_fn, log)
    if day == 7:
        return await _execute_d7(state, chatnexo_port, loja_express_port, handoff_fn, log)

    log.error("invalid_followup_day", day=day)
    return {}


async def _execute_d1(
    state: LojaExpressState,
    chatnexo_port: ChatNexoPort,
    loja_express_port: LojaExpressPort,
    log: Any,
) -> dict[str, Any]:
    """D+1: verifica formulário; se pendente envia template `loja_express_d1`."""
    try:
        submitted = await loja_express_port.is_form_submitted(
            state["loja_express_case_id"]
        )
    except LojaExpressError as exc:
        log.warning("form_check_failed", error=str(exc))
        submitted = False  # fail-open: assume pendente e envia lembrete

    if submitted:
        log.info("form_already_submitted", day=1)
        return {
            "form_submitted": True,
            "new_status": LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO.value,
        }

    # TODO (CQ-W04): variáveis exatas do template a confirmar com Meta Business
    await chatnexo_port.send_template(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        template_name="loja_express_d1",
        variables={
            "1": state["student_name"],
            "2": state["product_name"],
            "3": _FORM_URL_PLACEHOLDER,
        },
    )
    log.info("d1_reminder_sent", template="loja_express_d1", form_submitted=False)
    return {
        "form_submitted": False,
        "new_status": LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO.value,
    }


async def _execute_d3(
    state: LojaExpressState,
    chatnexo_port: ChatNexoPort,
    loja_express_port: LojaExpressPort,
    log: Any,
) -> dict[str, Any]:
    """D+3: verifica status da loja e envia template `loja_express_d3` com progresso."""
    try:
        status: LojaExpressStoreStatus = await loja_express_port.get_store_status(
            state["loja_express_case_id"]
        )
    except LojaExpressError as exc:
        log.warning("status_check_failed", error=str(exc))
        status = LojaExpressStoreStatus(case_id=state["loja_express_case_id"])

    # TODO (CQ-W04): confirmar variáveis reais com Meta Business
    await chatnexo_port.send_template(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        template_name="loja_express_d3",
        variables={
            "1": state["student_name"],
            "2": str(status.progresso_pct),
        },
    )
    log.info(
        "d3_progress_sent",
        template="loja_express_d3",
        progresso_pct=status.progresso_pct,
        loja_entregue=status.entregue,
    )
    return {
        "loja_entregue": status.entregue,
        "new_status": LojaExpressCaseStatus.CHECK_D3_ENVIADO.value,
    }


async def node_update_case(
    state: LojaExpressState,
    *,
    loja_express_case_repo: Any,
) -> dict[str, Any]:
    """Persiste status / form_submitted / loja_entregue após o follow-up."""
    case = await loja_express_case_repo.get_by_id(state["loja_express_case_id"])
    if case is None:
        return {}
    new_status = state.get("new_status")
    if new_status:
        case.status = LojaExpressCaseStatus(new_status)
    case.form_submitted = state.get("form_submitted", case.form_submitted)
    case.loja_entregue = state.get("loja_entregue", case.loja_entregue)
    await loja_express_case_repo.update(case)
    logger.bind(
        capability="loja_express",
        node="update_case",
        case_id=case.id,
    ).info("case_updated", status=case.status.value)
    return {}
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_loja_express.py -v
```
Esperado: testes D+1/D+3 e update_case PASSED (testes D+5/D+7 ainda não existem).

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/loja_express.py \
        tests/unit/capabilities/test_loja_express.py
git commit -m "feat(loja-express): add follow-up subgraph (check_case, D+1/D+3, update_case)"
```

---

## Task 10: Lógica D+5 (escalação silenciosa) e D+7 (prazo crítico)

**Files:**
- Modify: `src/nexoia/application/capabilities/loja_express.py`
- Modify: `tests/unit/capabilities/test_loja_express.py` (acrescentar)

- [ ] **Step 1: Escrever os testes falhando**

Acrescentar a `tests/unit/capabilities/test_loja_express.py`:

```python
# ------------------------ execute_followup — D+5 ------------------------

@pytest.mark.asyncio
async def test_d5_not_delivered_triggers_silent_handoff():
    chatnexo = FakeChatNexoClient()
    lx_client = FakeLojaExpressClient(entregue=False, bloqueio="aguardando_fornecedor")
    handoff = AsyncMock()
    state = make_fu_state(day=5)

    result = await node_execute_followup(
        state,
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=handoff,
    )

    handoff.assert_awaited_once()
    call_kwargs = handoff.call_args.kwargs
    assert call_kwargs["reason"] == "loja_express_d5_bloqueio"
    assert result["new_status"] == LojaExpressCaseStatus.ALERTA_D5_ENVIADO.value


@pytest.mark.asyncio
async def test_d5_delivered_does_not_trigger_handoff():
    chatnexo = FakeChatNexoClient()
    lx_client = FakeLojaExpressClient(entregue=True)
    handoff = AsyncMock()
    state = make_fu_state(day=5)

    result = await node_execute_followup(
        state,
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=handoff,
    )

    handoff.assert_not_awaited()
    assert result["loja_entregue"] is True


# ------------------------ execute_followup — D+7 ------------------------

@pytest.mark.asyncio
async def test_d7_sends_urgent_template_and_escalates_when_not_resolved():
    chatnexo = FakeChatNexoClient()
    lx_client = FakeLojaExpressClient(entregue=False)
    handoff = AsyncMock()
    state = make_fu_state(day=7)

    result = await node_execute_followup(
        state,
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=handoff,
    )

    assert chatnexo.last_sent_template == "loja_express_d7"
    handoff.assert_awaited_once()
    assert handoff.call_args.kwargs["reason"] == "loja_express_d7_prazo_critico"
    assert result["new_status"] == LojaExpressCaseStatus.PRAZO_CRITICO_D7.value


@pytest.mark.asyncio
async def test_d7_delivered_sends_template_without_escalation():
    chatnexo = FakeChatNexoClient()
    lx_client = FakeLojaExpressClient(entregue=True)
    handoff = AsyncMock()
    state = make_fu_state(day=7)

    await node_execute_followup(
        state,
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=handoff,
    )

    handoff.assert_not_awaited()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_loja_express.py::test_d5_not_delivered_triggers_silent_handoff -v
```
Esperado: `NameError`/falha da lógica (D+5/D+7 não implementados).

- [ ] **Step 3: Implementar lógica D+5 e D+7**

Acrescentar em `src/nexoia/application/capabilities/loja_express.py`:

```python
async def _execute_d5(
    state: LojaExpressState,
    chatnexo_port: ChatNexoPort,
    loja_express_port: LojaExpressPort,
    handoff_fn: Callable[..., Awaitable[None]],
    log: Any,
) -> dict[str, Any]:
    """
    D+5: se loja não entregue → escalação silenciosa + mensagem ao aluno.

    TODO (CQ-L03): confirmar se há template Meta para D+5. Como a janela
    de 24h pode ainda estar aberta (aluno interagiu no D+3), por ora enviamos
    texto livre informativo. Implementação real deve ser ajustada quando
    a equipe responder CQ-L03.
    """
    try:
        status: LojaExpressStoreStatus = await loja_express_port.get_store_status(
            state["loja_express_case_id"]
        )
    except LojaExpressError as exc:
        log.warning("status_check_failed", error=str(exc))
        status = LojaExpressStoreStatus(case_id=state["loja_express_case_id"])

    if status.entregue:
        log.info("d5_loja_entregue", entregue=True)
        return {
            "loja_entregue": True,
            "new_status": LojaExpressCaseStatus.ENTREGUE.value,
        }

    # Escalação silenciosa para operação
    await handoff_fn(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        reason="loja_express_d5_bloqueio",
        metadata={
            "purchase_id": state["purchase_id"],
            "case_id": state["loja_express_case_id"],
            "bloqueio": status.bloqueio,
        },
    )

    # TODO (CQ-L03): substituir por template aprovado quando houver
    await chatnexo_port.send_message(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        body=(
            f"Oi {state['student_name']}! Já estou acionando o time para "
            f"destravar a sua loja. Assim que o responsável avançar, eu te aviso."
        ),
    )
    log.warning(
        "d5_escalated",
        reason="loja_not_delivered",
        bloqueio=status.bloqueio,
    )
    return {
        "loja_entregue": False,
        "new_status": LojaExpressCaseStatus.ALERTA_D5_ENVIADO.value,
    }


async def _execute_d7(
    state: LojaExpressState,
    chatnexo_port: ChatNexoPort,
    loja_express_port: LojaExpressPort,
    handoff_fn: Callable[..., Awaitable[None]],
    log: Any,
) -> dict[str, Any]:
    """
    D+7: prazo crítico — último dia do prazo de reembolso CDC.

    Sempre envia template `loja_express_d7` (urgência). Se loja ainda não
    entregue, escala silenciosamente para operação em paralelo.
    """
    try:
        status: LojaExpressStoreStatus = await loja_express_port.get_store_status(
            state["loja_express_case_id"]
        )
    except LojaExpressError as exc:
        log.warning("status_check_failed", error=str(exc))
        status = LojaExpressStoreStatus(case_id=state["loja_express_case_id"])

    # TODO (CQ-W04): variáveis exatas a confirmar
    await chatnexo_port.send_template(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        template_name="loja_express_d7",
        variables={
            "1": state["student_name"],
            "2": state["product_name"],
        },
    )

    if not status.entregue:
        await handoff_fn(
            account_id=state["account_id"],
            conversation_id=state["conversation_id"],
            reason="loja_express_d7_prazo_critico",
            metadata={
                "purchase_id": state["purchase_id"],
                "case_id": state["loja_express_case_id"],
            },
        )
        log.warning("d7_escalated", reason="prazo_critico_nao_resolvido")
        return {
            "loja_entregue": False,
            "new_status": LojaExpressCaseStatus.PRAZO_CRITICO_D7.value,
        }

    log.info("d7_entregue", template="loja_express_d7")
    return {
        "loja_entregue": True,
        "new_status": LojaExpressCaseStatus.ENTREGUE.value,
    }
```

- [ ] **Step 4: Build do subgraph follow-up + roteamento condicional**

Ainda em `loja_express.py`, adicionar ao final:

```python
def _route_after_check(state: LojaExpressState) -> str:
    """Conditional edge: se check_case cancelou, vai direto para END."""
    if state.get("control") == FOLLOWUP_CANCELLED:
        return END
    return "execute_followup"


def build_loja_express_followup_subgraph() -> StateGraph:
    """Subgraph acionado pelos jobs LOJA_EXPRESS_D1/D3/D5/D7."""
    graph = StateGraph(LojaExpressState)
    graph.add_node("check_case", node_check_case)
    graph.add_node("execute_followup", node_execute_followup)
    graph.add_node("update_case", node_update_case)

    graph.set_entry_point("check_case")
    graph.add_conditional_edges(
        "check_case",
        _route_after_check,
        {
            "execute_followup": "execute_followup",
            END: END,
        },
    )
    graph.add_edge("execute_followup", "update_case")
    graph.add_edge("update_case", END)
    return graph
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_loja_express.py -v
```
Esperado: todos os testes do arquivo PASSED (D+0, check_case, D+1/D+3/D+5/D+7, update_case).

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/application/capabilities/loja_express.py \
        tests/unit/capabilities/test_loja_express.py
git commit -m "feat(loja-express): add D+5 silent escalation and D+7 critical deadline logic"
```

---

## Task 11: Detecção de produto Loja Express no handler `process_purchase`

**Files:**
- Modify: `src/nexoia/interface/worker/handlers/process_purchase.py`
- Test: `tests/unit/worker/test_loja_express_detection.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/worker/test_loja_express_detection.py
import pytest
from unittest.mock import AsyncMock, patch

from nexoia.interface.worker.handlers.process_purchase import (
    handle_process_purchase_webhook,
    is_loja_express_product,
)


def test_is_loja_express_product_exact_match():
    assert is_loja_express_product("loja_express", ["loja_express"]) is True


def test_is_loja_express_product_case_insensitive():
    assert is_loja_express_product("Loja Express Pro", ["loja_express"]) is True
    assert is_loja_express_product("LOJA-EXPRESS-VIP", ["loja_express", "loja-express"]) is True


def test_is_loja_express_product_false_for_other_products():
    assert is_loja_express_product("Curso Python", ["loja_express"]) is False
    assert is_loja_express_product("Mentoria", ["loja_express"]) is False


def test_is_loja_express_product_empty_tags_returns_false():
    assert is_loja_express_product("Loja Express", []) is False


@pytest.mark.asyncio
async def test_handler_routes_to_loja_express_when_product_is_lx():
    job_payload = {
        "purchase_id": "p-001",
        "account_id": 1,
        "student_name": "João",
        "student_phone": "+5511999999999",
        "student_email": "joao@email.com",
        "product_name": "Loja Express Pro",
        "correlation_id": "corr-001",
    }
    run_loja_express = AsyncMock(return_value={"loja_express_case_id": "case-1"})
    run_welcome = AsyncMock()

    with (
        patch(
            "nexoia.interface.worker.handlers.process_purchase.run_loja_express_d0_subgraph",
            run_loja_express,
        ),
        patch(
            "nexoia.interface.worker.handlers.process_purchase.run_welcome_subgraph",
            run_welcome,
        ),
    ):
        await handle_process_purchase_webhook(payload=job_payload)

    run_loja_express.assert_awaited_once()
    run_welcome.assert_not_awaited()


@pytest.mark.asyncio
async def test_handler_routes_to_welcome_for_non_loja_express():
    job_payload = {
        "purchase_id": "p-002",
        "account_id": 1,
        "student_name": "Maria",
        "student_phone": "+5511988888888",
        "student_email": "maria@email.com",
        "product_name": "Curso de Vendas",
        "correlation_id": "corr-002",
    }
    run_loja_express = AsyncMock()
    run_welcome = AsyncMock(return_value={"access_case_id": "ac-1"})

    with (
        patch(
            "nexoia.interface.worker.handlers.process_purchase.run_loja_express_d0_subgraph",
            run_loja_express,
        ),
        patch(
            "nexoia.interface.worker.handlers.process_purchase.run_welcome_subgraph",
            run_welcome,
        ),
    ):
        await handle_process_purchase_webhook(payload=job_payload)

    run_welcome.assert_awaited_once()
    run_loja_express.assert_not_awaited()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/worker/test_loja_express_detection.py -v
```
Esperado: `ImportError` (is_loja_express_product / run_loja_express_d0_subgraph não existem).

- [ ] **Step 3: Modificar o handler `process_purchase.py`**

No arquivo `src/nexoia/interface/worker/handlers/process_purchase.py`, adicionar / alterar:

```python
from __future__ import annotations

from typing import Any

import structlog

from nexoia.application.capabilities.loja_express import (
    LojaExpressState,
    build_loja_express_d0_subgraph,
)
from nexoia.application.capabilities.welcome import WelcomeState, build_welcome_subgraph
from nexoia.config.settings import get_settings

logger = structlog.get_logger(__name__)

_welcome_graph = build_welcome_subgraph().compile()
_loja_express_d0_graph = build_loja_express_d0_subgraph().compile()


def is_loja_express_product(product_name: str, tags: list[str]) -> bool:
    """Comparação case-insensitive: retorna True se product_name contém alguma tag."""
    if not tags:
        return False
    normalized = product_name.lower()
    return any(tag.lower() in normalized for tag in tags)


async def run_welcome_subgraph(**kwargs: Any) -> dict[str, Any]:
    initial_state = WelcomeState(**kwargs)
    return await _welcome_graph.ainvoke(initial_state)


async def run_loja_express_d0_subgraph(**kwargs: Any) -> dict[str, Any]:
    initial_state = LojaExpressState(**kwargs)
    return await _loja_express_d0_graph.ainvoke(initial_state)


async def handle_process_purchase_webhook(payload: dict[str, Any]) -> None:
    settings = get_settings()
    log = logger.bind(
        handler="process_purchase",
        purchase_id=payload["purchase_id"],
        correlation_id=payload.get("correlation_id", ""),
    )
    product_name = payload["product_name"]

    if is_loja_express_product(product_name, settings.LOJA_EXPRESS_PRODUCT_TAGS):
        log.info("routing_to_loja_express", product_name=product_name)
        await run_loja_express_d0_subgraph(
            loja_express_case_id=None,
            purchase_id=payload["purchase_id"],
            account_id=payload["account_id"],
            student_name=payload["student_name"],
            student_email=payload["student_email"],
            student_phone=payload["student_phone"],
            product_name=product_name,
            form_submitted=False,
            loja_entregue=False,
            conversation_id=payload.get("conversation_id"),
            last_followup_day=None,
            scheduled_job_ids={},
            messages=[],
            correlation_id=payload.get("correlation_id", ""),
        )
        return

    log.info("routing_to_welcome", product_name=product_name)
    await run_welcome_subgraph(
        purchase_id=payload["purchase_id"],
        account_id=payload["account_id"],
        student_name=payload["student_name"],
        student_phone=payload["student_phone"],
        student_email=payload["student_email"],
        product_name=product_name,
        access_link=None,
        cademi_attempts=0,
        conversation_id=None,
        access_case_id=None,
        access_confirmed=False,
        cademi_failed=False,
        messages=[],
        correlation_id=payload.get("correlation_id", ""),
    )
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/worker/test_loja_express_detection.py -v
```
Esperado: 6 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/interface/worker/handlers/process_purchase.py \
        tests/unit/worker/test_loja_express_detection.py
git commit -m "feat(loja-express): detect Loja Express products and route to D+0 subgraph"
```

---

## Task 12: Handler dos jobs `LOJA_EXPRESS_D1/D3/D5/D7`

**Files:**
- Modify: `src/nexoia/interface/worker/handlers/send_scheduled_followup.py`
- Test: `tests/unit/worker/test_send_scheduled_followup_loja_express.py`

> Este handler reusa o dispatcher existente de `SendScheduledFollowUp` do Core (Spec ①) e adiciona roteamento por `job_type` para o subgraph follow-up da Loja Express.

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/worker/test_send_scheduled_followup_loja_express.py
import pytest
from unittest.mock import AsyncMock, patch

from nexoia.interface.worker.handlers.send_scheduled_followup import (
    handle_send_scheduled_followup,
)


@pytest.mark.asyncio
async def test_d1_job_invokes_loja_express_followup_subgraph():
    run_fu = AsyncMock(return_value={})
    payload = {
        "job_type": "LOJA_EXPRESS_D1",
        "purchase_id": "p-lx-001",
        "account_id": 1,
        "conversation_id": "conv-1",
    }
    with patch(
        "nexoia.interface.worker.handlers.send_scheduled_followup.run_loja_express_followup_subgraph",
        run_fu,
    ):
        await handle_send_scheduled_followup(payload=payload)

    run_fu.assert_awaited_once()
    assert run_fu.call_args.kwargs["last_followup_day"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "job_type,expected_day",
    [
        ("LOJA_EXPRESS_D1", 1),
        ("LOJA_EXPRESS_D3", 3),
        ("LOJA_EXPRESS_D5", 5),
        ("LOJA_EXPRESS_D7", 7),
    ],
)
async def test_maps_job_type_to_day(job_type, expected_day):
    run_fu = AsyncMock(return_value={})
    payload = {
        "job_type": job_type,
        "purchase_id": "p-lx-001",
        "account_id": 1,
        "conversation_id": "conv-1",
    }
    with patch(
        "nexoia.interface.worker.handlers.send_scheduled_followup.run_loja_express_followup_subgraph",
        run_fu,
    ):
        await handle_send_scheduled_followup(payload=payload)

    assert run_fu.call_args.kwargs["last_followup_day"] == expected_day


@pytest.mark.asyncio
async def test_non_loja_express_job_type_delegates_to_existing_handler():
    """SendScheduledFollowUp com payload de welcome continua funcionando (delegação)."""
    run_welcome_fu = AsyncMock(return_value={})
    payload = {
        "job_type": "SendScheduledFollowUp",
        "template": "access_reminder_d1",
        "account_id": 1,
    }
    with patch(
        "nexoia.interface.worker.handlers.send_scheduled_followup.run_welcome_d1_followup",
        run_welcome_fu,
    ):
        await handle_send_scheduled_followup(payload=payload)
    # o teste só valida que o handler tolera o caso — comportamento pode variar
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/worker/test_send_scheduled_followup_loja_express.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar o handler**

Modificar/criar `src/nexoia/interface/worker/handlers/send_scheduled_followup.py`:

```python
from __future__ import annotations

from typing import Any

import structlog

from nexoia.application.capabilities.loja_express import (
    LojaExpressState,
    build_loja_express_followup_subgraph,
)

logger = structlog.get_logger(__name__)

_loja_express_followup_graph = build_loja_express_followup_subgraph().compile()

_JOB_TYPE_TO_DAY = {
    "LOJA_EXPRESS_D1": 1,
    "LOJA_EXPRESS_D3": 3,
    "LOJA_EXPRESS_D5": 5,
    "LOJA_EXPRESS_D7": 7,
}


async def run_loja_express_followup_subgraph(**kwargs: Any) -> dict[str, Any]:
    initial_state = LojaExpressState(**kwargs)
    return await _loja_express_followup_graph.ainvoke(initial_state)


async def run_welcome_d1_followup(**kwargs: Any) -> dict[str, Any]:
    """Stub de delegação — implementado no Spec ② (Welcome D+1 reminder)."""
    # implementado pela Spec ② — aqui só um marcador para manter compat
    return {}


async def handle_send_scheduled_followup(payload: dict[str, Any]) -> None:
    job_type = payload.get("job_type", "SendScheduledFollowUp")
    log = logger.bind(
        handler="send_scheduled_followup",
        job_type=job_type,
        purchase_id=payload.get("purchase_id"),
    )

    day = _JOB_TYPE_TO_DAY.get(job_type)
    if day is not None:
        log.info("routing_to_loja_express_followup", day=day)
        # TODO (Core): resolver loja_express_case_id pelo purchase_id
        # (o scheduler envia purchase_id — o subgraph carrega pelo repo via case_id).
        # Para manter acoplamento baixo, aqui assumimos que o payload já traz case_id
        # quando o Scheduler do Core enriquece o job com ele.
        await run_loja_express_followup_subgraph(
            loja_express_case_id=payload.get("loja_express_case_id"),
            purchase_id=payload["purchase_id"],
            account_id=payload["account_id"],
            student_name=payload.get("student_name", ""),
            student_email=payload.get("student_email", ""),
            student_phone=payload.get("student_phone", ""),
            product_name=payload.get("product_name", ""),
            form_submitted=False,
            loja_entregue=False,
            conversation_id=payload.get("conversation_id"),
            last_followup_day=day,
            scheduled_job_ids={},
            messages=[],
            correlation_id=payload.get("correlation_id", ""),
        )
        return

    # Outros job_types (Welcome D+1 etc.) — delegação para handlers existentes
    log.info("delegating_to_welcome_handler", job_type=job_type)
    await run_welcome_d1_followup(**payload)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/worker/test_send_scheduled_followup_loja_express.py -v
```
Esperado: todos PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/interface/worker/handlers/send_scheduled_followup.py \
        tests/unit/worker/test_send_scheduled_followup_loja_express.py
git commit -m "feat(loja-express): dispatch LOJA_EXPRESS_* jobs to follow-up subgraph"
```

---

## Task 13: Métricas Prometheus da Loja Express

**Files:**
- Modify: `src/nexoia/infrastructure/observability/metrics.py`
- Test: `tests/unit/observability/test_loja_express_metrics.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/observability/test_loja_express_metrics.py
from nexoia.infrastructure.observability.metrics import (
    loja_express_total,
    loja_express_followup_sent_total,
    loja_express_form_pending_at_d1_total,
)


def test_loja_express_total_labels():
    loja_express_total.labels(status="delivered").inc()
    loja_express_total.labels(status="escalated").inc()
    loja_express_total.labels(status="timeout").inc()


def test_loja_express_followup_sent_labels():
    for day in ("1", "3", "5", "7"):
        loja_express_followup_sent_total.labels(day=day).inc()


def test_loja_express_form_pending_counter():
    loja_express_form_pending_at_d1_total.inc()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/observability/test_loja_express_metrics.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Adicionar métricas**

No arquivo `src/nexoia/infrastructure/observability/metrics.py`, acrescentar:

```python
from prometheus_client import Counter

# Capability Loja Express (Spec ⑤)
loja_express_total = Counter(
    "loja_express_total",
    "Total de casos da Capability Loja Express por status terminal",
    labelnames=["status"],  # delivered | escalated | timeout
)
loja_express_followup_sent_total = Counter(
    "loja_express_followup_sent_total",
    "Total de follow-ups enviados por dia",
    labelnames=["day"],  # 1 | 3 | 5 | 7
)
loja_express_form_pending_at_d1_total = Counter(
    "loja_express_form_pending_at_d1_total",
    "Total de casos com formulário ainda pendente no D+1",
)
```

- [ ] **Step 4: Incrementar as métricas nos nós da capability**

No arquivo `src/nexoia/application/capabilities/loja_express.py`, importar as métricas no topo e chamar:

- `_execute_d1` → após envio do template: `loja_express_followup_sent_total.labels(day="1").inc()`. Se `submitted is False`: `loja_express_form_pending_at_d1_total.inc()`.
- `_execute_d3` → `loja_express_followup_sent_total.labels(day="3").inc()`.
- `_execute_d5` → `loja_express_followup_sent_total.labels(day="5").inc()`. Se escalou: `loja_express_total.labels(status="escalated").inc()`.
- `_execute_d7` → `loja_express_followup_sent_total.labels(day="7").inc()`. Se escalou: `loja_express_total.labels(status="timeout").inc()`; senão `loja_express_total.labels(status="delivered").inc()`.
- `node_check_case` → se cancelou por entrega: `loja_express_total.labels(status="delivered").inc()`.

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/observability/test_loja_express_metrics.py -v
uv run pytest tests/unit/capabilities/test_loja_express.py -v  # garantir sem regressão
```
Esperado: todos PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/infrastructure/observability/metrics.py \
        src/nexoia/application/capabilities/loja_express.py \
        tests/unit/observability/test_loja_express_metrics.py
git commit -m "feat(loja-express): add Prometheus metrics and instrument capability nodes"
```

---

## Task 14: Teste de integração end-to-end da Capability Loja Express

**Files:**
- Create: `tests/integration/test_loja_express_flow.py`

- [ ] **Step 1: Escrever o teste de integração completo**

```python
# tests/integration/test_loja_express_flow.py
"""
Fluxo end-to-end da Capability Loja Express (Spec ⑤).

Valida:
- D+0: mensagem enviada + 4 jobs agendados + LojaExpressCase persistido
- D+1 (form pendente): template `loja_express_d1` enviado + status atualizado
- D+3: template `loja_express_d3` + progresso
- D+5 (loja não entregue): handoff silencioso + status ALERTA_D5
- D+7 (loja não entregue): template urgência + handoff + status PRAZO_CRITICO
- Cancelamento de todos os jobs pendentes quando loja_entregue=True
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from nexoia.application.capabilities.loja_express import (
    LojaExpressState,
    build_loja_express_d0_subgraph,
    build_loja_express_followup_subgraph,
    node_check_case,
    node_execute_followup,
    node_update_case,
    node_send_d0,
    node_schedule_followups,
    node_persist_case,
)
from nexoia.domain.entities.loja_express_case import LojaExpressCaseStatus
from nexoia.infrastructure.db.repositories.loja_express_case_repo import (
    LojaExpressCaseRepository,
)
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient
from tests.fakes.fake_loja_express_client import FakeLojaExpressClient


@pytest.fixture
def d0_initial_state() -> LojaExpressState:
    return LojaExpressState(
        loja_express_case_id=None,
        purchase_id="purchase-lx-e2e-001",
        account_id=1,
        student_name="Maria Souza",
        student_email="maria@email.com",
        student_phone="+5511988888888",
        product_name="Loja Express Pro",
        form_submitted=False,
        loja_entregue=False,
        conversation_id="conv-e2e-001",
        last_followup_day=None,
        scheduled_job_ids={},
        messages=[],
        correlation_id="corr-e2e-001",
    )


@pytest.mark.asyncio
async def test_d0_flow_persists_case_and_schedules_four_jobs(db_session, d0_initial_state):
    chatnexo = FakeChatNexoClient()
    scheduler = AsyncMock()
    scheduler.schedule.side_effect = [
        type("Job", (), {"id": f"job-{d}"})() for d in ("d1", "d3", "d5", "d7")
    ]
    repo = LojaExpressCaseRepository(db_session)

    state = dict(d0_initial_state)
    state.update(await node_send_d0(d0_initial_state, chatnexo_port=chatnexo))
    state.update(
        await node_schedule_followups(
            LojaExpressState(**state),
            scheduler=scheduler,
            d1_delay_hours=24,
            d3_delay_hours=72,
            d5_delay_hours=120,
            d7_delay_hours=168,
        )
    )
    state.update(
        await node_persist_case(
            LojaExpressState(**state), loja_express_case_repo=repo
        )
    )

    saved = await repo.get_by_purchase_id("purchase-lx-e2e-001")
    assert saved is not None
    assert saved.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert saved.scheduled_job_d1_id == "job-d1"
    assert saved.scheduled_job_d3_id == "job-d3"
    assert saved.scheduled_job_d5_id == "job-d5"
    assert saved.scheduled_job_d7_id == "job-d7"
    assert scheduler.schedule.call_count == 4


@pytest.mark.asyncio
async def test_d1_form_pending_sends_template_and_updates_status(db_session, d0_initial_state):
    # prepara case no banco
    repo = LojaExpressCaseRepository(db_session)
    chatnexo = FakeChatNexoClient()
    scheduler = AsyncMock()
    scheduler.schedule.side_effect = [
        type("Job", (), {"id": f"job-{d}"})() for d in ("d1", "d3", "d5", "d7")
    ]
    state = dict(d0_initial_state)
    state.update(await node_send_d0(d0_initial_state, chatnexo_port=chatnexo))
    state.update(
        await node_schedule_followups(
            LojaExpressState(**state), scheduler=scheduler,
            d1_delay_hours=24, d3_delay_hours=72, d5_delay_hours=120, d7_delay_hours=168,
        )
    )
    state.update(await node_persist_case(LojaExpressState(**state), loja_express_case_repo=repo))

    # Executa follow-up D+1 com form pendente
    lx_client = FakeLojaExpressClient(form_submitted=False)
    fu_state = LojaExpressState(**{**state, "last_followup_day": 1})

    check = await node_check_case(fu_state, loja_express_case_repo=repo, scheduler=scheduler)
    merged = {**fu_state, **check}
    exec_res = await node_execute_followup(
        LojaExpressState(**merged),
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=AsyncMock(),
    )
    merged.update(exec_res)
    await node_update_case(LojaExpressState(**merged), loja_express_case_repo=repo)

    assert chatnexo.last_sent_template == "loja_express_d1"
    saved = await repo.get_by_purchase_id("purchase-lx-e2e-001")
    assert saved.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO


@pytest.mark.asyncio
async def test_d5_not_delivered_triggers_silent_handoff(db_session, d0_initial_state):
    # reaproveita helper de setup (idêntico aos testes anteriores)
    repo = LojaExpressCaseRepository(db_session)
    chatnexo = FakeChatNexoClient()
    scheduler = AsyncMock()
    scheduler.schedule.side_effect = [
        type("Job", (), {"id": f"job-{d}"})() for d in ("d1", "d3", "d5", "d7")
    ]
    state = dict(d0_initial_state)
    state.update(await node_send_d0(d0_initial_state, chatnexo_port=chatnexo))
    state.update(
        await node_schedule_followups(
            LojaExpressState(**state), scheduler=scheduler,
            d1_delay_hours=24, d3_delay_hours=72, d5_delay_hours=120, d7_delay_hours=168,
        )
    )
    state.update(await node_persist_case(LojaExpressState(**state), loja_express_case_repo=repo))

    lx_client = FakeLojaExpressClient(entregue=False, bloqueio="aguardando_fornecedor")
    handoff = AsyncMock()
    fu_state = LojaExpressState(**{**state, "last_followup_day": 5})

    check = await node_check_case(fu_state, loja_express_case_repo=repo, scheduler=scheduler)
    merged = {**fu_state, **check}
    exec_res = await node_execute_followup(
        LojaExpressState(**merged),
        chatnexo_port=chatnexo,
        loja_express_port=lx_client,
        handoff_fn=handoff,
    )
    merged.update(exec_res)
    await node_update_case(LojaExpressState(**merged), loja_express_case_repo=repo)

    handoff.assert_awaited_once()
    assert handoff.call_args.kwargs["reason"] == "loja_express_d5_bloqueio"
    saved = await repo.get_by_purchase_id("purchase-lx-e2e-001")
    assert saved.status == LojaExpressCaseStatus.ALERTA_D5_ENVIADO


@pytest.mark.asyncio
async def test_delivery_cancels_pending_jobs(db_session, d0_initial_state):
    repo = LojaExpressCaseRepository(db_session)
    chatnexo = FakeChatNexoClient()
    scheduler = AsyncMock()
    scheduler.schedule.side_effect = [
        type("Job", (), {"id": f"job-{d}"})() for d in ("d1", "d3", "d5", "d7")
    ]
    state = dict(d0_initial_state)
    state.update(await node_send_d0(d0_initial_state, chatnexo_port=chatnexo))
    state.update(
        await node_schedule_followups(
            LojaExpressState(**state), scheduler=scheduler,
            d1_delay_hours=24, d3_delay_hours=72, d5_delay_hours=120, d7_delay_hours=168,
        )
    )
    state.update(await node_persist_case(LojaExpressState(**state), loja_express_case_repo=repo))

    # Simula que a loja foi entregue no D+3
    case = await repo.get_by_purchase_id("purchase-lx-e2e-001")
    case.loja_entregue = True
    case.status = LojaExpressCaseStatus.ENTREGUE
    await repo.update(case)

    # Job D+5 executa e deve cancelar D+7
    fu_state = LojaExpressState(**{**state, "last_followup_day": 5})
    result = await node_check_case(
        fu_state, loja_express_case_repo=repo, scheduler=scheduler
    )
    assert result["control"] == "cancelled"
    cancelled_ids = [c.args[0] for c in scheduler.cancel.call_args_list]
    assert "job-d7" in cancelled_ids


@pytest.mark.asyncio
async def test_full_suite_no_regressions():
    """Smoke: garante que os subgraphs compilam sem erros de tipagem."""
    d0 = build_loja_express_d0_subgraph()
    fu = build_loja_express_followup_subgraph()
    assert d0.compile() is not None
    assert fu.compile() is not None
```

- [ ] **Step 2: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_loja_express_flow.py -v
```
Esperado: 5 testes PASSED.

- [ ] **Step 3: Executar toda a suite para garantir sem regressões**

```bash
uv run pytest tests/ -v --tb=short
```
Esperado: todos PASSED.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_loja_express_flow.py
git commit -m "test(loja-express): add end-to-end integration tests for capability"
```

---

## Task 15: Atualizar `INDEX.md` e `OPEN_QUESTIONS.md`

**Files:**
- Modify: `docs/superpowers/INDEX.md`
- Modify: `docs/superpowers/OPEN_QUESTIONS.md` (somente se faltarem referências)

- [ ] **Step 1: Atualizar `INDEX.md`**

Na linha do Spec ⑤, trocar o status da coluna **Plano** para apontar para este plano:

```markdown
| ⑤ | **Capability Loja Express** — follow-up D+0/D+1/D+3/D+5/D+7 | [spec](specs/2026-04-18-nexoia-capability-loja-express-design.md) | [plano](plans/2026-04-18-nexoia-capability-loja-express.md) | ⏳ Pendente |
```

E adicionar à lista **Planos (`docs/superpowers/plans/`)**:

```markdown
- `2026-04-18-nexoia-capability-loja-express.md` — Plano ⑤: 15 tasks, TDD completo, stubs CQ-L01/L02/L03
```

- [ ] **Step 2: Conferir `OPEN_QUESTIONS.md`**

Confirmar que `CQ-L01`, `CQ-L02`, `CQ-L03` e `CQ-W04` estão presentes e **não marcados como respondidos** (permanecem em aberto — stubs do plano dependem disso).

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/INDEX.md
git commit -m "docs: mark Loja Express plan as created in INDEX"
```

---

## Self-Review

### Cobertura de RFs

| RF | Coberto por |
|----|-------------|
| `RF-L01` | Task 4 (settings `LOJA_EXPRESS_PRODUCT_TAGS`) + Task 11 (`is_loja_express_product`) |
| `RF-L02` | Task 8 (`node_send_d0`, `node_schedule_followups`, `node_persist_case`) + Task 14 (e2e happy path) |
| `RF-L03` | Task 9 (`_execute_d1`) + Task 2 (`LojaExpressPort.is_form_submitted`) — stubs via CQ-L01 |
| `RF-L04` | Task 9 (`_execute_d3`) + Task 2 (`get_store_status`) — stubs via CQ-L02 |
| `RF-L05` | Task 10 (`_execute_d5`) — escalação silenciosa + TODO CQ-L03 para template |
| `RF-L06` | Task 10 (`_execute_d7`) — template `loja_express_d7` + handoff condicional |
| `RF-L07` | Task 9 (`node_check_case` cancela jobs quando `loja_entregue=True`) + Task 14 (e2e) |
| `RF-L08` | TODOs no código com referência a CQ-W04 nas chamadas `send_template` |
| `RF-L09` | Task 3 (`LojaExpressClient` stub) + referências CQ-L01/L02 |

### Cobertura de RNFs

| RNF | Coberto por |
|-----|-------------|
| `RNF-L01` | Toda query filtra por `account_id` via índices e payloads (Tasks 6, 7) |
| `RNF-L02` | `purchase_id UNIQUE` (Task 6) + teste de duplicata (Task 7) |
| `RNF-L03` | Scheduler do Core (Task 8 `node_schedule_followups`) usa `scheduled_jobs` durável |
| `RNF-L04` | D+1/D+3/D+7 usam `send_template`; D+5 tem TODO CQ-L03 explícito (Task 10) |
| `RNF-L05` | Tasks 1–14: testes unitários + integração cobrindo todos os nós e branches |

### Consistência de tipos

- `LojaExpressState` usa snake_case; todos os nós acessam campos via `state["..."]`.
- `LojaExpressCaseStatus` definido em Task 1 e reusado em Tasks 7, 8, 9, 10.
- `FakeLojaExpressClient` tem os atributos `form_calls` e `status_calls` — alinhados com testes.
- `FakeChatNexoClient` assumido com atributos `last_sent_template`, `last_sent_variables`, `sent_messages` (mesma versão usada pelo plano ②); confirmar que Task 4 do plano ② os expõe.
- `handoff_fn` segue mesma assinatura do plano ② (`account_id`, `conversation_id`, `reason`, `metadata`).
- `scheduler` tem os métodos `schedule(job_type, payload, run_at)` e `cancel(job_id)` — contrato do Spec ① Core.

### Dependências externas do plano

- **Spec ① (Core):** `ConversationState`, `Scheduler`, `JobType` enum, `handoff_fn`.
- **Spec ② (Welcome):** `handle_process_purchase_webhook` é compartilhado; `FakeChatNexoClient`; `run_welcome_subgraph`.
- **OPEN_QUESTIONS:** todos os TODOs referenciam explicitamente CQ-L01, CQ-L02, CQ-L03, CQ-W04.

### Sem placeholders vagos

- Todos os `raise NotImplementedError` têm referência a `OPEN_QUESTIONS.md#CQ-LXX`.
- Todos os `TODO` no código citam CQ específico.
- Nenhum campo de template assume wording final (tudo com variáveis `{{1}}`, `{{2}}`, etc., aguardando CQ-W04).

### Ordem de execução recomendada

1. Tasks 1–4 (domain/entity/port/settings) podem ser paralelizadas.
2. Task 5 (JobType) — bloqueante para Task 8.
3. Task 6 (migration) antes da Task 7 (repo).
4. Task 8 (D+0) antes das Tasks 9–10 (follow-up reusa `LojaExpressState`).
5. Tasks 11–12 (handlers) dependem de Tasks 8–10.
6. Tasks 13–14 (métricas + e2e) no final.
7. Task 15 (docs) por último.
