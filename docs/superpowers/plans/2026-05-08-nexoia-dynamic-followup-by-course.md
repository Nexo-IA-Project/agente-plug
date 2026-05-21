# Follow-up Dinâmico por Curso — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o matching de `product_tags` por uma entidade `Course` explícita; vincular `FollowupFlow` ao curso via FK; descontinuar a capability Loja Express convertendo-a em curso comum; introduzir variáveis dinâmicas em steps; trocar o modal centralizado por um drawer lateral compartilhado em todo o admin.

**Architecture:** Backend mantém Clean Architecture (domain → ports → adapters → application → interface). Mudança no fluxo da compra: `purchase_handler` faz lookup `Course.find_by_hubla_id(payload.product_id)` → enrolla em **todos os flows ativos** do curso (cada um agendado independentemente). Frontend troca o modal central por um componente `Drawer` reutilizável (encosta na linha da sidebar lateral, conteúdo full-width, slide horizontal suave) usado tanto na nova página `/admin/courses` quanto em `/admin/followup`.

**Tech Stack:** Backend — Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, asyncpg, pytest+pytest-asyncio. Frontend — Next.js 15 (App Router), React 19, TypeScript 5, Tailwind, sonner, dnd-kit (apenas para reorder interno de steps).

**Spec:** `docs/superpowers/specs/2026-05-08-nexoia-dynamic-followup-by-course-design.md`

---

## File Structure

### Backend — Criar

```
apps/api/src/shared/domain/entities/course.py
apps/api/src/shared/domain/ports/course_repository.py
apps/api/src/shared/domain/value_objects/step_variable_binding.py
apps/api/src/shared/adapters/db/repositories/course_repo.py
apps/api/src/shared/application/use_cases/followup/variable_resolver.py
apps/api/src/interface/http/routers/admin/courses.py
apps/api/migrations/versions/f3a4b5c6d7e8_dynamic_followup_by_course.py
apps/api/scripts/seed_loja_express.py
apps/api/tests/unit/followup/test_variable_resolver.py
apps/api/tests/unit/db/test_course_repo.py
apps/api/tests/integration/admin/test_courses_router.py
```

### Backend — Modificar

```
apps/api/src/shared/adapters/db/models.py
   + class CourseModel
   ~ FollowupFlowModel: + course_id (FK NOT NULL), - product_tags, - position
   ~ FollowupEnrollmentModel: + customer_name, + product_name
   - class LojaExpressCaseModel

apps/api/src/shared/domain/entities/followup.py
   ~ FollowupFlow: + course_id, - product_tags
   ~ FollowupEnrollment: + customer_name, + product_name
   ~ FollowupStep.template_variables — schema novo (StepVariableBinding)

apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py
   - find_active_by_product
   + list_active_by_course
   + find_by_id (passa a retornar flow com course)
   ~ create_flow / update_flow assinaturas

apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py
   ~ create assinatura (recebe customer_name, product_name)

apps/api/src/shared/application/use_cases/followup/enroll_contact.py
   ~ execute: recebe flow_id direto, customer_name, product_name

apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py
   ~ resolve template_variables via VariableResolver

apps/api/src/shared/application/purchase_handler.py
   ~ lookup Course → enrolla em todos os flows ativos; remove branch Loja Express

apps/api/src/interface/http/routers/admin/followup.py
   ~ schemas (CreateFlow.course_id, response inclui course)
   - reorder de flows externo

apps/api/src/interface/http/routers/webhook_purchase.py
   ~ PurchasePayload: customer_name, product_id, product_name

apps/api/src/interface/worker/handlers/scheduled.py
   - despachos LOJA_EXPRESS_D1/D3/D5/D7

apps/api/src/shared/config/settings.py
   - loja_express_product_tags / loja_express_d{1,3,5,7}_delay_hours

apps/api/.env.example
   - chaves LOJA_EXPRESS_*

apps/api/src/main.py (ou wherever DI/router registration is)
   + include_router de admin/courses
```

### Backend — Remover

```
apps/api/src/shared/application/use_cases/loja_express/
apps/api/src/shared/adapters/loja_express/
apps/api/src/shared/adapters/db/repositories/loja_express_case_repo.py
apps/api/src/shared/domain/entities/loja_express_case.py
apps/api/src/shared/domain/ports/loja_express_port.py
apps/api/tests/**/*loja_express*
```

### Frontend — Criar

```
apps/web/src/shared/components/Drawer.tsx
apps/web/src/features/courses/types.ts
apps/web/src/features/courses/hooks/useCourses.ts
apps/web/src/features/courses/components/CourseCard.tsx
apps/web/src/features/courses/components/CourseDrawer.tsx
apps/web/src/app/(admin)/courses/page.tsx
apps/web/src/features/followup/components/StepVariableEditor.tsx
```

### Frontend — Modificar

```
apps/web/src/lib/api.ts
   + listCourses, createCourse, updateCourse, deleteCourse
   ~ listFollowupFlows / createFollowupFlow / updateFollowupFlow (course_id)
   - reorderFollowupFlows
   ~ create/update step (template_variables novo schema)

apps/web/src/features/followup/types.ts
   ~ FollowupFlow.course (chip)
   ~ FollowupStep.template_variables (StepVariableBinding map)

apps/web/src/features/followup/components/FlowCard.tsx
   ~ exibe chip do curso, sem dnd handle externo

apps/web/src/features/followup/components/FlowDrawer.tsx
   ~ usa Drawer compartilhado; campo course_id; remove tags

apps/web/src/features/followup/components/StepInlineForm.tsx
   ~ integra StepVariableEditor

apps/web/src/app/(admin)/followup/page.tsx
   ~ remove dnd externo

apps/web/src/shared/components/layout/Sidebar.tsx
   + item Cursos
```

---

## Tasks

### Phase 1 — Backend domain e banco

#### Task 1: Domain entity e port de Course

**Files:**
- Create: `apps/api/src/shared/domain/entities/course.py`
- Create: `apps/api/src/shared/domain/ports/course_repository.py`

- [ ] **Step 1: Criar entity Course**

```python
# apps/api/src/shared/domain/entities/course.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class Course:
    id: UUID
    account_id: UUID
    name: str
    hubla_id: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

- [ ] **Step 2: Criar port CourseRepository**

```python
# apps/api/src/shared/domain/ports/course_repository.py
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.domain.entities.course import Course


class CourseRepository(Protocol):
    async def list_by_account(self, account_id: UUID) -> list[Course]: ...
    async def find_by_id(self, course_id: UUID) -> Course | None: ...
    async def find_active_by_hubla_id(
        self, account_id: UUID, hubla_id: str
    ) -> Course | None: ...
    async def create(
        self,
        *,
        account_id: UUID,
        name: str,
        hubla_id: str,
        is_active: bool = True,
    ) -> Course: ...
    async def update(
        self,
        course_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Course | None: ...
    async def delete(self, course_id: UUID) -> bool: ...
    async def count_flows(self, course_id: UUID) -> int: ...
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/shared/domain/entities/course.py apps/api/src/shared/domain/ports/course_repository.py
git commit -m "feat(domain): adicionar entity e port Course"
```

---

#### Task 2: Atualizar models.py — CourseModel + ajustes em FollowupFlow/Enrollment + drop LojaExpressCaseModel

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`

- [ ] **Step 1: Adicionar CourseModel**

Inserir após `MetaTemplateModel` (mantendo ordem alfabética por bloco — encaixar na seção de admin/catálogo):

```python
class CourseModel(Base):
    __tablename__ = "courses"
    __table_args__ = (
        sa.UniqueConstraint("account_id", "hubla_id", name="uq_courses_account_hubla"),
        sa.Index("ix_courses_account_id", "account_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    hubla_id: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 2: Alterar FollowupFlowModel**

Localizar `class FollowupFlowModel`. Remover linhas de `product_tags` e `position`. Adicionar `course_id`:

```python
course_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    sa.ForeignKey("courses.id", ondelete="RESTRICT"),
    nullable=False,
    index=True,
)
```

Remover essas duas linhas:
```python
product_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
position: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
```

- [ ] **Step 3: Alterar FollowupEnrollmentModel**

Adicionar logo após `purchase_id`:

```python
customer_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
product_name: Mapped[str] = mapped_column(sa.String(200), nullable=False)
```

- [ ] **Step 4: Remover LojaExpressCaseModel**

Apagar do arquivo a `class LojaExpressCaseModel(Base)` inteira (e qualquer enum/constante exclusiva dela).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/models.py
git commit -m "feat(db): adicionar CourseModel e refatorar followup; drop LojaExpressCaseModel"
```

---

#### Task 3: Migration `f3a4b5c6d7e8`

**Files:**
- Create: `apps/api/migrations/versions/f3a4b5c6d7e8_dynamic_followup_by_course.py`

- [ ] **Step 1: Criar arquivo de migration**

```python
"""Dynamic follow-up by course

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-05-08
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "f3a4b5c6d7e8"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Cria courses
    op.create_table(
        "courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("hubla_id", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "hubla_id", name="uq_courses_account_hubla"),
    )
    op.create_index("ix_courses_account_id", "courses", ["account_id"])

    # 2. Limpa dados de follow-up (rasgar e recriar)
    op.execute("DELETE FROM followup_enrollment_steps")
    op.execute("DELETE FROM followup_enrollments")
    op.execute("DELETE FROM followup_steps")
    op.execute("DELETE FROM followup_flows")

    # 3. Ajusta followup_flows
    op.add_column(
        "followup_flows",
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
    )
    op.create_foreign_key(
        "fk_followup_flows_course_id",
        "followup_flows", "courses",
        ["course_id"], ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_followup_flows_course_id", "followup_flows", ["course_id"])
    op.drop_column("followup_flows", "product_tags")
    op.drop_column("followup_flows", "position")

    # 4. Snapshots em followup_enrollments
    op.add_column(
        "followup_enrollments",
        sa.Column("customer_name", sa.String(200), nullable=False, server_default=""),
    )
    op.add_column(
        "followup_enrollments",
        sa.Column("product_name", sa.String(200), nullable=False, server_default=""),
    )
    op.alter_column("followup_enrollments", "customer_name", server_default=None)
    op.alter_column("followup_enrollments", "product_name", server_default=None)

    # 5. Drop loja_express_cases
    op.drop_table("loja_express_cases")


def downgrade() -> None:
    # Recria loja_express_cases (schema mínimo — dados não voltam)
    op.create_table(
        "loja_express_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("purchase_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"]),
    )

    # Reverte enrollments
    op.drop_column("followup_enrollments", "product_name")
    op.drop_column("followup_enrollments", "customer_name")

    # Reverte followup_flows
    op.add_column(
        "followup_flows",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "followup_flows",
        sa.Column("product_tags", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.drop_index("ix_followup_flows_course_id", table_name="followup_flows")
    op.drop_constraint("fk_followup_flows_course_id", "followup_flows", type_="foreignkey")
    op.drop_column("followup_flows", "course_id")

    # Drop courses
    op.drop_index("ix_courses_account_id", table_name="courses")
    op.drop_table("courses")
```

- [ ] **Step 2: Aplicar migration localmente**

```bash
cd apps/api && uv run alembic upgrade heads
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade e2f3a4b5c6d7 -> f3a4b5c6d7e8, Dynamic follow-up by course`

- [ ] **Step 3: Verificar schema no banco**

```bash
cd apps/api && uv run python -c "
from sqlalchemy import inspect
from shared.adapters.db.session import get_engine
import asyncio
async def check():
    engine = get_engine()
    async with engine.connect() as conn:
        cols = await conn.run_sync(lambda c: [c.name for c in inspect(c).get_columns('followup_flows')])
        print('followup_flows cols:', cols)
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
        print('has courses:', 'courses' in tables)
        print('has loja_express_cases:', 'loja_express_cases' in tables)
asyncio.run(check())
"
```

Expected: `followup_flows` contém `course_id`, NÃO contém `product_tags` nem `position`. `courses` existe. `loja_express_cases` NÃO existe.

- [ ] **Step 4: Commit**

```bash
git add apps/api/migrations/versions/f3a4b5c6d7e8_dynamic_followup_by_course.py
git commit -m "feat(db): migration dynamic followup by course (drop product_tags, course FK, drop loja_express_cases)"
```

---

#### Task 4: SqlCourseRepository (TDD)

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/course_repo.py`
- Test: `apps/api/tests/unit/db/test_course_repo.py`

- [ ] **Step 1: Escrever testes falhando**

```python
# apps/api/tests/unit/db/test_course_repo.py
from __future__ import annotations

import pytest
from uuid import uuid4

from shared.adapters.db.repositories.course_repo import SqlCourseRepository
from tests.factories import make_account


@pytest.mark.asyncio
async def test_create_and_find_by_id(session_factory):
    async with session_factory() as session:
        account = await make_account(session)
        repo = SqlCourseRepository(session)
        created = await repo.create(
            account_id=account.id,
            name="Marketing 360",
            hubla_id="prod-mkt-360",
        )
        assert created.id is not None
        found = await repo.find_by_id(created.id)
        assert found is not None
        assert found.name == "Marketing 360"
        assert found.hubla_id == "prod-mkt-360"
        assert found.is_active is True


@pytest.mark.asyncio
async def test_find_active_by_hubla_id(session_factory):
    async with session_factory() as session:
        account = await make_account(session)
        repo = SqlCourseRepository(session)
        await repo.create(account_id=account.id, name="Curso A", hubla_id="A")
        await repo.create(account_id=account.id, name="Curso B", hubla_id="B", is_active=False)

        found = await repo.find_active_by_hubla_id(account.id, "A")
        assert found is not None and found.name == "Curso A"

        inactive = await repo.find_active_by_hubla_id(account.id, "B")
        assert inactive is None


@pytest.mark.asyncio
async def test_unique_account_hubla_id(session_factory):
    async with session_factory() as session:
        account = await make_account(session)
        repo = SqlCourseRepository(session)
        await repo.create(account_id=account.id, name="A", hubla_id="X")
        with pytest.raises(Exception):
            await repo.create(account_id=account.id, name="B", hubla_id="X")


@pytest.mark.asyncio
async def test_update_partial(session_factory):
    async with session_factory() as session:
        account = await make_account(session)
        repo = SqlCourseRepository(session)
        c = await repo.create(account_id=account.id, name="Old", hubla_id="X")
        updated = await repo.update(c.id, name="New")
        assert updated is not None and updated.name == "New" and updated.hubla_id == "X"


@pytest.mark.asyncio
async def test_delete(session_factory):
    async with session_factory() as session:
        account = await make_account(session)
        repo = SqlCourseRepository(session)
        c = await repo.create(account_id=account.id, name="A", hubla_id="X")
        deleted = await repo.delete(c.id)
        assert deleted is True
        assert await repo.find_by_id(c.id) is None
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd apps/api && uv run pytest tests/unit/db/test_course_repo.py -v
```

Expected: ImportError em `course_repo`.

- [ ] **Step 3: Implementar repositório**

```python
# apps/api/src/shared/adapters/db/repositories/course_repo.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import CourseModel, FollowupFlowModel
from shared.domain.entities.course import Course


def _to_entity(m: CourseModel) -> Course:
    return Course(
        id=m.id,
        account_id=m.account_id,
        name=m.name,
        hubla_id=m.hubla_id,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@dataclass
class SqlCourseRepository:
    session: AsyncSession

    async def list_by_account(self, account_id: UUID) -> list[Course]:
        stmt = select(CourseModel).where(CourseModel.account_id == account_id).order_by(CourseModel.name)
        rows = (await self.session.execute(stmt)).scalars().all()
        return [_to_entity(m) for m in rows]

    async def find_by_id(self, course_id: UUID) -> Course | None:
        m = await self.session.get(CourseModel, course_id)
        return _to_entity(m) if m else None

    async def find_active_by_hubla_id(self, account_id: UUID, hubla_id: str) -> Course | None:
        stmt = select(CourseModel).where(
            CourseModel.account_id == account_id,
            CourseModel.hubla_id == hubla_id,
            CourseModel.is_active.is_(True),
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        return _to_entity(m) if m else None

    async def create(self, *, account_id: UUID, name: str, hubla_id: str, is_active: bool = True) -> Course:
        now = datetime.now(timezone.utc)
        m = CourseModel(
            id=uuid4(), account_id=account_id, name=name,
            hubla_id=hubla_id, is_active=is_active,
            created_at=now, updated_at=now,
        )
        self.session.add(m)
        await self.session.flush()
        return _to_entity(m)

    async def update(
        self,
        course_id: UUID,
        *,
        name: str | None = None,
        hubla_id: str | None = None,
        is_active: bool | None = None,
    ) -> Course | None:
        m = await self.session.get(CourseModel, course_id)
        if m is None:
            return None
        if name is not None:
            m.name = name
        if hubla_id is not None:
            m.hubla_id = hubla_id
        if is_active is not None:
            m.is_active = is_active
        m.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return _to_entity(m)

    async def delete(self, course_id: UUID) -> bool:
        m = await self.session.get(CourseModel, course_id)
        if m is None:
            return False
        await self.session.delete(m)
        await self.session.flush()
        return True

    async def count_flows(self, course_id: UUID) -> int:
        from sqlalchemy import func
        stmt = select(func.count(FollowupFlowModel.id)).where(FollowupFlowModel.course_id == course_id)
        return int((await self.session.execute(stmt)).scalar_one())
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/unit/db/test_course_repo.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/course_repo.py apps/api/tests/unit/db/test_course_repo.py
git commit -m "feat(repo): SqlCourseRepository com CRUD e count_flows"
```

---

#### Task 5: Atualizar FollowupFlowRepository

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py`
- Modify: `apps/api/src/shared/domain/entities/followup.py`

- [ ] **Step 1: Atualizar entity FollowupFlow**

Em `apps/api/src/shared/domain/entities/followup.py`, na classe `FollowupFlow`:
- Remover atributo `product_tags`.
- Remover atributo `position` (se existir nesta entity — caso esteja apenas no model, ignorar).
- Adicionar atributo `course_id: UUID`.

```python
@dataclass(slots=True)
class FollowupFlow:
    id: UUID
    account_id: UUID
    course_id: UUID
    name: str
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

- [ ] **Step 2: Atualizar followup_flow_repo.py**

Substituir o conteúdo do método `find_active_by_product` por `list_active_by_course`. Atualizar `create_flow` e `update_flow` para usarem `course_id` em vez de `product_tags`. Remover `reorder_flows`.

```python
# (substituir os métodos relevantes)

async def list_active_by_course(self, course_id: UUID) -> list[FollowupFlow]:
    stmt = select(FollowupFlowModel).where(
        FollowupFlowModel.course_id == course_id,
        FollowupFlowModel.is_active.is_(True),
    )
    rows = (await self.session.execute(stmt)).scalars().all()
    return [_to_flow_entity(m) for m in rows]

async def create_flow(
    self, *, account_id: UUID, course_id: UUID, name: str, is_active: bool = True
) -> FollowupFlow:
    now = datetime.now(timezone.utc)
    m = FollowupFlowModel(
        id=uuid4(), account_id=account_id, course_id=course_id,
        name=name, is_active=is_active,
        created_at=now, updated_at=now,
    )
    self.session.add(m)
    await self.session.flush()
    return _to_flow_entity(m)

async def update_flow(
    self,
    flow_id: UUID,
    *,
    name: str | None = None,
    course_id: UUID | None = None,
    is_active: bool | None = None,
) -> FollowupFlow | None:
    m = await self.session.get(FollowupFlowModel, flow_id)
    if m is None:
        return None
    if name is not None:
        m.name = name
    if course_id is not None:
        m.course_id = course_id
    if is_active is not None:
        m.is_active = is_active
    m.updated_at = datetime.now(timezone.utc)
    await self.session.flush()
    return _to_flow_entity(m)
```

Remover método `reorder_flows` por completo. Manter `find_active_by_product` removido. Atualizar `_to_flow_entity` (helper) para usar `course_id` em vez de `product_tags`.

- [ ] **Step 3: Rodar testes existentes do repo**

```bash
cd apps/api && uv run pytest tests/unit -k "followup_flow" -v
```

Expected: alguns testes vão falhar por causa da mudança de assinatura. **Atualize-os** para usar `course_id` (criando um Course antes via `make_course` factory — adicionar à `tests/factories.py` se não existir).

- [ ] **Step 4: Adicionar factory para Course**

Em `apps/api/tests/factories.py`:

```python
from shared.adapters.db.models import CourseModel
from datetime import datetime, timezone
from uuid import uuid4

async def make_course(session, *, account_id=None, name="Curso Teste", hubla_id="prod-test", is_active=True):
    if account_id is None:
        account = await make_account(session)
        account_id = account.id
    now = datetime.now(timezone.utc)
    m = CourseModel(
        id=uuid4(), account_id=account_id,
        name=name, hubla_id=hubla_id, is_active=is_active,
        created_at=now, updated_at=now,
    )
    session.add(m)
    await session.flush()
    return m
```

- [ ] **Step 5: Re-rodar e confirmar verde**

```bash
cd apps/api && uv run pytest tests/unit -k "followup_flow" -v
```

Expected: PASS (com testes atualizados para usar `course_id`).

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py apps/api/src/shared/domain/entities/followup.py apps/api/tests/factories.py apps/api/tests/unit
git commit -m "refactor(repo): FollowupFlow usa course_id; remove product_tags e reorder_flows"
```

---

#### Task 6: Atualizar FollowupEnrollmentRepository (snapshots)

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py`
- Modify: `apps/api/src/shared/domain/entities/followup.py`

- [ ] **Step 1: Atualizar entity FollowupEnrollment**

Adicionar atributos:

```python
@dataclass(slots=True)
class FollowupEnrollment:
    id: UUID
    account_id: UUID
    flow_id: UUID
    contact_id: UUID
    conversation_id: str
    contact_phone: str
    purchase_id: str
    customer_name: str    # NOVO
    product_name: str     # NOVO
    status: str = "active"
    created_at: datetime | None = None
```

- [ ] **Step 2: Atualizar create do repo**

Modificar a assinatura do `create` no `followup_enrollment_repo.py` para receber `customer_name` e `product_name`. Atualizar o helper `_to_enrollment_entity` para mapear esses campos.

```python
async def create(
    self,
    *,
    account_id: UUID,
    flow_id: UUID,
    contact_id: UUID,
    conversation_id: str,
    contact_phone: str,
    purchase_id: str,
    customer_name: str,
    product_name: str,
) -> FollowupEnrollment:
    now = datetime.now(timezone.utc)
    m = FollowupEnrollmentModel(
        id=uuid4(),
        account_id=account_id,
        flow_id=flow_id,
        contact_id=contact_id,
        conversation_id=conversation_id,
        contact_phone=contact_phone,
        purchase_id=purchase_id,
        customer_name=customer_name,
        product_name=product_name,
        status="active",
        created_at=now,
    )
    self.session.add(m)
    await self.session.flush()
    return _to_enrollment_entity(m)
```

- [ ] **Step 3: Rodar testes existentes**

```bash
cd apps/api && uv run pytest tests/unit -k "enrollment" -v
```

Expected: testes podem falhar por assinatura — atualize fakes/mocks para passarem `customer_name` e `product_name`.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py apps/api/src/shared/domain/entities/followup.py apps/api/tests/unit
git commit -m "feat(repo): snapshots customer_name/product_name em FollowupEnrollment"
```

---

### Phase 2 — Use cases

#### Task 7: StepVariableBinding + VariableResolver (TDD)

**Files:**
- Create: `apps/api/src/shared/domain/value_objects/step_variable_binding.py`
- Create: `apps/api/src/shared/application/use_cases/followup/variable_resolver.py`
- Test: `apps/api/tests/unit/followup/test_variable_resolver.py`

- [ ] **Step 1: Definir StepVariableBinding (DTO)**

```python
# apps/api/src/shared/domain/value_objects/step_variable_binding.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VariableSource = Literal[
    "customer_name", "product_name", "contact_phone", "contact_email", "static"
]


@dataclass(frozen=True, slots=True)
class StepVariableBinding:
    source: VariableSource
    value: str | None = None  # obrigatório se source == "static"

    @classmethod
    def from_dict(cls, raw: dict) -> "StepVariableBinding":
        source = raw.get("source")
        if source not in ("customer_name", "product_name", "contact_phone", "contact_email", "static"):
            raise ValueError(f"invalid source: {source!r}")
        value = raw.get("value")
        if source == "static" and not value:
            raise ValueError("static binding requires non-empty value")
        if source != "static" and value is not None:
            raise ValueError("non-static binding must not include value")
        return cls(source=source, value=value)

    def to_dict(self) -> dict:
        d: dict = {"source": self.source}
        if self.value is not None:
            d["value"] = self.value
        return d
```

- [ ] **Step 2: Escrever testes do resolver**

```python
# apps/api/tests/unit/followup/test_variable_resolver.py
from __future__ import annotations

import pytest

from shared.application.use_cases.followup.variable_resolver import (
    VariableResolver, ResolutionContext,
)
from shared.domain.value_objects.step_variable_binding import StepVariableBinding


def ctx(**kwargs):
    defaults = dict(
        customer_name="Fabio",
        product_name="Marketing 360",
        contact_phone="+5511999999999",
        contact_email="fabio@example.com",
    )
    defaults.update(kwargs)
    return ResolutionContext(**defaults)


def test_resolves_customer_name():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="customer_name"), ctx()) == "Fabio"


def test_resolves_product_name():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="product_name"), ctx()) == "Marketing 360"


def test_resolves_contact_phone():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="contact_phone"), ctx()) == "+5511999999999"


def test_resolves_contact_email():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="contact_email"), ctx()) == "fabio@example.com"


def test_resolves_static():
    resolver = VariableResolver()
    binding = StepVariableBinding(source="static", value="promoção limitada")
    assert resolver.resolve(binding, ctx()) == "promoção limitada"


def test_resolves_email_missing_returns_empty_string():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="contact_email"), ctx(contact_email=None)) == ""


def test_resolve_all_returns_dict_keyed_by_var_name():
    resolver = VariableResolver()
    raw = {
        "1": {"source": "customer_name"},
        "2": {"source": "static", "value": "Olá"},
    }
    out = resolver.resolve_all(raw, ctx())
    assert out == {"1": "Fabio", "2": "Olá"}


def test_resolve_all_skips_unknown_keys_silently():
    resolver = VariableResolver()
    out = resolver.resolve_all({}, ctx())
    assert out == {}
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
cd apps/api && uv run pytest tests/unit/followup/test_variable_resolver.py -v
```

Expected: ImportError.

- [ ] **Step 4: Implementar resolver**

```python
# apps/api/src/shared/application/use_cases/followup/variable_resolver.py
from __future__ import annotations

from dataclasses import dataclass

from shared.domain.value_objects.step_variable_binding import StepVariableBinding


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    customer_name: str
    product_name: str
    contact_phone: str
    contact_email: str | None


class VariableResolver:
    def resolve(self, binding: StepVariableBinding, ctx: ResolutionContext) -> str:
        if binding.source == "static":
            return binding.value or ""
        if binding.source == "customer_name":
            return ctx.customer_name
        if binding.source == "product_name":
            return ctx.product_name
        if binding.source == "contact_phone":
            return ctx.contact_phone
        if binding.source == "contact_email":
            return ctx.contact_email or ""
        raise ValueError(f"unknown source: {binding.source}")

    def resolve_all(self, raw: dict, ctx: ResolutionContext) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, raw_binding in raw.items():
            binding = StepVariableBinding.from_dict(raw_binding)
            out[key] = self.resolve(binding, ctx)
        return out
```

- [ ] **Step 5: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/unit/followup/test_variable_resolver.py -v
```

Expected: 8 PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/domain/value_objects/step_variable_binding.py apps/api/src/shared/application/use_cases/followup/variable_resolver.py apps/api/tests/unit/followup/test_variable_resolver.py
git commit -m "feat(followup): VariableResolver com 4 sources + static"
```

---

#### Task 8: Refatorar EnrollContact

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/followup/enroll_contact.py`
- Test: `apps/api/tests/unit/followup/test_enroll_contact.py` (atualizar)

- [ ] **Step 1: Atualizar testes**

Identifique os testes existentes em `tests/unit/followup/test_enroll_contact.py`. Substitua o setup e expectativas para refletir a nova assinatura: `execute()` recebe `flow_id`, `customer_name`, `product_name` (em vez de `product`).

```python
@pytest.mark.asyncio
async def test_enroll_creates_enrollment_with_snapshots():
    flow_repo = AsyncMock()
    enrollment_repo = AsyncMock()
    scheduler = AsyncMock()

    flow_repo.find_by_id.return_value = SimpleNamespace(id=uuid4(), name="F", is_active=True)
    flow_repo.get_steps.return_value = [
        SimpleNamespace(id=uuid4(), position=0, delay_from_purchase_hours=0,
                        meta_template_name="t", template_variables={}, message_text=None),
    ]
    enrollment_repo.create.return_value = SimpleNamespace(id=uuid4())

    uc = EnrollContact(flow_repo=flow_repo, enrollment_repo=enrollment_repo, scheduler=scheduler)
    purchase_time = datetime(2026, 5, 8, tzinfo=timezone.utc)

    result = await uc.execute(
        account_id=uuid4(), contact_id=uuid4(), conversation_id="conv1",
        contact_phone="+5511", purchase_id="p1",
        flow_id=uuid4(), customer_name="Fabio", product_name="Marketing 360",
        purchase_time=purchase_time,
    )
    assert result is not None
    enrollment_repo.create.assert_awaited_once()
    kwargs = enrollment_repo.create.call_args.kwargs
    assert kwargs["customer_name"] == "Fabio"
    assert kwargs["product_name"] == "Marketing 360"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd apps/api && uv run pytest tests/unit/followup/test_enroll_contact.py -v
```

Expected: TypeError ou AttributeError (assinatura mudou).

- [ ] **Step 3: Refatorar EnrollContact**

```python
# apps/api/src/shared/application/use_cases/followup/enroll_contact.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from shared.domain.entities.followup import FollowupEnrollment


@dataclass
class EnrollContact:
    flow_repo: object        # FollowupFlowRepository
    enrollment_repo: object  # FollowupEnrollmentRepository
    scheduler: object        # SchedulerPort

    async def execute(
        self,
        *,
        account_id: UUID,
        contact_id: UUID,
        conversation_id: str,
        contact_phone: str,
        purchase_id: str,
        flow_id: UUID,
        customer_name: str,
        product_name: str,
        purchase_time: datetime,
    ) -> FollowupEnrollment | None:
        flow = await self.flow_repo.find_by_id(flow_id)
        if flow is None or not flow.is_active:
            return None

        steps = await self.flow_repo.get_steps(flow_id)
        if not steps:
            return None

        enrollment = await self.enrollment_repo.create(
            account_id=account_id,
            flow_id=flow_id,
            contact_id=contact_id,
            conversation_id=conversation_id,
            contact_phone=contact_phone,
            purchase_id=purchase_id,
            customer_name=customer_name,
            product_name=product_name,
        )

        for step in steps:
            run_at = purchase_time + timedelta(hours=step.delay_from_purchase_hours)
            enrollment_step = await self.enrollment_repo.create_step(
                enrollment_id=enrollment.id,
                position=step.position,
                delay_from_purchase_hours=step.delay_from_purchase_hours,
                meta_template_name=step.meta_template_name,
                template_variables=step.template_variables,
                message_text=step.message_text,
            )
            job_id = await self.scheduler.schedule(
                kind="followup_step",
                run_at=run_at,
                payload={
                    "enrollment_step_id": str(enrollment_step.id),
                    "account_id": str(account_id),
                    "conversation_id": conversation_id,
                    "contact_phone": contact_phone,
                },
            )
            await self.enrollment_repo.set_scheduled_job(enrollment_step.id, job_id)

        return enrollment
```

> Se `FollowupFlowRepository` não tiver `find_by_id` ainda, adicione esse método (lookup direto via `session.get(FollowupFlowModel, flow_id)` retornando entity).

- [ ] **Step 4: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/unit/followup/test_enroll_contact.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/followup/enroll_contact.py apps/api/tests/unit/followup/test_enroll_contact.py apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py
git commit -m "refactor(uc): EnrollContact recebe flow_id direto e snapshots"
```

---

#### Task 9: Atualizar DispatchFollowupStep com VariableResolver

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py`

- [ ] **Step 1: Atualizar testes existentes**

Em `tests/unit/followup/test_dispatch_followup_step.py` (se existir; senão criar), garanta cobertura de:
- step com `template_variables = {"1": {"source": "customer_name"}}` e `enrollment.customer_name = "Fabio"` resolve para `{"1": "Fabio"}`.
- step com binding static resolve para o `value`.

```python
@pytest.mark.asyncio
async def test_dispatch_resolves_dynamic_variables():
    # arranja enrollment com snapshots
    enrollment = SimpleNamespace(
        id=uuid4(), customer_name="Fabio", product_name="Marketing 360",
        contact_phone="+5511", account_id=uuid4(),
    )
    contact = SimpleNamespace(email="fabio@example.com", phone=Phone("+5511"))
    enrollment_repo = AsyncMock()
    enrollment_repo.get_step.return_value = SimpleNamespace(
        id=uuid4(), enrollment_id=enrollment.id, position=0,
        meta_template_name="welcome",
        template_variables={"1": {"source": "customer_name"}, "2": {"source": "product_name"}},
        message_text=None, status="pending",
    )
    enrollment_repo.get_enrollment.return_value = enrollment
    contact_repo = AsyncMock()
    contact_repo.find_by_id.return_value = contact
    chatnexo = AsyncMock()
    template_repo = AsyncMock()
    template_repo.find_by_name.return_value = SimpleNamespace(
        name="welcome", language="pt_BR", media_url=None, media_kind=None, body="Olá {{1}} no curso {{2}}",
    )

    uc = DispatchFollowupStep(
        enrollment_repo=enrollment_repo, contact_repo=contact_repo,
        chatnexo=chatnexo, template_repo=template_repo,
    )
    await uc.execute(
        enrollment_step_id=uuid4(), account_id=enrollment.account_id,
        conversation_id="conv1", contact_phone="+5511",
    )
    sent_kwargs = chatnexo.send_template.call_args.kwargs
    assert sent_kwargs["variables"] == {"1": "Fabio", "2": "Marketing 360"}
```

- [ ] **Step 2: Implementar mudança**

No método `execute` de `DispatchFollowupStep`, depois de carregar o step e o enrollment, substituir o uso direto de `template_variables` pela resolução via resolver:

```python
from shared.application.use_cases.followup.variable_resolver import VariableResolver, ResolutionContext

# Dentro do execute():
contact = await self.contact_repo.find_by_id(enrollment.contact_id)
ctx = ResolutionContext(
    customer_name=enrollment.customer_name,
    product_name=enrollment.product_name,
    contact_phone=enrollment.contact_phone,
    contact_email=getattr(contact, "email", None),
)
resolved_vars = VariableResolver().resolve_all(step.template_variables or {}, ctx)
```

E depois passar `resolved_vars` (dict[str, str]) para `chatnexo.send_template(variables=resolved_vars, ...)`.

- [ ] **Step 3: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/unit/followup -v
```

Expected: tudo verde.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py apps/api/tests/unit/followup
git commit -m "refactor(uc): DispatchFollowupStep resolve variáveis dinâmicas via VariableResolver"
```

---

### Phase 3 — Cleanup Loja Express + refactor purchase_handler

#### Task 10: Refatorar purchase_handler (sem Loja Express)

**Files:**
- Modify: `apps/api/src/shared/application/purchase_handler.py`
- Test: `apps/api/tests/unit/application/test_purchase_handler.py` (atualizar)

- [ ] **Step 1: Atualizar testes**

```python
@pytest.mark.asyncio
async def test_purchase_with_known_course_enrolls_in_all_active_flows():
    course_repo = AsyncMock()
    flow_repo = AsyncMock()
    enroll_uc = AsyncMock()
    course_repo.find_active_by_hubla_id.return_value = SimpleNamespace(id=uuid4(), name="Mkt 360")
    flow_repo.list_active_by_course.return_value = [
        SimpleNamespace(id=uuid4()),
        SimpleNamespace(id=uuid4()),
    ]
    handler = PurchaseHandler(
        contact_repo=AsyncMock(), chatnexo=AsyncMock(),
        access_case_repo=AsyncMock(), scheduler=AsyncMock(),
        course_repo=course_repo, flow_repo=flow_repo, enroll_contact_uc=enroll_uc,
    )
    payload = build_payload(product_id="prod-123", customer_name="Fabio", product_name="Mkt 360")
    await handler.execute(payload)
    assert enroll_uc.execute.await_count == 2


@pytest.mark.asyncio
async def test_purchase_with_unknown_course_logs_warning_and_skips_enrollment(caplog):
    course_repo = AsyncMock()
    flow_repo = AsyncMock()
    enroll_uc = AsyncMock()
    course_repo.find_active_by_hubla_id.return_value = None
    handler = PurchaseHandler(
        contact_repo=AsyncMock(), chatnexo=AsyncMock(),
        access_case_repo=AsyncMock(), scheduler=AsyncMock(),
        course_repo=course_repo, flow_repo=flow_repo, enroll_contact_uc=enroll_uc,
    )
    await handler.execute(build_payload(product_id="prod-unknown"))
    enroll_uc.execute.assert_not_awaited()
    assert any("course not found" in r.message for r in caplog.records)
```

- [ ] **Step 2: Implementar refactor**

```python
# trecho relevante de purchase_handler.py
async def execute(self, payload):
    contact = await self._find_or_create_contact(payload)
    conversation_id = await self._open_conversation(contact, payload)

    course = await self.course_repo.find_active_by_hubla_id(payload.account_id, payload.product_id)
    if course is None:
        logger.warning("course not found", extra={"product_id": payload.product_id, "account_id": str(payload.account_id)})
    else:
        flows = await self.flow_repo.list_active_by_course(course.id)
        for flow in flows:
            await self.enroll_contact_uc.execute(
                account_id=payload.account_id,
                contact_id=contact.id,
                conversation_id=conversation_id,
                contact_phone=str(contact.phone),
                purchase_id=payload.purchase_id,
                flow_id=flow.id,
                customer_name=payload.customer_name,
                product_name=payload.product_name,
                purchase_time=payload.occurred_at,
            )

    # Mantém AccessCase + welcome template (lógica existente)
    await self.access_case_repo.create(...)
    await self.chatnexo.send_template(...)
```

Remover qualquer referência a `loja_express_case_repo`, `loja_express_port`, `criar_uc`, `loja_express_product_tags`. Atualizar a injeção do construtor:

```python
@dataclass
class PurchaseHandler:
    contact_repo: object
    chatnexo: object
    access_case_repo: object
    scheduler: object
    course_repo: object
    flow_repo: object
    enroll_contact_uc: object
```

- [ ] **Step 3: Atualizar DI no main.py / wherever PurchaseHandler is instantiated**

Localizar onde `PurchaseHandler` é construído (provavelmente em `apps/api/main.py` ou `interface/worker/handlers/handle_purchase.py`). Substituir kwargs antigos pelos novos (`course_repo`, `flow_repo`, `enroll_contact_uc`).

- [ ] **Step 4: Rodar testes**

```bash
cd apps/api && uv run pytest tests/unit/application -v
```

Expected: PASS (com testes atualizados).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/application/purchase_handler.py apps/api/tests/unit/application apps/api/main.py apps/api/src/interface/worker/handlers
git commit -m "refactor(purchase): lookup curso e enrollment N flows; remove branch Loja Express"
```

---

#### Task 11: Remover settings, configs e .env.example de Loja Express

**Files:**
- Modify: `apps/api/src/shared/config/settings.py`
- Modify: `apps/api/.env.example`

- [ ] **Step 1: Remover linhas em settings.py**

Apagar (linhas 64-69, comentário inclusive):
```python
# Capability Loja Express
loja_express_product_tags: list[str] = ["loja_express", "loja-express"]
loja_express_d1_delay_hours: int = 24
loja_express_d3_delay_hours: int = 72
loja_express_d5_delay_hours: int = 120
loja_express_d7_delay_hours: int = 168
```

- [ ] **Step 2: Remover de `.env.example`**

Procurar e remover qualquer linha com `LOJA_EXPRESS_` em `apps/api/.env.example`.

```bash
grep -n "LOJA_EXPRESS" apps/api/.env.example apps/api/.env.local 2>/dev/null
```

(Não tocar em `.env.local` direto — apenas reportar para o usuário se aparecer; ele remove manualmente.)

- [ ] **Step 3: Rodar testes para garantir que nada importa as configs**

```bash
cd apps/api && uv run pytest tests/unit/config -v && uv run ruff check src
```

Expected: PASS / sem erro de import.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/config/settings.py apps/api/.env.example
git commit -m "chore(config): remover settings LOJA_EXPRESS_*"
```

---

#### Task 12: Remover código fonte de Loja Express

**Files:**
- Delete: `apps/api/src/shared/application/use_cases/loja_express/` (diretório)
- Delete: `apps/api/src/shared/adapters/loja_express/` (diretório)
- Delete: `apps/api/src/shared/adapters/db/repositories/loja_express_case_repo.py`
- Delete: `apps/api/src/shared/domain/entities/loja_express_case.py`
- Delete: `apps/api/src/shared/domain/ports/loja_express_port.py`
- Delete: `apps/api/tests/**/*loja_express*`
- Modify: `apps/api/src/interface/worker/handlers/scheduled.py`

- [ ] **Step 1: Remover diretórios e arquivos**

```bash
cd apps/api
rm -rf src/shared/application/use_cases/loja_express
rm -rf src/shared/adapters/loja_express
rm src/shared/adapters/db/repositories/loja_express_case_repo.py
rm src/shared/domain/entities/loja_express_case.py
rm src/shared/domain/ports/loja_express_port.py
find tests -name "*loja_express*" -delete
```

- [ ] **Step 2: Remover handlers de scheduled.py**

Em `apps/api/src/interface/worker/handlers/scheduled.py`, apagar os ramos de `LOJA_EXPRESS_D1`, `D3`, `D5`, `D7` (e qualquer import correspondente).

- [ ] **Step 3: Buscar referências órfãs**

```bash
cd apps/api && grep -r "loja_express\|LojaExpress\|LOJA_EXPRESS" src tests --include="*.py" | head -30
```

Expected: vazio. Se houver matches, apagar/atualizar antes de prosseguir.

- [ ] **Step 4: Rodar gates**

```bash
cd apps/api && uv run ruff check src && uv run mypy src && uv run pytest tests/unit -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A apps/api
git commit -m "chore: remover capability Loja Express (vira curso comum)"
```

---

### Phase 4 — API

#### Task 13: Schemas + Router /admin/courses

**Files:**
- Create: `apps/api/src/interface/http/routers/admin/courses.py`
- Test: `apps/api/tests/integration/admin/test_courses_router.py`
- Modify: `apps/api/main.py` (registrar router)

- [ ] **Step 1: Escrever testes integration**

```python
# apps/api/tests/integration/admin/test_courses_router.py
import pytest
from uuid import uuid4

@pytest.mark.asyncio
async def test_create_course(client, admin_token):
    resp = await client.post(
        "/admin/courses",
        json={"name": "Marketing 360", "hubla_id": "prod-mkt-360"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Marketing 360"
    assert data["hubla_id"] == "prod-mkt-360"
    assert data["is_active"] is True
    assert data["flow_count"] == 0


@pytest.mark.asyncio
async def test_create_duplicate_returns_409(client, admin_token):
    body = {"name": "A", "hubla_id": "X"}
    await client.post("/admin/courses", json=body, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.post("/admin/courses", json=body, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_courses(client, admin_token):
    await client.post("/admin/courses", json={"name": "A", "hubla_id": "x1"}, headers={"Authorization": f"Bearer {admin_token}"})
    await client.post("/admin/courses", json={"name": "B", "hubla_id": "x2"}, headers={"Authorization": f"Bearer {admin_token}"})
    resp = await client.get("/admin/courses", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 2


@pytest.mark.asyncio
async def test_update_course(client, admin_token):
    create = await client.post("/admin/courses", json={"name": "Old", "hubla_id": "X"}, headers={"Authorization": f"Bearer {admin_token}"})
    cid = create.json()["id"]
    resp = await client.put(f"/admin/courses/{cid}", json={"name": "New"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New"


@pytest.mark.asyncio
async def test_delete_course_with_flow_returns_409(client, admin_token, seed_course_with_flow):
    cid, _ = seed_course_with_flow
    resp = await client.delete(f"/admin/courses/{cid}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_course_no_flows_returns_204(client, admin_token):
    create = await client.post("/admin/courses", json={"name": "x", "hubla_id": "y"}, headers={"Authorization": f"Bearer {admin_token}"})
    cid = create.json()["id"]
    resp = await client.delete(f"/admin/courses/{cid}", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 204
```

(Ajustar fixtures `client`, `admin_token`, `seed_course_with_flow` no `conftest.py` se ainda não existirem.)

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd apps/api && uv run pytest tests/integration/admin/test_courses_router.py -v
```

Expected: 404 (router não registrado).

- [ ] **Step 3: Implementar router**

```python
# apps/api/src/interface/http/routers/admin/courses.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from shared.adapters.db.repositories.course_repo import SqlCourseRepository
from shared.adapters.db.session import get_session
from interface.http.deps import require_admin

router = APIRouter(prefix="/admin/courses", tags=["admin", "courses"])


class CreateCourseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hubla_id: str = Field(min_length=1, max_length=200)
    is_active: bool = True


class UpdateCourseRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    hubla_id: str | None = Field(default=None, max_length=200)
    is_active: bool | None = None


class CourseResponse(BaseModel):
    id: UUID
    name: str
    hubla_id: str
    is_active: bool
    flow_count: int
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=list[CourseResponse])
async def list_courses(admin=Depends(require_admin), session=Depends(get_session)):
    repo = SqlCourseRepository(session)
    courses = await repo.list_by_account(admin.account_id)
    return [
        CourseResponse(
            id=c.id, name=c.name, hubla_id=c.hubla_id, is_active=c.is_active,
            flow_count=await repo.count_flows(c.id),
            created_at=c.created_at, updated_at=c.updated_at,
        )
        for c in courses
    ]


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(body: CreateCourseRequest, admin=Depends(require_admin), session=Depends(get_session)):
    repo = SqlCourseRepository(session)
    try:
        c = await repo.create(
            account_id=admin.account_id, name=body.name,
            hubla_id=body.hubla_id, is_active=body.is_active,
        )
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="course with hubla_id already exists")
    return CourseResponse(
        id=c.id, name=c.name, hubla_id=c.hubla_id, is_active=c.is_active,
        flow_count=0, created_at=c.created_at, updated_at=c.updated_at,
    )


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(course_id: UUID, body: UpdateCourseRequest, admin=Depends(require_admin), session=Depends(get_session)):
    repo = SqlCourseRepository(session)
    try:
        c = await repo.update(course_id, name=body.name, hubla_id=body.hubla_id, is_active=body.is_active)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=409, detail="course with hubla_id already exists")
    if c is None:
        raise HTTPException(status_code=404, detail="course not found")
    return CourseResponse(
        id=c.id, name=c.name, hubla_id=c.hubla_id, is_active=c.is_active,
        flow_count=await repo.count_flows(c.id),
        created_at=c.created_at, updated_at=c.updated_at,
    )


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(course_id: UUID, admin=Depends(require_admin), session=Depends(get_session)):
    repo = SqlCourseRepository(session)
    flow_count = await repo.count_flows(course_id)
    if flow_count > 0:
        raise HTTPException(status_code=409, detail=f"course has {flow_count} flow(s) linked")
    deleted = await repo.delete(course_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="course not found")
    await session.commit()
```

- [ ] **Step 4: Registrar router**

Em `apps/api/main.py` (ou onde os routers admin são incluídos):

```python
from interface.http.routers.admin import courses as admin_courses

app.include_router(admin_courses.router)
```

- [ ] **Step 5: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/integration/admin/test_courses_router.py -v
```

Expected: 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/interface/http/routers/admin/courses.py apps/api/tests/integration/admin/test_courses_router.py apps/api/main.py
git commit -m "feat(api): router /admin/courses (CRUD com 409 em hubla_id duplicado e flows vinculados)"
```

---

#### Task 14: Atualizar schemas + router /admin/followup

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/followup.py`

- [ ] **Step 1: Atualizar schemas Pydantic**

```python
class CreateFlowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    course_id: UUID
    is_active: bool = True


class UpdateFlowRequest(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    course_id: UUID | None = None
    is_active: bool | None = None


class CourseSummary(BaseModel):
    id: UUID
    name: str
    hubla_id: str


class FollowupFlowResponse(BaseModel):
    id: UUID
    name: str
    is_active: bool
    course: CourseSummary
    steps_count: int
    created_at: datetime
    updated_at: datetime


class StepVariableBindingDto(BaseModel):
    source: Literal["customer_name", "product_name", "contact_phone", "contact_email", "static"]
    value: str | None = None

    @model_validator(mode="after")
    def _check_value(self) -> "StepVariableBindingDto":
        if self.source == "static" and not self.value:
            raise ValueError("static binding requires non-empty value")
        if self.source != "static" and self.value is not None:
            raise ValueError("non-static binding must not include value")
        return self


class CreateStepRequest(BaseModel):
    delay_from_purchase_hours: int = Field(ge=0)
    meta_template_name: str | None = None
    template_variables: dict[str, StepVariableBindingDto] = Field(default_factory=dict)
    message_text: str | None = None

    @model_validator(mode="after")
    def _check_one_of(self) -> "CreateStepRequest":
        has_template = self.meta_template_name is not None
        has_text = self.message_text is not None
        if has_template == has_text:
            raise ValueError("exactly one of meta_template_name or message_text must be set")
        return self
```

- [ ] **Step 2: Adaptar handlers**

Substituir `find_active_by_product` por nada (esse endpoint é de admin, não chamado pelo handler). Atualizar `POST /flows` para validar que `course_id` pertence ao admin.account_id (404 se inexistente).

`PUT /flows/{id}/steps/{step_id}` e `POST /flows/{id}/steps`: aceitar `template_variables` no novo formato (dict de DTO). Persistir convertendo para dict cru: `{k: v.model_dump(exclude_none=True) for k, v in body.template_variables.items()}`.

- [ ] **Step 3: Remover `PATCH /admin/followup/flows/reorder`**

Apagar o endpoint inteiro do arquivo.

- [ ] **Step 4: Atualizar listagem**

`GET /flows` deve incluir `course` e `steps_count` no response. Implementação:

```python
@router.get("/flows", response_model=list[FollowupFlowResponse])
async def list_flows(admin=Depends(require_admin), session=Depends(get_session)):
    flow_repo = SqlFollowupFlowRepository(session)
    course_repo = SqlCourseRepository(session)
    flows = await flow_repo.list_flows(admin.account_id)
    out: list[FollowupFlowResponse] = []
    for f in flows:
        course = await course_repo.find_by_id(f.course_id)
        steps = await flow_repo.get_steps(f.id)
        out.append(FollowupFlowResponse(
            id=f.id, name=f.name, is_active=f.is_active,
            course=CourseSummary(id=course.id, name=course.name, hubla_id=course.hubla_id),
            steps_count=len(steps),
            created_at=f.created_at, updated_at=f.updated_at,
        ))
    return out
```

- [ ] **Step 5: Atualizar testes integration de followup**

Em `tests/integration/admin/test_followup_router.py`, ajustar:
- POST agora exige `course_id`.
- Listagem retorna `course` no response.
- Endpoint reorder removido (cobrir com 404 ou não testar).
- Steps com `template_variables` em formato novo.

- [ ] **Step 6: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/integration/admin/test_followup_router.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/interface/http/routers/admin/followup.py apps/api/tests/integration/admin/test_followup_router.py
git commit -m "feat(api): /admin/followup usa course_id e novo schema de template_variables"
```

---

#### Task 15: Atualizar PurchasePayload (webhook)

**Files:**
- Modify: `apps/api/src/interface/http/routers/webhook_purchase.py`

- [ ] **Step 1: Atualizar schema**

```python
class PurchasePayload(BaseModel):
    purchase_id: str
    account_id: int
    customer_name: str           # renomeado de `name`
    email: str
    phone: str
    document: str | None = None
    product_id: str              # NOVO — chave de match com Course.hubla_id
    product_name: str            # NOVO — snapshot pra variável dinâmica
    amount_brl: int
    occurred_at: str = Field(..., description="ISO 8601")
```

- [ ] **Step 2: Atualizar payload enfileirado**

Onde o handler enfileira o job, garantir que o dict salvo contenha as chaves novas. O `purchase_handler.execute` lê esses campos como `payload.customer_name`, `payload.product_id`, `payload.product_name`.

- [ ] **Step 3: Atualizar testes integration**

Em `tests/integration/test_webhook_purchase.py`, atualizar fixtures de body para usar campos novos:

```python
body = {
    "purchase_id": "p1", "account_id": 1,
    "customer_name": "Fabio", "email": "f@x.com", "phone": "+5511",
    "product_id": "prod-mkt-360", "product_name": "Marketing 360",
    "amount_brl": 9700, "occurred_at": "2026-05-08T10:00:00Z",
}
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/integration/test_webhook_purchase.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/interface/http/routers/webhook_purchase.py apps/api/tests/integration/test_webhook_purchase.py
git commit -m "feat(webhook): PurchasePayload com product_id/product_name/customer_name"
```

---

### Phase 5 — Seed do curso Loja Express

#### Task 16: Script de seed

**Files:**
- Create: `apps/api/scripts/seed_loja_express.py`

- [ ] **Step 1: Criar script**

```python
# apps/api/scripts/seed_loja_express.py
"""
Cria (idempotentemente) o curso "Loja Express" e um flow padrão com 5 steps
correspondendo aos delays históricos da capability descontinuada.

Uso:
  uv run python -m scripts.seed_loja_express <account_id> [--templates t0,t1,t3,t5,t7]
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from shared.adapters.db.session import get_sessionmaker
from shared.adapters.db.repositories.course_repo import SqlCourseRepository
from shared.adapters.db.repositories.followup_flow_repo import SqlFollowupFlowRepository

DEFAULT_TEMPLATES = [
    ("loja_express_d0", 0),
    ("loja_express_d1", 24),
    ("loja_express_d3", 72),
    ("loja_express_d5", 120),
    ("loja_express_d7", 168),
]


async def seed(account_id: UUID, templates: list[tuple[str, int]]) -> None:
    Session = get_sessionmaker()
    async with Session() as session:
        course_repo = SqlCourseRepository(session)
        flow_repo = SqlFollowupFlowRepository(session)

        existing = await course_repo.find_active_by_hubla_id(account_id, "loja-express")
        if existing is None:
            course = await course_repo.create(
                account_id=account_id,
                name="Loja Express",
                hubla_id="loja-express",
            )
            print(f"Created course {course.id} (Loja Express)")
        else:
            course = existing
            print(f"Course already exists: {course.id} (Loja Express) — skipping creation")

        flows = await flow_repo.list_active_by_course(course.id)
        if flows:
            print(f"Flow already exists for course; skipping seed of steps")
            await session.commit()
            return

        flow = await flow_repo.create_flow(
            account_id=account_id, course_id=course.id,
            name="Loja Express — sequência padrão", is_active=True,
        )
        for i, (template_name, hours) in enumerate(templates):
            await flow_repo.create_step(
                flow_id=flow.id, position=i,
                delay_from_purchase_hours=hours,
                meta_template_name=template_name,
                template_variables={"1": {"source": "customer_name"}},
                message_text=None,
            )
        await session.commit()
        print(f"Seeded flow {flow.id} with {len(templates)} steps")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("account_id", type=str, help="UUID da account")
    parser.add_argument(
        "--templates", type=str, default=None,
        help="CSV de nomes de templates (default: loja_express_d0..d7)",
    )
    args = parser.parse_args()

    if args.templates:
        names = args.templates.split(",")
        if len(names) != 5:
            raise SystemExit("--templates must have 5 entries")
        templates = list(zip(names, [0, 24, 72, 120, 168]))
    else:
        templates = DEFAULT_TEMPLATES

    asyncio.run(seed(UUID(args.account_id), templates))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

```bash
cd apps/api && uv run python -c "import scripts.seed_loja_express; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/scripts/seed_loja_express.py
git commit -m "chore(seed): script idempotente para curso Loja Express + flow padrão"
```

---

### Phase 6 — Frontend foundation

#### Task 17: Componente Drawer compartilhado

**Files:**
- Create: `apps/web/src/shared/components/Drawer.tsx`

- [ ] **Step 1: Criar componente**

```tsx
// apps/web/src/shared/components/Drawer.tsx
"use client";

import { useEffect, useRef } from "react";

interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}

const SIDEBAR_WIDTH = "var(--sidebar-width, 240px)";

export function Drawer({ open, onClose, title, children, footer }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  useEffect(() => {
    if (open) panelRef.current?.focus();
  }, [open]);

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden
        onClick={onClose}
        className={`fixed inset-y-0 right-0 z-40 bg-black/40 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
        style={{ left: SIDEBAR_WIDTH }}
      />

      {/* Painel */}
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={`fixed inset-y-0 right-0 z-50 flex flex-col bg-surface-container shadow-2xl transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        style={{ left: SIDEBAR_WIDTH }}
      >
        <header className="flex items-center justify-between border-b border-outline-variant px-6 py-4">
          <h2 className="text-lg font-semibold text-on-surface">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high"
            aria-label="Fechar"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </header>

        <div className="flex-1 overflow-auto px-6 py-6">{children}</div>

        {footer && (
          <footer className="border-t border-outline-variant px-6 py-4">
            {footer}
          </footer>
        )}
      </aside>
    </>
  );
}
```

- [ ] **Step 2: Garantir CSS variable da sidebar**

Em `apps/web/src/shared/components/layout/Sidebar.tsx` (ou no layout admin), confirmar que existe `--sidebar-width` no escopo. Se não houver, definir no root layout admin:

```css
:root {
  --sidebar-width: 240px;
}
```

(Se a sidebar atual usa Tailwind com largura fixa em `w-60` etc., apenas definir a variável CSS para o mesmo valor.)

- [ ] **Step 3: Smoke test rápido**

```bash
cd apps/web && npm run lint
```

Expected: sem warnings novos.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/shared/components/Drawer.tsx apps/web/src/shared/components/layout/Sidebar.tsx
git commit -m "feat(web): Drawer compartilhado (slide direita, encosta na sidebar)"
```

---

#### Task 18: Tipos TypeScript Course + API client

**Files:**
- Create: `apps/web/src/features/courses/types.ts`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Criar tipos**

```ts
// apps/web/src/features/courses/types.ts
export interface Course {
  id: string;
  name: string;
  hubla_id: string;
  is_active: boolean;
  flow_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateCourseInput {
  name: string;
  hubla_id: string;
  is_active?: boolean;
}

export interface UpdateCourseInput {
  name?: string;
  hubla_id?: string;
  is_active?: boolean;
}
```

- [ ] **Step 2: Adicionar funções ao api.ts**

```ts
// trecho a adicionar em apps/web/src/lib/api.ts
import { Course, CreateCourseInput, UpdateCourseInput } from "@/features/courses/types";

export async function listCourses(): Promise<Course[]> {
  return apiFetch("/admin/courses");
}

export async function createCourse(input: CreateCourseInput): Promise<Course> {
  return apiFetch("/admin/courses", { method: "POST", body: JSON.stringify(input) });
}

export async function updateCourse(id: string, input: UpdateCourseInput): Promise<Course> {
  return apiFetch(`/admin/courses/${id}`, { method: "PUT", body: JSON.stringify(input) });
}

export async function deleteCourse(id: string): Promise<void> {
  return apiFetch(`/admin/courses/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 3: Verificar typecheck**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: 0 erros.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/courses/types.ts apps/web/src/lib/api.ts
git commit -m "feat(web): tipos e api client de Courses"
```

---

### Phase 7 — Frontend Cursos

#### Task 19: Hook useCourses + CourseCard + CourseDrawer

**Files:**
- Create: `apps/web/src/features/courses/hooks/useCourses.ts`
- Create: `apps/web/src/features/courses/components/CourseCard.tsx`
- Create: `apps/web/src/features/courses/components/CourseDrawer.tsx`

- [ ] **Step 1: Hook useCourses**

```ts
// apps/web/src/features/courses/hooks/useCourses.ts
"use client";

import { useCallback, useEffect, useState } from "react";
import { listCourses, createCourse, updateCourse, deleteCourse } from "@/lib/api";
import { Course, CreateCourseInput, UpdateCourseInput } from "../types";

export function useCourses() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listCourses();
      setCourses(data);
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return {
    courses, loading, error, refresh,
    create: async (input: CreateCourseInput) => {
      const c = await createCourse(input);
      await refresh();
      return c;
    },
    update: async (id: string, input: UpdateCourseInput) => {
      const c = await updateCourse(id, input);
      await refresh();
      return c;
    },
    remove: async (id: string) => {
      await deleteCourse(id);
      await refresh();
    },
  };
}
```

- [ ] **Step 2: CourseCard**

```tsx
// apps/web/src/features/courses/components/CourseCard.tsx
"use client";

import { Course } from "../types";

interface Props {
  course: Course;
  onEdit: () => void;
  onDelete: () => void;
}

export function CourseCard({ course, onEdit, onDelete }: Props) {
  return (
    <article className="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container p-4">
      <div className="flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-on-surface">{course.name}</h3>
          {!course.is_active && (
            <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-xs text-on-surface-variant">
              Inativo
            </span>
          )}
        </div>
        <code className="text-xs text-on-surface-variant">{course.hubla_id}</code>
        <span className="text-xs text-on-surface-variant">
          {course.flow_count} follow-up{course.flow_count === 1 ? "" : "s"} vinculado{course.flow_count === 1 ? "" : "s"}
        </span>
      </div>
      <div className="flex gap-2">
        <button onClick={onEdit} className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high" aria-label="Editar">
          <span className="material-symbols-outlined">edit</span>
        </button>
        <button onClick={onDelete} className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high" aria-label="Excluir">
          <span className="material-symbols-outlined">delete</span>
        </button>
      </div>
    </article>
  );
}
```

- [ ] **Step 3: CourseDrawer**

```tsx
// apps/web/src/features/courses/components/CourseDrawer.tsx
"use client";

import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { Course, CreateCourseInput } from "../types";

interface Props {
  open: boolean;
  course: Course | null;
  onClose: () => void;
  onSubmit: (input: CreateCourseInput) => Promise<void>;
}

export function CourseDrawer({ open, course, onClose, onSubmit }: Props) {
  const [name, setName] = useState("");
  const [hublaId, setHublaId] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (course) {
      setName(course.name);
      setHublaId(course.hubla_id);
      setIsActive(course.is_active);
    } else {
      setName("");
      setHublaId("");
      setIsActive(true);
    }
  }, [course, open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({ name, hubla_id: hublaId, is_active: isActive });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={course ? `Editar curso — ${course.name}` : "Novo curso"}
      footer={
        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-md px-4 py-2 text-on-surface-variant hover:bg-surface-container-high">
            Cancelar
          </button>
          <button
            type="submit"
            form="course-form"
            disabled={submitting || !name || !hublaId}
            className="rounded-md bg-primary px-4 py-2 text-on-primary disabled:opacity-50"
          >
            {submitting ? "Salvando..." : "Salvar"}
          </button>
        </div>
      }
    >
      <form id="course-form" onSubmit={handleSubmit} className="flex flex-col gap-6">
        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium text-on-surface">Nome</span>
          <input
            type="text" value={name} onChange={(e) => setName(e.target.value)}
            className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-on-surface"
            placeholder="Ex: Marketing 360" required
          />
        </label>
        <label className="flex flex-col gap-2">
          <span className="text-sm font-medium text-on-surface">ID na Hubla</span>
          <input
            type="text" value={hublaId} onChange={(e) => setHublaId(e.target.value)}
            className="rounded-md border border-outline-variant bg-surface px-3 py-2 font-mono text-sm text-on-surface"
            placeholder="Ex: prod-mkt-360" required
          />
          <span className="text-xs text-on-surface-variant">
            Deve casar com o campo <code>product_id</code> que vem no webhook da Hubla.
          </span>
        </label>
        <label className="flex items-center gap-3">
          <input
            type="checkbox" checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="h-4 w-4"
          />
          <span className="text-sm text-on-surface">Curso ativo</span>
        </label>
      </form>
    </Drawer>
  );
}
```

- [ ] **Step 4: Lint e typecheck**

```bash
cd apps/web && npx tsc --noEmit && npm run lint
```

Expected: 0 erros.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/courses
git commit -m "feat(web): hook + CourseCard + CourseDrawer"
```

---

#### Task 20: Página /admin/courses + item na sidebar

**Files:**
- Create: `apps/web/src/app/(admin)/courses/page.tsx`
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`

- [ ] **Step 1: Criar página**

```tsx
// apps/web/src/app/(admin)/courses/page.tsx
"use client";

import { useState } from "react";
import { useCourses } from "@/features/courses/hooks/useCourses";
import { CourseCard } from "@/features/courses/components/CourseCard";
import { CourseDrawer } from "@/features/courses/components/CourseDrawer";
import { useToast } from "@/shared/hooks/useToast";
import { Course } from "@/features/courses/types";

export default function CoursesPage() {
  const { courses, loading, error, create, update, remove } = useCourses();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editing, setEditing] = useState<Course | null>(null);
  const toast = useToast();

  const openCreate = () => { setEditing(null); setDrawerOpen(true); };
  const openEdit = (c: Course) => { setEditing(c); setDrawerOpen(true); };

  const handleSubmit = async (input: { name: string; hubla_id: string; is_active?: boolean }) => {
    try {
      if (editing) {
        await update(editing.id, input);
        toast.success("Curso atualizado");
      } else {
        await create(input);
        toast.success("Curso criado");
      }
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("409")) {
        toast.error("Já existe curso com esse ID Hubla");
      } else {
        toast.error("Falha ao salvar curso", msg);
      }
      throw e;
    }
  };

  const handleDelete = async (c: Course) => {
    if (!confirm(`Remover o curso "${c.name}"?`)) return;
    try {
      await remove(c.id);
      toast.success("Curso removido");
    } catch (e) {
      const msg = (e as Error).message;
      if (msg.includes("409")) {
        toast.warning("Não é possível remover", "Existem follow-ups vinculados a este curso.");
      } else {
        toast.error("Falha ao remover", msg);
      }
    }
  };

  return (
    <div className="flex flex-col gap-6 p-8">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-on-surface">Cursos</h1>
          <p className="text-sm text-on-surface-variant">
            Cadastre os cursos vendidos para que os follow-ups possam ser disparados.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-on-primary"
        >
          <span className="material-symbols-outlined">add</span>
          Novo curso
        </button>
      </header>

      {loading && <p className="text-on-surface-variant">Carregando...</p>}
      {error && <p className="text-error">{error}</p>}
      {!loading && courses.length === 0 && (
        <div className="rounded-lg border border-dashed border-outline-variant p-8 text-center text-on-surface-variant">
          Nenhum curso cadastrado ainda.
        </div>
      )}

      <div className="flex flex-col gap-3">
        {courses.map((c) => (
          <CourseCard key={c.id} course={c} onEdit={() => openEdit(c)} onDelete={() => handleDelete(c)} />
        ))}
      </div>

      <CourseDrawer
        open={drawerOpen}
        course={editing}
        onClose={() => setDrawerOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
```

- [ ] **Step 2: Adicionar item na sidebar**

Em `apps/web/src/shared/components/layout/Sidebar.tsx`, no array `NAV_ITEMS`, adicionar entrada de Cursos antes de Follow-up:

```ts
const NAV_ITEMS = [
  { label: "Painel", href: "/dashboard", icon: "dashboard" },
  { label: "Base de Conhecimento", href: "/kb", icon: "database" },
  { label: "Contas", href: "/accounts", icon: "group" },
  { label: "Cursos", href: "/courses", icon: "school" },
  { label: "Follow-up", href: "/followup", icon: "schedule_send" },
  { label: "Templates", href: "/templates", icon: "sms" },
  { label: "Configurações", href: "/settings", icon: "settings", exact: true },
] as const;
```

- [ ] **Step 3: Smoke test no navegador**

```bash
cd apps/web && npm run dev
```

Acessar http://localhost:3000/courses, criar um curso de teste, verificar que aparece na lista, editar, excluir. Confirmar que o drawer entra da direita e encosta na linha da sidebar.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/\(admin\)/courses/page.tsx apps/web/src/shared/components/layout/Sidebar.tsx
git commit -m "feat(web): página /admin/courses + item na sidebar"
```

---

### Phase 8 — Frontend Follow-up refactor

#### Task 21: Atualizar tipos + API client de Followup

**Files:**
- Modify: `apps/web/src/features/followup/types.ts`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Atualizar types.ts**

```ts
// apps/web/src/features/followup/types.ts
export type StepVariableSource =
  | "customer_name" | "product_name" | "contact_phone" | "contact_email" | "static";

export interface StepVariableBinding {
  source: StepVariableSource;
  value?: string;
}

export interface FollowupStep {
  id: string;
  flow_id: string;
  position: number;
  delay_from_purchase_hours: number;
  meta_template_name: string | null;
  template_variables: Record<string, StepVariableBinding>;
  message_text: string | null;
}

export interface CourseSummary {
  id: string;
  name: string;
  hubla_id: string;
}

export interface FollowupFlow {
  id: string;
  name: string;
  is_active: boolean;
  course: CourseSummary;
  steps_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateFlowInput {
  name: string;
  course_id: string;
  is_active?: boolean;
}

export interface UpdateFlowInput {
  name?: string;
  course_id?: string;
  is_active?: boolean;
}

export interface CreateStepInput {
  delay_from_purchase_hours: number;
  meta_template_name?: string;
  template_variables?: Record<string, StepVariableBinding>;
  message_text?: string;
}
```

- [ ] **Step 2: Atualizar api.ts**

Em `apps/web/src/lib/api.ts`:
- Atualizar `createFollowupFlow`/`updateFollowupFlow` para usarem `CreateFlowInput` / `UpdateFlowInput`.
- Remover função `reorderFollowupFlows` se existir.
- Atualizar `createFollowupStep`/`updateFollowupStep` para `template_variables` no novo schema (apenas tipos — backend já aceita).

- [ ] **Step 3: Typecheck**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: erros aparecem em `FlowDrawer`, `StepInlineForm`, `FlowCard`, `page.tsx` por causa do schema novo. **Esses erros serão resolvidos nas próximas tasks** — pode commitar tipos e api antes.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/followup/types.ts apps/web/src/lib/api.ts
git commit -m "feat(web): tipos e api client atualizados para course_id e novo template_variables"
```

---

#### Task 22: StepVariableEditor

**Files:**
- Create: `apps/web/src/features/followup/components/StepVariableEditor.tsx`

- [ ] **Step 1: Criar componente**

```tsx
// apps/web/src/features/followup/components/StepVariableEditor.tsx
"use client";

import { StepVariableBinding, StepVariableSource } from "../types";

interface Props {
  templateBody: string | null;
  bindings: Record<string, StepVariableBinding>;
  onChange: (bindings: Record<string, StepVariableBinding>) => void;
}

const SOURCE_OPTIONS: Array<{ value: StepVariableSource; label: string }> = [
  { value: "customer_name", label: "Nome do aluno" },
  { value: "product_name", label: "Nome do curso" },
  { value: "contact_phone", label: "Telefone do aluno" },
  { value: "contact_email", label: "Email do aluno" },
  { value: "static", label: "Texto fixo..." },
];

function detectVariables(body: string | null): string[] {
  if (!body) return [];
  const matches = body.matchAll(/\{\{(\d+)\}\}/g);
  const set = new Set<string>();
  for (const m of matches) set.add(m[1]);
  return Array.from(set).sort((a, b) => Number(a) - Number(b));
}

export function StepVariableEditor({ templateBody, bindings, onChange }: Props) {
  const vars = detectVariables(templateBody);

  if (vars.length === 0) {
    return (
      <p className="text-xs text-on-surface-variant">
        Este template não tem variáveis dinâmicas.
      </p>
    );
  }

  const updateBinding = (key: string, patch: Partial<StepVariableBinding>) => {
    const current = bindings[key] ?? { source: "customer_name" };
    const next: StepVariableBinding = { ...current, ...patch };
    if (next.source !== "static") delete next.value;
    onChange({ ...bindings, [key]: next });
  };

  return (
    <div className="flex flex-col gap-3">
      {vars.map((key) => {
        const binding = bindings[key] ?? { source: "customer_name" as StepVariableSource };
        return (
          <div key={key} className="grid grid-cols-[80px_1fr] items-start gap-3">
            <label className="pt-2 text-sm font-medium text-on-surface">{`{{${key}}}`}</label>
            <div className="flex flex-col gap-2">
              <select
                value={binding.source}
                onChange={(e) => updateBinding(key, { source: e.target.value as StepVariableSource })}
                className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-on-surface"
              >
                {SOURCE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
              {binding.source === "static" && (
                <input
                  type="text"
                  value={binding.value ?? ""}
                  onChange={(e) => updateBinding(key, { value: e.target.value })}
                  placeholder="Texto fixo"
                  className="rounded-md border border-outline-variant bg-surface px-3 py-2 text-sm text-on-surface"
                />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

```bash
cd apps/web && npx tsc --noEmit src/features/followup/components/StepVariableEditor.tsx
```

Expected: 0 erros nesse arquivo.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/followup/components/StepVariableEditor.tsx
git commit -m "feat(web): StepVariableEditor (detecta {{N}} e mapeia para sources)"
```

---

#### Task 23: Refatorar StepInlineForm

**Files:**
- Modify: `apps/web/src/features/followup/components/StepInlineForm.tsx`

- [ ] **Step 1: Buscar template body por nome**

O form precisa, ao escolher um template Meta, recuperar o `body` do template para alimentar o `StepVariableEditor`. Reutilizar o hook/api existente para listar templates Meta — o body deve estar no objeto retornado por `listMetaTemplates`. Se não estiver, ajustar o backend (`apps/api/src/interface/http/routers/admin/meta_templates.py`) para incluir o `body` no response.

- [ ] **Step 2: Substituir input de variáveis cru pelo editor**

No arquivo `StepInlineForm.tsx`:
- Importar `StepVariableEditor` e tipos `StepVariableBinding`.
- Estado `templateVariables: Record<string, StepVariableBinding>`.
- Quando o usuário muda o `meta_template_name`, **resetar** `templateVariables` para `{}` (com confirmação se já tinha algo preenchido).
- Renderizar `<StepVariableEditor templateBody={selectedTemplate?.body ?? null} bindings={templateVariables} onChange={setTemplateVariables} />` apenas quando o usuário escolheu o modo "Template Meta".
- No submit, enviar `template_variables` no novo schema (já é o tipo correto).

- [ ] **Step 3: Typecheck**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: erros restantes são em `FlowDrawer`, `FlowCard`, `page.tsx` — próximos passos.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/followup/components/StepInlineForm.tsx apps/web/src/lib/api.ts apps/api/src/interface/http/routers/admin/meta_templates.py
git commit -m "feat(web): StepInlineForm integra StepVariableEditor"
```

---

#### Task 24: Refatorar FlowDrawer

**Files:**
- Modify: `apps/web/src/features/followup/components/FlowDrawer.tsx`

- [ ] **Step 1: Substituir modal por Drawer compartilhado**

Reescrever `FlowDrawer.tsx`:
- Importar `Drawer` de `@/shared/components/Drawer`.
- Remover toda a estilização de modal centralizado / scrim manual.
- Adicionar estado `courseId: string` e `useCourses()` para popular o select.
- Form principal:
  - Input nome.
  - Select de curso (obrigatório). Se `courses.length === 0`, mostrar mensagem com link para `/courses`.
  - Toggle ativo/inativo.
- Subseção de steps (lista + botão adicionar) abaixo do form principal — usar componentes existentes (`StepList`, `StepInlineForm`).
- Footer fixo: Cancelar / Salvar.

```tsx
// Esqueleto de referência
return (
  <Drawer open={open} onClose={onClose} title={flow ? `Editar — ${flow.name}` : "Novo follow-up"} footer={...}>
    <form id="flow-form" onSubmit={handleSubmit} className="flex flex-col gap-6">
      <input ... />
      <select value={courseId} onChange={...} required>
        <option value="" disabled>Selecione um curso</option>
        {courses.map(c => <option key={c.id} value={c.id}>{c.name} ({c.hubla_id})</option>)}
      </select>
      {courses.length === 0 && <p>Nenhum curso cadastrado. <Link href="/courses">Cadastre primeiro</Link></p>}
      <label><input type="checkbox" ... /> Ativo</label>
    </form>

    {flow && (
      <section className="mt-8">
        <h3>Steps</h3>
        <StepList flowId={flow.id} ... />
      </section>
    )}
  </Drawer>
);
```

- [ ] **Step 2: Typecheck**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: erros remanescentes em `FlowCard` e `page.tsx`.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/followup/components/FlowDrawer.tsx
git commit -m "refactor(web): FlowDrawer usa Drawer compartilhado e select de curso"
```

---

#### Task 25: Refatorar FlowCard + página /admin/followup

**Files:**
- Modify: `apps/web/src/features/followup/components/FlowCard.tsx`
- Modify: `apps/web/src/app/(admin)/followup/page.tsx`

- [ ] **Step 1: Atualizar FlowCard**

```tsx
// trecho relevante de FlowCard.tsx
<article className="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container p-4">
  <div className="flex flex-col gap-2">
    <div className="flex items-center gap-3">
      <h3 className="text-base font-semibold">{flow.name}</h3>
      {!flow.is_active && (
        <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-xs">Pausado</span>
      )}
    </div>
    <span className="inline-flex items-center gap-1 rounded-full bg-primary-container px-2 py-0.5 text-xs text-on-primary-container" title={flow.course.hubla_id}>
      <span className="material-symbols-outlined text-sm">school</span>
      {flow.course.name}
    </span>
    <span className="text-xs text-on-surface-variant">{flow.steps_count} step{flow.steps_count === 1 ? "" : "s"}</span>
  </div>
  <div className="flex gap-2">
    <button onClick={onToggle} aria-label="Ativar/Pausar"><span className="material-symbols-outlined">{flow.is_active ? "pause" : "play_arrow"}</span></button>
    <button onClick={onEdit} aria-label="Editar"><span className="material-symbols-outlined">edit</span></button>
    <button onClick={onDelete} aria-label="Excluir"><span className="material-symbols-outlined">delete</span></button>
  </div>
</article>
```

Remover qualquer prop/uso de `dragHandle` ou `useSortable`.

- [ ] **Step 2: Atualizar /admin/followup/page.tsx**

- Remover `DndContext`, `SortableContext`, `arrayMove`, todos os imports de `@dnd-kit`.
- Remover qualquer chamada a `reorderFollowupFlows`.
- Renderização vira lista simples:

```tsx
<div className="flex flex-col gap-3">
  {flows.map((f) => (
    <FlowCard key={f.id} flow={f} onEdit={...} onToggle={...} onDelete={...} />
  ))}
</div>
```

- [ ] **Step 3: Typecheck e lint**

```bash
cd apps/web && npx tsc --noEmit && npm run lint
```

Expected: 0 erros.

- [ ] **Step 4: Smoke test no navegador**

```bash
cd apps/web && npm run dev
```

Acessar http://localhost:3000/followup. Criar um flow de teste vinculado ao curso "Loja Express" cadastrado. Adicionar um step com template Meta que tenha variáveis e verificar que o editor renderiza um select por variável.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/features/followup/components/FlowCard.tsx apps/web/src/app/\(admin\)/followup/page.tsx
git commit -m "refactor(web): /admin/followup sem dnd externo; card mostra chip de curso"
```

---

### Phase 9 — Wrap up

#### Task 26: Atualizar CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Atualizar tabela de subsistemas**

Substituir a contagem de "11 subsistemas" por "10 subsistemas + 1 catálogo". Remover linha de Loja Express. Adicionar linha de Course Catalog.

- [ ] **Step 2: Atualizar tabela de tabelas DB**

Adicionar linha de `courses`. Remover linha de `loja_express_cases`. Atualizar descrição de `followup_flows` (sem `product_tags`/`position`, com `course_id`).

- [ ] **Step 3: Atualizar lista de endpoints**

Adicionar bloco `/admin/courses`. Remover `PATCH /admin/followup/flows/reorder`.

- [ ] **Step 4: Atualizar lista de jobs no worker**

Remover `scheduled_loja_express`.

- [ ] **Step 5: Atualizar settings**

Remover bloco de `LOJA_EXPRESS_*`.

- [ ] **Step 6: Atualizar branch info**

Atualizar a seção `Branch feat/dynamic-followup-meta-templates` com os pontos novos: course catalog, drawer compartilhado, variáveis dinâmicas em steps, fim da capability Loja Express.

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): atualiza para refletir Course catalog e fim de Loja Express"
```

---

#### Task 27: Gates locais e PR

**Files:** —

- [ ] **Step 1: Rodar todos os gates**

```bash
cd apps/api && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src && uv run pytest tests/unit -q
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```

Expected: tudo verde.

- [ ] **Step 2: Rodar testes integration**

```bash
cd apps/api && uv run pytest tests/integration -q
```

Expected: PASS (Postgres + Redis precisam estar rodando: `docker compose up postgres redis -d`).

- [ ] **Step 3: Smoke test E2E manual**

1. Subir API + worker + web localmente.
2. Criar curso "Loja Express" via UI (`/courses`).
3. Rodar `uv run python -m scripts.seed_loja_express <account_id>`.
4. Disparar webhook de compra simulado:

```bash
curl -X POST http://localhost:8000/webhook/purchase \
  -H "Content-Type: application/json" \
  -H "x-hubla-token: $HUBLA_WEBHOOK_SECRET" \
  -d '{
    "purchase_id": "test-001",
    "account_id": 1,
    "customer_name": "Fabio Test",
    "email": "fabio@test.com",
    "phone": "+5511999999999",
    "product_id": "loja-express",
    "product_name": "Loja Express",
    "amount_brl": 9700,
    "occurred_at": "2026-05-08T10:00:00Z"
  }'
```

5. Inspecionar `followup_enrollments` no banco — deve ter 1 enrollment para o curso Loja Express com `customer_name="Fabio Test"`, `product_name="Loja Express"` e 5 steps agendados em `followup_enrollment_steps`.

- [ ] **Step 4: Pedir code review (opcional)**

Invocar skill `superpowers:requesting-code-review` se desejar revisão multi-agente antes do PR.

- [ ] **Step 5: Push e abrir PR**

```bash
git push -u origin feat/dynamic-followup-meta-templates
gh pr create --title "feat: follow-up dinâmico por curso" --body "$(cat <<'EOF'
## Summary

- Nova entidade Course com CRUD + página /admin/courses
- FollowupFlow vincula-se a Course via FK; remove product_tags e ordenação externa
- Loja Express vira curso comum (drop da capability dedicada)
- Variáveis dinâmicas nos steps com 4 sources + texto fixo
- Drawer lateral compartilhado substitui modal centralizado
- Webhook Hubla estendido com product_id e product_name

## Test plan
- [ ] `pytest tests/unit` verde
- [ ] `pytest tests/integration` verde
- [ ] `tsc --noEmit` e `npm run lint` verdes
- [ ] `npm run build` ok
- [ ] Smoke test E2E: webhook → enrollment com snapshots e steps agendados
- [ ] Página /admin/courses funcional (CRUD + 409 ao excluir com flows vinculados)
- [ ] Página /admin/followup mostra chip do curso e drawer lateral funcional
- [ ] Editor de variáveis dinâmicas renderiza um campo por placeholder do template

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Commit final do plano (esta entrada)**

(Sem ação — o plano em si já está committado no início.)

---

## Summary of commits expected (~22 commits)

| # | Scope | Mensagem |
|---|-------|----------|
| 1 | domain | adicionar entity e port Course |
| 2 | db | adicionar CourseModel e refatorar followup; drop LojaExpressCaseModel |
| 3 | db | migration dynamic followup by course |
| 4 | repo | SqlCourseRepository com CRUD |
| 5 | repo | FollowupFlow usa course_id; remove product_tags |
| 6 | repo | snapshots customer_name/product_name em FollowupEnrollment |
| 7 | followup | VariableResolver com 4 sources + static |
| 8 | uc | EnrollContact recebe flow_id direto e snapshots |
| 9 | uc | DispatchFollowupStep resolve variáveis dinâmicas |
| 10 | purchase | refactor lookup curso e enrollment N flows |
| 11 | config | remover settings LOJA_EXPRESS_* |
| 12 | (chore) | remover capability Loja Express |
| 13 | api | router /admin/courses |
| 14 | api | /admin/followup com course_id |
| 15 | webhook | PurchasePayload com product_id |
| 16 | seed | script para curso Loja Express |
| 17 | web | Drawer compartilhado |
| 18 | web | tipos e api de Courses |
| 19 | web | hook + CourseCard + CourseDrawer |
| 20 | web | página /admin/courses + sidebar |
| 21 | web | tipos e api atualizados de Followup |
| 22 | web | StepVariableEditor |
| 23 | web | StepInlineForm integra editor |
| 24 | web | FlowDrawer com Drawer compartilhado |
| 25 | web | /admin/followup sem dnd externo |
| 26 | docs | atualiza CLAUDE.md |
| 27 | (PR) | abrir PR |
