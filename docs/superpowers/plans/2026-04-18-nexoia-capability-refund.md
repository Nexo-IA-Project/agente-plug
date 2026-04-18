# Capability Refund & Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Capability Refund & Retention — subgraph LangGraph acionado quando `intent = "refund"`. Coleta motivo + email + CPF, busca compra na Hubla (stub Playwright), verifica prazo CDC (Art. 49), tenta retenção N1 → N2, processa reembolso ou nega. Implementa 5 guards obrigatórios (PRD 7.3) e mutex Redis para deduplicação de jobs.

**Architecture:** Subgraph LangGraph com nós sequenciais e condicionais (`collect` → `check_deadline` → `retention_loop` → `process_refund`/`deny`/`deliver_offer`). Depende do Core (Spec ①) já implementado. `HublaClient` é stub — levanta `NotImplementedError` com referência a `OPEN_QUESTIONS.md#CQ-R01` e `#CQ-R04`. Cinco guards (`ExplicitRefundRequestGuard`, `ProductBlockedGuard`, `MandatoryRetentionGuard`, `SameTurnBlockGuard`, `RefundMutexGuard`) protegem `process_refund`; `LegalMentionGuard` é herdado do Core.

**Tech Stack:** Python 3.12, LangGraph, SQLAlchemy 2 async, Alembic, redis-py, structlog, prometheus-client, pytest, pytest-asyncio, testcontainers, uv

**Prerequisite:** Core (Spec ①) deve estar completamente implementado: `LegalMentionGuard`, mutex helpers Redis, `HandoffService`, `Legal History`, `ConversationState`, `intent_router`, `ChatNexoPort.send_text`/`send_template`, métricas base.

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `src/nexoia/domain/entities/refund_case.py` | Criar | Entidade `RefundCase` + enum `RefundCaseStatus` + enum `RefundStep` |
| `src/nexoia/domain/ports/hubla_port.py` | Criar | Protocol `HublaPort` |
| `src/nexoia/infrastructure/hubla/__init__.py` | Criar | Package marker |
| `src/nexoia/infrastructure/hubla/schemas.py` | Criar | Value objects `HublaPurchase`, `RefundResult` |
| `src/nexoia/infrastructure/hubla/client.py` | Criar | Stub `HublaClient` (Playwright-based) |
| `src/nexoia/domain/errors.py` | Modificar | Adicionar `HublaError`, `RefundMutexError` |
| `src/nexoia/infrastructure/db/models.py` | Modificar | Adicionar `RefundCaseModel` |
| `src/nexoia/infrastructure/db/repositories/refund_case_repo.py` | Criar | `RefundCaseRepository` |
| `migrations/versions/xxxx_add_refund_cases_table.py` | Criar | Alembic migration |
| `src/nexoia/application/capabilities/refund/__init__.py` | Criar | Package marker |
| `src/nexoia/application/capabilities/refund/state.py` | Criar | `RefundState` |
| `src/nexoia/application/capabilities/refund/guards/__init__.py` | Criar | Package marker |
| `src/nexoia/application/capabilities/refund/guards/explicit_request.py` | Criar | Guard 1 — `ExplicitRefundRequestGuard` |
| `src/nexoia/application/capabilities/refund/guards/product_blocked.py` | Criar | Guard 2 — `ProductBlockedGuard` |
| `src/nexoia/application/capabilities/refund/guards/mandatory_retention.py` | Criar | Guard 3 — `MandatoryRetentionGuard` |
| `src/nexoia/application/capabilities/refund/guards/same_turn_block.py` | Criar | Guard 4 — `SameTurnBlockGuard` |
| `src/nexoia/application/capabilities/refund/guards/refund_mutex.py` | Criar | Guard 5 — `RefundMutexGuard` (Redis SETNX TTL 1h) |
| `src/nexoia/application/capabilities/refund/nodes.py` | Criar | Nós `collect`, `check_deadline`, `retention_loop`, `process_refund`, `deny`, `deliver_offer` |
| `src/nexoia/application/capabilities/refund/graph.py` | Criar | `build_refund_subgraph` |
| `src/nexoia/application/intent_router.py` | Modificar | Adicionar intent `"refund"` ao roteamento |
| `src/nexoia/config/settings.py` | Modificar | `REFUND_DEADLINE_DAYS=7`, `REFUND_MUTEX_TTL_SECONDS=3600` |
| `src/nexoia/infrastructure/observability/metrics.py` | Modificar | Métricas Prometheus da capability |
| `tests/fakes/fake_hubla_client.py` | Criar | Fake configurável do `HublaPort` |
| `tests/fakes/fake_chatnexo_client.py` | Modificar | Garantir `last_sent_text`/`last_sent_template` |
| `tests/unit/domain/test_refund_case.py` | Criar | Testes da entidade |
| `tests/unit/domain/test_hubla_port.py` | Criar | Testes do port + fake |
| `tests/unit/infrastructure/test_hubla_client.py` | Criar | Stub levanta `NotImplementedError` |
| `tests/unit/capabilities/refund/test_guards.py` | Criar | Unit tests dos 5 guards |
| `tests/unit/capabilities/refund/test_nodes.py` | Criar | Unit tests dos nós |
| `tests/unit/capabilities/refund/test_intent_router.py` | Criar | Intent router reconhece "refund" |
| `tests/unit/observability/test_refund_metrics.py` | Criar | Métricas expostas |
| `tests/integration/test_refund_case_repo.py` | Criar | Persistência de `RefundCase` |
| `tests/integration/test_refund_flow.py` | Criar | E2E da capability |
| `docs/superpowers/OPEN_QUESTIONS.md` | Modificar | Garantir CQ-R03 aberta; CQ-R01/02/04 já respondidas |
| `docs/superpowers/INDEX.md` | Modificar | Marcar plano ④ como criado |

---

## Task 1: RefundCase entity + RefundCaseStatus + RefundStep enums

**Files:**
- Create: `src/nexoia/domain/entities/refund_case.py`
- Test: `tests/unit/domain/test_refund_case.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/domain/test_refund_case.py
from nexoia.domain.entities.refund_case import (
    RefundCase,
    RefundCaseStatus,
    RefundStep,
)


def test_refund_case_default_status_is_collecting():
    case = RefundCase(
        account_id=1,
        contact_id="contact-123",
        conversation_id="conv-456",
        student_email="aluno@email.com",
    )
    assert case.status == RefundCaseStatus.COLLECTING
    assert case.offers_made == []
    assert case.offer_accepted is False
    assert case.within_deadline is None
    assert case.student_cpf is None
    assert case.refund_reason is None
    assert case.purchase_id is None


def test_refund_case_uuid_id():
    case = RefundCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        student_email="a@a.com",
    )
    assert len(case.id) == 36  # UUID format


def test_refund_case_status_enum_string_values():
    assert RefundCaseStatus.COLLECTING == "collecting"
    assert RefundCaseStatus.CHECKING_DEADLINE == "checking_deadline"
    assert RefundCaseStatus.IN_RETENTION == "in_retention"
    assert RefundCaseStatus.OFFER_ACCEPTED == "offer_accepted"
    assert RefundCaseStatus.REFUNDED == "refunded"
    assert RefundCaseStatus.DENIED == "denied"
    assert RefundCaseStatus.ESCALATED == "escalated"


def test_refund_step_enum_string_values():
    assert RefundStep.COLLECT == "collect"
    assert RefundStep.DEADLINE == "check_deadline"
    assert RefundStep.RETENTION == "retention"
    assert RefundStep.PROCESS == "process_refund"
    assert RefundStep.DENY == "deny"
    assert RefundStep.DONE == "done"


def test_refund_case_offers_made_is_independent_per_instance():
    """Regressão: default_factory evita lista compartilhada."""
    case_a = RefundCase(
        account_id=1, contact_id="a", conversation_id="cv", student_email="a@a.com"
    )
    case_b = RefundCase(
        account_id=1, contact_id="b", conversation_id="cv", student_email="b@b.com"
    )
    case_a.offers_made.append("N1")
    assert case_b.offers_made == []
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
cd /path/to/nexoia-agent
uv run pytest tests/unit/domain/test_refund_case.py -v
```
Esperado: `ImportError` / `ModuleNotFoundError`

- [ ] **Step 3: Implementar a entidade**

```python
# src/nexoia/domain/entities/refund_case.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class RefundCaseStatus(str, Enum):
    COLLECTING = "collecting"
    CHECKING_DEADLINE = "checking_deadline"
    IN_RETENTION = "in_retention"
    OFFER_ACCEPTED = "offer_accepted"
    REFUNDED = "refunded"
    DENIED = "denied"
    ESCALATED = "escalated"


class RefundStep(str, Enum):
    """Etapa corrente no subgraph (usado para logs/observabilidade)."""

    COLLECT = "collect"
    DEADLINE = "check_deadline"
    RETENTION = "retention"
    PROCESS = "process_refund"
    DENY = "deny"
    DONE = "done"


@dataclass
class RefundCase:
    account_id: int
    contact_id: str
    conversation_id: str
    student_email: str

    id: str = field(default_factory=lambda: str(uuid4()))
    purchase_id: str | None = None
    product_name: str | None = None
    student_cpf: str | None = None
    refund_reason: str | None = None
    days_since_purchase: int | None = None
    within_deadline: bool | None = None
    offers_made: list[str] = field(default_factory=list)
    offer_accepted: bool = False
    status: RefundCaseStatus = RefundCaseStatus.COLLECTING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_refund_case.py -v
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/entities/refund_case.py tests/unit/domain/test_refund_case.py
git commit -m "feat(refund): add RefundCase entity with RefundCaseStatus and RefundStep enums"
```

---

## Task 2: HublaPort + HublaPurchase + RefundResult + HublaError

**Files:**
- Create: `src/nexoia/domain/ports/hubla_port.py`
- Create: `src/nexoia/infrastructure/hubla/__init__.py`
- Create: `src/nexoia/infrastructure/hubla/schemas.py`
- Modify: `src/nexoia/domain/errors.py`
- Create: `tests/fakes/fake_hubla_client.py`
- Test: `tests/unit/domain/test_hubla_port.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/domain/test_hubla_port.py
from datetime import datetime, timezone

import pytest

from nexoia.domain.errors import HublaError
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.infrastructure.hubla.schemas import HublaPurchase, RefundResult


def test_hubla_purchase_is_frozen():
    purchase = HublaPurchase(
        id="p-1",
        product_name="Curso X",
        created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
        amount=497.0,
        is_duplicate=False,
        is_recurring=False,
        first_charge_at=None,
    )
    with pytest.raises(Exception):
        purchase.amount = 0.0  # type: ignore[misc]


def test_hubla_purchase_recurring_has_first_charge_at():
    first_charge = datetime(2026, 3, 15, tzinfo=timezone.utc)
    purchase = HublaPurchase(
        id="p-2",
        product_name="Assinatura",
        created_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        amount=97.0,
        is_duplicate=False,
        is_recurring=True,
        first_charge_at=first_charge,
    )
    assert purchase.is_recurring is True
    assert purchase.first_charge_at == first_charge


def test_refund_result_success():
    result = RefundResult(success=True, refund_id="rf-001", error=None)
    assert result.success is True
    assert result.refund_id == "rf-001"
    assert result.error is None


def test_refund_result_failure_has_error():
    result = RefundResult(success=False, refund_id=None, error="timeout")
    assert result.success is False
    assert result.error == "timeout"


def test_hubla_error_is_exception():
    err = HublaError("Playwright session expired")
    assert isinstance(err, Exception)
    assert str(err) == "Playwright session expired"


@pytest.mark.asyncio
async def test_fake_hubla_satisfies_port():
    from tests.fakes.fake_hubla_client import FakeHublaClient

    client = FakeHublaClient()
    # Satisfaz o Protocol se tiver os métodos assíncronos
    assert hasattr(client, "get_purchase_by_email")
    assert hasattr(client, "process_refund")
    # Pode ser usada como HublaPort (Protocol estrutural)
    port: HublaPort = client  # noqa: F841
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/domain/test_hubla_port.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar erros de domínio**

No arquivo `src/nexoia/domain/errors.py`, adicionar ao final:

```python
class HublaError(Exception):
    """Falha ao comunicar com Hubla (Playwright). Ver OPEN_QUESTIONS.md#CQ-R01."""


class RefundMutexError(Exception):
    """Levantado quando o mutex de reembolso já está adquirido (job duplicado)."""
```

- [ ] **Step 4: Criar o package e schemas**

```bash
mkdir -p src/nexoia/infrastructure/hubla
touch src/nexoia/infrastructure/hubla/__init__.py
```

```python
# src/nexoia/infrastructure/hubla/schemas.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HublaPurchase:
    """Compra encontrada na Hubla.

    - `is_recurring=True`: prazo CDC conta a partir de `first_charge_at`
      (PRD 7.3 Passo 2 — recorrente: prazo conta da primeira parcela).
    - `is_duplicate=True`: o mesmo contact_id tem 2+ compras do mesmo produto
      → processa reembolso sem retenção.
    """

    id: str
    product_name: str
    created_at: datetime
    amount: float
    is_duplicate: bool
    is_recurring: bool
    first_charge_at: datetime | None


@dataclass(frozen=True)
class RefundResult:
    success: bool
    refund_id: str | None
    error: str | None
```

- [ ] **Step 5: Criar o port**

```python
# src/nexoia/domain/ports/hubla_port.py
from __future__ import annotations

from typing import Protocol

from nexoia.infrastructure.hubla.schemas import HublaPurchase, RefundResult


class HublaPort(Protocol):
    async def get_purchase_by_email(
        self, email: str, account_id: int
    ) -> HublaPurchase | None:
        """Busca a compra mais recente do aluno pelo e-mail.

        Retorna `None` se nenhuma compra for encontrada.
        Ver OPEN_QUESTIONS.md#CQ-R04 (Playwright, não há API REST).
        """
        ...

    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult:
        """Processa o reembolso da compra. Assíncrono do lado da Hubla.

        Ver OPEN_QUESTIONS.md#CQ-R01 (Playwright, timeout 150s, concorrência=1).
        """
        ...
```

- [ ] **Step 6: Criar o FakeHublaClient**

```python
# tests/fakes/fake_hubla_client.py
from __future__ import annotations

from datetime import datetime, timezone

from nexoia.domain.errors import HublaError
from nexoia.infrastructure.hubla.schemas import HublaPurchase, RefundResult


class FakeHublaClient:
    """Fake configurável do HublaPort para testes.

    - `purchase`: objeto retornado em `get_purchase_by_email`. Passe `None`
      para simular "compra não encontrada".
    - `fail_times_get`: nº de falhas consecutivas em `get_purchase_by_email`
      antes de retornar `purchase`.
    - `refund_result`: resultado retornado em `process_refund`.
    - `fail_times_refund`: nº de falhas em `process_refund`.
    """

    def __init__(
        self,
        purchase: HublaPurchase | None = None,
        fail_times_get: int = 0,
        refund_result: RefundResult | None = None,
        fail_times_refund: int = 0,
    ) -> None:
        self._purchase = purchase
        self._fail_times_get = fail_times_get
        self._refund_result = refund_result or RefundResult(
            success=True, refund_id="rf-fake-001", error=None
        )
        self._fail_times_refund = fail_times_refund
        self.get_calls = 0
        self.refund_calls = 0
        self.last_refund_reason: str | None = None

    async def get_purchase_by_email(
        self, email: str, account_id: int
    ) -> HublaPurchase | None:
        self.get_calls += 1
        if self.get_calls <= self._fail_times_get:
            raise HublaError(f"Hubla get failed (attempt {self.get_calls})")
        return self._purchase

    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult:
        self.refund_calls += 1
        self.last_refund_reason = reason
        if self.refund_calls <= self._fail_times_refund:
            raise HublaError(f"Hubla refund failed (attempt {self.refund_calls})")
        return self._refund_result

    # Utilitário para testes
    @staticmethod
    def make_purchase(
        days_ago: int = 3,
        is_recurring: bool = False,
        is_duplicate: bool = False,
        product_name: str = "Curso Python",
        purchase_id: str = "p-fake-001",
    ) -> HublaPurchase:
        now = datetime.now(timezone.utc)
        created = now.replace(microsecond=0)
        from datetime import timedelta

        created = created - timedelta(days=days_ago)
        return HublaPurchase(
            id=purchase_id,
            product_name=product_name,
            created_at=created,
            amount=497.0,
            is_duplicate=is_duplicate,
            is_recurring=is_recurring,
            first_charge_at=created if is_recurring else None,
        )
```

- [ ] **Step 7: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/domain/test_hubla_port.py -v
```
Esperado: 6 testes PASSED

- [ ] **Step 8: Commit**

```bash
git add src/nexoia/domain/ports/hubla_port.py \
        src/nexoia/domain/errors.py \
        src/nexoia/infrastructure/hubla/ \
        tests/fakes/fake_hubla_client.py \
        tests/unit/domain/test_hubla_port.py
git commit -m "feat(refund): add HublaPort, HublaPurchase, RefundResult, HublaError and FakeHublaClient"
```

---

## Task 3: HublaClient stub (Playwright-based, NotImplementedError)

**Files:**
- Create: `src/nexoia/infrastructure/hubla/client.py`
- Test: `tests/unit/infrastructure/test_hubla_client.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/infrastructure/test_hubla_client.py
import pytest

from nexoia.infrastructure.hubla.client import HublaClient


@pytest.mark.asyncio
async def test_hubla_client_get_purchase_raises_not_implemented():
    client = HublaClient(base_url="http://fake", username="u", password="p")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.get_purchase_by_email("aluno@email.com", account_id=1)


@pytest.mark.asyncio
async def test_hubla_client_process_refund_raises_not_implemented():
    client = HublaClient(base_url="http://fake", username="u", password="p")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.process_refund("purchase-1", "cliente pediu")


def test_hubla_client_stores_credentials():
    client = HublaClient(base_url="https://hubla.com", username="bot", password="secret")
    assert client._base_url == "https://hubla.com"
    assert client._username == "bot"
    assert client._password == "secret"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/infrastructure/test_hubla_client.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar o stub**

```python
# src/nexoia/infrastructure/hubla/client.py
# ⚠️  ATENÇÃO: Este cliente é um STUB.
# ANTES DE IMPLEMENTAR: consultar docs/superpowers/OPEN_QUESTIONS.md
#   - CQ-R01 (Playwright, timeout 150s, concorrência=1, MFA via IMAP)
#   - CQ-R04 (Playwright para get_purchase_by_email — não existe API REST pública)
#
# Requisitos documentados no PRD 12:
#   - Browser automation (Playwright) com self-healing de sessão
#   - Timeout 150s por operação
#   - Concorrência máxima = 1 (serializar operações via queue/worker)
#   - MFA por IMAP Gmail (credenciais em env)
from __future__ import annotations

from nexoia.infrastructure.hubla.schemas import HublaPurchase, RefundResult


class HublaClient:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self._base_url = base_url
        self._username = username
        self._password = password

    async def get_purchase_by_email(
        self, email: str, account_id: int
    ) -> HublaPurchase | None:
        # TODO (CQ-R04): implementar via Playwright.
        # Ver docs/superpowers/OPEN_QUESTIONS.md#CQ-R04
        raise NotImplementedError(
            "HublaClient.get_purchase_by_email não implementado — "
            "ver OPEN_QUESTIONS.md#CQ-R04 (Playwright, sem API REST)"
        )

    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult:
        # TODO (CQ-R01): implementar via Playwright.
        # Ver docs/superpowers/OPEN_QUESTIONS.md#CQ-R01
        raise NotImplementedError(
            "HublaClient.process_refund não implementado — "
            "ver OPEN_QUESTIONS.md#CQ-R01 (Playwright, timeout 150s, concorrência=1, MFA IMAP)"
        )
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/infrastructure/test_hubla_client.py -v
```
Esperado: 3 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/hubla/client.py \
        tests/unit/infrastructure/test_hubla_client.py
git commit -m "feat(refund): add HublaClient stub raising NotImplementedError with CQ refs"
```

---

## Task 4: Settings — REFUND_DEADLINE_DAYS e REFUND_MUTEX_TTL_SECONDS

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Test: `tests/unit/config/test_settings_refund.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/config/test_settings_refund.py
from nexoia.config.settings import Settings


def test_refund_settings_defaults():
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://localhost:6379",
        CHATNEXO_API_KEY="key",
        OPENAI_API_KEY="sk-test",
    )
    assert s.REFUND_DEADLINE_DAYS == 7  # Art. 49 CDC
    assert s.REFUND_MUTEX_TTL_SECONDS == 3600  # 1h (PRD 7.3 Guard 5)
    assert s.HUBLA_BASE_URL == ""
    assert s.HUBLA_USERNAME == ""
    assert s.HUBLA_PASSWORD == ""


def test_refund_settings_overridable():
    s = Settings(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://localhost:6379",
        CHATNEXO_API_KEY="k",
        OPENAI_API_KEY="sk",
        REFUND_DEADLINE_DAYS=14,
        REFUND_MUTEX_TTL_SECONDS=600,
    )
    assert s.REFUND_DEADLINE_DAYS == 14
    assert s.REFUND_MUTEX_TTL_SECONDS == 600
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/config/test_settings_refund.py -v
```
Esperado: `AttributeError` ou `ValidationError`

- [ ] **Step 3: Adicionar variáveis ao Settings**

No arquivo `src/nexoia/config/settings.py`, adicionar ao model `Settings`:

```python
    # Capability Refund & Retention (PRD 7.3 + CDC Art. 49)
    REFUND_DEADLINE_DAYS: int = 7  # prazo CDC Art. 49
    REFUND_MUTEX_TTL_SECONDS: int = 3600  # PRD 7.3 Guard 5: TTL 1h

    # Hubla (stub — ver OPEN_QUESTIONS.md#CQ-R01 e #CQ-R04)
    HUBLA_BASE_URL: str = ""
    HUBLA_USERNAME: str = ""
    HUBLA_PASSWORD: str = ""
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/config/test_settings_refund.py -v
```
Esperado: 2 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/config/settings.py tests/unit/config/test_settings_refund.py
git commit -m "feat(refund): add REFUND_DEADLINE_DAYS, REFUND_MUTEX_TTL_SECONDS and Hubla settings"
```

---

## Task 5: Alembic migration + RefundCaseModel

**Files:**
- Modify: `src/nexoia/infrastructure/db/models.py`
- Create: `migrations/versions/xxxx_add_refund_cases_table.py`

- [ ] **Step 1: Adicionar o model SQLAlchemy**

No arquivo `src/nexoia/infrastructure/db/models.py`, adicionar:

```python
from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID


class RefundCaseModel(Base):
    __tablename__ = "refund_cases"

    id = Column(PG_UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    account_id = Column(Integer, nullable=False, index=True)
    contact_id = Column(String, nullable=False)
    conversation_id = Column(String, nullable=False)
    purchase_id = Column(String, nullable=True)
    product_name = Column(String, nullable=True)
    student_email = Column(String, nullable=False)
    student_cpf = Column(String, nullable=True)
    refund_reason = Column(String, nullable=True)
    days_since_purchase = Column(Integer, nullable=True)
    within_deadline = Column(Boolean, nullable=True)
    offers_made = Column(JSONB, nullable=False, default=list)
    offer_accepted = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="collecting")
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
        Index("idx_refund_cases_account_contact", "account_id", "contact_id"),
    )
```

- [ ] **Step 2: Gerar migration Alembic**

```bash
uv run alembic revision --autogenerate -m "add_refund_cases_table"
```
Esperado: arquivo criado em `migrations/versions/XXXX_add_refund_cases_table.py`

- [ ] **Step 3: Revisar o arquivo gerado**

Abrir o arquivo e garantir:
- `op.create_table("refund_cases", ...)` com todas as colunas
- `offers_made` como `JSONB` com default `[]`
- `op.create_index("idx_refund_cases_account_contact", ...)`
- `downgrade()` drop the table and index

- [ ] **Step 4: Aplicar no banco dev**

```bash
uv run alembic upgrade head
```
Esperado: migration aplicada sem erro

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/models.py migrations/versions/
git commit -m "feat(refund): add refund_cases table migration and SQLAlchemy model"
```

---

## Task 6: RefundCaseRepository

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/refund_case_repo.py`
- Test: `tests/integration/test_refund_case_repo.py`

- [ ] **Step 1: Escrever o teste de integração falhando**

```python
# tests/integration/test_refund_case_repo.py
import pytest

from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.infrastructure.db.repositories.refund_case_repo import (
    RefundCaseRepository,
)


@pytest.mark.asyncio
async def test_save_and_get_by_id(db_session):
    repo = RefundCaseRepository(db_session)
    case = RefundCase(
        account_id=1,
        contact_id="c-1",
        conversation_id="conv-1",
        student_email="aluno@email.com",
        student_cpf="12345678900",
        refund_reason="Não gostei",
        status=RefundCaseStatus.COLLECTING,
    )
    await repo.save(case)

    found = await repo.get_by_id(case.id)
    assert found is not None
    assert found.student_email == "aluno@email.com"
    assert found.status == RefundCaseStatus.COLLECTING
    assert found.offers_made == []


@pytest.mark.asyncio
async def test_update_status_and_offers(db_session):
    repo = RefundCaseRepository(db_session)
    case = RefundCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        student_email="a@a.com",
    )
    await repo.save(case)

    case.status = RefundCaseStatus.IN_RETENTION
    case.offers_made = ["N1"]
    await repo.update(case)

    reloaded = await repo.get_by_id(case.id)
    assert reloaded.status == RefundCaseStatus.IN_RETENTION
    assert reloaded.offers_made == ["N1"]


@pytest.mark.asyncio
async def test_update_to_refunded_persists_offers(db_session):
    repo = RefundCaseRepository(db_session)
    case = RefundCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        student_email="a@a.com",
    )
    await repo.save(case)

    case.offers_made = ["N1", "N2"]
    case.status = RefundCaseStatus.REFUNDED
    case.within_deadline = True
    case.days_since_purchase = 3
    case.purchase_id = "hubla-p-001"
    await repo.update(case)

    reloaded = await repo.get_by_id(case.id)
    assert reloaded.offers_made == ["N1", "N2"]
    assert reloaded.status == RefundCaseStatus.REFUNDED
    assert reloaded.within_deadline is True
    assert reloaded.days_since_purchase == 3
    assert reloaded.purchase_id == "hubla-p-001"


@pytest.mark.asyncio
async def test_get_by_id_not_found_returns_none(db_session):
    repo = RefundCaseRepository(db_session)
    result = await repo.get_by_id("non-existent-uuid")
    assert result is None


@pytest.mark.asyncio
async def test_list_by_account_and_contact(db_session):
    repo = RefundCaseRepository(db_session)
    c1 = RefundCase(
        account_id=1, contact_id="contact-x", conversation_id="cv1",
        student_email="a@a.com",
    )
    c2 = RefundCase(
        account_id=1, contact_id="contact-x", conversation_id="cv2",
        student_email="b@b.com",
    )
    c3 = RefundCase(
        account_id=1, contact_id="contact-y", conversation_id="cv3",
        student_email="c@c.com",
    )
    await repo.save(c1)
    await repo.save(c2)
    await repo.save(c3)

    cases = await repo.list_by_contact(account_id=1, contact_id="contact-x")
    assert len(cases) == 2
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_refund_case_repo.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar o repositório**

```python
# src/nexoia/infrastructure/db/repositories/refund_case_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.infrastructure.db.models import RefundCaseModel


class RefundCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, case: RefundCase) -> None:
        model = RefundCaseModel(
            id=case.id,
            account_id=case.account_id,
            contact_id=case.contact_id,
            conversation_id=case.conversation_id,
            purchase_id=case.purchase_id,
            product_name=case.product_name,
            student_email=case.student_email,
            student_cpf=case.student_cpf,
            refund_reason=case.refund_reason,
            days_since_purchase=case.days_since_purchase,
            within_deadline=case.within_deadline,
            offers_made=list(case.offers_made),
            offer_accepted=case.offer_accepted,
            status=case.status.value,
        )
        self._session.add(model)
        await self._session.commit()

    async def update(self, case: RefundCase) -> None:
        model = await self._session.get(RefundCaseModel, case.id)
        if model is None:
            raise ValueError(f"RefundCase {case.id} not found")
        model.purchase_id = case.purchase_id
        model.product_name = case.product_name
        model.student_cpf = case.student_cpf
        model.refund_reason = case.refund_reason
        model.days_since_purchase = case.days_since_purchase
        model.within_deadline = case.within_deadline
        model.offers_made = list(case.offers_made)
        model.offer_accepted = case.offer_accepted
        model.status = case.status.value
        await self._session.commit()

    async def get_by_id(self, case_id: str) -> RefundCase | None:
        result = await self._session.execute(
            select(RefundCaseModel).where(RefundCaseModel.id == case_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return self._to_entity(model)

    async def list_by_contact(
        self, account_id: int, contact_id: str
    ) -> list[RefundCase]:
        result = await self._session.execute(
            select(RefundCaseModel).where(
                RefundCaseModel.account_id == account_id,
                RefundCaseModel.contact_id == contact_id,
            )
        )
        return [self._to_entity(m) for m in result.scalars().all()]

    def _to_entity(self, model: RefundCaseModel) -> RefundCase:
        case = RefundCase(
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            student_email=model.student_email,
        )
        case.id = str(model.id)
        case.purchase_id = model.purchase_id
        case.product_name = model.product_name
        case.student_cpf = model.student_cpf
        case.refund_reason = model.refund_reason
        case.days_since_purchase = model.days_since_purchase
        case.within_deadline = model.within_deadline
        case.offers_made = list(model.offers_made or [])
        case.offer_accepted = model.offer_accepted
        case.status = RefundCaseStatus(model.status)
        case.created_at = model.created_at
        case.updated_at = model.updated_at
        return case
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_refund_case_repo.py -v
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/refund_case_repo.py \
        tests/integration/test_refund_case_repo.py
git commit -m "feat(refund): add RefundCaseRepository with save, update, get_by_id, list_by_contact"
```

---

## Task 7: RefundState (TypedDict)

**Files:**
- Create: `src/nexoia/application/capabilities/refund/__init__.py`
- Create: `src/nexoia/application/capabilities/refund/state.py`
- Test: `tests/unit/capabilities/refund/test_state.py`

- [ ] **Step 1: Criar packages**

```bash
mkdir -p src/nexoia/application/capabilities/refund
touch src/nexoia/application/capabilities/refund/__init__.py
mkdir -p tests/unit/capabilities/refund
touch tests/unit/capabilities/refund/__init__.py
```

- [ ] **Step 2: Escrever o teste falhando**

```python
# tests/unit/capabilities/refund/test_state.py
from nexoia.application.capabilities.refund.state import RefundState


def test_refund_state_required_keys_exist():
    state: RefundState = {
        "account_id": 1,
        "conversation_id": "conv-1",
        "contact_id": "c-1",
        "messages": [],
        "correlation_id": "corr-1",
        "refund_case_id": None,
        "student_email": None,
        "student_cpf": None,
        "refund_reason": None,
        "purchase": None,
        "is_recurring": False,
        "days_since_purchase": None,
        "within_deadline": None,
        "is_duplicate_purchase": False,
        "is_cmp_student": False,
        "offers_made": [],
        "offer_accepted": False,
        "explicit_refund_request": False,
        "refund_blocked_products": [],
        "refund_processed": False,
        "refund_processed_in_current_turn": False,
        "refund_step": "collect",
        "insistence_count_after_deny": 0,
    }
    assert state["refund_case_id"] is None
    assert state["offers_made"] == []
    assert state["refund_blocked_products"] == []
    assert state["insistence_count_after_deny"] == 0
```

- [ ] **Step 3: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_state.py -v
```
Esperado: `ImportError`

- [ ] **Step 4: Implementar o RefundState**

```python
# src/nexoia/application/capabilities/refund/state.py
from __future__ import annotations

from nexoia.application.state import ConversationState
from nexoia.infrastructure.hubla.schemas import HublaPurchase


class RefundState(ConversationState, total=False):
    """Estado do subgraph Refund.

    - `explicit_refund_request` (Guard 1): o aluno pediu reembolso explicitamente
      no turno atual? "ok" a oferta N2 NÃO conta.
    - `refund_blocked_products` (Guard 2): produtos que o aluno disse
      "não quero cancelar X".
    - `refund_processed_in_current_turn` (Guard 4): flag que reseta no próximo
      turno — usada para bloquear `finish_attendance` no mesmo turno.
    - `insistence_count_after_deny`: conta insistências após deny → 3ª = handoff.
    """

    refund_case_id: str | None
    student_email: str | None
    student_cpf: str | None
    refund_reason: str | None
    purchase: HublaPurchase | None
    is_recurring: bool
    days_since_purchase: int | None
    within_deadline: bool | None
    is_duplicate_purchase: bool
    is_cmp_student: bool  # TODO (CQ-R03) — ver OPEN_QUESTIONS.md
    offers_made: list[str]
    offer_accepted: bool
    explicit_refund_request: bool
    refund_blocked_products: list[str]
    refund_processed: bool
    refund_processed_in_current_turn: bool
    refund_step: str  # RefundStep value
    insistence_count_after_deny: int
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_state.py -v
```
Esperado: 1 teste PASSED

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/application/capabilities/refund/ \
        tests/unit/capabilities/refund/
git commit -m "feat(refund): add RefundState TypedDict with all capability fields"
```

---

## Task 8: Guard 1 — ExplicitRefundRequestGuard

**Files:**
- Create: `src/nexoia/application/capabilities/refund/guards/__init__.py`
- Create: `src/nexoia/application/capabilities/refund/guards/explicit_request.py`
- Test: `tests/unit/capabilities/refund/test_guards.py`

- [ ] **Step 1: Criar package marker**

```bash
touch src/nexoia/application/capabilities/refund/guards/__init__.py
```

- [ ] **Step 2: Escrever o teste falhando**

```python
# tests/unit/capabilities/refund/test_guards.py (parte 1 — Guard 1)
from unittest.mock import AsyncMock

import pytest

from nexoia.application.capabilities.refund.guards.explicit_request import (
    ExplicitRefundRequestGuard,
)


@pytest.mark.asyncio
async def test_explicit_guard_passes_when_llm_says_explicit():
    llm = AsyncMock(return_value=True)  # LLM diz que é pedido explícito
    guard = ExplicitRefundRequestGuard(llm_classifier=llm)

    allowed = await guard.is_allowed(last_user_message="quero meu dinheiro de volta")

    assert allowed is True
    llm.assert_awaited_once_with("quero meu dinheiro de volta")


@pytest.mark.asyncio
async def test_explicit_guard_blocks_when_message_is_just_ok():
    llm = AsyncMock(return_value=False)  # LLM diz que "ok" não é pedido
    guard = ExplicitRefundRequestGuard(llm_classifier=llm)

    allowed = await guard.is_allowed(last_user_message="ok")

    assert allowed is False


@pytest.mark.asyncio
async def test_explicit_guard_blocks_when_empty_message():
    llm = AsyncMock(return_value=False)
    guard = ExplicitRefundRequestGuard(llm_classifier=llm)

    allowed = await guard.is_allowed(last_user_message="")

    assert allowed is False
    llm.assert_not_awaited()  # short-circuit sem chamar LLM
```

- [ ] **Step 3: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py::test_explicit_guard_passes_when_llm_says_explicit -v
```
Esperado: `ImportError`

- [ ] **Step 4: Implementar o Guard 1**

```python
# src/nexoia/application/capabilities/refund/guards/explicit_request.py
"""Guard 1 — ExplicitRefundRequestGuard (PRD 7.3 Guards).

Bloqueia `process_refund` se o aluno NÃO pediu reembolso explicitamente
no turno atual. Ex: responder "ok" a uma oferta N2 não conta como pedido
explícito de reembolso — a sequência correta é aluno dizer "mesmo assim
quero reembolso" (ou equivalente).

Usa LLM para classificar a última mensagem do aluno.
"""
from __future__ import annotations

from typing import Awaitable, Callable


LlmClassifier = Callable[[str], Awaitable[bool]]


class ExplicitRefundRequestGuard:
    def __init__(self, llm_classifier: LlmClassifier) -> None:
        self._llm = llm_classifier

    async def is_allowed(self, last_user_message: str) -> bool:
        """Retorna True se a mensagem contém pedido EXPLÍCITO de reembolso."""
        if not last_user_message or not last_user_message.strip():
            return False
        return await self._llm(last_user_message)
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "explicit_guard"
```
Esperado: 3 testes PASSED

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/application/capabilities/refund/guards/__init__.py \
        src/nexoia/application/capabilities/refund/guards/explicit_request.py \
        tests/unit/capabilities/refund/test_guards.py
git commit -m "feat(refund): add Guard 1 ExplicitRefundRequestGuard with LLM classifier"
```

---

## Task 9: Guard 2 — ProductBlockedGuard

**Files:**
- Create: `src/nexoia/application/capabilities/refund/guards/product_blocked.py`
- Test: append to `tests/unit/capabilities/refund/test_guards.py`

- [ ] **Step 1: Escrever os testes falhando**

Adicionar a `tests/unit/capabilities/refund/test_guards.py`:

```python
# ---- Guard 2 — ProductBlockedGuard ----
from nexoia.application.capabilities.refund.guards.product_blocked import (
    ProductBlockedGuard,
)


def test_product_blocked_allows_when_list_empty():
    guard = ProductBlockedGuard()
    assert guard.is_allowed(product_id="p-1", blocked_products=[]) is True


def test_product_blocked_denies_when_product_in_list():
    guard = ProductBlockedGuard()
    assert (
        guard.is_allowed(product_id="p-1", blocked_products=["p-1", "p-2"]) is False
    )


def test_product_blocked_allows_when_different_product():
    guard = ProductBlockedGuard()
    assert guard.is_allowed(product_id="p-3", blocked_products=["p-1"]) is True


def test_product_blocked_add_product_persists_on_list():
    guard = ProductBlockedGuard()
    blocked: list[str] = []
    new_list = guard.block(product_id="p-1", blocked_products=blocked)
    assert "p-1" in new_list


def test_product_blocked_add_is_idempotent():
    guard = ProductBlockedGuard()
    new_list = guard.block(product_id="p-1", blocked_products=["p-1"])
    assert new_list.count("p-1") == 1
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "product_blocked"
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar Guard 2**

```python
# src/nexoia/application/capabilities/refund/guards/product_blocked.py
"""Guard 2 — ProductBlockedGuard (PRD 7.3 Guards).

Se o aluno disse "não quero cancelar X" em turno anterior, esse produto fica
bloqueado para reembolso no estado da conversa (`refund_blocked_products`).
`process_refund` é bloqueado se `target_product_id` está na lista.
"""
from __future__ import annotations


class ProductBlockedGuard:
    def is_allowed(self, product_id: str, blocked_products: list[str]) -> bool:
        return product_id not in blocked_products

    def block(self, product_id: str, blocked_products: list[str]) -> list[str]:
        """Retorna nova lista com `product_id` adicionado (idempotente)."""
        if product_id in blocked_products:
            return list(blocked_products)
        return list(blocked_products) + [product_id]
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "product_blocked"
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/guards/product_blocked.py \
        tests/unit/capabilities/refund/test_guards.py
git commit -m "feat(refund): add Guard 2 ProductBlockedGuard with is_allowed and block helpers"
```

---

## Task 10: Guard 3 — MandatoryRetentionGuard

**Files:**
- Create: `src/nexoia/application/capabilities/refund/guards/mandatory_retention.py`
- Test: append to `tests/unit/capabilities/refund/test_guards.py`

- [ ] **Step 1: Escrever os testes falhando**

Adicionar a `tests/unit/capabilities/refund/test_guards.py`:

```python
# ---- Guard 3 — MandatoryRetentionGuard ----
from nexoia.application.capabilities.refund.guards.mandatory_retention import (
    MandatoryRetentionGuard,
)


def test_mandatory_retention_blocks_when_n2_not_offered_yet():
    guard = MandatoryRetentionGuard()
    allowed = guard.is_allowed(
        offers_made=["N1"],
        is_duplicate_purchase=False,
        is_cmp_student=False,
    )
    assert allowed is False


def test_mandatory_retention_allows_when_n2_offered():
    guard = MandatoryRetentionGuard()
    allowed = guard.is_allowed(
        offers_made=["N1", "N2"],
        is_duplicate_purchase=False,
        is_cmp_student=False,
    )
    assert allowed is True


def test_mandatory_retention_allows_when_duplicate_purchase():
    """PRD 7.3 exceção: compra duplicada → pula retenção."""
    guard = MandatoryRetentionGuard()
    allowed = guard.is_allowed(
        offers_made=[],
        is_duplicate_purchase=True,
        is_cmp_student=False,
    )
    assert allowed is True


def test_mandatory_retention_allows_when_cmp_student():
    """PRD 7.3 exceção: aluno CMP insistente → argumentação especial sem N1/N2."""
    guard = MandatoryRetentionGuard()
    allowed = guard.is_allowed(
        offers_made=[],
        is_duplicate_purchase=False,
        is_cmp_student=True,
    )
    assert allowed is True


def test_mandatory_retention_blocks_when_no_offers_and_no_exceptions():
    guard = MandatoryRetentionGuard()
    allowed = guard.is_allowed(
        offers_made=[],
        is_duplicate_purchase=False,
        is_cmp_student=False,
    )
    assert allowed is False
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "mandatory_retention"
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar Guard 3**

```python
# src/nexoia/application/capabilities/refund/guards/mandatory_retention.py
"""Guard 3 — MandatoryRetentionGuard (PRD 7.3 Guards).

Bloqueia `process_refund` se o aluno não passou pela retenção completa
(N1 ofertado → recusado → N2 ofertado → recusado).

Exceções (retenção NÃO obrigatória):
- `is_duplicate_purchase=True`: compra duplicada → reembolsa direto.
- `is_cmp_student=True`: aluno CMP — argumentação especial aplicada em
  retention_loop substitui N1/N2 (TODO CQ-R03).
"""
from __future__ import annotations


class MandatoryRetentionGuard:
    def is_allowed(
        self,
        *,
        offers_made: list[str],
        is_duplicate_purchase: bool,
        is_cmp_student: bool,
    ) -> bool:
        if is_duplicate_purchase or is_cmp_student:
            return True
        # N1 + N2 precisam ter sido ofertados
        return "N1" in offers_made and "N2" in offers_made
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "mandatory_retention"
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/guards/mandatory_retention.py \
        tests/unit/capabilities/refund/test_guards.py
git commit -m "feat(refund): add Guard 3 MandatoryRetentionGuard with duplicate/CMP exceptions"
```

---

## Task 11: Guard 4 — SameTurnBlockGuard

**Files:**
- Create: `src/nexoia/application/capabilities/refund/guards/same_turn_block.py`
- Test: append to `tests/unit/capabilities/refund/test_guards.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# ---- Guard 4 — SameTurnBlockGuard ----
from nexoia.application.capabilities.refund.guards.same_turn_block import (
    SameTurnBlockGuard,
)


def test_same_turn_blocks_finish_when_refund_processed_in_current_turn():
    guard = SameTurnBlockGuard()
    can_finish = guard.can_finish_attendance(refund_processed_in_current_turn=True)
    assert can_finish is False


def test_same_turn_allows_finish_when_no_refund_in_current_turn():
    guard = SameTurnBlockGuard()
    can_finish = guard.can_finish_attendance(refund_processed_in_current_turn=False)
    assert can_finish is True


def test_same_turn_reset_returns_false_flag():
    """Chamar `reset_for_next_turn` zera o flag."""
    guard = SameTurnBlockGuard()
    assert guard.reset_for_next_turn() is False
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "same_turn"
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar Guard 4**

```python
# src/nexoia/application/capabilities/refund/guards/same_turn_block.py
"""Guard 4 — SameTurnBlockGuard (PRD 7.3 Guards).

Crítico (PRD 7.3): "Nunca chamar `finish_attendance` no mesmo turno que
`process_refund`."

Garante que o encerramento da conversa NÃO acontece no mesmo turno em que
o reembolso foi disparado. O flag `refund_processed_in_current_turn` é setado
pelo nó `process_refund` e resetado no início do próximo turno.
"""
from __future__ import annotations


class SameTurnBlockGuard:
    def can_finish_attendance(self, refund_processed_in_current_turn: bool) -> bool:
        return not refund_processed_in_current_turn

    def reset_for_next_turn(self) -> bool:
        """Chamado no início de cada turno — zera o flag."""
        return False
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "same_turn"
```
Esperado: 3 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/guards/same_turn_block.py \
        tests/unit/capabilities/refund/test_guards.py
git commit -m "feat(refund): add Guard 4 SameTurnBlockGuard preventing finish_attendance in same turn"
```

---

## Task 12: Guard 5 — RefundMutexGuard (Redis SETNX TTL 1h)

**Files:**
- Create: `src/nexoia/application/capabilities/refund/guards/refund_mutex.py`
- Test: append to `tests/unit/capabilities/refund/test_guards.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# ---- Guard 5 — RefundMutexGuard ----
from unittest.mock import AsyncMock

import pytest

from nexoia.application.capabilities.refund.guards.refund_mutex import (
    RefundMutexGuard,
)
from nexoia.domain.errors import RefundMutexError


@pytest.mark.asyncio
async def test_mutex_acquire_returns_true_when_key_free():
    redis = AsyncMock()
    redis.set.return_value = True  # SETNX succeeded
    guard = RefundMutexGuard(redis=redis, ttl_seconds=3600)

    acquired = await guard.try_acquire(
        account_id=1, contact_id="c-1", product_id="p-1"
    )

    assert acquired is True
    redis.set.assert_awaited_once()
    call_args = redis.set.call_args
    # Key format: refund:mutex:{account_id}:{contact_id}:{product_id}
    assert call_args.args[0] == "refund:mutex:1:c-1:p-1"
    # nx=True (SETNX) e ex=3600 (TTL 1h)
    assert call_args.kwargs.get("nx") is True
    assert call_args.kwargs.get("ex") == 3600


@pytest.mark.asyncio
async def test_mutex_acquire_returns_false_when_already_held():
    redis = AsyncMock()
    redis.set.return_value = False  # SETNX failed — key exists
    guard = RefundMutexGuard(redis=redis, ttl_seconds=3600)

    acquired = await guard.try_acquire(
        account_id=1, contact_id="c-1", product_id="p-1"
    )

    assert acquired is False


@pytest.mark.asyncio
async def test_mutex_release_deletes_key():
    redis = AsyncMock()
    guard = RefundMutexGuard(redis=redis, ttl_seconds=3600)

    await guard.release(account_id=1, contact_id="c-1", product_id="p-1")

    redis.delete.assert_awaited_once_with("refund:mutex:1:c-1:p-1")


@pytest.mark.asyncio
async def test_mutex_acquire_or_raise_raises_when_held():
    redis = AsyncMock()
    redis.set.return_value = False
    guard = RefundMutexGuard(redis=redis, ttl_seconds=3600)

    with pytest.raises(RefundMutexError):
        await guard.acquire_or_raise(
            account_id=1, contact_id="c-1", product_id="p-1"
        )


@pytest.mark.asyncio
async def test_mutex_key_format_is_deterministic():
    redis = AsyncMock()
    redis.set.return_value = True
    guard = RefundMutexGuard(redis=redis, ttl_seconds=3600)

    await guard.try_acquire(account_id=42, contact_id="contact-z", product_id="prod-X")

    key = redis.set.call_args.args[0]
    assert key == "refund:mutex:42:contact-z:prod-X"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "mutex"
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar Guard 5**

```python
# src/nexoia/application/capabilities/refund/guards/refund_mutex.py
"""Guard 5 — RefundMutexGuard (PRD 7.3 Guards).

Redis mutex por `(account_id, contact_id, product_id)` com TTL 1h.
Evita que dois jobs simultâneos processem o mesmo reembolso.

Key pattern: `refund:mutex:{account_id}:{contact_id}:{product_id}`
Semântica: `SET key value NX EX 3600`.
"""
from __future__ import annotations

from typing import Any

from nexoia.domain.errors import RefundMutexError


class RefundMutexGuard:
    def __init__(self, redis: Any, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    def _key(self, account_id: int, contact_id: str, product_id: str) -> str:
        return f"refund:mutex:{account_id}:{contact_id}:{product_id}"

    async def try_acquire(
        self, *, account_id: int, contact_id: str, product_id: str
    ) -> bool:
        key = self._key(account_id, contact_id, product_id)
        result = await self._redis.set(key, "1", nx=True, ex=self._ttl)
        return bool(result)

    async def acquire_or_raise(
        self, *, account_id: int, contact_id: str, product_id: str
    ) -> None:
        if not await self.try_acquire(
            account_id=account_id, contact_id=contact_id, product_id=product_id
        ):
            raise RefundMutexError(
                f"Refund already in progress for "
                f"account_id={account_id}, contact_id={contact_id}, "
                f"product_id={product_id}"
            )

    async def release(
        self, *, account_id: int, contact_id: str, product_id: str
    ) -> None:
        key = self._key(account_id, contact_id, product_id)
        await self._redis.delete(key)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_guards.py -v -k "mutex"
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/guards/refund_mutex.py \
        tests/unit/capabilities/refund/test_guards.py
git commit -m "feat(refund): add Guard 5 RefundMutexGuard with Redis SETNX TTL 1h"
```

---

## Task 13: Nó `collect` — coleta motivo antes do email

**Files:**
- Create: `src/nexoia/application/capabilities/refund/nodes.py`
- Test: `tests/unit/capabilities/refund/test_nodes.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/capabilities/refund/test_nodes.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexoia.application.capabilities.refund.nodes import node_collect
from nexoia.application.capabilities.refund.state import RefundState


def make_state(**kwargs) -> RefundState:
    base: dict = dict(
        account_id=1,
        conversation_id="conv-1",
        contact_id="c-1",
        messages=[],
        correlation_id="corr-1",
        refund_case_id=None,
        student_email=None,
        student_cpf=None,
        refund_reason=None,
        purchase=None,
        is_recurring=False,
        days_since_purchase=None,
        within_deadline=None,
        is_duplicate_purchase=False,
        is_cmp_student=False,
        offers_made=[],
        offer_accepted=False,
        explicit_refund_request=False,
        refund_blocked_products=[],
        refund_processed=False,
        refund_processed_in_current_turn=False,
        refund_step="collect",
        insistence_count_after_deny=0,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_collect_asks_reason_first_when_absent():
    """
    CRÍTICO PRD 7.3 Passo 1: "Sempre perguntar motivo antes de pedir email."
    """
    chatnexo = AsyncMock()
    extractor = AsyncMock(return_value={"reason": None, "email": None, "cpf": None})
    state = make_state(messages=[{"role": "user", "content": "quero reembolso"}])

    result = await node_collect(
        state,
        chatnexo_port=chatnexo,
        extractor=extractor,
        refund_case_repo=AsyncMock(),
    )

    # Deve enviar mensagem perguntando motivo, NÃO pedir email diretamente
    chatnexo.send_text.assert_awaited_once()
    text_sent = chatnexo.send_text.call_args.kwargs.get("text") \
                 or chatnexo.send_text.call_args.args[-1]
    assert "aconteceu" in text_sent.lower() or "motivo" in text_sent.lower()
    assert "email" not in text_sent.lower() and "e-mail" not in text_sent.lower()


@pytest.mark.asyncio
async def test_collect_asks_email_and_cpf_together_after_reason():
    """
    Se motivo JÁ veio, envia empatia curta e pede email + CPF JUNTOS.
    """
    chatnexo = AsyncMock()
    extractor = AsyncMock(return_value={
        "reason": "não tive tempo",
        "email": None,
        "cpf": None,
    })
    state = make_state(messages=[
        {"role": "user", "content": "quero reembolso, não tive tempo"}
    ])

    result = await node_collect(
        state,
        chatnexo_port=chatnexo,
        extractor=extractor,
        refund_case_repo=AsyncMock(),
    )

    chatnexo.send_text.assert_awaited_once()
    text_sent = chatnexo.send_text.call_args.kwargs.get("text") \
                 or chatnexo.send_text.call_args.args[-1]
    # Mensagem pede email E CPF na mesma mensagem
    assert ("email" in text_sent.lower() or "e-mail" in text_sent.lower())
    assert "cpf" in text_sent.lower()
    assert result["refund_reason"] == "não tive tempo"


@pytest.mark.asyncio
async def test_collect_creates_refund_case_when_email_and_cpf_arrive():
    """
    Com email + CPF + motivo, cria RefundCase e avança para check_deadline.
    """
    chatnexo = AsyncMock()
    extractor = AsyncMock(return_value={
        "reason": "não tive tempo",
        "email": "aluno@email.com",
        "cpf": "12345678900",
    })
    repo = AsyncMock()
    state = make_state(
        refund_reason="não tive tempo",
        messages=[
            {"role": "user", "content": "não tive tempo"},
            {"role": "assistant", "content": "entendi, me passa email + cpf"},
            {"role": "user", "content": "aluno@email.com 123.456.789-00"},
        ],
    )

    result = await node_collect(
        state,
        chatnexo_port=chatnexo,
        extractor=extractor,
        refund_case_repo=repo,
    )

    # Criou RefundCase
    repo.save.assert_awaited_once()
    saved = repo.save.call_args.args[0]
    assert saved.student_email == "aluno@email.com"
    assert saved.student_cpf == "12345678900"

    # Avança para check_deadline
    assert result["refund_step"] == "check_deadline"
    assert result["refund_case_id"] == saved.id
    assert result["student_email"] == "aluno@email.com"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "collect"
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar `node_collect`**

```python
# src/nexoia/application/capabilities/refund/nodes.py
"""Nós do subgraph Refund & Retention.

REGRAS CRÍTICAS (PRD 7.3):
- Sempre perguntar motivo antes de pedir email.
- Nunca dizer "fizemos" ou "processado" — é assíncrono. Usar apenas mensagem padrão.
- Nunca chamar `finish_attendance` no mesmo turno que `process_refund`.
- Nunca falar sobre prazo sem ter buscado a compra na Hubla antes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import structlog

from nexoia.application.capabilities.refund.state import RefundState
from nexoia.domain.entities.refund_case import (
    RefundCase,
    RefundCaseStatus,
    RefundStep,
)
from nexoia.domain.ports.chatnexo_port import ChatNexoPort

logger = structlog.get_logger(__name__)


# Mensagens padronizadas
MSG_ASK_REASON = "Poxa, me conta o que aconteceu?"
MSG_ASK_EMAIL_CPF_AFTER_REASON = (
    "Entendi. Pra eu te ajudar com isso, me passa seu e-mail de cadastro "
    "e o CPF (na mesma mensagem), tá?"
)


Extractor = Callable[[list[dict[str, Any]]], Awaitable[dict[str, Any]]]


async def node_collect(
    state: RefundState,
    *,
    chatnexo_port: ChatNexoPort,
    extractor: Extractor,
    refund_case_repo: Any,
) -> dict[str, Any]:
    """
    Coleta motivo + email + CPF.

    PRD 7.3 Passo 1 (CRÍTICO):
    - Sempre perguntar o motivo antes de pedir e-mail.
    - Se motivo já veio: 1 frase de empatia + pedir email + CPF juntos.
    - Buscar compra na Hubla assim que tiver o e-mail (próximo nó).
    """
    log = logger.bind(
        node="collect",
        capability="refund",
        account_id=state["account_id"],
        refund_case_id=state.get("refund_case_id"),
    )

    extracted = await extractor(state.get("messages", []))
    reason = extracted.get("reason") or state.get("refund_reason")
    email = extracted.get("email") or state.get("student_email")
    cpf = extracted.get("cpf") or state.get("student_cpf")

    # 1) Motivo ausente → pergunta motivo primeiro
    if not reason:
        log.info("asking_reason_first", has_email=bool(email))
        await chatnexo_port.send_text(
            account_id=state["account_id"],
            conversation_id=state["conversation_id"],
            text=MSG_ASK_REASON,
        )
        return {
            "refund_step": RefundStep.COLLECT.value,
            "refund_reason": None,
        }

    # 2) Motivo presente, mas falta email ou CPF → pede os dois juntos
    if not email or not cpf:
        log.info("asking_email_cpf", has_email=bool(email), has_cpf=bool(cpf))
        await chatnexo_port.send_text(
            account_id=state["account_id"],
            conversation_id=state["conversation_id"],
            text=MSG_ASK_EMAIL_CPF_AFTER_REASON,
        )
        return {
            "refund_step": RefundStep.COLLECT.value,
            "refund_reason": reason,
            "student_email": email,
            "student_cpf": cpf,
        }

    # 3) Temos tudo → cria RefundCase e avança para check_deadline
    case = RefundCase(
        account_id=state["account_id"],
        contact_id=state["contact_id"],
        conversation_id=state["conversation_id"],
        student_email=email,
        student_cpf=cpf,
        refund_reason=reason,
        status=RefundCaseStatus.CHECKING_DEADLINE,
    )
    await refund_case_repo.save(case)
    log.info("refund_case_created", refund_case_id=case.id)

    return {
        "refund_step": RefundStep.DEADLINE.value,
        "refund_case_id": case.id,
        "refund_reason": reason,
        "student_email": email,
        "student_cpf": cpf,
    }
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "collect"
```
Esperado: 3 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/nodes.py \
        tests/unit/capabilities/refund/test_nodes.py
git commit -m "feat(refund): add node_collect asking reason before email (PRD 7.3 critical rule)"
```

---

## Task 14: Nó `check_deadline` — busca Hubla + recorrência + Art. 49

**Files:**
- Modify: `src/nexoia/application/capabilities/refund/nodes.py`
- Test: append to `tests/unit/capabilities/refund/test_nodes.py`

- [ ] **Step 1: Escrever os testes falhando**

Adicionar a `tests/unit/capabilities/refund/test_nodes.py`:

```python
# ---- node_check_deadline ----
from datetime import datetime, timedelta, timezone

from nexoia.application.capabilities.refund.nodes import node_check_deadline
from tests.fakes.fake_hubla_client import FakeHublaClient


@pytest.mark.asyncio
async def test_check_deadline_within_cdc_window():
    """Compra feita 3 dias atrás → dentro do prazo (7 dias CDC)."""
    purchase = FakeHublaClient.make_purchase(days_ago=3)
    hubla = FakeHublaClient(purchase=purchase)
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=MagicMock(id="rc-1"))

    state = make_state(
        refund_case_id="rc-1",
        student_email="aluno@email.com",
        refund_reason="não quero",
    )

    result = await node_check_deadline(
        state,
        hubla_port=hubla,
        refund_case_repo=repo,
        art49_checker=AsyncMock(return_value=False),
        deadline_days=7,
    )

    assert result["within_deadline"] is True
    assert result["days_since_purchase"] == 3
    assert result["is_recurring"] is False
    assert result["purchase"] is not None
    assert result["refund_step"] == "retention"


@pytest.mark.asyncio
async def test_check_deadline_outside_cdc_window_goes_to_deny():
    """Compra feita há 10 dias → fora do prazo."""
    purchase = FakeHublaClient.make_purchase(days_ago=10)
    hubla = FakeHublaClient(purchase=purchase)
    state = make_state(
        refund_case_id="rc-1",
        student_email="aluno@email.com",
    )

    result = await node_check_deadline(
        state,
        hubla_port=hubla,
        refund_case_repo=AsyncMock(),
        art49_checker=AsyncMock(return_value=False),
        deadline_days=7,
    )

    assert result["within_deadline"] is False
    assert result["days_since_purchase"] == 10
    assert result["refund_step"] == "deny"


@pytest.mark.asyncio
async def test_check_deadline_recurring_counts_from_first_charge():
    """PRD 7.3 Passo 2: recorrente → prazo conta da PRIMEIRA parcela."""
    now = datetime.now(timezone.utc)
    first_charge = now - timedelta(days=30)  # 30 dias atrás (fora do prazo)
    latest_charge = now - timedelta(days=2)  # 2 dias atrás (mas não conta)

    from nexoia.infrastructure.hubla.schemas import HublaPurchase
    purchase = HublaPurchase(
        id="p-rec",
        product_name="Assinatura",
        created_at=latest_charge,
        amount=97.0,
        is_duplicate=False,
        is_recurring=True,
        first_charge_at=first_charge,
    )
    hubla = FakeHublaClient(purchase=purchase)

    state = make_state(
        refund_case_id="rc-1",
        student_email="aluno@email.com",
    )

    result = await node_check_deadline(
        state,
        hubla_port=hubla,
        refund_case_repo=AsyncMock(),
        art49_checker=AsyncMock(return_value=False),
        deadline_days=7,
    )

    # Prazo conta de first_charge_at (30 dias atrás) → FORA do prazo
    assert result["within_deadline"] is False
    assert result["days_since_purchase"] == 30
    assert result["is_recurring"] is True


@pytest.mark.asyncio
async def test_check_deadline_art49_forces_within_deadline():
    """
    Art. 49 CDC: se aluno pediu em canal anterior dentro do prazo,
    within_deadline=True mesmo com data expirada.
    """
    purchase = FakeHublaClient.make_purchase(days_ago=15)  # fora do prazo
    hubla = FakeHublaClient(purchase=purchase)

    state = make_state(
        refund_case_id="rc-1",
        student_email="aluno@email.com",
    )

    result = await node_check_deadline(
        state,
        hubla_port=hubla,
        refund_case_repo=AsyncMock(),
        art49_checker=AsyncMock(return_value=True),  # pediu antes dentro do prazo
        deadline_days=7,
    )

    assert result["within_deadline"] is True
    assert result["refund_step"] == "retention"


@pytest.mark.asyncio
async def test_check_deadline_duplicate_purchase_flag():
    """Compra duplicada → flag is_duplicate_purchase=True (pula retenção)."""
    purchase = FakeHublaClient.make_purchase(days_ago=2, is_duplicate=True)
    hubla = FakeHublaClient(purchase=purchase)

    state = make_state(
        refund_case_id="rc-1",
        student_email="aluno@email.com",
    )

    result = await node_check_deadline(
        state,
        hubla_port=hubla,
        refund_case_repo=AsyncMock(),
        art49_checker=AsyncMock(return_value=False),
        deadline_days=7,
    )

    assert result["is_duplicate_purchase"] is True
    assert result["within_deadline"] is True
    # Roteamento no graph decidirá pular retenção → process_refund


@pytest.mark.asyncio
async def test_check_deadline_purchase_not_found_escalates():
    """Hubla retorna None → escala (RF-R09 análogo)."""
    hubla = FakeHublaClient(purchase=None)

    state = make_state(
        refund_case_id="rc-1",
        student_email="aluno@email.com",
    )

    result = await node_check_deadline(
        state,
        hubla_port=hubla,
        refund_case_repo=AsyncMock(),
        art49_checker=AsyncMock(return_value=False),
        deadline_days=7,
    )

    # Sem compra, não dá pra falar de prazo — escalar silenciosamente
    assert result["refund_step"] == "deny"
    assert result["purchase"] is None
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "check_deadline"
```
Esperado: `ImportError` / `AttributeError`

- [ ] **Step 3: Adicionar `node_check_deadline` a `nodes.py`**

```python
# (append em src/nexoia/application/capabilities/refund/nodes.py)
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from nexoia.domain.ports.hubla_port import HublaPort


Art49Checker = Callable[[dict[str, Any]], Awaitable[bool]]


async def node_check_deadline(
    state: RefundState,
    *,
    hubla_port: HublaPort,
    refund_case_repo: Any,
    art49_checker: Art49Checker,
    deadline_days: int,
) -> dict[str, Any]:
    """
    Busca compra na Hubla e verifica prazo CDC.

    CRÍTICO PRD 7.3 Passo 2: "Nunca falar sobre prazo sem ter buscado a compra
    na Hubla antes."

    Lógica:
      - `is_recurring=True`: prazo conta de `first_charge_at` (PRD 7.3 Passo 2).
      - Compra única: prazo conta de `created_at`.
      - Art. 49 CDC: se aluno pediu em canal anterior dentro do prazo → força
        within_deadline=True.
      - Compras separadas: cada purchase_id tem prazo independente (por ora,
        usa a compra retornada; multi-produto resolvido em roadmap futuro).
      - Compra não encontrada → refund_step=deny (escalar via handler upstream).
    """
    log = logger.bind(
        node="check_deadline",
        capability="refund",
        account_id=state["account_id"],
        refund_case_id=state.get("refund_case_id"),
    )

    purchase = await hubla_port.get_purchase_by_email(
        email=state["student_email"] or "",
        account_id=state["account_id"],
    )

    if purchase is None:
        log.warning("purchase_not_found_in_hubla", email=state.get("student_email"))
        return {
            "refund_step": RefundStep.DENY.value,
            "purchase": None,
            "within_deadline": None,
        }

    # Calcula dias desde a compra
    now = datetime.now(timezone.utc)
    reference_date = (
        purchase.first_charge_at
        if purchase.is_recurring and purchase.first_charge_at is not None
        else purchase.created_at
    )
    days = (now - reference_date).days

    # Art. 49 CDC: verifica canal anterior
    art49_applies = await art49_checker({
        "account_id": state["account_id"],
        "contact_id": state["contact_id"],
        "email": state["student_email"],
        "deadline_days": deadline_days,
    })

    within_deadline = days <= deadline_days or art49_applies

    log.info(
        "deadline_checked",
        days_since_purchase=days,
        is_recurring=purchase.is_recurring,
        within_deadline=within_deadline,
        art49_applies=art49_applies,
        is_duplicate=purchase.is_duplicate,
    )

    # Persiste campos calculados no RefundCase
    if state.get("refund_case_id"):
        case = await refund_case_repo.get_by_id(state["refund_case_id"])
        if case is not None:
            case.purchase_id = purchase.id
            case.product_name = purchase.product_name
            case.days_since_purchase = days
            case.within_deadline = within_deadline
            case.status = (
                RefundCaseStatus.IN_RETENTION
                if within_deadline
                else RefundCaseStatus.DENIED
            )
            await refund_case_repo.update(case)

    next_step = RefundStep.RETENTION if within_deadline else RefundStep.DENY

    return {
        "purchase": purchase,
        "is_recurring": purchase.is_recurring,
        "days_since_purchase": days,
        "within_deadline": within_deadline,
        "is_duplicate_purchase": purchase.is_duplicate,
        "refund_step": next_step.value,
    }
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "check_deadline"
```
Esperado: 6 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/nodes.py \
        tests/unit/capabilities/refund/test_nodes.py
git commit -m "feat(refund): add node_check_deadline with recurring, Art.49 CDC and duplicate logic"
```

---

## Task 15: Nó `retention_loop` — N1 → N2, exceções duplicate/CMP

**Files:**
- Modify: `src/nexoia/application/capabilities/refund/nodes.py`
- Test: append to `tests/unit/capabilities/refund/test_nodes.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# ---- node_retention_loop ----
from nexoia.application.capabilities.refund.nodes import node_retention_loop


@pytest.mark.asyncio
async def test_retention_duplicate_skips_to_process_refund():
    """is_duplicate_purchase=True → vai direto para process_refund (sem ofertas)."""
    chatnexo = AsyncMock()
    state = make_state(is_duplicate_purchase=True, within_deadline=True)

    result = await node_retention_loop(
        state,
        chatnexo_port=chatnexo,
        offer_classifier=AsyncMock(),
    )

    assert result["refund_step"] == "process_refund"
    assert result["offers_made"] == []
    chatnexo.send_text.assert_not_awaited()


@pytest.mark.asyncio
async def test_retention_cmp_student_applies_special_argument():
    """
    TODO CQ-R03: aluno CMP → argumentação especial (stub por ora).
    Por ora, apenas skip para process_refund após marcar.
    """
    state = make_state(is_cmp_student=True, within_deadline=True)

    result = await node_retention_loop(
        state,
        chatnexo_port=AsyncMock(),
        offer_classifier=AsyncMock(),
    )
    # Comportamento stub: marca offers_made=[] e vai para process_refund.
    # TODO CQ-R03: substituir por argumentação especial real.
    assert result["refund_step"] == "process_refund"


@pytest.mark.asyncio
async def test_retention_offers_n1_when_no_offers_made():
    """Primeira iteração: N1 não ofertado ainda → envia N1 e aguarda resposta."""
    chatnexo = AsyncMock()
    state = make_state(
        offers_made=[],
        within_deadline=True,
        is_duplicate_purchase=False,
        is_cmp_student=False,
    )

    result = await node_retention_loop(
        state,
        chatnexo_port=chatnexo,
        offer_classifier=AsyncMock(),
    )

    chatnexo.send_text.assert_awaited_once()
    text_sent = chatnexo.send_text.call_args.kwargs.get("text") \
                 or chatnexo.send_text.call_args.args[-1]
    assert "acesso vitalício" in text_sent.lower() or "vitalício" in text_sent.lower()
    assert result["offers_made"] == ["N1"]
    assert result["refund_step"] == "retention"  # aguarda resposta


@pytest.mark.asyncio
async def test_retention_n1_accepted_goes_to_deliver_offer():
    """Aluno aceitou N1 → deliver_offer, sem processar reembolso."""
    chatnexo = AsyncMock()
    classifier = AsyncMock(return_value="accept")
    state = make_state(
        offers_made=["N1"],
        within_deadline=True,
        messages=[
            {"role": "assistant", "content": "oferta N1..."},
            {"role": "user", "content": "aceito!"},
        ],
    )

    result = await node_retention_loop(
        state,
        chatnexo_port=chatnexo,
        offer_classifier=classifier,
    )

    assert result["offer_accepted"] is True
    assert result["refund_step"] == "deliver_offer"


@pytest.mark.asyncio
async def test_retention_n1_refused_sends_n2():
    """N1 recusado e N2 não ofertado → oferece N2."""
    chatnexo = AsyncMock()
    classifier = AsyncMock(return_value="refuse")
    state = make_state(
        offers_made=["N1"],
        within_deadline=True,
        messages=[
            {"role": "assistant", "content": "oferta N1"},
            {"role": "user", "content": "não quero"},
        ],
    )

    result = await node_retention_loop(
        state,
        chatnexo_port=chatnexo,
        offer_classifier=classifier,
    )

    chatnexo.send_text.assert_awaited_once()
    text_sent = chatnexo.send_text.call_args.kwargs.get("text") \
                 or chatnexo.send_text.call_args.args[-1]
    assert "mentoria" in text_sent.lower() or "tráfego" in text_sent.lower()
    assert result["offers_made"] == ["N1", "N2"]
    assert result["refund_step"] == "retention"


@pytest.mark.asyncio
async def test_retention_n2_refused_goes_to_process_refund():
    """N2 recusado → process_refund (recusa dupla)."""
    classifier = AsyncMock(return_value="refuse")
    state = make_state(
        offers_made=["N1", "N2"],
        within_deadline=True,
        messages=[
            {"role": "assistant", "content": "oferta N2"},
            {"role": "user", "content": "não quero, quero reembolso"},
        ],
    )

    result = await node_retention_loop(
        state,
        chatnexo_port=AsyncMock(),
        offer_classifier=classifier,
    )

    assert result["refund_step"] == "process_refund"
    assert result["offer_accepted"] is False


@pytest.mark.asyncio
async def test_retention_never_repeats_same_offer():
    """PRD 7.3: Nunca repetir a mesma oferta. Já fez N1 e N2 → só pode ir para process."""
    classifier = AsyncMock(return_value="refuse")
    state = make_state(
        offers_made=["N1", "N2"],
        within_deadline=True,
    )

    result = await node_retention_loop(
        state,
        chatnexo_port=AsyncMock(),
        offer_classifier=classifier,
    )

    # offers_made não cresce — já tem N2 → process
    assert result["offers_made"] == ["N1", "N2"]
    assert result["refund_step"] == "process_refund"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "retention"
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar `node_retention_loop`**

```python
# (append em src/nexoia/application/capabilities/refund/nodes.py)
# Textos das ofertas (PRD 7.3 + resposta CQ-R02 em OPEN_QUESTIONS.md)
MSG_OFFER_N1 = (
    "Antes de seguir com o reembolso, posso te fazer uma oferta: "
    "transformar seu acesso em VITALÍCIO, sem custo. Você mantém tudo que "
    "comprou pra sempre. O que acha?"
)
MSG_OFFER_N2 = (
    "Entendo. Tenho uma outra proposta: liberar GRÁTIS a Mentoria de Tráfego "
    "(curso pago) junto com seu acesso. Topa?"
)


OfferClassifier = Callable[[list[dict[str, Any]]], Awaitable[str]]
# Retorna: "accept" | "refuse"


async def node_retention_loop(
    state: RefundState,
    *,
    chatnexo_port: ChatNexoPort,
    offer_classifier: OfferClassifier,
) -> dict[str, Any]:
    """
    Oferece retenção N1 → N2 (máx 2; nunca repetir).

    PRD 7.3 Passo 3:
    - N1 obrigatório antes de qualquer reembolso (salvo exceções).
    - Se N1 recusado, N2 obrigatório. Proibido ir direto ao reembolso após N1.
    - Exceção compra duplicada: reembolsa sem retenção.
    - Exceção aluno CMP: argumentação especial (TODO CQ-R03 — por ora stub).
    - Máx 2 ofertas; nunca repete a mesma.
    """
    log = logger.bind(
        node="retention_loop",
        capability="refund",
        account_id=state["account_id"],
        refund_case_id=state.get("refund_case_id"),
    )

    # Exceção 1: compra duplicada → skip para process_refund
    if state.get("is_duplicate_purchase"):
        log.info("skip_retention_duplicate_purchase")
        return {"refund_step": RefundStep.PROCESS.value}

    # Exceção 2: aluno CMP → argumentação especial (TODO CQ-R03)
    # Por ora, stub: segue para process_refund.
    # Ver OPEN_QUESTIONS.md#CQ-R03 para regra definitiva.
    if state.get("is_cmp_student"):
        log.warning(
            "cmp_student_stub_skipping_retention",
            todo="CQ-R03",
            note="special_argument_pending_definition",
        )
        return {"refund_step": RefundStep.PROCESS.value}

    offers_made = list(state.get("offers_made") or [])

    # Se já ofertou N1 e N2, classifica última resposta e decide
    if "N1" in offers_made and "N2" in offers_made:
        decision = await offer_classifier(state.get("messages", []))
        if decision == "accept":
            log.info("offer_accepted_n2")
            return {
                "offer_accepted": True,
                "offers_made": offers_made,
                "refund_step": RefundStep.DONE.value
                # Nó `deliver_offer` é invocado via roteamento do graph
                if False else "deliver_offer",
            }
        log.info("offer_refused_n2_going_to_process_refund")
        return {
            "offers_made": offers_made,
            "offer_accepted": False,
            "refund_step": RefundStep.PROCESS.value,
        }

    # Se já ofertou N1 (e não N2), classifica última resposta
    if "N1" in offers_made and "N2" not in offers_made:
        decision = await offer_classifier(state.get("messages", []))
        if decision == "accept":
            log.info("offer_accepted_n1")
            return {
                "offer_accepted": True,
                "offers_made": offers_made,
                "refund_step": "deliver_offer",
            }
        # Recusou N1 → oferece N2
        await chatnexo_port.send_text(
            account_id=state["account_id"],
            conversation_id=state["conversation_id"],
            text=MSG_OFFER_N2,
        )
        offers_made.append("N2")
        log.info("offer_sent", offer="N2")
        return {
            "offers_made": offers_made,
            "refund_step": RefundStep.RETENTION.value,
        }

    # Nenhuma oferta ainda → envia N1
    await chatnexo_port.send_text(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        text=MSG_OFFER_N1,
    )
    offers_made.append("N1")
    log.info("offer_sent", offer="N1")
    return {
        "offers_made": offers_made,
        "refund_step": RefundStep.RETENTION.value,
    }
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "retention"
```
Esperado: 7 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/nodes.py \
        tests/unit/capabilities/refund/test_nodes.py
git commit -m "feat(refund): add node_retention_loop with N1/N2 offers, duplicate/CMP exceptions"
```

---

## Task 16: Nó `process_refund` — mutex + mensagem padrão (nunca "processado")

**Files:**
- Modify: `src/nexoia/application/capabilities/refund/nodes.py`
- Test: append to `tests/unit/capabilities/refund/test_nodes.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# ---- node_process_refund ----
from nexoia.application.capabilities.refund.nodes import (
    MSG_REFUND_PROCESSING,
    node_process_refund,
)
from nexoia.domain.errors import RefundMutexError


@pytest.mark.asyncio
async def test_process_refund_sends_standard_message_never_past_tense():
    """
    CRÍTICO PRD 7.3 Passo 4: "Nunca dizer 'fizemos' ou 'processado'."
    Mensagem padrão usa apenas "tô processando agora" (gerúndio).
    """
    # Garante que a constante está correta
    assert "processando" in MSG_REFUND_PROCESSING.lower()
    assert "fizemos" not in MSG_REFUND_PROCESSING.lower()
    assert "processado" not in MSG_REFUND_PROCESSING.lower()
    assert "72 horas" in MSG_REFUND_PROCESSING
    assert "fatura" in MSG_REFUND_PROCESSING.lower()


@pytest.mark.asyncio
async def test_process_refund_acquires_mutex_and_calls_hubla():
    hubla = FakeHublaClient(purchase=FakeHublaClient.make_purchase())
    mutex = AsyncMock()
    mutex.acquire_or_raise = AsyncMock()
    mutex.release = AsyncMock()
    chatnexo = AsyncMock()
    explicit_guard = AsyncMock()
    explicit_guard.is_allowed = AsyncMock(return_value=True)
    mandatory_guard = MagicMock()
    mandatory_guard.is_allowed = MagicMock(return_value=True)
    product_guard = MagicMock()
    product_guard.is_allowed = MagicMock(return_value=True)

    from nexoia.infrastructure.hubla.schemas import HublaPurchase
    purchase = FakeHublaClient.make_purchase(purchase_id="p-xyz")

    state = make_state(
        refund_case_id="rc-1",
        student_email="a@a.com",
        purchase=purchase,
        offers_made=["N1", "N2"],
        explicit_refund_request=True,
        messages=[{"role": "user", "content": "quero reembolso"}],
    )

    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=MagicMock(id="rc-1"))

    result = await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=mutex,
        explicit_guard=explicit_guard,
        mandatory_guard=mandatory_guard,
        product_guard=product_guard,
        chatnexo_port=chatnexo,
        refund_case_repo=repo,
    )

    mutex.acquire_or_raise.assert_awaited_once()
    assert hubla.refund_calls == 1
    # Mensagem padrão enviada
    chatnexo.send_text.assert_awaited_once()
    text_sent = chatnexo.send_text.call_args.kwargs.get("text") \
                 or chatnexo.send_text.call_args.args[-1]
    assert text_sent == MSG_REFUND_PROCESSING
    # Flags atualizados
    assert result["refund_processed"] is True
    assert result["refund_processed_in_current_turn"] is True
    assert result["refund_step"] == "done"


@pytest.mark.asyncio
async def test_process_refund_blocked_by_explicit_guard():
    """Aluno não pediu explicitamente → guard bloqueia."""
    hubla = FakeHublaClient()
    mutex = AsyncMock()
    explicit_guard = AsyncMock()
    explicit_guard.is_allowed = AsyncMock(return_value=False)
    mandatory_guard = MagicMock()
    mandatory_guard.is_allowed = MagicMock(return_value=True)
    product_guard = MagicMock()
    product_guard.is_allowed = MagicMock(return_value=True)

    state = make_state(
        refund_case_id="rc-1",
        offers_made=["N1", "N2"],
        purchase=FakeHublaClient.make_purchase(),
        messages=[{"role": "user", "content": "ok"}],
    )

    result = await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=mutex,
        explicit_guard=explicit_guard,
        mandatory_guard=mandatory_guard,
        product_guard=product_guard,
        chatnexo_port=AsyncMock(),
        refund_case_repo=AsyncMock(),
    )

    # Não chamou Hubla nem mutex
    assert hubla.refund_calls == 0
    # Fluxo volta para retention (Guard pede para ofertar algo mais)
    assert result["refund_step"] == "retention"
    assert result.get("refund_processed") is not True


@pytest.mark.asyncio
async def test_process_refund_blocked_by_mandatory_retention_guard():
    """N2 não oferecido ainda → guard bloqueia."""
    hubla = FakeHublaClient()
    mandatory_guard = MagicMock()
    mandatory_guard.is_allowed = MagicMock(return_value=False)
    explicit_guard = AsyncMock()
    explicit_guard.is_allowed = AsyncMock(return_value=True)
    product_guard = MagicMock()
    product_guard.is_allowed = MagicMock(return_value=True)

    state = make_state(
        offers_made=["N1"],
        purchase=FakeHublaClient.make_purchase(),
        explicit_refund_request=True,
    )

    result = await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=AsyncMock(),
        explicit_guard=explicit_guard,
        mandatory_guard=mandatory_guard,
        product_guard=product_guard,
        chatnexo_port=AsyncMock(),
        refund_case_repo=AsyncMock(),
    )

    assert hubla.refund_calls == 0
    assert result["refund_step"] == "retention"


@pytest.mark.asyncio
async def test_process_refund_blocked_by_product_guard():
    """Produto na lista refund_blocked_products → bloqueia."""
    hubla = FakeHublaClient()
    product_guard = MagicMock()
    product_guard.is_allowed = MagicMock(return_value=False)
    mandatory_guard = MagicMock()
    mandatory_guard.is_allowed = MagicMock(return_value=True)
    explicit_guard = AsyncMock()
    explicit_guard.is_allowed = AsyncMock(return_value=True)

    state = make_state(
        offers_made=["N1", "N2"],
        purchase=FakeHublaClient.make_purchase(purchase_id="p-blocked"),
        explicit_refund_request=True,
        refund_blocked_products=["p-blocked"],
    )

    result = await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=AsyncMock(),
        explicit_guard=explicit_guard,
        mandatory_guard=mandatory_guard,
        product_guard=product_guard,
        chatnexo_port=AsyncMock(),
        refund_case_repo=AsyncMock(),
    )

    assert hubla.refund_calls == 0
    assert result["refund_step"] == "done"  # encerra (produto bloqueado)


@pytest.mark.asyncio
async def test_process_refund_mutex_held_raises():
    """Mutex já adquirido → não chama Hubla duas vezes."""
    hubla = FakeHublaClient()
    mutex = AsyncMock()
    mutex.acquire_or_raise = AsyncMock(side_effect=RefundMutexError("held"))
    explicit_guard = AsyncMock()
    explicit_guard.is_allowed = AsyncMock(return_value=True)
    mandatory_guard = MagicMock()
    mandatory_guard.is_allowed = MagicMock(return_value=True)
    product_guard = MagicMock()
    product_guard.is_allowed = MagicMock(return_value=True)

    state = make_state(
        offers_made=["N1", "N2"],
        purchase=FakeHublaClient.make_purchase(purchase_id="p-1"),
        explicit_refund_request=True,
    )

    result = await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=mutex,
        explicit_guard=explicit_guard,
        mandatory_guard=mandatory_guard,
        product_guard=product_guard,
        chatnexo_port=AsyncMock(),
        refund_case_repo=AsyncMock(),
    )

    assert hubla.refund_calls == 0
    assert result["refund_step"] == "done"
    # Não seta refund_processed_in_current_turn se Hubla não foi chamada
    assert result.get("refund_processed") is not True
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "process_refund"
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar `node_process_refund`**

```python
# (append em src/nexoia/application/capabilities/refund/nodes.py)
from nexoia.domain.errors import RefundMutexError


# CRÍTICO PRD 7.3 Passo 4: "Nunca dizer 'fizemos' ou 'processado' — é assíncrono.
# Usar APENAS esta mensagem padrão."
MSG_REFUND_PROCESSING = (
    "Tô processando seu reembolso agora! O prazo de estorno de pix é até "
    "72 horas e cartão de 1 a 2 faturas, ambos dependem da sua operadora. "
    "Você vai receber a confirmação assim que o processamento terminar, tá?"
)


async def node_process_refund(
    state: RefundState,
    *,
    hubla_port: HublaPort,
    mutex_guard: Any,  # RefundMutexGuard
    explicit_guard: Any,  # ExplicitRefundRequestGuard
    mandatory_guard: Any,  # MandatoryRetentionGuard
    product_guard: Any,  # ProductBlockedGuard
    chatnexo_port: ChatNexoPort,
    refund_case_repo: Any,
) -> dict[str, Any]:
    """
    Processa o reembolso.

    Ordem de checagem (fail-fast):
      1. Guard 1 (ExplicitRefundRequest) — aluno pediu explicitamente no turno?
      2. Guard 2 (ProductBlocked) — produto não está na lista?
      3. Guard 3 (MandatoryRetention) — N2 ofertado após N1 recusado?
      4. Guard 5 (RefundMutex) — adquire mutex Redis.
      5. Hubla.process_refund() — via Playwright (stub).
      6. Envia mensagem padrão (nunca "fizemos"/"processado").
      7. Seta refund_processed_in_current_turn=True (Guard 4 bloqueia finish).
    """
    log = logger.bind(
        node="process_refund",
        capability="refund",
        account_id=state["account_id"],
        refund_case_id=state.get("refund_case_id"),
    )

    purchase = state.get("purchase")
    if purchase is None:
        log.warning("process_refund_without_purchase", skipping=True)
        return {"refund_step": RefundStep.DONE.value}

    messages = state.get("messages") or []
    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            last_user_msg = msg.get("content", "")
            break

    # --- Guard 1: pedido explícito ---
    if not await explicit_guard.is_allowed(last_user_msg):
        log.warning("guard_blocked", guard="explicit_request")
        # Volta para retenção — força nova rodada de oferta/pergunta
        return {"refund_step": RefundStep.RETENTION.value}

    # --- Guard 2: produto bloqueado ---
    if not product_guard.is_allowed(
        product_id=purchase.id,
        blocked_products=state.get("refund_blocked_products") or [],
    ):
        log.warning("guard_blocked", guard="product_blocked", product_id=purchase.id)
        return {"refund_step": RefundStep.DONE.value}

    # --- Guard 3: retenção obrigatória ---
    if not mandatory_guard.is_allowed(
        offers_made=state.get("offers_made") or [],
        is_duplicate_purchase=state.get("is_duplicate_purchase", False),
        is_cmp_student=state.get("is_cmp_student", False),
    ):
        log.warning("guard_blocked", guard="mandatory_retention")
        return {"refund_step": RefundStep.RETENTION.value}

    # --- Guard 5: mutex Redis ---
    try:
        await mutex_guard.acquire_or_raise(
            account_id=state["account_id"],
            contact_id=state["contact_id"],
            product_id=purchase.id,
        )
    except RefundMutexError:
        log.warning(
            "guard_blocked",
            guard="refund_mutex",
            reason="duplicate_refund_job",
        )
        return {"refund_step": RefundStep.DONE.value}

    # --- Processa reembolso via Hubla (stub Playwright) ---
    try:
        result = await hubla_port.process_refund(
            purchase_id=purchase.id,
            reason=state.get("refund_reason") or "",
        )
    except Exception as exc:
        log.error("hubla_refund_failed", error=str(exc))
        # Libera o mutex em caso de falha — outro job pode tentar
        await mutex_guard.release(
            account_id=state["account_id"],
            contact_id=state["contact_id"],
            product_id=purchase.id,
        )
        return {"refund_step": RefundStep.DONE.value}

    log.info(
        "refund_processed_via_hubla",
        purchase_id=purchase.id,
        success=result.success,
        refund_id=result.refund_id,
    )

    # --- Envia mensagem padrão (CRÍTICO: nunca "fizemos"/"processado") ---
    await chatnexo_port.send_text(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        text=MSG_REFUND_PROCESSING,
    )

    # --- Atualiza RefundCase ---
    if state.get("refund_case_id"):
        case = await refund_case_repo.get_by_id(state["refund_case_id"])
        if case is not None:
            case.status = RefundCaseStatus.REFUNDED
            await refund_case_repo.update(case)

    # --- Guard 4: marca flag same-turn ---
    return {
        "refund_processed": True,
        "refund_processed_in_current_turn": True,
        "refund_step": RefundStep.DONE.value,
    }
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "process_refund"
```
Esperado: 6 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/nodes.py \
        tests/unit/capabilities/refund/test_nodes.py
git commit -m "feat(refund): add node_process_refund with 4 guards, mutex, Hubla stub and standard message"
```

---

## Task 17: Nós `deny` e `deliver_offer`

**Files:**
- Modify: `src/nexoia/application/capabilities/refund/nodes.py`
- Test: append to `tests/unit/capabilities/refund/test_nodes.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# ---- node_deny ----
from nexoia.application.capabilities.refund.nodes import node_deny, node_deliver_offer


@pytest.mark.asyncio
async def test_deny_informs_purchase_date():
    """
    PRD 7.3 Passo 5: informar data da compra e que passou dos 7 dias.
    """
    chatnexo = AsyncMock()
    purchase = FakeHublaClient.make_purchase(days_ago=12)
    state = make_state(
        purchase=purchase,
        days_since_purchase=12,
        within_deadline=False,
    )

    result = await node_deny(
        state,
        chatnexo_port=chatnexo,
        handoff_service=AsyncMock(),
        refund_case_repo=AsyncMock(),
    )

    chatnexo.send_text.assert_awaited_once()
    text_sent = chatnexo.send_text.call_args.kwargs.get("text") \
                 or chatnexo.send_text.call_args.args[-1]
    # Menciona 7 dias e data da compra
    assert "7 dias" in text_sent.lower() or "sete dias" in text_sent.lower()
    assert result["refund_step"] == "done"


@pytest.mark.asyncio
async def test_deny_third_insistence_triggers_handoff():
    """
    PRD 7.3 Passo 5: na 3ª insistência após deny → escala silenciosa.
    """
    chatnexo = AsyncMock()
    handoff = AsyncMock()
    state = make_state(
        within_deadline=False,
        insistence_count_after_deny=3,
    )

    result = await node_deny(
        state,
        chatnexo_port=chatnexo,
        handoff_service=handoff,
        refund_case_repo=AsyncMock(),
    )

    handoff.escalate.assert_awaited_once()
    # Escala silenciosa: NADA enviado ao aluno
    chatnexo.send_text.assert_not_awaited()
    assert result["refund_step"] == "done"


@pytest.mark.asyncio
async def test_deny_increments_insistence_counter():
    """Cada novo turno após deny incrementa insistence_count."""
    state = make_state(
        within_deadline=False,
        insistence_count_after_deny=1,
    )

    result = await node_deny(
        state,
        chatnexo_port=AsyncMock(),
        handoff_service=AsyncMock(),
        refund_case_repo=AsyncMock(),
    )

    assert result["insistence_count_after_deny"] == 2


# ---- node_deliver_offer ----
@pytest.mark.asyncio
async def test_deliver_offer_marks_accepted_and_done():
    chatnexo = AsyncMock()
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=MagicMock(id="rc-1"))
    state = make_state(
        refund_case_id="rc-1",
        offer_accepted=True,
        offers_made=["N1"],
    )

    result = await node_deliver_offer(
        state,
        chatnexo_port=chatnexo,
        refund_case_repo=repo,
    )

    chatnexo.send_text.assert_awaited_once()
    assert result["refund_step"] == "done"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "deny or deliver_offer"
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar `node_deny` e `node_deliver_offer`**

```python
# (append em src/nexoia/application/capabilities/refund/nodes.py)
MSG_DENY_OUTSIDE_DEADLINE = (
    "Infelizmente seu prazo para reembolso já passou. Sua compra foi em "
    "{purchase_date}, e o direito de arrependimento (CDC) é de 7 dias. "
    "Posso te ajudar com mais alguma coisa?"
)


async def node_deny(
    state: RefundState,
    *,
    chatnexo_port: ChatNexoPort,
    handoff_service: Any,
    refund_case_repo: Any,
) -> dict[str, Any]:
    """
    Nega o reembolso por prazo vencido.

    PRD 7.3 Passo 5:
    - Informa data da compra e que passou dos 7 dias.
    - Na 3ª insistência: escala silenciosa (sem mensagem).
    - Procon/advogado/ação judicial: LegalMentionGuard (Core) já escalou antes
      de chegar aqui.
    """
    log = logger.bind(
        node="deny",
        capability="refund",
        account_id=state["account_id"],
        refund_case_id=state.get("refund_case_id"),
    )

    insistence = state.get("insistence_count_after_deny", 0)

    # 3ª insistência → escala silenciosa (sem mensagem)
    if insistence >= 3:
        log.warning(
            "third_insistence_handoff",
            insistence_count=insistence,
            reason="post_deny_insistence",
        )
        await handoff_service.escalate(
            account_id=state["account_id"],
            conversation_id=state["conversation_id"],
            reason="refund_post_deny_insistence",
        )
        if state.get("refund_case_id"):
            case = await refund_case_repo.get_by_id(state["refund_case_id"])
            if case is not None:
                case.status = RefundCaseStatus.ESCALATED
                await refund_case_repo.update(case)
        return {"refund_step": RefundStep.DONE.value}

    # Envia mensagem de deny com data da compra
    purchase = state.get("purchase")
    purchase_date = (
        purchase.created_at.strftime("%d/%m/%Y")
        if purchase is not None
        else "data desconhecida"
    )
    text = MSG_DENY_OUTSIDE_DEADLINE.format(purchase_date=purchase_date)
    await chatnexo_port.send_text(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        text=text,
    )
    log.info(
        "deny_sent",
        days_since_purchase=state.get("days_since_purchase"),
        insistence_count=insistence,
    )

    if state.get("refund_case_id"):
        case = await refund_case_repo.get_by_id(state["refund_case_id"])
        if case is not None:
            case.status = RefundCaseStatus.DENIED
            await refund_case_repo.update(case)

    return {
        "refund_step": RefundStep.DONE.value,
        "insistence_count_after_deny": insistence + 1,
    }


MSG_DELIVER_OFFER = (
    "Perfeito! Vou liberar seu benefício agora. Você recebe a confirmação "
    "por e-mail em instantes."
)


async def node_deliver_offer(
    state: RefundState,
    *,
    chatnexo_port: ChatNexoPort,
    refund_case_repo: Any,
) -> dict[str, Any]:
    """Entrega o benefício N1/N2 aceito e encerra com status OFFER_ACCEPTED."""
    log = logger.bind(
        node="deliver_offer",
        capability="refund",
        account_id=state["account_id"],
        refund_case_id=state.get("refund_case_id"),
    )

    await chatnexo_port.send_text(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        text=MSG_DELIVER_OFFER,
    )

    if state.get("refund_case_id"):
        case = await refund_case_repo.get_by_id(state["refund_case_id"])
        if case is not None:
            case.status = RefundCaseStatus.OFFER_ACCEPTED
            case.offer_accepted = True
            case.offers_made = list(state.get("offers_made") or [])
            await refund_case_repo.update(case)

    log.info("offer_delivered", offers_made=state.get("offers_made"))
    return {"refund_step": RefundStep.DONE.value}
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "deny or deliver_offer"
```
Esperado: 4 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/nodes.py \
        tests/unit/capabilities/refund/test_nodes.py
git commit -m "feat(refund): add node_deny (with 3rd insistence handoff) and node_deliver_offer"
```

---

## Task 18: build_refund_subgraph (LangGraph wiring)

**Files:**
- Create: `src/nexoia/application/capabilities/refund/graph.py`
- Test: append to `tests/unit/capabilities/refund/test_nodes.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# ---- build_refund_subgraph ----
from nexoia.application.capabilities.refund.graph import build_refund_subgraph


def test_build_refund_subgraph_returns_stategraph():
    graph = build_refund_subgraph()
    # Confirma que o grafo tem os nós esperados
    compiled = graph.compile()
    # API LangGraph expõe nodes via atributo
    assert "collect" in graph.nodes
    assert "check_deadline" in graph.nodes
    assert "retention_loop" in graph.nodes
    assert "process_refund" in graph.nodes
    assert "deny" in graph.nodes
    assert "deliver_offer" in graph.nodes
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "build_refund_subgraph"
```
Esperado: `ImportError`

- [ ] **Step 3: Implementar o graph builder**

```python
# src/nexoia/application/capabilities/refund/graph.py
"""Subgraph LangGraph da Capability Refund & Retention.

Fluxo:
    collect → check_deadline
        ├─ within_deadline=True + !duplicate → retention_loop
        │       ├─ offer_accepted=True → deliver_offer → END
        │       ├─ N2 recusado → process_refund → END
        │       └─ ainda no loop → END (aguarda próximo turno)
        ├─ within_deadline=True + duplicate → process_refund → END
        └─ within_deadline=False → deny → END

NOTA: Os guards (1/2/3/4/5) são invocados DENTRO do node_process_refund — não
como nós separados no grafo. Isso simplifica o wiring e permite rollback ao
retention_loop quando a retenção obrigatória falha.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from nexoia.application.capabilities.refund.nodes import (
    node_check_deadline,
    node_collect,
    node_deliver_offer,
    node_deny,
    node_process_refund,
    node_retention_loop,
)
from nexoia.application.capabilities.refund.state import RefundState


def _route_after_collect(state: RefundState) -> str:
    step = state.get("refund_step", "collect")
    if step == "check_deadline":
        return "check_deadline"
    return END  # aguarda próximo turno (precisa de mais dados)


def _route_after_check_deadline(state: RefundState) -> str:
    step = state.get("refund_step", "")
    if step == "deny":
        return "deny"
    if state.get("is_duplicate_purchase"):
        return "process_refund"
    if step == "retention":
        return "retention_loop"
    return END


def _route_after_retention(state: RefundState) -> str:
    step = state.get("refund_step", "")
    if step == "process_refund":
        return "process_refund"
    if step == "deliver_offer":
        return "deliver_offer"
    return END  # ainda aguardando resposta do aluno


def _route_after_process(state: RefundState) -> str:
    step = state.get("refund_step", "")
    if step == "retention":
        return "retention_loop"  # guards devolveram para retenção
    return END


def build_refund_subgraph() -> StateGraph:
    graph = StateGraph(RefundState)

    graph.add_node("collect", node_collect)
    graph.add_node("check_deadline", node_check_deadline)
    graph.add_node("retention_loop", node_retention_loop)
    graph.add_node("process_refund", node_process_refund)
    graph.add_node("deny", node_deny)
    graph.add_node("deliver_offer", node_deliver_offer)

    graph.set_entry_point("collect")

    graph.add_conditional_edges(
        "collect",
        _route_after_collect,
        {"check_deadline": "check_deadline", END: END},
    )
    graph.add_conditional_edges(
        "check_deadline",
        _route_after_check_deadline,
        {
            "deny": "deny",
            "process_refund": "process_refund",
            "retention_loop": "retention_loop",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "retention_loop",
        _route_after_retention,
        {
            "process_refund": "process_refund",
            "deliver_offer": "deliver_offer",
            END: END,
        },
    )
    graph.add_conditional_edges(
        "process_refund",
        _route_after_process,
        {"retention_loop": "retention_loop", END: END},
    )
    graph.add_edge("deny", END)
    graph.add_edge("deliver_offer", END)

    return graph
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_nodes.py -v -k "build_refund_subgraph"
```
Esperado: 1 teste PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/refund/graph.py \
        tests/unit/capabilities/refund/test_nodes.py
git commit -m "feat(refund): add build_refund_subgraph with 6 nodes and conditional routing"
```

---

## Task 19: Intent router — reconhece "refund"

**Files:**
- Modify: `src/nexoia/application/intent_router.py`
- Test: `tests/unit/capabilities/refund/test_intent_router.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/capabilities/refund/test_intent_router.py
import pytest

from nexoia.application.intent_router import classify_intent


@pytest.mark.asyncio
async def test_intent_classifies_refund_explicit():
    intent = await classify_intent("quero meu dinheiro de volta")
    assert intent == "refund"


@pytest.mark.asyncio
async def test_intent_classifies_refund_alt_phrasing():
    for phrase in [
        "quero cancelar minha compra",
        "quero reembolso",
        "como faço pra pedir reembolso",
        "pode estornar?",
    ]:
        assert await classify_intent(phrase) == "refund", f"falhou em: {phrase!r}"


@pytest.mark.asyncio
async def test_intent_does_not_classify_access_as_refund():
    intent = await classify_intent("como acesso o curso?")
    assert intent != "refund"


@pytest.mark.asyncio
async def test_intent_does_not_classify_knowledge_as_refund():
    intent = await classify_intent("o que é tráfego pago?")
    assert intent != "refund"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/refund/test_intent_router.py -v
```
Esperado: todos FAIL (intent "refund" não reconhecido)

- [ ] **Step 3: Adicionar intent ao router existente**

No arquivo `src/nexoia/application/intent_router.py`, adicionar ao prompt/classifier:

```python
# ... prompt existente ...
# Incluir no enumerado de intents:
#   - "refund": quando o aluno pede reembolso, cancelamento ou estorno.
#     Exemplos: "quero reembolso", "cancelar compra", "estornar", "meu dinheiro de volta".
#
# Regra de prioridade: se a mensagem menciona Procon/advogado/ação judicial,
# o LegalMentionGuard (Core) já deve ter escalado antes — não chega aqui.
```

Também adicionar ao mapa de roteamento `INTENT_TO_CAPABILITY`:

```python
INTENT_TO_CAPABILITY = {
    # ... mapeamentos existentes ...,
    "refund": "refund",
}
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/refund/test_intent_router.py -v
```
Esperado: 4 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/intent_router.py \
        tests/unit/capabilities/refund/test_intent_router.py
git commit -m "feat(refund): register 'refund' intent in router with explicit classification examples"
```

---

## Task 20: Métricas Prometheus da capability

**Files:**
- Modify: `src/nexoia/infrastructure/observability/metrics.py`
- Test: `tests/unit/observability/test_refund_metrics.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/observability/test_refund_metrics.py
from nexoia.infrastructure.observability.metrics import (
    refund_capability_total,
    refund_deadline_check_total,
    refund_retention_offer_total,
    refund_retention_acceptance_rate,
    refund_mutex_blocked_total,
)


def test_refund_capability_counter_labels():
    refund_capability_total.labels(status="refunded").inc()
    refund_capability_total.labels(status="denied").inc()
    refund_capability_total.labels(status="offer_accepted").inc()
    refund_capability_total.labels(status="escalated").inc()
    refund_capability_total.labels(status="error").inc()


def test_refund_deadline_check_labels():
    refund_deadline_check_total.labels(result="within").inc()
    refund_deadline_check_total.labels(result="exceeded").inc()


def test_refund_retention_offer_labels():
    refund_retention_offer_total.labels(offer="N1").inc()
    refund_retention_offer_total.labels(offer="N2").inc()


def test_refund_retention_acceptance_rate_gauge():
    refund_retention_acceptance_rate.set(0.35)


def test_refund_mutex_blocked_counter():
    refund_mutex_blocked_total.inc()
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/observability/test_refund_metrics.py -v
```
Esperado: `ImportError`

- [ ] **Step 3: Adicionar métricas ao arquivo existente**

No arquivo `src/nexoia/infrastructure/observability/metrics.py`, adicionar:

```python
from prometheus_client import Counter, Gauge

# --- Capability Refund & Retention ---
refund_capability_total = Counter(
    "refund_capability_total",
    "Total de execuções da Capability Refund",
    labelnames=["status"],  # refunded | denied | offer_accepted | escalated | error
)
refund_deadline_check_total = Counter(
    "refund_deadline_check_total",
    "Checagens de prazo CDC na Capability Refund",
    labelnames=["result"],  # within | exceeded
)
refund_retention_offer_total = Counter(
    "refund_retention_offer_total",
    "Ofertas de retenção enviadas",
    labelnames=["offer"],  # N1 | N2
)
refund_retention_acceptance_rate = Gauge(
    "refund_retention_acceptance_rate",
    "Taxa de aceitação de ofertas de retenção (0.0 a 1.0)",
)
refund_mutex_blocked_total = Counter(
    "refund_mutex_blocked_total",
    "Total de jobs de reembolso bloqueados pelo mutex Redis",
)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/observability/test_refund_metrics.py -v
```
Esperado: 5 testes PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/observability/metrics.py \
        tests/unit/observability/test_refund_metrics.py
git commit -m "feat(refund): add Prometheus metrics for Refund capability"
```

---

## Task 21: Teste de integração E2E (incluindo mutex, Art.49, duplicate)

**Files:**
- Create: `tests/integration/test_refund_flow.py`

- [ ] **Step 1: Escrever o teste de integração completo**

```python
# tests/integration/test_refund_flow.py
"""
Teste E2E da Capability Refund & Retention usando fakes e DB real.

Cobre:
- Happy path: dentro do prazo, recusa N1+N2, reembolso processado com mensagem padrão
- Retenção N1 aceita → deliver_offer
- Retenção N2 aceita → deliver_offer
- Fora do prazo → deny com data da compra
- Compra duplicada → pula retenção
- Art. 49 CDC → força within_deadline=True
- Mutex Redis → 2º job simultâneo bloqueado
- 3ª insistência pós-deny → handoff silencioso
- Legal mention → handoff silencioso imediato (Core LegalMentionGuard)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from nexoia.application.capabilities.refund.graph import build_refund_subgraph
from nexoia.application.capabilities.refund.guards.explicit_request import (
    ExplicitRefundRequestGuard,
)
from nexoia.application.capabilities.refund.guards.mandatory_retention import (
    MandatoryRetentionGuard,
)
from nexoia.application.capabilities.refund.guards.product_blocked import (
    ProductBlockedGuard,
)
from nexoia.application.capabilities.refund.guards.refund_mutex import (
    RefundMutexGuard,
)
from nexoia.application.capabilities.refund.guards.same_turn_block import (
    SameTurnBlockGuard,
)
from nexoia.application.capabilities.refund.nodes import (
    MSG_REFUND_PROCESSING,
    node_check_deadline,
    node_collect,
    node_deliver_offer,
    node_deny,
    node_process_refund,
    node_retention_loop,
)
from nexoia.application.capabilities.refund.state import RefundState
from nexoia.domain.entities.refund_case import RefundCaseStatus
from nexoia.domain.errors import RefundMutexError
from nexoia.infrastructure.db.repositories.refund_case_repo import (
    RefundCaseRepository,
)
from nexoia.infrastructure.hubla.schemas import HublaPurchase
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient
from tests.fakes.fake_hubla_client import FakeHublaClient


def _initial_state(**overrides) -> RefundState:
    base: dict = dict(
        account_id=1,
        conversation_id="conv-int-1",
        contact_id="contact-int-1",
        messages=[],
        correlation_id="corr-int-1",
        refund_case_id=None,
        student_email=None,
        student_cpf=None,
        refund_reason=None,
        purchase=None,
        is_recurring=False,
        days_since_purchase=None,
        within_deadline=None,
        is_duplicate_purchase=False,
        is_cmp_student=False,
        offers_made=[],
        offer_accepted=False,
        explicit_refund_request=False,
        refund_blocked_products=[],
        refund_processed=False,
        refund_processed_in_current_turn=False,
        refund_step="collect",
        insistence_count_after_deny=0,
    )
    base.update(overrides)
    return base  # type: ignore[return-value]


# ---------- Happy path: dentro do prazo, N1+N2 recusados ----------
@pytest.mark.asyncio
async def test_happy_path_refund_processed(db_session):
    """
    Cenário: aluno pede reembolso 3 dias após a compra, recusa N1, recusa N2,
    pede explicitamente → reembolso é processado com mensagem padrão.
    """
    purchase = FakeHublaClient.make_purchase(days_ago=3, purchase_id="p-happy")
    hubla = FakeHublaClient(purchase=purchase)
    chatnexo = FakeChatNexoClient()
    repo = RefundCaseRepository(db_session)

    # Redis mutex fake: set retorna True; delete: no-op
    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock()
    mutex = RefundMutexGuard(redis=redis_mock, ttl_seconds=3600)
    explicit_guard = ExplicitRefundRequestGuard(
        llm_classifier=AsyncMock(return_value=True),
    )
    mandatory_guard = MandatoryRetentionGuard()
    product_guard = ProductBlockedGuard()

    extractor = AsyncMock(return_value={
        "reason": "não era o que esperava",
        "email": "aluno@email.com",
        "cpf": "12345678900",
    })

    state = _initial_state(
        messages=[
            {"role": "user", "content": "quero reembolso, não era o que esperava"},
            {"role": "user", "content": "aluno@email.com 123.456.789-00"},
        ],
    )

    # collect → cria RefundCase
    upd = await node_collect(
        state, chatnexo_port=chatnexo, extractor=extractor, refund_case_repo=repo,
    )
    state.update(upd)

    # check_deadline → within_deadline=True
    upd = await node_check_deadline(
        state,
        hubla_port=hubla,
        refund_case_repo=repo,
        art49_checker=AsyncMock(return_value=False),
        deadline_days=7,
    )
    state.update(upd)
    assert state["within_deadline"] is True

    # retention_loop — N1 ofertado
    upd = await node_retention_loop(
        state, chatnexo_port=chatnexo,
        offer_classifier=AsyncMock(return_value="refuse"),
    )
    state.update(upd)
    assert state["offers_made"] == ["N1"]

    # retention_loop — N1 recusado → N2 ofertado
    state["messages"].append({"role": "user", "content": "não quero"})
    upd = await node_retention_loop(
        state, chatnexo_port=chatnexo,
        offer_classifier=AsyncMock(return_value="refuse"),
    )
    state.update(upd)
    assert state["offers_made"] == ["N1", "N2"]

    # retention_loop — N2 recusado → process_refund
    state["messages"].append({"role": "user", "content": "quero reembolso mesmo"})
    upd = await node_retention_loop(
        state, chatnexo_port=chatnexo,
        offer_classifier=AsyncMock(return_value="refuse"),
    )
    state.update(upd)
    assert state["refund_step"] == "process_refund"

    # process_refund → envia mensagem padrão
    upd = await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=mutex,
        explicit_guard=explicit_guard,
        mandatory_guard=mandatory_guard,
        product_guard=product_guard,
        chatnexo_port=chatnexo,
        refund_case_repo=repo,
    )
    state.update(upd)

    # Validações
    assert state["refund_processed"] is True
    assert state["refund_processed_in_current_turn"] is True
    assert hubla.refund_calls == 1
    assert chatnexo.last_sent_text == MSG_REFUND_PROCESSING
    # Nunca diz "fizemos" / "processado"
    assert "fizemos" not in chatnexo.last_sent_text.lower()
    assert "processado" not in chatnexo.last_sent_text.lower()

    # Guard 4: same-turn block impede finish_attendance
    same_turn = SameTurnBlockGuard()
    assert same_turn.can_finish_attendance(
        refund_processed_in_current_turn=state["refund_processed_in_current_turn"]
    ) is False

    # RefundCase persistido como REFUNDED
    case = await repo.get_by_id(state["refund_case_id"])
    assert case is not None
    assert case.status == RefundCaseStatus.REFUNDED


# ---------- Retenção N1 aceita ----------
@pytest.mark.asyncio
async def test_retention_n1_accepted_delivers_offer(db_session):
    purchase = FakeHublaClient.make_purchase(days_ago=2)
    hubla = FakeHublaClient(purchase=purchase)
    chatnexo = FakeChatNexoClient()
    repo = RefundCaseRepository(db_session)
    extractor = AsyncMock(return_value={
        "reason": "cansei", "email": "a@a.com", "cpf": "11122233344",
    })

    state = _initial_state(messages=[
        {"role": "user", "content": "quero cancelar, cansei"},
        {"role": "user", "content": "a@a.com 11122233344"},
    ])

    state.update(await node_collect(
        state, chatnexo_port=chatnexo, extractor=extractor, refund_case_repo=repo,
    ))
    state.update(await node_check_deadline(
        state, hubla_port=hubla, refund_case_repo=repo,
        art49_checker=AsyncMock(return_value=False), deadline_days=7,
    ))
    state.update(await node_retention_loop(
        state, chatnexo_port=chatnexo, offer_classifier=AsyncMock(),
    ))
    # Aluno aceita N1
    state["messages"].append({"role": "user", "content": "aceito!"})
    state.update(await node_retention_loop(
        state, chatnexo_port=chatnexo,
        offer_classifier=AsyncMock(return_value="accept"),
    ))
    assert state["refund_step"] == "deliver_offer"

    state.update(await node_deliver_offer(
        state, chatnexo_port=chatnexo, refund_case_repo=repo,
    ))

    case = await repo.get_by_id(state["refund_case_id"])
    assert case.status == RefundCaseStatus.OFFER_ACCEPTED
    assert case.offer_accepted is True


# ---------- Fora do prazo ----------
@pytest.mark.asyncio
async def test_deny_outside_deadline_informs_date(db_session):
    purchase = FakeHublaClient.make_purchase(days_ago=15, purchase_id="p-old")
    hubla = FakeHublaClient(purchase=purchase)
    chatnexo = FakeChatNexoClient()
    repo = RefundCaseRepository(db_session)
    extractor = AsyncMock(return_value={
        "reason": "atrasou", "email": "a@a.com", "cpf": "99988877766",
    })

    state = _initial_state(messages=[
        {"role": "user", "content": "quero reembolso, atrasou"},
        {"role": "user", "content": "a@a.com 99988877766"},
    ])

    state.update(await node_collect(
        state, chatnexo_port=chatnexo, extractor=extractor, refund_case_repo=repo,
    ))
    state.update(await node_check_deadline(
        state, hubla_port=hubla, refund_case_repo=repo,
        art49_checker=AsyncMock(return_value=False), deadline_days=7,
    ))
    assert state["within_deadline"] is False
    assert state["refund_step"] == "deny"

    state.update(await node_deny(
        state, chatnexo_port=chatnexo,
        handoff_service=AsyncMock(), refund_case_repo=repo,
    ))

    assert "7 dias" in chatnexo.last_sent_text.lower()
    case = await repo.get_by_id(state["refund_case_id"])
    assert case.status == RefundCaseStatus.DENIED


# ---------- Compra duplicada pula retenção ----------
@pytest.mark.asyncio
async def test_duplicate_purchase_skips_retention(db_session):
    purchase = FakeHublaClient.make_purchase(
        days_ago=3, is_duplicate=True, purchase_id="p-dup",
    )
    hubla = FakeHublaClient(purchase=purchase)
    chatnexo = FakeChatNexoClient()
    repo = RefundCaseRepository(db_session)
    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock()
    mutex = RefundMutexGuard(redis=redis_mock, ttl_seconds=3600)
    extractor = AsyncMock(return_value={
        "reason": "comprei duplicado", "email": "a@a.com", "cpf": "11111111111",
    })

    state = _initial_state(messages=[
        {"role": "user", "content": "comprei duplicado, quero reembolso"},
        {"role": "user", "content": "a@a.com 11111111111"},
    ])

    state.update(await node_collect(
        state, chatnexo_port=chatnexo, extractor=extractor, refund_case_repo=repo,
    ))
    state.update(await node_check_deadline(
        state, hubla_port=hubla, refund_case_repo=repo,
        art49_checker=AsyncMock(return_value=False), deadline_days=7,
    ))
    assert state["is_duplicate_purchase"] is True

    # Segue direto para process_refund
    state.update(await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=mutex,
        explicit_guard=ExplicitRefundRequestGuard(
            llm_classifier=AsyncMock(return_value=True),
        ),
        mandatory_guard=MandatoryRetentionGuard(),
        product_guard=ProductBlockedGuard(),
        chatnexo_port=chatnexo,
        refund_case_repo=repo,
    ))

    assert state["refund_processed"] is True
    assert state["offers_made"] == []  # nenhuma oferta feita
    assert hubla.refund_calls == 1


# ---------- Art. 49 CDC ----------
@pytest.mark.asyncio
async def test_art49_forces_within_deadline(db_session):
    purchase = FakeHublaClient.make_purchase(days_ago=15)  # fora do prazo
    hubla = FakeHublaClient(purchase=purchase)
    repo = RefundCaseRepository(db_session)

    state = _initial_state(
        refund_case_id=None, student_email="a@a.com",
    )
    # Simula RefundCase já criado (pulando collect)
    from nexoia.domain.entities.refund_case import RefundCase
    case = RefundCase(
        account_id=1, contact_id="contact-int-1",
        conversation_id="conv-int-1", student_email="a@a.com",
    )
    await repo.save(case)
    state["refund_case_id"] = case.id

    state.update(await node_check_deadline(
        state, hubla_port=hubla, refund_case_repo=repo,
        art49_checker=AsyncMock(return_value=True),  # Art. 49 aplicável
        deadline_days=7,
    ))
    assert state["within_deadline"] is True
    assert state["refund_step"] == "retention"


# ---------- Mutex Redis bloqueia job duplicado ----------
@pytest.mark.asyncio
async def test_mutex_blocks_duplicate_concurrent_jobs(db_session):
    """Dois jobs simultâneos para o mesmo (account, contact, product) → 2º bloqueado."""
    purchase = FakeHublaClient.make_purchase(purchase_id="p-mutex")

    # Simula comportamento real de Redis: 1ª chamada set()=True, 2ª set()=False
    redis_mock = AsyncMock()
    redis_mock.set = AsyncMock(side_effect=[True, False])  # 1º ok, 2º bloqueado
    redis_mock.delete = AsyncMock()

    mutex_a = RefundMutexGuard(redis=redis_mock, ttl_seconds=3600)
    mutex_b = RefundMutexGuard(redis=redis_mock, ttl_seconds=3600)

    acquired_a = await mutex_a.try_acquire(
        account_id=1, contact_id="c-1", product_id="p-mutex",
    )
    acquired_b = await mutex_b.try_acquire(
        account_id=1, contact_id="c-1", product_id="p-mutex",
    )

    assert acquired_a is True
    assert acquired_b is False

    # Segunda tentativa em node_process_refund deve short-circuit
    hubla = FakeHublaClient(purchase=purchase)
    chatnexo = FakeChatNexoClient()
    redis_mock_blocked = AsyncMock()
    redis_mock_blocked.set = AsyncMock(return_value=False)
    redis_mock_blocked.delete = AsyncMock()
    mutex_blocked = RefundMutexGuard(redis=redis_mock_blocked, ttl_seconds=3600)

    state = _initial_state(
        purchase=purchase,
        offers_made=["N1", "N2"],
        explicit_refund_request=True,
        messages=[{"role": "user", "content": "quero reembolso"}],
    )

    state.update(await node_process_refund(
        state,
        hubla_port=hubla,
        mutex_guard=mutex_blocked,
        explicit_guard=ExplicitRefundRequestGuard(
            llm_classifier=AsyncMock(return_value=True),
        ),
        mandatory_guard=MandatoryRetentionGuard(),
        product_guard=ProductBlockedGuard(),
        chatnexo_port=chatnexo,
        refund_case_repo=RefundCaseRepository(db_session),
    ))

    # Hubla NÃO chamada 2x — mutex bloqueou
    assert hubla.refund_calls == 0


# ---------- 3ª insistência pós-deny → handoff silencioso ----------
@pytest.mark.asyncio
async def test_third_insistence_post_deny_escalates_silently(db_session):
    handoff = AsyncMock()
    chatnexo = FakeChatNexoClient()
    repo = RefundCaseRepository(db_session)
    from nexoia.domain.entities.refund_case import RefundCase
    case = RefundCase(
        account_id=1, contact_id="contact-int-1",
        conversation_id="conv-int-1", student_email="a@a.com",
    )
    await repo.save(case)

    state = _initial_state(
        refund_case_id=case.id,
        insistence_count_after_deny=3,
        within_deadline=False,
    )

    chatnexo.last_sent_text = None  # reset
    state.update(await node_deny(
        state, chatnexo_port=chatnexo, handoff_service=handoff, refund_case_repo=repo,
    ))

    handoff.escalate.assert_awaited_once()
    # Silencioso: nada enviado ao aluno
    assert chatnexo.last_sent_text is None
    reloaded = await repo.get_by_id(case.id)
    assert reloaded.status == RefundCaseStatus.ESCALATED
```

- [ ] **Step 2: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_refund_flow.py -v
```
Esperado: 7 testes PASSED

- [ ] **Step 3: Rodar toda a suite para regressão**

```bash
uv run pytest tests/ -v --tb=short
```
Esperado: todos PASSED

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_refund_flow.py
git commit -m "feat(refund): add E2E integration tests (happy path, Art.49, mutex, duplicate, insistence)"
```

---

## Task 22: Atualizar OPEN_QUESTIONS.md e INDEX.md

**Files:**
- Modify: `docs/superpowers/OPEN_QUESTIONS.md`
- Modify: `docs/superpowers/INDEX.md`

- [ ] **Step 1: Garantir que CQ-R03 continua aberta**

No arquivo `docs/superpowers/OPEN_QUESTIONS.md`, confirmar que a seção **Capability Refund & Retention (Spec ④)** mantém CQ-R03 (o que é "aluno CMP") como única questão ainda em aberto. CQ-R01, CQ-R02 e CQ-R04 já foram respondidas e estão na seção "Respondidas".

Se necessário, adicionar lembrete no topo:

```markdown
> Status da Spec ④: CQ-R01 (Playwright refund), CQ-R02 (ofertas N1/N2 fixas)
> e CQ-R04 (Playwright get_purchase) já respondidas — stubs refletem isso.
> CQ-R03 (aluno CMP) continua aberta — `is_cmp_student` é stub no retention_loop.
```

- [ ] **Step 2: Atualizar INDEX.md**

No arquivo `docs/superpowers/INDEX.md`, atualizar a linha do Spec ④:

```markdown
| ④ | **Capability Refund & Retention** — fluxo de reembolso, retenção N1/N2, Art.49 CDC | [spec](specs/2026-04-18-nexoia-capability-refund-design.md) | [plano](plans/2026-04-18-nexoia-capability-refund.md) | ⏳ Pendente |
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/OPEN_QUESTIONS.md docs/superpowers/INDEX.md
git commit -m "docs: mark Refund plan as created in INDEX and note CQ-R03 still open"
```

---

## Self-Review

### Cobertura de Requisitos Funcionais (RF)

| RF | Requisito | Coberto por |
|----|-----------|-------------|
| `RF-R01` | Coleta motivo + email + CPF juntos; motivo extraído via LLM se veio na 1ª msg | Task 13 — `node_collect` + testes `test_collect_asks_reason_first_when_absent`, `test_collect_asks_email_and_cpf_together_after_reason`, `test_collect_creates_refund_case_when_email_and_cpf_arrive` |
| `RF-R02` | Verifica prazo CDC (≤7 dentro, >7 fora) | Task 14 — `node_check_deadline` + testes `test_check_deadline_within_cdc_window`, `test_check_deadline_outside_cdc_window_goes_to_deny` |
| `RF-R03` | Art. 49 CDC: canal anterior dentro do prazo → within_deadline=True | Task 14 — `art49_checker` param + teste `test_check_deadline_art49_forces_within_deadline`; Task 21 — `test_art49_forces_within_deadline` |
| `RF-R04` | Compra duplicada → reembolso sem retenção | Task 14 (seta `is_duplicate_purchase`) + Task 15 (skip em retention_loop) + Task 21 — `test_duplicate_purchase_skips_retention` |
| `RF-R05` | Retenção máx 2 ofertas, nunca repete | Task 15 — `node_retention_loop` + testes `test_retention_offers_n1_when_no_offers_made`, `test_retention_n1_refused_sends_n2`, `test_retention_never_repeats_same_offer` |
| `RF-R06` | Ofertas N1/N2 por produto — respondida em CQ-R02 (fixas para G2) | Task 15 — constantes `MSG_OFFER_N1`, `MSG_OFFER_N2` (Acesso Vitalício e Mentoria Tráfego) |
| `RF-R07` | Aluno CMP — TODO CQ-R03 | Task 15 — stub com `log.warning(todo="CQ-R03")` em `node_retention_loop` |
| `RF-R08` | Após recusa dupla: process_refund + mensagem padrão; NUNCA "fizemos"/"processado" | Task 16 — `node_process_refund` + constante `MSG_REFUND_PROCESSING` + teste `test_process_refund_sends_standard_message_never_past_tense` |
| `RF-R09` | Deny fora do prazo informa data; 3ª insistência → handoff silencioso | Task 17 — `node_deny` + testes `test_deny_informs_purchase_date`, `test_deny_third_insistence_triggers_handoff`, `test_deny_increments_insistence_counter` |
| `RF-R10` | Procon/advogado → handoff silencioso imediato | Herdado do Core (Spec ①) `LegalMentionGuard` — notado nas docstrings de `node_deny` e no spec |
| `RF-R11` | `process_refund` stub via Playwright | Task 3 — `HublaClient.process_refund()` levanta `NotImplementedError` com referência a CQ-R01 |
| `RF-R12` | Mutex Redis Guard 5 `(account_id, contact_id, product_id)` TTL 1h | Task 12 — `RefundMutexGuard` + teste `test_mutex_key_format_is_deterministic`, `test_mutex_acquire_returns_false_when_already_held`; Task 21 — `test_mutex_blocks_duplicate_concurrent_jobs` |
| `RF-R13` | Recorrente → prazo conta da primeira parcela | Task 14 — `node_check_deadline` usa `first_charge_at` se `is_recurring` + teste `test_check_deadline_recurring_counts_from_first_charge` |
| `RF-R14` | Compras separadas → prazo independente por purchase_id | Task 14 — cada invocação usa `purchase.id` específico (documentado na docstring); roadmap multi-produto futuro |
| `RF-R15` | Guard 1 ExplicitRefundRequest | Task 8 — `ExplicitRefundRequestGuard` + Task 16 checagem em `node_process_refund` + teste `test_process_refund_blocked_by_explicit_guard` |
| `RF-R16` | Guard 2 ProductBlocked | Task 9 — `ProductBlockedGuard` + Task 16 checagem + teste `test_process_refund_blocked_by_product_guard` |
| `RF-R17` | Guard 3 MandatoryRetention | Task 10 — `MandatoryRetentionGuard` + Task 16 checagem + teste `test_process_refund_blocked_by_mandatory_retention_guard` |
| `RF-R18` | Guard 4 SameTurnBlock (nunca finish no mesmo turno que process_refund) | Task 11 — `SameTurnBlockGuard` + Task 16 seta `refund_processed_in_current_turn=True` + Task 21 assert no E2E |
| `RF-R19` | Nunca falar sobre prazo sem ter buscado a compra na Hubla antes | Task 14 — `node_check_deadline` só retorna `days_since_purchase` APÓS `hubla_port.get_purchase_by_email`; docstring reforça regra crítica |

### Cobertura de Requisitos Não-Funcionais (RNF)

| RNF | Requisito | Coberto por |
|-----|-----------|-------------|
| `RNF-R01` | Tenant isolation: toda query filtra por account_id | Task 6 — `RefundCaseRepository.list_by_contact(account_id, contact_id)` e model com `account_id` indexado |
| `RNF-R02` | Estado entre turnos via checkpoint LangGraph | Task 7 — `RefundState` herda de `ConversationState` (Core gerencia checkpointing) |
| `RNF-R03` | Circuit breaker herdado do Core aplicado ao HublaClient | Herdado do Core — `FakeHublaClient.fail_times_*` permite testar; breaker decorator aplicado no wiring do container DI (fora deste plano) |
| `RNF-R04` | Cobertura de testes ≥90% | Tasks 1-21 — cada nó, guard e repositório tem testes unitários e integração |
| `RNF-R05` | Idle/timeout via Core | Nota explícita no spec; capability não tem lógica própria |

### Regras Críticas do PRD 7.3 — Verificação

| Regra crítica | Onde é aplicada |
|---------------|-----------------|
| "Sempre perguntar motivo antes de pedir email" | Task 13 — `node_collect` + docstring + teste `test_collect_asks_reason_first_when_absent` |
| "Nunca dizer 'fizemos' ou 'processado'" | Task 16 — constante `MSG_REFUND_PROCESSING` (gerúndio "tô processando") + teste assertivo |
| "Nunca chamar `finish_attendance` no mesmo turno que `process_refund`" | Task 11 (Guard 4) + Task 16 seta flag + Task 21 assert `can_finish_attendance(...) is False` |
| "Nunca falar sobre prazo sem ter buscado a compra na Hubla antes" | Task 14 — ordem sequencial no `node_check_deadline` + docstring |
| "N1 obrigatório antes de qualquer reembolso, salvo exceções" | Task 10 (Guard 3) + Task 15 (oferta N1 antes de N2) |
| "Se N1 recusado, N2 obrigatório" | Task 10 (Guard 3) + Task 15 + Task 21 happy path |
| "Máximo 2 ofertas. Nunca repetir a mesma" | Task 15 — lógica de `offers_made` + teste `test_retention_never_repeats_same_offer` |
| "Fora do prazo = zero retenção. Informar e negar" | Task 17 — `node_deny` + routing do graph em Task 18 |
| "Na 3ª insistência: escala silenciosa" | Task 17 — `insistence_count_after_deny >= 3` → handoff sem mensagem |
| "Procon/advogado → escala silenciosa imediata, nenhuma mensagem" | Core `LegalMentionGuard` (Spec ①) — nota explícita |

### TODOs com referência a OPEN_QUESTIONS.md

- **CQ-R01** — `HublaClient.process_refund` em Task 3 → `NotImplementedError` com string `"ver OPEN_QUESTIONS.md#CQ-R01"` (respondida: Playwright)
- **CQ-R03** — `node_retention_loop` em Task 15 → `log.warning("cmp_student_stub_skipping_retention", todo="CQ-R03")` (**continua em aberto**)
- **CQ-R04** — `HublaClient.get_purchase_by_email` em Task 3 → `NotImplementedError` com `"#CQ-R04"` (respondida: Playwright)

### Dependência explícita da Spec ① Core

- `ConversationState` — base de `RefundState` (Task 7)
- `LegalMentionGuard` — escala imediata para menções jurídicas (referenciado em Task 17 e no spec)
- `HandoffService` — usado em `node_deny` para 3ª insistência (Task 17)
- `mutex Redis helpers` — `RefundMutexGuard` (Task 12) usa `redis.set(..., nx=True, ex=TTL)` que assume cliente Redis async já configurado pelo Core
- `intent_router` — extendido em Task 19 (Core define a base)
- `ChatNexoPort.send_text` / `send_template` — usados por todos os nós (Core define o port)
- `Legal History` — fonte para `art49_checker` (busca mensagens de canais anteriores) — implementação do checker é injetada, assumida do Core

### Tipos consistentes

- `RefundCaseStatus` definido em Task 1, usado em Tasks 6, 13, 14, 16, 17, 21
- `RefundStep` definido em Task 1, usado em Tasks 13-18 como chave `refund_step` no state
- `HublaPurchase` / `RefundResult` definidos em Task 2, usados em Tasks 3, 14, 16, 21
- `FakeHublaClient.make_purchase()` helper criado em Task 2 e reutilizado em Tasks 14-21
- Guards expostos com assinaturas coerentes (todos retornam bool; mutex é async)

### Sem placeholders vagos

Todos os `TODO` no código têm referência explícita a `OPEN_QUESTIONS.md#CQ-RXX` ou a uma das respostas já documentadas. O único comportamento ainda stub é `is_cmp_student` (Task 15), apontando para CQ-R03.

### Ordem de commits

Cada task termina com um único commit com mensagem `feat(refund): ...` ou `docs: ...` seguindo Conventional Commits. Nenhuma task executa operação destrutiva ou push remoto.
