# Capability ⑤ Loja Express — Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a fully proactive, worker-driven Loja Express capability that monitors store delivery after a product purchase, sends timed follow-up messages at D+1, D+3, D+5, and D+7, escalates to human on D+5 and D+7 if delivery is blocked, and marks cases as delivered when confirmed.

**Architecture:** No `@tool` skills, no LLM orchestration. Worker jobs call use cases directly. State persists in `loja_express_cases` DB table. `PurchaseHandler` detects loja express products by tag and routes to `CriarCasoLojaExpress` instead of the normal welcome flow.

**Tech Stack:** Python 3.11, SQLAlchemy 2 async ORM, Alembic, pytest-asyncio + AsyncMock, Redis queue worker, PostgreSQL.

---

## Task 1 — `LojaExpressCaseStatus` enum + `LojaExpressCase` entity + unit test

### Overview
Create the domain entity and status enum for the Loja Express capability. The entity stores all follow-up scheduling state and tracks whether the loja has been delivered or the form submitted.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/domain/test_loja_express_case.py`:

```python
# tests/unit/domain/test_loja_express_case.py
from __future__ import annotations

import pytest
from datetime import UTC, datetime

from nexoia.domain.entities.loja_express_case import (
    LojaExpressCase,
    LojaExpressCaseStatus,
)


def test_status_values_are_lowercase_strings():
    assert LojaExpressCaseStatus.AGUARDANDO_FORMULARIO == "aguardando_formulario"
    assert LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO == "lembrete_d1_enviado"
    assert LojaExpressCaseStatus.CHECK_D3_ENVIADO == "check_d3_enviado"
    assert LojaExpressCaseStatus.ALERTA_D5_ENVIADO == "alerta_d5_enviado"
    assert LojaExpressCaseStatus.PRAZO_CRITICO_D7 == "prazo_critico_d7"
    assert LojaExpressCaseStatus.ENTREGUE == "entregue"
    assert LojaExpressCaseStatus.ESCALADO == "escalado"


def test_loja_express_case_defaults():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
    )
    assert case.account_id == 1
    assert case.contact_id == "5511999990000"
    assert case.conversation_id == "conv-1"
    assert case.purchase_id == "purchase-abc"
    assert case.product_name == "Loja Express Pack"
    assert case.student_email == "aluno@test.com"
    assert case.form_submitted is False
    assert case.loja_entregue is False
    assert case.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert case.scheduled_job_d1_id is None
    assert case.scheduled_job_d3_id is None
    assert case.scheduled_job_d5_id is None
    assert case.scheduled_job_d7_id is None
    assert isinstance(case.id, str)
    assert len(case.id) == 36  # UUID format
    assert isinstance(case.created_at, datetime)
    assert isinstance(case.updated_at, datetime)


def test_loja_express_case_id_is_unique_per_instance():
    case1 = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-1",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    case2 = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-2",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    assert case1.id != case2.id


def test_loja_express_case_explicit_id_is_preserved():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express",
        student_email="a@b.com",
        id="my-fixed-id",
    )
    assert case.id == "my-fixed-id"


def test_loja_express_case_status_can_be_changed():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    case.status = LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
    assert case.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO


def test_loja_express_case_job_ids_can_be_set():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    case.scheduled_job_d1_id = "job-d1-id"
    case.scheduled_job_d3_id = "job-d3-id"
    case.scheduled_job_d5_id = "job-d5-id"
    case.scheduled_job_d7_id = "job-d7-id"
    assert case.scheduled_job_d1_id == "job-d1-id"
    assert case.scheduled_job_d3_id == "job-d3-id"
    assert case.scheduled_job_d5_id == "job-d5-id"
    assert case.scheduled_job_d7_id == "job-d7-id"
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/domain/test_loja_express_case.py -v
```

Expected: `ModuleNotFoundError` — entity does not exist yet.

- [ ] **Step 3 — Implement the entity**

Create `src/nexoia/domain/entities/loja_express_case.py`:

```python
# src/nexoia/domain/entities/loja_express_case.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class LojaExpressCaseStatus(StrEnum):
    AGUARDANDO_FORMULARIO = "aguardando_formulario"
    LEMBRETE_D1_ENVIADO   = "lembrete_d1_enviado"
    CHECK_D3_ENVIADO      = "check_d3_enviado"
    ALERTA_D5_ENVIADO     = "alerta_d5_enviado"
    PRAZO_CRITICO_D7      = "prazo_critico_d7"
    ENTREGUE              = "entregue"
    ESCALADO              = "escalado"


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
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/domain/test_loja_express_case.py -v
```

Expected: 6 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/domain/entities/loja_express_case.py tests/unit/domain/test_loja_express_case.py
git commit -m "feat(loja-express): add LojaExpressCase entity and LojaExpressCaseStatus enum"
```

---

## Task 2 — `LojaExpressPort` protocol + `LojaExpressClient` stub + unit test

### Overview
Define the port protocol that external loja integrations must satisfy. Implement a stub client that raises `NotImplementedError` for all methods (the real adapter will be implemented in a future sprint). Tests verify the protocol shape and that the stub raises as expected.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/domain/test_loja_express_port.py`:

```python
# tests/unit/domain/test_loja_express_port.py
from __future__ import annotations

import pytest

from nexoia.domain.ports.loja_express_port import LojaExpressPort
from nexoia.infrastructure.loja_express.stub_client import LojaExpressStubClient


def test_loja_express_port_is_protocol():
    """LojaExpressPort must be a Protocol (runtime_checkable)."""
    from typing import runtime_checkable, Protocol
    import inspect
    assert issubclass(LojaExpressPort, Protocol)


def test_stub_satisfies_protocol():
    """LojaExpressStubClient must satisfy the LojaExpressPort protocol."""
    stub = LojaExpressStubClient()
    assert isinstance(stub, LojaExpressPort)


@pytest.mark.asyncio
async def test_stub_is_form_submitted_raises():
    stub = LojaExpressStubClient()
    with pytest.raises(NotImplementedError):
        await stub.is_form_submitted("case-1")


@pytest.mark.asyncio
async def test_stub_get_store_status_raises():
    stub = LojaExpressStubClient()
    with pytest.raises(NotImplementedError):
        await stub.get_store_status("case-1")
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/domain/test_loja_express_port.py -v
```

Expected: `ModuleNotFoundError` — port and stub do not exist yet.

- [ ] **Step 3 — Implement the port and stub**

Create `src/nexoia/domain/ports/loja_express_port.py`:

```python
# src/nexoia/domain/ports/loja_express_port.py
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LojaExpressPort(Protocol):
    async def is_form_submitted(self, case_id: str) -> bool:
        """Return True if the student submitted the enrollment form."""
        ...

    async def get_store_status(self, case_id: str) -> str:
        """Return delivery status: 'delivered' | 'pending' | 'processing'."""
        ...
```

Create `src/nexoia/infrastructure/loja_express/__init__.py` (empty):

```python
```

Create `src/nexoia/infrastructure/loja_express/stub_client.py`:

```python
# src/nexoia/infrastructure/loja_express/stub_client.py
from __future__ import annotations


class LojaExpressStubClient:
    """Stub implementation — raises NotImplementedError until real adapter is built."""

    async def is_form_submitted(self, case_id: str) -> bool:
        raise NotImplementedError(
            "LojaExpressStubClient.is_form_submitted: real adapter not implemented yet"
        )

    async def get_store_status(self, case_id: str) -> str:
        raise NotImplementedError(
            "LojaExpressStubClient.get_store_status: real adapter not implemented yet"
        )
```

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/domain/test_loja_express_port.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/domain/ports/loja_express_port.py src/nexoia/infrastructure/loja_express/__init__.py src/nexoia/infrastructure/loja_express/stub_client.py tests/unit/domain/test_loja_express_port.py
git commit -m "feat(loja-express): add LojaExpressPort protocol and LojaExpressStubClient"
```

---

## Task 3 — `LojaExpressCaseModel` in `models.py` + Alembic migration

### Overview
Add the `loja_express_cases` SQLAlchemy model to `models.py` and generate the corresponding Alembic migration. The `purchase_id` column has a UNIQUE constraint for idempotency. All job ID columns are nullable strings.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/infrastructure/db/test_loja_express_case_model.py`:

```python
# tests/unit/infrastructure/db/test_loja_express_case_model.py
from nexoia.infrastructure.db.models import LojaExpressCaseModel


def test_loja_express_case_model_tablename():
    assert LojaExpressCaseModel.__tablename__ == "loja_express_cases"


def test_loja_express_case_model_has_required_columns():
    cols = {c.name for c in LojaExpressCaseModel.__table__.columns}
    required = {
        "id", "account_id", "contact_id", "conversation_id",
        "purchase_id", "product_name", "student_email",
        "form_submitted", "loja_entregue", "status",
        "scheduled_job_d1_id", "scheduled_job_d3_id",
        "scheduled_job_d5_id", "scheduled_job_d7_id",
        "created_at", "updated_at",
    }
    assert required.issubset(cols)


def test_purchase_id_has_unique_constraint():
    unique_cols = set()
    for c in LojaExpressCaseModel.__table__.columns:
        if c.name == "purchase_id" and c.unique:
            unique_cols.add(c.name)
    assert "purchase_id" in unique_cols


def test_account_id_is_indexed():
    indexed_cols = {
        c.name
        for c in LojaExpressCaseModel.__table__.columns
        if c.index
    }
    assert "account_id" in indexed_cols
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/infrastructure/db/test_loja_express_case_model.py -v
```

Expected: `ImportError` — `LojaExpressCaseModel` does not exist yet.

- [ ] **Step 3 — Add the model to `models.py`**

Append to `src/nexoia/infrastructure/db/models.py` (after `RefundCaseModel`):

```python
class LojaExpressCaseModel(Base):
    __tablename__ = "loja_express_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    contact_id: Mapped[str] = mapped_column(String, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String, nullable=False)
    purchase_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    product_name: Mapped[str] = mapped_column(String, nullable=False)
    student_email: Mapped[str] = mapped_column(String, nullable=False)
    form_submitted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    loja_entregue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="aguardando_formulario")
    scheduled_job_d1_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_job_d3_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_job_d5_id: Mapped[str | None] = mapped_column(String, nullable=True)
    scheduled_job_d7_id: Mapped[str | None] = mapped_column(String, nullable=True)
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
        Index("idx_loja_express_cases_account_contact", "account_id", "contact_id"),
    )
```

Then generate the Alembic migration. Create `alembic/versions/<new_hash>_add_loja_express_cases_table.py` with content:

```python
"""add loja_express_cases table

Revision ID: <generate_with_alembic>
Revises: 50d62657fc63
Create Date: 2026-04-25 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "<generate_with_alembic>"
down_revision = "50d62657fc63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loja_express_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("contact_id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("purchase_id", sa.String(), nullable=False, unique=True),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("student_email", sa.String(), nullable=False),
        sa.Column("form_submitted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("loja_entregue", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(40), nullable=False, server_default="aguardando_formulario"),
        sa.Column("scheduled_job_d1_id", sa.String(), nullable=True),
        sa.Column("scheduled_job_d3_id", sa.String(), nullable=True),
        sa.Column("scheduled_job_d5_id", sa.String(), nullable=True),
        sa.Column("scheduled_job_d7_id", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_loja_express_cases_account_contact",
        "loja_express_cases",
        ["account_id", "contact_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_loja_express_cases_account_contact", table_name="loja_express_cases")
    op.drop_table("loja_express_cases")
```

> **Note:** Run `uv run alembic revision --autogenerate -m "add loja_express_cases table"` to generate the real file with a proper revision ID, then verify the generated content matches the schema above. Use the autogenerated file, do not use the template above verbatim — only the `upgrade()`/`downgrade()` body should match.

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/infrastructure/db/test_loja_express_case_model.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/infrastructure/db/models.py tests/unit/infrastructure/db/test_loja_express_case_model.py alembic/versions/
git commit -m "feat(loja-express): add LojaExpressCaseModel and migration for loja_express_cases table"
```

---

## Task 4 — `LojaExpressCaseRepository` + unit tests

### Overview
Implement the repository with four methods: `save`, `update`, `find_by_purchase_context`, and `find_by_id`. The `find_by_purchase_context` method returns the most recent case for a given `account_id` + `contact_id` that is not `ENTREGUE`. The `save` method relies on DB unique constraint to enforce idempotency on `purchase_id` — if a duplicate is inserted, the DB raises `IntegrityError` which propagates to the caller.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/infrastructure/db/test_loja_express_case_repo.py`:

```python
# tests/unit/infrastructure/db/test_loja_express_case_repo.py
from __future__ import annotations

import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus
from nexoia.infrastructure.db.repositories.loja_express_case_repo import LojaExpressCaseRepository


def _make_model(
    status: str = "aguardando_formulario",
    loja_entregue: bool = False,
    form_submitted: bool = False,
    scheduled_job_d1_id: str | None = None,
    scheduled_job_d3_id: str | None = None,
    scheduled_job_d5_id: str | None = None,
    scheduled_job_d7_id: str | None = None,
):
    m = MagicMock()
    m.id = "case-le-1"
    m.account_id = 1
    m.contact_id = "5511999990000"
    m.conversation_id = "conv-1"
    m.purchase_id = "purchase-abc"
    m.product_name = "Loja Express Pack"
    m.student_email = "aluno@test.com"
    m.form_submitted = form_submitted
    m.loja_entregue = loja_entregue
    m.status = status
    m.scheduled_job_d1_id = scheduled_job_d1_id
    m.scheduled_job_d3_id = scheduled_job_d3_id
    m.scheduled_job_d5_id = scheduled_job_d5_id
    m.scheduled_job_d7_id = scheduled_job_d7_id
    m.created_at = datetime.now(UTC)
    m.updated_at = datetime.now(UTC)
    return m


@pytest.mark.asyncio
async def test_save_adds_model_and_flushes():
    session = AsyncMock()
    repo = LojaExpressCaseRepository(session)
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
    )
    await repo.save(case)
    session.add.assert_called_once()
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_update_persists_all_fields():
    session = AsyncMock()
    mock_model = _make_model()
    session.get = AsyncMock(return_value=mock_model)
    repo = LojaExpressCaseRepository(session)
    case = LojaExpressCase(
        id="case-le-1",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        status=LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO,
        form_submitted=True,
        loja_entregue=False,
        scheduled_job_d1_id="job-d1",
        scheduled_job_d3_id="job-d3",
        scheduled_job_d5_id="job-d5",
        scheduled_job_d7_id="job-d7",
    )
    await repo.update(case)
    session.flush.assert_called_once()
    assert mock_model.status == "lembrete_d1_enviado"
    assert mock_model.form_submitted is True
    assert mock_model.loja_entregue is False
    assert mock_model.scheduled_job_d1_id == "job-d1"
    assert mock_model.scheduled_job_d3_id == "job-d3"
    assert mock_model.scheduled_job_d5_id == "job-d5"
    assert mock_model.scheduled_job_d7_id == "job-d7"


@pytest.mark.asyncio
async def test_update_raises_when_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    repo = LojaExpressCaseRepository(session)
    case = LojaExpressCase(
        id="missing-id",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
    )
    with pytest.raises(ValueError, match="missing-id"):
        await repo.update(case)


@pytest.mark.asyncio
async def test_find_by_purchase_context_returns_none_when_not_found():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=execute_result)
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_purchase_context(account_id=1, contact_id="5511999990000")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_purchase_context_maps_to_entity():
    session = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = _make_model(
        status="lembrete_d1_enviado",
        scheduled_job_d1_id="job-d1",
    )
    session.execute = AsyncMock(return_value=execute_result)
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_purchase_context(account_id=1, contact_id="5511999990000")
    assert result is not None
    assert result.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
    assert result.scheduled_job_d1_id == "job-d1"
    assert result.account_id == 1
    assert result.purchase_id == "purchase-abc"


@pytest.mark.asyncio
async def test_find_by_id_returns_none_when_not_found():
    session = AsyncMock()
    session.get = AsyncMock(return_value=None)
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_id("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_find_by_id_returns_entity():
    session = AsyncMock()
    session.get = AsyncMock(return_value=_make_model(loja_entregue=True, status="entregue"))
    repo = LojaExpressCaseRepository(session)
    result = await repo.find_by_id("case-le-1")
    assert result is not None
    assert result.loja_entregue is True
    assert result.status == LojaExpressCaseStatus.ENTREGUE
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/infrastructure/db/test_loja_express_case_repo.py -v
```

Expected: `ModuleNotFoundError` — repository does not exist yet.

- [ ] **Step 3 — Implement the repository**

Create `src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py`:

```python
# src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus
from nexoia.infrastructure.db.models import LojaExpressCaseModel


class LojaExpressCaseRepository:
    # Session lifecycle managed by caller (Unit of Work).
    # flush() sends SQL within current transaction; commit() is caller's responsibility.

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
        await self._session.flush()

    async def update(self, case: LojaExpressCase) -> None:
        model = await self._session.get(LojaExpressCaseModel, case.id)
        if model is None:
            raise ValueError(f"LojaExpressCase {case.id} not found")
        model.status = case.status.value
        model.form_submitted = case.form_submitted
        model.loja_entregue = case.loja_entregue
        model.scheduled_job_d1_id = case.scheduled_job_d1_id
        model.scheduled_job_d3_id = case.scheduled_job_d3_id
        model.scheduled_job_d5_id = case.scheduled_job_d5_id
        model.scheduled_job_d7_id = case.scheduled_job_d7_id
        await self._session.flush()

    async def find_by_purchase_context(
        self, account_id: int, contact_id: str
    ) -> LojaExpressCase | None:
        """Return the most recent active (not ENTREGUE) case for account+contact."""
        result = await self._session.execute(
            select(LojaExpressCaseModel)
            .where(LojaExpressCaseModel.account_id == account_id)
            .where(LojaExpressCaseModel.contact_id == contact_id)
            .where(LojaExpressCaseModel.status != LojaExpressCaseStatus.ENTREGUE.value)
            .order_by(LojaExpressCaseModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return None if model is None else self._to_entity(model)

    async def find_by_id(self, case_id: str) -> LojaExpressCase | None:
        model = await self._session.get(LojaExpressCaseModel, case_id)
        return None if model is None else self._to_entity(model)

    def _to_entity(self, model: LojaExpressCaseModel) -> LojaExpressCase:
        return LojaExpressCase(
            id=str(model.id),
            account_id=model.account_id,
            contact_id=model.contact_id,
            conversation_id=model.conversation_id,
            purchase_id=model.purchase_id,
            product_name=model.product_name,
            student_email=model.student_email,
            form_submitted=model.form_submitted,
            loja_entregue=model.loja_entregue,
            status=LojaExpressCaseStatus(model.status),
            scheduled_job_d1_id=model.scheduled_job_d1_id,
            scheduled_job_d3_id=model.scheduled_job_d3_id,
            scheduled_job_d5_id=model.scheduled_job_d5_id,
            scheduled_job_d7_id=model.scheduled_job_d7_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
```

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/infrastructure/db/test_loja_express_case_repo.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/loja_express_case_repo.py tests/unit/infrastructure/db/test_loja_express_case_repo.py
git commit -m "feat(loja-express): add LojaExpressCaseRepository with save, update, find_by_purchase_context, find_by_id"
```

---

## Task 5 — Add 4 `JobType` values + 5 settings + unit tests

### Overview
Extend the `JobType` StrEnum with 4 new loja express job types. Add 5 settings fields to `Settings`. Write separate test files following the existing pattern for settings tests.

### Steps

- [ ] **Step 1 — Write the failing test files**

Create `tests/unit/domain/test_loja_express_job_types.py`:

```python
# tests/unit/domain/test_loja_express_job_types.py
from nexoia.domain.entities.scheduled_job import JobType


def test_loja_express_d1_value():
    assert JobType.LOJA_EXPRESS_D1 == "loja_express_d1"


def test_loja_express_d3_value():
    assert JobType.LOJA_EXPRESS_D3 == "loja_express_d3"


def test_loja_express_d5_value():
    assert JobType.LOJA_EXPRESS_D5 == "loja_express_d5"


def test_loja_express_d7_value():
    assert JobType.LOJA_EXPRESS_D7 == "loja_express_d7"


def test_all_job_types_are_lowercase():
    for jt in JobType:
        assert jt == jt.lower(), f"JobType.{jt.name} value is not lowercase: {jt.value!r}"
```

Create `tests/unit/config/test_settings_loja_express.py`:

```python
# tests/unit/config/test_settings_loja_express.py
from nexoia.config.settings import Settings


def _make_settings(**overrides) -> Settings:
    defaults = dict(
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
    defaults.update(overrides)
    return Settings(**defaults)


def test_loja_express_product_tags_default():
    s = _make_settings()
    assert s.loja_express_product_tags == ["loja_express", "loja-express"]


def test_loja_express_d1_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d1_delay_hours == 24


def test_loja_express_d3_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d3_delay_hours == 72


def test_loja_express_d5_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d5_delay_hours == 120


def test_loja_express_d7_delay_hours_default():
    s = _make_settings()
    assert s.loja_express_d7_delay_hours == 168
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/domain/test_loja_express_job_types.py tests/unit/config/test_settings_loja_express.py -v
```

Expected: `AttributeError` on `JobType.LOJA_EXPRESS_D1` and `AttributeError` on `settings.loja_express_product_tags`.

- [ ] **Step 3 — Implement the changes**

Edit `src/nexoia/domain/entities/scheduled_job.py` — add 4 new values to `JobType`:

```python
class JobType(StrEnum):
    IDLE_PING        = "idle_ping"
    IDLE_CLOSE       = "idle_close"
    FOLLOWUP_D1      = "followup_d1"
    FOLLOWUP_CUSTOM  = "followup_custom"
    LOJA_EXPRESS_D1  = "loja_express_d1"
    LOJA_EXPRESS_D3  = "loja_express_d3"
    LOJA_EXPRESS_D5  = "loja_express_d5"
    LOJA_EXPRESS_D7  = "loja_express_d7"
```

Edit `src/nexoia/config/settings.py` — add 5 settings fields to `Settings` (after `refund_mutex_ttl_seconds`):

```python
    # Capability Loja Express
    loja_express_product_tags: list[str] = ["loja_express", "loja-express"]
    loja_express_d1_delay_hours: int = 24
    loja_express_d3_delay_hours: int = 72
    loja_express_d5_delay_hours: int = 120
    loja_express_d7_delay_hours: int = 168
```

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/domain/test_loja_express_job_types.py tests/unit/config/test_settings_loja_express.py -v
```

Expected: 10 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/domain/entities/scheduled_job.py src/nexoia/config/settings.py tests/unit/domain/test_loja_express_job_types.py tests/unit/config/test_settings_loja_express.py
git commit -m "feat(loja-express): add LOJA_EXPRESS_D{1,3,5,7} JobType values and 5 settings fields"
```

---

## Task 6 — `CriarCasoLojaExpress` use case + 5 tests

### Overview
Implement the use case that creates a `LojaExpressCase`, sends the D+0 template, and schedules 4 follow-up jobs. The repo `save` raises on duplicate `purchase_id` (DB unique constraint propagates as `IntegrityError`). Each `scheduler.create_job` call returns a job ID string; these IDs are stored on the case and persisted via `repo.update`.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/use_cases/loja_express/test_criar_caso.py`:

```python
# tests/unit/use_cases/loja_express/test_criar_caso.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, call

from nexoia.application.use_cases.loja_express.criar_caso import CriarCasoLojaExpress
from nexoia.domain.entities.loja_express_case import LojaExpressCaseStatus


def _make_deps():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.update = AsyncMock()
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    # scheduler.create_job returns distinct job IDs per call
    scheduler.create_job = AsyncMock(
        side_effect=["job-d1", "job-d3", "job-d5", "job-d7"]
    )
    return repo, chatnexo, scheduler


@pytest.mark.asyncio
async def test_creates_case_and_saves_to_repo():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    result = await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    repo.save.assert_called_once()
    saved_case = repo.save.call_args.args[0]
    assert saved_case.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert saved_case.purchase_id == "purchase-abc"
    assert "CASO_CRIADO" in result


@pytest.mark.asyncio
async def test_sends_d0_template_with_correct_variables():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d0"
    assert call_kwargs["variables"]["nome"] == "João Silva"
    assert call_kwargs["variables"]["produto"] == "Loja Express Pack"
    # account_id must be passed as str
    assert call_kwargs["account_id"] == "1"


@pytest.mark.asyncio
async def test_schedules_four_jobs_with_correct_types():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    assert scheduler.create_job.call_count == 4
    job_types_called = [
        c.kwargs["job_type"]
        for c in scheduler.create_job.call_args_list
    ]
    from nexoia.domain.entities.scheduled_job import JobType
    assert JobType.LOJA_EXPRESS_D1 in job_types_called
    assert JobType.LOJA_EXPRESS_D3 in job_types_called
    assert JobType.LOJA_EXPRESS_D5 in job_types_called
    assert JobType.LOJA_EXPRESS_D7 in job_types_called


@pytest.mark.asyncio
async def test_updates_case_with_job_ids_after_scheduling():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    repo.update.assert_called_once()
    updated_case = repo.update.call_args.args[0]
    assert updated_case.scheduled_job_d1_id == "job-d1"
    assert updated_case.scheduled_job_d3_id == "job-d3"
    assert updated_case.scheduled_job_d5_id == "job-d5"
    assert updated_case.scheduled_job_d7_id == "job-d7"


@pytest.mark.asyncio
async def test_result_contains_case_id():
    repo, chatnexo, scheduler = _make_deps()
    uc = CriarCasoLojaExpress(repo=repo, chatnexo=chatnexo, scheduler=scheduler)
    result = await uc.execute(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        contact_name="João Silva",
    )
    assert "case_id=" in result
```

Also create `tests/unit/use_cases/loja_express/__init__.py` (empty).

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/use_cases/loja_express/test_criar_caso.py -v
```

Expected: `ModuleNotFoundError` — use case does not exist yet.

- [ ] **Step 3 — Implement the use case**

Create `src/nexoia/application/use_cases/loja_express/__init__.py` (empty).

Create `src/nexoia/application/use_cases/loja_express/criar_caso.py`:

```python
# src/nexoia/application/use_cases/loja_express/criar_caso.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus
from nexoia.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


class CriarCasoLojaExpress:
    def __init__(self, repo: Any, chatnexo: Any, scheduler: Any) -> None:
        self._repo = repo
        self._chatnexo = chatnexo
        self._scheduler = scheduler

    async def execute(
        self,
        *,
        account_id: int,
        contact_id: str,
        conversation_id: str,
        purchase_id: str,
        product_name: str,
        student_email: str,
        contact_name: str,
    ) -> str:
        account_id_str = str(account_id)
        now = datetime.now(UTC)

        case = LojaExpressCase(
            account_id=account_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            purchase_id=purchase_id,
            product_name=product_name,
            student_email=student_email,
            status=LojaExpressCaseStatus.AGUARDANDO_FORMULARIO,
        )
        await self._repo.save(case)

        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d0",
            variables={"nome": contact_name, "produto": product_name},
        )

        job_d1_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D1,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=24),
        )
        job_d3_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D3,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=72),
        )
        job_d5_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D5,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=120),
        )
        job_d7_id = await self._scheduler.create_job(
            job_type=JobType.LOJA_EXPRESS_D7,
            account_id=account_id_str,
            conversation_id=conversation_id,
            run_at=now + timedelta(hours=168),
        )

        case.scheduled_job_d1_id = str(job_d1_id)
        case.scheduled_job_d3_id = str(job_d3_id)
        case.scheduled_job_d5_id = str(job_d5_id)
        case.scheduled_job_d7_id = str(job_d7_id)
        await self._repo.update(case)

        log.info(
            "loja_express_case_created",
            case_id=case.id,
            account_id=account_id,
            purchase_id=purchase_id,
        )
        return f"CASO_CRIADO: case_id={case.id}"
```

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/use_cases/loja_express/test_criar_caso.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/application/use_cases/loja_express/__init__.py src/nexoia/application/use_cases/loja_express/criar_caso.py tests/unit/use_cases/loja_express/__init__.py tests/unit/use_cases/loja_express/test_criar_caso.py
git commit -m "feat(loja-express): add CriarCasoLojaExpress use case"
```

---

## Task 7 — `EnviarFollowup` use case + 8 tests

### Overview
The `EnviarFollowup` use case drives all timed follow-up logic. It receives `day: int` (1, 3, 5, or 7), finds the case, and dispatches the correct behavior per day. Stub `NotImplementedError` is caught and treated as `False`/`"pending"`. The guard (loja already delivered) cancels all pending jobs and returns early.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/use_cases/loja_express/test_enviar_followup.py`:

```python
# tests/unit/use_cases/loja_express/test_enviar_followup.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from nexoia.application.use_cases.loja_express.enviar_followup import EnviarFollowup
from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus


def _make_case(
    loja_entregue: bool = False,
    status: LojaExpressCaseStatus = LojaExpressCaseStatus.AGUARDANDO_FORMULARIO,
    scheduled_job_d1_id: str | None = "job-d1",
    scheduled_job_d3_id: str | None = "job-d3",
    scheduled_job_d5_id: str | None = "job-d5",
    scheduled_job_d7_id: str | None = "job-d7",
) -> LojaExpressCase:
    return LojaExpressCase(
        id="case-le-1",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        loja_entregue=loja_entregue,
        status=status,
        scheduled_job_d1_id=scheduled_job_d1_id,
        scheduled_job_d3_id=scheduled_job_d3_id,
        scheduled_job_d5_id=scheduled_job_d5_id,
        scheduled_job_d7_id=scheduled_job_d7_id,
    )


def _make_deps(case: LojaExpressCase | None = None):
    repo = AsyncMock()
    repo.find_by_purchase_context = AsyncMock(return_value=case or _make_case())
    repo.update = AsyncMock()
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    loja_express_port = AsyncMock()
    loja_express_port.is_form_submitted = AsyncMock(return_value=False)
    loja_express_port.get_store_status = AsyncMock(return_value="pending")
    return repo, chatnexo, scheduler, loja_express_port


@pytest.mark.asyncio
async def test_guard_returns_ignorado_when_loja_already_delivered():
    case = _make_case(loja_entregue=True)
    repo, chatnexo, scheduler, loja_express_port = _make_deps(case=case)
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert "IGNORADO" in result
    assert "loja já entregue" in result
    chatnexo.send_template.assert_not_called()


@pytest.mark.asyncio
async def test_guard_cancels_pending_jobs_when_loja_delivered():
    case = _make_case(loja_entregue=True)
    repo, chatnexo, scheduler, loja_express_port = _make_deps(case=case)
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert scheduler.cancel_job.call_count == 4
    cancelled = {c.args[0] for c in scheduler.cancel_job.call_args_list}
    assert cancelled == {"job-d1", "job-d3", "job-d5", "job-d7"}


@pytest.mark.asyncio
async def test_d1_sends_lembrete_template_and_updates_status():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d1"
    assert "FOLLOWUP_D1" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO


@pytest.mark.asyncio
async def test_d1_treats_stub_not_implemented_as_false():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    loja_express_port.is_form_submitted = AsyncMock(side_effect=NotImplementedError)
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    # Must not raise; must proceed with followup regardless
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert "FOLLOWUP_D1" in result


@pytest.mark.asyncio
async def test_d3_sends_check_template_and_updates_status():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=3)
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d3"
    assert "FOLLOWUP_D3" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.CHECK_D3_ENVIADO


@pytest.mark.asyncio
async def test_d5_transfers_to_human_when_not_delivered():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    loja_express_port.get_store_status = AsyncMock(return_value="pending")
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=5)
    chatnexo.transfer_to_human.assert_called_once()
    call_kwargs = chatnexo.transfer_to_human.call_args.kwargs
    assert call_kwargs["reason"] == "loja_express_d5_bloqueio"
    assert "ESCALADO" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.ALERTA_D5_ENVIADO


@pytest.mark.asyncio
async def test_d7_sends_template_and_transfers_to_human():
    repo, chatnexo, scheduler, loja_express_port = _make_deps()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=7)
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "loja_express_d7"
    chatnexo.transfer_to_human.assert_called_once()
    transfer_kwargs = chatnexo.transfer_to_human.call_args.kwargs
    assert transfer_kwargs["reason"] == "loja_express_d7_prazo_critico"
    assert "ESCALADO" in result
    updated_case = repo.update.call_args.args[0]
    assert updated_case.status == LojaExpressCaseStatus.PRAZO_CRITICO_D7


@pytest.mark.asyncio
async def test_case_not_found_returns_error():
    repo = AsyncMock()
    repo.find_by_purchase_context = AsyncMock(return_value=None)
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    loja_express_port = AsyncMock()
    uc = EnviarFollowup(repo=repo, chatnexo=chatnexo, scheduler=scheduler, loja_express_port=loja_express_port)
    result = await uc.execute(account_id=1, contact_id="5511999990000", conversation_id="conv-1", day=1)
    assert "ERRO" in result
    chatnexo.send_template.assert_not_called()
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/use_cases/loja_express/test_enviar_followup.py -v
```

Expected: `ModuleNotFoundError` — use case does not exist yet.

- [ ] **Step 3 — Implement the use case**

Create `src/nexoia/application/use_cases/loja_express/enviar_followup.py`:

```python
# src/nexoia/application/use_cases/loja_express/enviar_followup.py
from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.entities.loja_express_case import LojaExpressCaseStatus

log = structlog.get_logger(__name__)


class EnviarFollowup:
    def __init__(
        self,
        repo: Any,
        chatnexo: Any,
        scheduler: Any,
        loja_express_port: Any,
    ) -> None:
        self._repo = repo
        self._chatnexo = chatnexo
        self._scheduler = scheduler
        self._loja_express_port = loja_express_port

    async def execute(
        self,
        *,
        account_id: int,
        contact_id: str,
        conversation_id: str,
        day: int,
    ) -> str:
        account_id_str = str(account_id)

        case = await self._repo.find_by_purchase_context(
            account_id=account_id, contact_id=contact_id
        )
        if case is None:
            log.warning(
                "loja_express_followup_case_not_found",
                account_id=account_id,
                contact_id=contact_id,
                day=day,
            )
            return "ERRO: caso loja express não encontrado"

        # Guard: loja already delivered — cancel all pending jobs
        if case.loja_entregue is True:
            for job_id in [
                case.scheduled_job_d1_id,
                case.scheduled_job_d3_id,
                case.scheduled_job_d5_id,
                case.scheduled_job_d7_id,
            ]:
                if job_id is not None:
                    await self._scheduler.cancel_job(job_id)
            log.info("loja_express_followup_ignored_delivered", case_id=case.id, day=day)
            return "IGNORADO: loja já entregue"

        if day == 1:
            return await self._handle_d1(case, account_id_str, conversation_id)
        elif day == 3:
            return await self._handle_d3(case, account_id_str, conversation_id)
        elif day == 5:
            return await self._handle_d5(case, account_id_str, conversation_id)
        elif day == 7:
            return await self._handle_d7(case, account_id_str, conversation_id)
        else:
            log.warning("loja_express_followup_unknown_day", day=day, case_id=case.id)
            return f"ERRO: dia desconhecido {day}"

    async def _handle_d1(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        try:
            await self._loja_express_port.is_form_submitted(case.id)
        except NotImplementedError:
            pass  # Treat stub as False — send reminder regardless

        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d1",
            variables={"produto": case.product_name},
        )
        case.status = LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
        await self._repo.update(case)
        log.info("loja_express_d1_sent", case_id=case.id)
        return "FOLLOWUP_D1: template enviado"

    async def _handle_d3(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        try:
            await self._loja_express_port.get_store_status(case.id)
        except NotImplementedError:
            pass  # Treat stub as "pending" — send check regardless

        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d3",
            variables={"produto": case.product_name},
        )
        case.status = LojaExpressCaseStatus.CHECK_D3_ENVIADO
        await self._repo.update(case)
        log.info("loja_express_d3_sent", case_id=case.id)
        return "FOLLOWUP_D3: template enviado"

    async def _handle_d5(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        store_status = "pending"
        try:
            store_status = await self._loja_express_port.get_store_status(case.id)
        except NotImplementedError:
            pass  # Treat stub as "pending"

        if store_status != "delivered":
            reason = "loja_express_d5_bloqueio"
            await self._chatnexo.transfer_to_human(
                account_id=account_id_str,
                conversation_id=conversation_id,
                reason=reason,
            )
            case.status = LojaExpressCaseStatus.ALERTA_D5_ENVIADO
            await self._repo.update(case)
            log.info("loja_express_d5_escalated", case_id=case.id, reason=reason)
            return f"ESCALADO: reason={reason}"

        case.status = LojaExpressCaseStatus.ALERTA_D5_ENVIADO
        await self._repo.update(case)
        log.info("loja_express_d5_delivered", case_id=case.id)
        return "FOLLOWUP_D5: loja entregue, nenhuma ação necessária"

    async def _handle_d7(self, case: Any, account_id_str: str, conversation_id: str) -> str:
        await self._chatnexo.send_template(
            account_id=account_id_str,
            conversation_id=conversation_id,
            template_name="loja_express_d7",
            variables={"produto": case.product_name},
        )
        reason = "loja_express_d7_prazo_critico"
        await self._chatnexo.transfer_to_human(
            account_id=account_id_str,
            conversation_id=conversation_id,
            reason=reason,
        )
        case.status = LojaExpressCaseStatus.PRAZO_CRITICO_D7
        await self._repo.update(case)
        log.info("loja_express_d7_escalated", case_id=case.id, reason=reason)
        return f"ESCALADO: reason={reason}"
```

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/use_cases/loja_express/test_enviar_followup.py -v
```

Expected: 8 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/application/use_cases/loja_express/enviar_followup.py tests/unit/use_cases/loja_express/test_enviar_followup.py
git commit -m "feat(loja-express): add EnviarFollowup use case with D1/D3/D5/D7 logic and guard"
```

---

## Task 8 — `MarcarEntregue` use case + 3 tests

### Overview
When the loja confirms delivery, `MarcarEntregue` marks the case as delivered, sets the status to `ENTREGUE`, and cancels all pending scheduled jobs. Returns a summary with case ID and count of jobs cancelled.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/use_cases/loja_express/test_marcar_entregue.py`:

```python
# tests/unit/use_cases/loja_express/test_marcar_entregue.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from nexoia.application.use_cases.loja_express.marcar_entregue import MarcarEntregue
from nexoia.domain.entities.loja_express_case import LojaExpressCase, LojaExpressCaseStatus


def _make_case(
    scheduled_job_d1_id: str | None = "job-d1",
    scheduled_job_d3_id: str | None = "job-d3",
    scheduled_job_d5_id: str | None = None,
    scheduled_job_d7_id: str | None = "job-d7",
) -> LojaExpressCase:
    return LojaExpressCase(
        id="case-le-1",
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
        status=LojaExpressCaseStatus.CHECK_D3_ENVIADO,
        scheduled_job_d1_id=scheduled_job_d1_id,
        scheduled_job_d3_id=scheduled_job_d3_id,
        scheduled_job_d5_id=scheduled_job_d5_id,
        scheduled_job_d7_id=scheduled_job_d7_id,
    )


@pytest.mark.asyncio
async def test_marks_case_as_delivered_and_updates():
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=_make_case())
    repo.update = AsyncMock()
    scheduler = AsyncMock()
    uc = MarcarEntregue(repo=repo, scheduler=scheduler)
    result = await uc.execute(case_id="case-le-1")
    repo.update.assert_called_once()
    updated_case = repo.update.call_args.args[0]
    assert updated_case.loja_entregue is True
    assert updated_case.status == LojaExpressCaseStatus.ENTREGUE
    assert "ENTREGUE" in result
    assert "case-le-1" in result


@pytest.mark.asyncio
async def test_cancels_only_non_none_job_ids():
    # D5 job is None — only d1, d3, d7 should be cancelled (3 jobs)
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(
        return_value=_make_case(
            scheduled_job_d1_id="job-d1",
            scheduled_job_d3_id="job-d3",
            scheduled_job_d5_id=None,
            scheduled_job_d7_id="job-d7",
        )
    )
    repo.update = AsyncMock()
    scheduler = AsyncMock()
    uc = MarcarEntregue(repo=repo, scheduler=scheduler)
    result = await uc.execute(case_id="case-le-1")
    assert scheduler.cancel_job.call_count == 3
    cancelled = {c.args[0] for c in scheduler.cancel_job.call_args_list}
    assert cancelled == {"job-d1", "job-d3", "job-d7"}
    assert "jobs_cancelados=3" in result


@pytest.mark.asyncio
async def test_returns_error_when_case_not_found():
    repo = AsyncMock()
    repo.find_by_id = AsyncMock(return_value=None)
    scheduler = AsyncMock()
    uc = MarcarEntregue(repo=repo, scheduler=scheduler)
    result = await uc.execute(case_id="nonexistent-id")
    assert "ERRO" in result
    repo.update.assert_not_called()
    scheduler.cancel_job.assert_not_called()
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/use_cases/loja_express/test_marcar_entregue.py -v
```

Expected: `ModuleNotFoundError` — use case does not exist yet.

- [ ] **Step 3 — Implement the use case**

Create `src/nexoia/application/use_cases/loja_express/marcar_entregue.py`:

```python
# src/nexoia/application/use_cases/loja_express/marcar_entregue.py
from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.entities.loja_express_case import LojaExpressCaseStatus

log = structlog.get_logger(__name__)


class MarcarEntregue:
    def __init__(self, repo: Any, scheduler: Any) -> None:
        self._repo = repo
        self._scheduler = scheduler

    async def execute(self, *, case_id: str) -> str:
        case = await self._repo.find_by_id(case_id)
        if case is None:
            log.warning("loja_express_marcar_entregue_not_found", case_id=case_id)
            return f"ERRO: caso {case_id} não encontrado"

        case.loja_entregue = True
        case.status = LojaExpressCaseStatus.ENTREGUE

        jobs_cancelados = 0
        for job_id in [
            case.scheduled_job_d1_id,
            case.scheduled_job_d3_id,
            case.scheduled_job_d5_id,
            case.scheduled_job_d7_id,
        ]:
            if job_id is not None:
                await self._scheduler.cancel_job(job_id)
                jobs_cancelados += 1

        await self._repo.update(case)

        log.info(
            "loja_express_marked_delivered",
            case_id=case.id,
            jobs_cancelados=jobs_cancelados,
        )
        return f"ENTREGUE: case_id={case.id}, jobs_cancelados={jobs_cancelados}"
```

- [ ] **Step 4 — Run to confirm passage**

```bash
uv run pytest tests/unit/use_cases/loja_express/test_marcar_entregue.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/application/use_cases/loja_express/marcar_entregue.py tests/unit/use_cases/loja_express/test_marcar_entregue.py
git commit -m "feat(loja-express): add MarcarEntregue use case"
```

---

## Task 9 — Wire `PurchaseHandler` with Loja Express detection + 2 new tests

### Overview
Extend `PurchaseHandler` to accept `loja_express_case_repo`, `loja_express_port`, and `criar_uc` parameters. When `event.product` contains any of the configured loja express tags (case-insensitive), route to `criar_uc.execute(...)` instead of the normal access-case + welcome-template flow. The existing flow remains unchanged for non-loja-express products.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/application/test_purchase_handler_loja_express.py`:

```python
# tests/unit/application/test_purchase_handler_loja_express.py
from __future__ import annotations

import pytest
from datetime import UTC, datetime
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock

from nexoia.application.purchase_handler import PurchaseHandler
from nexoia.domain.events.purchase_received import PurchaseReceived


def _fake_event(product: str = "Loja Express Pack") -> PurchaseReceived:
    return PurchaseReceived(
        purchase_id="p-loja-1",
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        contact_name="Maria Lima",
        contact_email="maria@test.com",
        contact_phone="5511988880000",
        product=product,
        amount_brl=19700,
        occurred_at=datetime.now(UTC),
    )


def _make_loja_handler(criar_uc: AsyncMock) -> PurchaseHandler:
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511988880000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = None
    chatnexo.create_conversation.return_value = "conv-loja"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    return PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
        loja_express_case_repo=AsyncMock(),
        loja_express_port=AsyncMock(),
        criar_uc=criar_uc,
    )


@pytest.mark.asyncio
async def test_loja_express_product_routes_to_criar_uc():
    """When product name contains 'loja_express' tag, criar_uc.execute is called."""
    criar_uc = AsyncMock()
    criar_uc.execute = AsyncMock(return_value="CASO_CRIADO: case_id=abc")
    handler = _make_loja_handler(criar_uc)
    event = _fake_event(product="loja_express Curso Avancado")
    await handler.execute(event)
    criar_uc.execute.assert_called_once()
    call_kwargs = criar_uc.execute.call_args.kwargs
    assert call_kwargs["purchase_id"] == "p-loja-1"
    assert call_kwargs["contact_name"] == "Maria Lima"
    assert call_kwargs["student_email"] == "maria@test.com"


@pytest.mark.asyncio
async def test_non_loja_express_product_uses_normal_welcome_flow():
    """When product has no loja express tag, normal access-case flow runs, criar_uc is NOT called."""
    criar_uc = AsyncMock()
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-2", phone="5511988880000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-existing"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
        loja_express_case_repo=AsyncMock(),
        loja_express_port=AsyncMock(),
        criar_uc=criar_uc,
    )
    event = _fake_event(product="Mentoria de Tráfego")
    await handler.execute(event)
    criar_uc.execute.assert_not_called()
    access_case_repo.save.assert_called_once()
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/application/test_purchase_handler_loja_express.py -v
```

Expected: `TypeError` — `PurchaseHandler.__init__` does not accept the new parameters yet.

- [ ] **Step 3 — Update `PurchaseHandler`**

Edit `src/nexoia/application/purchase_handler.py` to add loja express detection:

```python
# src/nexoia/application/purchase_handler.py
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from nexoia.config.settings import get_settings
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.domain.entities.scheduled_job import JobType
from nexoia.domain.events.purchase_received import PurchaseReceived
from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)


class PurchaseHandler:
    def __init__(
        self,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        access_case_repo: Any,
        scheduler: Any,
        loja_express_case_repo: Any = None,
        loja_express_port: Any = None,
        criar_uc: Any = None,
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler
        self._loja_express_case_repo = loja_express_case_repo
        self._loja_express_port = loja_express_port
        self._criar_uc = criar_uc

    async def execute(self, event: PurchaseReceived) -> None:
        settings = get_settings()
        account_id = str(event.account_id)

        contact = await self._contact_repo.find_or_create(
            account_id=account_id,
            phone=event.contact_phone,
            name=event.contact_name,
            email=event.contact_email,
        )

        conversation_id = await self._chatnexo.get_open_conversation(
            account_id=account_id, contact_phone=contact.phone
        )
        if conversation_id is None:
            conversation_id = await self._chatnexo.create_conversation(
                account_id=account_id, contact_phone=contact.phone
            )

        is_loja_express = any(
            tag in event.product.lower()
            for tag in settings.loja_express_product_tags
        )

        if is_loja_express and self._criar_uc is not None:
            await self._criar_uc.execute(
                account_id=int(event.account_id),
                contact_id=contact.id,
                conversation_id=conversation_id,
                purchase_id=event.purchase_id,
                product_name=event.product,
                student_email=event.contact_email,
                contact_name=event.contact_name,
            )
            log.info(
                "loja_express_purchase_routed",
                account_id=account_id,
                purchase_id=event.purchase_id,
            )
            return

        # Normal welcome flow (Access capability)
        case = AccessCase(
            id=str(uuid4()),
            account_id=account_id,
            contact_id=contact.id,
            conversation_id=conversation_id,
            purchase_id=event.purchase_id,
            product_name=event.product,
            status=AccessCaseStatus.LINK_SENT,
        )
        await self._access_case_repo.save(case)

        await self._chatnexo.send_template(
            account_id=account_id,
            conversation_id=conversation_id,
            template_name="welcome_purchase",
            variables={"nome": event.contact_name, "produto": event.product},
        )

        await self._scheduler.create_job(
            job_type=JobType.FOLLOWUP_D1,
            account_id=account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(hours=24),
        )

        log.info(
            "purchase_handled",
            account_id=account_id,
            purchase_id=event.purchase_id,
            conversation_id=conversation_id,
        )
```

- [ ] **Step 4 — Run to confirm passage (new tests + existing tests)**

```bash
uv run pytest tests/unit/application/test_purchase_handler_loja_express.py tests/unit/application/test_purchase_handler.py -v
```

Expected: all 5 tests pass (2 new + 3 existing).

- [ ] **Step 5 — Commit**

```bash
git add src/nexoia/application/purchase_handler.py tests/unit/application/test_purchase_handler_loja_express.py
git commit -m "feat(loja-express): wire PurchaseHandler to detect loja express products and route to CriarCasoLojaExpress"
```

---

## Task 10 — Wire `handle_scheduled` for new job types + 2 new tests

### Overview
Extend `handle_scheduled` in the worker to handle 4 new `LOJA_EXPRESS_D*` job types by calling `EnviarFollowup` with the appropriate `day` value. A `_get_followup_handler()` function provides the use case instance (DI configured in main.py). Job type strings in payloads are uppercase — follow the same `elif job_type == "LOJA_EXPRESS_D1"` pattern as the existing `"IDLE_PING"` checks, plus a secondary check against the StrEnum value for safety.

### Steps

- [ ] **Step 1 — Write the failing test file**

Create `tests/unit/worker/test_loja_express_scheduled.py`:

```python
# tests/unit/worker/test_loja_express_scheduled.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_scheduled_loja_express_d1_calls_followup_day_1():
    mock_followup = AsyncMock()
    mock_followup.execute = AsyncMock(return_value="FOLLOWUP_D1: template enviado")
    with patch(
        "nexoia.interface.worker.handlers.scheduled._get_followup_handler",
        return_value=mock_followup,
    ):
        from nexoia.interface.worker.handlers import scheduled
        import importlib
        importlib.reload(scheduled)
        with patch(
            "nexoia.interface.worker.handlers.scheduled._get_followup_handler",
            return_value=mock_followup,
        ):
            from nexoia.interface.worker.handlers.scheduled import handle_scheduled
            await handle_scheduled({
                "job_type": "LOJA_EXPRESS_D1",
                "account_id": "1",
                "contact_id": "5511999990000",
                "conversation_id": "conv-1",
            })
    mock_followup.execute.assert_called_once()
    call_kwargs = mock_followup.execute.call_args.kwargs
    assert call_kwargs["day"] == 1


@pytest.mark.asyncio
async def test_handle_scheduled_loja_express_d7_calls_followup_day_7():
    mock_followup = AsyncMock()
    mock_followup.execute = AsyncMock(return_value="ESCALADO: reason=loja_express_d7_prazo_critico")
    with patch(
        "nexoia.interface.worker.handlers.scheduled._get_followup_handler",
        return_value=mock_followup,
    ):
        from nexoia.interface.worker.handlers.scheduled import handle_scheduled
        await handle_scheduled({
            "job_type": "LOJA_EXPRESS_D7",
            "account_id": "1",
            "contact_id": "5511999990000",
            "conversation_id": "conv-1",
        })
    mock_followup.execute.assert_called_once()
    call_kwargs = mock_followup.execute.call_args.kwargs
    assert call_kwargs["day"] == 7
```

- [ ] **Step 2 — Run to confirm failure**

```bash
uv run pytest tests/unit/worker/test_loja_express_scheduled.py -v
```

Expected: `AttributeError` — `_get_followup_handler` does not exist yet; the `LOJA_EXPRESS_D1` branch is not handled.

- [ ] **Step 3 — Update `handle_scheduled`**

Edit `src/nexoia/interface/worker/handlers/scheduled.py`:

```python
# src/nexoia/interface/worker/handlers/scheduled.py
from __future__ import annotations

import structlog

from nexoia.application.lifecycle_handler import LifecycleHandler
from nexoia.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


def _get_lifecycle_handler() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle_handler: configure DI em main.py")


def _get_followup_handler():
    raise NotImplementedError("_get_followup_handler: configure DI em main.py")


async def handle_scheduled(payload: dict) -> None:
    job_type: str = payload["job_type"]
    account_id: str = payload["account_id"]
    phone: str = payload.get("phone", "")
    conversation_id: str = payload["conversation_id"]
    contact_id: str = payload.get("contact_id", phone)

    lifecycle = _get_lifecycle_handler()

    if job_type == "IDLE_PING":
        await lifecycle.send_ping(
            account_id=account_id, phone=phone, conversation_id=conversation_id
        )
    elif job_type == "IDLE_CLOSE":
        await lifecycle.send_close(
            account_id=account_id, phone=phone, conversation_id=conversation_id
        )
    elif job_type in ("LOJA_EXPRESS_D1", str(JobType.LOJA_EXPRESS_D1).upper()):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=1,
        )
    elif job_type in ("LOJA_EXPRESS_D3", str(JobType.LOJA_EXPRESS_D3).upper()):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=3,
        )
    elif job_type in ("LOJA_EXPRESS_D5", str(JobType.LOJA_EXPRESS_D5).upper()):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=5,
        )
    elif job_type in ("LOJA_EXPRESS_D7", str(JobType.LOJA_EXPRESS_D7).upper()):
        followup = _get_followup_handler()
        await followup.execute(
            account_id=int(account_id),
            contact_id=contact_id,
            conversation_id=conversation_id,
            day=7,
        )
    else:
        log.warning("unknown_job_type", job_type=job_type)
```

- [ ] **Step 4 — Run to confirm passage (new tests + existing scheduled test)**

```bash
uv run pytest tests/unit/worker/test_loja_express_scheduled.py tests/unit/worker/test_purchase_handler_wire.py -v
```

Expected: all 4 tests pass (2 new + 2 existing).

- [ ] **Step 5 — Final full run to verify no regressions**

```bash
uv run pytest tests/unit/ -v --tb=short
```

Expected: all unit tests pass with no regressions.

- [ ] **Step 6 — Commit**

```bash
git add src/nexoia/interface/worker/handlers/scheduled.py tests/unit/worker/test_loja_express_scheduled.py
git commit -m "feat(loja-express): wire handle_scheduled for LOJA_EXPRESS_D1/D3/D5/D7 job types"
```

---

## Self-review checklist

### Spec coverage
- [x] `LojaExpressCaseStatus` with all 7 values (Task 1)
- [x] `LojaExpressCase` entity with all fields including 4 job ID fields (Task 1)
- [x] `LojaExpressPort` protocol (`is_form_submitted`, `get_store_status`) (Task 2)
- [x] `LojaExpressStubClient` raises `NotImplementedError` (Task 2)
- [x] `LojaExpressCaseModel` with `purchase_id UNIQUE`, composite index (Task 3)
- [x] Alembic migration `down_revision = '50d62657fc63'` (Task 3)
- [x] Repository: `save` (flush, not commit), `update`, `find_by_purchase_context` (excludes ENTREGUE), `find_by_id` (Task 4)
- [x] 4 `JobType` StrEnum values (`loja_express_d1..d7`) (Task 5)
- [x] 5 settings fields with correct defaults (Task 5)
- [x] `CriarCasoLojaExpress`: creates entity, saves, sends `loja_express_d0`, schedules 4 jobs, updates case with job IDs (Task 6)
- [x] `account_id` converted to `str` for all chatnexo calls (Tasks 6, 7)
- [x] `EnviarFollowup`: guard (loja_entregue → cancel all + return IGNORADO) (Task 7)
- [x] D+1: `is_form_submitted` stub catch, send `loja_express_d1`, status=LEMBRETE_D1_ENVIADO (Task 7)
- [x] D+3: `get_store_status` stub catch, send `loja_express_d3`, status=CHECK_D3_ENVIADO (Task 7)
- [x] D+5: `get_store_status`, if not "delivered" → `transfer_to_human(reason="loja_express_d5_bloqueio")`, status=ALERTA_D5_ENVIADO (Task 7)
- [x] D+7: send `loja_express_d7`, `transfer_to_human(reason="loja_express_d7_prazo_critico")`, status=PRAZO_CRITICO_D7 (Task 7)
- [x] `MarcarEntregue`: `loja_entregue=True`, `status=ENTREGUE`, cancel non-None jobs, count in return string (Task 8)
- [x] `PurchaseHandler` loja express detection by product tag (case-insensitive) (Task 9)
- [x] Existing normal welcome flow untouched when no loja tag (Task 9)
- [x] `handle_scheduled` handles `LOJA_EXPRESS_D{1,3,5,7}` uppercase strings (Task 10)
- [x] `_get_followup_handler()` DI stub follows same pattern as `_get_lifecycle_handler()` (Task 10)

### No placeholders
All code blocks are complete and ready to copy-paste with no "TBD", "similar to above", or "add your logic here" placeholders.

### Type consistency
- `account_id` in domain entities: `int`
- `account_id` passed to `chatnexo.*`: `str(account_id)` — converted at use-case boundary
- `account_id` in `PurchaseHandler`: `event.account_id` is `UUID`; `int(event.account_id)` passed to use case, `str(event.account_id)` used for chatnexo internally
- All repository methods use `flush()` not `commit()`
- `find_by_purchase_context` excludes `ENTREGUE` cases
- `scheduler.create_job(...)` returns job ID string; stored as `str(job_id)` defensively
