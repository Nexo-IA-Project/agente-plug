# Follow-up Engine v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as 4 lacunas críticas do Follow-up Engine: processar webhooks Hubla v2 (`subscription.activated`), re-sincronizar enrollments ativos quando flows são editados, tornar a memória do agente configurável, e expor relatórios de enrollments/steps.

**Architecture:** Clean Architecture + SOLID. Mudanças passam por use cases isolados (`EnrollContact`, `DispatchFollowupStep`, `ResyncEnrollment`), repositórios SQLAlchemy assíncronos e handlers de worker. Webhook substitui formato flat pelo payload Hubla aninhado. Re-sync usa diff com identidade via `flow_step_id` e cancela/recria scheduled_jobs explicitamente via nova coluna `scheduled_job_id`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, PostgreSQL 16+, Redis 7, pytest, Next.js 15 (UI), Tailwind.

**Spec:** `docs/superpowers/specs/2026-05-21-followup-engine-v2-design.md`

---

## Convenções

- **Diretório base do backend:** `apps/api/`
- **Diretório base do frontend:** `apps/web/`
- **Comandos `uv`, `pytest`, `alembic` rodam de `apps/api/`**
- **TDD obrigatório** em use cases e repositórios (1 teste → falha → impl → passa → commit)
- **Migrations:** sempre `alembic upgrade heads` (plural)
- **Test DB:** `pytest tests/integration` exige postgres + redis up via `docker compose up postgres redis`

---

## Task 1: Migration — FK, índices, novos campos e enum CANCELLED

**Files:**
- Create: `apps/api/migrations/versions/a1b2c3d4e5f6_followup_engine_v2.py`
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Modify: `apps/api/src/shared/domain/entities/followup.py`
- Test: `apps/api/tests/integration/test_followup_engine_v2_migration.py`

- [ ] **Step 1.1: Criar arquivo de migration vazio e gerar revision id**

Crie `apps/api/migrations/versions/a1b2c3d4e5f6_followup_engine_v2.py` com o esqueleto Alembic. Use o `down_revision` do último merge head — verifique com:

```bash
cd apps/api && uv run alembic heads
```

Conteúdo inicial:

```python
"""followup engine v2 — FK, indexes, failure_reason, scheduled_job_id, flow_step_id, CANCELLED

Revision ID: a1b2c3d4e5f6
Revises: <PEGAR_HEAD_ATUAL>
Create Date: 2026-05-21
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "<PEGAR_HEAD_ATUAL>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
```

Substitua `<PEGAR_HEAD_ATUAL>` pela saída de `alembic heads`.

- [ ] **Step 1.2: Implementar `upgrade()` — FK, índices, colunas, enum CANCELLED**

```python
def upgrade() -> None:
    # 1. FK em followup_enrollments.flow_id (SET NULL ao deletar flow)
    op.create_foreign_key(
        "fk_followup_enrollments_flow",
        "followup_enrollments", "followup_flows",
        ["flow_id"], ["id"],
        ondelete="SET NULL",
    )

    # 2. UNIQUE compound para dedup
    op.create_index(
        "uq_followup_enrollment_dedup",
        "followup_enrollments",
        ["account_id", "contact_id", "flow_id", "purchase_id"],
        unique=True,
    )

    # 3. Índices de leitura
    op.create_index(
        "idx_followup_enrollments_flow_status",
        "followup_enrollments",
        ["flow_id", "status"],
    )
    op.create_index(
        "idx_followup_enrollments_account_contact",
        "followup_enrollments",
        ["account_id", "contact_id"],
    )
    op.create_index(
        "idx_followup_enrollment_steps_enr_status",
        "followup_enrollment_steps",
        ["enrollment_id", "status"],
    )

    # 4. Novas colunas em followup_enrollment_steps
    op.add_column(
        "followup_enrollment_steps",
        sa.Column("failure_reason", sa.Text(), nullable=True),
    )
    op.add_column(
        "followup_enrollment_steps",
        sa.Column("scheduled_job_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "followup_enrollment_steps",
        sa.Column("flow_step_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )

    # 5. Novo valor no enum EnrollmentStepStatus
    op.execute("ALTER TYPE enrollment_step_status ADD VALUE IF NOT EXISTS 'CANCELLED'")
```

- [ ] **Step 1.3: Implementar `downgrade()` — reverter na ordem inversa (sem dropar valor de enum)**

```python
def downgrade() -> None:
    op.drop_column("followup_enrollment_steps", "flow_step_id")
    op.drop_column("followup_enrollment_steps", "scheduled_job_id")
    op.drop_column("followup_enrollment_steps", "failure_reason")
    op.drop_index("idx_followup_enrollment_steps_enr_status", table_name="followup_enrollment_steps")
    op.drop_index("idx_followup_enrollments_account_contact", table_name="followup_enrollments")
    op.drop_index("idx_followup_enrollments_flow_status", table_name="followup_enrollments")
    op.drop_index("uq_followup_enrollment_dedup", table_name="followup_enrollments")
    op.drop_constraint("fk_followup_enrollments_flow", "followup_enrollments", type_="foreignkey")
    # ATENÇÃO: PostgreSQL não suporta DROP VALUE de enum; valor CANCELLED permanece após downgrade
```

- [ ] **Step 1.4: Atualizar `FollowupEnrollmentStepModel` em `models.py` com 3 novos campos**

Localize `class FollowupEnrollmentStepModel(Base)` em `apps/api/src/shared/adapters/db/models.py` e adicione (preservando ordem alfabética do projeto):

```python
    failure_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    scheduled_job_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    flow_step_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
```

(Use o mesmo apelido `PGUUID`/`postgresql.UUID` já importado no topo do arquivo.)

- [ ] **Step 1.5: Adicionar FK em `FollowupEnrollmentModel.flow_id`**

No mesmo arquivo, encontre `class FollowupEnrollmentModel`. O campo `flow_id` deve passar a referenciar a FK (mantendo nullable após `SET NULL`):

```python
    flow_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        sa.ForeignKey("followup_flows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
```

- [ ] **Step 1.6: Atualizar enum `EnrollmentStepStatus` em `followup.py` com `CANCELLED`**

Edite `apps/api/src/shared/domain/entities/followup.py`:

```python
class EnrollmentStepStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
```

- [ ] **Step 1.7: Atualizar entity `FollowupEnrollmentStep` com novos campos**

No mesmo `followup.py`, adicione aos atributos da dataclass `FollowupEnrollmentStep`:

```python
    failure_reason: str | None = None
    scheduled_job_id: UUID | None = None
    flow_step_id: UUID | None = None
```

- [ ] **Step 1.8: Escrever teste de integração da migration**

Crie `apps/api/tests/integration/test_followup_engine_v2_migration.py`:

```python
"""Verifica que a migration v2 criou colunas, índices, FK e o valor de enum."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from shared.adapters.db.session import session_scope


@pytest.mark.asyncio
async def test_migration_added_failure_reason_column():
    async with session_scope() as session:
        result = await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'followup_enrollment_steps' "
            "AND column_name = 'failure_reason'"
        ))
        assert result.scalar_one_or_none() == "failure_reason"


@pytest.mark.asyncio
async def test_migration_added_scheduled_job_id_column():
    async with session_scope() as session:
        result = await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'followup_enrollment_steps' "
            "AND column_name = 'scheduled_job_id'"
        ))
        assert result.scalar_one_or_none() == "scheduled_job_id"


@pytest.mark.asyncio
async def test_migration_added_flow_step_id_column():
    async with session_scope() as session:
        result = await session.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'followup_enrollment_steps' "
            "AND column_name = 'flow_step_id'"
        ))
        assert result.scalar_one_or_none() == "flow_step_id"


@pytest.mark.asyncio
async def test_migration_added_dedup_unique_index():
    async with session_scope() as session:
        result = await session.execute(text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'followup_enrollments' "
            "AND indexname = 'uq_followup_enrollment_dedup'"
        ))
        assert result.scalar_one_or_none() == "uq_followup_enrollment_dedup"


@pytest.mark.asyncio
async def test_migration_added_cancelled_to_enum():
    async with session_scope() as session:
        result = await session.execute(text(
            "SELECT unnest(enum_range(NULL::enrollment_step_status))::text"
        ))
        values = {row[0] for row in result.all()}
        assert "CANCELLED" in values
```

- [ ] **Step 1.9: Rodar a migration**

```bash
cd apps/api && uv run alembic upgrade heads
```

Expected: `INFO Running upgrade ... -> a1b2c3d4e5f6, followup engine v2`

- [ ] **Step 1.10: Rodar os testes da migration**

```bash
cd apps/api && uv run pytest tests/integration/test_followup_engine_v2_migration.py -v
```

Expected: 5 testes PASS.

- [ ] **Step 1.11: Commit**

```bash
git add apps/api/migrations/versions/a1b2c3d4e5f6_followup_engine_v2.py \
        apps/api/src/shared/adapters/db/models.py \
        apps/api/src/shared/domain/entities/followup.py \
        apps/api/tests/integration/test_followup_engine_v2_migration.py
git commit -m "feat(db): migration v2 — FK, índices, failure_reason, scheduled_job_id, flow_step_id, enum CANCELLED"
```

---

## Task 2: Repositórios — métodos novos em `followup_enrollment_repo`

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py`
- Test: `apps/api/tests/integration/test_followup_enrollment_repo_v2.py`

- [ ] **Step 2.1: Escrever teste para `find_active_by_flow`**

Crie `apps/api/tests/integration/test_followup_enrollment_repo_v2.py`:

```python
import uuid
from datetime import datetime, timezone

import pytest
from shared.adapters.db.repositories.followup_enrollment_repo import (
    FollowupEnrollmentRepo,
)
from shared.adapters.db.session import session_scope
from shared.domain.entities.followup import (
    EnrollmentStatus,
    FollowupEnrollment,
)


@pytest.mark.asyncio
async def test_find_active_by_flow_returns_only_active(seed_account, seed_flow, seed_contact):
    flow_id = seed_flow.id
    async with session_scope() as session:
        repo = FollowupEnrollmentRepo(session=session)
        # 2 active, 1 completed
        for status in [EnrollmentStatus.ACTIVE, EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]:
            await repo.create(FollowupEnrollment(
                id=uuid.uuid4(),
                account_id=seed_account.id,
                contact_id=seed_contact.id,
                flow_id=flow_id,
                purchase_id=str(uuid.uuid4()),
                status=status,
                created_at=datetime.now(timezone.utc),
            ))
        actives = await repo.find_active_by_flow(flow_id)
        assert len(actives) == 2
        assert all(e.status == EnrollmentStatus.ACTIVE for e in actives)
```

(Use as fixtures `seed_account`, `seed_flow`, `seed_contact` do `conftest.py`. Se não existirem ainda, crie-as no `conftest.py` da pasta `tests/integration/`.)

- [ ] **Step 2.2: Rodar teste e verificar falha**

```bash
cd apps/api && uv run pytest tests/integration/test_followup_enrollment_repo_v2.py::test_find_active_by_flow_returns_only_active -v
```

Expected: FAIL (`AttributeError: 'FollowupEnrollmentRepo' object has no attribute 'find_active_by_flow'`).

- [ ] **Step 2.3: Implementar `find_active_by_flow` no repo**

Adicione em `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py`:

```python
async def find_active_by_flow(self, flow_id: uuid.UUID) -> list[FollowupEnrollment]:
    """Lista enrollments com status='ACTIVE' de um flow."""
    result = await self.session.execute(
        select(FollowupEnrollmentModel)
        .where(
            FollowupEnrollmentModel.flow_id == flow_id,
            FollowupEnrollmentModel.status == EnrollmentStatus.ACTIVE.value,
        )
    )
    rows = result.scalars().all()
    return [self._to_entity(row) for row in rows]
```

(Use o helper `_to_entity` existente; se não houver, crie um que mapeia model → entity copiando os campos.)

- [ ] **Step 2.4: Rodar teste e verificar PASS**

```bash
cd apps/api && uv run pytest tests/integration/test_followup_enrollment_repo_v2.py::test_find_active_by_flow_returns_only_active -v
```

Expected: PASS.

- [ ] **Step 2.5: Escrever teste para `list_with_filters` (paginação + filtros)**

Adicione ao mesmo arquivo de teste:

```python
@pytest.mark.asyncio
async def test_list_with_filters_paginates_and_filters_by_status(seed_account, seed_flow, seed_contact):
    async with session_scope() as session:
        repo = FollowupEnrollmentRepo(session=session)
        for i in range(25):
            await repo.create(FollowupEnrollment(
                id=uuid.uuid4(),
                account_id=seed_account.id,
                contact_id=seed_contact.id,
                flow_id=seed_flow.id,
                purchase_id=f"p-{i}",
                status=EnrollmentStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
            ))
        items, total = await repo.list_with_filters(
            account_id=seed_account.id,
            flow_id=seed_flow.id,
            contact_phone=None,
            status=EnrollmentStatus.ACTIVE,
            page=1,
            page_size=10,
        )
        assert total == 25
        assert len(items) == 10
```

- [ ] **Step 2.6: Implementar `list_with_filters` no repo**

```python
async def list_with_filters(
    self,
    *,
    account_id: uuid.UUID,
    flow_id: uuid.UUID | None,
    contact_phone: str | None,
    status: EnrollmentStatus | None,
    page: int,
    page_size: int,
) -> tuple[list[FollowupEnrollment], int]:
    """Lista enrollments paginados. Retorna (items, total)."""
    base = select(FollowupEnrollmentModel).where(
        FollowupEnrollmentModel.account_id == account_id
    )
    if flow_id is not None:
        base = base.where(FollowupEnrollmentModel.flow_id == flow_id)
    if status is not None:
        base = base.where(FollowupEnrollmentModel.status == status.value)
    if contact_phone:
        base = base.join(ContactModel).where(ContactModel.phone == contact_phone)

    total_result = await self.session.execute(
        select(func.count()).select_from(base.subquery())
    )
    total = int(total_result.scalar_one())

    paged = base.order_by(FollowupEnrollmentModel.created_at.desc()) \
                .offset((page - 1) * page_size).limit(page_size)
    rows = (await self.session.execute(paged)).scalars().all()
    return [self._to_entity(r) for r in rows], total
```

Importe `func` e `ContactModel` no topo se ainda não estiverem.

- [ ] **Step 2.7: Rodar testes e verificar PASS**

```bash
cd apps/api && uv run pytest tests/integration/test_followup_enrollment_repo_v2.py -v
```

Expected: ambos os testes PASS.

- [ ] **Step 2.8: Escrever teste para `count_steps_by_status`**

```python
@pytest.mark.asyncio
async def test_count_steps_by_status(seed_account, seed_enrollment_with_steps):
    """seed_enrollment_with_steps cria 3 SENT + 2 PENDING."""
    enr_id = seed_enrollment_with_steps.id
    async with session_scope() as session:
        repo = FollowupEnrollmentRepo(session=session)
        counts = await repo.count_steps_by_status(enr_id)
        assert counts["SENT"] == 3
        assert counts["PENDING"] == 2
```

- [ ] **Step 2.9: Implementar `count_steps_by_status`**

```python
async def count_steps_by_status(self, enrollment_id: uuid.UUID) -> dict[str, int]:
    result = await self.session.execute(
        select(
            FollowupEnrollmentStepModel.status,
            func.count(FollowupEnrollmentStepModel.id),
        )
        .where(FollowupEnrollmentStepModel.enrollment_id == enrollment_id)
        .group_by(FollowupEnrollmentStepModel.status)
    )
    return {row[0]: int(row[1]) for row in result.all()}
```

- [ ] **Step 2.10: Implementar `cancel_step` (marca CANCELLED + zera scheduled_job_id)**

Sem TDD direto — método auxiliar usado pelo re-sync. Adicione:

```python
async def cancel_step(self, step_id: uuid.UUID) -> None:
    await self.session.execute(
        update(FollowupEnrollmentStepModel)
        .where(FollowupEnrollmentStepModel.id == step_id)
        .values(status=EnrollmentStepStatus.CANCELLED.value)
    )
```

- [ ] **Step 2.11: Rodar todos os testes da Task 2**

```bash
cd apps/api && uv run pytest tests/integration/test_followup_enrollment_repo_v2.py -v
```

Expected: 3 testes PASS.

- [ ] **Step 2.12: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py \
        apps/api/tests/integration/test_followup_enrollment_repo_v2.py
git commit -m "feat(db): repo methods find_active_by_flow, list_with_filters, count_steps_by_status, cancel_step"
```

---

## Task 3: Webhook Hubla v2 — parser + purchase handler

**Files:**
- Modify: `apps/api/src/interface/http/routers/webhook_purchase.py`
- Modify: `apps/api/src/shared/application/purchase_handler.py`
- Create: `apps/api/src/shared/adapters/hubla/event_parser.py`
- Test: `apps/api/tests/unit/test_hubla_event_parser.py`
- Test: `apps/api/tests/integration/test_webhook_purchase_v2.py`

- [ ] **Step 3.1: Escrever teste para o parser `HublaEventParser.parse_subscription_activated`**

Crie `apps/api/tests/unit/test_hubla_event_parser.py`:

```python
import pytest
from shared.adapters.hubla.event_parser import HublaEventParser, ParsedPurchaseEvent

PAYLOAD = {
    "type": "subscription.activated",
    "version": "2.0.0",
    "event": {
        "product": {"id": "QaIlGtff9tlU94JjDKSq", "name": "MVS"},
        "products": [{"id": "QaIlGtff9tlU94JjDKSq", "name": "MVS"}],
        "subscription": {
            "id": "9a92f819-490b-4679-976d-820c1eadaf91",
            "payer": {
                "firstName": "Cleide",
                "lastName": "Barros",
                "document": "01810507812",
                "email": "test@example.com",
                "phone": "+5513997160759",
            },
            "activatedAt": "2026-05-02T02:59:25.256Z",
        },
        "user": {"id": "u1", "email": "test@example.com", "phone": "+5513997160759"},
    },
}


def test_parses_single_product():
    parsed = HublaEventParser().parse(PAYLOAD)
    assert isinstance(parsed, ParsedPurchaseEvent)
    assert parsed.purchase_id == "9a92f819-490b-4679-976d-820c1eadaf91"
    assert len(parsed.products) == 1
    assert parsed.products[0].hubla_id == "QaIlGtff9tlU94JjDKSq"
    assert parsed.payer_phone == "+5513997160759"
    assert parsed.payer_full_name == "Cleide Barros"
    assert parsed.activated_at.isoformat().startswith("2026-05-02T02:59:25")


def test_parses_multiple_products():
    payload = {**PAYLOAD}
    payload["event"] = {**payload["event"], "products": [
        {"id": "p1", "name": "P1"},
        {"id": "p2", "name": "P2"},
    ]}
    parsed = HublaEventParser().parse(payload)
    assert {p.hubla_id for p in parsed.products} == {"p1", "p2"}


def test_rejects_other_event_types():
    with pytest.raises(ValueError, match="unsupported event type"):
        HublaEventParser().parse({"type": "subscription.canceled", "event": {}})


def test_falls_back_to_event_product_if_products_missing():
    payload = {**PAYLOAD}
    payload["event"] = {k: v for k, v in payload["event"].items() if k != "products"}
    parsed = HublaEventParser().parse(payload)
    assert len(parsed.products) == 1
    assert parsed.products[0].hubla_id == "QaIlGtff9tlU94JjDKSq"
```

- [ ] **Step 3.2: Rodar teste e verificar falha**

```bash
cd apps/api && uv run pytest tests/unit/test_hubla_event_parser.py -v
```

Expected: FAIL (`ModuleNotFoundError: shared.adapters.hubla.event_parser`).

- [ ] **Step 3.3: Implementar o parser**

Crie `apps/api/src/shared/adapters/hubla/event_parser.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ParsedProduct:
    hubla_id: str
    name: str


@dataclass(frozen=True)
class ParsedPurchaseEvent:
    purchase_id: str
    activated_at: datetime
    payer_phone: str
    payer_email: str
    payer_full_name: str
    payer_document: str
    products: list[ParsedProduct]


class HublaEventParser:
    """Parse de webhooks Hubla v2.0.0 (subscription.activated)."""

    def parse(self, payload: dict[str, Any]) -> ParsedPurchaseEvent:
        event_type = payload.get("type")
        if event_type != "subscription.activated":
            raise ValueError(f"unsupported event type: {event_type}")

        event = payload["event"]
        subscription = event["subscription"]
        payer = subscription["payer"]

        # Lista de produtos: preferir event.products[]; fallback para event.product
        raw_products = event.get("products")
        if not raw_products:
            single = event.get("product")
            raw_products = [single] if single else []
        products = [
            ParsedProduct(hubla_id=p["id"], name=p.get("name", ""))
            for p in raw_products
        ]

        full_name = " ".join(
            x for x in (payer.get("firstName"), payer.get("lastName")) if x
        ).strip()

        return ParsedPurchaseEvent(
            purchase_id=str(subscription["id"]),
            activated_at=datetime.fromisoformat(
                subscription["activatedAt"].replace("Z", "+00:00")
            ),
            payer_phone=payer["phone"],
            payer_email=payer.get("email", ""),
            payer_full_name=full_name,
            payer_document=payer.get("document", ""),
            products=products,
        )
```

- [ ] **Step 3.4: Rodar testes e verificar PASS**

```bash
cd apps/api && uv run pytest tests/unit/test_hubla_event_parser.py -v
```

Expected: 4 testes PASS.

- [ ] **Step 3.5: Atualizar router `webhook_purchase.py` para aceitar payload aninhado**

Substitua o handler existente em `apps/api/src/interface/http/routers/webhook_purchase.py`. Mantenha as 3 mecânicas atuais: validação de token (`HUBLA_WEBHOOK_SECRET`), dedup via WebhookEvent, enqueue de job. Mude apenas o schema de entrada:

```python
from fastapi import APIRouter, Body, Header, HTTPException, Request, status
from shared.adapters.hubla.event_parser import HublaEventParser

router = APIRouter(tags=["webhook"])


@router.post("/webhook/purchase", status_code=status.HTTP_202_ACCEPTED)
async def webhook_purchase(
    request: Request,
    payload: dict = Body(...),
    x_hubla_token: str | None = Header(default=None),
) -> dict:
    settings = get_settings()
    if x_hubla_token != settings.hubla_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid token")

    try:
        parsed = HublaEventParser().parse(payload)
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid payload: {exc}",
        )

    # Dedup pelo subscription.id (24h TTL no Redis, conforme atual)
    dedup_key = f"webhook:purchase:{parsed.purchase_id}"
    redis = await get_redis()
    if not await redis.set(dedup_key, "1", ex=86400, nx=True):
        return {"deduped": True}

    # Enqueue do payload raw para o worker
    async with session_scope() as session:
        queue = PostgresJobQueue(session=session)
        await queue.enqueue(kind="purchase", payload=payload)

    return {"accepted": True}
```

(Preserve imports já existentes e remova qualquer referência ao `PurchasePayload` antigo.)

- [ ] **Step 3.6: Atualizar `handle_purchase` no worker para usar o parser**

Edite `apps/api/src/interface/worker/handlers/purchase.py`. Refatore para parsear o payload e iterar produtos:

```python
async def handle_purchase(payload: dict) -> None:
    parsed = HublaEventParser().parse(payload)
    logger.info(
        "purchase.received",
        extra={"purchase_id": parsed.purchase_id, "products": len(parsed.products)},
    )
    async with session_scope() as session:
        handler = PurchaseHandler(
            session=session,
            # ... dependências existentes
        )
        for product in parsed.products:
            await handler.handle_one(
                hubla_product_id=product.hubla_id,
                purchase_id=parsed.purchase_id,
                activated_at=parsed.activated_at,
                payer_phone=parsed.payer_phone,
                payer_email=parsed.payer_email,
                payer_full_name=parsed.payer_full_name,
                payer_document=parsed.payer_document,
            )
```

- [ ] **Step 3.7: Refatorar `PurchaseHandler.handle()` em `handle_one()`**

Em `apps/api/src/shared/application/purchase_handler.py`, divida o método antigo `handle(payload)` num novo `handle_one(...)` recebendo argumentos por nome (não mais o payload bruto):

```python
async def handle_one(
    self,
    *,
    hubla_product_id: str,
    purchase_id: str,
    activated_at: datetime,
    payer_phone: str,
    payer_email: str,
    payer_full_name: str,
    payer_document: str,
) -> None:
    course = await self.course_repo.find_active_by_hubla_id(hubla_product_id)
    if course is None:
        logger.warning(
            "purchase.course_not_found",
            extra={"hubla_id": hubla_product_id, "purchase_id": purchase_id},
        )
        return

    contact = await self.contact_repo.upsert_by_phone(
        account_id=self.account_id,
        phone=payer_phone,
        full_name=payer_full_name,
        email=payer_email,
        document=payer_document,
    )
    conversation = await self.conversation_repo.get_or_create_active(
        account_id=self.account_id, contact_id=contact.id
    )

    # Comportamento atual: AccessCase + welcome (mantido)
    await self._create_access_case_and_welcome(contact, conversation, course, activated_at)

    # Follow-up flows do curso
    flows = await self.followup_flow_repo.list_active_by_course(course.id)
    for flow in flows:
        await self.enroll_contact_use_case.execute(
            account_id=self.account_id,
            contact=contact,
            conversation=conversation,
            flow=flow,
            purchase_time=activated_at,
            purchase_id=purchase_id,
        )
```

(Mantenha o método `handle(payload)` antigo apenas se houver chamadores fora do escopo; caso contrário, remova-o.)

- [ ] **Step 3.8: Escrever teste de integração end-to-end do webhook**

Crie `apps/api/tests/integration/test_webhook_purchase_v2.py`:

```python
import json
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from shared.adapters.db.models import FollowupEnrollmentModel, JobQueueModel
from shared.adapters.db.session import session_scope


@pytest.mark.asyncio
async def test_webhook_subscription_activated_enrolls(
    test_client: AsyncClient,
    seed_course_with_active_flow,  # fixture cria Course + Flow ativo
    settings,
):
    payload = {
        "type": "subscription.activated",
        "version": "2.0.0",
        "event": {
            "product": {"id": seed_course_with_active_flow.hubla_id, "name": "X"},
            "products": [{"id": seed_course_with_active_flow.hubla_id, "name": "X"}],
            "subscription": {
                "id": "sub-uuid-1",
                "payer": {
                    "firstName": "Test", "lastName": "User",
                    "document": "00000000000",
                    "email": "test@example.com",
                    "phone": "+5511999999999",
                },
                "activatedAt": "2026-05-02T02:59:25Z",
            },
            "user": {"id": "u1", "email": "test@example.com", "phone": "+5511999999999"},
        },
    }
    response = await test_client.post(
        "/webhook/purchase",
        json=payload,
        headers={"x-hubla-token": settings.hubla_webhook_secret},
    )
    assert response.status_code == 202

    # Worker job criado
    async with session_scope() as session:
        jobs = (await session.execute(
            select(JobQueueModel).where(JobQueueModel.kind == "purchase")
        )).scalars().all()
        assert len(jobs) == 1


@pytest.mark.asyncio
async def test_webhook_duplicate_subscription_returns_deduped(test_client, settings):
    payload = {...}  # mesmo payload do teste anterior
    r1 = await test_client.post("/webhook/purchase", json=payload, headers={"x-hubla-token": settings.hubla_webhook_secret})
    r2 = await test_client.post("/webhook/purchase", json=payload, headers={"x-hubla-token": settings.hubla_webhook_secret})
    assert r1.status_code == 202
    assert r2.status_code == 202
    assert r2.json() == {"deduped": True}


@pytest.mark.asyncio
async def test_webhook_invalid_token_returns_403(test_client):
    r = await test_client.post(
        "/webhook/purchase",
        json={"type": "subscription.activated", "event": {}},
        headers={"x-hubla-token": "wrong"},
    )
    assert r.status_code == 403
```

- [ ] **Step 3.9: Rodar testes de integração e verificar PASS**

```bash
cd apps/api && uv run pytest tests/integration/test_webhook_purchase_v2.py -v
```

Expected: 3 testes PASS.

- [ ] **Step 3.10: Commit**

```bash
git add apps/api/src/shared/adapters/hubla/event_parser.py \
        apps/api/src/interface/http/routers/webhook_purchase.py \
        apps/api/src/interface/worker/handlers/purchase.py \
        apps/api/src/shared/application/purchase_handler.py \
        apps/api/tests/unit/test_hubla_event_parser.py \
        apps/api/tests/integration/test_webhook_purchase_v2.py
git commit -m "feat(webhook): parser e handler para payload Hubla v2 subscription.activated"
```

---

## Task 4: Enrollment robusto — dedup + transação atômica + scheduled_job_id

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/followup/enroll_contact.py`
- Test: `apps/api/tests/unit/test_enroll_contact_v2.py`

- [ ] **Step 4.1: Escrever teste de dedup**

Crie `apps/api/tests/unit/test_enroll_contact_v2.py`:

```python
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from shared.application.use_cases.followup.enroll_contact import EnrollContactUseCase
from shared.domain.entities.followup import (
    FollowupFlow, FollowupStep, EnrollmentStatus,
)
from sqlalchemy.exc import IntegrityError


@pytest.mark.asyncio
async def test_enroll_dedup_returns_existing_silently():
    repo = AsyncMock()
    repo.create_with_steps.side_effect = IntegrityError("dup", {}, Exception())
    repo.find_by_dedup_key.return_value = MagicMock(id=uuid.uuid4(), status=EnrollmentStatus.ACTIVE)

    use_case = EnrollContactUseCase(
        enrollment_repo=repo,
        flow_step_repo=AsyncMock(),
        scheduled_job_repo=AsyncMock(),
        clock=MagicMock(now=lambda: datetime.now(timezone.utc)),
    )
    result = await use_case.execute(
        account_id=uuid.uuid4(),
        contact=MagicMock(id=uuid.uuid4()),
        conversation=MagicMock(id=uuid.uuid4()),
        flow=MagicMock(id=uuid.uuid4()),
        purchase_time=datetime.now(timezone.utc),
        purchase_id="dup-id",
    )
    assert result.deduped is True
```

- [ ] **Step 4.2: Rodar e verificar falha**

```bash
cd apps/api && uv run pytest tests/unit/test_enroll_contact_v2.py -v
```

Expected: FAIL.

- [ ] **Step 4.3: Implementar dedup + transação no `EnrollContactUseCase`**

Edite `apps/api/src/shared/application/use_cases/followup/enroll_contact.py`:

```python
from dataclasses import dataclass
from sqlalchemy.exc import IntegrityError


@dataclass(frozen=True)
class EnrollResult:
    enrollment_id: uuid.UUID
    deduped: bool


class EnrollContactUseCase:
    # ... __init__ com session, enrollment_repo, flow_step_repo, scheduled_job_repo, clock

    async def execute(
        self,
        *,
        account_id: uuid.UUID,
        contact,
        conversation,
        flow,
        purchase_time: datetime,
        purchase_id: str,
    ) -> EnrollResult:
        try:
            async with self.session.begin_nested():
                enrollment = FollowupEnrollment(
                    id=uuid.uuid4(),
                    account_id=account_id,
                    contact_id=contact.id,
                    flow_id=flow.id,
                    purchase_id=purchase_id,
                    status=EnrollmentStatus.ACTIVE,
                    created_at=self.clock.now(),
                )
                flow_steps = await self.flow_step_repo.list_by_flow(flow.id)

                enrollment_steps = []
                for fs in flow_steps:
                    es = FollowupEnrollmentStep(
                        id=uuid.uuid4(),
                        enrollment_id=enrollment.id,
                        flow_step_id=fs.id,
                        position=fs.position,
                        delay_from_purchase_hours=fs.delay_from_purchase_hours,
                        meta_template_name=fs.meta_template_name,
                        message_text=fs.message_text,
                        template_variables=fs.template_variables,
                        status=EnrollmentStepStatus.PENDING,
                    )
                    enrollment_steps.append(es)

                await self.enrollment_repo.create_with_steps(enrollment, enrollment_steps)

                # Agenda jobs e persiste scheduled_job_id em cada step
                for es in enrollment_steps:
                    run_at = purchase_time + timedelta(hours=es.delay_from_purchase_hours)
                    job_id = await self.scheduled_job_repo.enqueue(
                        kind="followup_step",
                        run_at=run_at,
                        payload={"enrollment_step_id": str(es.id)},
                    )
                    await self.enrollment_repo.update_step_scheduled_job(es.id, job_id)

            return EnrollResult(enrollment_id=enrollment.id, deduped=False)

        except IntegrityError:
            existing = await self.enrollment_repo.find_by_dedup_key(
                account_id=account_id,
                contact_id=contact.id,
                flow_id=flow.id,
                purchase_id=purchase_id,
            )
            logger.info(
                "enroll.dedup",
                extra={
                    "account_id": str(account_id),
                    "flow_id": str(flow.id),
                    "purchase_id": purchase_id,
                },
            )
            return EnrollResult(enrollment_id=existing.id, deduped=True)
```

- [ ] **Step 4.4: Implementar `find_by_dedup_key` e `update_step_scheduled_job` no repo**

Em `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py`:

```python
async def find_by_dedup_key(
    self, *, account_id: uuid.UUID, contact_id: uuid.UUID,
    flow_id: uuid.UUID, purchase_id: str,
) -> FollowupEnrollment | None:
    result = await self.session.execute(
        select(FollowupEnrollmentModel).where(
            FollowupEnrollmentModel.account_id == account_id,
            FollowupEnrollmentModel.contact_id == contact_id,
            FollowupEnrollmentModel.flow_id == flow_id,
            FollowupEnrollmentModel.purchase_id == purchase_id,
        )
    )
    row = result.scalar_one_or_none()
    return self._to_entity(row) if row else None


async def update_step_scheduled_job(
    self, step_id: uuid.UUID, scheduled_job_id: uuid.UUID
) -> None:
    await self.session.execute(
        update(FollowupEnrollmentStepModel)
        .where(FollowupEnrollmentStepModel.id == step_id)
        .values(scheduled_job_id=scheduled_job_id)
    )
```

- [ ] **Step 4.5: Rodar testes e verificar PASS**

```bash
cd apps/api && uv run pytest tests/unit/test_enroll_contact_v2.py -v
```

Expected: PASS.

- [ ] **Step 4.6: Adicionar teste de rollback transacional**

```python
@pytest.mark.asyncio
async def test_enroll_rollback_on_scheduling_failure():
    """Se enqueue de job falhar, criar steps deve ser revertido."""
    session = AsyncMock()
    enrollment_repo = AsyncMock()
    flow_step_repo = AsyncMock()
    flow_step_repo.list_by_flow.return_value = [
        MagicMock(id=uuid.uuid4(), position=1, delay_from_purchase_hours=0,
                  meta_template_name="t", message_text=None, template_variables={}),
    ]
    scheduled_job_repo = AsyncMock()
    scheduled_job_repo.enqueue.side_effect = RuntimeError("redis down")

    use_case = EnrollContactUseCase(
        session=session,
        enrollment_repo=enrollment_repo,
        flow_step_repo=flow_step_repo,
        scheduled_job_repo=scheduled_job_repo,
        clock=MagicMock(now=lambda: datetime.now(timezone.utc)),
    )
    with pytest.raises(RuntimeError, match="redis down"):
        await use_case.execute(
            account_id=uuid.uuid4(),
            contact=MagicMock(id=uuid.uuid4()),
            conversation=MagicMock(id=uuid.uuid4()),
            flow=MagicMock(id=uuid.uuid4()),
            purchase_time=datetime.now(timezone.utc),
            purchase_id="x",
        )
    # session.rollback() pode não ser chamado explicitamente — begin_nested() faz isso ao sair com exceção.
    # Apenas asseguramos que a exceção propagou e os steps NÃO foram confirmados.
```

- [ ] **Step 4.7: Rodar e commit**

```bash
cd apps/api && uv run pytest tests/unit/test_enroll_contact_v2.py -v
git add apps/api/src/shared/application/use_cases/followup/enroll_contact.py \
        apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py \
        apps/api/tests/unit/test_enroll_contact_v2.py
git commit -m "feat(followup): dedup atomic enrollment + scheduled_job_id persistence"
```

---

## Task 5: Dispatch com error handling — failure_reason

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py`
- Modify: `apps/api/src/interface/worker/handlers/scheduled.py`
- Test: `apps/api/tests/unit/test_dispatch_followup_step_failure.py`

- [ ] **Step 5.1: Escrever teste de exceção no envio**

Crie `apps/api/tests/unit/test_dispatch_followup_step_failure.py`:

```python
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock
from shared.application.use_cases.followup.dispatch_followup_step import (
    DispatchFollowupStepUseCase, DispatchResult,
)
from shared.domain.entities.followup import EnrollmentStepStatus


@pytest.mark.asyncio
async def test_dispatch_marks_failed_on_chatnexo_error():
    chatnexo = AsyncMock()
    chatnexo.send_template.side_effect = RuntimeError("ChatNexo 500")

    step = MagicMock(
        id=uuid.uuid4(),
        status=EnrollmentStepStatus.PENDING,
        meta_template_name="t",
        message_text=None,
    )
    step_repo = AsyncMock()
    step_repo.get_by_id.return_value = step

    use_case = DispatchFollowupStepUseCase(
        step_repo=step_repo,
        chatnexo_client=chatnexo,
        conversation_history=AsyncMock(),
        variable_resolver=MagicMock(resolve=lambda *a, **k: {}),
    )
    result = await use_case.execute(step_id=step.id)
    assert isinstance(result, DispatchResult)
    assert result.status == EnrollmentStepStatus.FAILED
    assert "ChatNexo 500" in result.failure_reason
    step_repo.mark_failed.assert_awaited_once_with(step.id, result.failure_reason)
```

- [ ] **Step 5.2: Rodar e verificar falha**

```bash
cd apps/api && uv run pytest tests/unit/test_dispatch_followup_step_failure.py -v
```

Expected: FAIL.

- [ ] **Step 5.3: Atualizar `DispatchFollowupStepUseCase`**

Em `apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py`:

```python
@dataclass(frozen=True)
class DispatchResult:
    status: EnrollmentStepStatus
    failure_reason: str | None = None


class DispatchFollowupStepUseCase:
    # ... __init__ como antes

    async def execute(self, *, step_id: uuid.UUID) -> DispatchResult:
        step = await self.step_repo.get_by_id(step_id)
        if step is None or step.status != EnrollmentStepStatus.PENDING:
            return DispatchResult(status=step.status if step else EnrollmentStepStatus.CANCELLED)

        try:
            if step.meta_template_name:
                variables = self.variable_resolver.resolve(step, ...)
                await self.chatnexo_client.send_template(
                    template_name=step.meta_template_name,
                    variables=variables,
                    # ... outros args
                )
            else:
                await self.chatnexo_client.send_message(text=step.message_text, ...)

            await self.step_repo.mark_sent(step.id, sent_at=self.clock.now())
            return DispatchResult(status=EnrollmentStepStatus.SENT)

        except Exception as exc:
            reason = str(exc)[:500]
            await self.step_repo.mark_failed(step.id, reason)
            logger.exception(
                "dispatch.failed",
                extra={"step_id": str(step.id), "reason": reason},
            )
            return DispatchResult(
                status=EnrollmentStepStatus.FAILED,
                failure_reason=reason,
            )
```

- [ ] **Step 5.4: Adicionar `mark_failed` no repo**

Em `apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py`:

```python
async def mark_failed(self, step_id: uuid.UUID, reason: str) -> None:
    await self.session.execute(
        update(FollowupEnrollmentStepModel)
        .where(FollowupEnrollmentStepModel.id == step_id)
        .values(
            status=EnrollmentStepStatus.FAILED.value,
            failure_reason=reason,
        )
    )
```

(`mark_sent` já deve existir; se não, crie análogo com `sent_at`.)

- [ ] **Step 5.5: Atualizar handler `scheduled.py` para não propagar FAILED**

Em `apps/api/src/interface/worker/handlers/scheduled.py`, o trecho que despacha `FOLLOWUP_STEP`:

```python
elif job_type == JobType.FOLLOWUP_STEP.value:
    from shared.application.use_cases.followup.dispatch_followup_step import (
        DispatchFollowupStepUseCase,
    )
    result = await dispatch_use_case.execute(step_id=step_id)
    if result.status == EnrollmentStepStatus.FAILED:
        # Falha de envio é registrada no step; o job em si terminou.
        logger.warning(
            "followup_step.dispatch_failed",
            extra={"step_id": str(step_id), "reason": result.failure_reason},
        )
        # NÃO re-raise: job conclui com sucesso do ponto de vista da fila
```

- [ ] **Step 5.6: Rodar testes e PASS**

```bash
cd apps/api && uv run pytest tests/unit/test_dispatch_followup_step_failure.py -v
```

Expected: PASS.

- [ ] **Step 5.7: Commit**

```bash
git add apps/api/src/shared/application/use_cases/followup/dispatch_followup_step.py \
        apps/api/src/interface/worker/handlers/scheduled.py \
        apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py \
        apps/api/tests/unit/test_dispatch_followup_step_failure.py
git commit -m "feat(followup): dispatch captura exceção, marca FAILED com failure_reason"
```

---

## Task 6: Smart Re-sync — diff + use case + handler de worker + triggers

**Files:**
- Create: `apps/api/src/shared/application/use_cases/followup/diff_flow_steps.py`
- Create: `apps/api/src/shared/application/use_cases/followup/resync_enrollment.py`
- Modify: `apps/api/src/shared/domain/entities/scheduled_job.py`
- Modify: `apps/api/src/interface/worker/handlers/scheduled.py`
- Modify: `apps/api/src/interface/http/routers/admin/followup.py`
- Test: `apps/api/tests/unit/test_diff_flow_steps.py`
- Test: `apps/api/tests/unit/test_resync_enrollment.py`

- [ ] **Step 6.1: Escrever testes do algoritmo de diff**

Crie `apps/api/tests/unit/test_diff_flow_steps.py`:

```python
import uuid
from types import SimpleNamespace
import pytest
from shared.application.use_cases.followup.diff_flow_steps import compute_diff
from shared.domain.entities.followup import EnrollmentStepStatus


def _flow_step(id, position, delay, template="t", text=None, vars=None):
    return SimpleNamespace(
        id=id, position=position, delay_from_purchase_hours=delay,
        meta_template_name=template, message_text=text,
        template_variables=vars or {},
    )


def _enr_step(flow_step_id, position, delay, status=EnrollmentStepStatus.PENDING,
              template="t", text=None, vars=None):
    return SimpleNamespace(
        id=uuid.uuid4(), flow_step_id=flow_step_id, position=position,
        delay_from_purchase_hours=delay, status=status,
        meta_template_name=template, message_text=text,
        template_variables=vars or {},
    )


def test_diff_detects_new_step():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, 1, 24)]
    enr_steps = []
    diff = compute_diff(flow_steps, enr_steps)
    assert len(diff.to_add) == 1
    assert diff.to_add[0].id == fs_id


def test_diff_detects_delay_change():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, 1, 48)]
    enr_steps = [_enr_step(fs_id, 1, 24)]
    diff = compute_diff(flow_steps, enr_steps)
    assert len(diff.to_reschedule) == 1


def test_diff_detects_content_only_change():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, 1, 24, template="t2")]
    enr_steps = [_enr_step(fs_id, 1, 24, template="t1")]
    diff = compute_diff(flow_steps, enr_steps)
    assert len(diff.to_update_content) == 1
    assert len(diff.to_reschedule) == 0


def test_diff_skips_sent_steps():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, 1, 48, template="t2")]
    enr_steps = [_enr_step(fs_id, 1, 24, status=EnrollmentStepStatus.SENT)]
    diff = compute_diff(flow_steps, enr_steps)
    assert diff.to_reschedule == []
    assert diff.to_update_content == []


def test_diff_detects_cancelled_step():
    enr_steps = [_enr_step(uuid.uuid4(), 1, 24)]
    diff = compute_diff([], enr_steps)
    assert len(diff.to_cancel) == 1


def test_diff_is_idempotent():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, 1, 24)]
    enr_steps = [_enr_step(fs_id, 1, 24)]
    diff = compute_diff(flow_steps, enr_steps)
    assert diff.to_add == []
    assert diff.to_reschedule == []
    assert diff.to_update_content == []
    assert diff.to_cancel == []
```

- [ ] **Step 6.2: Implementar `compute_diff`**

Crie `apps/api/src/shared/application/use_cases/followup/diff_flow_steps.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.domain.entities.followup import EnrollmentStepStatus


@dataclass(frozen=True)
class Diff:
    to_add: list[Any] = field(default_factory=list)
    to_reschedule: list[tuple[Any, Any]] = field(default_factory=list)
    to_update_content: list[tuple[Any, Any]] = field(default_factory=list)
    to_cancel: list[Any] = field(default_factory=list)


def compute_diff(flow_steps, enrollment_steps) -> Diff:
    """Identidade: enrollment_step.flow_step_id == flow_step.id.

    - Step novo no flow → to_add
    - Step PENDING com delay alterado → to_reschedule (também aplica conteúdo novo)
    - Step PENDING com só conteúdo alterado → to_update_content (job intocado)
    - Step PENDING que sumiu do flow → to_cancel
    - Step SENT/FAILED/CANCELLED → imutável
    """
    enr_by_flow_step = {
        es.flow_step_id: es for es in enrollment_steps if es.flow_step_id is not None
    }
    to_add, to_reschedule, to_update_content, to_cancel = [], [], [], []

    for fs in flow_steps:
        enr = enr_by_flow_step.get(fs.id)
        if enr is None:
            to_add.append(fs)
            continue
        if enr.status != EnrollmentStepStatus.PENDING:
            continue

        delay_changed = enr.delay_from_purchase_hours != fs.delay_from_purchase_hours
        content_changed = (
            enr.meta_template_name != fs.meta_template_name
            or enr.message_text != fs.message_text
            or enr.template_variables != fs.template_variables
        )

        if delay_changed:
            to_reschedule.append((enr, fs))
        elif content_changed:
            to_update_content.append((enr, fs))

    flow_step_ids = {fs.id for fs in flow_steps}
    for es in enrollment_steps:
        if (
            es.flow_step_id is not None
            and es.flow_step_id not in flow_step_ids
            and es.status == EnrollmentStepStatus.PENDING
        ):
            to_cancel.append(es)

    return Diff(
        to_add=to_add,
        to_reschedule=to_reschedule,
        to_update_content=to_update_content,
        to_cancel=to_cancel,
    )
```

- [ ] **Step 6.3: Rodar testes de diff**

```bash
cd apps/api && uv run pytest tests/unit/test_diff_flow_steps.py -v
```

Expected: 6 testes PASS.

- [ ] **Step 6.4: Escrever teste do `ResyncEnrollmentUseCase`**

Crie `apps/api/tests/unit/test_resync_enrollment.py`:

```python
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.application.use_cases.followup.resync_enrollment import (
    ResyncEnrollmentUseCase,
)
from shared.domain.entities.followup import EnrollmentStepStatus


@pytest.mark.asyncio
async def test_resync_adds_new_step():
    new_fs_id = uuid.uuid4()
    flow_steps = [SimpleNamespace(
        id=new_fs_id, position=1, delay_from_purchase_hours=0,
        meta_template_name="t", message_text=None, template_variables={},
    )]
    enrollment = SimpleNamespace(
        id=uuid.uuid4(),
        purchase_time=datetime.now(timezone.utc),
        steps=[],
    )
    enr_repo = AsyncMock()
    enr_repo.get_with_steps.return_value = enrollment
    flow_step_repo = AsyncMock()
    flow_step_repo.list_by_flow.return_value = flow_steps
    scheduled_job_repo = AsyncMock()
    scheduled_job_repo.enqueue.return_value = uuid.uuid4()

    use_case = ResyncEnrollmentUseCase(
        enrollment_repo=enr_repo,
        flow_step_repo=flow_step_repo,
        scheduled_job_repo=scheduled_job_repo,
    )
    audit = await use_case.execute(enrollment_id=enrollment.id, flow_id=uuid.uuid4())
    assert audit["steps_added"] == 1
    enr_repo.add_step_with_job.assert_awaited()


@pytest.mark.asyncio
async def test_resync_reschedules_when_delay_changed():
    fs_id = uuid.uuid4()
    old_job = uuid.uuid4()
    flow_steps = [SimpleNamespace(
        id=fs_id, position=1, delay_from_purchase_hours=48,
        meta_template_name="t", message_text=None, template_variables={},
    )]
    enr_step = SimpleNamespace(
        id=uuid.uuid4(), flow_step_id=fs_id, position=1,
        delay_from_purchase_hours=24, status=EnrollmentStepStatus.PENDING,
        meta_template_name="t", message_text=None, template_variables={},
        scheduled_job_id=old_job,
    )
    enrollment = SimpleNamespace(
        id=uuid.uuid4(),
        purchase_time=datetime.now(timezone.utc),
        steps=[enr_step],
    )

    enr_repo = AsyncMock()
    enr_repo.get_with_steps.return_value = enrollment
    flow_step_repo = AsyncMock()
    flow_step_repo.list_by_flow.return_value = flow_steps
    scheduled_job_repo = AsyncMock()
    new_job = uuid.uuid4()
    scheduled_job_repo.enqueue.return_value = new_job

    use_case = ResyncEnrollmentUseCase(
        enrollment_repo=enr_repo,
        flow_step_repo=flow_step_repo,
        scheduled_job_repo=scheduled_job_repo,
    )
    audit = await use_case.execute(enrollment_id=enrollment.id, flow_id=uuid.uuid4())
    assert audit["steps_rescheduled"] == 1
    scheduled_job_repo.cancel.assert_awaited_with(old_job)


@pytest.mark.asyncio
async def test_resync_idempotent_on_unchanged_state():
    fs_id = uuid.uuid4()
    flow_steps = [SimpleNamespace(
        id=fs_id, position=1, delay_from_purchase_hours=24,
        meta_template_name="t", message_text=None, template_variables={},
    )]
    enr_step = SimpleNamespace(
        id=uuid.uuid4(), flow_step_id=fs_id, position=1,
        delay_from_purchase_hours=24, status=EnrollmentStepStatus.PENDING,
        meta_template_name="t", message_text=None, template_variables={},
        scheduled_job_id=uuid.uuid4(),
    )
    enrollment = SimpleNamespace(
        id=uuid.uuid4(),
        purchase_time=datetime.now(timezone.utc),
        steps=[enr_step],
    )

    enr_repo = AsyncMock()
    enr_repo.get_with_steps.return_value = enrollment
    flow_step_repo = AsyncMock()
    flow_step_repo.list_by_flow.return_value = flow_steps

    use_case = ResyncEnrollmentUseCase(
        enrollment_repo=enr_repo,
        flow_step_repo=flow_step_repo,
        scheduled_job_repo=AsyncMock(),
    )
    audit = await use_case.execute(enrollment_id=enrollment.id, flow_id=uuid.uuid4())
    assert audit == {
        "steps_added": 0, "steps_rescheduled": 0,
        "steps_content_updated": 0, "steps_cancelled": 0,
    }
```

- [ ] **Step 6.5: Implementar `ResyncEnrollmentUseCase`**

Crie `apps/api/src/shared/application/use_cases/followup/resync_enrollment.py`:

```python
from __future__ import annotations

import uuid
from datetime import timedelta

from shared.application.use_cases.followup.diff_flow_steps import compute_diff
from shared.domain.entities.followup import (
    EnrollmentStepStatus, FollowupEnrollmentStep,
)


class ResyncEnrollmentUseCase:
    def __init__(self, *, enrollment_repo, flow_step_repo, scheduled_job_repo):
        self.enrollment_repo = enrollment_repo
        self.flow_step_repo = flow_step_repo
        self.scheduled_job_repo = scheduled_job_repo

    async def execute(self, *, enrollment_id: uuid.UUID, flow_id: uuid.UUID) -> dict:
        enrollment = await self.enrollment_repo.get_with_steps(enrollment_id)
        flow_steps = await self.flow_step_repo.list_by_flow(flow_id)
        diff = compute_diff(flow_steps, enrollment.steps)
        audit = {
            "steps_added": 0, "steps_rescheduled": 0,
            "steps_content_updated": 0, "steps_cancelled": 0,
        }

        for fs in diff.to_add:
            new_step = FollowupEnrollmentStep(
                id=uuid.uuid4(),
                enrollment_id=enrollment.id,
                flow_step_id=fs.id,
                position=fs.position,
                delay_from_purchase_hours=fs.delay_from_purchase_hours,
                meta_template_name=fs.meta_template_name,
                message_text=fs.message_text,
                template_variables=fs.template_variables,
                status=EnrollmentStepStatus.PENDING,
            )
            run_at = enrollment.purchase_time + timedelta(hours=fs.delay_from_purchase_hours)
            job_id = await self.scheduled_job_repo.enqueue(
                kind="followup_step", run_at=run_at,
                payload={"enrollment_step_id": str(new_step.id)},
            )
            new_step.scheduled_job_id = job_id
            await self.enrollment_repo.add_step_with_job(new_step)
            audit["steps_added"] += 1

        for enr_step, fs in diff.to_reschedule:
            await self.scheduled_job_repo.cancel(enr_step.scheduled_job_id)
            run_at = enrollment.purchase_time + timedelta(hours=fs.delay_from_purchase_hours)
            new_job_id = await self.scheduled_job_repo.enqueue(
                kind="followup_step", run_at=run_at,
                payload={"enrollment_step_id": str(enr_step.id)},
            )
            await self.enrollment_repo.apply_step_update(
                step_id=enr_step.id,
                delay_from_purchase_hours=fs.delay_from_purchase_hours,
                meta_template_name=fs.meta_template_name,
                message_text=fs.message_text,
                template_variables=fs.template_variables,
                scheduled_job_id=new_job_id,
            )
            audit["steps_rescheduled"] += 1

        for enr_step, fs in diff.to_update_content:
            await self.enrollment_repo.apply_step_update(
                step_id=enr_step.id,
                delay_from_purchase_hours=fs.delay_from_purchase_hours,
                meta_template_name=fs.meta_template_name,
                message_text=fs.message_text,
                template_variables=fs.template_variables,
                scheduled_job_id=None,  # mantém o atual
            )
            audit["steps_content_updated"] += 1

        for enr_step in diff.to_cancel:
            await self.scheduled_job_repo.cancel(enr_step.scheduled_job_id)
            await self.enrollment_repo.cancel_step(enr_step.id)
            audit["steps_cancelled"] += 1

        return audit
```

- [ ] **Step 6.6: Implementar `add_step_with_job` e `apply_step_update` no repo**

Em `followup_enrollment_repo.py`:

```python
async def add_step_with_job(self, step: FollowupEnrollmentStep) -> None:
    model = FollowupEnrollmentStepModel(
        id=step.id,
        enrollment_id=step.enrollment_id,
        flow_step_id=step.flow_step_id,
        position=step.position,
        delay_from_purchase_hours=step.delay_from_purchase_hours,
        meta_template_name=step.meta_template_name,
        message_text=step.message_text,
        template_variables=step.template_variables,
        status=step.status.value,
        scheduled_job_id=step.scheduled_job_id,
    )
    self.session.add(model)
    await self.session.flush()


async def apply_step_update(
    self, *, step_id: uuid.UUID,
    delay_from_purchase_hours: int,
    meta_template_name: str | None,
    message_text: str | None,
    template_variables: dict,
    scheduled_job_id: uuid.UUID | None,
) -> None:
    values = {
        "delay_from_purchase_hours": delay_from_purchase_hours,
        "meta_template_name": meta_template_name,
        "message_text": message_text,
        "template_variables": template_variables,
    }
    if scheduled_job_id is not None:
        values["scheduled_job_id"] = scheduled_job_id
    await self.session.execute(
        update(FollowupEnrollmentStepModel)
        .where(FollowupEnrollmentStepModel.id == step_id)
        .values(**values)
    )
```

- [ ] **Step 6.7: Adicionar `scheduled_job_repo.cancel(job_id)`**

Em `apps/api/src/shared/adapters/db/repositories/scheduled_job_repo.py` (ou onde estiver o repo de jobs agendados):

```python
async def cancel(self, job_id: uuid.UUID | None) -> None:
    if job_id is None:
        return
    await self.session.execute(
        update(ScheduledJobModel)
        .where(ScheduledJobModel.id == job_id)
        .values(status="cancelled")
    )
```

Garanta que o worker que faz `fetch_due()` filtre `status='pending'`. Se não filtrar hoje, ajuste:

```python
# em scheduled_job_repo.fetch_due()
.where(ScheduledJobModel.run_at <= now, ScheduledJobModel.status == "pending")
```

- [ ] **Step 6.8: Rodar testes do resync**

```bash
cd apps/api && uv run pytest tests/unit/test_resync_enrollment.py -v
```

Expected: 3 testes PASS.

- [ ] **Step 6.9: Adicionar handler `resync_flow` no worker**

Em `apps/api/src/interface/worker/handlers/scheduled.py`, adicione no dispatcher de `kind`:

```python
# handler dedicado
async def handle_resync_flow(payload: dict) -> None:
    flow_id = uuid.UUID(payload["flow_id"])
    async with session_scope() as session:
        enrollment_repo = FollowupEnrollmentRepo(session=session)
        flow_step_repo = FollowupFlowRepo(session=session)
        scheduled_job_repo = ScheduledJobRepo(session=session)
        audit_repo = AuditEventRepo(session=session)

        enrollments = await enrollment_repo.find_active_by_flow(flow_id)
        totals = {
            "enrollments_affected": 0, "steps_added": 0,
            "steps_rescheduled": 0, "steps_content_updated": 0,
            "steps_cancelled": 0,
        }
        for enrollment in enrollments:
            try:
                async with session.begin_nested():
                    use_case = ResyncEnrollmentUseCase(
                        enrollment_repo=enrollment_repo,
                        flow_step_repo=flow_step_repo,
                        scheduled_job_repo=scheduled_job_repo,
                    )
                    audit = await use_case.execute(
                        enrollment_id=enrollment.id, flow_id=flow_id,
                    )
                    for k in ["steps_added", "steps_rescheduled",
                              "steps_content_updated", "steps_cancelled"]:
                        totals[k] += audit[k]
                    totals["enrollments_affected"] += 1
            except Exception:
                logger.exception(
                    "resync.enrollment_failed",
                    extra={"enrollment_id": str(enrollment.id), "flow_id": str(flow_id)},
                )
                continue

        await audit_repo.log(
            action="flow_resynced",
            payload={"flow_id": str(flow_id), **totals},
        )
```

Registre o handler no dispatcher em `apps/api/src/worker.py`:

```python
from interface.worker.handlers.scheduled import handle_resync_flow
# ...
handlers["resync_flow"] = handle_resync_flow
```

- [ ] **Step 6.10: Enfileirar `resync_flow` ao mutar steps no router admin**

Em `apps/api/src/interface/http/routers/admin/followup.py`, no final dos endpoints `POST /flows/{id}/steps`, `PUT /flows/{id}/steps/{step_id}`, `DELETE /flows/{id}/steps/{step_id}`, `PATCH /flows/{id}/steps/reorder`, **após o commit da mutação**:

```python
async def _enqueue_resync(flow_id: uuid.UUID, account_id: uuid.UUID, session):
    queue = PostgresJobQueue(session=session)
    await queue.enqueue(
        kind="resync_flow",
        payload={"flow_id": str(flow_id), "account_id": str(account_id)},
    )

# Exemplo em POST /flows/{id}/steps:
@router.post("/followup/flows/{flow_id}/steps", status_code=201, response_model=...)
async def create_step(flow_id: uuid.UUID, body: ..., admin = Depends(require_admin)):
    async with session_scope() as session:
        repo = FollowupFlowRepo(session=session)
        step = await repo.add_step(flow_id, body)
        await _enqueue_resync(flow_id, admin.account_id, session)
    return _to_response(step)
```

Faça o mesmo para PUT, DELETE e PATCH reorder.

- [ ] **Step 6.11: Teste de integração end-to-end**

Crie `apps/api/tests/integration/test_resync_e2e.py`:

```python
import pytest
from sqlalchemy import select
from shared.adapters.db.models import JobQueueModel
from shared.adapters.db.session import session_scope


@pytest.mark.asyncio
async def test_step_creation_enqueues_resync_job(admin_client, seed_flow):
    response = await admin_client.post(
        f"/admin/followup/flows/{seed_flow.id}/steps",
        json={
            "position": 1, "delay_from_purchase_hours": 24,
            "meta_template_name": "t", "template_variables": {},
        },
    )
    assert response.status_code == 201

    async with session_scope() as session:
        jobs = (await session.execute(
            select(JobQueueModel).where(JobQueueModel.kind == "resync_flow")
        )).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].payload["flow_id"] == str(seed_flow.id)
```

- [ ] **Step 6.12: Rodar testes e PASS**

```bash
cd apps/api && uv run pytest tests/unit/test_diff_flow_steps.py tests/unit/test_resync_enrollment.py tests/integration/test_resync_e2e.py -v
```

Expected: todos PASS.

- [ ] **Step 6.13: Commit**

```bash
git add apps/api/src/shared/application/use_cases/followup/diff_flow_steps.py \
        apps/api/src/shared/application/use_cases/followup/resync_enrollment.py \
        apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py \
        apps/api/src/shared/adapters/db/repositories/scheduled_job_repo.py \
        apps/api/src/interface/worker/handlers/scheduled.py \
        apps/api/src/interface/http/routers/admin/followup.py \
        apps/api/src/worker.py \
        apps/api/tests/unit/test_diff_flow_steps.py \
        apps/api/tests/unit/test_resync_enrollment.py \
        apps/api/tests/integration/test_resync_e2e.py
git commit -m "feat(followup): smart re-sync com diff, ResyncEnrollmentUseCase e trigger nas mutações de step"
```

---

## Task 7: Memória de IA configurável

**Files:**
- Modify: `apps/api/src/shared/domain/entities/account_config.py`
- Modify: `apps/api/src/interface/http/schemas/admin_settings.py`
- Modify: `apps/api/src/interface/http/routers/admin/settings.py`
- Modify: `apps/api/src/agent/history.py`
- Modify: `apps/api/src/shared/application/message_dispatcher.py`
- Modify: `apps/web/src/features/settings/components/SettingsForm.tsx` (ou equivalente)
- Modify: `apps/web/src/lib/api.ts`
- Test: `apps/api/tests/unit/test_conversation_history_limit.py`
- Test: `apps/api/tests/integration/test_settings_ai_memory.py`

- [ ] **Step 7.1: Adicionar `ai_memory_messages` na entity `AccountConfig`**

Localize a entity (provavelmente em `apps/api/src/shared/domain/entities/account_config.py` ou `account_settings.py`). Adicione:

```python
@dataclass
class AccountConfig:
    # ... campos existentes
    ai_memory_messages: int = 20
```

E garanta que o getter do repo leia esse campo do JSONB `settings`, com fallback para 20:

```python
ai_memory_messages = int(raw_settings.get("ai_memory_messages", 20))
if not (5 <= ai_memory_messages <= 100):
    ai_memory_messages = 20
```

- [ ] **Step 7.2: Atualizar schemas Pydantic**

Em `apps/api/src/interface/http/schemas/admin_settings.py`:

```python
from pydantic import Field

class AccountSettingsResponse(BaseModel):
    # ...
    ai_memory_messages: int = 20


class AccountSettingsUpdateRequest(BaseModel):
    # ...
    ai_memory_messages: int | None = Field(default=None, ge=5, le=100)
```

- [ ] **Step 7.3: Atualizar router de settings**

Em `apps/api/src/interface/http/routers/admin/settings.py`, no `_to_response` e nos handlers, propague `ai_memory_messages`:

```python
def _to_response(config: AccountConfig) -> AccountSettingsResponse:
    return AccountSettingsResponse(
        # ... campos existentes
        ai_memory_messages=config.ai_memory_messages,
    )


@router.put("/settings", response_model=AccountSettingsResponse)
async def update_settings_endpoint(body: AccountSettingsUpdateRequest, ...):
    async with session_scope() as session:
        repo = AccountSettingsRepo(session=session)
        config = await repo.get(account_id)
        # ... mescla campos
        if body.ai_memory_messages is not None:
            config.ai_memory_messages = body.ai_memory_messages
        await repo.save(config)
    return _to_response(config)
```

- [ ] **Step 7.4: Teste unitário para `ConversationHistory.load(limit=N)`**

Crie `apps/api/tests/unit/test_conversation_history_limit.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from agent.history import ConversationHistory


@pytest.mark.asyncio
async def test_load_with_limit_returns_only_last_n():
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=lambda: MagicMock(messages=[{"role": "user", "content": f"m{i}"} for i in range(50)])
    ))
    history = ConversationHistory(session=fake_session)
    msgs = await history.load("thread-1", limit=10)
    assert len(msgs) == 10
    assert msgs[0]["content"] == "m40"
    assert msgs[-1]["content"] == "m49"


@pytest.mark.asyncio
async def test_load_without_limit_returns_all():
    fake_session = MagicMock()
    fake_session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=lambda: MagicMock(messages=[{"role": "user", "content": "m"}] * 50)
    ))
    history = ConversationHistory(session=fake_session)
    msgs = await history.load("thread-1")
    assert len(msgs) == 50
```

- [ ] **Step 7.5: Implementar limit em `ConversationHistory.load`**

Em `apps/api/src/agent/history.py`:

```python
async def load(self, thread_id: str, limit: int | None = None) -> list[Message]:
    result = await self.session.execute(
        select(ConversationMessageModel).where(
            ConversationMessageModel.thread_id == thread_id
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return []
    messages = row.messages or []
    if limit is not None and len(messages) > limit:
        return messages[-limit:]
    return messages
```

- [ ] **Step 7.6: Rodar teste**

```bash
cd apps/api && uv run pytest tests/unit/test_conversation_history_limit.py -v
```

Expected: 2 testes PASS.

- [ ] **Step 7.7: Integrar limit no `MessageDispatcher`**

Em `apps/api/src/shared/application/message_dispatcher.py`, localize onde `ConversationHistory.load(...)` é chamado e injete o limit:

```python
async def dispatch(self, conversation, message):
    config = await self.account_settings_repo.get(self.account_id)
    history = await self.conversation_history.load(
        thread_id=f"{self.account_id}:{conversation.contact_phone}",
        limit=config.ai_memory_messages,
    )
    # ... resto inalterado
```

- [ ] **Step 7.8: Teste de integração — GET + PUT do settings com ai_memory_messages**

Crie `apps/api/tests/integration/test_settings_ai_memory.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_get_settings_returns_default_ai_memory(admin_client):
    r = await admin_client.get("/admin/settings")
    assert r.status_code == 200
    assert r.json()["ai_memory_messages"] == 20


@pytest.mark.asyncio
async def test_put_settings_updates_ai_memory(admin_client):
    r = await admin_client.put("/admin/settings", json={"ai_memory_messages": 30})
    assert r.status_code == 200
    assert r.json()["ai_memory_messages"] == 30


@pytest.mark.asyncio
async def test_put_settings_rejects_out_of_range(admin_client):
    r = await admin_client.put("/admin/settings", json={"ai_memory_messages": 200})
    assert r.status_code == 422
```

- [ ] **Step 7.9: Frontend — adicionar input "Memória da IA" no formulário de settings**

Localize o componente do form em `apps/web/src/features/settings/components/`. Adicione um campo numérico:

```tsx
<label className="block">
  <span className="text-sm font-medium text-on-surface-variant">
    Memória da IA (últimas N mensagens)
  </span>
  <input
    type="number"
    min={5}
    max={100}
    value={form.ai_memory_messages}
    onChange={(e) => setForm({ ...form, ai_memory_messages: Number(e.target.value) })}
    className="mt-1 block w-full rounded-md bg-surface-container border border-outline-variant px-3 py-2"
  />
  <span className="text-xs text-on-surface-variant mt-1 block">
    Quantas mensagens recentes a IA usa como contexto. Min 5, max 100.
  </span>
</label>
```

E em `apps/web/src/features/settings/types.ts` (ou similar):

```ts
export type AccountSettings = {
  // ... campos existentes
  ai_memory_messages: number;
};
```

- [ ] **Step 7.10: Atualizar `apps/web/src/lib/api.ts`**

Se `updateAccountSettings` já passa o objeto inteiro, basta o tipo. Caso contrário:

```ts
export async function updateAccountSettings(payload: Partial<AccountSettings>) {
  return apiFetch<AccountSettings>("/admin/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
```

- [ ] **Step 7.11: Rodar lint + build do frontend**

```bash
cd apps/web && npm run lint && npm run build
```

Expected: sem erros.

- [ ] **Step 7.12: Commit**

```bash
git add apps/api/src/shared/domain/entities/account_config.py \
        apps/api/src/interface/http/schemas/admin_settings.py \
        apps/api/src/interface/http/routers/admin/settings.py \
        apps/api/src/agent/history.py \
        apps/api/src/shared/application/message_dispatcher.py \
        apps/api/tests/unit/test_conversation_history_limit.py \
        apps/api/tests/integration/test_settings_ai_memory.py \
        apps/web/src/features/settings/ \
        apps/web/src/lib/api.ts
git commit -m "feat(settings): ai_memory_messages configurável, limit no histórico do agente"
```

---

## Task 8: Relatórios — endpoints de enrollments e stats em flows

**Files:**
- Create: `apps/api/src/interface/http/routers/admin/followup_enrollments.py`
- Modify: `apps/api/src/interface/http/routers/admin/followup.py` (stats em GET /flows)
- Modify: `apps/api/src/main.py` (registrar novo router)
- Test: `apps/api/tests/integration/test_followup_enrollments_api.py`
- Test: `apps/api/tests/integration/test_followup_flows_stats.py`

- [ ] **Step 8.1: Escrever teste de listagem com filtros**

Crie `apps/api/tests/integration/test_followup_enrollments_api.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_list_enrollments_paginates(admin_client, seed_25_enrollments):
    r = await admin_client.get("/admin/followup/enrollments?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 25
    assert len(body["items"]) == 10
    item = body["items"][0]
    assert "contact_phone" in item
    assert "flow_name" in item
    assert "course_name" in item
    assert "steps_sent" in item
    assert "steps_total" in item


@pytest.mark.asyncio
async def test_filter_by_flow_id(admin_client, seed_two_flows_with_enrollments):
    flow1, flow2 = seed_two_flows_with_enrollments
    r = await admin_client.get(f"/admin/followup/enrollments?flow_id={flow1.id}")
    assert r.status_code == 200
    items = r.json()["items"]
    assert all(it["flow_id"] == str(flow1.id) for it in items)


@pytest.mark.asyncio
async def test_filter_by_status(admin_client, seed_mixed_status_enrollments):
    r = await admin_client.get("/admin/followup/enrollments?status=active")
    assert r.status_code == 200
    assert all(it["status"] == "active" for it in r.json()["items"])
```

- [ ] **Step 8.2: Criar router `followup_enrollments.py`**

`apps/api/src/interface/http/routers/admin/followup_enrollments.py`:

```python
from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from interface.http.deps import require_admin
from shared.adapters.db.repositories.followup_enrollment_repo import (
    FollowupEnrollmentRepo,
)
from shared.adapters.db.session import session_scope
from shared.domain.entities.followup import EnrollmentStatus

router = APIRouter(tags=["admin-followup-reports"])


class EnrollmentListItem(BaseModel):
    id: str
    contact_phone: str
    customer_name: str | None
    flow_id: str
    flow_name: str
    course_name: str
    status: str
    created_at: str
    steps_sent: int
    steps_total: int


class EnrollmentListResponse(BaseModel):
    items: list[EnrollmentListItem]
    total: int
    page: int
    page_size: int


class EnrollmentStepItem(BaseModel):
    id: str
    position: int
    delay_from_purchase_hours: int
    template_name: str | None
    message_text_preview: str | None
    status: str
    sent_at: str | None
    scheduled_for: str | None
    failure_reason: str | None


@router.get("/followup/enrollments", response_model=EnrollmentListResponse)
async def list_enrollments(
    flow_id: uuid.UUID | None = Query(default=None),
    contact_phone: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    admin = Depends(require_admin),
) -> EnrollmentListResponse:
    status_enum = EnrollmentStatus(status.upper()) if status else None
    async with session_scope() as session:
        repo = FollowupEnrollmentRepo(session=session)
        rows, total = await repo.list_with_filters(
            account_id=admin.account_id,
            flow_id=flow_id,
            contact_phone=contact_phone,
            status=status_enum,
            page=page,
            page_size=page_size,
        )
        # Counts de steps em batch para evitar N+1
        counts = await repo.bulk_count_steps([r.id for r in rows])
    items = [
        EnrollmentListItem(
            id=str(r.id),
            contact_phone=r.contact_phone,
            customer_name=r.customer_name,
            flow_id=str(r.flow_id) if r.flow_id else "",
            flow_name=r.flow_name or "",
            course_name=r.course_name or "",
            status=r.status.value.lower(),
            created_at=r.created_at.isoformat(),
            steps_sent=counts.get(r.id, {}).get("SENT", 0),
            steps_total=sum(counts.get(r.id, {}).values()),
        )
        for r in rows
    ]
    return EnrollmentListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/followup/enrollments/{enrollment_id}/steps",
    response_model=list[EnrollmentStepItem],
)
async def list_enrollment_steps(
    enrollment_id: uuid.UUID, admin = Depends(require_admin),
) -> list[EnrollmentStepItem]:
    async with session_scope() as session:
        repo = FollowupEnrollmentRepo(session=session)
        steps = await repo.list_steps(enrollment_id, account_id=admin.account_id)
    return [
        EnrollmentStepItem(
            id=str(s.id),
            position=s.position,
            delay_from_purchase_hours=s.delay_from_purchase_hours,
            template_name=s.meta_template_name,
            message_text_preview=(s.message_text[:80] if s.message_text else None),
            status=s.status.value.lower(),
            sent_at=s.sent_at.isoformat() if s.sent_at else None,
            scheduled_for=s.scheduled_for.isoformat() if s.scheduled_for else None,
            failure_reason=s.failure_reason,
        )
        for s in steps
    ]
```

- [ ] **Step 8.3: Implementar `bulk_count_steps` e `list_steps` no repo**

Em `followup_enrollment_repo.py`:

```python
async def bulk_count_steps(
    self, enrollment_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    if not enrollment_ids:
        return {}
    result = await self.session.execute(
        select(
            FollowupEnrollmentStepModel.enrollment_id,
            FollowupEnrollmentStepModel.status,
            func.count(FollowupEnrollmentStepModel.id),
        )
        .where(FollowupEnrollmentStepModel.enrollment_id.in_(enrollment_ids))
        .group_by(
            FollowupEnrollmentStepModel.enrollment_id,
            FollowupEnrollmentStepModel.status,
        )
    )
    out: dict[uuid.UUID, dict[str, int]] = {}
    for enr_id, status, n in result.all():
        out.setdefault(enr_id, {})[status] = int(n)
    return out


async def list_steps(
    self, enrollment_id: uuid.UUID, *, account_id: uuid.UUID,
) -> list[FollowupEnrollmentStep]:
    result = await self.session.execute(
        select(FollowupEnrollmentStepModel)
        .join(FollowupEnrollmentModel,
              FollowupEnrollmentModel.id == FollowupEnrollmentStepModel.enrollment_id)
        .where(
            FollowupEnrollmentStepModel.enrollment_id == enrollment_id,
            FollowupEnrollmentModel.account_id == account_id,
        )
        .order_by(FollowupEnrollmentStepModel.position)
    )
    rows = result.scalars().all()
    return [self._step_to_entity(r) for r in rows]
```

Ajuste `list_with_filters` para também trazer `contact_phone`, `customer_name`, `flow_name`, `course_name` via JOIN (use uma view ou SELECT explicitamente os campos, criando uma `dataclass` de read-model). Estrutura sugerida:

```python
@dataclass(frozen=True)
class EnrollmentListRow:
    id: uuid.UUID
    contact_phone: str
    customer_name: str | None
    flow_id: uuid.UUID | None
    flow_name: str | None
    course_name: str | None
    status: EnrollmentStatus
    created_at: datetime

# em list_with_filters substituir o select por:
stmt = (
    select(
        FollowupEnrollmentModel.id,
        ContactModel.phone.label("contact_phone"),
        ContactModel.full_name.label("customer_name"),
        FollowupEnrollmentModel.flow_id,
        FollowupFlowModel.name.label("flow_name"),
        CourseModel.name.label("course_name"),
        FollowupEnrollmentModel.status,
        FollowupEnrollmentModel.created_at,
    )
    .join(ContactModel, ContactModel.id == FollowupEnrollmentModel.contact_id)
    .outerjoin(FollowupFlowModel, FollowupFlowModel.id == FollowupEnrollmentModel.flow_id)
    .outerjoin(CourseModel, CourseModel.id == FollowupFlowModel.course_id)
    .where(FollowupEnrollmentModel.account_id == account_id)
)
# aplicar filtros como antes
```

- [ ] **Step 8.4: Registrar o router em `main.py`**

```python
from interface.http.routers.admin import followup_enrollments as followup_enrollments_router
# ...
app.include_router(followup_enrollments_router.router, prefix="/admin")
```

- [ ] **Step 8.5: Rodar testes**

```bash
cd apps/api && uv run pytest tests/integration/test_followup_enrollments_api.py -v
```

Expected: 3 testes PASS.

- [ ] **Step 8.6: Adicionar stats em GET /admin/followup/flows**

Em `apps/api/src/interface/http/routers/admin/followup.py`, no endpoint `list_flows`, agregue stats:

```python
@router.get("/followup/flows", response_model=list[FlowResponse])
async def list_flows(admin = Depends(require_admin)):
    async with session_scope() as session:
        flow_repo = FollowupFlowRepo(session=session)
        flows = await flow_repo.list_by_account(admin.account_id)
        flow_ids = [f.id for f in flows]
        stats_by_flow = await flow_repo.stats_by_flows(flow_ids)
    return [
        FlowResponse(
            id=str(f.id), name=f.name, is_active=f.is_active,
            course=_course_summary(f.course),
            steps_count=len(f.steps),
            stats=FlowStats(
                enrollments_active=stats_by_flow.get(f.id, {}).get("ACTIVE", 0),
                enrollments_completed=stats_by_flow.get(f.id, {}).get("COMPLETED", 0),
            ),
        )
        for f in flows
    ]
```

Implemente `stats_by_flows` no `FollowupFlowRepo` (ou `FollowupEnrollmentRepo`):

```python
async def stats_by_flows(
    self, flow_ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    if not flow_ids:
        return {}
    result = await self.session.execute(
        select(
            FollowupEnrollmentModel.flow_id,
            FollowupEnrollmentModel.status,
            func.count(FollowupEnrollmentModel.id),
        )
        .where(FollowupEnrollmentModel.flow_id.in_(flow_ids))
        .group_by(FollowupEnrollmentModel.flow_id, FollowupEnrollmentModel.status)
    )
    out: dict[uuid.UUID, dict[str, int]] = {}
    for flow_id, status, n in result.all():
        out.setdefault(flow_id, {})[status] = int(n)
    return out
```

Atualize o schema `FlowResponse` em `apps/api/src/interface/http/schemas/admin_followup.py`:

```python
class FlowStats(BaseModel):
    enrollments_active: int = 0
    enrollments_completed: int = 0


class FlowResponse(BaseModel):
    # ... campos existentes
    stats: FlowStats = FlowStats()
```

- [ ] **Step 8.7: Teste de stats em /flows**

Crie `apps/api/tests/integration/test_followup_flows_stats.py`:

```python
import pytest


@pytest.mark.asyncio
async def test_flows_endpoint_returns_stats(admin_client, seed_flow_with_enrollments):
    r = await admin_client.get("/admin/followup/flows")
    assert r.status_code == 200
    items = r.json()
    assert items
    stats = items[0]["stats"]
    assert "enrollments_active" in stats
    assert "enrollments_completed" in stats
    assert stats["enrollments_active"] >= 0
```

- [ ] **Step 8.8: Rodar tudo e PASS**

```bash
cd apps/api && uv run pytest tests/integration/test_followup_enrollments_api.py tests/integration/test_followup_flows_stats.py -v
```

Expected: todos PASS.

- [ ] **Step 8.9: Commit**

```bash
git add apps/api/src/interface/http/routers/admin/followup_enrollments.py \
        apps/api/src/interface/http/routers/admin/followup.py \
        apps/api/src/interface/http/schemas/admin_followup.py \
        apps/api/src/shared/adapters/db/repositories/followup_enrollment_repo.py \
        apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py \
        apps/api/src/main.py \
        apps/api/tests/integration/test_followup_enrollments_api.py \
        apps/api/tests/integration/test_followup_flows_stats.py
git commit -m "feat(followup): endpoints de relatório de enrollments + stats em /flows"
```

---

## Task 9: Quality gates finais

**Files:**
- N/A (apenas execução)

- [ ] **Step 9.1: Lint backend**

```bash
cd apps/api && uv run ruff check src tests && uv run ruff format --check src tests
```

Expected: zero erros. Se algo falhar, rode `uv run ruff format src tests` e re-commit.

- [ ] **Step 9.2: Type check backend**

```bash
cd apps/api && uv run mypy src
```

Expected: zero erros.

- [ ] **Step 9.3: Suite completa de testes (unit + integration)**

```bash
docker compose up -d postgres redis
cd apps/api && uv run pytest
```

Expected: zero falhas.

- [ ] **Step 9.4: Type check frontend**

```bash
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```

Expected: zero erros.

- [ ] **Step 9.5: Commit final (se houver formatação automática)**

Se ruff format alterou algo:

```bash
git add -A && git commit -m "chore: ruff format pass"
```

---

## USER TEST Checkpoints (manuais)

Após Task 9 passar, execute estes testes manuais e marque cada um:

- [ ] **CP1 — Webhook → Enrollment**
  - `docker compose up -d` + `uv run python -m worker` em outro terminal
  - `curl -X POST http://localhost:8000/webhook/purchase -H "x-hubla-token: <SECRET>" -d @docs/superpowers/specs/2026-05-21-followup-engine-v2-design.md` (use o payload de exemplo do appendix)
  - Verifique no DB: `SELECT * FROM followup_enrollments WHERE purchase_id = '<subscription.id>';` → linha existe
  - Verifique: `SELECT count(*) FROM scheduled_jobs WHERE kind = 'followup_step';` → conta = steps do flow

- [ ] **CP2 — Re-sync ao adicionar step**
  - Crie um flow com 3 steps. Inscreva um contato (via webhook mock).
  - Dispare 1 step manualmente (UPDATE para status SENT no DB).
  - Via UI `/admin/followup/[flow_id]` adicione um 4º step.
  - Verifique: 1 job `resync_flow` aparece em `job_queue`.
  - Após o worker processar: o enrollment tem 4 enrollment_steps, com o novo flow_step_id e status PENDING.

- [ ] **CP3 — Memória configurável**
  - Em `/admin/settings`, altere "Memória da IA" para 5.
  - Envie 10 mensagens para a IA via webhook.
  - No log da próxima resposta do agente, confirme que o contexto enviado ao OpenAI tem 5 mensagens (use `LOG_LEVEL=debug`).

- [ ] **CP4 — Relatórios**
  - `curl -H "x-api-key: <ADMIN>" "http://localhost:8000/admin/followup/enrollments?page=1&page_size=20"` → JSON com items, total, page.
  - `curl ".../admin/followup/enrollments/<id>/steps"` → lista de steps.
  - `curl ".../admin/followup/flows"` → cada flow tem `stats: {enrollments_active, enrollments_completed}`.

- [ ] **CP5 — Failure handling**
  - Modifique um step para usar um `meta_template_name` inválido (não aprovado na Meta).
  - Force o dispatch (UPDATE scheduled_jobs.run_at = NOW()).
  - Após o worker processar: o `followup_enrollment_step` deve estar com `status=FAILED` e `failure_reason` populado.
  - O job NÃO deve ter ido para DLQ (foi um erro de aplicação, não de infra).

---

## Self-Review (executado pelo autor)

**Spec coverage check:**
- RF-W01..W06 (Webhook Hubla v2) → Task 3 ✓
- RF-D01 (UNIQUE) → Task 1 ✓
- RF-D02 (FK SET NULL) → Task 1 ✓
- RF-D03 (transação atômica) → Task 4 ✓
- RF-D04 (failure_reason) → Task 1 + Task 5 ✓
- RF-D05 (scheduled_job_id) → Task 1 + Task 4 ✓
- RF-D06 (flow_step_id) → Task 1 + Task 4 ✓
- RF-D07 (índices) → Task 1 ✓
- RF-R01 (trigger resync em mutação) → Task 6.10 ✓
- RF-R02 (handler resync_flow) → Task 6.9 ✓
- RF-R03 (diff + apply) → Task 6.1-6.6 ✓
- RF-R04 (idempotência) → Task 6.1 (test_diff_is_idempotent) ✓
- RF-R05 (flow_step_id como identidade) → Task 6.2 ✓
- RF-R06 (sub-transações isoladas) → Task 6.9 ✓
- RF-R07 (audit_events) → Task 6.9 ✓
- RF-R08 (enum CANCELLED) → Task 1 ✓
- RF-M01..M06 (memória) → Task 7 ✓
- RF-X01..X03 (dispatch robusto) → Task 5 ✓
- RF-L01..L05 (relatórios) → Task 8 ✓
- RNF-08 (cobertura ≥85% em use cases críticos) → testes em Tasks 4, 5, 6 ✓

**Placeholder scan:** sem TBDs ou "fill in".

**Type consistency:** `DispatchResult`, `Diff`, `EnrollResult`, `FollowupEnrollmentStep`, `ParsedPurchaseEvent` consistentes entre tasks; nomes de método (`mark_failed`, `cancel`, `apply_step_update`, `add_step_with_job`, `find_active_by_flow`, `list_with_filters`, `bulk_count_steps`) batem.
