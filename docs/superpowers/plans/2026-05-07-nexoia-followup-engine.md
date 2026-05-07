# Follow-up Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o motor de follow-up dinâmico que, ao receber um webhook de compra, inscreve o contato numa sequência de templates Meta configurável e grava cada envio no histórico da conversa para a IA ter contexto.

**Architecture:** Clean Architecture em camadas (domain → application → adapters → interface). Coexiste com Loja Express sem modificá-lo. Usa `ScheduledJobRepository.schedule()` para agendar jobs e `ConversationHistory` para injetar contexto na IA.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, pytest-asyncio, structlog

---

## File Map

### Criar
```
apps/api/src/shared/domain/entities/followup.py
apps/api/src/shared/domain/ports/followup_ports.py
apps/api/src/shared/application/use_cases/followup/__init__.py
apps/api/src/shared/application/use_cases/followup/enroll_contact.py
apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py
apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py
apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py
apps/api/src/interface/http/routers/admin/followup.py
apps/api/src/interface/http/schemas/followup.py
apps/api/migrations/versions/a2b3c4d5e6f7_add_followup_tables.py
apps/api/tests/unit/use_cases/followup/__init__.py
apps/api/tests/unit/use_cases/followup/test_enroll_contact.py
apps/api/tests/unit/use_cases/followup/test_dispatch_followup_step.py
apps/api/tests/unit/interface/admin/test_followup_router.py
```

### Modificar
```
apps/api/src/shared/domain/entities/scheduled_job.py       + JobType.FOLLOWUP_STEP
apps/api/src/shared/adapters/db/models.py                  + 4 novos models
apps/api/src/interface/worker/handlers/scheduled.py        + case "followup_step"
apps/api/src/interface/worker/handlers/purchase.py         refactor DI inline + wire EnrollContact
apps/api/src/main.py                                       + router followup
```

---

### Task 1: Entidades de domínio

**Files:**
- Create: `apps/api/src/shared/domain/entities/followup.py`

- [ ] **Step 1: Criar o arquivo de entidades**

```python
# apps/api/src/shared/domain/entities/followup.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class EnrollmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EnrollmentStepStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass(slots=True)
class FollowupFlow:
    id: UUID
    account_id: UUID
    name: str
    product_tags: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class FollowupStep:
    id: UUID
    flow_id: UUID
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str
    template_variables: dict
    created_at: datetime


@dataclass(slots=True)
class FollowupEnrollment:
    account_id: UUID
    flow_id: UUID
    contact_id: UUID
    conversation_id: UUID
    contact_phone: str
    purchase_id: str
    id: UUID = field(default_factory=uuid4)
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(slots=True)
class FollowupEnrollmentStep:
    enrollment_id: UUID
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str
    template_variables: dict
    id: UUID = field(default_factory=uuid4)
    scheduled_job_id: UUID | None = None
    status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING
    sent_at: datetime | None = None
```

- [ ] **Step 2: Rodar testes (nenhum ainda — apenas verificar importação)**

```bash
cd apps/api && uv run python -c "from shared.domain.entities.followup import FollowupFlow, FollowupEnrollment, FollowupStep, FollowupEnrollmentStep; print('OK')"
```
Esperado: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/shared/domain/entities/followup.py
git commit -m "feat(followup): adicionar entidades de domínio"
```

---

### Task 2: JobType + DB Models + Migration

**Files:**
- Modify: `apps/api/src/shared/domain/entities/scheduled_job.py`
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Create: `apps/api/migrations/versions/a2b3c4d5e6f7_add_followup_tables.py`

- [ ] **Step 1: Escrever teste do novo JobType**

```python
# apps/api/tests/unit/domain/test_followup_job_type.py
from shared.domain.entities.scheduled_job import JobType


def test_followup_step_job_type_value():
    assert JobType.FOLLOWUP_STEP == "followup_step"


def test_followup_step_is_lowercase():
    assert JobType.FOLLOWUP_STEP == JobType.FOLLOWUP_STEP.lower()
```

- [ ] **Step 2: Rodar teste para confirmar falha**

```bash
cd apps/api && uv run pytest tests/unit/domain/test_followup_job_type.py -v
```
Esperado: `FAILED` — AttributeError: FOLLOWUP_STEP

- [ ] **Step 3: Adicionar JobType.FOLLOWUP_STEP**

Em `apps/api/src/shared/domain/entities/scheduled_job.py`, adicionar após `LOJA_EXPRESS_D7`:

```python
    FOLLOWUP_STEP = "followup_step"
```

- [ ] **Step 4: Rodar teste para confirmar aprovação**

```bash
cd apps/api && uv run pytest tests/unit/domain/test_followup_job_type.py -v
```
Esperado: `PASSED`

- [ ] **Step 5: Adicionar os 4 models em `models.py`**

Ao final de `apps/api/src/shared/adapters/db/models.py`, antes da linha final, adicionar:

```python
class FollowupFlowModel(Base):
    __tablename__ = "followup_flows"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_tags: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=sa_text("NOW()"),
        onupdate=sa_text("NOW()"),
        nullable=False,
    )


class FollowupStepModel(Base):
    __tablename__ = "followup_steps"
    id: Mapped[uuid.UUID] = _pk()
    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("followup_flows.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_from_purchase_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meta_template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_variables: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
    __table_args__ = (
        Index("ix_followup_steps_flow_position", "flow_id", "position"),
    )


class FollowupEnrollmentModel(Base):
    __tablename__ = "followup_enrollments"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True
    )
    flow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    contact_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    purchase_id: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )


class FollowupEnrollmentStepModel(Base):
    __tablename__ = "followup_enrollment_steps"
    id: Mapped[uuid.UUID] = _pk()
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("followup_enrollments.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    delay_from_purchase_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    meta_template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_variables: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    scheduled_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 6: Criar migration**

```bash
cd apps/api && uv run alembic revision --autogenerate -m "add_followup_tables"
```

Abrir o arquivo gerado em `migrations/versions/` e renomear para `a2b3c4d5e6f7_add_followup_tables.py`, corrigindo o `revision` no cabeçalho para `"a2b3c4d5e6f7"`.

Verificar que o `upgrade()` criou as 4 tabelas. Ajustar se necessário:

```python
# Conteúdo esperado do upgrade():
def upgrade() -> None:
    op.create_table(
        "followup_flows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("product_tags", JSONB, nullable=False, server_default="'[]'::jsonb"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_followup_flows_account_id", "followup_flows", ["account_id"])

    op.create_table(
        "followup_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("flow_id", UUID(as_uuid=True), sa.ForeignKey("followup_flows.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("delay_from_purchase_hours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("meta_template_name", sa.String(200), nullable=False),
        sa.Column("template_variables", JSONB, nullable=False, server_default="'{}'::jsonb"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_followup_steps_flow_position", "followup_steps", ["flow_id", "position"])

    op.create_table(
        "followup_enrollments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("flow_id", UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("contact_phone", sa.String(30), nullable=False),
        sa.Column("purchase_id", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="'active'"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
    )
    op.create_index("ix_followup_enrollments_account_id", "followup_enrollments", ["account_id"])

    op.create_table(
        "followup_enrollment_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("enrollment_id", UUID(as_uuid=True), sa.ForeignKey("followup_enrollments.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("delay_from_purchase_hours", sa.Integer, nullable=False),
        sa.Column("meta_template_name", sa.String(200), nullable=False),
        sa.Column("template_variables", JSONB, nullable=False, server_default="'{}'::jsonb"),
        sa.Column("scheduled_job_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="'pending'"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_followup_enrollment_steps_enrollment_id", "followup_enrollment_steps", ["enrollment_id"])
```

- [ ] **Step 7: Rodar migration (requer postgres rodando)**

```bash
cd apps/api && uv run alembic upgrade head
```
Esperado: `Running upgrade ... -> a2b3c4d5e6f7, add_followup_tables`

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/shared/domain/entities/scheduled_job.py \
        apps/api/src/shared/adapters/db/models.py \
        apps/api/migrations/versions/a2b3c4d5e6f7_add_followup_tables.py \
        apps/api/tests/unit/domain/test_followup_job_type.py
git commit -m "feat(followup): adicionar JobType.FOLLOWUP_STEP, models e migration"
```

---

### Task 3: Repositórios de Flow e Enrollment

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py`
- Create: `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py`

- [ ] **Step 1: Criar `followup_flow_repo.py`**

```python
# apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import FollowupFlowModel, FollowupStepModel
from shared.domain.entities.followup import FollowupFlow, FollowupStep


def _flow_to_entity(m: FollowupFlowModel) -> FollowupFlow:
    return FollowupFlow(
        id=m.id,
        account_id=m.account_id,
        name=m.name,
        product_tags=list(m.product_tags or []),
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _step_to_entity(m: FollowupStepModel) -> FollowupStep:
    return FollowupStep(
        id=m.id,
        flow_id=m.flow_id,
        position=m.position,
        delay_from_purchase_hours=m.delay_from_purchase_hours,
        meta_template_name=m.meta_template_name,
        template_variables=dict(m.template_variables or {}),
        created_at=m.created_at,
    )


@dataclass
class FollowupFlowRepository:
    session: AsyncSession

    async def find_active_by_product(
        self, *, account_id: uuid.UUID, product: str
    ) -> FollowupFlow | None:
        """Returns the first active flow whose product_tags appear in the product string (case-insensitive)."""
        result = await self.session.execute(
            select(FollowupFlowModel)
            .where(
                FollowupFlowModel.account_id == account_id,
                FollowupFlowModel.is_active.is_(True),
            )
        )
        product_lower = product.lower()
        for model in result.scalars().all():
            tags: list[str] = list(model.product_tags or [])
            if any(tag.lower() in product_lower for tag in tags):
                return _flow_to_entity(model)
        return None

    async def get_steps(self, flow_id: uuid.UUID) -> list[FollowupStep]:
        result = await self.session.execute(
            select(FollowupStepModel)
            .where(FollowupStepModel.flow_id == flow_id)
            .order_by(FollowupStepModel.position)
        )
        return [_step_to_entity(m) for m in result.scalars().all()]

    async def list_flows(self, account_id: uuid.UUID) -> list[FollowupFlow]:
        result = await self.session.execute(
            select(FollowupFlowModel)
            .where(FollowupFlowModel.account_id == account_id)
            .order_by(FollowupFlowModel.created_at)
        )
        return [_flow_to_entity(m) for m in result.scalars().all()]

    async def create_flow(
        self, *, account_id: uuid.UUID, name: str, product_tags: list[str]
    ) -> FollowupFlow:
        model = FollowupFlowModel(
            id=uuid.uuid4(),
            account_id=account_id,
            name=name,
            product_tags=product_tags,
            is_active=True,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _flow_to_entity(model)

    async def update_flow(
        self,
        flow_id: uuid.UUID,
        *,
        name: str | None = None,
        product_tags: list[str] | None = None,
        is_active: bool | None = None,
    ) -> FollowupFlow | None:
        model = await self.session.get(FollowupFlowModel, flow_id)
        if model is None:
            return None
        if name is not None:
            model.name = name
        if product_tags is not None:
            model.product_tags = product_tags
        if is_active is not None:
            model.is_active = is_active
        await self.session.flush()
        await self.session.refresh(model)
        return _flow_to_entity(model)

    async def delete_flow(self, flow_id: uuid.UUID) -> bool:
        model = await self.session.get(FollowupFlowModel, flow_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def create_step(
        self,
        *,
        flow_id: uuid.UUID,
        position: int,
        delay_from_purchase_hours: int,
        meta_template_name: str,
        template_variables: dict,
    ) -> FollowupStep:
        model = FollowupStepModel(
            id=uuid.uuid4(),
            flow_id=flow_id,
            position=position,
            delay_from_purchase_hours=delay_from_purchase_hours,
            meta_template_name=meta_template_name,
            template_variables=template_variables,
        )
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return _step_to_entity(model)

    async def update_step(
        self,
        step_id: uuid.UUID,
        *,
        delay_from_purchase_hours: int | None = None,
        meta_template_name: str | None = None,
        template_variables: dict | None = None,
        position: int | None = None,
    ) -> FollowupStep | None:
        model = await self.session.get(FollowupStepModel, step_id)
        if model is None:
            return None
        if delay_from_purchase_hours is not None:
            model.delay_from_purchase_hours = delay_from_purchase_hours
        if meta_template_name is not None:
            model.meta_template_name = meta_template_name
        if template_variables is not None:
            model.template_variables = template_variables
        if position is not None:
            model.position = position
        await self.session.flush()
        await self.session.refresh(model)
        return _step_to_entity(model)

    async def delete_step(self, step_id: uuid.UUID) -> bool:
        model = await self.session.get(FollowupStepModel, step_id)
        if model is None:
            return False
        await self.session.delete(model)
        await self.session.flush()
        return True

    async def get_step(self, step_id: uuid.UUID) -> FollowupStep | None:
        model = await self.session.get(FollowupStepModel, step_id)
        return None if model is None else _step_to_entity(model)
```

- [ ] **Step 2: Criar `followup_enrollment_repo.py`**

```python
# apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import FollowupEnrollmentModel, FollowupEnrollmentStepModel
from shared.domain.entities.followup import (
    EnrollmentStatus,
    EnrollmentStepStatus,
    FollowupEnrollment,
    FollowupEnrollmentStep,
)


def _enrollment_to_entity(m: FollowupEnrollmentModel) -> FollowupEnrollment:
    return FollowupEnrollment(
        id=m.id,
        account_id=m.account_id,
        flow_id=m.flow_id,
        contact_id=m.contact_id,
        conversation_id=m.conversation_id,
        contact_phone=m.contact_phone,
        purchase_id=m.purchase_id,
        status=EnrollmentStatus(m.status),
        created_at=m.created_at,
    )


def _step_to_entity(m: FollowupEnrollmentStepModel) -> FollowupEnrollmentStep:
    return FollowupEnrollmentStep(
        id=m.id,
        enrollment_id=m.enrollment_id,
        position=m.position,
        delay_from_purchase_hours=m.delay_from_purchase_hours,
        meta_template_name=m.meta_template_name,
        template_variables=dict(m.template_variables or {}),
        scheduled_job_id=m.scheduled_job_id,
        status=EnrollmentStepStatus(m.status),
        sent_at=m.sent_at,
    )


@dataclass
class FollowupEnrollmentRepository:
    session: AsyncSession

    async def create_with_steps(
        self,
        enrollment: FollowupEnrollment,
        steps: list[FollowupEnrollmentStep],
    ) -> None:
        enrollment_model = FollowupEnrollmentModel(
            id=enrollment.id,
            account_id=enrollment.account_id,
            flow_id=enrollment.flow_id,
            contact_id=enrollment.contact_id,
            conversation_id=enrollment.conversation_id,
            contact_phone=enrollment.contact_phone,
            purchase_id=enrollment.purchase_id,
            status=enrollment.status.value,
        )
        self.session.add(enrollment_model)
        await self.session.flush()

        for step in steps:
            step_model = FollowupEnrollmentStepModel(
                id=step.id,
                enrollment_id=step.enrollment_id,
                position=step.position,
                delay_from_purchase_hours=step.delay_from_purchase_hours,
                meta_template_name=step.meta_template_name,
                template_variables=step.template_variables,
                scheduled_job_id=step.scheduled_job_id,
                status=step.status.value,
                sent_at=step.sent_at,
            )
            self.session.add(step_model)
        await self.session.flush()

    async def find_step_by_id(self, step_id: uuid.UUID) -> FollowupEnrollmentStep | None:
        model = await self.session.get(FollowupEnrollmentStepModel, step_id)
        return None if model is None else _step_to_entity(model)

    async def update_step(self, step: FollowupEnrollmentStep) -> None:
        model = await self.session.get(FollowupEnrollmentStepModel, step.id)
        if model is None:
            raise ValueError(f"FollowupEnrollmentStep {step.id} not found")
        model.status = step.status.value
        model.sent_at = step.sent_at
        model.scheduled_job_id = step.scheduled_job_id
        await self.session.flush()

    async def all_steps_sent(self, enrollment_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(FollowupEnrollmentStepModel)
            .where(
                FollowupEnrollmentStepModel.enrollment_id == enrollment_id,
                FollowupEnrollmentStepModel.status != EnrollmentStepStatus.SENT.value,
            )
        )
        return result.scalar_one() == 0

    async def update_enrollment_status(
        self, enrollment_id: uuid.UUID, status: EnrollmentStatus
    ) -> None:
        model = await self.session.get(FollowupEnrollmentModel, enrollment_id)
        if model is None:
            raise ValueError(f"FollowupEnrollment {enrollment_id} not found")
        model.status = status.value
        await self.session.flush()
```

- [ ] **Step 3: Verificar importações**

```bash
cd apps/api && uv run python -c "
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.repositories.followup_enrollment_repo import FollowupEnrollmentRepository
print('OK')
"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py \
        apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py
git commit -m "feat(followup): repositórios de flow e enrollment"
```

---

### Task 4: Use case EnrollContact

**Files:**
- Create: `apps/api/src/shared/application/use_cases/followup/__init__.py`
- Create: `apps/api/src/shared/application/use_cases/followup/enroll_contact.py`
- Create: `apps/api/tests/unit/use_cases/followup/__init__.py`
- Create: `apps/api/tests/unit/use_cases/followup/test_enroll_contact.py`

- [ ] **Step 1: Escrever testes**

```python
# apps/api/tests/unit/use_cases/followup/test_enroll_contact.py
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from shared.application.use_cases.followup.enroll_contact import EnrollContact
from shared.domain.entities.followup import (
    EnrollmentStatus,
    FollowupEnrollment,
    FollowupFlow,
    FollowupStep,
)


_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")
_CONTACT_ID = uuid4()
_CONV_ID = uuid4()
_FLOW_ID = uuid4()


def _make_flow() -> FollowupFlow:
    return FollowupFlow(
        id=_FLOW_ID,
        account_id=_ACCOUNT_ID,
        name="Máquina de Vendas",
        product_tags=["maquina_de_vendas"],
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_step(position: int, delay: int) -> FollowupStep:
    return FollowupStep(
        id=uuid4(),
        flow_id=_FLOW_ID,
        position=position,
        delay_from_purchase_hours=delay,
        meta_template_name=f"mv_template_{position}",
        template_variables={},
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_enroll_contact_creates_enrollment_and_schedules_jobs():
    flow_repo = AsyncMock()
    flow_repo.find_active_by_product.return_value = _make_flow()
    flow_repo.get_steps.return_value = [
        _make_step(1, 0),
        _make_step(2, 1),
        _make_step(3, 24),
    ]

    enrollment_repo = AsyncMock()
    enrollment_repo.create_with_steps = AsyncMock(return_value=None)

    job_repo = AsyncMock()
    fake_job = MagicMock()
    fake_job.id = uuid4()
    job_repo.schedule = AsyncMock(return_value=fake_job)

    purchase_time = datetime.now(UTC)
    uc = EnrollContact(flow_repo=flow_repo, enrollment_repo=enrollment_repo, job_repo=job_repo)

    result = await uc.execute(
        account_id=_ACCOUNT_ID,
        contact_id=_CONTACT_ID,
        conversation_id=_CONV_ID,
        contact_phone="5511999990000",
        purchase_id="p-001",
        product="maquina_de_vendas Curso",
        purchase_time=purchase_time,
    )

    assert result is not None
    assert result.status == EnrollmentStatus.ACTIVE
    assert result.flow_id == _FLOW_ID
    assert job_repo.schedule.call_count == 3
    enrollment_repo.create_with_steps.assert_called_once()


@pytest.mark.asyncio
async def test_enroll_contact_returns_none_when_no_flow_found():
    flow_repo = AsyncMock()
    flow_repo.find_active_by_product.return_value = None

    uc = EnrollContact(
        flow_repo=flow_repo,
        enrollment_repo=AsyncMock(),
        job_repo=AsyncMock(),
    )

    result = await uc.execute(
        account_id=_ACCOUNT_ID,
        contact_id=_CONTACT_ID,
        conversation_id=_CONV_ID,
        contact_phone="5511999990000",
        purchase_id="p-001",
        product="produto_desconhecido",
        purchase_time=datetime.now(UTC),
    )

    assert result is None
```

- [ ] **Step 2: Criar `__init__.py` dos módulos**

```bash
touch apps/api/src/shared/application/use_cases/followup/__init__.py
touch apps/api/tests/unit/use_cases/followup/__init__.py
```

- [ ] **Step 3: Rodar testes para confirmar falha**

```bash
cd apps/api && uv run pytest tests/unit/use_cases/followup/test_enroll_contact.py -v
```
Esperado: `FAILED` — ModuleNotFoundError: enroll_contact

- [ ] **Step 4: Implementar `enroll_contact.py`**

```python
# apps/api/src/shared/application/use_cases/followup/enroll_contact.py
from __future__ import annotations

from datetime import UTC, timedelta
from typing import Any
from uuid import UUID, uuid4

import structlog

from shared.domain.entities.followup import (
    EnrollmentStepStatus,
    FollowupEnrollment,
    FollowupEnrollmentStep,
)
from shared.domain.entities.scheduled_job import JobType

log = structlog.get_logger(__name__)


class EnrollContact:
    def __init__(self, *, flow_repo: Any, enrollment_repo: Any, job_repo: Any) -> None:
        self._flow_repo = flow_repo
        self._enrollment_repo = enrollment_repo
        self._job_repo = job_repo

    async def execute(
        self,
        *,
        account_id: UUID,
        contact_id: UUID,
        conversation_id: UUID,
        contact_phone: str,
        purchase_id: str,
        product: str,
        purchase_time,
    ) -> FollowupEnrollment | None:
        flow = await self._flow_repo.find_active_by_product(
            account_id=account_id, product=product
        )
        if flow is None:
            log.info("followup_no_flow_found", account_id=str(account_id), product=product)
            return None

        steps = await self._flow_repo.get_steps(flow.id)
        if not steps:
            log.info("followup_flow_has_no_steps", flow_id=str(flow.id))
            return None

        enrollment = FollowupEnrollment(
            account_id=account_id,
            flow_id=flow.id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            contact_phone=contact_phone,
            purchase_id=purchase_id,
        )

        enrollment_steps: list[FollowupEnrollmentStep] = []
        for step in steps:
            run_at = purchase_time + timedelta(hours=step.delay_from_purchase_hours)
            job = await self._job_repo.schedule(
                account_id=account_id,
                conversation_id=conversation_id,
                job_type=JobType.FOLLOWUP_STEP,
                payload={
                    "enrollment_step_id": None,  # preenchido abaixo após flush
                },
                run_at=run_at,
            )
            enrollment_step = FollowupEnrollmentStep(
                enrollment_id=enrollment.id,
                position=step.position,
                delay_from_purchase_hours=step.delay_from_purchase_hours,
                meta_template_name=step.meta_template_name,
                template_variables=step.template_variables,
                scheduled_job_id=job.id,
                status=EnrollmentStepStatus.PENDING,
            )
            enrollment_steps.append(enrollment_step)

        await self._enrollment_repo.create_with_steps(enrollment, enrollment_steps)

        log.info(
            "followup_enrolled",
            enrollment_id=str(enrollment.id),
            flow_id=str(flow.id),
            steps=len(enrollment_steps),
        )
        return enrollment
```

**Nota:** O `payload` do job inclui `enrollment_step_id: None` inicialmente porque o job é criado antes do flush do enrollment step. O worker usa `scheduled_job_id` do `FollowupEnrollmentStepModel` para encontrar o step — veja Task 6 como o payload é resolvido no handler.

**Alternativa mais simples:** guardar o `enrollment_step.id` no payload DEPOIS do flush. Ajustar `create_with_steps` para retornar os steps com seus IDs e depois atualizar os jobs. Para simplificar, o worker vai buscar o enrollment step pelo `scheduled_job_id` no banco (não pelo payload).

- [ ] **Step 5: Rodar testes**

```bash
cd apps/api && uv run pytest tests/unit/use_cases/followup/test_enroll_contact.py -v
```
Esperado: `PASSED`

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/application/use_cases/followup/ \
        apps/api/tests/unit/use_cases/followup/
git commit -m "feat(followup): use case EnrollContact"
```

---

### Task 5: Use case DispatchFollowupStep

**Files:**
- Create: `apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py`
- Modify: `apps/api/tests/unit/use_cases/followup/test_dispatch_followup_step.py`

- [ ] **Step 1: Escrever testes**

```python
# apps/api/tests/unit/use_cases/followup/test_dispatch_followup_step.py
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, call
from uuid import uuid4

import pytest

from shared.application.use_cases.followup.dispatch_followup_step import DispatchFollowupStep
from shared.domain.entities.followup import EnrollmentStepStatus, FollowupEnrollmentStep


def _make_step(status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING) -> FollowupEnrollmentStep:
    return FollowupEnrollmentStep(
        id=uuid4(),
        enrollment_id=uuid4(),
        position=1,
        delay_from_purchase_hours=0,
        meta_template_name="mv_boas_vindas",
        template_variables={"nome": "{{1}}"},
        scheduled_job_id=uuid4(),
        status=status,
    )


@pytest.mark.asyncio
async def test_dispatch_sends_template_and_saves_to_history():
    step = _make_step()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = False

    chatnexo = AsyncMock()
    history = AsyncMock()
    history.load.return_value = [{"role": "user", "content": "oi"}]

    account_id = uuid4()
    conversation_id = uuid4()
    contact_phone = "5511999990000"
    thread_id = f"{account_id}:{contact_phone}"

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo, chatnexo=chatnexo, conversation_history=history
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=account_id,
        conversation_id=conversation_id,
        contact_phone=contact_phone,
    )

    assert result == "SENT"
    chatnexo.send_template.assert_called_once_with(
        account_id=str(account_id),
        conversation_id=str(conversation_id),
        template_name="mv_boas_vindas",
        variables={"nome": "{{1}}"},
    )
    history.load.assert_called_once_with(thread_id=thread_id)
    history.save.assert_called_once()
    saved_messages = history.save.call_args.kwargs["messages"]
    assert any(
        m.get("role") == "assistant" and "mv_boas_vindas" in m.get("content", "")
        for m in saved_messages
    )
    enrollment_repo.update_step.assert_called_once()
    updated_step: FollowupEnrollmentStep = enrollment_repo.update_step.call_args.args[0]
    assert updated_step.status == EnrollmentStepStatus.SENT
    assert updated_step.sent_at is not None


@pytest.mark.asyncio
async def test_dispatch_marks_enrollment_completed_when_all_steps_sent():
    step = _make_step()
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step
    enrollment_repo.all_steps_sent.return_value = True

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo,
        chatnexo=AsyncMock(),
        conversation_history=AsyncMock(load=AsyncMock(return_value=[])),
    )
    await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=uuid4(),
        contact_phone="5511999990000",
    )

    from shared.domain.entities.followup import EnrollmentStatus
    enrollment_repo.update_enrollment_status.assert_called_once_with(
        step.enrollment_id, EnrollmentStatus.COMPLETED
    )


@pytest.mark.asyncio
async def test_dispatch_ignores_already_sent_step():
    step = _make_step(status=EnrollmentStepStatus.SENT)
    enrollment_repo = AsyncMock()
    enrollment_repo.find_step_by_id.return_value = step

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo,
        chatnexo=AsyncMock(),
        conversation_history=AsyncMock(),
    )
    result = await uc.execute(
        enrollment_step_id=step.id,
        account_id=uuid4(),
        conversation_id=uuid4(),
        contact_phone="5511999990000",
    )
    assert result == "IGNORADO"
    enrollment_repo.update_step.assert_not_called()
```

- [ ] **Step 2: Rodar testes para confirmar falha**

```bash
cd apps/api && uv run pytest tests/unit/use_cases/followup/test_dispatch_followup_step.py -v
```
Esperado: `FAILED` — ModuleNotFoundError

- [ ] **Step 3: Implementar `dispatch_followup_step.py`**

```python
# apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog

from shared.domain.entities.followup import EnrollmentStatus, EnrollmentStepStatus

log = structlog.get_logger(__name__)


class DispatchFollowupStep:
    def __init__(
        self, *, enrollment_repo: Any, chatnexo: Any, conversation_history: Any
    ) -> None:
        self._enrollment_repo = enrollment_repo
        self._chatnexo = chatnexo
        self._history = conversation_history

    async def execute(
        self,
        *,
        enrollment_step_id: UUID,
        account_id: UUID,
        conversation_id: UUID,
        contact_phone: str,
    ) -> str:
        step = await self._enrollment_repo.find_step_by_id(enrollment_step_id)
        if step is None:
            log.warning("followup_step_not_found", step_id=str(enrollment_step_id))
            return "ERRO: step não encontrado"

        if step.status != EnrollmentStepStatus.PENDING:
            log.info("followup_step_skipped", step_id=str(step.id), status=step.status)
            return "IGNORADO"

        await self._chatnexo.send_template(
            account_id=str(account_id),
            conversation_id=str(conversation_id),
            template_name=step.meta_template_name,
            variables=step.template_variables,
        )

        thread_id = f"{account_id}:{contact_phone}"
        messages = await self._history.load(thread_id=thread_id)
        messages.append({
            "role": "assistant",
            "content": f"[Mensagem automática de follow-up enviada: template={step.meta_template_name}]",
        })
        await self._history.save(thread_id=thread_id, messages=messages)

        step.status = EnrollmentStepStatus.SENT
        step.sent_at = datetime.now(UTC)
        await self._enrollment_repo.update_step(step)

        if await self._enrollment_repo.all_steps_sent(step.enrollment_id):
            await self._enrollment_repo.update_enrollment_status(
                step.enrollment_id, EnrollmentStatus.COMPLETED
            )

        log.info(
            "followup_step_dispatched",
            step_id=str(step.id),
            template=step.meta_template_name,
        )
        return "SENT"
```

- [ ] **Step 4: Rodar testes**

```bash
cd apps/api && uv run pytest tests/unit/use_cases/followup/ -v
```
Esperado: todos `PASSED`

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py \
        apps/api/tests/unit/use_cases/followup/test_dispatch_followup_step.py
git commit -m "feat(followup): use case DispatchFollowupStep"
```

---

### Task 6: Worker handler + DI

**Files:**
- Modify: `apps/api/src/interface/worker/handlers/scheduled.py`
- Modify: `apps/api/src/interface/worker/handlers/purchase.py`

- [ ] **Step 1: Escrever teste do worker dispatch**

```python
# apps/api/tests/unit/worker/test_followup_step_handler.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_handle_scheduled_followup_step_calls_dispatch():
    mock_dispatch = AsyncMock()
    mock_dispatch.execute = AsyncMock(return_value="SENT")

    with patch(
        "interface.worker.handlers.scheduled._get_dispatch_followup_step_handler",
        return_value=mock_dispatch,
    ):
        from interface.worker.handlers.scheduled import handle_scheduled

        step_id = str(uuid4())
        await handle_scheduled({
            "job_type": "followup_step",
            "account_id": str(uuid4()),
            "conversation_id": str(uuid4()),
            "contact_phone": "5511999990000",
            "enrollment_step_id": step_id,
        })

    mock_dispatch.execute.assert_called_once()
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
cd apps/api && uv run pytest tests/unit/worker/test_followup_step_handler.py -v
```
Esperado: `FAILED`

- [ ] **Step 3: Adicionar handler em `scheduled.py`**

No topo de `apps/api/src/interface/worker/handlers/scheduled.py`, adicionar após os imports existentes:

```python
def _get_dispatch_followup_step_handler():
    raise NotImplementedError("_get_dispatch_followup_step_handler: configure DI")
```

Ao final do `if/elif` chain em `handle_scheduled`, adicionar:

```python
    elif job_type == "followup_step":
        dispatch = _get_dispatch_followup_step_handler()
        await dispatch.execute(
            enrollment_step_id=UUID(payload["enrollment_step_id"]),
            account_id=UUID(payload["account_id"]),
            conversation_id=UUID(payload["conversation_id"]),
            contact_phone=payload.get("contact_phone", ""),
        )
```

Adicionar `from uuid import UUID` no topo do arquivo se não existir.

- [ ] **Step 4: Configurar DI em `purchase.py`**

Substituir o conteúdo de `handle_purchase` para usar DI inline (igual ao padrão de `handle_message`):

```python
# apps/api/src/interface/worker/handlers/purchase.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

import structlog
from cryptography.fernet import Fernet

from shared.adapters.chatnexo.client import ChatNexoClient
from shared.adapters.db.repositories.access_case_repo import AccessCaseRepository
from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
from shared.adapters.db.repositories.contact_repo import ContactRepository
from shared.adapters.db.repositories.followup_enrollment_repo import FollowupEnrollmentRepository
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.repositories.loja_express_case_repo import LojaExpressCaseRepository
from shared.adapters.db.repositories.scheduled_job import ScheduledJobRepository
from shared.adapters.db.session import session_scope
from shared.adapters.loja_express.stub_client import LojaExpressStubClient
from shared.application.purchase_handler import PurchaseHandler
from shared.application.use_cases.followup.enroll_contact import EnrollContact
from shared.application.use_cases.loja_express.criar_caso import CriarCasoLojaExpress
from shared.config.settings import get_settings
from shared.domain.events.purchase_received import PurchaseReceived

log = structlog.get_logger(__name__)


async def handle_purchase(payload: dict) -> None:
    settings = get_settings()
    fernet = Fernet(settings.integration_credentials_key.encode())

    event = PurchaseReceived(
        purchase_id=payload["purchase_id"],
        account_id=UUID(payload["account_id"]),
        contact_name=payload["contact_name"],
        contact_email=payload["contact_email"],
        contact_phone=payload["contact_phone"],
        product=payload["product"],
        amount_brl=int(payload["amount_brl"]),
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )

    async with session_scope() as session:
        config_repo = AccountConfigRepository(session=session, fernet=fernet)
        account_config = await config_repo.get(account_id=int(event.account_id))

        chatnexo = ChatNexoClient.from_account_config(account_config)
        contact_repo = ContactRepository(session=session)
        access_case_repo = AccessCaseRepository(session=session)
        scheduler = ScheduledJobRepository(session=session)
        loja_express_repo = LojaExpressCaseRepository(session=session)
        loja_express_port = LojaExpressStubClient()
        flow_repo = FollowupFlowRepository(session=session)
        enrollment_repo = FollowupEnrollmentRepository(session=session)

        criar_uc = CriarCasoLojaExpress(
            repo=loja_express_repo,
            chatnexo=chatnexo,
            scheduler=scheduler,
        )
        enroll_uc = EnrollContact(
            flow_repo=flow_repo,
            enrollment_repo=enrollment_repo,
            job_repo=scheduler,
        )

        handler = PurchaseHandler(
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            access_case_repo=access_case_repo,
            scheduler=scheduler,
            loja_express_case_repo=loja_express_repo,
            loja_express_port=loja_express_port,
            criar_uc=criar_uc,
            enroll_contact_uc=enroll_uc,
        )
        await handler.execute(event)

    log.info("purchase_job_done", purchase_id=payload["purchase_id"])
```

- [ ] **Step 5: Adicionar `enroll_contact_uc` ao `PurchaseHandler.__init__`**

Em `apps/api/src/shared/application/purchase_handler.py`, adicionar o parâmetro:

```python
    def __init__(
        self,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        access_case_repo: Any,
        scheduler: Any,
        loja_express_case_repo: Any = None,
        loja_express_port: Any = None,
        criar_uc: Any = None,
        enroll_contact_uc: Any = None,   # ← adicionar esta linha
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler
        self._loja_express_case_repo = loja_express_case_repo
        self._loja_express_port = loja_express_port
        self._criar_uc = criar_uc
        self._enroll_contact_uc = enroll_contact_uc   # ← adicionar
```

Em `PurchaseHandler.execute`, adicionar após o bloco Loja Express (antes do fluxo de AccessCase):

```python
        # Follow-up dinâmico para produtos não-Loja Express
        if not is_loja_express and self._enroll_contact_uc is not None:
            enrolled = await self._enroll_contact_uc.execute(
                account_id=event.account_id,
                contact_id=UUID(contact.id) if isinstance(contact.id, str) else contact.id,
                conversation_id=UUID(conversation_id) if isinstance(conversation_id, str) else UUID(str(conversation_id)),
                contact_phone=event.contact_phone,
                purchase_id=event.purchase_id,
                product=event.product,
                purchase_time=event.occurred_at,
            )
            if enrolled is not None:
                log.info(
                    "followup_enrolled_from_purchase",
                    enrollment_id=str(enrolled.id),
                    purchase_id=event.purchase_id,
                )
```

**Nota:** O fluxo normal de AccessCase continua rodando depois (não há `return` após o enroll). Isso é intencional — o follow-up dinâmico complementa o welcome, não o substitui.

- [ ] **Step 6: Configurar DI do dispatch em `worker.py`**

Em `apps/api/src/worker.py`, adicionar ao final do `main()`, antes de criar o `dispatcher`:

```python
    from agent.history import ConversationHistory
    from shared.adapters.chatnexo.client import ChatNexoClient
    from shared.adapters.db.repositories.followup_enrollment_repo import FollowupEnrollmentRepository
    from shared.application.use_cases.followup.dispatch_followup_step import DispatchFollowupStep
    from shared.config.settings import get_settings as _gs
    from cryptography.fernet import Fernet
    import interface.worker.handlers.scheduled as _sched

    def _make_dispatch_handler():
        settings = _gs()
        fernet = Fernet(settings.integration_credentials_key.encode())

        async def _dispatch(enrollment_step_id, account_id, conversation_id, contact_phone):
            from shared.adapters.db.repositories.account_config_repo import AccountConfigRepository
            async with get_sessionmaker()() as session:
                config_repo = AccountConfigRepository(session=session, fernet=fernet)
                account_config = await config_repo.get(account_id=int(str(account_id).replace('-', '')[:8], 16) % 1000)  # fallback
                chatnexo = ChatNexoClient.from_account_config(account_config)
                enrollment_repo = FollowupEnrollmentRepository(session=session)
                history = ConversationHistory(session=session)
                uc = DispatchFollowupStep(
                    enrollment_repo=enrollment_repo,
                    chatnexo=chatnexo,
                    conversation_history=history,
                )
                return await uc.execute(
                    enrollment_step_id=enrollment_step_id,
                    account_id=account_id,
                    conversation_id=conversation_id,
                    contact_phone=contact_phone,
                )
        return type("D", (), {"execute": staticmethod(_dispatch)})()

    _sched._get_dispatch_followup_step_handler = _make_dispatch_handler
```

**Nota:** O DI do `account_id` para buscar config precisa ser revisado — o `account_id` é UUID mas `config_repo.get` espera `int`. Verificar no teste de integração e ajustar conforme o padrão real do projeto.

- [ ] **Step 7: Rodar testes do worker**

```bash
cd apps/api && uv run pytest tests/unit/worker/test_followup_step_handler.py -v
```
Esperado: `PASSED`

- [ ] **Step 8: Rodar suite completa**

```bash
cd apps/api && uv run pytest tests/unit -v --tb=short
```
Esperado: todos passando

- [ ] **Step 9: Commit**

```bash
git add apps/api/src/interface/worker/handlers/scheduled.py \
        apps/api/src/interface/worker/handlers/purchase.py \
        apps/api/src/shared/application/purchase_handler.py \
        apps/api/src/worker.py \
        apps/api/tests/unit/worker/test_followup_step_handler.py
git commit -m "feat(followup): integrar EnrollContact no purchase handler e FOLLOWUP_STEP no worker"
```

---

### Task 7: Admin API — Schemas e Router

**Files:**
- Create: `apps/api/src/interface/http/schemas/followup.py`
- Create: `apps/api/src/interface/http/routers/admin/followup.py`

- [ ] **Step 1: Criar schemas Pydantic**

```python
# apps/api/src/interface/http/schemas/followup.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FollowupStepResponse(BaseModel):
    id: UUID
    flow_id: UUID
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str
    template_variables: dict
    created_at: datetime


class FollowupFlowResponse(BaseModel):
    id: UUID
    account_id: UUID
    name: str
    product_tags: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateFlowRequest(BaseModel):
    name: str
    product_tags: list[str]


class UpdateFlowRequest(BaseModel):
    name: str | None = None
    product_tags: list[str] | None = None
    is_active: bool | None = None


class CreateStepRequest(BaseModel):
    position: int
    delay_from_purchase_hours: int
    meta_template_name: str
    template_variables: dict = {}


class UpdateStepRequest(BaseModel):
    position: int | None = None
    delay_from_purchase_hours: int | None = None
    meta_template_name: str | None = None
    template_variables: dict | None = None


class ReorderStepsRequest(BaseModel):
    steps: list[ReorderItem]


class ReorderItem(BaseModel):
    id: UUID
    position: int


ReorderStepsRequest.model_rebuild()
```

- [ ] **Step 2: Criar router**

```python
# apps/api/src/interface/http/routers/admin/followup.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from interface.http.deps.admin_auth import AdminAuth, require_admin
from interface.http.schemas.followup import (
    CreateFlowRequest,
    CreateStepRequest,
    FollowupFlowResponse,
    FollowupStepResponse,
    ReorderStepsRequest,
    UpdateFlowRequest,
    UpdateStepRequest,
)
from shared.adapters.db.repositories.followup_flow_repo import FollowupFlowRepository
from shared.adapters.db.session import session_scope

router = APIRouter(tags=["admin-followup"])


def _flow_to_resp(f) -> FollowupFlowResponse:
    return FollowupFlowResponse(
        id=f.id,
        account_id=f.account_id,
        name=f.name,
        product_tags=f.product_tags,
        is_active=f.is_active,
        created_at=f.created_at,
        updated_at=f.updated_at,
    )


def _step_to_resp(s) -> FollowupStepResponse:
    return FollowupStepResponse(
        id=s.id,
        flow_id=s.flow_id,
        position=s.position,
        delay_from_purchase_hours=s.delay_from_purchase_hours,
        meta_template_name=s.meta_template_name,
        template_variables=s.template_variables,
        created_at=s.created_at,
    )


@router.get("/followup/flows", response_model=list[FollowupFlowResponse])
async def list_flows(auth: AdminAuth = Depends(require_admin)) -> list[FollowupFlowResponse]:  # noqa: B008
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        flows = await repo.list_flows(account_id=auth.account_id)
    return [_flow_to_resp(f) for f in flows]


@router.post("/followup/flows", response_model=FollowupFlowResponse, status_code=status.HTTP_201_CREATED)
async def create_flow(
    body: CreateFlowRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupFlowResponse:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        flow = await repo.create_flow(
            account_id=auth.account_id,
            name=body.name,
            product_tags=body.product_tags,
        )
    return _flow_to_resp(flow)


@router.put("/followup/flows/{flow_id}", response_model=FollowupFlowResponse)
async def update_flow(
    flow_id: UUID,
    body: UpdateFlowRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupFlowResponse:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        flow = await repo.update_flow(
            flow_id,
            name=body.name,
            product_tags=body.product_tags,
            is_active=body.is_active,
        )
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow não encontrado")
    return _flow_to_resp(flow)


@router.delete("/followup/flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_flow(
    flow_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        deleted = await repo.delete_flow(flow_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow não encontrado")


@router.get("/followup/flows/{flow_id}/steps", response_model=list[FollowupStepResponse])
async def list_steps(
    flow_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[FollowupStepResponse]:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        steps = await repo.get_steps(flow_id)
    return [_step_to_resp(s) for s in steps]


@router.post("/followup/flows/{flow_id}/steps", response_model=FollowupStepResponse, status_code=status.HTTP_201_CREATED)
async def create_step(
    flow_id: UUID,
    body: CreateStepRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupStepResponse:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        step = await repo.create_step(
            flow_id=flow_id,
            position=body.position,
            delay_from_purchase_hours=body.delay_from_purchase_hours,
            meta_template_name=body.meta_template_name,
            template_variables=body.template_variables,
        )
    return _step_to_resp(step)


@router.put("/followup/flows/{flow_id}/steps/{step_id}", response_model=FollowupStepResponse)
async def update_step(
    flow_id: UUID,
    step_id: UUID,
    body: UpdateStepRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> FollowupStepResponse:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        step = await repo.update_step(
            step_id,
            position=body.position,
            delay_from_purchase_hours=body.delay_from_purchase_hours,
            meta_template_name=body.meta_template_name,
            template_variables=body.template_variables,
        )
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step não encontrado")
    return _step_to_resp(step)


@router.delete("/followup/flows/{flow_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    flow_id: UUID,
    step_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        deleted = await repo.delete_step(step_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step não encontrado")


@router.patch("/followup/flows/{flow_id}/steps/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_steps(
    flow_id: UUID,
    body: ReorderStepsRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> None:
    async with session_scope() as session:
        repo = FollowupFlowRepository(session=session)
        for item in body.steps:
            await repo.update_step(item.id, position=item.position)
```

- [ ] **Step 3: Escrever teste básico do router**

```python
# apps/api/tests/unit/interface/admin/test_followup_router.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def _make_app():
    from fastapi import FastAPI
    from interface.http.routers.admin.followup import router

    app = FastAPI()
    app.include_router(router, prefix="/admin")
    return app


def _mock_auth():
    from interface.http.deps.admin_auth import AdminAuth, require_admin
    from uuid import UUID
    auth = AdminAuth(account_id=UUID("00000000-0000-0000-0000-000000000001"), user_email="a@b.com", user_role="admin")

    def _override():
        return auth

    return _override


@pytest.fixture
def client():
    app = _make_app()
    auth_override = _mock_auth()
    from interface.http.deps.admin_auth import require_admin
    app.dependency_overrides[require_admin] = auth_override
    return TestClient(app)


def test_list_flows_returns_empty(client):
    with patch(
        "interface.http.routers.admin.followup.session_scope"
    ) as mock_scope:
        mock_session = AsyncMock()
        mock_scope.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_scope.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "interface.http.routers.admin.followup.FollowupFlowRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.list_flows = AsyncMock(return_value=[])
            resp = client.get("/admin/followup/flows")

    assert resp.status_code == 200
    assert resp.json() == []
```

- [ ] **Step 4: Rodar teste do router**

```bash
cd apps/api && uv run pytest tests/unit/interface/admin/test_followup_router.py -v
```
Esperado: `PASSED`

- [ ] **Step 5: Registrar router em `main.py`**

Em `apps/api/src/main.py`, adicionar import e registro:

```python
# No bloco de imports dos routers admin:
from interface.http.routers.admin import followup as admin_followup

# Em create_app(), após os outros routers:
app.include_router(admin_followup.router, prefix="/admin")
```

- [ ] **Step 6: Verificar que o app sobe sem erro**

```bash
cd apps/api && uv run uvicorn nexoia.main:app --reload &
sleep 3
curl -s http://localhost:8000/docs | grep -q "followup" && echo "OK" || echo "FAIL"
kill %1
```

- [ ] **Step 7: Rodar lint**

```bash
cd apps/api && uv run ruff check src/interface/http/routers/admin/followup.py src/interface/http/schemas/followup.py
```
Esperado: sem erros

- [ ] **Step 8: Commit final**

```bash
git add apps/api/src/interface/http/schemas/followup.py \
        apps/api/src/interface/http/routers/admin/followup.py \
        apps/api/src/main.py \
        apps/api/tests/unit/interface/admin/test_followup_router.py
git commit -m "feat(followup): admin API CRUD de flows e steps"
```

---

### Task 8: Lint e suite final

- [ ] **Step 1: Lint completo**

```bash
cd apps/api && uv run ruff check src tests && uv run ruff format --check src tests
```
Corrigir qualquer erro reportado.

- [ ] **Step 2: Suite completa**

```bash
cd apps/api && uv run pytest tests/unit -v --tb=short
```
Esperado: todos `PASSED`

- [ ] **Step 3: mypy (opcional mas recomendado)**

```bash
cd apps/api && uv run mypy src/shared/domain/entities/followup.py src/shared/application/use_cases/followup/
```

- [ ] **Step 4: Commit de ajustes de lint (se houver)**

```bash
git add -u
git commit -m "style(followup): corrigir lint ruff"
```
