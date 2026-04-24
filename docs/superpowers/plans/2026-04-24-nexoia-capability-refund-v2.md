# Capability ④ Refund & Retention — Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Capability Refund & Retention — fluxo LLM-orquestrado com 3 skills (`verificar_elegibilidade_reembolso`, `oferecer_retencao`, `processar_reembolso`), retenção N1→N2, mutex Redis anti-duplicata e regra CDC de 7 dias.

**Architecture:** Skill Architecture (Core v2) — factory-with-closure `make_refund_skills(ports) -> list[BaseTool]`. Use cases recebem dependências via `__init__`, `@tool` closures capturam os use cases, `get_config()["configurable"]` lê `account_id/phone` por request. Estado entre turnos persiste em `RefundCase` no banco — sem estado no grafo.

**Tech Stack:** Python 3.12, SQLAlchemy 2 (async ORM), Alembic, Redis SETNX, LangChain `@tool`, LangGraph `get_config()`, pytest-asyncio, AsyncMock.

---

## Estrutura de arquivos

**Criar:**
```
src/nexoia/domain/entities/refund_case.py
src/nexoia/domain/ports/hubla_port.py
src/nexoia/domain/ports/refund_mutex.py
src/nexoia/domain/ports/legal_history_port.py
src/nexoia/infrastructure/hubla/__init__.py
src/nexoia/infrastructure/hubla/client.py
src/nexoia/infrastructure/redis/refund_mutex.py
src/nexoia/infrastructure/db/repositories/refund_case_repo.py
src/nexoia/application/use_cases/refund/__init__.py
src/nexoia/application/use_cases/refund/verificar_elegibilidade.py
src/nexoia/application/use_cases/refund/iniciar_retencao.py
src/nexoia/application/use_cases/refund/processar_reembolso.py
src/nexoia/infrastructure/skills/refund.py
tests/unit/domain/test_refund_case.py
tests/unit/infrastructure/db/test_refund_case_repo.py
tests/unit/infrastructure/skills/test_refund_skills.py
tests/unit/use_cases/refund/__init__.py
tests/unit/use_cases/refund/test_verificar_elegibilidade.py
tests/unit/use_cases/refund/test_iniciar_retencao.py
tests/unit/use_cases/refund/test_processar_reembolso.py
migrations/versions/add_refund_cases_table.py  (gerado via alembic)
```

**Modificar:**
```
src/nexoia/infrastructure/db/models.py          — + RefundCaseModel
src/nexoia/config/settings.py                   — + refund_deadline_days, refund_mutex_ttl_seconds
src/nexoia/infrastructure/langgraph_runtime/graph_builder.py  — + make_refund_skills(...)
```

---

### Task 1: RefundCase entity + RefundCaseStatus enum

**Files:**
- Create: `src/nexoia/domain/entities/refund_case.py`
- Test: `tests/unit/domain/test_refund_case.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/domain/test_refund_case.py
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus


def test_refund_case_defaults():
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="aluno@g2.com",
    )
    assert case.status == RefundCaseStatus.COLLECTING
    assert case.offers_made == []
    assert case.offer_accepted is False
    assert case.within_deadline is None
    assert case.is_duplicate_purchase is False
    assert case.refund_processed_this_turn is False
    assert case.id is not None


def test_refund_case_status_values():
    assert RefundCaseStatus.COLLECTING == "collecting"
    assert RefundCaseStatus.REFUNDED == "refunded"
    assert RefundCaseStatus.DENIED == "denied"
    assert RefundCaseStatus.IN_RETENTION == "in_retention"
    assert RefundCaseStatus.ESCALATED == "escalated"
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/domain/test_refund_case.py -v
```
Esperado: `ImportError` — módulo não existe.

- [ ] **Step 3: Implementar o arquivo**

```python
# src/nexoia/domain/entities/refund_case.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class RefundCaseStatus(StrEnum):
    COLLECTING        = "collecting"
    CHECKING_DEADLINE = "checking_deadline"
    IN_RETENTION      = "in_retention"
    OFFER_ACCEPTED    = "offer_accepted"
    REFUNDED          = "refunded"
    DENIED            = "denied"
    ESCALATED         = "escalated"


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
    is_duplicate_purchase: bool = False
    offers_made: list[str] = field(default_factory=list)
    offer_accepted: bool = False
    refund_processed_this_turn: bool = False
    status: RefundCaseStatus = RefundCaseStatus.COLLECTING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/domain/test_refund_case.py -v
```
Esperado: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/entities/refund_case.py tests/unit/domain/test_refund_case.py
git commit -m "feat: add RefundCase entity and RefundCaseStatus enum"
```

---

### Task 2: Ports — HublaPort, HublaPurchase, RefundResult, RefundMutexPort, LegalHistoryPort

**Files:**
- Create: `src/nexoia/domain/ports/hubla_port.py`
- Create: `src/nexoia/domain/ports/refund_mutex.py`
- Create: `src/nexoia/domain/ports/legal_history_port.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/domain/test_refund_ports.py
from datetime import datetime, UTC
from nexoia.domain.ports.hubla_port import HublaPurchase, RefundResult, HublaPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort
from nexoia.domain.ports.legal_history_port import LegalHistoryPort


def test_hubla_purchase_is_frozen():
    p = HublaPurchase(
        id="p1",
        product_name="Curso X",
        created_at=datetime.now(UTC),
        amount=99.0,
        is_duplicate=False,
        is_recurring=False,
        first_charge_at=None,
    )
    assert p.id == "p1"
    assert p.is_recurring is False


def test_refund_result_is_frozen():
    r = RefundResult(success=True, refund_id="ref-1", error=None)
    assert r.success is True


def test_hubla_port_is_protocol():
    # Protocol é runtime_checkable — verifica que a interface foi declarada
    assert hasattr(HublaPort, "get_purchase_by_email")
    assert hasattr(HublaPort, "process_refund")


def test_refund_mutex_port_is_protocol():
    assert hasattr(RefundMutexPort, "acquire")
    assert hasattr(RefundMutexPort, "release")


def test_legal_history_port_is_protocol():
    assert hasattr(LegalHistoryPort, "has_prior_refund_mention")
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/domain/test_refund_ports.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar os ports**

```python
# src/nexoia/domain/ports/hubla_port.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class HublaPurchase:
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


@runtime_checkable
class HublaPort(Protocol):
    async def get_purchase_by_email(self, email: str, account_id: int) -> HublaPurchase | None: ...
    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult: ...
```

```python
# src/nexoia/domain/ports/refund_mutex.py
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RefundMutexPort(Protocol):
    async def acquire(self, account_id: str, contact_id: str, product_id: str) -> bool: ...
    async def release(self, account_id: str, contact_id: str, product_id: str) -> None: ...
```

```python
# src/nexoia/domain/ports/legal_history_port.py
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class LegalHistoryPort(Protocol):
    async def has_prior_refund_mention(
        self,
        *,
        account_id: int,
        contact_id: str,
        purchase_date: datetime,
    ) -> bool: ...
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/domain/test_refund_ports.py -v
```
Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/ports/hubla_port.py \
        src/nexoia/domain/ports/refund_mutex.py \
        src/nexoia/domain/ports/legal_history_port.py \
        tests/unit/domain/test_refund_ports.py
git commit -m "feat: add HublaPort, RefundMutexPort and LegalHistoryPort protocols"
```

---

### Task 3: Infrastructure stubs — HublaClient e RedisRefundMutex

**Files:**
- Create: `src/nexoia/infrastructure/hubla/__init__.py`
- Create: `src/nexoia/infrastructure/hubla/client.py`
- Create: `src/nexoia/infrastructure/redis/refund_mutex.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/infrastructure/test_refund_stubs.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.infrastructure.hubla.client import HublaClient
from nexoia.infrastructure.redis.refund_mutex import RedisRefundMutex


@pytest.mark.asyncio
async def test_hubla_client_get_purchase_raises_not_implemented():
    client = HublaClient()
    with pytest.raises(NotImplementedError):
        await client.get_purchase_by_email("a@b.com", 1)


@pytest.mark.asyncio
async def test_hubla_client_process_refund_raises_not_implemented():
    client = HublaClient()
    with pytest.raises(NotImplementedError):
        await client.process_refund("p1", "nao gostei")


@pytest.mark.asyncio
async def test_redis_refund_mutex_acquire_returns_true_when_key_free():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    mutex = RedisRefundMutex(redis_client=redis, ttl_seconds=3600)
    result = await mutex.acquire("1", "5511999990000", "prod-1")
    assert result is True
    redis.set.assert_called_once_with(
        "refund:mutex:1:5511999990000:prod-1", "1", nx=True, ex=3600
    )


@pytest.mark.asyncio
async def test_redis_refund_mutex_acquire_returns_false_when_key_taken():
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=None)  # SETNX falhou — chave existe
    mutex = RedisRefundMutex(redis_client=redis, ttl_seconds=3600)
    result = await mutex.acquire("1", "5511999990000", "prod-1")
    assert result is False


@pytest.mark.asyncio
async def test_redis_refund_mutex_release_deletes_key():
    redis = AsyncMock()
    mutex = RedisRefundMutex(redis_client=redis, ttl_seconds=3600)
    await mutex.release("1", "5511999990000", "prod-1")
    redis.delete.assert_called_once_with("refund:mutex:1:5511999990000:prod-1")
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/infrastructure/test_refund_stubs.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar HublaClient**

```python
# src/nexoia/infrastructure/hubla/__init__.py
```

```python
# src/nexoia/infrastructure/hubla/client.py
from __future__ import annotations

from nexoia.domain.ports.hubla_port import HublaPurchase, RefundResult


class HublaClient:
    # ⚠️  TODO CQ-R04: implementar get_purchase_by_email — verificar endpoint Hubla
    # ⚠️  TODO CQ-R01: implementar process_refund via API Hubla ou Playwright

    async def get_purchase_by_email(self, email: str, account_id: int) -> HublaPurchase | None:
        raise NotImplementedError("HublaClient.get_purchase_by_email — ver CQ-R04")

    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult:
        raise NotImplementedError("HublaClient.process_refund — ver CQ-R01")
```

- [ ] **Step 4: Implementar RedisRefundMutex**

```python
# src/nexoia/infrastructure/redis/refund_mutex.py
from __future__ import annotations

from redis.asyncio import Redis


class RedisRefundMutex:
    def __init__(self, redis_client: Redis, ttl_seconds: int = 3600) -> None:
        self._redis = redis_client
        self._ttl = ttl_seconds

    def _key(self, account_id: str, contact_id: str, product_id: str) -> str:
        return f"refund:mutex:{account_id}:{contact_id}:{product_id}"

    async def acquire(self, account_id: str, contact_id: str, product_id: str) -> bool:
        key = self._key(account_id, contact_id, product_id)
        result = await self._redis.set(key, "1", nx=True, ex=self._ttl)
        return result is not None

    async def release(self, account_id: str, contact_id: str, product_id: str) -> None:
        key = self._key(account_id, contact_id, product_id)
        await self._redis.delete(key)
```

- [ ] **Step 5: Rodar e verificar que passa**

```
pytest tests/unit/infrastructure/test_refund_stubs.py -v
```
Esperado: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/infrastructure/hubla/ \
        src/nexoia/infrastructure/redis/refund_mutex.py \
        tests/unit/infrastructure/test_refund_stubs.py
git commit -m "feat: add HublaClient stub and RedisRefundMutex"
```

---

### Task 4: DB model — RefundCaseModel em models.py

**Files:**
- Modify: `src/nexoia/infrastructure/db/models.py`
- Test: `tests/unit/infrastructure/db/test_refund_case_model.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/infrastructure/db/test_refund_case_model.py
from nexoia.infrastructure.db.models import RefundCaseModel


def test_refund_case_model_tablename():
    assert RefundCaseModel.__tablename__ == "refund_cases"


def test_refund_case_model_has_required_columns():
    cols = {c.name for c in RefundCaseModel.__table__.columns}
    required = {
        "id", "account_id", "contact_id", "conversation_id",
        "student_email", "status", "offers_made", "offer_accepted",
        "is_duplicate_purchase", "refund_processed_this_turn",
        "created_at", "updated_at",
    }
    assert required.issubset(cols)
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/infrastructure/db/test_refund_case_model.py -v
```
Esperado: `ImportError` ou `AttributeError` — modelo não existe.

- [ ] **Step 3: Adicionar RefundCaseModel ao final de models.py**

Adicionar no final de `src/nexoia/infrastructure/db/models.py` (após `AccessCaseModel`):

```python
class RefundCaseModel(Base):
    __tablename__ = "refund_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False)
    purchase_id: Mapped[str | None] = mapped_column(String, nullable=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    student_email: Mapped[str] = mapped_column(String, nullable=False)
    student_cpf: Mapped[str | None] = mapped_column(String, nullable=True)
    refund_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    days_since_purchase: Mapped[int | None] = mapped_column(Integer, nullable=True)
    within_deadline: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_duplicate_purchase: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    offers_made: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    offer_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    refund_processed_this_turn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="collecting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("NOW()"),
        onupdate=text("NOW()"),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_refund_cases_account_contact", "account_id", "contact_id"),
    )
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/infrastructure/db/test_refund_case_model.py -v
```
Esperado: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/models.py \
        tests/unit/infrastructure/db/test_refund_case_model.py
git commit -m "feat: add RefundCaseModel to db models"
```

---

### Task 5: Repository — RefundCaseRepository

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/refund_case_repo.py`
- Test: `tests/unit/infrastructure/db/test_refund_case_repo.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/infrastructure/db/test_refund_case_repo.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.infrastructure.db.repositories.refund_case_repo import RefundCaseRepository


def _make_model(
    status: str = "collecting",
    purchase_id: str | None = None,
    within_deadline: bool | None = None,
    is_duplicate_purchase: bool = False,
    offers_made: list[str] | None = None,
):
    m = MagicMock()
    m.id = "case-1"
    m.account_id = 1
    m.contact_id = "5511999990000"
    m.conversation_id = "conv-1"
    m.purchase_id = purchase_id
    m.product_name = "Curso X"
    m.student_email = "a@b.com"
    m.student_cpf = None
    m.refund_reason = None
    m.days_since_purchase = None
    m.within_deadline = within_deadline
    m.is_duplicate_purchase = is_duplicate_purchase
    m.offers_made = offers_made or []
    m.offer_accepted = False
    m.refund_processed_this_turn = False
    m.status = status
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


@pytest.mark.asyncio
async def test_save_adds_model_and_flushes():
    session = AsyncMock()
    repo = RefundCaseRepository(session)
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
    )
    await repo.save(case)
    session.add.assert_called_once()
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_persists_fields():
    session = AsyncMock()
    session.get = AsyncMock(return_value=_make_model())
    repo = RefundCaseRepository(session)
    case = RefundCase(
        id="case-1",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
        status=RefundCaseStatus.REFUNDED,
        offers_made=["N1", "N2"],
    )
    await repo.update(case)
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_raises_when_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    repo = RefundCaseRepository(session)
    case = RefundCase(
        id="missing",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
    )
    with pytest.raises(ValueError, match="missing"):
        await repo.update(case)


@pytest.mark.asyncio
async def test_find_by_phone_returns_none_when_not_found():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    repo = RefundCaseRepository(session)
    result = await repo.find_by_phone(account_id=1, phone="5511999990000")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_phone_maps_to_entity():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = _make_model(
        status="in_retention",
        offers_made=["N1"],
        within_deadline=True,
    )
    session.execute = AsyncMock(return_value=execute_result)
    repo = RefundCaseRepository(session)
    result = await repo.find_by_phone(account_id=1, phone="5511999990000")
    assert result is not None
    assert result.status == RefundCaseStatus.IN_RETENTION
    assert result.offers_made == ["N1"]
    assert result.within_deadline is True
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/infrastructure/db/test_refund_case_repo.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar o repositório**

```python
# src/nexoia/infrastructure/db/repositories/refund_case_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.infrastructure.db.models import RefundCaseModel


class RefundCaseRepository:
    # Session lifecycle managed by caller (Unit of Work).
    # flush() sends SQL within current transaction; commit() is caller's responsibility.

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
            is_duplicate_purchase=case.is_duplicate_purchase,
            offers_made=case.offers_made,
            offer_accepted=case.offer_accepted,
            refund_processed_this_turn=case.refund_processed_this_turn,
            status=case.status.value,
        )
        self._session.add(model)
        await self._session.flush()

    async def update(self, case: RefundCase) -> None:
        model = await self._session.get(RefundCaseModel, case.id)
        if model is None:
            raise ValueError(f"RefundCase {case.id} not found")
        model.status = case.status.value
        model.purchase_id = case.purchase_id
        model.product_name = case.product_name
        model.student_cpf = case.student_cpf
        model.refund_reason = case.refund_reason
        model.days_since_purchase = case.days_since_purchase
        model.within_deadline = case.within_deadline
        model.is_duplicate_purchase = case.is_duplicate_purchase
        model.offers_made = case.offers_made
        model.offer_accepted = case.offer_accepted
        model.refund_processed_this_turn = case.refund_processed_this_turn
        await self._session.flush()

    async def find_by_phone(self, *, account_id: int, phone: str) -> RefundCase | None:
        result = await self._session.execute(
            select(RefundCaseModel)
            .where(RefundCaseModel.account_id == account_id)
            .where(RefundCaseModel.contact_id == phone)
            .order_by(RefundCaseModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)

    def _to_entity(self, model: RefundCaseModel) -> RefundCase:
        return RefundCase(
            id=str(model.id),
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            purchase_id=model.purchase_id,
            product_name=model.product_name,
            student_email=model.student_email,
            student_cpf=model.student_cpf,
            refund_reason=model.refund_reason,
            days_since_purchase=model.days_since_purchase,
            within_deadline=model.within_deadline,
            is_duplicate_purchase=model.is_duplicate_purchase,
            offers_made=list(model.offers_made or []),
            offer_accepted=model.offer_accepted,
            refund_processed_this_turn=model.refund_processed_this_turn,
            status=RefundCaseStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/infrastructure/db/test_refund_case_repo.py -v
```
Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/refund_case_repo.py \
        tests/unit/infrastructure/db/test_refund_case_repo.py
git commit -m "feat: add RefundCaseRepository with save/update/find_by_phone"
```

---

### Task 6: Settings + Migration

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Create: migration via `alembic revision --autogenerate`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/config/test_settings_refund.py
from nexoia.config.settings import Settings


def test_refund_deadline_days_default():
    s = Settings(
        database_url="postgresql+asyncpg://x:x@localhost/x",
        redis_url="redis://localhost",
        openai_api_key="sk-x",
        chatnexo_base_url="http://x",
        chatnexo_api_key="x",
        hubla_webhook_secret="x",
        admin_api_key="x",
        meta_api_key="x",
        integration_credentials_key="x" * 32,
    )
    assert s.refund_deadline_days == 7
    assert s.refund_mutex_ttl_seconds == 3600
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/config/test_settings_refund.py -v
```
Esperado: `AttributeError: 'Settings' object has no attribute 'refund_deadline_days'`.

- [ ] **Step 3: Adicionar campos em settings.py**

Adicionar após o bloco `# Capability Welcome` em `src/nexoia/config/settings.py`:

```python
    # Capability Refund
    refund_deadline_days: int = 7
    refund_mutex_ttl_seconds: int = 3600
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/config/test_settings_refund.py -v
```
Esperado: 1 passed.

- [ ] **Step 5: Gerar a migration**

```bash
cd /home/fabio/www/agente-plug
alembic revision --autogenerate -m "add_refund_cases_table"
```

Isso gera um arquivo em `migrations/versions/XXXX_add_refund_cases_table.py`. Abrir o arquivo gerado e verificar que contém `create_table('refund_cases', ...)` com todas as colunas. Se o autogenerate não detectar (comum quando o banco não está rodando), criar manualmente com o conteúdo abaixo.

**Conteúdo esperado do arquivo de migration** (ajustar `revision` e `down_revision` conforme gerado):

```python
"""add_refund_cases_table

Revision ID: <gerado pelo alembic>
Revises: 995e17c86849
Create Date: 2026-04-24 ...

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = '<gerado>'
down_revision: Union[str, None] = '995e17c86849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'refund_cases',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.String(), nullable=False),
        sa.Column('conversation_id', sa.String(), nullable=False),
        sa.Column('purchase_id', sa.String(), nullable=True),
        sa.Column('product_name', sa.String(), nullable=True),
        sa.Column('student_email', sa.String(), nullable=False),
        sa.Column('student_cpf', sa.String(), nullable=True),
        sa.Column('refund_reason', sa.String(), nullable=True),
        sa.Column('days_since_purchase', sa.Integer(), nullable=True),
        sa.Column('within_deadline', sa.Boolean(), nullable=True),
        sa.Column('is_duplicate_purchase', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('offers_made', JSONB(), nullable=False, server_default='[]'),
        sa.Column('offer_accepted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('refund_processed_this_turn', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='collecting'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_refund_cases_account_contact', 'refund_cases', ['account_id', 'contact_id'])
    op.create_index(op.f('ix_refund_cases_account_id'), 'refund_cases', ['account_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_refund_cases_account_id'), table_name='refund_cases')
    op.drop_index('idx_refund_cases_account_contact', table_name='refund_cases')
    op.drop_table('refund_cases')
```

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/config/settings.py \
        migrations/versions/*add_refund_cases_table.py \
        tests/unit/config/test_settings_refund.py
git commit -m "feat: add refund settings and migration for refund_cases table"
```

---

### Task 7: Use case — VerificarElegibilidadeReembolso

**Files:**
- Create: `src/nexoia/application/use_cases/refund/__init__.py`
- Create: `src/nexoia/application/use_cases/refund/verificar_elegibilidade.py`
- Create: `tests/unit/use_cases/refund/__init__.py`
- Test: `tests/unit/use_cases/refund/test_verificar_elegibilidade.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/use_cases/refund/test_verificar_elegibilidade.py
from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.use_cases.refund.verificar_elegibilidade import (
    VerificarElegibilidadeReembolso,
)
from nexoia.domain.ports.hubla_port import HublaPurchase


def _make_purchase(
    days_ago: int = 3,
    is_duplicate: bool = False,
    is_recurring: bool = False,
    first_charge_at: datetime | None = None,
) -> HublaPurchase:
    created_at = datetime.now(UTC) - timedelta(days=days_ago)
    return HublaPurchase(
        id="purchase-1",
        product_name="Curso Python",
        created_at=created_at,
        amount=199.0,
        is_duplicate=is_duplicate,
        is_recurring=is_recurring,
        first_charge_at=first_charge_at,
    )


def _make_repo():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.mark.asyncio
async def test_eligible_within_deadline():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=3))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "ELEGIVEL" in result
    assert "3" in result  # dias


@pytest.mark.asyncio
async def test_ineligible_outside_deadline():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=10))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "INELEGIVEL" in result
    assert "10" in result or "data_compra" in result


@pytest.mark.asyncio
async def test_purchase_not_found_returns_error():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=None)
    legal = AsyncMock()
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "COMPRA_NAO_ENCONTRADA" in result


@pytest.mark.asyncio
async def test_duplicate_purchase_returns_duplicate_signal():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=2, is_duplicate=True))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    assert "COMPRA_DUPLICADA" in result


@pytest.mark.asyncio
async def test_art49_prior_mention_forces_within_deadline():
    repo = _make_repo()
    hubla = AsyncMock()
    hubla.get_purchase_by_email = AsyncMock(return_value=_make_purchase(days_ago=10))
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=True)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    # Art. 49: solicitação anterior no prazo → elegível mesmo com 10 dias
    assert "ELEGIVEL" in result


@pytest.mark.asyncio
async def test_recurring_purchase_uses_first_charge_date():
    repo = _make_repo()
    hubla = AsyncMock()
    # first_charge_at foi há 3 dias (dentro do prazo), mas created_at foi há 30 dias
    first_charge = datetime.now(UTC) - timedelta(days=3)
    purchase = _make_purchase(days_ago=30, is_recurring=True, first_charge_at=first_charge)
    hubla.get_purchase_by_email = AsyncMock(return_value=purchase)
    legal = AsyncMock()
    legal.has_prior_refund_mention = AsyncMock(return_value=False)
    uc = VerificarElegibilidadeReembolso(repo, hubla, legal)
    result = await uc.execute(1, "5511999990000", "conv-1", "nao gostei", "a@b.com", "123")
    # Deve ser ELEGIVEL porque usa first_charge_at (3 dias atrás), não created_at (30 dias)
    assert "ELEGIVEL" in result
```

- [ ] **Step 2: Criar os `__init__.py` e rodar os testes**

```bash
touch src/nexoia/application/use_cases/refund/__init__.py
touch tests/unit/use_cases/refund/__init__.py
pytest tests/unit/use_cases/refund/test_verificar_elegibilidade.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar o use case**

```python
# src/nexoia/application/use_cases/refund/verificar_elegibilidade.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from nexoia.config.settings import get_settings
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.domain.ports.hubla_port import HublaPort

log = structlog.get_logger(__name__)


class VerificarElegibilidadeReembolso:
    def __init__(
        self,
        refund_repo: Any,
        hubla: HublaPort,
        legal_history: Any,
    ) -> None:
        self._repo = refund_repo
        self._hubla = hubla
        self._legal_history = legal_history

    async def execute(
        self,
        account_id: int,
        phone: str,
        conversation_id: str,
        motivo: str,
        email: str,
        cpf: str,
    ) -> str:
        case = RefundCase(
            account_id=account_id,
            contact_id=phone,
            conversation_id=conversation_id,
            student_email=email,
            student_cpf=cpf,
            refund_reason=motivo,
            status=RefundCaseStatus.CHECKING_DEADLINE,
        )
        await self._repo.save(case)

        # RF-R19: buscar compra antes de qualquer menção a prazo
        purchase = await self._hubla.get_purchase_by_email(email, account_id)
        if purchase is None:
            log.warning("purchase_not_found", email=email, account_id=account_id)
            case.status = RefundCaseStatus.ESCALATED
            await self._repo.update(case)
            return "COMPRA_NAO_ENCONTRADA: Não foi possível localizar compra para este email."

        deadline_days = get_settings().refund_deadline_days
        today = datetime.now(UTC).date()

        # RF-R13: recorrente → usa first_charge_at
        if purchase.is_recurring and purchase.first_charge_at is not None:
            base_date = purchase.first_charge_at.date()
        else:
            base_date = purchase.created_at.date()

        days = (today - base_date).days

        case.purchase_id = purchase.id
        case.product_name = purchase.product_name
        case.days_since_purchase = days

        # RF-R03: Art. 49 — solicitação anterior no prazo
        has_prior = await self._legal_history.has_prior_refund_mention(
            account_id=account_id,
            contact_id=phone,
            purchase_date=purchase.first_charge_at if (purchase.is_recurring and purchase.first_charge_at) else purchase.created_at,
        )

        within = days <= deadline_days or has_prior
        case.within_deadline = within

        # RF-R04: compra duplicada → sinaliza sem retenção
        if purchase.is_duplicate:
            case.is_duplicate_purchase = True
            await self._repo.update(case)
            log.info("duplicate_purchase", case_id=case.id)
            return f"COMPRA_DUPLICADA: case_id={case.id}, product={purchase.product_name}"

        await self._repo.update(case)

        if within:
            log.info("eligible_for_refund", case_id=case.id, days=days)
            return f"ELEGIVEL: case_id={case.id}, dias={days}, produto={purchase.product_name}"

        purchase_date_str = base_date.strftime("%d/%m/%Y")
        log.info("refund_denied_deadline", case_id=case.id, days=days)
        return f"INELEGIVEL: case_id={case.id}, data_compra={purchase_date_str}, dias={days}"
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/use_cases/refund/test_verificar_elegibilidade.py -v
```
Esperado: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/refund/ \
        tests/unit/use_cases/refund/__init__.py \
        tests/unit/use_cases/refund/test_verificar_elegibilidade.py
git commit -m "feat: implement VerificarElegibilidadeReembolso use case (CDC 7-day check)"
```

---

### Task 8: Use case — IniciarRetencao

**Files:**
- Create: `src/nexoia/application/use_cases/refund/iniciar_retencao.py`
- Test: `tests/unit/use_cases/refund/test_iniciar_retencao.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/use_cases/refund/test_iniciar_retencao.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.use_cases.refund.iniciar_retencao import IniciarRetencao
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus


def _make_case(
    offers_made: list[str] | None = None,
    within_deadline: bool | None = True,
    is_duplicate: bool = False,
) -> RefundCase:
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
        within_deadline=within_deadline,
        is_duplicate_purchase=is_duplicate,
    )
    case.offers_made = offers_made or []
    return case


@pytest.mark.asyncio
async def test_offers_n1_when_no_offers_made():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case())
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "OFERTA_N1" in result
    repo.update.assert_called_once()
    # N1 foi adicionado às ofertas feitas
    updated_case = repo.update.call_args[0][0]
    assert "N1" in updated_case.offers_made


@pytest.mark.asyncio
async def test_offers_n2_when_n1_already_made():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1"]))
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "OFERTA_N2" in result
    updated_case = repo.update.call_args[0][0]
    assert "N2" in updated_case.offers_made


@pytest.mark.asyncio
async def test_returns_retention_exhausted_when_both_offers_made():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "RETENCAO_ESGOTADA" in result


@pytest.mark.asyncio
async def test_returns_error_when_case_not_found():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=None)
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result


@pytest.mark.asyncio
async def test_returns_error_when_not_within_deadline():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(within_deadline=False))
    uc = IniciarRetencao(repo)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result


@pytest.mark.asyncio
async def test_status_set_to_in_retention_after_offer():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case())
    uc = IniciarRetencao(repo)
    await uc.execute(1, "5511999990000")
    updated_case = repo.update.call_args[0][0]
    assert updated_case.status == RefundCaseStatus.IN_RETENTION
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/use_cases/refund/test_iniciar_retencao.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar o use case**

```python
# src/nexoia/application/use_cases/refund/iniciar_retencao.py
from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.entities.refund_case import RefundCaseStatus

log = structlog.get_logger(__name__)

# TODO CQ-R02: substituir por ofertas reais por produto (buscar via config ou DB)
_OFFERS: dict[str, str] = {
    "N1": "Oferta N1: acesso por mais 30 dias sem custo adicional.",
    "N2": "Oferta N2: desconto de 50% na próxima renovação.",
}


class IniciarRetencao:
    def __init__(self, refund_repo: Any) -> None:
        self._repo = refund_repo

    async def execute(self, account_id: int, phone: str) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)
        if case is None:
            return "ERRO: Caso de reembolso não encontrado."

        if case.within_deadline is False:
            return "ERRO: Aluno fora do prazo CDC — não iniciar retenção."

        offers_made = list(case.offers_made)

        if "N1" not in offers_made:
            offers_made.append("N1")
            case.offers_made = offers_made
            case.status = RefundCaseStatus.IN_RETENTION
            await self._repo.update(case)
            log.info("retention_offer", offer="N1", case_id=case.id)
            return f"OFERTA_N1: {_OFFERS['N1']}"

        if "N2" not in offers_made:
            offers_made.append("N2")
            case.offers_made = offers_made
            case.status = RefundCaseStatus.IN_RETENTION
            await self._repo.update(case)
            log.info("retention_offer", offer="N2", case_id=case.id)
            return f"OFERTA_N2: {_OFFERS['N2']}"

        log.info("retention_exhausted", case_id=case.id)
        return "RETENCAO_ESGOTADA: N1 e N2 já oferecidos. Processar reembolso."
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/use_cases/refund/test_iniciar_retencao.py -v
```
Esperado: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/refund/iniciar_retencao.py \
        tests/unit/use_cases/refund/test_iniciar_retencao.py
git commit -m "feat: implement IniciarRetencao use case (N1→N2 retention flow)"
```

---

### Task 9: Use case — ProcessarReembolso

**Files:**
- Create: `src/nexoia/application/use_cases/refund/processar_reembolso.py`
- Test: `tests/unit/use_cases/refund/test_processar_reembolso.py`

- [ ] **Step 1: Escrever os testes que falham**

```python
# tests/unit/use_cases/refund/test_processar_reembolso.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock
from nexoia.application.use_cases.refund.processar_reembolso import ProcessarReembolso
from nexoia.domain.entities.refund_case import RefundCase, RefundCaseStatus
from nexoia.domain.ports.hubla_port import RefundResult

_REFUND_MSG_FRAGMENT = "processando seu reembolso"


def _make_case(
    offers_made: list[str] | None = None,
    is_duplicate: bool = False,
    purchase_id: str = "purchase-1",
) -> RefundCase:
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="a@b.com",
        purchase_id=purchase_id,
        within_deadline=True,
        is_duplicate_purchase=is_duplicate,
    )
    case.offers_made = offers_made or []
    case.refund_reason = "não quero mais"
    return case


@pytest.mark.asyncio
async def test_happy_path_processes_refund():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=True, refund_id="ref-1", error=None))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert _REFUND_MSG_FRAGMENT in result
    repo.update.assert_called_once()
    updated = repo.update.call_args[0][0]
    assert updated.status == RefundCaseStatus.REFUNDED


@pytest.mark.asyncio
async def test_mandatory_retention_invariant_blocks_without_n2():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1"]))
    hubla = AsyncMock()
    mutex = AsyncMock()
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result
    assert "N2" in result
    hubla.process_refund.assert_not_called()


@pytest.mark.asyncio
async def test_mandatory_retention_not_triggered_for_duplicate():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=[], is_duplicate=True))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=True, refund_id="ref-2", error=None))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert _REFUND_MSG_FRAGMENT in result


@pytest.mark.asyncio
async def test_mutex_blocks_duplicate_job():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=False)  # já bloqueado
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result
    assert "processamento" in result.lower() or "duplicado" in result.lower() or "mutex" in result.lower()
    hubla.process_refund.assert_not_called()


@pytest.mark.asyncio
async def test_returns_error_when_case_not_found():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=None)
    uc = ProcessarReembolso(AsyncMock(), AsyncMock(), AsyncMock())
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result


@pytest.mark.asyncio
async def test_sets_refund_processed_this_turn_flag():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=True, refund_id="ref-3", error=None))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    uc = ProcessarReembolso(repo, hubla, mutex)
    await uc.execute(1, "5511999990000")
    updated = repo.update.call_args[0][0]
    assert updated.refund_processed_this_turn is True


@pytest.mark.asyncio
async def test_hubla_failure_releases_mutex_and_returns_error():
    repo = AsyncMock()
    repo.find_by_phone = AsyncMock(return_value=_make_case(offers_made=["N1", "N2"]))
    hubla = AsyncMock()
    hubla.process_refund = AsyncMock(return_value=RefundResult(success=False, refund_id=None, error="timeout"))
    mutex = AsyncMock()
    mutex.acquire = AsyncMock(return_value=True)
    mutex.release = AsyncMock()
    uc = ProcessarReembolso(repo, hubla, mutex)
    result = await uc.execute(1, "5511999990000")
    assert "ERRO" in result
    mutex.release.assert_called_once()
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/use_cases/refund/test_processar_reembolso.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar o use case**

```python
# src/nexoia/application/use_cases/refund/processar_reembolso.py
from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.entities.refund_case import RefundCaseStatus
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort

log = structlog.get_logger(__name__)

_REFUND_MESSAGE = (
    "Tô processando seu reembolso agora! O prazo de estorno de pix é até 72 horas e "
    "cartão de 1 a 2 faturas, ambos dependem da sua operadora. "
    "Você vai receber a confirmação assim que o processamento terminar, tá?"
)


class ProcessarReembolso:
    def __init__(
        self,
        refund_repo: Any,
        hubla: HublaPort,
        refund_mutex: RefundMutexPort,
    ) -> None:
        self._repo = refund_repo
        self._hubla = hubla
        self._mutex = refund_mutex

    async def execute(self, account_id: int, phone: str) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)
        if case is None:
            return "ERRO: Caso de reembolso não encontrado."

        if case.purchase_id is None:
            return "ERRO: ID de compra não disponível — execute verificar_elegibilidade primeiro."

        # Invariante 3 (MandatoryRetention): bypassa se compra duplicada
        if not case.is_duplicate_purchase:
            if "N2" not in case.offers_made:
                log.warning("mandatory_retention_violated", case_id=case.id, offers=case.offers_made)
                return "ERRO: Retenção obrigatória — N2 não foi oferecido ainda. Chame oferecer_retencao."

        # Guard Redis: evita processamento duplicado (TTL 1h)
        acquired = await self._mutex.acquire(str(account_id), phone, case.purchase_id)
        if not acquired:
            log.warning("refund_mutex_blocked", case_id=case.id)
            return "ERRO: Reembolso já em processamento para esta compra. Aguarde."

        result = await self._hubla.process_refund(case.purchase_id, case.refund_reason or "")
        if not result.success:
            await self._mutex.release(str(account_id), phone, case.purchase_id)
            log.error("refund_failed", case_id=case.id, error=result.error)
            return f"ERRO: Falha ao processar reembolso — {result.error}"

        case.status = RefundCaseStatus.REFUNDED
        case.refund_processed_this_turn = True
        await self._repo.update(case)
        log.info("refund_processed", case_id=case.id, refund_id=result.refund_id)
        return _REFUND_MESSAGE
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/use_cases/refund/test_processar_reembolso.py -v
```
Esperado: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/refund/processar_reembolso.py \
        tests/unit/use_cases/refund/test_processar_reembolso.py
git commit -m "feat: implement ProcessarReembolso use case (mutex, mandatory retention, CDC)"
```

---

### Task 10: Skills factory — make_refund_skills()

**Files:**
- Create: `src/nexoia/infrastructure/skills/refund.py`
- Test: `tests/unit/infrastructure/skills/test_refund_skills.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/infrastructure/skills/test_refund_skills.py
from unittest.mock import AsyncMock
from nexoia.infrastructure.skills.refund import make_refund_skills


def test_make_refund_skills_returns_three_tools():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    assert len(skills) == 3


def test_make_refund_skills_tool_names():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    names = {s.name for s in skills}
    assert names == {
        "verificar_elegibilidade_reembolso",
        "oferecer_retencao",
        "processar_reembolso",
    }
```

- [ ] **Step 2: Rodar e verificar que falha**

```
pytest tests/unit/infrastructure/skills/test_refund_skills.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar a factory**

```python
# src/nexoia/infrastructure/skills/refund.py
from __future__ import annotations

from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config

from nexoia.application.use_cases.refund.iniciar_retencao import IniciarRetencao
from nexoia.application.use_cases.refund.processar_reembolso import ProcessarReembolso
from nexoia.application.use_cases.refund.verificar_elegibilidade import VerificarElegibilidadeReembolso
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.domain.ports.legal_history_port import LegalHistoryPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort


def make_refund_skills(
    refund_repo: object,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
) -> list[BaseTool]:
    verificar_uc  = VerificarElegibilidadeReembolso(refund_repo, hubla, legal_history)
    reter_uc      = IniciarRetencao(refund_repo)
    processar_uc  = ProcessarReembolso(refund_repo, hubla, refund_mutex)

    @tool
    async def verificar_elegibilidade_reembolso(motivo: str, email: str, cpf: str) -> str:
        """
        Verifica elegibilidade do aluno para reembolso (CDC 7 dias).
        Use quando: aluno solicita reembolso e forneceu motivo + email + CPF.
        Não use quando: dados incompletos — colete-os conversacionalmente antes.
        Retorna: ELEGIVEL / INELEGIVEL com data / COMPRA_DUPLICADA.
        """
        cfg = get_config()["configurable"]
        return await verificar_uc.execute(
            cfg["account_id"], cfg["phone"], cfg.get("conversation_id", ""), motivo, email, cpf
        )

    @tool
    async def oferecer_retencao() -> str:
        """
        Oferece retenção N1 ou N2 ao aluno elegível para reembolso.
        Use quando: aluno é elegível (dentro do prazo, não duplicada) e ainda não recusou N2.
        Não use quando: compra duplicada, N2 já recusado, ou aluno fora do prazo.
        Retorna: texto da oferta N1/N2 ou RETENCAO_ESGOTADA.
        """
        cfg = get_config()["configurable"]
        return await reter_uc.execute(cfg["account_id"], cfg["phone"])

    @tool
    async def processar_reembolso() -> str:
        """
        Processa o reembolso após dupla recusa de retenção ou compra duplicada.
        Use quando: aluno recusou N1 e N2, OU compra duplicada confirmada.
        Não use quando: N2 ainda não foi oferecido — invariante bloqueará e retornará erro.
        Retorna: mensagem padrão de processamento (PRD 7.3).
        """
        cfg = get_config()["configurable"]
        return await processar_uc.execute(cfg["account_id"], cfg["phone"])

    return [verificar_elegibilidade_reembolso, oferecer_retencao, processar_reembolso]
```

- [ ] **Step 4: Rodar e verificar que passa**

```
pytest tests/unit/infrastructure/skills/test_refund_skills.py -v
```
Esperado: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/skills/refund.py \
        tests/unit/infrastructure/skills/test_refund_skills.py
git commit -m "feat: add make_refund_skills factory with 3 LangChain tools"
```

---

### Task 11: Wire refund skills into graph_builder.py

**Files:**
- Modify: `src/nexoia/infrastructure/langgraph_runtime/graph_builder.py`
- Test: `tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py`

- [ ] **Step 1: Ler o arquivo de testes existente e verificar o que já existe**

```bash
cat tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py
```

- [ ] **Step 2: Adicionar um teste para os novos parâmetros**

No arquivo `tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py`, adicionar ao final (sem remover os testes existentes):

```python
# Adicionar ao final de tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py
from unittest.mock import AsyncMock


def test_build_graph_accepts_refund_params():
    """build_graph deve aceitar refund_repo, hubla, legal_history, refund_mutex."""
    from nexoia.infrastructure.langgraph_runtime.graph_builder import build_graph
    # Se o parâmetro não existir, TypeError é levantado aqui
    graph = build_graph(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
        guard_service=AsyncMock(),
        long_term_repo=AsyncMock(),
        llm=AsyncMock(),
        capability_repo=AsyncMock(),
        memory_extractor=AsyncMock(),
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
        checkpointer=None,
    )
    assert graph is not None
```

- [ ] **Step 3: Rodar e verificar que falha**

```
pytest tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py::test_build_graph_accepts_refund_params -v
```
Esperado: `TypeError: build_graph() got an unexpected keyword argument 'refund_repo'`.

- [ ] **Step 4: Modificar graph_builder.py**

```python
# src/nexoia/infrastructure/langgraph_runtime/graph_builder.py
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.domain.ports.legal_history_port import LegalHistoryPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort
from nexoia.infrastructure.langgraph_runtime.nodes import (
    _roteador,
    make_pos_execucao_node,
    make_raciocinar_node,
)
from nexoia.infrastructure.langgraph_runtime.state import AgentState
from nexoia.infrastructure.skills.access import make_access_skills
from nexoia.infrastructure.skills.core import make_core_skills
from nexoia.infrastructure.skills.refund import make_refund_skills


def build_graph(
    *,
    access_repo: Any,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
    guard_service: Any,
    long_term_repo: Any,
    llm: Any,
    capability_repo: Any,
    memory_extractor: Any,
    refund_repo: Any,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    skills = (
        make_access_skills(access_repo, cademi, chatnexo)
        + make_refund_skills(refund_repo, hubla, legal_history, refund_mutex)
        + make_core_skills(chatnexo)
    )

    raciocinar_node = make_raciocinar_node(guard_service, long_term_repo, llm)
    pos_execucao_node = make_pos_execucao_node(capability_repo, memory_extractor)

    graph = StateGraph(AgentState)
    graph.add_node("raciocinar", raciocinar_node)
    graph.add_node("executar", ToolNode(skills))
    graph.add_node("pos_execucao", pos_execucao_node)

    graph.set_entry_point("raciocinar")
    graph.add_conditional_edges("raciocinar", _roteador)
    graph.add_edge("executar", "pos_execucao")
    graph.add_edge("pos_execucao", "raciocinar")

    return graph.compile(checkpointer=checkpointer)


# Deprecated alias — kept for backward compatibility during migration
build_main_graph = build_graph
```

- [ ] **Step 5: Rodar todos os testes**

```
pytest tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py -v
```
Esperado: todos os testes existentes continuam passando + novo teste passa.

- [ ] **Step 6: Rodar suite completa para verificar regressões**

```
pytest tests/unit/ -v --tb=short 2>&1 | tail -20
```
Esperado: todos os testes unitários passam (exceto testes que dependem de Docker/testcontainers).

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/infrastructure/langgraph_runtime/graph_builder.py \
        tests/unit/infrastructure/langgraph_runtime/test_graph_builder.py
git commit -m "feat: wire make_refund_skills into build_graph (Capability ④ Refund)"
```

---

## Self-Review checklist

Após escrever o plano, verificar contra a spec:

| Req | Task | Status |
|-----|------|--------|
| RF-R01: LLM coleta motivo+email+CPF antes de invocar skill | Skills docstring + `verificar_elegibilidade_reembolso` recebe esses params | ✅ |
| RF-R02: CDC 7 dias | Task 7 `VerificarElegibilidadeReembolso` | ✅ |
| RF-R03: Art. 49 — solicitação anterior | Task 7 `has_prior_refund_mention` | ✅ |
| RF-R04: Compra duplicada → sem retenção | Tasks 7+9 `is_duplicate_purchase` | ✅ |
| RF-R05: Retenção máx 2 ofertas, sem repetição | Task 8 `IniciarRetencao` | ✅ |
| RF-R06: Ofertas N1/N2 por produto | Task 8 stub com TODO CQ-R02 | ✅ |
| RF-R08: Mensagem padrão após recusa dupla | Task 9 `_REFUND_MESSAGE` | ✅ |
| RF-R11: process_refund stub | Task 3 HublaClient | ✅ |
| RF-R12: Mutex Redis TTL 1h | Task 3 RedisRefundMutex | ✅ |
| RF-R13: Recorrente usa first_charge_at | Task 7 branch `is_recurring` | ✅ |
| RF-R15: ExplicitRefundRequest Guard | Responsabilidade do LLM + docstring | ✅ |
| RF-R17: MandatoryRetention | Task 9 invariante | ✅ |
| RF-R18: SameTurnBlock | Task 9 `refund_processed_this_turn=True` | ✅ |
| RF-R19: Nunca falar de prazo sem buscar compra | Task 7 busca Hubla antes de tudo | ✅ |
| RNF-R01: Tenant isolation | Todas queries filtram por `account_id` | ✅ |
| RNF-R04: Cobertura ≥90% | 7+6+7=20 testes unitários cobrindo use cases | ✅ |
