# Multi-Atendentes ChatNexo + Rename Follow-up → Onboarding — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Suportar N chaves de API ChatNexo por conta (cada uma = um atendente com nome), selecionadas aleatoriamente nos disparos de onboarding e travadas por conversa quando o usuário responde; simultaneamente renomear toda a stack de "follow-up" para "onboarding".

**Architecture:** Tabela `chatnexo_agents` (UUID FK accounts.id, Fernet-encrypted api_key) + coluna `conversations.last_onboarding_agent_id`. `AgentSelectionStrategy` Protocol (SOLID O/C) com implementação `RandomAgentSelection`. Utilitário `build_chatnexo_client()` chamado nos três pontos de envio (message handler, scheduled/onboarding handler, lifecycle). O rename é feito primeiro para que todo código novo já use a nomenclatura correta.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 (async) / Alembic / Fernet / pytest + testcontainers; Next.js 15 / TypeScript / Tailwind

---

## Mapa de Arquivos

### PARTE 1 — Rename

| Ação | Arquivo |
|---|---|
| Criar migration | `apps/api/migrations/versions/<rev>_rename_followup_to_onboarding.py` |
| Renomear (git mv) | `apps/api/src/shared/domain/entities/followup.py` → `onboarding.py` |
| Modificar | `apps/api/src/shared/adapters/db/models.py` — 4 classes e __tablename__ |
| Renomear (git mv) | `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py` → `onboarding_flow_repo.py` |
| Renomear (git mv) | `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py` → `onboarding_enrollment_repo.py` |
| Renomear (git mv) | `apps/api/src/shared/application/use_cases/followup/` → `use_cases/onboarding/` |
| Renomear (git mv) | `apps/api/src/interface/http/schemas/followup.py` → `schemas/onboarding.py` |
| Renomear (git mv) | `apps/api/src/interface/http/routers/admin/followup.py` → `onboarding.py` |
| Renomear (git mv) | `apps/api/src/interface/http/routers/admin/followup_enrollments.py` → `onboarding_enrollments.py` |
| Modificar | `apps/api/src/main.py` — imports e router registrations |
| Modificar | `apps/api/src/interface/worker/handlers/scheduled.py` — import paths |
| Modificar | `apps/api/src/interface/worker/handlers/hubla_event.py` — import paths |
| Modificar | `apps/api/src/interface/worker/handlers/resync.py` — import paths |
| Renomear test | `apps/api/tests/unit/test_followup_flow_repo_trigger.py` → `test_onboarding_flow_repo_trigger.py` |
| Renomear test | `apps/api/tests/unit/test_followup_schemas_trigger.py` → `test_onboarding_schemas_trigger.py` |
| Modificar tests | Todos os demais arquivos de teste que importam de `followup` |
| Renomear (git mv) | `apps/web/src/features/followup/` → `features/onboarding/` |
| Criar | `apps/web/src/app/(admin)/onboarding/page.tsx` |
| Criar | `apps/web/src/app/(admin)/onboarding/[id]/page.tsx` |
| Criar | `apps/web/src/app/(admin)/followup/page.tsx` — redirect 301 |
| Modificar | `apps/web/src/lib/api.ts` — renomear funções |
| Modificar | `apps/web/src/shared/components/layout/Sidebar.tsx` |

### PARTE 2 — Multi-Atendentes

| Ação | Arquivo |
|---|---|
| Criar migration | `apps/api/migrations/versions/<rev>_add_chatnexo_agents.py` |
| Criar | `apps/api/src/shared/domain/entities/chatnexo_agent.py` |
| Criar | `apps/api/src/shared/domain/ports/agent_selection.py` |
| Criar | `apps/api/src/shared/domain/ports/chatnexo_agent_repo.py` |
| Modificar | `apps/api/src/shared/domain/entities/account_config.py` — adicionar campo |
| Modificar | `apps/api/src/shared/adapters/db/models.py` — adicionar ChatNexoAgentModel |
| Modificar | `apps/api/src/shared/adapters/chatnexo/client.py` — adicionar with_key() |
| Criar | `apps/api/src/shared/adapters/chatnexo/agent_picker.py` |
| Criar | `apps/api/src/shared/adapters/agent_selection/__init__.py` |
| Criar | `apps/api/src/shared/adapters/agent_selection/random_selection.py` |
| Criar | `apps/api/src/shared/adapters/db/repositories/chatnexo_agent_repo.py` |
| Modificar | `apps/api/src/shared/adapters/db/repositories/conversation.py` — 2 métodos |
| Modificar | `apps/api/src/shared/adapters/db/repositories/account_config_repo.py` — load agents |
| Modificar | `apps/api/src/interface/worker/handlers/message.py` |
| Modificar | `apps/api/src/interface/worker/handlers/scheduled.py` |
| Modificar | `apps/api/src/shared/application/lifecycle_handler.py` |
| Criar | `apps/api/src/interface/http/routers/admin/chatnexo_agents.py` |
| Modificar | `apps/api/src/main.py` — registrar router |
| Criar | `apps/api/tests/unit/chatnexo/test_agent_picker.py` |
| Criar | `apps/api/tests/integration/test_chatnexo_agent_repo.py` |
| Modificar | `apps/web/src/lib/api.ts` — funções novas |
| Criar | `apps/web/src/features/settings/components/ChatNexoAgentsSection.tsx` |
| Modificar | `apps/web/src/app/(admin)/settings/page.tsx` — incluir seção |

---

## PARTE 1 — Rename Follow-up → Onboarding

---

### Task 1: Migration — renomear 4 tabelas

**Files:**
- Create: `apps/api/migrations/versions/<rev>_rename_followup_to_onboarding.py`

- [ ] **Step 1: Gerar arquivo de migration**

```bash
cd apps/api
uv run alembic revision --message "rename_followup_to_onboarding"
```

Isso cria um arquivo com `revision = "<hash_gerado>"` e `down_revision = "64664593d802"`. Abra o arquivo gerado e substitua o conteúdo por:

```python
"""rename followup to onboarding tables

Revision ID: <hash_gerado_pelo_alembic>
Revises: 64664593d802
Create Date: 2026-05-25
"""
from __future__ import annotations

from alembic import op


revision = "<hash_gerado_pelo_alembic>"
down_revision = "64664593d802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table("followup_flows", "onboarding_flows")
    op.rename_table("followup_steps", "onboarding_steps")
    op.rename_table("followup_enrollments", "onboarding_enrollments")
    op.rename_table("followup_enrollment_steps", "onboarding_enrollment_steps")

    # Renomear índice de steps
    op.execute(
        "ALTER INDEX ix_followup_steps_flow_position "
        "RENAME TO ix_onboarding_steps_flow_position"
    )

    # Atualizar FKs cujo nome referencia o nome da tabela origem
    # O PostgreSQL atualiza automaticamente as FKs ao renomear tabelas,
    # mas o nome do constraint permanece com o nome antigo. Renomear para
    # manter consistência com os modelos SQLAlchemy.
    op.execute(
        "ALTER TABLE onboarding_steps "
        "RENAME CONSTRAINT followup_steps_flow_id_fkey "
        "TO onboarding_steps_flow_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollments "
        "RENAME CONSTRAINT followup_enrollments_flow_id_fkey "
        "TO onboarding_enrollments_flow_id_fkey"
    )
    op.execute(
        "ALTER TABLE onboarding_enrollment_steps "
        "RENAME CONSTRAINT followup_enrollment_steps_enrollment_id_fkey "
        "TO onboarding_enrollment_steps_enrollment_id_fkey"
    )


def downgrade() -> None:
    op.rename_table("onboarding_enrollment_steps", "followup_enrollment_steps")
    op.rename_table("onboarding_enrollments", "followup_enrollments")
    op.rename_table("onboarding_steps", "followup_steps")
    op.rename_table("onboarding_flows", "followup_flows")

    op.execute(
        "ALTER INDEX ix_onboarding_steps_flow_position "
        "RENAME TO ix_followup_steps_flow_position"
    )
```

> **Nota:** Os nomes de FK variam conforme a migration original. Se `upgrade()` falhar com "constraint not found", inspecione com `\d onboarding_steps` no psql e ajuste os nomes. As FKs podem ter sido nomeadas automaticamente pelo PostgreSQL — o padrão é `<tabela>_<coluna>_fkey`.

- [ ] **Step 2: Aplicar migration**

```bash
cd apps/api
uv run alembic upgrade heads
```

Esperado: `Running upgrade 64664593d802 -> <hash>, rename_followup_to_onboarding tables`

- [ ] **Step 3: Verificar no DB**

```bash
uv run python -c "
import asyncio
from shared.adapters.db.session import create_engine
from sqlalchemy import text
async def check():
    from shared.config.settings import get_settings
    s = get_settings()
    engine = create_engine(s.database_url)
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT tablename FROM pg_tables WHERE tablename LIKE 'onboarding%'\"))
        for row in result:
            print(row[0])
asyncio.run(check())
"
```

Esperado: 4 linhas com `onboarding_flows`, `onboarding_steps`, `onboarding_enrollments`, `onboarding_enrollment_steps`.

- [ ] **Step 4: Commit**

```bash
git add apps/api/migrations/versions/
git commit -m "feat(db): renomear tabelas followup_ → onboarding_"
```

---

### Task 2: models.py — renomear 4 classes SQLAlchemy

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`

- [ ] **Step 1: Renomear classes e __tablename__ no models.py**

No arquivo `apps/api/src/shared/adapters/db/models.py`, execute as substituições:

```python
# Linha ~480: FollowupFlowModel → OnboardingFlowModel
class OnboardingFlowModel(Base):
    __tablename__ = "onboarding_flows"
    # ... resto inalterado

# Linha ~511: FollowupStepModel → OnboardingStepModel
class OnboardingStepModel(Base):
    __tablename__ = "onboarding_steps"
    id: Mapped[uuid.UUID] = _pk()
    flow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_flows.id"), nullable=False, index=True
    )
    # ... resto inalterado
    __table_args__ = (Index("ix_onboarding_steps_flow_position", "flow_id", "position"),)

# Linha ~528: FollowupEnrollmentModel → OnboardingEnrollmentModel
class OnboardingEnrollmentModel(Base):
    __tablename__ = "onboarding_enrollments"
    id: Mapped[uuid.UUID] = _pk()
    # ...
    flow_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("onboarding_flows.id", ondelete="SET NULL"),
        nullable=True,
    )
    # ... resto inalterado

# Linha ~553: FollowupEnrollmentStepModel → OnboardingEnrollmentStepModel
class OnboardingEnrollmentStepModel(Base):
    __tablename__ = "onboarding_enrollment_steps"
    id: Mapped[uuid.UUID] = _pk()
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("onboarding_enrollments.id"), nullable=False, index=True
    )
    # ... resto inalterado
```

- [ ] **Step 2: Checar que não sobrou nenhuma referência às classes antigas**

```bash
grep -n "FollowupFlowModel\|FollowupStepModel\|FollowupEnrollmentModel\|FollowupEnrollmentStepModel" apps/api/src/shared/adapters/db/models.py
```

Esperado: 0 linhas.

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/shared/adapters/db/models.py
git commit -m "refactor: renomear SQLAlchemy models followup → onboarding"
```

---

### Task 3: Renomear entidade de domínio followup.py → onboarding.py

**Files:**
- Rename: `apps/api/src/shared/domain/entities/followup.py` → `onboarding.py`

- [ ] **Step 1: Renomear arquivo e atualizar nomes de classes**

```bash
git mv apps/api/src/shared/domain/entities/followup.py \
       apps/api/src/shared/domain/entities/onboarding.py
```

No arquivo `apps/api/src/shared/domain/entities/onboarding.py`, renomear:

```python
# Antes → Depois
class FollowupFlow      → class OnboardingFlow
class FollowupStep      → class OnboardingStep
class FollowupEnrollment → class OnboardingEnrollment
class FollowupEnrollmentStep → class OnboardingEnrollmentStep
# EnrollmentStatus e EnrollmentStepStatus: manter nomes (não têm "Followup")
```

Exemplo do início do arquivo após rename:

```python
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
    CANCELLED = "cancelled"


@dataclass(slots=True)
class OnboardingFlow:
    id: UUID
    account_id: UUID
    product_id: UUID
    name: str
    trigger_event_type: str = "subscription.activated"
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class OnboardingStep:
    id: UUID
    flow_id: UUID
    position: int
    delay_from_purchase_minutes: int
    meta_template_name: str | None
    template_variables: dict
    created_at: datetime
    message_text: str | None = None


@dataclass(slots=True)
class OnboardingEnrollment:
    account_id: UUID
    flow_id: UUID | None
    contact_id: UUID
    conversation_id: str
    contact_phone: str
    purchase_id: str
    customer_name: str
    product_name: str
    id: UUID = field(default_factory=uuid4)
    status: EnrollmentStatus = EnrollmentStatus.ACTIVE
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    purchase_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    steps: list = field(default_factory=list)


@dataclass(slots=True)
class OnboardingEnrollmentStep:
    enrollment_id: UUID
    position: int
    delay_from_purchase_minutes: int
    meta_template_name: str | None
    template_variables: dict
    id: UUID = field(default_factory=uuid4)
    scheduled_job_id: UUID | None = None
    status: EnrollmentStepStatus = EnrollmentStepStatus.PENDING
    sent_at: datetime | None = None
    message_text: str | None = None
    failure_reason: str | None = None
    flow_step_id: UUID | None = None
```

- [ ] **Step 2: Atualizar imports em todos os arquivos que importam de followup**

```bash
grep -rn "from shared.domain.entities.followup import\|from shared.domain.entities import followup" \
     apps/api/src/ apps/api/tests/ | grep -v __pycache__
```

Para cada arquivo encontrado, substituir `shared.domain.entities.followup` por `shared.domain.entities.onboarding` e as classes pelo novo nome.

Arquivos esperados (verificar com grep acima):
- `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py` (será renomeado na Task 4)
- `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py` (será renomeado na Task 4)
- `apps/api/src/shared/application/use_cases/followup/*.py` (será renomeado na Task 5)
- `apps/api/src/interface/http/schemas/followup.py` (será renomeado na Task 6)
- Arquivos de teste

- [ ] **Step 3: Verificar sem referências residuais**

```bash
grep -rn "entities.followup\|FollowupFlow\|FollowupStep\|FollowupEnrollment" \
     apps/api/src/ apps/api/tests/ | grep -v __pycache__
```

Esperado: 0 linhas (ou apenas nos arquivos que serão renomeados nas próximas tasks).

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/domain/entities/
git commit -m "refactor: renomear entities followup → onboarding"
```

---

### Task 4: Renomear repositórios

**Files:**
- Rename: `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py` → `onboarding_flow_repo.py`
- Rename: `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py` → `onboarding_enrollment_repo.py`

- [ ] **Step 1: Renomear arquivos**

```bash
git mv apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py \
       apps/api/src/shared/adapters/db/repositories/onboarding_flow_repo.py

git mv apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py \
       apps/api/src/shared/adapters/db/repositories/onboarding_enrollment_repo.py
```

- [ ] **Step 2: Atualizar imports e nomes de classe em onboarding_flow_repo.py**

No topo do arquivo, substituir:

```python
# Antes:
from shared.adapters.db.models import (
    FollowupEnrollmentModel,
    FollowupFlowModel,
    FollowupStepModel,
)
from shared.domain.entities.followup import FollowupFlow, FollowupStep

# Depois:
from shared.adapters.db.models import (
    OnboardingEnrollmentModel,
    OnboardingFlowModel,
    OnboardingStepModel,
)
from shared.domain.entities.onboarding import OnboardingFlow, OnboardingStep
```

Renomear a classe do repositório e as funções helper:

```python
# Antes:
def _flow_to_entity(m: FollowupFlowModel) -> FollowupFlow:
    return FollowupFlow(...)

def _step_to_entity(m: FollowupStepModel) -> FollowupStep:
    return FollowupStep(...)

@dataclass
class FollowupFlowRepository:
    ...

# Depois:
def _flow_to_entity(m: OnboardingFlowModel) -> OnboardingFlow:
    return OnboardingFlow(...)

def _step_to_entity(m: OnboardingStepModel) -> OnboardingStep:
    return OnboardingStep(...)

@dataclass
class OnboardingFlowRepository:
    ...
```

Substituir todos os usos de `FollowupFlowModel` → `OnboardingFlowModel`, `FollowupStepModel` → `OnboardingStepModel` dentro do arquivo.

- [ ] **Step 3: Atualizar imports e nomes de classe em onboarding_enrollment_repo.py**

Mesma lógica: substituir `FollowupEnrollmentModel` → `OnboardingEnrollmentModel`, `FollowupEnrollmentStepModel` → `OnboardingEnrollmentStepModel`, `FollowupEnrollment*` → `OnboardingEnrollment*` nos imports e nos type hints.

```python
# Antes:
from shared.adapters.db.models import FollowupEnrollmentModel, FollowupEnrollmentStepModel
from shared.domain.entities.followup import (
    FollowupEnrollment, FollowupEnrollmentStep, EnrollmentStatus, EnrollmentStepStatus
)

@dataclass
class FollowupEnrollmentRepository:
    ...

# Depois:
from shared.adapters.db.models import OnboardingEnrollmentModel, OnboardingEnrollmentStepModel
from shared.domain.entities.onboarding import (
    OnboardingEnrollment, OnboardingEnrollmentStep, EnrollmentStatus, EnrollmentStepStatus
)

@dataclass
class OnboardingEnrollmentRepository:
    ...
```

- [ ] **Step 4: Atualizar referências em outros arquivos**

```bash
grep -rn "followup_flow_repo\|followup_enrollment_repo\|FollowupFlowRepository\|FollowupEnrollmentRepository" \
     apps/api/src/ apps/api/tests/ | grep -v __pycache__
```

Substituir em cada arquivo encontrado:
- `followup_flow_repo` → `onboarding_flow_repo`
- `followup_enrollment_repo` → `onboarding_enrollment_repo`
- `FollowupFlowRepository` → `OnboardingFlowRepository`
- `FollowupEnrollmentRepository` → `OnboardingEnrollmentRepository`

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/
git commit -m "refactor: renomear repos followup → onboarding"
```

---

### Task 5: Renomear use cases

**Files:**
- Rename dir: `apps/api/src/shared/application/use_cases/followup/` → `use_cases/onboarding/`

- [ ] **Step 1: Renomear diretório**

```bash
git mv apps/api/src/shared/application/use_cases/followup \
       apps/api/src/shared/application/use_cases/onboarding
```

- [ ] **Step 2: Renomear classe DispatchFollowupStep → DispatchOnboardingStep**

No arquivo `apps/api/src/shared/application/use_cases/onboarding/dispatch_followup_step.py`:
- Renomear o arquivo: `git mv ... dispatch_onboarding_step.py`
- Renomear a classe `DispatchFollowupStep` → `DispatchOnboardingStep`
- Atualizar imports internos de `followup` → `onboarding`

```bash
git mv apps/api/src/shared/application/use_cases/onboarding/dispatch_followup_step.py \
       apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py
```

No arquivo, substituir:
```python
# Antes:
from shared.domain.entities.followup import EnrollmentStatus, EnrollmentStepStatus

class DispatchFollowupStep:
    ...

# Depois:
from shared.domain.entities.onboarding import EnrollmentStatus, EnrollmentStepStatus

class DispatchOnboardingStep:
    ...
```

- [ ] **Step 3: Atualizar imports dos outros use cases**

Em `enroll_contact.py`, `resync_enrollment.py`, `diff_flow_steps.py`, `variable_resolver.py`:
- Substituir `from shared.domain.entities.followup import` → `from shared.domain.entities.onboarding import`
- Substituir `FollowupFlow` → `OnboardingFlow`, `FollowupStep` → `OnboardingStep`, etc.

- [ ] **Step 4: Atualizar referências externas**

```bash
grep -rn "use_cases.followup\|DispatchFollowupStep\|from shared.application.use_cases.followup" \
     apps/api/src/ apps/api/tests/ | grep -v __pycache__
```

Para cada arquivo, atualizar imports:
```python
# Antes:
from shared.application.use_cases.followup.dispatch_followup_step import DispatchFollowupStep
from shared.application.use_cases.followup.enroll_contact import EnrollContact

# Depois:
from shared.application.use_cases.onboarding.dispatch_onboarding_step import DispatchOnboardingStep
from shared.application.use_cases.onboarding.enroll_contact import EnrollContact
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/application/use_cases/
git commit -m "refactor: renomear use_cases/followup → use_cases/onboarding"
```

---

### Task 6: Renomear schemas + routers + atualizar main.py

**Files:**
- Rename: `apps/api/src/interface/http/schemas/followup.py` → `onboarding.py`
- Rename: `apps/api/src/interface/http/routers/admin/followup.py` → `onboarding.py`
- Rename: `apps/api/src/interface/http/routers/admin/followup_enrollments.py` → `onboarding_enrollments.py`
- Modify: `apps/api/src/main.py`

- [ ] **Step 1: Renomear schemas**

```bash
git mv apps/api/src/interface/http/schemas/followup.py \
       apps/api/src/interface/http/schemas/onboarding.py
```

No arquivo renomeado, substituir nomes de classes Pydantic e rotas:

```python
# Antes → Depois (nomes de classes Pydantic)
FollowupFlowResponse    → OnboardingFlowResponse
FollowupStepResponse    → OnboardingStepResponse
FollowupFlowStats       → OnboardingFlowStats
CreateFlowRequest       → mantido (genérico)
UpdateFlowRequest       → mantido
CreateStepRequest       → mantido
UpdateStepRequest       → mantido
```

- [ ] **Step 2: Renomear routers**

```bash
git mv apps/api/src/interface/http/routers/admin/followup.py \
       apps/api/src/interface/http/routers/admin/onboarding.py

git mv apps/api/src/interface/http/routers/admin/followup_enrollments.py \
       apps/api/src/interface/http/routers/admin/onboarding_enrollments.py
```

Em `onboarding.py` (router), atualizar:

```python
# Imports dos schemas:
from interface.http.schemas.onboarding import (
    CreateFlowRequest,
    CreateStepRequest,
    OnboardingFlowResponse,
    OnboardingFlowStats,
    OnboardingStepResponse,
    ProductSummary,
    ReorderStepsRequest,
    StepVariableBindingDto,
    UpdateFlowRequest,
    UpdateStepRequest,
)

# Imports dos repos:
from shared.adapters.db.repositories.onboarding_flow_repo import OnboardingFlowRepository

# Tag do router:
router = APIRouter(tags=["admin-onboarding"])

# Rotas: substituir /followup/ por /onboarding/
# Ex: @router.get("/followup/flows") → @router.get("/onboarding/flows")
# Ex: @router.get("/followup/flows/{id}/steps") → @router.get("/onboarding/flows/{id}/steps")
```

Em `onboarding_enrollments.py` (router), mesma lógica para rotas `/onboarding/enrollments/`.

- [ ] **Step 3: Atualizar main.py**

```python
# apps/api/src/main.py — substituir imports e router registrations:

# Antes:
from interface.http.routers.admin import followup as admin_followup
from interface.http.routers.admin import (
    followup_enrollments as admin_followup_enrollments,
)

# Depois:
from interface.http.routers.admin import onboarding as admin_onboarding
from interface.http.routers.admin import (
    onboarding_enrollments as admin_onboarding_enrollments,
)

# E nos include_router:
# Antes:
app.include_router(admin_followup.router, prefix="/admin")
app.include_router(admin_followup_enrollments.router, prefix="/admin")

# Depois:
app.include_router(admin_onboarding.router, prefix="/admin")
app.include_router(admin_onboarding_enrollments.router, prefix="/admin")
```

- [ ] **Step 4: Verificar sem referências residuais ao followup nos routers**

```bash
grep -rn "from interface.http.routers.admin import followup\|from interface.http.schemas.followup" \
     apps/api/src/ | grep -v __pycache__
```

Esperado: 0 linhas.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/interface/http/
git add apps/api/src/main.py
git commit -m "refactor: renomear schemas e routers followup → onboarding"
```

---

### Task 7: Atualizar handlers e testes de backend

**Files:**
- Modify: `apps/api/src/interface/worker/handlers/scheduled.py`
- Modify: `apps/api/src/interface/worker/handlers/hubla_event.py`
- Modify: `apps/api/src/interface/worker/handlers/resync.py`
- Rename tests

- [ ] **Step 1: Atualizar handlers**

Em `scheduled.py`, substituir:

```python
# Antes:
from shared.adapters.db.repositories.followup_enrollment_repo import (
    FollowupEnrollmentRepository,
)
from shared.application.use_cases.followup.dispatch_followup_step import (
    DispatchFollowupStep,
)
from shared.domain.entities.followup import EnrollmentStepStatus

# Depois:
from shared.adapters.db.repositories.onboarding_enrollment_repo import (
    OnboardingEnrollmentRepository,
)
from shared.application.use_cases.onboarding.dispatch_onboarding_step import (
    DispatchOnboardingStep,
)
from shared.domain.entities.onboarding import EnrollmentStepStatus
```

No corpo do handler, substituir `FollowupEnrollmentRepository` → `OnboardingEnrollmentRepository`, `DispatchFollowupStep` → `DispatchOnboardingStep`.

Manter o handler aceitando `job_type in ("followup_step", "onboarding_step")`:

```python
elif job_type in ("followup_step", "onboarding_step"):
    ...  # mesmo bloco de código
```

Em `hubla_event.py` e `resync.py`, mesma lógica de substituição de imports.

- [ ] **Step 2: Renomear arquivos de teste**

```bash
cd apps/api

git mv tests/unit/test_followup_flow_repo_trigger.py \
       tests/unit/test_onboarding_flow_repo_trigger.py

git mv tests/unit/test_followup_schemas_trigger.py \
       tests/unit/test_onboarding_schemas_trigger.py
```

Em cada arquivo renomeado, atualizar imports internos.

- [ ] **Step 3: Atualizar imports nos demais testes**

```bash
grep -rn "followup\|Followup" apps/api/tests/ | grep -v __pycache__ | grep -v ".pyc"
```

Para cada arquivo, substituir imports de `followup` → `onboarding` e classes pelo novo nome.

- [ ] **Step 4: Rodar todos os testes unitários**

```bash
cd apps/api
uv run pytest tests/unit -v 2>&1 | tail -20
```

Esperado: todos os testes passando. Se algum falhar, corrigir o import antes de continuar.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/ apps/api/tests/
git commit -m "refactor: atualizar handlers e testes followup → onboarding"
```

---

### Task 8: Frontend rename

**Files:**
- Rename dir: `apps/web/src/features/followup/` → `features/onboarding/`
- Create: `apps/web/src/app/(admin)/onboarding/page.tsx`
- Create: `apps/web/src/app/(admin)/onboarding/[id]/page.tsx`
- Modify: `apps/web/src/app/(admin)/followup/page.tsx` → redirect
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`

- [ ] **Step 1: Renomear pasta features**

```bash
git mv apps/web/src/features/followup apps/web/src/features/onboarding
```

No diretório `apps/web/src/features/onboarding/`, renomear:
- `hooks/useFollowupFlows.ts` → `hooks/useOnboardingFlows.ts`
- `hooks/useFollowupSteps.ts` → `hooks/useOnboardingSteps.ts`

Em `types.ts`, renomear interfaces:
```typescript
// Antes → Depois
export interface FollowupFlow  → export interface OnboardingFlow
export interface FollowupStep  → export interface OnboardingStep
```

Em `hooks/useOnboardingFlows.ts`:
```typescript
// Antes:
import { FollowupFlow } from "../types";
export function useFollowupFlows() { ... }

// Depois:
import { OnboardingFlow } from "../types";
export function useOnboardingFlows() { ... }
```

- [ ] **Step 2: Renomear rotas de páginas**

```bash
# Criar diretório novo
mkdir -p apps/web/src/app/\(admin\)/onboarding/\[id\]

# Mover arquivos de página
git mv "apps/web/src/app/(admin)/followup/[id]/page.tsx" \
       "apps/web/src/app/(admin)/onboarding/[id]/page.tsx"
```

O arquivo de listagem original `/followup/page.tsx` vira redirect:

```tsx
// apps/web/src/app/(admin)/followup/page.tsx
import { redirect } from "next/navigation";

export default function FollowupRedirect() {
  redirect("/onboarding");
}
```

Criar `apps/web/src/app/(admin)/onboarding/page.tsx` com o conteúdo da página de listagem de flows, atualizando imports:

```tsx
// Substituir no topo:
import { useOnboardingFlows } from "@/features/onboarding/hooks/useOnboardingFlows";
import { OnboardingFlow } from "@/features/onboarding/types";
import FlowCard from "@/features/onboarding/components/FlowCard";
import FlowDrawer from "@/features/onboarding/components/FlowDrawer";
```

- [ ] **Step 3: Atualizar api.ts — renomear funções**

Em `apps/web/src/lib/api.ts`, substituir:

```typescript
// Antes → Depois (function names)
listFollowupFlows    → listOnboardingFlows
createFollowupFlow   → createOnboardingFlow
updateFollowupFlow   → updateOnboardingFlow
deleteFollowupFlow   → deleteOnboardingFlow
listFollowupSteps    → listOnboardingSteps
createFollowupStep   → createOnboardingStep
updateFollowupStep   → updateOnboardingStep
deleteFollowupStep   → deleteOnboardingStep
reorderFollowupSteps → reorderOnboardingSteps

// Imports de tipos:
import { OnboardingFlow, OnboardingStep } from "@/features/onboarding/types";

// URLs das requisições:
/admin/followup/flows → /admin/onboarding/flows
```

- [ ] **Step 4: Atualizar Sidebar**

```tsx
// apps/web/src/shared/components/layout/Sidebar.tsx
// Antes:
{ label: "Follow-up", href: "/followup", icon: "schedule_send" },

// Depois:
{ label: "Onboarding", href: "/onboarding", icon: "schedule_send" },
```

- [ ] **Step 5: Atualizar todos os imports nos componentes da feature**

Em todos os arquivos em `apps/web/src/features/onboarding/components/`, `apps/web/src/features/leads/`, `apps/web/src/features/products/`, substituir imports de `@/features/followup` → `@/features/onboarding` e tipos `FollowupFlow` → `OnboardingFlow`, `FollowupStep` → `OnboardingStep`.

```bash
grep -rn "followup\|Followup\|follow-up" apps/web/src/ | grep -v __pycache__ | grep -v ".next"
```

Corrigir cada ocorrência.

- [ ] **Step 6: Build de verificação**

```bash
cd apps/web
npm run build 2>&1 | tail -30
```

Esperado: build sem erros de TypeScript.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/
git commit -m "refactor: renomear frontend followup → onboarding"
```

---

## PARTE 2 — Multi-Atendentes ChatNexo

---

### Task 9: Migration — chatnexo_agents + conversations.last_onboarding_agent_id

**Files:**
- Create: `apps/api/migrations/versions/<rev>_add_chatnexo_agents.py`

- [ ] **Step 1: Gerar arquivo de migration**

```bash
cd apps/api
uv run alembic revision --message "add_chatnexo_agents"
```

Substitua o conteúdo pelo seguinte (use o `revision` e `down_revision` gerados — `down_revision` deve ser o hash da migration da Task 1):

```python
"""add chatnexo_agents table and conversations.last_onboarding_agent_id

Revision ID: <hash_gerado>
Revises: <hash_da_task1>
Create Date: 2026-05-25
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "<hash_gerado>"
down_revision = "<hash_da_task1>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chatnexo_agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "name", name="uq_chatnexo_agents_account_name"),
    )
    op.create_index("ix_chatnexo_agents_account", "chatnexo_agents", ["account_id"])

    op.add_column(
        "conversations",
        sa.Column("last_onboarding_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_conversations_last_onboarding_agent",
        "conversations",
        "chatnexo_agents",
        ["last_onboarding_agent_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_conversations_last_onboarding_agent", "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "last_onboarding_agent_id")
    op.drop_index("ix_chatnexo_agents_account", table_name="chatnexo_agents")
    op.drop_table("chatnexo_agents")
```

- [ ] **Step 2: Aplicar migration**

```bash
cd apps/api
uv run alembic upgrade heads
```

Esperado: `Running upgrade <hash_task1> -> <hash_task9>, add_chatnexo_agents table`

- [ ] **Step 3: Commit**

```bash
git add apps/api/migrations/
git commit -m "feat(db): adicionar tabela chatnexo_agents e coluna conversations.last_onboarding_agent_id"
```

---

### Task 10: Domínio — entidade, ports e atualização de IntegrationConfig

**Files:**
- Create: `apps/api/src/shared/domain/entities/chatnexo_agent.py`
- Create: `apps/api/src/shared/domain/ports/agent_selection.py`
- Create: `apps/api/src/shared/domain/ports/chatnexo_agent_repo.py`
- Modify: `apps/api/src/shared/domain/entities/account_config.py`

- [ ] **Step 1: Escrever teste da entidade (smoke)**

Criar `apps/api/tests/unit/chatnexo/__init__.py` (arquivo vazio) e `apps/api/tests/unit/chatnexo/test_agent_entity.py`:

```python
# apps/api/tests/unit/chatnexo/test_agent_entity.py
from uuid import UUID
from shared.domain.entities.chatnexo_agent import ChatNexoAgent


def test_chatnexo_agent_is_frozen():
    agent = ChatNexoAgent(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Ana",
        api_key="secret",
        is_active=True,
    )
    assert agent.name == "Ana"
    assert agent.is_active is True


def test_chatnexo_agent_immutable():
    import pytest
    agent = ChatNexoAgent(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name="Ana",
        api_key="secret",
        is_active=True,
    )
    with pytest.raises((AttributeError, TypeError)):
        agent.name = "outro"  # type: ignore[misc]
```

- [ ] **Step 2: Rodar para verificar falha**

```bash
cd apps/api
uv run pytest tests/unit/chatnexo/test_agent_entity.py -v
```

Esperado: `ImportError: No module named 'shared.domain.entities.chatnexo_agent'`

- [ ] **Step 3: Criar entidade**

```python
# apps/api/src/shared/domain/entities/chatnexo_agent.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class ChatNexoAgent:
    id: UUID
    name: str
    api_key: str
    is_active: bool
    created_at: datetime | None = field(default=None)
```

- [ ] **Step 4: Criar Protocol de seleção**

```python
# apps/api/src/shared/domain/ports/agent_selection.py
from __future__ import annotations

from typing import Protocol

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


class AgentSelectionStrategy(Protocol):
    def pick(self, agents: list[ChatNexoAgent]) -> ChatNexoAgent: ...
```

- [ ] **Step 5: Criar Protocol do repositório**

```python
# apps/api/src/shared/domain/ports/chatnexo_agent_repo.py
from __future__ import annotations

from typing import Protocol
from uuid import UUID

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


class ChatNexoAgentRepositoryPort(Protocol):
    async def list_active(self, account_id: UUID) -> list[ChatNexoAgent]: ...
    async def create(self, account_id: UUID, name: str, api_key: str) -> ChatNexoAgent: ...
    async def update(
        self, *, id: UUID, account_id: UUID, name: str | None, api_key: str | None
    ) -> ChatNexoAgent: ...
    async def delete(self, id: UUID, account_id: UUID) -> None: ...
```

- [ ] **Step 6: Atualizar IntegrationConfig e AccountConfigPatch**

Em `apps/api/src/shared/domain/entities/account_config.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


@dataclass(frozen=True)
class IntegrationConfig:
    chatnexo_base_url: str
    chatnexo_api_key: str
    hubla_webhook_secret: str
    cademi_api_url: str
    cademi_api_key: str
    cademi_max_retries: int
    cademi_retry_base_seconds: float
    openai_api_key: str
    meta_api_key: str
    meta_waba_id: str
    meta_app_id: str
    chatnexo_agents: list[ChatNexoAgent] = field(default_factory=list)
    # ... resto inalterado
```

> **Nota:** `AccountConfigPatch` não precisa de mudança — os agentes são gerenciados pelo próprio `ChatNexoAgentRepository`, não pelo mecanismo de patch de settings.

- [ ] **Step 7: Rodar testes**

```bash
cd apps/api
uv run pytest tests/unit/chatnexo/ -v
```

Esperado: `2 passed`

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/shared/domain/ apps/api/tests/unit/chatnexo/
git commit -m "feat: entidade ChatNexoAgent + ports AgentSelectionStrategy e ChatNexoAgentRepositoryPort"
```

---

### Task 11: Adapter — modelo SQLAlchemy + ChatNexoClient.with_key + agent_picker

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Modify: `apps/api/src/shared/adapters/chatnexo/client.py`
- Create: `apps/api/src/shared/adapters/agent_selection/__init__.py`
- Create: `apps/api/src/shared/adapters/agent_selection/random_selection.py`
- Create: `apps/api/src/shared/adapters/chatnexo/agent_picker.py`
- Create: `apps/api/tests/unit/chatnexo/test_agent_picker.py`

- [ ] **Step 1: Escrever testes do agent_picker e RandomAgentSelection**

```python
# apps/api/tests/unit/chatnexo/test_agent_picker.py
from __future__ import annotations

import pytest
from unittest.mock import patch
from uuid import UUID

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


def _agent(name: str, key: str) -> ChatNexoAgent:
    return ChatNexoAgent(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        name=name,
        api_key=key,
        is_active=True,
    )


# ── RandomAgentSelection ──────────────────────────────────────


def test_random_selection_returns_one_of_the_agents():
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection

    agents = [_agent("Ana", "key-a"), _agent("Bob", "key-b")]
    strategy = RandomAgentSelection()
    result = strategy.pick(agents)
    assert result in agents


def test_random_selection_raises_if_empty():
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection
    import random

    strategy = RandomAgentSelection()
    with pytest.raises(IndexError):
        strategy.pick([])


# ── build_chatnexo_client ─────────────────────────────────────


def test_build_returns_agent_client_when_agents_available():
    from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection

    agents = [_agent("Ana", "key-ana")]
    client, agent_id = build_chatnexo_client(
        base_url="https://chat.example.com",
        agents=agents,
        strategy=RandomAgentSelection(),
        fallback_api_key="fallback-key",
    )
    assert agent_id == agents[0].id
    assert client is not None


def test_build_returns_fallback_client_when_no_agents():
    from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
    from shared.adapters.agent_selection.random_selection import RandomAgentSelection

    client, agent_id = build_chatnexo_client(
        base_url="https://chat.example.com",
        agents=[],
        strategy=RandomAgentSelection(),
        fallback_api_key="fallback-key",
    )
    assert agent_id is None
    assert client is not None
```

- [ ] **Step 2: Rodar para verificar falha**

```bash
cd apps/api
uv run pytest tests/unit/chatnexo/test_agent_picker.py -v
```

Esperado: `ImportError` nos módulos ainda não criados.

- [ ] **Step 3: Adicionar ChatNexoAgentModel em models.py**

No final da seção de models (antes ou depois de `HublaEventModel`), adicionar:

```python
class ChatNexoAgentModel(Base):
    __tablename__ = "chatnexo_agents"
    id: Mapped[uuid.UUID] = _pk()
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
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
    __table_args__ = (
        UniqueConstraint("account_id", "name", name="uq_chatnexo_agents_account_name"),
    )
```

Também adicionar `last_onboarding_agent_id` em `ConversationModel`:

```python
class ConversationModel(Base):
    __tablename__ = "conversations"
    # ... campos existentes ...
    last_onboarding_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chatnexo_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    # __table_args__ existente continua igual
```

- [ ] **Step 4: Adicionar ChatNexoClient.with_key()**

Em `apps/api/src/shared/adapters/chatnexo/client.py`, adicionar após `from_account_config`:

```python
@classmethod
def with_key(cls, base_url: str, api_key: str) -> ChatNexoClient:
    client = httpx.AsyncClient(
        base_url=base_url,
        headers={"api_access_token": api_key},
        timeout=httpx.Timeout(10.0, connect=3.0),
    )
    return cls(http=client)
```

- [ ] **Step 5: Criar RandomAgentSelection**

```python
# apps/api/src/shared/adapters/agent_selection/__init__.py
# (vazio)
```

```python
# apps/api/src/shared/adapters/agent_selection/random_selection.py
from __future__ import annotations

import random

from shared.domain.entities.chatnexo_agent import ChatNexoAgent


class RandomAgentSelection:
    def pick(self, agents: list[ChatNexoAgent]) -> ChatNexoAgent:
        return random.choice(agents)
```

- [ ] **Step 6: Criar agent_picker.py**

```python
# apps/api/src/shared/adapters/chatnexo/agent_picker.py
from __future__ import annotations

from uuid import UUID

from shared.adapters.chatnexo.client import ChatNexoClient
from shared.domain.entities.chatnexo_agent import ChatNexoAgent
from shared.domain.ports.agent_selection import AgentSelectionStrategy


def build_chatnexo_client(
    *,
    base_url: str,
    agents: list[ChatNexoAgent],
    strategy: AgentSelectionStrategy,
    fallback_api_key: str,
) -> tuple[ChatNexoClient, UUID | None]:
    """Constrói ChatNexoClient a partir de um agente selecionado ou do fallback.

    Retorna (client, agent_id). agent_id é None quando usa a chave de fallback.
    """
    if agents:
        agent = strategy.pick(agents)
        return ChatNexoClient.with_key(base_url, agent.api_key), agent.id
    return ChatNexoClient.with_key(base_url, fallback_api_key), None
```

- [ ] **Step 7: Rodar testes**

```bash
cd apps/api
uv run pytest tests/unit/chatnexo/ -v
```

Esperado: todos passando.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/shared/adapters/ apps/api/tests/
git commit -m "feat: ChatNexoAgentModel, ChatNexoClient.with_key, RandomAgentSelection, build_chatnexo_client"
```

---

### Task 12: ChatNexoAgentRepository

**Files:**
- Create: `apps/api/src/shared/adapters/db/repositories/chatnexo_agent_repo.py`
- Create: `apps/api/tests/integration/test_chatnexo_agent_repo.py`

- [ ] **Step 1: Escrever testes de integração**

```python
# apps/api/tests/integration/test_chatnexo_agent_repo.py
"""Testes de integração: ChatNexoAgentRepository."""
from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.repositories.chatnexo_agent_repo import ChatNexoAgentRepository
from shared.config.single_tenant import get_default_account_uuid, reset_cache


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations(database_url: str) -> None:
    import os
    from shared.config.settings import get_settings
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()  # type: ignore[attr-defined]
    try:
        from alembic import command
        from alembic.config import Config as AlembicConfig
        cfg = AlembicConfig("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", database_url)
        command.upgrade(cfg, "heads")
    finally:
        if original is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original
        get_settings.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture
def fernet() -> Fernet:
    return Fernet(Fernet.generate_key())


@pytest.fixture(autouse=True)
def _reset_single_tenant_cache():
    reset_cache()
    yield
    reset_cache()


@pytest.mark.integration
async def test_create_and_list_agent(db_session: AsyncSession, fernet: Fernet) -> None:
    # Precisa de um account no DB
    await db_session.execute(
        text(
            "INSERT INTO accounts (id, name, settings) "
            "VALUES (gen_random_uuid(), 'Test', '{}') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await db_session.flush()

    account_id = await get_default_account_uuid(db_session)
    repo = ChatNexoAgentRepository(session=db_session, fernet=fernet)

    agent = await repo.create(account_id=account_id, name="Ana", api_key="raw-key-123")
    assert agent.name == "Ana"
    assert agent.api_key == "raw-key-123"
    assert agent.is_active is True

    agents = await repo.list_active(account_id)
    assert len(agents) == 1
    assert agents[0].name == "Ana"
    assert agents[0].api_key == "raw-key-123"


@pytest.mark.integration
async def test_delete_agent(db_session: AsyncSession, fernet: Fernet) -> None:
    await db_session.execute(
        text(
            "INSERT INTO accounts (id, name, settings) "
            "VALUES (gen_random_uuid(), 'Test2', '{}') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await db_session.flush()
    account_id = await get_default_account_uuid(db_session)
    repo = ChatNexoAgentRepository(session=db_session, fernet=fernet)

    agent = await repo.create(account_id=account_id, name="Bob", api_key="key-bob")
    await repo.delete(id=agent.id, account_id=account_id)

    agents = await repo.list_active(account_id)
    assert all(a.id != agent.id for a in agents)


@pytest.mark.integration
async def test_update_agent_name(db_session: AsyncSession, fernet: Fernet) -> None:
    await db_session.execute(
        text(
            "INSERT INTO accounts (id, name, settings) "
            "VALUES (gen_random_uuid(), 'Test3', '{}') "
            "ON CONFLICT DO NOTHING"
        )
    )
    await db_session.flush()
    account_id = await get_default_account_uuid(db_session)
    repo = ChatNexoAgentRepository(session=db_session, fernet=fernet)

    agent = await repo.create(account_id=account_id, name="Carol", api_key="key-carol")
    updated = await repo.update(id=agent.id, account_id=account_id, name="Carolina", api_key=None)
    assert updated.name == "Carolina"
    assert updated.api_key == "key-carol"
```

- [ ] **Step 2: Rodar para verificar falha**

```bash
cd apps/api
uv run pytest tests/integration/test_chatnexo_agent_repo.py -v -m integration
```

Esperado: `ImportError: No module named 'shared.adapters.db.repositories.chatnexo_agent_repo'`

- [ ] **Step 3: Implementar ChatNexoAgentRepository**

```python
# apps/api/src/shared/adapters/db/repositories/chatnexo_agent_repo.py
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import ChatNexoAgentModel
from shared.domain.entities.chatnexo_agent import ChatNexoAgent


def _decrypt(fernet: Fernet, value: str) -> str:
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return ""


def _encrypt(fernet: Fernet, value: str) -> str:
    return fernet.encrypt(value.encode()).decode()


def _mask(value: str) -> str:
    if not value:
        return "****"
    if len(value) < 8:
        return "****"
    return value[:8] + "****"


def _to_entity(model: ChatNexoAgentModel, fernet: Fernet) -> ChatNexoAgent:
    return ChatNexoAgent(
        id=model.id,
        name=model.name,
        api_key=_decrypt(fernet, model.api_key_encrypted),
        is_active=model.is_active,
        created_at=model.created_at,
    )


@dataclass
class ChatNexoAgentRepository:
    session: AsyncSession
    fernet: Fernet

    async def list_active(self, account_id: UUID) -> list[ChatNexoAgent]:
        stmt = select(ChatNexoAgentModel).where(
            ChatNexoAgentModel.account_id == account_id,
            ChatNexoAgentModel.is_active.is_(True),
        )
        result = await self.session.execute(stmt)
        return [_to_entity(m, self.fernet) for m in result.scalars().all()]

    async def list_all(self, account_id: UUID) -> list[ChatNexoAgentModel]:
        """Retorna modelos crus para exibição admin (chave mascarada pelo router)."""
        stmt = select(ChatNexoAgentModel).where(
            ChatNexoAgentModel.account_id == account_id,
        ).order_by(ChatNexoAgentModel.created_at)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, *, account_id: UUID, name: str, api_key: str) -> ChatNexoAgent:
        model = ChatNexoAgentModel(
            account_id=account_id,
            name=name,
            api_key_encrypted=_encrypt(self.fernet, api_key),
            is_active=True,
        )
        self.session.add(model)
        await self.session.flush()
        return _to_entity(model, self.fernet)

    async def update(
        self,
        *,
        id: UUID,
        account_id: UUID,
        name: str | None,
        api_key: str | None,
    ) -> ChatNexoAgent:
        stmt = select(ChatNexoAgentModel).where(
            ChatNexoAgentModel.id == id,
            ChatNexoAgentModel.account_id == account_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado")
        if name is not None:
            model.name = name
        if api_key is not None:
            model.api_key_encrypted = _encrypt(self.fernet, api_key)
        await self.session.flush()
        return _to_entity(model, self.fernet)

    async def delete(self, *, id: UUID, account_id: UUID) -> None:
        stmt = select(ChatNexoAgentModel).where(
            ChatNexoAgentModel.id == id,
            ChatNexoAgentModel.account_id == account_id,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado")
        await self.session.delete(model)
        await self.session.flush()
```

- [ ] **Step 4: Rodar testes**

```bash
cd apps/api
uv run pytest tests/integration/test_chatnexo_agent_repo.py -v -m integration
```

Esperado: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/chatnexo_agent_repo.py \
        apps/api/tests/integration/test_chatnexo_agent_repo.py
git commit -m "feat: ChatNexoAgentRepository com create/list_active/update/delete"
```

---

### Task 13: ConversationRepository — tracking do agente

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/conversation.py`

- [ ] **Step 1: Escrever teste unitário**

```python
# apps/api/tests/unit/chatnexo/test_conversation_agent_tracking.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID


@pytest.mark.asyncio
async def test_set_last_onboarding_agent_id_updates_model():
    """Verifica que set_last_onboarding_agent_id atualiza o campo correto."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from shared.adapters.db.repositories.conversation import ConversationRepository
    from shared.adapters.db.models import ConversationModel

    mock_session = AsyncMock(spec=AsyncSession)
    conv_model = MagicMock(spec=ConversationModel)
    conv_model.last_onboarding_agent_id = None

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = conv_model
    mock_session.execute = AsyncMock(return_value=mock_result)

    repo = ConversationRepository(session=mock_session)
    agent_id = UUID("aaaaaaaa-0000-0000-0000-000000000001")

    await repo.set_last_onboarding_agent_id(
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        chatnexo_conversation_id=42,
        agent_id=agent_id,
    )

    assert conv_model.last_onboarding_agent_id == agent_id
```

- [ ] **Step 2: Rodar para verificar falha**

```bash
cd apps/api
uv run pytest tests/unit/chatnexo/test_conversation_agent_tracking.py -v
```

Esperado: `AttributeError` — método ainda não existe.

- [ ] **Step 3: Implementar os dois novos métodos em conversation.py**

```python
# Adicionar no final da classe ConversationRepository
# em apps/api/src/shared/adapters/db/repositories/conversation.py

async def get_last_onboarding_agent_id(
    self, *, account_id: UUID, chatnexo_conversation_id: int
) -> UUID | None:
    stmt = select(ConversationModel).where(
        ConversationModel.account_id == account_id,
        ConversationModel.chatnexo_conversation_id == chatnexo_conversation_id,
    )
    result = await self.session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        return None
    return model.last_onboarding_agent_id  # type: ignore[return-value]

async def set_last_onboarding_agent_id(
    self,
    *,
    account_id: UUID,
    chatnexo_conversation_id: int,
    agent_id: UUID,
) -> None:
    stmt = select(ConversationModel).where(
        ConversationModel.account_id == account_id,
        ConversationModel.chatnexo_conversation_id == chatnexo_conversation_id,
    )
    result = await self.session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is not None:
        model.last_onboarding_agent_id = agent_id
```

- [ ] **Step 4: Rodar testes**

```bash
cd apps/api
uv run pytest tests/unit/chatnexo/ -v
```

Esperado: todos passando.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/conversation.py \
        apps/api/tests/unit/chatnexo/
git commit -m "feat: ConversationRepository.get/set_last_onboarding_agent_id"
```

---

### Task 14: AccountConfigRepository — carregar agentes ativos

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/account_config_repo.py`

- [ ] **Step 1: Atualizar o método get() para carregar agentes**

Em `account_config_repo.py`, atualizar o método `get()`:

```python
# Adicionar import no topo:
from shared.adapters.db.repositories.chatnexo_agent_repo import ChatNexoAgentRepository
from shared.config.single_tenant import get_default_account_uuid

# Dentro do método get():
async def get(self, *, account_id: int) -> AccountConfig:
    model = await self._load_model()
    raw: dict = dict(model.settings or {}) if model else {}

    # ... código existente para carregar settings ...

    # Carregar agentes ativos
    agent_repo = ChatNexoAgentRepository(session=self.session, fernet=self.fernet)
    account_uuid = await get_default_account_uuid(self.session)
    agents = await agent_repo.list_active(account_uuid)

    return AccountConfig(
        integration=IntegrationConfig(
            chatnexo_base_url=gs("chatnexo_base_url", s.chatnexo_base_url),
            chatnexo_api_key=gs("chatnexo_api_key", s.chatnexo_api_key),
            # ... outros campos ...
            chatnexo_agents=agents,
        ),
        behavior=BehaviorConfig(
            # ... campos existentes ...
        ),
    )
```

- [ ] **Step 2: Rodar testes unitários para garantir que nada quebrou**

```bash
cd apps/api
uv run pytest tests/unit -v 2>&1 | tail -20
```

Esperado: todos passando (AccountConfigRepository usa mock em testes unitários).

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/account_config_repo.py
git commit -m "feat: AccountConfigRepository carrega chatnexo_agents ativos"
```

---

### Task 15: Atualizar handlers — seleção de agente

**Files:**
- Modify: `apps/api/src/interface/worker/handlers/message.py`
- Modify: `apps/api/src/interface/worker/handlers/scheduled.py`
- Modify: `apps/api/src/shared/application/lifecycle_handler.py`

- [ ] **Step 1: Atualizar message.py**

Em `apps/api/src/interface/worker/handlers/message.py`, dentro de `_process_message()`:

```python
# Adicionar imports no topo do arquivo:
from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
from shared.adapters.agent_selection.random_selection import RandomAgentSelection
from shared.adapters.db.repositories.conversation import ConversationRepository
from shared.config.single_tenant import get_default_account_uuid

# Dentro do session_scope, após carregar account_config:
async with session_scope() as session:
    config_repo = AccountConfigRepository(session=session, fernet=fernet)
    account_config = await config_repo.get(account_id=account_id)

    # Resolução de agente: usar last_onboarding_agent_id se existir
    account_uuid = await get_default_account_uuid(session)
    conv_repo = ConversationRepository(session=session)
    last_agent_id = await conv_repo.get_last_onboarding_agent_id(
        account_id=account_uuid,
        chatnexo_conversation_id=conversation_id,
    )

    agents = account_config.integration.chatnexo_agents
    base_url = account_config.integration.chatnexo_base_url
    fallback_key = account_config.integration.chatnexo_api_key

    if last_agent_id:
        locked_agent = next((a for a in agents if a.id == last_agent_id), None)
        if locked_agent:
            chatnexo = ChatNexoClient.with_key(base_url, locked_agent.api_key)
        else:
            chatnexo, _ = build_chatnexo_client(
                base_url=base_url,
                agents=agents,
                strategy=RandomAgentSelection(),
                fallback_api_key=fallback_key,
            )
    else:
        chatnexo, _ = build_chatnexo_client(
            base_url=base_url,
            agents=agents,
            strategy=RandomAgentSelection(),
            fallback_api_key=fallback_key,
        )

    # ... resto do session_scope (run_agent, etc.) ...

# send_message permanece fora do session_scope (como antes):
await chatnexo.send_message(
    account_id=str(account_id),
    conversation_id=str(conversation_id),
    text=reply,
)
```

- [ ] **Step 2: Atualizar scheduled.py — step de onboarding**

No bloco `elif job_type in ("followup_step", "onboarding_step"):` dentro de `handle_scheduled()`:

```python
# Adicionar imports no bloco (já estão em lazy imports):
from shared.adapters.chatnexo.agent_picker import build_chatnexo_client
from shared.adapters.agent_selection.random_selection import RandomAgentSelection
from shared.adapters.db.repositories.chatnexo_agent_repo import ChatNexoAgentRepository
from shared.adapters.db.repositories.conversation import ConversationRepository
from shared.config.single_tenant import get_default_account_uuid

# Dentro do session_scope:
async with session_scope() as session:
    config_repo = AccountConfigRepository(session=session, fernet=fernet)
    config = await config_repo.get(account_id=1)

    account_uuid = await get_default_account_uuid(session)
    agents = config.integration.chatnexo_agents
    base_url = config.integration.chatnexo_base_url
    fallback_key = config.integration.chatnexo_api_key

    chatnexo, chosen_agent_id = build_chatnexo_client(
        base_url=base_url,
        agents=agents,
        strategy=RandomAgentSelection(),
        fallback_api_key=fallback_key,
    )

    dispatch = DispatchOnboardingStep(
        enrollment_repo=OnboardingEnrollmentRepository(session=session),
        contact_repo=ContactRepository(session=session),
        chatnexo=chatnexo,
        conversation_history=ConversationHistory(session=session),
        meta_template_repo=MetaTemplateRepository(session=session),
    )
    result = await dispatch.execute(
        enrollment_step_id=_UUID(payload["enrollment_step_id"]),
        account_id=_UUID(payload["account_id"]),
        conversation_id=payload["conversation_id"],
        contact_phone=payload.get("contact_phone", ""),
    )

    # Persistir o agente escolhido na conversa (para a IA usar na próxima resposta)
    if chosen_agent_id and result.status == EnrollmentStepStatus.SENT:
        conv_repo = ConversationRepository(session=session)
        try:
            chatnexo_conv_id = int(payload["conversation_id"])
            await conv_repo.set_last_onboarding_agent_id(
                account_id=account_uuid,
                chatnexo_conversation_id=chatnexo_conv_id,
                agent_id=chosen_agent_id,
            )
        except (ValueError, TypeError):
            pass  # conversation_id não é inteiro — não persistir
```

- [ ] **Step 3: Atualizar lifecycle_handler.py**

Em `apps/api/src/shared/application/lifecycle_handler.py`:

```python
# O LifecycleHandler já recebe chatnexo via __init__ (injeção de dependência).
# O ponto de mudança está onde o LifecycleHandler é instanciado.
# Verificar em main.py/worker.py onde _get_lifecycle_handler é configurado.
```

Localizar onde `LifecycleHandler` é instanciado (em `apps/api/src/main.py` ou no worker):

```bash
grep -rn "LifecycleHandler\|_get_lifecycle_handler" apps/api/src/ | grep -v __pycache__
```

No ponto de instanciação, substituir `ChatNexoClient.from_account_config(config)` por:

```python
chatnexo, _ = build_chatnexo_client(
    base_url=config.integration.chatnexo_base_url,
    agents=config.integration.chatnexo_agents,
    strategy=RandomAgentSelection(),
    fallback_api_key=config.integration.chatnexo_api_key,
)
```

- [ ] **Step 4: Rodar testes unitários**

```bash
cd apps/api
uv run pytest tests/unit -v 2>&1 | tail -20
```

Esperado: todos passando.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/interface/worker/handlers/ \
        apps/api/src/shared/application/lifecycle_handler.py
git commit -m "feat: handlers usam build_chatnexo_client com seleção aleatória e travamento por conversa"
```

---

### Task 16: API endpoints — /admin/chatnexo-agents

**Files:**
- Create: `apps/api/src/interface/http/routers/admin/chatnexo_agents.py`
- Modify: `apps/api/src/main.py`

- [ ] **Step 1: Criar o router**

```python
# apps/api/src/interface/http/routers/admin/chatnexo_agents.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from interface.http.deps.admin_auth import require_admin
from shared.adapters.db.repositories.chatnexo_agent_repo import (
    ChatNexoAgentRepository,
    _mask,
)
from shared.adapters.db.session import session_scope
from shared.config.settings import get_settings
from shared.config.single_tenant import get_default_account_uuid

router = APIRouter(tags=["admin-chatnexo-agents"])


class AgentItem(BaseModel):
    id: UUID
    name: str
    api_key_masked: str
    is_active: bool
    created_at: datetime


class CreateAgentInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    api_key: str = Field(min_length=1)


class UpdateAgentInput(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    api_key: str | None = Field(default=None, min_length=1)


def _fernet() -> Fernet:
    return Fernet(get_settings().integration_credentials_key.encode())


@router.get("/chatnexo-agents", response_model=list[AgentItem])
async def list_agents(_auth=Depends(require_admin)) -> list[AgentItem]:
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        models = await repo.list_all(account_id)
        return [
            AgentItem(
                id=m.id,
                name=m.name,
                api_key_masked=_mask(fernet.decrypt(m.api_key_encrypted.encode()).decode()),
                is_active=m.is_active,
                created_at=m.created_at,
            )
            for m in models
        ]


@router.post("/chatnexo-agents", response_model=AgentItem, status_code=status.HTTP_201_CREATED)
async def create_agent(body: CreateAgentInput, _auth=Depends(require_admin)) -> AgentItem:
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        agent = await repo.create(account_id=account_id, name=body.name, api_key=body.api_key)
    return AgentItem(
        id=agent.id,
        name=agent.name,
        api_key_masked=_mask(agent.api_key),
        is_active=agent.is_active,
        created_at=agent.created_at or datetime.utcnow(),
    )


@router.patch("/chatnexo-agents/{agent_id}", response_model=AgentItem)
async def update_agent(
    agent_id: UUID, body: UpdateAgentInput, _auth=Depends(require_admin)
) -> AgentItem:
    if body.name is None and body.api_key is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça name e/ou api_key para atualizar.",
        )
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        agent = await repo.update(
            id=agent_id, account_id=account_id, name=body.name, api_key=body.api_key
        )
    return AgentItem(
        id=agent.id,
        name=agent.name,
        api_key_masked=_mask(agent.api_key),
        is_active=agent.is_active,
        created_at=agent.created_at or datetime.utcnow(),
    )


@router.delete("/chatnexo-agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: UUID, _auth=Depends(require_admin)) -> None:
    async with session_scope() as session:
        fernet = _fernet()
        repo = ChatNexoAgentRepository(session=session, fernet=fernet)
        account_id = await get_default_account_uuid(session)
        await repo.delete(id=agent_id, account_id=account_id)
```

- [ ] **Step 2: Registrar em main.py**

```python
# apps/api/src/main.py — adicionar import:
from interface.http.routers.admin import chatnexo_agents as admin_chatnexo_agents

# E no include_router:
app.include_router(admin_chatnexo_agents.router, prefix="/admin")
```

- [ ] **Step 3: Verificar que a API sobe**

```bash
cd apps/api
uv run uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health
kill %1
```

Esperado: `{"status":"ok"}`

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/interface/http/routers/admin/chatnexo_agents.py \
        apps/api/src/main.py
git commit -m "feat: endpoints CRUD /admin/chatnexo-agents"
```

---

### Task 17: Frontend — ChatNexoAgentsSection na página de Settings

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/features/settings/components/ChatNexoAgentsSection.tsx`
- Modify: `apps/web/src/app/(admin)/settings/page.tsx`

- [ ] **Step 1: Adicionar funções à api.ts**

Em `apps/web/src/lib/api.ts`, adicionar:

```typescript
// Tipos
export interface AgentItem {
  id: string;
  name: string;
  api_key_masked: string;
  is_active: boolean;
  created_at: string;
}

export interface CreateAgentInput {
  name: string;
  api_key: string;
}

export interface UpdateAgentInput {
  name?: string;
  api_key?: string;
}

// Funções
export async function listChatnexoAgents(): Promise<AgentItem[]> {
  return apiFetch<AgentItem[]>("/admin/chatnexo-agents");
}

export async function createChatnexoAgent(dto: CreateAgentInput): Promise<AgentItem> {
  return apiFetch<AgentItem>("/admin/chatnexo-agents", {
    method: "POST",
    body: JSON.stringify(dto),
  });
}

export async function updateChatnexoAgent(id: string, dto: UpdateAgentInput): Promise<AgentItem> {
  return apiFetch<AgentItem>(`/admin/chatnexo-agents/${id}`, {
    method: "PATCH",
    body: JSON.stringify(dto),
  });
}

export async function deleteChatnexoAgent(id: string): Promise<void> {
  return apiFetch<void>(`/admin/chatnexo-agents/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 2: Criar ChatNexoAgentsSection**

```tsx
// apps/web/src/features/settings/components/ChatNexoAgentsSection.tsx
"use client";

import { useState, useEffect } from "react";
import {
  AgentItem,
  listChatnexoAgents,
  createChatnexoAgent,
  deleteChatnexoAgent,
} from "@/lib/api";
import { useToast } from "@/shared/hooks/useToast";

export function ChatNexoAgentsSection() {
  const { toast } = useToast();
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listChatnexoAgents()
      .then(setAgents)
      .catch(() => toast.error("Erro ao carregar atendentes"))
      .finally(() => setLoading(false));
  }, []);

  async function handleAdd() {
    if (!name.trim() || !apiKey.trim()) return;
    setSaving(true);
    try {
      const agent = await createChatnexoAgent({ name: name.trim(), api_key: apiKey.trim() });
      setAgents((prev) => [...prev, agent]);
      setName("");
      setApiKey("");
      toast.success(`Atendente "${agent.name}" adicionado`);
    } catch {
      toast.error("Erro ao adicionar atendente");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(agent: AgentItem) {
    try {
      await deleteChatnexoAgent(agent.id);
      setAgents((prev) => prev.filter((a) => a.id !== agent.id));
      toast.success(`Atendente "${agent.name}" removido`);
    } catch {
      toast.error("Erro ao remover atendente");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-on-surface">
          Atendentes ChatNexo
        </h3>
        <span className="text-xs text-on-surface-variant">
          {agents.length === 0
            ? "Nenhum atendente — usando chave de fallback"
            : `${agents.length} atendente${agents.length > 1 ? "s" : ""}`}
        </span>
      </div>

      {loading ? (
        <p className="text-sm text-on-surface-variant">Carregando...</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {agents.map((agent) => (
            <li
              key={agent.id}
              className="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container px-3 py-2"
            >
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-on-surface">{agent.name}</span>
                <span className="font-mono text-xs text-on-surface-variant">
                  {agent.api_key_masked}
                </span>
              </div>
              <button
                onClick={() => handleDelete(agent)}
                className="text-on-surface-variant hover:text-error transition-colors"
                title="Remover atendente"
              >
                <span className="material-symbols-outlined text-[18px]">delete</span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-2 rounded-lg border border-outline-variant bg-surface-container p-3">
        <p className="text-xs font-medium text-on-surface-variant">Adicionar atendente</p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Nome do atendente"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="flex-1 rounded-md border border-outline-variant bg-surface px-3 py-1.5 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <input
            type="password"
            placeholder="API Key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="flex-1 rounded-md border border-outline-variant bg-surface px-3 py-1.5 text-sm text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <button
            onClick={handleAdd}
            disabled={saving || !name.trim() || !apiKey.trim()}
            className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-on-primary disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {saving ? "..." : "Adicionar"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Integrar na página de Settings**

Em `apps/web/src/app/(admin)/settings/page.tsx`, adicionar a seção após a seção de configurações do ChatNexo existente:

```tsx
// No topo do arquivo, adicionar import:
import { ChatNexoAgentsSection } from "@/features/settings/components/ChatNexoAgentsSection";

// No JSX, após o campo chatnexo_api_key (que agora tem label de fallback):
// Localizar onde o campo chatnexo_api_key é renderizado e adicionar nota de fallback:
// label: "API Key ChatNexo (fallback — usada quando não há atendentes cadastrados)"

// Após a seção de integração ChatNexo:
<div className="flex flex-col gap-4 rounded-xl border border-outline-variant bg-surface-container-low p-6">
  <ChatNexoAgentsSection />
</div>
```

- [ ] **Step 4: Verificar build**

```bash
cd apps/web
npm run build 2>&1 | tail -20
```

Esperado: build sem erros.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/
git commit -m "feat: ChatNexoAgentsSection na página de Settings"
```

---

### Task 18: Verificação final e PR

- [ ] **Step 1: Rodar todos os testes unitários**

```bash
cd apps/api
uv run pytest tests/unit -v 2>&1 | tail -30
```

Esperado: todos passando.

- [ ] **Step 2: Rodar linting e type check**

```bash
cd apps/api
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src 2>&1 | tail -20
```

Esperado: sem erros.

- [ ] **Step 3: Type check frontend**

```bash
cd apps/web
npx tsc --noEmit 2>&1 | tail -20
```

Esperado: sem erros.

- [ ] **Step 4: Checar critérios de aceite**

```
✅ CRUD de atendentes funciona via API
✅ Fallback para chave única quando lista vazia
✅ Disparo de onboarding usa agente aleatório
✅ Resposta da IA usa agente travado (last_onboarding_agent_id)
✅ Lifecycle usa aleatório sem persistência
✅ Tabelas renomeadas (followup_ → onboarding_)
✅ Rotas /admin/onboarding/flows respondem
✅ Rotas /admin/followup/ retornam 404
✅ Frontend sidebar mostra "Onboarding"
✅ Redirect 301 de /followup → /onboarding funciona
✅ Jobs com kind="followup_step" ainda processados
```

- [ ] **Step 5: Commit final e PR**

```bash
git push origin <branch>
gh pr create \
  --title "feat: multi-atendentes ChatNexo + rename follow-up → onboarding" \
  --body "Implementa suporte a N chaves de API por conta com seleção aleatória e travamento por conversa. Renomeia toda a stack de follow-up → onboarding."
```
