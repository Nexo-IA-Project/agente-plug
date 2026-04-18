# Capability Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Capability Access — subgraph LangGraph reativo acionado quando `intent = "access"`. O subgraph localiza o `AccessCase` persistido pela Welcome (spec ②), checa se o problema é de plataforma fora do escopo (Shopee/KYC), executa a cascade de busca Cademi (email → CPF stored → nome+telefone, máx 3 tentativas), envia link nominal de auto-login ao aluno e atualiza o `AccessCase` para `REACTIVE_LINK_SENT` ou escala silenciosamente para `REACTIVE_ESCALATED`.

**Architecture:** Subgraph LangGraph com 5 nós sequenciais (`lookup_access_case` → `check_platform_scope` → `search_cademi_cascade` → `send_access` → `update_access_case`). Aproveita `AccessCase`, `CademiPort`, `CademiStudent` e `CademiClient` já criados na Spec ②. A busca por `nome+telefone` (3ª tentativa) é stub com `NotImplementedError` referenciando CQ-A02. O estado entre turnos (ex: aguardando CPF do aluno) é persistido via checkpoint LangGraph herdado do Core (Spec ①).

**Tech Stack:** Python 3.12, LangGraph, SQLAlchemy 2 async, Alembic, structlog, prometheus-client, pytest, pytest-asyncio, testcontainers, factory-boy, uv

**Prerequisite:** Core (Spec ①) e Capability Welcome (Spec ②) devem estar completamente implementados antes deste plano. Em particular, são necessários:
- Entidade `AccessCase` + enum `AccessCaseStatus` (spec ②)
- `CademiPort`, `CademiStudent`, `CademiError`, `FakeCademiClient` (spec ②)
- `ChatNexoPort` com `send_message`, `send_template`, `transfer_to_human` (spec ① + ②)
- `AccessCaseRepository` com `save`, `update`, `get_by_purchase_id` (spec ②)
- Main graph do Core com `intent_router` (spec ①)
- Tabela `access_cases` criada via Alembic (spec ②)

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `src/nexoia/domain/entities/access_case.py` | Modificar | Adicionar `student_cpf`, `search_attempts` + status `REACTIVE_LINK_SENT`, `REACTIVE_ESCALATED` |
| `src/nexoia/domain/ports/cademi_port.py` | Modificar | Adicionar stub `get_student_by_name_phone` (levanta `NotImplementedError`) |
| `src/nexoia/infrastructure/db/models.py` | Modificar | Adicionar colunas `student_cpf` e `search_attempts` ao `AccessCaseModel` |
| `src/nexoia/infrastructure/db/repositories/access_case_repo.py` | Modificar | Adicionar `find_by_phone(account_id, phone)` + `update_status(case_id, status, search_attempts)` + mapear novos campos |
| `src/nexoia/interface/http/schemas/webhook_purchase.py` | Modificar | Adicionar `document: str \| None` ao `PurchaseWebhookPayload` |
| `src/nexoia/interface/http/routers/webhook_purchase.py` | Modificar | Propagar `document` ao job/payload do Welcome |
| `src/nexoia/interface/worker/handlers/process_purchase.py` | Modificar | Persistir `student_cpf` no `AccessCase` |
| `src/nexoia/application/capabilities/welcome.py` | Modificar | `node_persist_access_case` recebe `student_cpf` do state |
| `src/nexoia/application/capabilities/access.py` | Criar | `AccessState` + subgraph + 5 nós da Capability Access |
| `src/nexoia/application/intent_router.py` | Modificar | Registrar rota `intent = "access"` → subgraph Access |
| `src/nexoia/infrastructure/observability/metrics.py` | Modificar | Adicionar counters/histogram Prometheus da Access |
| `migrations/versions/xxxx_add_access_case_reactive_fields.py` | Criar | Alembic: `ALTER TABLE access_cases ADD COLUMN student_cpf / search_attempts` |
| `tests/fakes/fake_cademi_client.py` | Modificar | Adicionar suporte a cascade (student por email/cpf/nome+telefone) + `get_student_by_name_phone` raising `NotImplementedError` |
| `tests/fakes/fake_chatnexo_client.py` | Modificar | Garantir que `transfer_to_human` e `send_message` registram a última chamada |
| `tests/unit/domain/test_access_case_reactive.py` | Criar | Testa novos campos/entidades |
| `tests/unit/capabilities/test_access.py` | Criar | Testes unitários dos 5 nós + casos de borda |
| `tests/integration/test_access_flow.py` | Criar | End-to-end: webhook → welcome → mensagem reativa → cascade → link enviado |
| `tests/unit/observability/test_access_metrics.py` | Criar | Valida métricas Prometheus da Access |
| `docs/superpowers/OPEN_QUESTIONS.md` | Modificar | Status de CQ-A02 e referência a CQ-A01 (já respondida) |
| `docs/superpowers/INDEX.md` | Modificar | Marcar plano ③ como criado |

---

## Task 1: Atualizar entidade AccessCase com campos reativos

**Files:**
- Modify: `src/nexoia/domain/entities/access_case.py`
- Create: `tests/unit/domain/test_access_case_reactive.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/domain/test_access_case_reactive.py
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus


def test_access_case_default_student_cpf_is_none():
    case = AccessCase(
        account_id=1,
        contact_id="contact-123",
        conversation_id="conv-456",
        purchase_id="purchase-789",
        product_name="Curso Python",
    )
    assert case.student_cpf is None


def test_access_case_default_search_attempts_is_zero():
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="P",
    )
    assert case.search_attempts == 0


def test_access_case_with_student_cpf():
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="Curso",
        student_cpf="123.456.789-00",
    )
    assert case.student_cpf == "123.456.789-00"


def test_access_case_search_attempts_mutable():
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="Curso",
    )
    case.search_attempts = 2
    assert case.search_attempts == 2


def test_access_case_reactive_status_enum_values():
    assert AccessCaseStatus.REACTIVE_LINK_SENT == "reactive_link_sent"
    assert AccessCaseStatus.REACTIVE_ESCALATED == "reactive_escalated"


def test_access_case_existing_status_preserved():
    """Spec ② status must continue to exist."""
    assert AccessCaseStatus.PENDING == "pending"
    assert AccessCaseStatus.LINK_SENT == "link_sent_proativo"
    assert AccessCaseStatus.ACCESSED == "accessed"
    assert AccessCaseStatus.REMINDED_D1 == "reminded_d1"
    assert AccessCaseStatus.ESCALATED == "escalated"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_access_case_reactive.py -v
```
Esperado: `AttributeError: student_cpf` ou `search_attempts` não existe; `AccessCaseStatus.REACTIVE_LINK_SENT` também não.

- [ ] **Step 3: Atualizar a entidade**

Abrir `src/nexoia/domain/entities/access_case.py` e adicionar os campos novos na dataclass + novos valores do enum.

```python
# src/nexoia/domain/entities/access_case.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class AccessCaseStatus(str, Enum):
    # Status da Capability Welcome (spec ②) — proativa
    PENDING = "pending"
    LINK_SENT = "link_sent_proativo"
    ACCESSED = "accessed"
    REMINDED_D1 = "reminded_d1"
    ESCALATED = "escalated"
    # Status da Capability Access (spec ③) — reativa
    REACTIVE_LINK_SENT = "reactive_link_sent"   # aluno pediu ajuda → enviamos acesso
    REACTIVE_ESCALATED = "reactive_escalated"    # 3 tentativas falharam → handoff


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
    # Novos campos (spec ③ — Capability Access)
    student_cpf: str | None = None   # CPF/CNPJ do webhook Hubla (campo `document`)
    search_attempts: int = 0         # contador de tentativas na Cademi (0..3)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_access_case_reactive.py -v
uv run pytest tests/unit/domain/test_access_case.py -v  # spec ② continua passando
```
Esperado: 6 testes novos PASSED + os testes do spec ② continuam PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/entities/access_case.py tests/unit/domain/test_access_case_reactive.py
git commit -m "feat(access): add student_cpf, search_attempts and reactive statuses to AccessCase"
```

---

## Task 2: Alembic migration — adicionar colunas reativas

**Files:**
- Modify: `src/nexoia/infrastructure/db/models.py`
- Create: `migrations/versions/xxxx_add_access_case_reactive_fields.py`

- [ ] **Step 1: Atualizar o model SQLAlchemy**

Em `src/nexoia/infrastructure/db/models.py`, adicionar as colunas novas ao `AccessCaseModel`:

```python
# src/nexoia/infrastructure/db/models.py (trecho AccessCaseModel)

class AccessCaseModel(Base):
    __tablename__ = "access_cases"

    # campos existentes (spec ②) ...
    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    purchase_id = Column(String, nullable=False, unique=True)
    product_name = Column(String, nullable=False)
    access_link = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    access_confirmed = Column(Boolean, nullable=False, default=False)
    scheduled_d1_job_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    # Novos (spec ③)
    student_cpf = Column(String, nullable=True)                         # CPF/CNPJ do webhook Hubla
    search_attempts = Column(Integer, nullable=False, default=0)        # 0..3

    __table_args__ = (
        Index("idx_access_cases_account_contact", "account_id", "contact_id"),
        Index("idx_access_cases_account_phone", "account_id", "contact_id"),  # index de busca por phone
    )
```

> **Observação:** no spec ③, o `find_by_phone` usa `contact_phone` para filtrar. No modelo da spec ② o `contact_id` é o identificador do contato. Se o Core (spec ①) tiver mapeamento direto entre `phone` e `contact_id`, o índice já é suficiente. Se o modelo de `Contact` armazenar o `phone` como atributo próprio, o repositório fará um `JOIN` — a implementação em Task 4 deve seguir a convenção já estabelecida no Core.

- [ ] **Step 2: Gerar a migration Alembic**

```bash
uv run alembic revision --autogenerate -m "add_access_case_reactive_fields"
```
Esperado: arquivo criado em `migrations/versions/XXXX_add_access_case_reactive_fields.py`.

- [ ] **Step 3: Revisar e (se necessário) ajustar o arquivo gerado**

Abrir o arquivo e garantir que o `upgrade()` contém:

```python
def upgrade() -> None:
    op.add_column(
        "access_cases",
        sa.Column("student_cpf", sa.String(), nullable=True),
    )
    op.add_column(
        "access_cases",
        sa.Column(
            "search_attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    # Opcional: remover o server_default após aplicar, se a política do projeto exigir:
    op.alter_column("access_cases", "search_attempts", server_default=None)


def downgrade() -> None:
    op.drop_column("access_cases", "search_attempts")
    op.drop_column("access_cases", "student_cpf")
```

> **Crítico:** `search_attempts` precisa de `server_default="0"` no `ADD COLUMN` porque é `NOT NULL`; sem isso a migração falha em tabelas com registros pré-existentes (spec ②).

- [ ] **Step 4: Aplicar a migration no banco de dev**

```bash
uv run alembic upgrade head
```
Esperado: `Running upgrade ... -> XXXX, add_access_case_reactive_fields`.

- [ ] **Step 5: Commit**

```bash
git add migrations/versions/ src/nexoia/infrastructure/db/models.py
git commit -m "feat(access): add student_cpf and search_attempts columns to access_cases"
```

---

## Task 3: Atualizar CademiPort e FakeCademiClient com cascade + stub nome+telefone

**Files:**
- Modify: `src/nexoia/domain/ports/cademi_port.py`
- Modify: `tests/fakes/fake_cademi_client.py`
- Create: `tests/unit/domain/test_cademi_port_cascade.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/domain/test_cademi_port_cascade.py
import pytest
from nexoia.domain.ports.cademi_port import CademiStudent
from tests.fakes.fake_cademi_client import FakeCademiClient


@pytest.mark.asyncio
async def test_fake_cademi_returns_student_by_email_only():
    alice = CademiStudent(id="s1", name="Alice", email="alice@x.com", phone="+5511999990001")
    client = FakeCademiClient(students_by_email={"alice@x.com": alice})
    result = await client.get_student_by_email("alice@x.com")
    assert result == alice


@pytest.mark.asyncio
async def test_fake_cademi_returns_none_when_email_not_mapped():
    client = FakeCademiClient(students_by_email={})
    result = await client.get_student_by_email("nope@x.com")
    assert result is None


@pytest.mark.asyncio
async def test_fake_cademi_returns_student_by_cpf():
    bob = CademiStudent(id="s2", name="Bob", email="bob@x.com", phone="+5511999990002")
    client = FakeCademiClient(students_by_cpf={"12345678900": bob})
    result = await client.get_student_by_cpf("12345678900")
    assert result == bob


@pytest.mark.asyncio
async def test_fake_cademi_returns_none_when_cpf_not_mapped():
    client = FakeCademiClient(students_by_cpf={})
    result = await client.get_student_by_cpf("00000000000")
    assert result is None


@pytest.mark.asyncio
async def test_fake_cademi_name_phone_raises_not_implemented_by_default():
    # CQ-A02: Cademi API pode não suportar nome+telefone.
    # Default do stub é NotImplementedError para forçar decisão explícita no teste.
    client = FakeCademiClient()
    with pytest.raises(NotImplementedError, match="CQ-A02"):
        await client.get_student_by_name_phone("Alice", "+5511999990001")


@pytest.mark.asyncio
async def test_fake_cademi_name_phone_configurable_returns_none():
    client = FakeCademiClient(name_phone_supported=True, students_by_name_phone={})
    result = await client.get_student_by_name_phone("Alice", "+5511999990001")
    assert result is None


@pytest.mark.asyncio
async def test_fake_cademi_name_phone_configurable_returns_student():
    student = CademiStudent(id="s3", name="Carla", email="carla@x.com", phone="+5511999990003")
    client = FakeCademiClient(
        name_phone_supported=True,
        students_by_name_phone={("Carla", "+5511999990003"): student},
    )
    result = await client.get_student_by_name_phone("Carla", "+5511999990003")
    assert result == student


@pytest.mark.asyncio
async def test_fake_cademi_tracks_call_counts_per_method():
    client = FakeCademiClient()
    await client.get_student_by_email("x@x.com")
    await client.get_student_by_email("y@x.com")
    await client.get_student_by_cpf("111")
    assert client.email_calls == 2
    assert client.cpf_calls == 1
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_cademi_port_cascade.py -v
```
Esperado: `AttributeError` em `students_by_email`/`get_student_by_name_phone`/`email_calls`.

- [ ] **Step 3: Atualizar o Port (stub nome+telefone)**

Em `src/nexoia/domain/ports/cademi_port.py`:

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
    async def get_student_by_name_phone(
        self, name: str, phone: str
    ) -> CademiStudent | None:
        """
        TODO (CQ-A02): a Cademi API suporta busca por nome+telefone?
        Se sim, implementar no CademiClient.
        Se não, a 3ª tentativa do cascade deve escalar diretamente.
        Stub atual: levanta NotImplementedError citando OPEN_QUESTIONS.md.
        """
        ...
```

> **Observação:** implementações concretas (`CademiClient` e `FakeCademiClient`) continuam levantando `NotImplementedError` até que CQ-A02 seja respondida.

- [ ] **Step 4: Atualizar FakeCademiClient para suportar cascade**

Abrir `tests/fakes/fake_cademi_client.py` e reescrever para suportar os 3 métodos do cascade. Preservar o comportamento existente (`student`, `fail_times`) como fallback.

```python
# tests/fakes/fake_cademi_client.py
from __future__ import annotations

from nexoia.domain.errors import CademiError
from nexoia.domain.ports.cademi_port import CademiStudent


class FakeCademiClient:
    """
    Fake configurável para testes da Capability Welcome (spec ②) e Access (spec ③).

    Modos de uso:

    1) Compat com spec ② (simples): passe `student=...` e todos os métodos retornam o mesmo aluno.
    2) Cascade (spec ③): passe `students_by_email`, `students_by_cpf` e/ou `students_by_name_phone`.
    3) Falhas: `fail_times=N` faz o 1º N-ésimos chamadas de `get_student_by_email` levantarem `CademiError`.
    4) Stub nome+telefone (CQ-A02): por padrão, `get_student_by_name_phone` levanta NotImplementedError.
       Defina `name_phone_supported=True` para habilitar o mapping dos testes.
    """

    def __init__(
        self,
        *,
        student: CademiStudent | None = None,
        students_by_email: dict[str, CademiStudent] | None = None,
        students_by_cpf: dict[str, CademiStudent] | None = None,
        students_by_name_phone: dict[tuple[str, str], CademiStudent] | None = None,
        name_phone_supported: bool = False,
        fail_times: int = 0,
        access_link: str = "https://cademi.com.br/auto-login/test-token",
    ) -> None:
        self._student = student
        self._students_by_email = students_by_email or {}
        self._students_by_cpf = students_by_cpf or {}
        self._students_by_name_phone = students_by_name_phone or {}
        self._name_phone_supported = name_phone_supported
        self._fail_times = fail_times
        self._access_link = access_link
        # contadores úteis para asserções
        self.call_count = 0
        self.email_calls = 0
        self.cpf_calls = 0
        self.name_phone_calls = 0

    async def get_student_by_email(self, email: str) -> CademiStudent | None:
        self.call_count += 1
        self.email_calls += 1
        if self.call_count <= self._fail_times:
            raise CademiError(f"Connection failed (attempt {self.call_count})")
        if self._students_by_email:
            return self._students_by_email.get(email)
        return self._student

    async def get_student_by_cpf(self, cpf: str) -> CademiStudent | None:
        self.cpf_calls += 1
        if self._students_by_cpf:
            return self._students_by_cpf.get(cpf)
        return self._student

    async def get_student_by_name_phone(
        self, name: str, phone: str
    ) -> CademiStudent | None:
        self.name_phone_calls += 1
        if not self._name_phone_supported:
            # CQ-A02: Cademi API não confirma suporte a nome+telefone.
            raise NotImplementedError(
                "FakeCademiClient.get_student_by_name_phone não habilitado — "
                "ver OPEN_QUESTIONS.md#CQ-A02"
            )
        return self._students_by_name_phone.get((name, phone))

    async def get_access_link(self, student_id: str, product_id: str) -> str:
        return self._access_link
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_cademi_port_cascade.py -v
uv run pytest tests/ -k "welcome" -v  # spec ② continua passando
```
Esperado: 8 testes novos PASSED + os testes do spec ② continuam PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/domain/ports/cademi_port.py \
        tests/fakes/fake_cademi_client.py \
        tests/unit/domain/test_cademi_port_cascade.py
git commit -m "feat(access): extend CademiPort and FakeCademiClient with cascade search + name+phone stub"
```

---

## Task 4: AccessCaseRepository — find_by_phone + update_status + campos novos

**Files:**
- Modify: `src/nexoia/infrastructure/db/repositories/access_case_repo.py`
- Modify: `tests/integration/test_access_case_repo.py`

- [ ] **Step 1: Escrever o teste de integração falhando**

Adicionar ao arquivo `tests/integration/test_access_case_repo.py` (criado no spec ②) os seguintes testes novos:

```python
# tests/integration/test_access_case_repo.py (append)
import pytest
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.infrastructure.db.repositories.access_case_repo import AccessCaseRepository


@pytest.mark.asyncio
async def test_save_persists_student_cpf_and_search_attempts(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id="+5511999999999",
        conversation_id="conv-1",
        purchase_id="p-cpf-001",
        product_name="Curso X",
        student_cpf="111.222.333-44",
        search_attempts=2,
    )
    await repo.save(case)
    found = await repo.get_by_purchase_id("p-cpf-001")
    assert found is not None
    assert found.student_cpf == "111.222.333-44"
    assert found.search_attempts == 2


@pytest.mark.asyncio
async def test_find_by_phone_returns_most_recent(db_session):
    """Se houver múltiplos AccessCases para o mesmo phone, retorna o mais recente."""
    repo = AccessCaseRepository(db_session)
    older = AccessCase(
        account_id=1,
        contact_id="+5511999999999",
        conversation_id="cv-older",
        purchase_id="p-older",
        product_name="Curso Antigo",
    )
    newer = AccessCase(
        account_id=1,
        contact_id="+5511999999999",
        conversation_id="cv-newer",
        purchase_id="p-newer",
        product_name="Curso Novo",
    )
    await repo.save(older)
    # pequena espera para garantir diferença de timestamp
    import asyncio
    await asyncio.sleep(0.01)
    await repo.save(newer)

    found = await repo.find_by_phone(account_id=1, phone="+5511999999999")
    assert found is not None
    assert found.purchase_id == "p-newer"


@pytest.mark.asyncio
async def test_find_by_phone_respects_account_id_isolation(db_session):
    """Tenant isolation: mesmo phone em accounts diferentes são invisíveis."""
    repo = AccessCaseRepository(db_session)
    case_tenant_a = AccessCase(
        account_id=1,
        contact_id="+5511999999999",
        conversation_id="cv-a",
        purchase_id="p-tenant-a",
        product_name="Curso A",
    )
    case_tenant_b = AccessCase(
        account_id=2,
        contact_id="+5511999999999",
        conversation_id="cv-b",
        purchase_id="p-tenant-b",
        product_name="Curso B",
    )
    await repo.save(case_tenant_a)
    await repo.save(case_tenant_b)

    found_a = await repo.find_by_phone(account_id=1, phone="+5511999999999")
    found_b = await repo.find_by_phone(account_id=2, phone="+5511999999999")
    assert found_a.purchase_id == "p-tenant-a"
    assert found_b.purchase_id == "p-tenant-b"


@pytest.mark.asyncio
async def test_find_by_phone_returns_none_when_no_case(db_session):
    repo = AccessCaseRepository(db_session)
    found = await repo.find_by_phone(account_id=1, phone="+5511000000000")
    assert found is None


@pytest.mark.asyncio
async def test_update_status_sets_status_and_attempts_and_updated_at(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id="+5511999999999",
        conversation_id="cv-upd",
        purchase_id="p-update-status",
        product_name="Curso",
    )
    await repo.save(case)

    await repo.update_status(
        case_id=case.id,
        status=AccessCaseStatus.REACTIVE_LINK_SENT,
        search_attempts=1,
    )

    found = await repo.get_by_purchase_id("p-update-status")
    assert found.status == AccessCaseStatus.REACTIVE_LINK_SENT
    assert found.search_attempts == 1
    # `updated_at` tocado (onupdate=func.now())
    assert found.updated_at >= found.created_at


@pytest.mark.asyncio
async def test_update_status_raises_when_case_not_found(db_session):
    repo = AccessCaseRepository(db_session)
    with pytest.raises(ValueError, match="not found"):
        await repo.update_status(
            case_id="nonexistent-id",
            status=AccessCaseStatus.REACTIVE_LINK_SENT,
            search_attempts=0,
        )
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_access_case_repo.py -v
```
Esperado: `AttributeError: 'AccessCaseRepository' object has no attribute 'find_by_phone'`.

- [ ] **Step 3: Implementar `find_by_phone` e `update_status`, e mapear novos campos**

Atualizar `src/nexoia/infrastructure/db/repositories/access_case_repo.py`:

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
            # novos campos (spec ③)
            student_cpf=case.student_cpf,
            search_attempts=case.search_attempts,
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
        model.student_cpf = case.student_cpf
        model.search_attempts = case.search_attempts
        await self._session.commit()

    async def update_status(
        self,
        *,
        case_id: str,
        status: AccessCaseStatus,
        search_attempts: int,
    ) -> None:
        """
        Atualização pontual usada pela Capability Access (spec ③):
        - status: REACTIVE_LINK_SENT ou REACTIVE_ESCALATED
        - search_attempts: 0..3
        updated_at é tocado automaticamente via onupdate=func.now() no model.
        """
        model = await self._session.get(AccessCaseModel, case_id)
        if model is None:
            raise ValueError(f"AccessCase {case_id} not found")
        model.status = status.value
        model.search_attempts = search_attempts
        await self._session.commit()

    async def get_by_purchase_id(self, purchase_id: str) -> AccessCase | None:
        result = await self._session.execute(
            select(AccessCaseModel).where(AccessCaseModel.purchase_id == purchase_id)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)

    async def find_by_phone(
        self, *, account_id: int, phone: str
    ) -> AccessCase | None:
        """
        Busca o AccessCase mais recente do par (account_id, phone).
        Tenant isolation: sempre filtra por account_id (RNF-A01).
        Convenção da Capability Welcome (spec ②): o `contact_id` armazena o telefone.
        """
        result = await self._session.execute(
            select(AccessCaseModel)
            .where(AccessCaseModel.account_id == account_id)
            .where(AccessCaseModel.contact_id == phone)
            .order_by(AccessCaseModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)

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
        # novos campos (spec ③)
        case.student_cpf = model.student_cpf
        case.search_attempts = model.search_attempts
        return case
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_access_case_repo.py -v
```
Esperado: todos os testes PASSED (os antigos do spec ② + os 6 novos do spec ③).

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/access_case_repo.py \
        tests/integration/test_access_case_repo.py
git commit -m "feat(access): add find_by_phone and update_status to AccessCaseRepository"
```

---

## Task 5: Propagar campo `document` do webhook Hubla até o AccessCase

**Files:**
- Modify: `src/nexoia/interface/http/schemas/webhook_purchase.py`
- Modify: `src/nexoia/interface/http/routers/webhook_purchase.py`
- Modify: `src/nexoia/interface/worker/handlers/process_purchase.py`
- Modify: `src/nexoia/application/capabilities/welcome.py`
- Create: `tests/unit/interface/test_webhook_purchase_document.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/interface/test_webhook_purchase_document.py
import pytest
from pydantic import ValidationError

from nexoia.interface.http.schemas.webhook_purchase import PurchaseWebhookPayload


def test_payload_accepts_document_field():
    payload = PurchaseWebhookPayload(
        purchase_id="p-001",
        nome="João Silva",
        email="joao@email.com",
        telefone="+5511999999999",
        produto="Curso Python",
        valor=197.00,
        timestamp="2026-04-18T10:00:00Z",
        document="123.456.789-00",
    )
    assert payload.document == "123.456.789-00"


def test_payload_document_defaults_to_none():
    payload = PurchaseWebhookPayload(
        purchase_id="p-001",
        nome="João Silva",
        email="joao@email.com",
        telefone="+5511999999999",
        produto="Curso Python",
        valor=197.00,
        timestamp="2026-04-18T10:00:00Z",
    )
    assert payload.document is None


def test_payload_document_accepts_cnpj():
    payload = PurchaseWebhookPayload(
        purchase_id="p-002",
        nome="Empresa LTDA",
        email="empresa@email.com",
        telefone="+5511999999999",
        produto="Curso",
        valor=500.00,
        timestamp="2026-04-18T10:00:00Z",
        document="12.345.678/0001-90",
    )
    assert payload.document == "12.345.678/0001-90"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/interface/test_webhook_purchase_document.py -v
```
Esperado: `ValidationError` — campo `document` não existe no schema.

- [ ] **Step 3: Adicionar campo `document` no schema Pydantic**

Em `src/nexoia/interface/http/schemas/webhook_purchase.py`:

```python
# src/nexoia/interface/http/schemas/webhook_purchase.py
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PurchaseWebhookPayload(BaseModel):
    """Payload do webhook Hubla — POST /webhook/purchase."""

    purchase_id: str
    nome: str
    email: str
    telefone: str
    produto: str
    valor: float
    timestamp: datetime
    # Spec ③: CPF ou CNPJ do comprador; None se Hubla não enviou.
    # Persistido em access_cases.student_cpf e usado na cascade da Capability Access.
    document: str | None = Field(default=None, description="CPF ou CNPJ do comprador")
```

- [ ] **Step 4: Propagar no router e no job payload**

Em `src/nexoia/interface/http/routers/webhook_purchase.py`, onde o payload é montado para o job `ProcessPurchaseWebhook`, incluir `document`:

```python
# src/nexoia/interface/http/routers/webhook_purchase.py (trecho)
async def handle_purchase_webhook(payload: PurchaseWebhookPayload, ...):
    # ... idempotência Redis NX, validação de token ...
    await queue.enqueue(
        job_type="ProcessPurchaseWebhook",
        payload={
            "purchase_id": payload.purchase_id,
            "account_id": account_id,
            "student_name": payload.nome,
            "student_phone": payload.telefone,
            "student_email": payload.email,
            "product_name": payload.produto,
            "student_cpf": payload.document,   # ← novo (spec ③)
            "correlation_id": correlation_id,
        },
    )
```

- [ ] **Step 5: Propagar até o handler e o subgraph Welcome**

Em `src/nexoia/interface/worker/handlers/process_purchase.py`, adicionar o campo ao `run_welcome_subgraph(...)`:

```python
# src/nexoia/interface/worker/handlers/process_purchase.py (trecho)
await run_welcome_subgraph(
    purchase_id=payload["purchase_id"],
    account_id=payload["account_id"],
    student_name=payload["student_name"],
    student_phone=payload["student_phone"],
    student_email=payload["student_email"],
    product_name=payload["product_name"],
    student_cpf=payload.get("student_cpf"),   # ← novo (spec ③); pode vir ausente
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

Em `src/nexoia/application/capabilities/welcome.py`, atualizar o `WelcomeState` e o `node_persist_access_case`:

```python
# src/nexoia/application/capabilities/welcome.py (trecho)
class WelcomeState(ConversationState):
    purchase_id: str
    student_name: str
    student_phone: str
    student_email: str
    student_cpf: str | None   # ← novo (spec ③)
    product_name: str
    access_link: str | None
    cademi_attempts: int
    conversation_id: str | None
    access_case_id: str | None
    access_confirmed: bool
    cademi_failed: bool


async def node_persist_access_case(
    state: WelcomeState,
    *,
    access_case_repo: Any,
) -> dict[str, Any]:
    case = AccessCase(
        account_id=state["account_id"],
        contact_id=state["student_phone"],   # Spec ②: contact_id = phone
        conversation_id=state["conversation_id"],
        purchase_id=state["purchase_id"],
        product_name=state["product_name"],
        access_link=state.get("access_link"),
        status=AccessCaseStatus.ESCALATED if state.get("cademi_failed") else AccessCaseStatus.LINK_SENT,
        student_cpf=state.get("student_cpf"),   # ← novo (spec ③)
    )
    await access_case_repo.save(case)
    # ...
    return {"access_case_id": case.id}
```

- [ ] **Step 6: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/interface/test_webhook_purchase_document.py -v
uv run pytest tests/ -k "welcome" -v  # spec ② continua passando
```
Esperado: 3 novos PASSED + spec ② continua verde.

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/interface/http/schemas/webhook_purchase.py \
        src/nexoia/interface/http/routers/webhook_purchase.py \
        src/nexoia/interface/worker/handlers/process_purchase.py \
        src/nexoia/application/capabilities/welcome.py \
        tests/unit/interface/test_webhook_purchase_document.py
git commit -m "feat(access): propagate Hubla document (CPF/CNPJ) into AccessCase.student_cpf"
```

---

## Task 6: AccessState + esqueleto do subgraph Access

**Files:**
- Create: `src/nexoia/application/capabilities/access.py` (esqueleto apenas — nós reais nas Tasks 7-11)
- Create: `tests/unit/capabilities/test_access_state.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/capabilities/test_access_state.py
from nexoia.application.capabilities.access import AccessState, build_access_subgraph


def test_access_state_fields():
    state: AccessState = {
        "account_id": 1,
        "correlation_id": "corr-1",
        "messages": [],
        "access_case_id": None,
        "student_email": None,
        "student_cpf": None,
        "student_name": None,
        "student_phone": "+5511999999999",
        "cademi_student": None,
        "search_attempts": 0,
        "cpf_asked": False,
        "access_link": None,
        "out_of_scope": False,
        "email_mismatch_pending": False,
    }
    # não deve levantar em construção — TypedDict é permissivo
    assert state["student_phone"] == "+5511999999999"
    assert state["search_attempts"] == 0
    assert state["cpf_asked"] is False


def test_build_access_subgraph_is_compilable():
    graph = build_access_subgraph()
    compiled = graph.compile()
    # smoke test — o subgraph precisa compilar sem erros
    assert compiled is not None
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_access_state.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Criar o esqueleto do módulo**

```python
# src/nexoia/application/capabilities/access.py
"""
Capability Access (spec ③) — fluxo reativo de recuperação de acesso.

Acionada pelo Intent Router quando `intent = "access"`.

Grafo de nós:
    START
      │
      ▼
    lookup_access_case      (Task 7)
      │
      ▼
    check_platform_scope    (Task 8 — PRD 7.2: Shopee/KYC out of scope)
      │
      ▼
    search_cademi_cascade   (Task 9 — email → CPF → nome+telefone; máx 3)
      │
      ▼
    send_access             (Task 10 — link nominal auto-login; PRD 7.2)
      │
      ▼
    update_access_case      (Task 11 — REACTIVE_LINK_SENT)
      │
      ▼
    END
"""
from __future__ import annotations

import structlog
from langgraph.graph import END, StateGraph

from nexoia.application.state import ConversationState
from nexoia.domain.ports.cademi_port import CademiStudent

logger = structlog.get_logger(__name__)

# Regras do PRD 7.2 em constantes — nunca no prompt do LLM (RNF-02/regras fora do prompt)
CADEMI_MAX_ATTEMPTS = 3           # RF-A02: cascade com no máximo 3 tentativas
CPF_REQUEST_MESSAGE = (
    "Pra eu te ajudar mais rápido, me passa seu CPF (só números, por favor)?"
)
EMAIL_MISMATCH_MESSAGE = (
    "Percebi que o email que vc passou é diferente do cadastro da compra. "
    "Quer que eu atualize pra esse novo email antes de reenviar o acesso?"
)
OUT_OF_SCOPE_REASONS = {
    "shopee": "shopee_or_kyc_out_of_scope",
    "kyc": "shopee_or_kyc_out_of_scope",
}


class AccessState(ConversationState):
    # Populados por lookup_access_case
    access_case_id: str | None
    student_email: str | None
    student_cpf: str | None       # do AccessCase (pode ser None se Hubla não enviou)
    student_name: str | None
    student_phone: str | None

    # Populados durante a cascade
    cademi_student: CademiStudent | None
    search_attempts: int          # 0..3
    cpf_asked: bool               # True se já pedimos CPF ao aluno neste caso
    access_link: str | None

    # Sinais de controle
    out_of_scope: bool             # True → handoff por PRD 7.2 (Shopee/KYC)
    email_mismatch_pending: bool   # True → aguardando aluno confirmar update de email


def build_access_subgraph() -> StateGraph:
    """
    Constrói o subgraph da Capability Access.
    Os nós concretos são importados no nível de função para evitar ciclos de import
    e serem individualmente testáveis.
    """
    from nexoia.application.capabilities.access import (  # type: ignore[import-outside-toplevel]
        node_lookup_access_case,
        node_check_platform_scope,
        node_search_cademi_cascade,
        node_send_access,
        node_update_access_case,
    )

    graph = StateGraph(AccessState)
    graph.add_node("lookup_access_case", node_lookup_access_case)
    graph.add_node("check_platform_scope", node_check_platform_scope)
    graph.add_node("search_cademi_cascade", node_search_cademi_cascade)
    graph.add_node("send_access", node_send_access)
    graph.add_node("update_access_case", node_update_access_case)

    graph.set_entry_point("lookup_access_case")
    graph.add_edge("lookup_access_case", "check_platform_scope")
    graph.add_edge("check_platform_scope", "search_cademi_cascade")
    graph.add_edge("search_cademi_cascade", "send_access")
    graph.add_edge("send_access", "update_access_case")
    graph.add_edge("update_access_case", END)

    return graph


# -----------------------------------------------------------------------------
# Nós — stubs iniciais (serão implementados nas Tasks 7-11)
# -----------------------------------------------------------------------------

async def node_lookup_access_case(state: AccessState, **deps):
    raise NotImplementedError("Task 7")


async def node_check_platform_scope(state: AccessState, **deps):
    raise NotImplementedError("Task 8")


async def node_search_cademi_cascade(state: AccessState, **deps):
    raise NotImplementedError("Task 9")


async def node_send_access(state: AccessState, **deps):
    raise NotImplementedError("Task 10")


async def node_update_access_case(state: AccessState, **deps):
    raise NotImplementedError("Task 11")
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_access_state.py -v
```
Esperado: 2 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/access.py \
        tests/unit/capabilities/test_access_state.py
git commit -m "feat(access): scaffold AccessState and Access subgraph with 5-node skeleton"
```

---

## Task 7: Nó `lookup_access_case`

**Files:**
- Modify: `src/nexoia/application/capabilities/access.py`
- Create: `tests/unit/capabilities/test_access_lookup.py`

> **Observação (RF-A01):** busca `AccessCase` ativo pelo `contact_phone` + `account_id`. Se não encontrado: handoff silencioso (caso raro — aluno sem compra registrada). Popula `student_email`, `student_cpf`, `student_name` no state.

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/capabilities/test_access_lookup.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import (
    AccessState,
    node_lookup_access_case,
)
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus


def make_state(**kwargs) -> AccessState:
    base = dict(
        account_id=1,
        correlation_id="corr-1",
        messages=[],
        access_case_id=None,
        student_email=None,
        student_cpf=None,
        student_name=None,
        student_phone="+5511999999999",
        cademi_student=None,
        search_attempts=0,
        cpf_asked=False,
        access_link=None,
        out_of_scope=False,
        email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_lookup_populates_state_from_access_case():
    case = AccessCase(
        account_id=1,
        contact_id="+5511999999999",
        conversation_id="conv-1",
        purchase_id="p-1",
        product_name="Curso Python",
    )
    case.student_cpf = "111.222.333-44"

    repo = AsyncMock()
    repo.find_by_phone.return_value = case
    handoff = AsyncMock()

    state = make_state()
    result = await node_lookup_access_case(
        state,
        access_case_repo=repo,
        chatnexo_port=AsyncMock(),
        handoff_fn=handoff,
    )

    repo.find_by_phone.assert_awaited_once_with(account_id=1, phone="+5511999999999")
    assert result["access_case_id"] == case.id
    assert result["student_cpf"] == "111.222.333-44"
    # student_email e student_name vêm do contato/fatos de longo prazo via Core.
    # No MVP, o lookup popula pelo menos cpf e id; demais campos são propagados pelo
    # context_builder do Core antes do subgraph rodar.
    handoff.assert_not_called()


@pytest.mark.asyncio
async def test_lookup_triggers_handoff_when_no_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    chatnexo = AsyncMock()
    handoff = AsyncMock()

    state = make_state()
    result = await node_lookup_access_case(
        state,
        access_case_repo=repo,
        chatnexo_port=chatnexo,
        handoff_fn=handoff,
    )

    handoff.assert_awaited_once()
    call_kwargs = handoff.await_args.kwargs
    assert call_kwargs["reason"] == "no_access_case"
    assert result["access_case_id"] is None


@pytest.mark.asyncio
async def test_lookup_respects_account_id_isolation():
    """RNF-A01: find_by_phone é sempre chamado com account_id do state."""
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    handoff = AsyncMock()

    state = make_state(account_id=42, student_phone="+5511999999991")
    await node_lookup_access_case(
        state,
        access_case_repo=repo,
        chatnexo_port=AsyncMock(),
        handoff_fn=handoff,
    )
    repo.find_by_phone.assert_awaited_once_with(
        account_id=42, phone="+5511999999991"
    )
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_access_lookup.py -v
```
Esperado: `NotImplementedError: Task 7`.

- [ ] **Step 3: Implementar o nó**

Substituir o stub `node_lookup_access_case` em `src/nexoia/application/capabilities/access.py`:

```python
# src/nexoia/application/capabilities/access.py (substituir o stub)
from typing import Any, Awaitable, Callable

# ... imports existentes ...

async def node_lookup_access_case(
    state: AccessState,
    *,
    access_case_repo: Any,
    chatnexo_port: Any,
    handoff_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    """
    RF-A01: localiza AccessCase ativo pelo (account_id, student_phone).
    Se não encontrado: handoff silencioso (RF-A01 parte final).
    """
    log = logger.bind(
        capability="access",
        node="lookup_access_case",
        account_id=state["account_id"],
    )
    case = await access_case_repo.find_by_phone(
        account_id=state["account_id"],
        phone=state["student_phone"],
    )

    if case is None:
        log.warning("no_access_case", reason="no_access_case")
        await handoff_fn(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            reason="no_access_case",
        )
        return {"access_case_id": None}

    log.info("access_case_found", access_case_id=case.id)
    return {
        "access_case_id": case.id,
        "student_cpf": case.student_cpf,
        # student_email e student_name são injetados pelo Context Builder do Core
        # a partir do Contact/long_term_facts — mas mantemos fallback aqui caso
        # o Context Builder não tenha populado.
        "student_email": state.get("student_email"),
        "student_name": state.get("student_name"),
        "search_attempts": case.search_attempts,
    }
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_access_lookup.py -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/access.py \
        tests/unit/capabilities/test_access_lookup.py
git commit -m "feat(access): implement node_lookup_access_case with handoff on miss"
```

---

## Task 8: Nó `check_platform_scope` (Shopee/KYC out of scope — PRD 7.2)

**Files:**
- Modify: `src/nexoia/application/capabilities/access.py`
- Create: `tests/unit/capabilities/test_access_platform_scope.py`

> **Crítico (PRD 7.2):** *"Nunca usar `resend_access` para problemas de cadastro Shopee ou KYC — são plataformas distintas."* Se a mensagem mencionar Shopee ou KYC, o nó dispara handoff silencioso com `reason="shopee_or_kyc_out_of_scope"` e marca `out_of_scope=True` no state (os nós seguintes devem detectar esse flag e pular).

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/capabilities/test_access_platform_scope.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import (
    AccessState,
    node_check_platform_scope,
)


def make_state(last_user_message: str, **kwargs) -> AccessState:
    base = dict(
        account_id=1,
        correlation_id="corr-1",
        messages=[{"role": "user", "content": last_user_message}],
        access_case_id="ac-1",
        student_email="joao@email.com",
        student_cpf="123.456.789-00",
        student_name="João",
        student_phone="+5511999999999",
        cademi_student=None,
        search_attempts=0,
        cpf_asked=False,
        access_link=None,
        out_of_scope=False,
        email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_scope_passes_through_when_message_is_about_access():
    handoff = AsyncMock()
    state = make_state("não consigo entrar no curso, esqueci a senha")
    result = await node_check_platform_scope(state, handoff_fn=handoff)
    assert result.get("out_of_scope", False) is False
    handoff.assert_not_called()


@pytest.mark.asyncio
async def test_scope_detects_shopee_and_handoffs():
    handoff = AsyncMock()
    state = make_state("meu cadastro shopee não tá aprovado")
    result = await node_check_platform_scope(state, handoff_fn=handoff)
    assert result["out_of_scope"] is True
    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "shopee_or_kyc_out_of_scope"


@pytest.mark.asyncio
async def test_scope_detects_kyc_case_insensitive():
    handoff = AsyncMock()
    state = make_state("to travado no KYC, me ajuda")
    result = await node_check_platform_scope(state, handoff_fn=handoff)
    assert result["out_of_scope"] is True
    handoff.assert_awaited_once()


@pytest.mark.asyncio
async def test_scope_detects_shopee_case_insensitive_and_variations():
    handoff = AsyncMock()
    state = make_state("problema no SHOPEE ID")
    result = await node_check_platform_scope(state, handoff_fn=handoff)
    assert result["out_of_scope"] is True


@pytest.mark.asyncio
async def test_scope_skipped_when_lookup_failed():
    """Se o lookup não achou AccessCase, o state já foi finalizado; o scope não age."""
    handoff = AsyncMock()
    state = make_state("não consigo entrar", access_case_id=None)
    result = await node_check_platform_scope(state, handoff_fn=handoff)
    # Quando access_case_id é None, nada a fazer — state retorna intacto
    assert result.get("out_of_scope", False) is False
    handoff.assert_not_called()


@pytest.mark.asyncio
async def test_scope_uses_last_user_message_only():
    """O handoff considera apenas a ÚLTIMA mensagem do aluno (não mensagens antigas)."""
    handoff = AsyncMock()
    messages = [
        {"role": "user", "content": "antes: falei de shopee"},
        {"role": "assistant", "content": "resposta anterior"},
        {"role": "user", "content": "agora: não consigo acessar o curso"},
    ]
    state = make_state("agora: não consigo acessar o curso")
    state["messages"] = messages
    result = await node_check_platform_scope(state, handoff_fn=handoff)
    assert result.get("out_of_scope", False) is False
    handoff.assert_not_called()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_access_platform_scope.py -v
```
Esperado: `NotImplementedError: Task 8`.

- [ ] **Step 3: Implementar o nó**

```python
# src/nexoia/application/capabilities/access.py (substituir o stub)

# Constante no topo do módulo (adicionar se ainda não existe):
_OUT_OF_SCOPE_KEYWORDS = ("shopee", "kyc")


def _extract_last_user_message(state: AccessState) -> str:
    """Retorna o conteúdo da última mensagem com role='user', ou string vazia."""
    messages = state.get("messages", []) or []
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return str(msg.get("content", ""))
    return ""


async def node_check_platform_scope(
    state: AccessState,
    *,
    handoff_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    """
    RF-A05a / PRD 7.2: se o aluno mencionar Shopee ou KYC, estamos fora do escopo
    do fluxo de acesso à Cademi (plataformas distintas). Handoff silencioso.
    """
    log = logger.bind(
        capability="access",
        node="check_platform_scope",
        account_id=state["account_id"],
    )

    # Se o lookup não achou case, não há acesso a resolver.
    if state.get("access_case_id") is None:
        return {}

    last_msg = _extract_last_user_message(state).lower()
    if any(kw in last_msg for kw in _OUT_OF_SCOPE_KEYWORDS):
        log.warning("out_of_scope", reason="shopee_or_kyc_out_of_scope")
        await handoff_fn(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            reason="shopee_or_kyc_out_of_scope",
        )
        return {"out_of_scope": True}

    return {"out_of_scope": False}
```

> **Observação:** a detecção por keyword é intencional e suficiente para MVP. Uma evolução futura pode usar LLM para classificar, mas a regra absoluta do PRD 7.2 é binária e custa caro errar — manter determinístico.

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_access_platform_scope.py -v
```
Esperado: 6 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/access.py \
        tests/unit/capabilities/test_access_platform_scope.py
git commit -m "feat(access): add Shopee/KYC scope guard (PRD 7.2) with silent handoff"
```

---

## Task 9: Nó `search_cademi_cascade` — email → CPF stored → nome+telefone

**Files:**
- Modify: `src/nexoia/application/capabilities/access.py`
- Create: `tests/unit/capabilities/test_access_cascade.py`

> **Regras críticas (PRD 7.2 + Spec ③):**
> - Máx 3 tentativas. Depois → `REACTIVE_ESCALATED` + handoff silencioso.
> - Email mismatch: se aluno fornecer email ≠ email do AccessCase, oferece atualizar cadastro **antes** de reenviar.
> - Se `student_cpf = None`: pede CPF ao aluno e aguarda próxima mensagem (`cpf_asked=True`).
> - 3ª tentativa (nome+telefone): stub `NotImplementedError` citando CQ-A02.

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/capabilities/test_access_cascade.py
import re
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import (
    AccessState,
    node_search_cademi_cascade,
)
from nexoia.domain.ports.cademi_port import CademiStudent
from tests.fakes.fake_cademi_client import FakeCademiClient


def make_state(**kwargs) -> AccessState:
    base = dict(
        account_id=1,
        correlation_id="corr-1",
        messages=[{"role": "user", "content": "não consigo acessar"}],
        access_case_id="ac-1",
        student_email="joao@email.com",
        student_cpf=None,
        student_name="João",
        student_phone="+5511999999999",
        cademi_student=None,
        search_attempts=0,
        cpf_asked=False,
        access_link=None,
        out_of_scope=False,
        email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_cascade_skips_when_out_of_scope():
    cademi = FakeCademiClient()
    state = make_state(out_of_scope=True)
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=AsyncMock(),
        handoff_fn=AsyncMock(),
    )
    assert result == {}
    assert cademi.email_calls == 0


@pytest.mark.asyncio
async def test_cascade_found_by_email_on_first_attempt():
    alice = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = FakeCademiClient(students_by_email={"joao@email.com": alice})

    state = make_state()
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=AsyncMock(),
        handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == alice
    assert result["search_attempts"] == 1


@pytest.mark.asyncio
async def test_cascade_falls_back_to_cpf_when_email_misses():
    bob = CademiStudent(id="s2", name="João", email="joao2@email.com", phone="+5511999999999")
    cademi = FakeCademiClient(
        students_by_email={},
        students_by_cpf={"11122233344": bob},
    )
    state = make_state(student_cpf="11122233344")
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=AsyncMock(),
        handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == bob
    assert result["search_attempts"] == 2
    assert cademi.email_calls == 1
    assert cademi.cpf_calls == 1


@pytest.mark.asyncio
async def test_cascade_asks_cpf_when_not_available():
    """RF-A03: se student_cpf=None, IA pede CPF ao aluno e interrompe."""
    cademi = FakeCademiClient(students_by_email={})
    chatnexo = AsyncMock()
    state = make_state(student_cpf=None)
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=chatnexo,
        handoff_fn=AsyncMock(),
    )
    # Pediu CPF e setou o flag; NÃO chamou CPF ainda
    chatnexo.send_message.assert_awaited_once()
    assert result["cpf_asked"] is True
    assert result.get("cademi_student") is None
    # search_attempts fica em 1 (tentou email) — não avança para CPF ainda
    assert result["search_attempts"] == 1
    assert cademi.cpf_calls == 0


@pytest.mark.asyncio
async def test_cascade_consumes_cpf_from_next_turn():
    """
    Quando cpf_asked=True e o aluno responde com um CPF, o próximo turno
    re-executa o nó, que detecta o CPF na última mensagem e tenta a Cademi.
    """
    student = CademiStudent(id="s3", name="Maria", email="x@x.com", phone="+5511988888888")
    cademi = FakeCademiClient(
        students_by_email={},
        students_by_cpf={"98765432100": student},
    )
    state = make_state(
        student_cpf=None,
        cpf_asked=True,
        search_attempts=1,
        messages=[
            {"role": "user", "content": "não consigo acessar"},
            {"role": "assistant", "content": "me passa seu cpf"},
            {"role": "user", "content": "987.654.321-00"},
        ],
    )
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=AsyncMock(),
        handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == student
    assert result["student_cpf"] == "98765432100"  # normalizado
    assert result["search_attempts"] == 2


@pytest.mark.asyncio
async def test_cascade_name_phone_raises_not_implemented_by_default():
    """
    3ª tentativa (CQ-A02): Cademi API não confirma suporte a nome+telefone.
    Com FakeCademiClient default (name_phone_supported=False), o nó deve
    escalar silenciosamente em vez de crashar o subgraph.
    """
    cademi = FakeCademiClient(
        students_by_email={},
        students_by_cpf={},
        name_phone_supported=False,
    )
    handoff = AsyncMock()
    state = make_state(student_cpf="99988877766", search_attempts=0)
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=AsyncMock(),
        handoff_fn=handoff,
    )
    assert result.get("cademi_student") is None
    assert result["search_attempts"] == 3
    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "cademi_not_found_after_3_attempts"


@pytest.mark.asyncio
async def test_cascade_escalates_after_3_attempts_even_if_name_phone_supported():
    """RF-A04: 3 tentativas exaustas → handoff + REACTIVE_ESCALATED no update."""
    cademi = FakeCademiClient(
        students_by_email={},
        students_by_cpf={},
        students_by_name_phone={},  # nenhum match
        name_phone_supported=True,
    )
    handoff = AsyncMock()
    state = make_state(student_cpf="11122233344")
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=AsyncMock(),
        handoff_fn=handoff,
    )
    assert result.get("cademi_student") is None
    assert result["search_attempts"] == 3
    handoff.assert_awaited_once()


@pytest.mark.asyncio
async def test_cascade_email_mismatch_pending_triggers_offer():
    """
    RF-A05b / PRD 7.2: aluno menciona email ≠ email do AccessCase →
    oferece atualizar cadastro e interrompe (email_mismatch_pending=True).
    """
    cademi = FakeCademiClient(students_by_email={})
    chatnexo = AsyncMock()
    state = make_state(
        student_email="joao@email.com",
        messages=[
            {"role": "user", "content": "tentei entrar com joao.novo@gmail.com"},
        ],
    )
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=chatnexo,
        handoff_fn=AsyncMock(),
    )
    assert result["email_mismatch_pending"] is True
    chatnexo.send_message.assert_awaited_once()
    # Não avançou Cademi ainda — aguardando confirmação do aluno
    assert cademi.email_calls == 0


@pytest.mark.asyncio
async def test_cascade_email_mismatch_updates_and_searches_on_confirm():
    """Depois do aluno confirmar, o state tem email_mismatch_pending=False e um novo email."""
    alice = CademiStudent(id="s1", name="João", email="joao.novo@gmail.com", phone="+5511999999999")
    cademi = FakeCademiClient(students_by_email={"joao.novo@gmail.com": alice})

    state = make_state(
        student_email="joao.novo@gmail.com",  # já atualizado pelo turno anterior
        email_mismatch_pending=False,
        messages=[
            {"role": "user", "content": "pode atualizar sim"},
        ],
    )
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=AsyncMock(),
        handoff_fn=AsyncMock(),
    )
    assert result["cademi_student"] == alice


@pytest.mark.asyncio
async def test_cascade_cpf_invalid_in_message_asks_again():
    """
    Se o aluno respondeu com algo que não parece CPF, não avança a tentativa —
    o Response Composer do Core pode pedir de novo.
    """
    cademi = FakeCademiClient(students_by_email={}, students_by_cpf={})
    chatnexo = AsyncMock()
    state = make_state(
        student_cpf=None,
        cpf_asked=True,
        search_attempts=1,
        messages=[
            {"role": "user", "content": "não consigo acessar"},
            {"role": "assistant", "content": "me passa seu cpf"},
            {"role": "user", "content": "não sei direito, é tipo 123"},
        ],
    )
    result = await node_search_cademi_cascade(
        state,
        cademi_port=cademi,
        chatnexo_port=chatnexo,
        handoff_fn=AsyncMock(),
    )
    # Ainda cpf_asked, sem chamar Cademi por CPF, sem escalar.
    assert result["cpf_asked"] is True
    assert cademi.cpf_calls == 0
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_access_cascade.py -v
```
Esperado: `NotImplementedError: Task 9`.

- [ ] **Step 3: Implementar o nó**

Substituir `node_search_cademi_cascade` em `src/nexoia/application/capabilities/access.py` por uma implementação completa. Adicionar também os helpers de extração de email e CPF.

```python
# src/nexoia/application/capabilities/access.py (substituir stub + adicionar helpers)
import re

_EMAIL_REGEX = re.compile(r"[\w\.\-\+]+@[\w\-]+(?:\.[\w\-]+)+")
_CPF_REGEX = re.compile(r"\d{3}\.?\d{3}\.?\d{3}\-?\d{2}")


def _normalize_cpf(raw: str) -> str:
    """Remove pontos/hífens. Retorna string vazia se não houver dígitos suficientes."""
    digits = re.sub(r"\D", "", raw)
    return digits if len(digits) == 11 else ""


def _extract_email_from_last_message(state: AccessState) -> str | None:
    msg = _extract_last_user_message(state)
    match = _EMAIL_REGEX.search(msg)
    return match.group(0).lower() if match else None


def _extract_cpf_from_last_message(state: AccessState) -> str | None:
    msg = _extract_last_user_message(state)
    match = _CPF_REGEX.search(msg)
    if match is None:
        return None
    return _normalize_cpf(match.group(0)) or None


async def node_search_cademi_cascade(
    state: AccessState,
    *,
    cademi_port: Any,
    chatnexo_port: Any,
    handoff_fn: Callable[..., Awaitable[None]],
) -> dict[str, Any]:
    """
    RF-A02: cascade email → CPF (stored) → nome+telefone. Máx 3 tentativas.
    RF-A03: se student_cpf=None, pede CPF ao aluno (cpf_asked=True).
    RF-A04: após 3 tentativas sem match → handoff silencioso.
    RF-A05b: se aluno menciona email diferente → oferece atualizar cadastro antes.
    """
    log = logger.bind(
        capability="access",
        node="search_cademi_cascade",
        account_id=state["account_id"],
        access_case_id=state.get("access_case_id"),
    )

    # Bypass se escopo errado ou lookup falhou
    if state.get("out_of_scope") or state.get("access_case_id") is None:
        return {}

    # --- Regra PRD 7.2: email mismatch ------------------------------------
    email_from_msg = _extract_email_from_last_message(state)
    stored_email = state.get("student_email")
    if (
        email_from_msg
        and stored_email
        and email_from_msg.lower() != stored_email.lower()
        and not state.get("email_mismatch_pending", False)
    ):
        log.info(
            "email_mismatch_detected",
            stored_email=stored_email,
            new_email=email_from_msg,
        )
        await chatnexo_port.send_message(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            text=EMAIL_MISMATCH_MESSAGE,
        )
        return {"email_mismatch_pending": True}

    attempts = state.get("search_attempts", 0)

    # --- Tentativa 1: email -----------------------------------------------
    if attempts < 1:
        email_to_try = email_from_msg or stored_email
        if email_to_try:
            log.info("attempt_email", attempt=1, method="email")
            student = await cademi_port.get_student_by_email(email_to_try)
            attempts = 1
            if student is not None:
                return {"cademi_student": student, "search_attempts": attempts}

    # --- Tentativa 2: CPF ---------------------------------------------------
    if attempts < 2:
        current_cpf = state.get("student_cpf")
        # Se chegamos aqui sem CPF mas já pedimos antes, verificar se a msg atual traz um
        cpf_from_msg = _extract_cpf_from_last_message(state)
        if current_cpf is None and cpf_from_msg:
            current_cpf = cpf_from_msg

        if current_cpf is None and not state.get("cpf_asked", False):
            # Primeira vez que cai aqui sem CPF → pede ao aluno e interrompe
            log.info("asking_cpf", reason="cpf_not_in_hubla_payload")
            await chatnexo_port.send_message(
                account_id=state["account_id"],
                conversation_id=state.get("conversation_id"),
                text=CPF_REQUEST_MESSAGE,
            )
            return {"cpf_asked": True, "search_attempts": attempts}

        if current_cpf is None:
            # Já pedimos antes e o aluno ainda não mandou CPF válido — não avança
            log.info("waiting_valid_cpf")
            return {"cpf_asked": True, "search_attempts": attempts}

        log.info("attempt_cpf", attempt=2, method="cpf")
        student = await cademi_port.get_student_by_cpf(current_cpf)
        attempts = 2
        if student is not None:
            return {
                "cademi_student": student,
                "search_attempts": attempts,
                "student_cpf": current_cpf,
            }

    # --- Tentativa 3: nome + telefone --------------------------------------
    if attempts < CADEMI_MAX_ATTEMPTS:
        log.info("attempt_name_phone", attempt=3, method="name_phone")
        try:
            student = await cademi_port.get_student_by_name_phone(
                name=state.get("student_name") or "",
                phone=state["student_phone"],
            )
        except NotImplementedError:
            # CQ-A02: Cademi API sem suporte a nome+telefone — escala direto
            log.warning(
                "name_phone_unsupported",
                reason="cademi_name_phone_not_implemented",
            )
            student = None

        attempts = CADEMI_MAX_ATTEMPTS
        if student is not None:
            return {"cademi_student": student, "search_attempts": attempts}

    # --- Esgotado: handoff silencioso + REACTIVE_ESCALATED (no update node)
    log.warning(
        "cademi_exhausted",
        reason="cademi_not_found_after_3_attempts",
        attempts=attempts,
    )
    await handoff_fn(
        account_id=state["account_id"],
        conversation_id=state.get("conversation_id"),
        reason="cademi_not_found_after_3_attempts",
    )
    return {"cademi_student": None, "search_attempts": attempts}
```

> **Observação importante:** a detecção de "aluno confirmou update de email" é feita pelo Context Builder do Core (já atualizou `student_email` no long_term_facts e passou ao state). O nó só age quando detecta uma nova divergência.

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_access_cascade.py -v
```
Esperado: 10 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/access.py \
        tests/unit/capabilities/test_access_cascade.py
git commit -m "feat(access): implement Cademi cascade (email → CPF → name+phone) with max 3 attempts"
```

---

## Task 10: Nó `send_access` — link nominal de auto-login (PRD 7.2)

**Files:**
- Modify: `src/nexoia/application/capabilities/access.py`
- Create: `tests/unit/capabilities/test_access_send.py`

> **Regra (PRD 7.2):** *"Link de acesso deve ser nominal (auto-login) — aluno não cria senha."*
>
> - Dentro da janela 24h → texto livre com o link.
> - Fora da janela → template Meta aprovado.
> - O state carrega o indicador `within_24h_window` propagado pelo Core (spec ①). Se ausente, por segurança (RNF-08 — compliance Meta fail-closed) usamos template.

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/capabilities/test_access_send.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import AccessState, node_send_access
from nexoia.domain.ports.cademi_port import CademiStudent


def make_state(student: CademiStudent | None, **kwargs) -> AccessState:
    base = dict(
        account_id=1,
        correlation_id="corr-1",
        messages=[],
        access_case_id="ac-1",
        student_email="joao@email.com",
        student_cpf="11122233344",
        student_name="João",
        student_phone="+5511999999999",
        cademi_student=student,
        search_attempts=1,
        cpf_asked=False,
        access_link=None,
        out_of_scope=False,
        email_mismatch_pending=False,
        conversation_id="conv-1",
        purchase_id="p-1",
        product_name="Curso Python",
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_send_access_skips_when_out_of_scope():
    state = make_state(None, out_of_scope=True)
    chatnexo = AsyncMock()
    result = await node_send_access(
        state,
        cademi_port=AsyncMock(),
        chatnexo_port=chatnexo,
    )
    chatnexo.send_message.assert_not_called()
    chatnexo.send_template.assert_not_called()
    assert result == {}


@pytest.mark.asyncio
async def test_send_access_skips_when_student_not_found():
    state = make_state(None)
    chatnexo = AsyncMock()
    result = await node_send_access(
        state,
        cademi_port=AsyncMock(),
        chatnexo_port=chatnexo,
    )
    chatnexo.send_message.assert_not_called()
    chatnexo.send_template.assert_not_called()


@pytest.mark.asyncio
async def test_send_access_skips_when_awaiting_cpf():
    state = make_state(None, cpf_asked=True)
    chatnexo = AsyncMock()
    await node_send_access(state, cademi_port=AsyncMock(), chatnexo_port=chatnexo)
    chatnexo.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_access_sends_free_text_within_24h():
    student = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/auto-login/nominal-abc"
    chatnexo = AsyncMock()
    state = make_state(student)
    state["within_24h_window"] = True

    result = await node_send_access(
        state,
        cademi_port=cademi,
        chatnexo_port=chatnexo,
    )
    cademi.get_access_link.assert_awaited_once_with(student_id="s1", product_id="p-1")
    chatnexo.send_message.assert_awaited_once()
    chatnexo.send_template.assert_not_called()
    assert "https://cademi.com.br/auto-login/nominal-abc" in chatnexo.send_message.await_args.kwargs["text"]
    assert result["access_link"] == "https://cademi.com.br/auto-login/nominal-abc"


@pytest.mark.asyncio
async def test_send_access_uses_template_outside_24h():
    student = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/auto-login/xyz"
    chatnexo = AsyncMock()
    state = make_state(student)
    state["within_24h_window"] = False

    await node_send_access(state, cademi_port=cademi, chatnexo_port=chatnexo)

    chatnexo.send_template.assert_awaited_once()
    call_kwargs = chatnexo.send_template.await_args.kwargs
    assert call_kwargs["template_name"] == "access_reminder_d1"  # ou o template de resend
    chatnexo.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_access_defaults_to_template_when_window_unknown():
    """RNF-08 fail-closed: se o Core não informou janela, usa template."""
    student = CademiStudent(id="s1", name="João", email="joao@email.com", phone="+5511999999999")
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/auto-login/xyz"
    chatnexo = AsyncMock()
    state = make_state(student)
    # within_24h_window ausente

    await node_send_access(state, cademi_port=cademi, chatnexo_port=chatnexo)

    chatnexo.send_template.assert_awaited_once()
    chatnexo.send_message.assert_not_called()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_access_send.py -v
```
Esperado: `NotImplementedError: Task 10`.

- [ ] **Step 3: Implementar o nó**

```python
# src/nexoia/application/capabilities/access.py (substituir o stub)

ACCESS_FREE_TEXT = (
    "Tudo certo! Aqui tá seu acesso, {name} — é só clicar que já entra direto: {link}"
)
# TODO (CQ-W03 / CQ-A01 já respondida por PRD 7.2):
# confirmar com equipe se existe template específico para reenvio reativo,
# ou se usamos o mesmo `access_reminder_d1` aprovado no spec ②.
ACCESS_RESEND_TEMPLATE = "access_reminder_d1"


async def node_send_access(
    state: AccessState,
    *,
    cademi_port: Any,
    chatnexo_port: Any,
) -> dict[str, Any]:
    """
    RF-A05 / PRD 7.2: envia link NOMINAL de auto-login.
    - Dentro da janela 24h → texto livre (send_message).
    - Fora da janela → template Meta aprovado (send_template).
    - Sem info de janela → template (fail-closed por RNF-08).
    """
    log = logger.bind(
        capability="access",
        node="send_access",
        account_id=state["account_id"],
        access_case_id=state.get("access_case_id"),
    )

    # Bypass: fora de escopo, lookup falhou, aguardando CPF, ou sem student
    if (
        state.get("out_of_scope")
        or state.get("access_case_id") is None
        or state.get("cpf_asked") and state.get("cademi_student") is None
        or state.get("cademi_student") is None
    ):
        return {}

    student: CademiStudent = state["cademi_student"]  # type: ignore[assignment]
    product_id = state.get("purchase_id", "")   # usar purchase_id como product_id (CQ-W01)
    link = await cademi_port.get_access_link(student_id=student.id, product_id=product_id)

    within_24h = bool(state.get("within_24h_window", False))
    if within_24h:
        text = ACCESS_FREE_TEXT.format(name=student.name.split()[0] if student.name else "", link=link)
        await chatnexo_port.send_message(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            text=text,
        )
        log.info("sent_free_text", conversation_id=state.get("conversation_id"))
    else:
        # RNF-08: fora da janela 24h (ou desconhecida) → template aprovado
        await chatnexo_port.send_template(
            account_id=state["account_id"],
            conversation_id=state.get("conversation_id"),
            template_name=ACCESS_RESEND_TEMPLATE,
            variables={
                "1": student.name or "",
                "2": state.get("product_name", ""),
                "3": link,
            },
        )
        log.info(
            "sent_template",
            template=ACCESS_RESEND_TEMPLATE,
            conversation_id=state.get("conversation_id"),
        )

    return {"access_link": link}
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_access_send.py -v
```
Esperado: 6 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/access.py \
        tests/unit/capabilities/test_access_send.py
git commit -m "feat(access): implement node_send_access with 24h-window decision (free text vs template)"
```

---

## Task 11: Nó `update_access_case`

**Files:**
- Modify: `src/nexoia/application/capabilities/access.py`
- Create: `tests/unit/capabilities/test_access_update.py`

> **RF-A08:** após envio bem-sucedido: `status = REACTIVE_LINK_SENT`, `search_attempts` atualizado.
> **RF-A04:** se escalou: `status = REACTIVE_ESCALATED` (o handoff_fn já foi chamado na cascade).

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/capabilities/test_access_update.py
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import AccessState, node_update_access_case
from nexoia.domain.entities.access_case import AccessCaseStatus
from nexoia.domain.ports.cademi_port import CademiStudent


def make_state(**kwargs) -> AccessState:
    base = dict(
        account_id=1,
        correlation_id="corr-1",
        messages=[],
        access_case_id="ac-1",
        student_email="joao@email.com",
        student_cpf="11122233344",
        student_name="João",
        student_phone="+5511999999999",
        cademi_student=None,
        search_attempts=1,
        cpf_asked=False,
        access_link=None,
        out_of_scope=False,
        email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_update_sets_reactive_link_sent_when_link_sent():
    repo = AsyncMock()
    state = make_state(
        cademi_student=CademiStudent(id="s1", name="João", email="j@e.com", phone=None),
        access_link="https://cademi.com.br/auto-login/abc",
        search_attempts=1,
    )
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_awaited_once_with(
        case_id="ac-1",
        status=AccessCaseStatus.REACTIVE_LINK_SENT,
        search_attempts=1,
    )


@pytest.mark.asyncio
async def test_update_sets_reactive_escalated_when_no_link():
    repo = AsyncMock()
    state = make_state(
        cademi_student=None,
        access_link=None,
        search_attempts=3,
    )
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_awaited_once_with(
        case_id="ac-1",
        status=AccessCaseStatus.REACTIVE_ESCALATED,
        search_attempts=3,
    )


@pytest.mark.asyncio
async def test_update_noop_when_no_access_case():
    repo = AsyncMock()
    state = make_state(access_case_id=None)
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_update_noop_when_out_of_scope():
    repo = AsyncMock()
    state = make_state(out_of_scope=True)
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_update_noop_when_awaiting_cpf():
    """Se ainda estamos esperando CPF do aluno, não é hora de atualizar status."""
    repo = AsyncMock()
    state = make_state(cpf_asked=True, cademi_student=None, access_link=None)
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_not_called()


@pytest.mark.asyncio
async def test_update_noop_when_email_mismatch_pending():
    repo = AsyncMock()
    state = make_state(email_mismatch_pending=True)
    await node_update_access_case(state, access_case_repo=repo)
    repo.update_status.assert_not_called()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_access_update.py -v
```
Esperado: `NotImplementedError: Task 11`.

- [ ] **Step 3: Implementar o nó**

```python
# src/nexoia/application/capabilities/access.py (substituir o stub)
from nexoia.domain.entities.access_case import AccessCaseStatus


async def node_update_access_case(
    state: AccessState,
    *,
    access_case_repo: Any,
) -> dict[str, Any]:
    """
    RF-A08 / RF-A04: finaliza o AccessCase com status reativo apropriado.

    Cenários:
    - Link enviado → REACTIVE_LINK_SENT
    - 3 tentativas sem match → REACTIVE_ESCALATED (handoff já feito na cascade)
    - Aguardando aluno (cpf_asked ou email_mismatch_pending) → noop
    - Out of scope ou sem AccessCase → noop
    """
    log = logger.bind(
        capability="access",
        node="update_access_case",
        account_id=state["account_id"],
        access_case_id=state.get("access_case_id"),
    )

    # Noop guards
    if state.get("access_case_id") is None or state.get("out_of_scope"):
        return {}
    if state.get("cpf_asked") and state.get("cademi_student") is None:
        return {}
    if state.get("email_mismatch_pending"):
        return {}

    attempts = state.get("search_attempts", 0)

    if state.get("access_link") and state.get("cademi_student") is not None:
        new_status = AccessCaseStatus.REACTIVE_LINK_SENT
    else:
        new_status = AccessCaseStatus.REACTIVE_ESCALATED

    await access_case_repo.update_status(
        case_id=state["access_case_id"],
        status=new_status,
        search_attempts=attempts,
    )
    log.info("access_case_updated", new_status=new_status.value, attempts=attempts)
    return {}
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_access_update.py -v
```
Esperado: 6 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/access.py \
        tests/unit/capabilities/test_access_update.py
git commit -m "feat(access): implement node_update_access_case with REACTIVE_LINK_SENT/ESCALATED logic"
```

---

## Task 12: Registrar subgraph Access no Intent Router

**Files:**
- Modify: `src/nexoia/application/intent_router.py`
- Create: `tests/unit/application/test_intent_router_access.py`

> **Objetivo:** quando o Intent Router classificar a intenção do aluno como `"access"`, o main graph do Core deve delegar ao subgraph da Capability Access.

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/application/test_intent_router_access.py
import pytest
from nexoia.application.intent_router import route_to_capability


def test_intent_access_routes_to_access_subgraph():
    node_name = route_to_capability(intent="access")
    assert node_name == "capability_access"


def test_intent_refund_routes_to_refund():
    node_name = route_to_capability(intent="refund")
    # sanity check — não deve bater na Access
    assert node_name != "capability_access"


def test_unknown_intent_falls_back_to_knowledge_or_default():
    node_name = route_to_capability(intent="chit_chat")
    assert node_name != "capability_access"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/application/test_intent_router_access.py -v
```
Esperado: a Access não está mapeada — teste falha.

- [ ] **Step 3: Adicionar a rota**

Em `src/nexoia/application/intent_router.py`, adicionar ao mapping/dict de intents:

```python
# src/nexoia/application/intent_router.py (trecho)
INTENT_TO_NODE = {
    "welcome": "capability_welcome",
    "access": "capability_access",      # ← novo (spec ③)
    "refund": "capability_refund",      # spec ④
    "loja_express": "capability_loja_express",
    "knowledge": "capability_knowledge",
    # ...
}


def route_to_capability(intent: str) -> str:
    """Retorna o nome do nó do main graph correspondente ao intent."""
    return INTENT_TO_NODE.get(intent, "capability_knowledge")  # fallback: KB
```

Adicionar o nó no main graph (onde a compilação do graph acontece):

```python
# src/nexoia/application/graph.py (trecho)
from nexoia.application.capabilities.access import build_access_subgraph

def build_main_graph() -> StateGraph:
    # ... construção existente (intent_router, welcome, etc.) ...
    graph.add_node("capability_access", build_access_subgraph().compile())
    graph.add_conditional_edges(
        "intent_router",
        lambda state: route_to_capability(state["intent"]),
        {
            "capability_welcome": "capability_welcome",
            "capability_access": "capability_access",   # ← novo
            # ...
        },
    )
    graph.add_edge("capability_access", END)
    return graph
```

> **Observação:** a forma exata de compor o subgraph no main graph segue o padrão estabelecido no spec ① (Core). Se o projeto usar `add_node` com subgraph compilado diretamente, o exemplo acima é válido; se usar `subgraph_as_node(...)`, adaptar.

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/application/test_intent_router_access.py -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/intent_router.py \
        src/nexoia/application/graph.py \
        tests/unit/application/test_intent_router_access.py
git commit -m "feat(access): register Access subgraph in intent_router and main graph"
```

---

## Task 13: Métricas Prometheus da Capability Access

**Files:**
- Modify: `src/nexoia/infrastructure/observability/metrics.py`
- Modify: `src/nexoia/application/capabilities/access.py` (instrumentar nós)
- Create: `tests/unit/observability/test_access_metrics.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/observability/test_access_metrics.py
from nexoia.infrastructure.observability.metrics import (
    access_capability_total,
    access_cademi_cascade_attempts,
    access_cpf_fallback_total,
)


def test_access_capability_counter_labels_exist():
    access_capability_total.labels(status="success").inc()
    access_capability_total.labels(status="escalated").inc()
    access_capability_total.labels(status="no_access_case").inc()
    access_capability_total.labels(status="out_of_scope").inc()
    access_capability_total.labels(status="error").inc()


def test_access_cascade_attempts_histogram_observes():
    access_cademi_cascade_attempts.observe(1)
    access_cademi_cascade_attempts.observe(2)
    access_cademi_cascade_attempts.observe(3)


def test_access_cpf_fallback_counter_increments():
    before = access_cpf_fallback_total._value.get()  # prometheus_client internal
    access_cpf_fallback_total.inc()
    after = access_cpf_fallback_total._value.get()
    assert after == before + 1
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/observability/test_access_metrics.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Adicionar as métricas**

```python
# src/nexoia/infrastructure/observability/metrics.py (adicionar)
from prometheus_client import Counter, Histogram

# Capability Access (spec ③)
access_capability_total = Counter(
    "access_capability_total",
    "Total de execuções da Capability Access",
    labelnames=["status"],  # success | escalated | no_access_case | out_of_scope | error
)
access_cademi_cascade_attempts = Histogram(
    "access_cademi_cascade_attempts",
    "Distribuição de tentativas até encontrar aluno na cascade Cademi",
    buckets=[1, 2, 3],
)
access_cpf_fallback_total = Counter(
    "access_cpf_fallback_total",
    "Vezes que a IA pediu CPF ao aluno (student_cpf=None no AccessCase)",
)
```

- [ ] **Step 4: Instrumentar os nós (instrumentação pontual)**

Em `src/nexoia/application/capabilities/access.py`, importar e incrementar nos locais-chave:

```python
# src/nexoia/application/capabilities/access.py (trechos pontuais)
from nexoia.infrastructure.observability.metrics import (
    access_capability_total,
    access_cademi_cascade_attempts,
    access_cpf_fallback_total,
)

# node_lookup_access_case — quando não achar:
access_capability_total.labels(status="no_access_case").inc()

# node_check_platform_scope — quando detectar shopee/kyc:
access_capability_total.labels(status="out_of_scope").inc()

# node_search_cademi_cascade — quando pedir CPF ao aluno:
access_cpf_fallback_total.inc()

# node_search_cademi_cascade — quando encontrar o aluno:
access_cademi_cascade_attempts.observe(attempts)
access_capability_total.labels(status="success").inc()

# node_search_cademi_cascade — quando escalar:
access_capability_total.labels(status="escalated").inc()
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/observability/test_access_metrics.py -v
uv run pytest tests/unit/capabilities/ -v  # smoke: nenhum teste existente quebrou
```
Esperado: 3 testes novos PASSED + suíte da Access continua verde.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/infrastructure/observability/metrics.py \
        src/nexoia/application/capabilities/access.py \
        tests/unit/observability/test_access_metrics.py
git commit -m "feat(access): add Prometheus metrics (capability_total, cascade_attempts, cpf_fallback)"
```

---

## Task 14: Teste de integração end-to-end da Capability Access

**Files:**
- Create: `tests/integration/test_access_flow.py`

> **Objetivo:** validar o fluxo completo combinando Welcome (cria AccessCase via webhook) + Access (aluno manda mensagem → cascade → link). Usa `FakeCademiClient` configurado por cenário, `FakeChatNexoClient` e banco real (testcontainers via fixture `db_session`).

- [ ] **Step 1: Escrever o teste de integração**

```python
# tests/integration/test_access_flow.py
"""
Integração end-to-end da Capability Access (spec ③).

Cenários cobertos:
  1) Happy path — cascade resolve no email (1ª tentativa) dentro da janela 24h.
  2) Fallback por CPF stored — email miss, CPF do AccessCase resolve.
  3) CPF pedido ao aluno — student_cpf=None, aluno responde, segue.
  4) Escalation — 3 tentativas falham; status vira REACTIVE_ESCALATED.
  5) Out of scope — aluno menciona Shopee; handoff silencioso e sem update.
"""
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import (
    AccessState,
    node_lookup_access_case,
    node_check_platform_scope,
    node_search_cademi_cascade,
    node_send_access,
    node_update_access_case,
)
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.domain.ports.cademi_port import CademiStudent
from nexoia.infrastructure.db.repositories.access_case_repo import AccessCaseRepository
from tests.fakes.fake_cademi_client import FakeCademiClient
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


async def _seed_access_case(db_session, *, cpf: str | None, phone: str) -> str:
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id=phone,
        conversation_id="conv-seed",
        purchase_id=f"purchase-seed-{phone}",
        product_name="Curso Python",
        student_cpf=cpf,
        status=AccessCaseStatus.LINK_SENT,  # welcome já enviou proativo
    )
    await repo.save(case)
    return case.id


def _make_state(
    phone: str,
    *,
    email: str,
    cpf: str | None,
    last_message: str,
    within_24h: bool = True,
    conversation_id: str = "conv-seed",
) -> AccessState:
    return {  # type: ignore[typeddict-item]
        "account_id": 1,
        "correlation_id": "corr-access-int",
        "messages": [{"role": "user", "content": last_message}],
        "access_case_id": None,
        "student_email": email,
        "student_cpf": cpf,
        "student_name": "João Silva",
        "student_phone": phone,
        "cademi_student": None,
        "search_attempts": 0,
        "cpf_asked": False,
        "access_link": None,
        "out_of_scope": False,
        "email_mismatch_pending": False,
        "conversation_id": conversation_id,
        "purchase_id": f"purchase-seed-{phone}",
        "product_name": "Curso Python",
        "within_24h_window": within_24h,
    }


async def _run_subgraph(
    state: AccessState,
    *,
    repo,
    cademi,
    chatnexo,
    handoff,
) -> AccessState:
    """Executa os 5 nós em sequência (simula o subgraph)."""
    updates = await node_lookup_access_case(
        state, access_case_repo=repo, chatnexo_port=chatnexo, handoff_fn=handoff
    )
    state.update(updates)
    updates = await node_check_platform_scope(state, handoff_fn=handoff)
    state.update(updates)
    updates = await node_search_cademi_cascade(
        state, cademi_port=cademi, chatnexo_port=chatnexo, handoff_fn=handoff
    )
    state.update(updates)
    updates = await node_send_access(
        state, cademi_port=cademi, chatnexo_port=chatnexo
    )
    state.update(updates)
    updates = await node_update_access_case(state, access_case_repo=repo)
    state.update(updates)
    return state


@pytest.mark.asyncio
async def test_happy_path_email_within_24h(db_session):
    phone = "+5511900000001"
    await _seed_access_case(db_session, cpf="11122233344", phone=phone)
    repo = AccessCaseRepository(db_session)

    alice = CademiStudent(id="s1", name="João Silva", email="joao@e.com", phone=phone)
    cademi = FakeCademiClient(
        students_by_email={"joao@e.com": alice},
        access_link="https://cademi.com.br/auto-login/nominal-alice",
    )
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf="11122233344",
        last_message="não consigo entrar no curso",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    # Assertions
    assert state["cademi_student"] == alice
    assert state["access_link"] == "https://cademi.com.br/auto-login/nominal-alice"
    assert chatnexo.last_sent_text is not None
    assert "https://cademi.com.br/auto-login/nominal-alice" in chatnexo.last_sent_text
    handoff.assert_not_called()

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.REACTIVE_LINK_SENT
    assert saved.search_attempts == 1


@pytest.mark.asyncio
async def test_found_by_cpf_stored(db_session):
    phone = "+5511900000002"
    await _seed_access_case(db_session, cpf="22233344455", phone=phone)
    repo = AccessCaseRepository(db_session)

    bob = CademiStudent(id="s2", name="João Silva", email="joao@e.com", phone=phone)
    cademi = FakeCademiClient(
        students_by_email={},   # email falha
        students_by_cpf={"22233344455": bob},
        access_link="https://cademi.com.br/auto-login/nominal-bob",
    )
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf=None,  # CPF vem do AccessCase via lookup
        last_message="esqueci senha, não consigo",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )
    assert state["cademi_student"] == bob
    assert state["search_attempts"] == 2

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.REACTIVE_LINK_SENT


@pytest.mark.asyncio
async def test_cpf_asked_when_none_in_access_case(db_session):
    phone = "+5511900000003"
    await _seed_access_case(db_session, cpf=None, phone=phone)  # Hubla não enviou document
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient(students_by_email={})  # email falha
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf=None,
        last_message="não consigo acessar, help",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    # Pediu CPF e interrompeu — AccessCase ainda NÃO foi atualizado
    assert state["cpf_asked"] is True
    assert state["cademi_student"] is None
    assert chatnexo.last_sent_text is not None
    assert "cpf" in chatnexo.last_sent_text.lower()

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.LINK_SENT  # não mudou ainda


@pytest.mark.asyncio
async def test_escalation_after_3_attempts(db_session):
    phone = "+5511900000004"
    await _seed_access_case(db_session, cpf="33344455566", phone=phone)
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient(
        students_by_email={},
        students_by_cpf={},
        name_phone_supported=False,  # CQ-A02: não suportado
    )
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf="33344455566",
        last_message="não consigo entrar",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    assert state["cademi_student"] is None
    assert state["search_attempts"] == 3
    handoff.assert_awaited()
    assert handoff.await_args.kwargs["reason"] == "cademi_not_found_after_3_attempts"

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.REACTIVE_ESCALATED
    assert saved.search_attempts == 3


@pytest.mark.asyncio
async def test_out_of_scope_shopee(db_session):
    phone = "+5511900000005"
    await _seed_access_case(db_session, cpf="44455566677", phone=phone)
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient()  # não será chamado
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf="44455566677",
        last_message="meu cadastro shopee tá travado, help!",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    assert state["out_of_scope"] is True
    assert cademi.email_calls == 0  # cascade não rodou
    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "shopee_or_kyc_out_of_scope"

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    # AccessCase não foi atualizado — mantém status da Welcome
    assert saved.status == AccessCaseStatus.LINK_SENT


@pytest.mark.asyncio
async def test_no_access_case_handoff(db_session):
    """RF-A01 parte final: aluno sem AccessCase → handoff silencioso."""
    phone_unknown = "+5511900000999"
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient()
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone_unknown, email="ghost@e.com", cpf=None,
        last_message="não consigo entrar",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "no_access_case"
    assert state["access_case_id"] is None
    # Cascade e send não rodam
    assert cademi.email_calls == 0
    assert chatnexo.last_sent_text is None
```

- [ ] **Step 2: Garantir que `FakeChatNexoClient` registra `last_sent_text`**

Confirmar que em `tests/fakes/fake_chatnexo_client.py` existe o atributo. Se o spec ② só registrou templates, adicionar também para `send_message`:

```python
# tests/fakes/fake_chatnexo_client.py (trecho — garantir que existe)
class FakeChatNexoClient:
    def __init__(self, ...):
        # ... existentes ...
        self.last_sent_text: str | None = None
        self.last_sent_template: str | None = None
        self.last_sent_variables: dict | None = None
        self.last_handoff_reason: str | None = None

    async def send_message(self, *, account_id, conversation_id, text):
        self.last_sent_text = text

    async def send_template(self, *, account_id, conversation_id, template_name, variables):
        self.last_sent_template = template_name
        self.last_sent_variables = variables

    async def transfer_to_human(self, *, account_id, conversation_id, reason):
        self.last_handoff_reason = reason
```

- [ ] **Step 3: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_access_flow.py -v
```
Esperado: 6 testes PASSED.

- [ ] **Step 4: Executar a suíte inteira para garantir sem regressões**

```bash
uv run pytest tests/ -v --tb=short
```
Esperado: todos PASSED (spec ① + spec ② + spec ③).

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_access_flow.py tests/fakes/fake_chatnexo_client.py
git commit -m "test(access): add end-to-end integration tests covering 6 cascade scenarios"
```

---

## Task 15: Atualizar INDEX.md e OPEN_QUESTIONS.md

**Files:**
- Modify: `docs/superpowers/INDEX.md`
- Modify: `docs/superpowers/OPEN_QUESTIONS.md`

- [ ] **Step 1: Atualizar INDEX.md**

Atualizar a linha do Spec ③ em `docs/superpowers/INDEX.md` para referenciar o plano:

```markdown
| ③ | **Capability Access** — aluno sem acesso ao produto | [spec](specs/2026-04-18-nexoia-capability-access-design.md) | [plano](plans/2026-04-18-nexoia-capability-access.md) | ⏳ Pendente |
```

E na seção "Planos":

```markdown
- `2026-04-18-nexoia-capability-access.md` — Plano ③: 15 tasks, TDD completo, cascade Cademi + REACTIVE_LINK_SENT
```

- [ ] **Step 2: Atualizar OPEN_QUESTIONS.md**

Confirmar que CQ-A01 permanece na seção "Respondidas" (já foi respondida por PRD 7.2 — link nominal de auto-login) e que CQ-A02 está na seção de pendências. Nenhuma mudança nova necessária se essa estrutura já existe.

Adicionar nota explícita em CQ-A02 indicando a cobertura do stub:

```markdown
### CQ-A02 — Cademi suporta busca por nome + telefone?
...
**Cobertura atual (Plano ③):**
- Port `CademiPort.get_student_by_name_phone` existe mas é stub.
- `FakeCademiClient.get_student_by_name_phone` levanta `NotImplementedError` por padrão (`name_phone_supported=False`).
- Nó `search_cademi_cascade` captura `NotImplementedError` e escala silenciosamente (RF-A04) — fluxo fail-safe.
- Quando a resposta chegar, basta implementar no `CademiClient` real e habilitar o suporte no fake.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/INDEX.md docs/superpowers/OPEN_QUESTIONS.md
git commit -m "docs: register Access plan in INDEX and add CQ-A02 coverage note"
```

---

## Self-Review

### Cobertura de RFs

| RF | Coberto por |
|----|-------------|
| `RF-A01` | Task 1 (campos) + Task 4 (`find_by_phone` com `account_id` — RNF-A01) + Task 7 (`node_lookup_access_case` + handoff silencioso quando não encontrado) + Task 14 (`test_no_access_case_handoff`) |
| `RF-A02` | Task 3 (FakeCademi cascade) + Task 9 (`node_search_cademi_cascade` — máx 3 tentativas) + Task 14 (cenários happy path email, fallback CPF, escalation) |
| `RF-A03` | Task 9 (asking_cpf + `cpf_asked=True`) + Task 14 (`test_cpf_asked_when_none_in_access_case`) |
| `RF-A04` | Task 9 (escalação após exaurir cascade — chama `handoff_fn`) + Task 11 (`node_update_access_case` → `REACTIVE_ESCALATED`) + Task 14 (`test_escalation_after_3_attempts`) |
| `RF-A05` | Task 10 (`node_send_access` com link nominal + within_24h_window → free text vs template Meta fail-closed) |
| `RF-A05a` | Task 8 (`node_check_platform_scope` detecta Shopee/KYC) + Task 14 (`test_out_of_scope_shopee`) |
| `RF-A05b` | Task 9 (email_mismatch_pending + `EMAIL_MISMATCH_MESSAGE`) + Task 9 (testes unitários cobrem fluxo) |
| `RF-A06` | Task 3 (Port + Fake com stub) + Task 9 (try/except `NotImplementedError` → handoff) + CQ-A02 referenciado em OPEN_QUESTIONS |
| `RF-A07` | Task 1 (campo `student_cpf`) + Task 2 (migration) + Task 5 (propaga `document` do webhook → handler → `node_persist_access_case`) + Task 5 teste (`test_payload_accepts_document_field`) |
| `RF-A08` | Task 11 (`node_update_access_case` → `REACTIVE_LINK_SENT` + `search_attempts`) + Task 14 (integração happy path verifica status no banco) |

### Cobertura de RNFs

| RNF | Coberto por |
|-----|-------------|
| `RNF-A01` | Task 4 (`find_by_phone` sempre filtra `account_id`) + Task 4 teste (`test_find_by_phone_respects_account_id_isolation`) + Task 7 (`node_lookup_access_case` passa `state["account_id"]`) |
| `RNF-A02` | Task 9 (fluxo de CPF atravessa turnos via `cpf_asked` + `search_attempts` no state → checkpoint LangGraph herdado do Core) |
| `RNF-A03` | `CademiClient` / `CademiPort` herdados do Core/spec ② mantêm circuit breaker — não refatorados aqui |
| `RNF-A04` | Tasks 7-14: cada nó com 3+ testes unitários + 6 testes de integração cobrindo happy path + 5 ramos de borda |
| `RNF-A05` | Idle/timeout não é tocado — responsabilidade do Core (spec ①). Subgraph é invocado por turno e termina |

### Dependências claras

- Tasks 1-2 (entidade + migration) são pré-requisito de Task 4 (repo).
- Task 3 (port + fake) é pré-requisito de Tasks 7-11 (nós do subgraph).
- Task 5 (webhook → AccessCase.student_cpf) é pré-requisito para Task 9 tentativa 2 funcionar via CPF stored em cenários reais.
- Task 6 cria esqueleto antes dos nós reais; Tasks 7-11 substituem cada stub `NotImplementedError` por implementação testada.
- Task 12 conecta o subgraph ao main graph — só faz sentido após Tasks 7-11.
- Task 13 adiciona observabilidade — pode ser instrumentada em paralelo, mas commit depois.
- Task 14 é integração E2E — última task de código, antes da documentação.

### Tipos e invariantes consistentes

- `AccessState` estende `ConversationState` do Core (spec ①) — herda `account_id`, `correlation_id`, `messages`, `conversation_id`.
- `student_phone` armazena o telefone normalizado do Core (ex: `+55...`) — mesmo formato que é usado como `contact_id` no `AccessCase` criado pela Welcome.
- `search_attempts` é `0..3`: 0 inicial, 1 após email, 2 após CPF, 3 após nome+telefone ou quando `NotImplementedError`.
- `cpf_asked=True` é idempotente entre turnos; só retorna a `False` se o nó retomar cascade com sucesso.
- Regras de PRD 7.2 (Shopee/KYC, email mismatch, link nominal) estão implementadas como código Python determinístico — NÃO como instrução no prompt (RNF-02 do core).

### Sem placeholders vagos

Todos os TODOs têm referência explícita:
- `CQ-A02` (Cademi nome+telefone): Tasks 3, 9.
- `CQ-W01` (documentação Cademi API): herdado do spec ② — `CademiClient` continua stub.
- `CQ-W03` (template de resend reativo): Task 10 usa `access_reminder_d1` como default; nota no código menciona confirmação com equipe.

### Runtime de execução sugerido

15 tasks × ~15-25 min cada (TDD completo) = ~4-6 horas de execução focada em sessão supervisionada com subagent-driven-development, ou ~1 dia com code review entre tasks.
