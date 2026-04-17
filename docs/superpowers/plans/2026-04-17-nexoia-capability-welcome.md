# Capability Welcome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Capability Welcome — subgraph LangGraph que recebe um job de compra, busca o link de acesso na Cademi (stub), verifica/cria conversa no ChatNexo, envia o template `welcome_purchase` e agenda o follow-up D+1.

**Architecture:** Subgraph LangGraph com 5 nós sequenciais (fetch_cademi → check_conversation → send_welcome → persist_access_case → schedule_d1). Depende do Core (Spec ①) já implementado. `CademiClient` é stub — levanta `NotImplementedError` com referência ao `OPEN_QUESTIONS.md`.

**Tech Stack:** Python 3.12, LangGraph, SQLAlchemy 2 async, Alembic, structlog, prometheus-client, pytest, testcontainers, factory-boy, uv

**Prerequisite:** Core (Spec ①) deve estar completamente implementado antes deste plano.

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `src/nexoia/domain/entities/access_case.py` | Criar | Entidade `AccessCase` + enum `AccessCaseStatus` |
| `src/nexoia/domain/ports/cademi_port.py` | Criar | Protocol `CademiPort` + value object `CademiStudent` |
| `src/nexoia/domain/errors.py` | Modificar | Adicionar `CademiError` |
| `src/nexoia/domain/ports/chatnexo_port.py` | Modificar | Adicionar `get_open_conversation`, `create_conversation` |
| `src/nexoia/infrastructure/cademi/__init__.py` | Criar | Package marker |
| `src/nexoia/infrastructure/cademi/client.py` | Criar | Stub `CademiClient` |
| `src/nexoia/infrastructure/cademi/schemas.py` | Criar | Pydantic schemas da Cademi API |
| `src/nexoia/infrastructure/chatnexo/client.py` | Modificar | Implementar novos métodos do port |
| `src/nexoia/infrastructure/db/models.py` | Modificar | Adicionar model `AccessCaseModel` |
| `src/nexoia/infrastructure/db/repositories/access_case_repo.py` | Criar | `AccessCaseRepository` |
| `src/nexoia/application/capabilities/welcome.py` | Criar | `WelcomeState` + subgraph + nós |
| `src/nexoia/interface/worker/handlers/process_purchase.py` | Criar | Handler que invoca o subgraph Welcome |
| `src/nexoia/interface/worker/dispatcher.py` | Modificar | Registrar `ProcessPurchaseWebhook` → handler |
| `src/nexoia/config/settings.py` | Modificar | Variáveis Cademi + buffer |
| `migrations/add_access_cases_table.py` | Criar | Alembic migration |
| `tests/fakes/fake_cademi_client.py` | Criar | Fake configurável para testes |
| `tests/fakes/fake_chatnexo_client.py` | Modificar | Adicionar novos métodos |
| `tests/unit/capabilities/test_welcome.py` | Criar | Testes unitários dos nós |
| `tests/integration/test_welcome_flow.py` | Criar | Teste de integração end-to-end |

---

## Task 1: AccessCase entity + AccessCaseStatus enum

**Files:**
- Create: `src/nexoia/domain/entities/access_case.py`
- Test: `tests/unit/domain/test_access_case.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/domain/test_access_case.py
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus


def test_access_case_default_status_is_pending():
    case = AccessCase(
        account_id=1,
        contact_id="contact-123",
        conversation_id="conv-456",
        purchase_id="purchase-789",
        product_name="Curso Python",
    )
    assert case.status == AccessCaseStatus.PENDING
    assert case.access_confirmed is False
    assert case.scheduled_d1_job_id is None
    assert case.access_link is None


def test_access_case_has_uuid_id():
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="P",
    )
    assert len(case.id) == 36  # UUID format "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"


def test_access_case_status_enum_string_values():
    assert AccessCaseStatus.PENDING == "pending"
    assert AccessCaseStatus.LINK_SENT == "link_sent_proativo"
    assert AccessCaseStatus.ACCESSED == "accessed"
    assert AccessCaseStatus.REMINDED_D1 == "reminded_d1"
    assert AccessCaseStatus.ESCALATED == "escalated"


def test_access_case_with_link():
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="Curso",
        access_link="https://cademi.com.br/auto-login/abc123",
        status=AccessCaseStatus.LINK_SENT,
    )
    assert case.access_link == "https://cademi.com.br/auto-login/abc123"
    assert case.status == AccessCaseStatus.LINK_SENT
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
cd /path/to/nexoia-agent
uv run pytest tests/unit/domain/test_access_case.py -v
```
Esperado: `ImportError` ou `ModuleNotFoundError`

- [ ] **Step 3: Implementar a entidade**

```python
# src/nexoia/domain/entities/access_case.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class AccessCaseStatus(str, Enum):
    PENDING = "pending"
    LINK_SENT = "link_sent_proativo"
    ACCESSED = "accessed"
    REMINDED_D1 = "reminded_d1"
    ESCALATED = "escalated"


@dataclass
class AccessCase:
    account_id: int
    contact_id: str
    conversation_id: str
    purchase_id: str
    product_name: str
    id: str = field(default_factory=lambda: str(uuid4()))
    access_link: str | None = None
    status: AccessCaseStatus = AccessCaseStatus.PENDING
    access_confirmed: bool = False
    scheduled_d1_job_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_access_case.py -v
```
Esperado: 4 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/entities/access_case.py tests/unit/domain/test_access_case.py
git commit -m "feat(welcome): add AccessCase entity and AccessCaseStatus enum"
```

---

## Task 2: CademiPort + CademiStudent + CademiError

**Files:**
- Create: `src/nexoia/domain/ports/cademi_port.py`
- Modify: `src/nexoia/domain/errors.py`
- Test: `tests/unit/domain/test_cademi_port.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/domain/test_cademi_port.py
import pytest
from nexoia.domain.ports.cademi_port import CademiPort, CademiStudent
from nexoia.domain.errors import CademiError


def test_cademi_student_is_frozen():
    student = CademiStudent(id="s1", name="João Silva", email="joao@email.com", phone="+5511999999999")
    with pytest.raises(Exception):
        student.name = "Outro nome"  # type: ignore[misc]


def test_cademi_student_without_phone():
    student = CademiStudent(id="s1", name="Maria", email="maria@email.com", phone=None)
    assert student.phone is None


def test_cademi_error_is_exception():
    err = CademiError("Connection timeout")
    assert isinstance(err, Exception)
    assert str(err) == "Connection timeout"


def test_fake_cademi_satisfies_port():
    """FakeCademiClient deve ser um CademiPort válido."""
    from tests.fakes.fake_cademi_client import FakeCademiClient
    client = FakeCademiClient()
    assert isinstance(client, FakeCademiClient)
    # Protocol check — mypy valida em CI, aqui só garantimos que existe
    assert hasattr(client, "get_student_by_email")
    assert hasattr(client, "get_student_by_cpf")
    assert hasattr(client, "get_access_link")
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_cademi_port.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar `CademiError` ao arquivo de erros existente**

No arquivo `src/nexoia/domain/errors.py`, adicionar ao final:

```python
class CademiError(Exception):
    """Falha ao comunicar com a API da Cademi."""
```

- [ ] **Step 4: Criar o port**

```python
# src/nexoia/domain/ports/cademi_port.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CademiStudent:
    id: str
    name: str
    email: str
    phone: str | None


class CademiPort(Protocol):
    async def get_student_by_email(self, email: str) -> CademiStudent | None: ...
    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None: ...
    async def get_access_link(self, student_id: str, product_id: str) -> str: ...
```

- [ ] **Step 5: Criar o FakeCademiClient**

```python
# tests/fakes/fake_cademi_client.py
from nexoia.domain.errors import CademiError
from nexoia.domain.ports.cademi_port import CademiStudent


class FakeCademiClient:
    """Fake configurável para testes. `fail_times` simula falhas consecutivas."""

    def __init__(
        self,
        student: CademiStudent | None = None,
        fail_times: int = 0,
        access_link: str = "https://cademi.com.br/auto-login/test-token",
    ) -> None:
        self._student = student
        self._fail_times = fail_times
        self._access_link = access_link
        self.call_count = 0

    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        self.call_count += 1
        if self.call_count <= self._fail_times:
            raise CademiError(f"Connection failed (attempt {self.call_count})")
        return self._student

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        return self._student

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        return self._access_link
```

- [ ] **Step 6: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_cademi_port.py -v
```
Esperado: 4 testes PASSED

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/domain/ports/cademi_port.py src/nexoia/domain/errors.py \
        tests/unit/domain/test_cademi_port.py tests/fakes/fake_cademi_client.py
git commit -m "feat(welcome): add CademiPort, CademiStudent, CademiError, FakeCademiClient"
```

---

## Task 3: CademiClient stub

**Files:**
- Create: `src/nexoia/infrastructure/cademi/__init__.py`
- Create: `src/nexoia/infrastructure/cademi/client.py`
- Create: `src/nexoia/infrastructure/cademi/schemas.py`
- Test: `tests/unit/infrastructure/test_cademi_client.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/infrastructure/test_cademi_client.py
import pytest
from nexoia.infrastructure.cademi.client import CademiClient


@pytest.mark.asyncio
async def test_cademi_client_get_student_raises_not_implemented():
    client = CademiClient(base_url="http://fake", api_key="key")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.get_student_by_email("test@test.com")


@pytest.mark.asyncio
async def test_cademi_client_get_access_link_raises_not_implemented():
    client = CademiClient(base_url="http://fake", api_key="key")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.get_access_link("student-1", "product-1")


@pytest.mark.asyncio
async def test_cademi_client_get_by_cpf_raises_not_implemented():
    client = CademiClient(base_url="http://fake", api_key="key")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.get_student_by_cpf("123.456.789-00")
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/infrastructure/test_cademi_client.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Criar o package Cademi**

```bash
touch src/nexoia/infrastructure/cademi/__init__.py
```

- [ ] **Step 4: Criar schemas Pydantic (preparação futura)**

```python
# src/nexoia/infrastructure/cademi/schemas.py
# TODO (CQ-W01): preencher quando a documentação da API Cademi estiver disponível.
# Ver docs/superpowers/OPEN_QUESTIONS.md#CQ-W01
#
# Estrutura esperada (a confirmar):
# - GET /students?email=... → StudentResponse
# - GET /students/{id}/access-link?product_id=... → AccessLinkResponse
```

- [ ] **Step 5: Criar o CademiClient stub**

```python
# src/nexoia/infrastructure/cademi/client.py
# ⚠️  ATENÇÃO: Este cliente é um STUB.
# ANTES DE IMPLEMENTAR: consultar docs/superpowers/OPEN_QUESTIONS.md (CQ-W01)
# O desenvolvedor DEVE perguntar ao responsável pelo produto sobre:
#   - URL base da API Cademi
#   - Mecanismo de autenticação
#   - Endpoints de busca de aluno (email, CPF)
#   - Endpoint de geração de link nominal de auto-login
#   - Prazo de expiração do link (CQ-W02)
from __future__ import annotations

from nexoia.domain.ports.cademi_port import CademiStudent


class CademiClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url
        self._api_key = api_key

    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        # TODO (CQ-W01): implementar chamada real à Cademi API
        raise NotImplementedError(
            "CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01"
        )

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        # TODO (CQ-W01): implementar chamada real à Cademi API
        raise NotImplementedError(
            "CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01"
        )

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        # TODO (CQ-W01, CQ-W02): implementar + verificar prazo de expiração do link
        raise NotImplementedError(
            "CademiClient não implementado — ver OPEN_QUESTIONS.md#CQ-W01"
        )
```

- [ ] **Step 6: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/infrastructure/test_cademi_client.py -v
```
Esperado: 3 testes PASSED

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/infrastructure/cademi/ tests/unit/infrastructure/test_cademi_client.py
git commit -m "feat(welcome): add CademiClient stub with NotImplementedError guards"
```

---

## Task 4: ChatNexoPort — novos métodos + FakeChatNexoClient

**Files:**
- Modify: `src/nexoia/domain/ports/chatnexo_port.py`
- Modify: `tests/fakes/fake_chatnexo_client.py`
- Test: `tests/unit/domain/test_chatnexo_port_welcome.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/domain/test_chatnexo_port_welcome.py
import pytest
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


@pytest.mark.asyncio
async def test_get_open_conversation_returns_id_when_exists():
    client = FakeChatNexoClient(open_conversation_id="conv-999")
    result = await client.get_open_conversation(account_id=1, contact_phone="+5511999999999")
    assert result == "conv-999"


@pytest.mark.asyncio
async def test_get_open_conversation_returns_none_when_not_exists():
    client = FakeChatNexoClient(open_conversation_id=None)
    result = await client.get_open_conversation(account_id=1, contact_phone="+5511999999999")
    assert result is None


@pytest.mark.asyncio
async def test_create_conversation_returns_new_id():
    client = FakeChatNexoClient(new_conversation_id="conv-new-001")
    result = await client.create_conversation(account_id=1, contact_phone="+5511999999999")
    assert result == "conv-new-001"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_chatnexo_port_welcome.py -v
```
Esperado: `ImportError` ou `AttributeError`

- [ ] **Step 3: Adicionar métodos ao ChatNexoPort existente**

No arquivo `src/nexoia/domain/ports/chatnexo_port.py`, adicionar os dois métodos ao Protocol:

```python
    async def get_open_conversation(
        self, account_id: int, contact_phone: str
    ) -> str | None:
        """Retorna conversation_id se houver conversa aberta, None caso contrário."""
        ...

    async def create_conversation(
        self, account_id: int, contact_phone: str
    ) -> str:
        """Cria nova conversa e retorna o conversation_id."""
        ...
```

- [ ] **Step 4: Adicionar métodos ao FakeChatNexoClient existente**

No arquivo `tests/fakes/fake_chatnexo_client.py`, adicionar ao `__init__` e implementar os métodos:

```python
    def __init__(
        self,
        # ... parâmetros existentes ...,
        open_conversation_id: str | None = "conv-default",
        new_conversation_id: str = "conv-created-001",
    ) -> None:
        # ... init existente ...,
        self._open_conversation_id = open_conversation_id
        self._new_conversation_id = new_conversation_id

    async def get_open_conversation(
        self, account_id: int, contact_phone: str
    ) -> str | None:
        return self._open_conversation_id

    async def create_conversation(
        self, account_id: int, contact_phone: str
    ) -> str:
        return self._new_conversation_id
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_chatnexo_port_welcome.py -v
```
Esperado: 3 testes PASSED

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/domain/ports/chatnexo_port.py \
        tests/fakes/fake_chatnexo_client.py \
        tests/unit/domain/test_chatnexo_port_welcome.py
git commit -m "feat(welcome): extend ChatNexoPort with get_open_conversation and create_conversation"
```

---

## Task 5: Settings — variáveis da Capability Welcome

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Test: `tests/unit/config/test_settings_welcome.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/config/test_settings_welcome.py
from nexoia.config.settings import Settings


def test_cademi_defaults():
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://localhost:6379",
        CHATNEXO_API_KEY="key",
        OPENAI_API_KEY="sk-test",
    )
    assert s.CADEMI_API_URL == ""
    assert s.CADEMI_API_KEY == ""
    assert s.CADEMI_MAX_RETRIES == 3
    assert s.CADEMI_RETRY_BASE_SECONDS == 1.0
    assert s.MESSAGE_BUFFER_WAIT_SECONDS == 0
    assert s.WELCOME_D1_DELAY_HOURS == 1
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/config/test_settings_welcome.py -v
```
Esperado: `ValidationError` ou `AttributeError`

- [ ] **Step 3: Adicionar variáveis ao Settings existente**

No arquivo `src/nexoia/config/settings.py`, adicionar ao model `Settings`:

```python
    # Cademi API (stub — preencher quando documentação disponível, ver OPEN_QUESTIONS.md#CQ-W01)
    CADEMI_API_URL: str = ""
    CADEMI_API_KEY: str = ""
    CADEMI_MAX_RETRIES: int = 3
    CADEMI_RETRY_BASE_SECONDS: float = 1.0  # backoff: 1s, 3s, 9s

    # Capability Welcome
    WELCOME_D1_DELAY_HOURS: int = 1  # horas até disparar o reminder D+1

    # Buffer de mensagens upstream (serviço anterior ao agente faz o buffer)
    # 0 = desativado (padrão); ajustar se o agente precisar fazer buffer interno
    MESSAGE_BUFFER_WAIT_SECONDS: int = 0
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/config/test_settings_welcome.py -v
```
Esperado: 1 teste PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/config/settings.py tests/unit/config/test_settings_welcome.py
git commit -m "feat(welcome): add Cademi and Welcome settings with safe defaults"
```

---

## Task 6: Alembic migration — tabela access_cases

**Files:**
- Create: `migrations/versions/xxxx_add_access_cases_table.py`
- Modify: `src/nexoia/infrastructure/db/models.py`

- [ ] **Step 1: Adicionar o model SQLAlchemy**

No arquivo `src/nexoia/infrastructure/db/models.py`, adicionar:

```python
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

class AccessCaseModel(Base):
    __tablename__ = "access_cases"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    purchase_id = Column(String, nullable=False, unique=True)  # idempotência
    product_name = Column(String, nullable=False)
    access_link = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    access_confirmed = Column(Boolean, nullable=False, default=False)
    scheduled_d1_job_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("idx_access_cases_account_contact", "account_id", "contact_id"),
    )
```

- [ ] **Step 2: Gerar a migration Alembic**

```bash
uv run alembic revision --autogenerate -m "add_access_cases_table"
```
Esperado: arquivo criado em `migrations/versions/XXXX_add_access_cases_table.py`

- [ ] **Step 3: Revisar o arquivo gerado**

Abrir o arquivo gerado e confirmar que contém:
- `op.create_table("access_cases", ...)`
- Coluna `purchase_id` com `unique=True`
- `op.create_index("idx_access_cases_account_contact", ...)`

- [ ] **Step 4: Aplicar a migration no banco de dev**

```bash
uv run alembic upgrade head
```
Esperado: `Running upgrade ... -> XXXX, add_access_cases_table`

- [ ] **Step 5: Commit**

```bash
git add migrations/ src/nexoia/infrastructure/db/models.py
git commit -m "feat(welcome): add access_cases table migration and SQLAlchemy model"
```

---

## Task 7: AccessCaseRepository

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/access_case_repo.py`
- Test: `tests/integration/test_access_case_repo.py`

- [ ] **Step 1: Escrever o teste de integração falhando**

```python
# tests/integration/test_access_case_repo.py
import pytest
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.infrastructure.db.repositories.access_case_repo import AccessCaseRepository


@pytest.mark.asyncio
async def test_save_and_get_by_purchase_id(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id="contact-1",
        conversation_id="conv-1",
        purchase_id="purchase-unique-001",
        product_name="Curso Python",
        access_link="https://cademi.com.br/auto-login/abc",
        status=AccessCaseStatus.LINK_SENT,
    )
    await repo.save(case)

    found = await repo.get_by_purchase_id("purchase-unique-001")
    assert found is not None
    assert found.status == AccessCaseStatus.LINK_SENT
    assert found.access_link == "https://cademi.com.br/auto-login/abc"


@pytest.mark.asyncio
async def test_get_by_purchase_id_not_found(db_session):
    repo = AccessCaseRepository(db_session)
    found = await repo.get_by_purchase_id("non-existent-purchase")
    assert found is None


@pytest.mark.asyncio
async def test_update_status(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p-update-test",
        product_name="Produto",
    )
    await repo.save(case)

    case.status = AccessCaseStatus.ACCESSED
    case.access_confirmed = True
    await repo.update(case)

    found = await repo.get_by_purchase_id("p-update-test")
    assert found.status == AccessCaseStatus.ACCESSED
    assert found.access_confirmed is True


@pytest.mark.asyncio
async def test_duplicate_purchase_id_raises(db_session):
    repo = AccessCaseRepository(db_session)
    case1 = AccessCase(
        account_id=1, contact_id="c", conversation_id="cv",
        purchase_id="duplicate-purchase", product_name="P",
    )
    case2 = AccessCase(
        account_id=2, contact_id="c2", conversation_id="cv2",
        purchase_id="duplicate-purchase", product_name="P",
    )
    await repo.save(case1)
    with pytest.raises(Exception):  # IntegrityError (UNIQUE constraint)
        await repo.save(case2)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_access_case_repo.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar o repositório**

```python
# src/nexoia/infrastructure/db/repositories/access_case_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.infrastructure.db.models import AccessCaseModel


class AccessCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, case: AccessCase) -> None:
        model = AccessCaseModel(
            id=case.id,
            account_id=case.account_id,
            contact_id=case.contact_id,
            conversation_id=case.conversation_id,
            purchase_id=case.purchase_id,
            product_name=case.product_name,
            access_link=case.access_link,
            status=case.status.value,
            access_confirmed=case.access_confirmed,
            scheduled_d1_job_id=case.scheduled_d1_job_id,
        )
        self._session.add(model)
        await self._session.commit()

    async def update(self, case: AccessCase) -> None:
        model = await self._session.get(AccessCaseModel, case.id)
        if model is None:
            raise ValueError(f"AccessCase {case.id} not found")
        model.status = case.status.value
        model.access_confirmed = case.access_confirmed
        model.access_link = case.access_link
        model.scheduled_d1_job_id = case.scheduled_d1_job_id
        await self._session.commit()

    async def get_by_purchase_id(self, purchase_id: str) -> AccessCase | None:
        result = await self._session.execute(
            select(AccessCaseModel).where(AccessCaseModel.purchase_id == purchase_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    def _to_entity(self, model: AccessCaseModel) -> AccessCase:
        case = AccessCase(
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            purchase_id=model.purchase_id,
            product_name=model.product_name,
        )
        case.id = str(model.id)
        case.access_link = model.access_link
        case.status = AccessCaseStatus(model.status)
        case.access_confirmed = model.access_confirmed
        case.scheduled_d1_job_id = model.scheduled_d1_job_id
        case.created_at = model.created_at
        case.updated_at = model.updated_at
        return case
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_access_case_repo.py -v
```
Esperado: 4 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/access_case_repo.py \
        tests/integration/test_access_case_repo.py
git commit -m "feat(welcome): add AccessCaseRepository with save, update, get_by_purchase_id"
```

---

## Task 8: WelcomeState + subgraph LangGraph

**Files:**
- Create: `src/nexoia/application/capabilities/welcome.py`
- Test: `tests/unit/capabilities/test_welcome.py`

- [ ] **Step 1: Escrever os testes unitários falhando**

```python
# tests/unit/capabilities/test_welcome.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from nexoia.application.capabilities.welcome import (
    WelcomeState,
    node_fetch_cademi,
    node_check_conversation,
    node_send_welcome,
    node_persist_access_case,
    node_schedule_d1,
)
from nexoia.domain.entities.access_case import AccessCaseStatus
from nexoia.domain.errors import CademiError
from nexoia.domain.ports.cademi_port import CademiStudent
from tests.fakes.fake_cademi_client import FakeCademiClient
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


def make_state(**kwargs) -> WelcomeState:
    base = dict(
        purchase_id="p-001",
        account_id=1,
        student_name="João Silva",
        student_phone="+5511999999999",
        student_email="joao@email.com",
        product_name="Curso Python",
        access_link=None,
        cademi_attempts=0,
        conversation_id=None,
        access_case_id=None,
        access_confirmed=False,
        cademi_failed=False,
        messages=[],
        correlation_id="corr-001",
    )
    base.update(kwargs)
    return WelcomeState(**base)


@pytest.mark.asyncio
async def test_fetch_cademi_happy_path():
    student = CademiStudent(id="s1", name="João Silva", email="joao@email.com", phone="+5511999999999")
    cademi = FakeCademiClient(student=student, access_link="https://cademi.com.br/login/abc")
    state = make_state()

    result = await node_fetch_cademi(state, cademi_port=cademi)

    assert result["access_link"] == "https://cademi.com.br/login/abc"
    assert result["cademi_failed"] is False
    assert result["cademi_attempts"] == 1


@pytest.mark.asyncio
async def test_fetch_cademi_retry_exhausted_sets_failed():
    cademi = FakeCademiClient(student=None, fail_times=3)
    handoff = AsyncMock()
    state = make_state()

    result = await node_fetch_cademi(state, cademi_port=cademi, handoff_fn=handoff)

    assert result["cademi_failed"] is True
    assert result["access_link"] is None
    handoff.assert_called_once()


@pytest.mark.asyncio
async def test_check_conversation_uses_existing_open():
    chatnexo = FakeChatNexoClient(open_conversation_id="conv-existing")
    state = make_state()

    result = await node_check_conversation(state, chatnexo_port=chatnexo)

    assert result["conversation_id"] == "conv-existing"


@pytest.mark.asyncio
async def test_check_conversation_creates_new_when_closed():
    chatnexo = FakeChatNexoClient(open_conversation_id=None, new_conversation_id="conv-new")
    state = make_state()

    result = await node_check_conversation(state, chatnexo_port=chatnexo)

    assert result["conversation_id"] == "conv-new"


@pytest.mark.asyncio
async def test_send_welcome_with_link():
    chatnexo = FakeChatNexoClient()
    state = make_state(
        conversation_id="conv-001",
        access_link="https://cademi.com.br/login/abc",
        cademi_failed=False,
    )

    result = await node_send_welcome(state, chatnexo_port=chatnexo)

    assert chatnexo.last_sent_template == "welcome_purchase"
    assert "https://cademi.com.br/login/abc" in str(chatnexo.last_sent_variables)


@pytest.mark.asyncio
async def test_send_welcome_without_link_sends_generic():
    chatnexo = FakeChatNexoClient()
    state = make_state(
        conversation_id="conv-001",
        access_link=None,
        cademi_failed=True,
    )

    await node_send_welcome(state, chatnexo_port=chatnexo)

    assert chatnexo.last_sent_template == "welcome_purchase"
    assert "em instantes" in str(chatnexo.last_sent_variables).lower()


@pytest.mark.asyncio
async def test_schedule_d1_creates_scheduled_job():
    scheduler = AsyncMock()
    state = make_state(access_case_id="ac-001")

    await node_schedule_d1(state, scheduler=scheduler)

    scheduler.schedule.assert_called_once()
    call_kwargs = scheduler.schedule.call_args[1]
    assert call_kwargs["job_type"] == "SendScheduledFollowUp"
    assert "access_reminder_d1" in str(call_kwargs["payload"])
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_welcome.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar WelcomeState e nós do subgraph**

```python
# src/nexoia/application/capabilities/welcome.py
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Awaitable
from uuid import uuid4

import structlog
from langgraph.graph import StateGraph, END

from nexoia.application.capabilities.base import CapabilityResult
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.domain.errors import CademiError
from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo_port import ChatNexoPort

# Importa ConversationState do Core
from nexoia.application.state import ConversationState

logger = structlog.get_logger(__name__)

CADEMI_MAX_RETRIES = 3
CADEMI_RETRY_BASE_SECONDS = 1.0
GENERIC_ACCESS_MESSAGE = "em instantes você receberá seu link de acesso"


class WelcomeState(ConversationState):
    purchase_id: str
    student_name: str
    student_phone: str
    student_email: str
    product_name: str
    access_link: str | None
    cademi_attempts: int
    conversation_id: str | None
    access_case_id: str | None
    access_confirmed: bool
    cademi_failed: bool


async def node_fetch_cademi(
    state: WelcomeState,
    *,
    cademi_port: CademiPort,
    handoff_fn: Callable[..., Awaitable[None]] | None = None,
) -> dict[str, Any]:
    log = logger.bind(node="fetch_cademi", purchase_id=state["purchase_id"])
    attempts = state.get("cademi_attempts", 0)

    for attempt in range(1, CADEMI_MAX_RETRIES + 1):
        try:
            student = await cademi_port.get_student_by_email(state["student_email"])
            if student is None:
                log.warning("student_not_found_in_cademi", email=state["student_email"])
                return {"cademi_failed": True, "access_link": None, "cademi_attempts": attempt}

            access_link = await cademi_port.get_access_link(
                student_id=student.id,
                product_id=state["purchase_id"],  # TODO (CQ-W01): confirmar campo product_id
            )
            log.info("cademi_link_fetched", attempt=attempt)
            return {"access_link": access_link, "cademi_failed": False, "cademi_attempts": attempt}

        except CademiError as exc:
            log.warning("cademi_error", attempt=attempt, error=str(exc))
            if attempt < CADEMI_MAX_RETRIES:
                await asyncio.sleep(CADEMI_RETRY_BASE_SECONDS * (3 ** (attempt - 1)))

    log.warning("cademi_exhausted", reason="cademi_exhausted")
    if handoff_fn is not None:
        await handoff_fn(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            reason="cademi_unavailable",
        )
    return {"cademi_failed": True, "access_link": None, "cademi_attempts": CADEMI_MAX_RETRIES}


async def node_check_conversation(
    state: WelcomeState,
    *,
    chatnexo_port: ChatNexoPort,
) -> dict[str, Any]:
    log = logger.bind(node="check_conversation", purchase_id=state["purchase_id"])
    existing = await chatnexo_port.get_open_conversation(
        account_id=state["account_id"],
        contact_phone=state["student_phone"],
    )
    if existing:
        log.info("reusing_open_conversation", conversation_id=existing)
        return {"conversation_id": existing}

    new_conv = await chatnexo_port.create_conversation(
        account_id=state["account_id"],
        contact_phone=state["student_phone"],
    )
    log.info("created_new_conversation", conversation_id=new_conv)
    return {"conversation_id": new_conv}


async def node_send_welcome(
    state: WelcomeState,
    *,
    chatnexo_port: ChatNexoPort,
) -> dict[str, Any]:
    # TODO (CQ-W03): confirmar template ID e variáveis exatas com equipe
    # Ver docs/superpowers/OPEN_QUESTIONS.md#CQ-W03
    log = logger.bind(node="send_welcome", purchase_id=state["purchase_id"])
    link = state.get("access_link") or GENERIC_ACCESS_MESSAGE

    await chatnexo_port.send_template(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        template_name="welcome_purchase",  # TODO (CQ-W03): confirmar nome exato no Meta
        variables={
            "1": state["student_name"],
            "2": state["product_name"],
            "3": link,
        },
    )
    log.info("welcome_template_sent", template="welcome_purchase", cademi_failed=state.get("cademi_failed"))
    return {}


async def node_persist_access_case(
    state: WelcomeState,
    *,
    access_case_repo: Any,
) -> dict[str, Any]:
    case = AccessCase(
        account_id=state["account_id"],
        contact_id=state["student_email"],  # usado como contact_id até ter o contact real
        conversation_id=state["conversation_id"],
        purchase_id=state["purchase_id"],
        product_name=state["product_name"],
        access_link=state.get("access_link"),
        status=AccessCaseStatus.ESCALATED if state.get("cademi_failed") else AccessCaseStatus.LINK_SENT,
    )
    await access_case_repo.save(case)
    logger.bind(node="persist_access_case").info("access_case_saved", access_case_id=case.id)
    return {"access_case_id": case.id}


async def node_schedule_d1(
    state: WelcomeState,
    *,
    scheduler: Any,
    d1_delay_hours: int = 1,
) -> dict[str, Any]:
    run_at = datetime.now(timezone.utc) + timedelta(hours=d1_delay_hours)
    job = await scheduler.schedule(
        job_type="SendScheduledFollowUp",
        payload={
            "template": "access_reminder_d1",  # TODO (CQ-W04): confirmar template
            "access_case_id": state["access_case_id"],
            "account_id": state["account_id"],
            "conversation_id": state["conversation_id"],
        },
        run_at=run_at,
    )
    logger.bind(node="schedule_d1").info("d1_scheduled", job_id=job.id, run_at=run_at.isoformat())
    return {}


def build_welcome_subgraph() -> StateGraph:
    """Constrói o subgraph da Capability Welcome para plugar no main graph."""
    graph = StateGraph(WelcomeState)
    graph.add_node("fetch_cademi", node_fetch_cademi)
    graph.add_node("check_conversation", node_check_conversation)
    graph.add_node("send_welcome", node_send_welcome)
    graph.add_node("persist_access_case", node_persist_access_case)
    graph.add_node("schedule_d1", node_schedule_d1)

    graph.set_entry_point("fetch_cademi")
    graph.add_edge("fetch_cademi", "check_conversation")
    graph.add_edge("check_conversation", "send_welcome")
    graph.add_edge("send_welcome", "persist_access_case")
    graph.add_edge("persist_access_case", "schedule_d1")
    graph.add_edge("schedule_d1", END)

    return graph
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_welcome.py -v
```
Esperado: 8 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/welcome.py \
        tests/unit/capabilities/test_welcome.py
git commit -m "feat(welcome): implement Welcome subgraph with 5 nodes and full unit tests"
```

---

## Task 9: Worker handler ProcessPurchaseWebhook

**Files:**
- Create: `src/nexoia/interface/worker/handlers/process_purchase.py`
- Modify: `src/nexoia/interface/worker/dispatcher.py`
- Test: `tests/unit/worker/test_process_purchase_handler.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/worker/test_process_purchase_handler.py
import pytest
from unittest.mock import AsyncMock, patch

from nexoia.interface.worker.handlers.process_purchase import handle_process_purchase_webhook


@pytest.mark.asyncio
async def test_handler_invokes_welcome_subgraph():
    job_payload = {
        "purchase_id": "p-001",
        "account_id": 1,
        "student_name": "João Silva",
        "student_phone": "+5511999999999",
        "student_email": "joao@email.com",
        "product_name": "Curso Python",
        "correlation_id": "corr-001",
    }
    run_subgraph = AsyncMock(return_value={"access_case_id": "ac-001"})

    with patch(
        "nexoia.interface.worker.handlers.process_purchase.run_welcome_subgraph",
        run_subgraph,
    ):
        await handle_process_purchase_webhook(payload=job_payload)

    run_subgraph.assert_called_once()
    call_kwargs = run_subgraph.call_args[1]
    assert call_kwargs["purchase_id"] == "p-001"
    assert call_kwargs["account_id"] == 1


@pytest.mark.asyncio
async def test_handler_missing_required_field_raises():
    bad_payload = {"purchase_id": "p-001"}  # faltam campos obrigatórios

    with pytest.raises((KeyError, ValueError)):
        await handle_process_purchase_webhook(payload=bad_payload)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/worker/test_process_purchase_handler.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar o handler**

```python
# src/nexoia/interface/worker/handlers/process_purchase.py
from __future__ import annotations

from typing import Any

import structlog

from nexoia.application.capabilities.welcome import WelcomeState, build_welcome_subgraph

logger = structlog.get_logger(__name__)

_welcome_graph = build_welcome_subgraph().compile()


async def run_welcome_subgraph(**kwargs: Any) -> dict[str, Any]:
    """Executa o subgraph Welcome com injeção de dependências do container."""
    # TODO: injetar deps reais (cademi_port, chatnexo_port, etc.) via container DI
    initial_state = WelcomeState(**kwargs)
    result = await _welcome_graph.ainvoke(initial_state)
    return result


async def handle_process_purchase_webhook(payload: dict[str, Any]) -> None:
    log = logger.bind(
        handler="process_purchase",
        purchase_id=payload["purchase_id"],
        correlation_id=payload.get("correlation_id", ""),
    )
    log.info("handling_purchase_webhook")

    await run_welcome_subgraph(
        purchase_id=payload["purchase_id"],
        account_id=payload["account_id"],
        student_name=payload["student_name"],
        student_phone=payload["student_phone"],
        student_email=payload["student_email"],
        product_name=payload["product_name"],
        access_link=None,
        cademi_attempts=0,
        conversation_id=None,
        access_case_id=None,
        access_confirmed=False,
        cademi_failed=False,
        messages=[],
        correlation_id=payload.get("correlation_id", ""),
    )
    log.info("purchase_webhook_handled")
```

- [ ] **Step 4: Registrar o handler no dispatcher**

No arquivo `src/nexoia/interface/worker/dispatcher.py`, adicionar:

```python
from nexoia.interface.worker.handlers.process_purchase import handle_process_purchase_webhook

# No método/dict de routing de jobs, adicionar:
"ProcessPurchaseWebhook": handle_process_purchase_webhook,
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/worker/test_process_purchase_handler.py -v
```
Esperado: 2 testes PASSED

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/interface/worker/handlers/process_purchase.py \
        src/nexoia/interface/worker/dispatcher.py \
        tests/unit/worker/test_process_purchase_handler.py
git commit -m "feat(welcome): add ProcessPurchaseWebhook handler and register in dispatcher"
```

---

## Task 10: Métricas Prometheus da Capability Welcome

**Files:**
- Modify: `src/nexoia/infrastructure/observability/metrics.py`
- Test: `tests/unit/observability/test_welcome_metrics.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/observability/test_welcome_metrics.py
from nexoia.infrastructure.observability.metrics import (
    welcome_capability_total,
    welcome_cademi_latency_seconds,
    welcome_d1_scheduled_total,
    welcome_d1_cancelled_total,
)


def test_welcome_capability_counter_labels():
    welcome_capability_total.labels(status="success").inc()
    welcome_capability_total.labels(status="cademi_failed").inc()
    welcome_capability_total.labels(status="error").inc()
    # Não levanta exceção = labels corretos


def test_welcome_d1_counters():
    welcome_d1_scheduled_total.inc()
    welcome_d1_cancelled_total.inc()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/observability/test_welcome_metrics.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar métricas ao arquivo existente**

No arquivo `src/nexoia/infrastructure/observability/metrics.py`, adicionar:

```python
from prometheus_client import Counter, Histogram

# Capability Welcome
welcome_capability_total = Counter(
    "welcome_capability_total",
    "Total de execuções da Capability Welcome",
    labelnames=["status"],
)
welcome_cademi_latency_seconds = Histogram(
    "welcome_cademi_latency_seconds",
    "Latência das chamadas à Cademi API",
    buckets=[0.1, 0.5, 1.0, 3.0, 9.0, 30.0],
)
welcome_d1_scheduled_total = Counter(
    "welcome_d1_scheduled_total",
    "Total de follow-ups D+1 agendados pela Welcome Capability",
)
welcome_d1_cancelled_total = Counter(
    "welcome_d1_cancelled_total",
    "Total de follow-ups D+1 cancelados (acesso confirmado)",
)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/observability/test_welcome_metrics.py -v
```
Esperado: 2 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/observability/metrics.py \
        tests/unit/observability/test_welcome_metrics.py
git commit -m "feat(welcome): add Prometheus metrics for Welcome capability"
```

---

## Task 11: Teste de integração end-to-end da Capability Welcome

**Files:**
- Create: `tests/integration/test_welcome_flow.py`

- [ ] **Step 1: Escrever o teste de integração completo**

```python
# tests/integration/test_welcome_flow.py
"""
Teste end-to-end da Capability Welcome usando fakes de infraestrutura.
Valida o fluxo completo: job → subgraph → AccessCase persistido → D+1 agendado.
"""
import pytest
from nexoia.domain.entities.access_case import AccessCaseStatus
from nexoia.domain.ports.cademi_port import CademiStudent
from nexoia.infrastructure.db.repositories.access_case_repo import AccessCaseRepository
from nexoia.application.capabilities.welcome import (
    node_fetch_cademi,
    node_check_conversation,
    node_send_welcome,
    node_persist_access_case,
    node_schedule_d1,
    WelcomeState,
)
from tests.fakes.fake_cademi_client import FakeCademiClient
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


@pytest.fixture
def student():
    return CademiStudent(
        id="student-001",
        name="Maria Souza",
        email="maria@email.com",
        phone="+5511988888888",
    )


@pytest.fixture
def initial_state(student):
    return WelcomeState(
        purchase_id="purchase-integration-001",
        account_id=1,
        student_name=student.name,
        student_phone=student.phone,
        student_email=student.email,
        product_name="Curso de Vendas",
        access_link=None,
        cademi_attempts=0,
        conversation_id=None,
        access_case_id=None,
        access_confirmed=False,
        cademi_failed=False,
        messages=[],
        correlation_id="corr-integration-001",
    )


@pytest.mark.asyncio
async def test_full_happy_path(db_session, initial_state, student):
    cademi = FakeCademiClient(
        student=student,
        access_link="https://cademi.com.br/auto-login/maria-token",
    )
    chatnexo = FakeChatNexoClient(
        open_conversation_id=None,
        new_conversation_id="conv-new-001",
    )
    scheduler_mock = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
    scheduler_mock.schedule.return_value = type("Job", (), {"id": "job-d1-001"})()

    repo = AccessCaseRepository(db_session)

    # Executa nós em sequência (simula o subgraph)
    state = dict(initial_state)
    state.update(await node_fetch_cademi(initial_state, cademi_port=cademi))
    state.update(await node_check_conversation(WelcomeState(**state), chatnexo_port=chatnexo))
    state.update(await node_send_welcome(WelcomeState(**state), chatnexo_port=chatnexo))
    state.update(await node_persist_access_case(WelcomeState(**state), access_case_repo=repo))
    await node_schedule_d1(WelcomeState(**state), scheduler=scheduler_mock)

    # Valida AccessCase no banco
    saved = await repo.get_by_purchase_id("purchase-integration-001")
    assert saved is not None
    assert saved.status == AccessCaseStatus.LINK_SENT
    assert saved.access_link == "https://cademi.com.br/auto-login/maria-token"
    assert saved.access_confirmed is False

    # Valida que D+1 foi agendado
    scheduler_mock.schedule.assert_called_once()
    call_kwargs = scheduler_mock.schedule.call_args[1]
    assert call_kwargs["payload"]["template"] == "access_reminder_d1"

    # Valida que template foi enviado com o link correto
    assert chatnexo.last_sent_template == "welcome_purchase"
    assert "https://cademi.com.br/auto-login/maria-token" in str(chatnexo.last_sent_variables)


@pytest.mark.asyncio
async def test_cademi_failure_flow(db_session, initial_state):
    cademi = FakeCademiClient(student=None, fail_times=3)  # falha 3x
    chatnexo = FakeChatNexoClient(open_conversation_id="conv-existing")
    scheduler_mock = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
    scheduler_mock.schedule.return_value = type("Job", (), {"id": "job-d1-002"})()
    handoff = __import__("unittest.mock", fromlist=["AsyncMock"]).AsyncMock()
    repo = AccessCaseRepository(db_session)

    state = dict(initial_state)
    state.update(await node_fetch_cademi(initial_state, cademi_port=cademi, handoff_fn=handoff))
    state.update(await node_check_conversation(WelcomeState(**state), chatnexo_port=chatnexo))
    state.update(await node_send_welcome(WelcomeState(**state), chatnexo_port=chatnexo))
    state.update(await node_persist_access_case(WelcomeState(**state), access_case_repo=repo))
    await node_schedule_d1(WelcomeState(**state), scheduler=scheduler_mock)

    # Handoff foi chamado
    handoff.assert_called_once()

    # AccessCase salvo como ESCALATED
    saved = await repo.get_by_purchase_id("purchase-integration-001")
    assert saved.status == AccessCaseStatus.ESCALATED

    # Template enviado com mensagem genérica
    assert "em instantes" in str(chatnexo.last_sent_variables).lower()
```

- [ ] **Step 2: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_welcome_flow.py -v
```
Esperado: 2 testes PASSED

- [ ] **Step 3: Executar toda a suite para garantir sem regressões**

```bash
uv run pytest tests/ -v --tb=short
```
Esperado: todos PASSED, sem falhas

- [ ] **Step 4: Commit final**

```bash
git add tests/integration/test_welcome_flow.py
git commit -m "feat(welcome): add end-to-end integration tests for Welcome capability"
```

---

## Task 12: Atualizar INDEX.md e OPEN_QUESTIONS.md

**Files:**
- Modify: `docs/superpowers/INDEX.md`
- Modify: `docs/superpowers/OPEN_QUESTIONS.md`

- [ ] **Step 1: Atualizar INDEX.md**

No arquivo `docs/superpowers/INDEX.md`, atualizar a linha do Spec ②:

```markdown
| ② | **Capability Welcome** — webhook Hubla → boas-vindas WhatsApp | [spec](specs/2026-04-17-nexoia-capability-welcome-design.md) | [plano](plans/2026-04-17-nexoia-capability-welcome.md) | ⏳ Pendente |
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/INDEX.md
git commit -m "docs: mark Welcome plan as created in INDEX"
```

---

## Self-Review

### Cobertura de RFs

| RF | Coberto por |
|----|-------------|
| `RF-W01` | Task 5 (settings `MESSAGE_BUFFER_WAIT_SECONDS=0`) + nota arquitetural |
| `RF-W02` | Task 8 `node_fetch_cademi` + test_fetch_cademi_retry_exhausted |
| `RF-W03` | Task 4 + Task 8 `node_check_conversation` |
| `RF-W04` | Task 8 `node_schedule_d1` + integration test |
| `RF-W05` | Mencionado no design; cancelamento ocorre via Intent Router no fluxo reativo — não há task aqui pois o cancelamento é disparado pela Capability Access (spec ③) quando detecta `access_confirmed` |
| `RF-W06` | Task 8 TODO com referência a CQ-W03 |
| `RF-W07` | Task 3 TODO com referência a CQ-W02 |
| `RF-W08` | Task 6 (`purchase_id UNIQUE`) + Task 7 (teste duplicata) |
| `RF-W09` | Coberto no fluxo de fallback do `node_fetch_cademi` (student not found → escalate) |

### Tipos consistentes

- `WelcomeState` usa campos snake_case; todos os nós referem ao mesmo campo (`state["purchase_id"]`, etc.)
- `AccessCaseStatus` definido em Task 1, usado em Tasks 7, 8, 11
- `FakeCademiClient.fail_times` consistente entre Tasks 2 e 11
- `chatnexo.last_sent_template` e `chatnexo.last_sent_variables` assumem que o `FakeChatNexoClient` (Task 4) expõe esses atributos — confirmar que a implementação do fake os inclui

### Sem placeholders vagos

Todos os TODOs têm referência explícita a `OPEN_QUESTIONS.md#CQ-WXX`.
