# Sistema de Leads Hubla — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capturar todos os eventos Hubla em `hubla_events` e materializar dados de lead (UTMs, valores, dados de sessão) em `leads`. Expor via `/admin/leads` com filtros, paginação e exportação CSV. Adicionar item "Leads" na sidebar.

**Architecture:** Duas novas tabelas: `hubla_events` (log imutável) e `leads` (upsert por `hubla_subscription_id`). O `HublaEventHandler` (do plano `trigger-based-followup`) é estendido para gravar em ambas as tabelas. Três endpoints admin: listagem, detalhe com timeline, exportação CSV.

**Tech Stack:** SQLAlchemy/Alembic, FastAPI, Next.js App Router, Tailwind

> **Pré-requisitos:** Planos `rename-cursos-produtos` e `trigger-based-followup` já aplicados. O `HublaEventHandler` existe em `shared/application/hubla_event_handler.py`.

---

## File Map

**Backend — create:**
- `apps/api/migrations/versions/<hash>_create_hubla_events_leads.py`
- `apps/api/src/shared/adapters/db/repositories/hubla_event_repo.py`
- `apps/api/src/shared/adapters/db/repositories/lead_repo.py`
- `apps/api/src/interface/http/routers/admin/leads.py`

**Backend — modify:**
- `apps/api/src/shared/adapters/db/models.py` — 2 novos models
- `apps/api/src/shared/application/hubla_event_handler.py` — chamar repos ao processar
- `apps/api/src/main.py` — registrar router leads

**Frontend — create:**
- `apps/web/src/features/leads/types.ts`
- `apps/web/src/features/leads/hooks/useLeads.ts`
- `apps/web/src/features/leads/components/LeadTable.tsx`
- `apps/web/src/features/leads/components/LeadDrawer.tsx`
- `apps/web/src/app/(admin)/leads/page.tsx`

**Frontend — modify:**
- `apps/web/src/lib/api.ts` — adicionar funções de leads
- `apps/web/src/shared/components/layout/Sidebar.tsx` — adicionar item Leads

---

### Task 1: Migration — tabelas hubla_events e leads

**Files:**
- Create: `apps/api/migrations/versions/<hash>_create_hubla_events_leads.py`

- [ ] **Step 1: Criar migration**

```bash
cd apps/api
uv run alembic revision -m "create_hubla_events_and_leads"
```

Substituir conteúdo pelo seguinte:

```python
"""create hubla_events and leads tables

Revision ID: <gerado>
Revises: <anterior>
Create Date: 2026-05-22
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "<gerado>"
down_revision = "<anterior>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hubla_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("hubla_subscription_id", sa.String(100), nullable=False),
        sa.Column("hubla_product_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("product_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("payer_phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("payer_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("payer_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hubla_events_account_type", "hubla_events", ["account_id", "event_type"])
    op.create_index("ix_hubla_events_subscription", "hubla_events", ["account_id", "hubla_subscription_id"])

    op.create_table(
        "leads",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("hubla_subscription_id", sa.String(100), nullable=False),
        sa.Column("contact_id", sa.UUID(), nullable=True),
        sa.Column("payer_phone", sa.String(30), nullable=False, server_default=""),
        sa.Column("payer_name", sa.String(200), nullable=False, server_default=""),
        sa.Column("payer_email", sa.String(200), nullable=False, server_default=""),
        sa.Column("payer_document", sa.String(20), nullable=True),
        sa.Column("hubla_product_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("product_name", sa.String(300), nullable=False, server_default=""),
        sa.Column("offer_id", sa.String(100), nullable=True),
        sa.Column("offer_name", sa.String(300), nullable=True),
        sa.Column("amount_total_cents", sa.Integer(), nullable=True),
        sa.Column("amount_subtotal_cents", sa.Integer(), nullable=True),
        sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("subscription_status", sa.String(30), nullable=False, server_default="unknown"),
        sa.Column("utm_source", sa.String(200), nullable=True),
        sa.Column("utm_medium", sa.String(200), nullable=True),
        sa.Column("utm_campaign", sa.String(500), nullable=True),
        sa.Column("utm_content", sa.String(500), nullable=True),
        sa.Column("utm_term", sa.String(200), nullable=True),
        sa.Column("session_ip", sa.String(50), nullable=True),
        sa.Column("session_url", sa.Text(), nullable=True),
        sa.Column("fbp", sa.String(100), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_event_type", sa.String(80), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "hubla_subscription_id", name="uq_leads_account_subscription"),
    )
    op.create_index("ix_leads_account_phone", "leads", ["account_id", "payer_phone"])
    op.create_index("ix_leads_account_status", "leads", ["account_id", "subscription_status"])
    op.create_index("ix_leads_account_activated", "leads", ["account_id", "activated_at"])


def downgrade() -> None:
    op.drop_table("leads")
    op.drop_table("hubla_events")
```

- [ ] **Step 2: Aplicar migration**

```bash
cd apps/api
uv run alembic upgrade heads
```

Esperado: `Running upgrade ... → <rev>, create_hubla_events_and_leads`

- [ ] **Step 3: Commit**

```bash
git add apps/api/migrations/
git commit -m "feat(db): cria tabelas hubla_events e leads"
```

---

### Task 2: Backend — Models + Repositories

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Create: `apps/api/src/shared/adapters/db/repositories/hubla_event_repo.py`
- Create: `apps/api/src/shared/adapters/db/repositories/lead_repo.py`

- [ ] **Step 1: Adicionar HublaEventModel ao models.py**

Em `apps/api/src/shared/adapters/db/models.py`, adicionar após `WebhookEventModel`:

```python
class HublaEventModel(Base):
    __tablename__ = "hubla_events"
    __table_args__ = (
        Index("ix_hubla_events_account_type", "account_id", "event_type"),
        Index("ix_hubla_events_subscription", "account_id", "hubla_subscription_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(80))
    hubla_subscription_id: Mapped[str] = mapped_column(String(100))
    hubla_product_id: Mapped[str] = mapped_column(String(100), default="")
    product_name: Mapped[str] = mapped_column(String(300), default="")
    payer_phone: Mapped[str] = mapped_column(String(30), default="")
    payer_email: Mapped[str] = mapped_column(String(200), default="")
    payer_name: Mapped[str] = mapped_column(String(200), default="")
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    payload: Mapped[dict] = mapped_column(JSON)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Adicionar LeadModel ao models.py**

```python
class LeadModel(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("account_id", "hubla_subscription_id", name="uq_leads_account_subscription"),
        Index("ix_leads_account_phone", "account_id", "payer_phone"),
        Index("ix_leads_account_status", "account_id", "subscription_status"),
        Index("ix_leads_account_activated", "account_id", "activated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    hubla_subscription_id: Mapped[str] = mapped_column(String(100))
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    payer_phone: Mapped[str] = mapped_column(String(30), default="")
    payer_name: Mapped[str] = mapped_column(String(200), default="")
    payer_email: Mapped[str] = mapped_column(String(200), default="")
    payer_document: Mapped[str | None] = mapped_column(String(20), nullable=True)
    hubla_product_id: Mapped[str] = mapped_column(String(100), default="")
    product_name: Mapped[str] = mapped_column(String(300), default="")
    offer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    offer_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    amount_total_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount_subtotal_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(30), default="unknown")
    utm_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_medium: Mapped[str | None] = mapped_column(String(200), nullable=True)
    utm_campaign: Mapped[str | None] = mapped_column(String(500), nullable=True)
    utm_content: Mapped[str | None] = mapped_column(String(500), nullable=True)
    utm_term: Mapped[str | None] = mapped_column(String(200), nullable=True)
    session_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    session_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fbp: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_event_type: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 3: Criar SqlHublaEventRepository**

`apps/api/src/shared/adapters/db/repositories/hubla_event_repo.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import HublaEventModel


@dataclass
class SqlHublaEventRepository:
    session: AsyncSession

    async def insert(
        self,
        *,
        account_id: UUID,
        event_type: str,
        hubla_subscription_id: str,
        hubla_product_id: str = "",
        product_name: str = "",
        payer_phone: str = "",
        payer_email: str = "",
        payer_name: str = "",
        contact_id: UUID | None = None,
        payload: dict,
    ) -> HublaEventModel:
        m = HublaEventModel(
            id=uuid4(),
            account_id=account_id,
            event_type=event_type,
            hubla_subscription_id=hubla_subscription_id,
            hubla_product_id=hubla_product_id,
            product_name=product_name,
            payer_phone=payer_phone,
            payer_email=payer_email,
            payer_name=payer_name,
            contact_id=contact_id,
            payload=payload,
            received_at=datetime.now(UTC),
            processed_at=None,
        )
        self.session.add(m)
        await self.session.flush()
        return m
```

- [ ] **Step 4: Criar SqlLeadRepository**

`apps/api/src/shared/adapters/db/repositories/lead_repo.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import LeadModel


@dataclass
class SqlLeadRepository:
    session: AsyncSession

    async def upsert(
        self,
        *,
        account_id: UUID,
        hubla_subscription_id: str,
        event_type: str,
        contact_id: UUID | None = None,
        payer_phone: str = "",
        payer_name: str = "",
        payer_email: str = "",
        payer_document: str | None = None,
        hubla_product_id: str = "",
        product_name: str = "",
        offer_id: str | None = None,
        offer_name: str | None = None,
        amount_total_cents: int | None = None,
        amount_subtotal_cents: int | None = None,
        payment_method: str | None = None,
        subscription_status: str = "unknown",
        utm_source: str | None = None,
        utm_medium: str | None = None,
        utm_campaign: str | None = None,
        utm_content: str | None = None,
        utm_term: str | None = None,
        session_ip: str | None = None,
        session_url: str | None = None,
        fbp: str | None = None,
        event_at: datetime | None = None,
    ) -> LeadModel:
        now = datetime.now(UTC)
        event_time = event_at or now

        values = dict(
            id=uuid4(),
            account_id=account_id,
            hubla_subscription_id=hubla_subscription_id,
            contact_id=contact_id,
            payer_phone=payer_phone,
            payer_name=payer_name,
            payer_email=payer_email,
            payer_document=payer_document,
            hubla_product_id=hubla_product_id,
            product_name=product_name,
            offer_id=offer_id,
            offer_name=offer_name,
            amount_total_cents=amount_total_cents,
            amount_subtotal_cents=amount_subtotal_cents,
            payment_method=payment_method,
            subscription_status=subscription_status,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
            utm_content=utm_content,
            utm_term=utm_term,
            session_ip=session_ip,
            session_url=session_url,
            fbp=fbp,
            first_seen_at=event_time,
            activated_at=event_time if event_type == "subscription.activated" else None,
            last_event_at=event_time,
            last_event_type=event_type,
            created_at=now,
            updated_at=now,
        )

        stmt = pg_insert(LeadModel).values(**values)
        # Em caso de conflito (mesmo hubla_subscription_id + account_id): atualiza status e timestamps
        update_set: dict = {
            "subscription_status": stmt.excluded.subscription_status,
            "last_event_at": stmt.excluded.last_event_at,
            "last_event_type": stmt.excluded.last_event_type,
            "updated_at": stmt.excluded.updated_at,
        }
        # Só seta activated_at se o evento for subscription.activated e ainda for null
        if event_type == "subscription.activated":
            update_set["activated_at"] = stmt.excluded.activated_at
        if contact_id is not None:
            update_set["contact_id"] = stmt.excluded.contact_id

        stmt = stmt.on_conflict_do_update(
            constraint="uq_leads_account_subscription",
            set_=update_set,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        lead = await self.session.get(LeadModel, values["id"])
        if lead is None:
            # Conflito resolvido — buscar pelo subscription_id
            q = select(LeadModel).where(
                LeadModel.account_id == account_id,
                LeadModel.hubla_subscription_id == hubla_subscription_id,
            )
            lead = (await self.session.execute(q)).scalar_one()
        return lead

    async def list(
        self,
        account_id: UUID,
        *,
        product_id: str | None = None,
        status: str | None = None,
        utm_source: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[LeadModel], int]:
        from sqlalchemy import func

        stmt = select(LeadModel).where(LeadModel.account_id == account_id)
        if product_id:
            stmt = stmt.where(LeadModel.hubla_product_id == product_id)
        if status:
            stmt = stmt.where(LeadModel.subscription_status == status)
        if utm_source:
            stmt = stmt.where(LeadModel.utm_source == utm_source)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self.session.execute(total_stmt)).scalar_one()

        stmt = stmt.order_by(LeadModel.last_event_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        rows = (await self.session.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_events(
        self, account_id: UUID, hubla_subscription_id: str
    ) -> list[HublaEventModel]:
        from shared.adapters.db.models import HublaEventModel

        stmt = (
            select(HublaEventModel)
            .where(
                HublaEventModel.account_id == account_id,
                HublaEventModel.hubla_subscription_id == hubla_subscription_id,
            )
            .order_by(HublaEventModel.received_at.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/
git commit -m "feat(api): HublaEventModel, LeadModel e seus repositórios"
```

---

### Task 3: Backend — HublaEventHandler integra os repos

**Files:**
- Modify: `apps/api/src/shared/application/hubla_event_handler.py`

- [ ] **Step 1: Escrever teste para gravação de Lead**

Em `apps/api/tests/unit/test_hubla_event_handler.py`, adicionar:

```python
@pytest.mark.asyncio
async def test_subscription_created_saves_lead_with_utms():
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)  # produto não cadastrado

    lead_repo = AsyncMock()
    hubla_event_repo = AsyncMock()

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
        lead_repo=lead_repo,
        hubla_event_repo=hubla_event_repo,
    )

    payload = {
        "type": "subscription.created",
        "version": "2.0.0",
        "event": {
            "product": {"id": "prod-123", "name": "Produto X"},
            "products": [
                {
                    "id": "prod-123",
                    "name": "Produto X",
                    "offers": [{"id": "offer-1", "name": "Oferta A", "cohorts": []}],
                }
            ],
            "subscription": {
                "id": "sub-abc",
                "payer": {
                    "firstName": "Maria",
                    "lastName": "Souza",
                    "document": "99988877766",
                    "email": "maria@email.com",
                    "phone": "+5521988887777",
                },
                "paymentMethod": "pix",
                "status": "inactive",
                "firstPaymentSession": {
                    "ip": "200.0.0.1",
                    "url": "https://pay.hub.la/offer-1?utm_source=Meta+Ads",
                    "utm": {
                        "source": "Meta Ads",
                        "medium": "cpc",
                        "campaign": "Campanha 1",
                        "content": "Ad 1",
                        "term": "keyword1",
                    },
                    "cookies": {"fbp": "fb.1.123.456789"},
                },
                "lastInvoice": {
                    "amount": {"totalCents": 9700, "subtotalCents": 9700},
                    "paymentMethod": "pix",
                },
            },
        },
    }

    await handler.handle(payload)

    lead_repo.upsert.assert_called_once()
    call_kwargs = lead_repo.upsert.call_args.kwargs
    assert call_kwargs["utm_source"] == "Meta Ads"
    assert call_kwargs["utm_campaign"] == "Campanha 1"
    assert call_kwargs["fbp"] == "fb.1.123.456789"
    assert call_kwargs["amount_total_cents"] == 9700
    assert call_kwargs["subscription_status"] == "inactive"

    hubla_event_repo.insert.assert_called_once()
```

- [ ] **Step 2: Rodar teste — verificar que falha**

```bash
cd apps/api
uv run pytest tests/unit/test_hubla_event_handler.py::test_subscription_created_saves_lead_with_utms -v
```

Esperado: `FAILED` — `HublaEventHandler.__init__` não aceita `lead_repo` e `hubla_event_repo` ainda.

- [ ] **Step 3: Atualizar HublaEventHandler para incluir repos**

Em `apps/api/src/shared/application/hubla_event_handler.py`:

Adicionar parâmetros ao `__init__`:
```python
def __init__(
    self,
    *,
    product_repo: Any,
    flow_repo: Any,
    contact_repo: Any,
    chatnexo: Any,
    enroll_contact_uc: Any,
    purchase_handler: Any,
    lead_repo: Any | None = None,         # ← novo (None = não grava lead)
    hubla_event_repo: Any | None = None,  # ← novo
    account_id: UUID | None = None,
) -> None:
    ...
    self._lead_repo = lead_repo
    self._hubla_event_repo = hubla_event_repo
```

No método `handle`, extrair campos extras do payload e gravar:

```python
# Extrair dados adicionais
first_session = subscription.get("firstPaymentSession", {})
utm = first_session.get("utm", {})
last_invoice = subscription.get("lastInvoice", {})
amount = last_invoice.get("amount", {})
offers = product_data.get("offers", [])
first_offer = offers[0] if offers else {}
cookies = first_session.get("cookies", {})
sub_status = subscription.get("status", "unknown")

# Gravar HublaEvent
if self._hubla_event_repo is not None:
    await self._hubla_event_repo.insert(
        account_id=account_id,
        event_type=event_type,
        hubla_subscription_id=purchase_id,
        hubla_product_id=hubla_product_id,
        product_name=product_name,
        payer_phone=payer_phone,
        payer_email=payer_email,
        payer_name=payer_name,
        payload=payload,
    )

# Upsert Lead
if self._lead_repo is not None:
    await self._lead_repo.upsert(
        account_id=account_id,
        hubla_subscription_id=purchase_id,
        event_type=event_type,
        payer_phone=payer_phone,
        payer_name=payer_name,
        payer_email=payer_email,
        payer_document=payer.get("document"),
        hubla_product_id=hubla_product_id,
        product_name=product_name,
        offer_id=first_offer.get("id"),
        offer_name=first_offer.get("name"),
        amount_total_cents=amount.get("totalCents"),
        amount_subtotal_cents=amount.get("subtotalCents"),
        payment_method=subscription.get("paymentMethod"),
        subscription_status=sub_status,
        utm_source=utm.get("source"),
        utm_medium=utm.get("medium"),
        utm_campaign=utm.get("campaign"),
        utm_content=utm.get("content"),
        utm_term=utm.get("term"),
        session_ip=first_session.get("ip"),
        session_url=first_session.get("url"),
        fbp=cookies.get("fbp"),
        event_at=activated_at,
    )
```

- [ ] **Step 4: Atualizar worker hubla_event.py para injetar repos**

Em `apps/api/src/interface/worker/handlers/hubla_event.py`, adicionar imports e injeção:

```python
from shared.adapters.db.repositories.hubla_event_repo import SqlHublaEventRepository
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository

async def handle_hubla_event(job_payload: dict[str, Any]) -> None:
    ...
    async with session_scope() as session:
        ...
        hubla_event_repo = SqlHublaEventRepository(session=session)
        lead_repo = SqlLeadRepository(session=session)

        handler = HublaEventHandler(
            ...
            lead_repo=lead_repo,
            hubla_event_repo=hubla_event_repo,
        )
        await handler.handle(payload)
```

- [ ] **Step 5: Rodar testes**

```bash
cd apps/api
uv run pytest tests/unit/test_hubla_event_handler.py -v
```

Esperado: todos passando.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/ apps/api/tests/
git commit -m "feat(api): HublaEventHandler grava hubla_events e upsert leads com UTMs"
```

---

### Task 4: Backend — Endpoints Admin /leads

**Files:**
- Create: `apps/api/src/interface/http/routers/admin/leads.py`
- Modify: `apps/api/src/main.py`

- [ ] **Step 1: Criar router leads.py**

`apps/api/src/interface/http/routers/admin/leads.py`:

```python
from __future__ import annotations

import csv
import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from interface.http.deps.admin_auth import AdminAuth, require_admin
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository
from shared.adapters.db.session import session_scope
from pydantic import BaseModel

router = APIRouter(tags=["admin-leads"])


class LeadResponse(BaseModel):
    id: UUID
    hubla_subscription_id: str
    payer_phone: str
    payer_name: str
    payer_email: str
    payer_document: str | None
    hubla_product_id: str
    product_name: str
    offer_name: str | None
    amount_total_cents: int | None
    payment_method: str | None
    subscription_status: str
    utm_source: str | None
    utm_campaign: str | None
    first_seen_at: datetime
    activated_at: datetime | None
    last_event_at: datetime
    last_event_type: str


class LeadListResponse(BaseModel):
    items: list[LeadResponse]
    total: int
    page: int
    page_size: int


class HublaEventResponse(BaseModel):
    id: UUID
    event_type: str
    received_at: datetime
    payer_phone: str
    product_name: str


class LeadDetailResponse(LeadResponse):
    events: list[HublaEventResponse]


async def _get_account_uuid(session: object) -> UUID:
    from sqlalchemy import select
    from shared.adapters.db.models import AccountModel
    result = await session.execute(select(AccountModel.id).limit(1))  # type: ignore[attr-defined]
    return result.scalar_one()


@router.get("/leads", response_model=LeadListResponse)
async def list_leads(
    product_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    utm_source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> LeadListResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        items, total = await repo.list(
            account_uuid,
            product_id=product_id,
            status=status,
            utm_source=utm_source,
            page=page,
            page_size=page_size,
        )
    return LeadListResponse(
        items=[_to_response(m) for m in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/leads/export")
async def export_leads(
    product_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    utm_source: str | None = Query(default=None),
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> StreamingResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        items, _ = await repo.list(
            account_uuid,
            product_id=product_id,
            status=status,
            utm_source=utm_source,
            page=1,
            page_size=10_000,
        )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "nome", "telefone", "email", "cpf", "produto", "oferta",
        "valor_total_r$", "metodo_pagamento", "status",
        "utm_source", "utm_campaign", "utm_medium", "utm_content", "utm_term",
        "data_primeiro_evento", "data_ativacao",
    ])
    for m in items:
        writer.writerow([
            m.payer_name, m.payer_phone, m.payer_email, m.payer_document or "",
            m.product_name, m.offer_name or "",
            f"{(m.amount_total_cents or 0) / 100:.2f}".replace(".", ","),
            m.payment_method or "",
            m.subscription_status,
            m.utm_source or "", m.utm_campaign or "",
            m.utm_medium or "", m.utm_content or "", m.utm_term or "",
            m.first_seen_at.strftime("%d/%m/%Y %H:%M") if m.first_seen_at else "",
            m.activated_at.strftime("%d/%m/%Y %H:%M") if m.activated_at else "",
        ])

    output.seek(0)
    date_str = datetime.now().strftime("%Y%m%d")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=leads-{date_str}.csv"},
    )


@router.get("/leads/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: UUID,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> LeadDetailResponse:
    async with session_scope() as session:
        account_uuid = await _get_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        from sqlalchemy import select
        from shared.adapters.db.models import LeadModel
        m = await session.get(LeadModel, lead_id)
        if m is None or m.account_id != account_uuid:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="lead not found")
        events = await repo.get_events(account_uuid, m.hubla_subscription_id)

    return LeadDetailResponse(
        **_to_response(m).model_dump(),
        events=[
            HublaEventResponse(
                id=e.id,
                event_type=e.event_type,
                received_at=e.received_at,
                payer_phone=e.payer_phone,
                product_name=e.product_name,
            )
            for e in events
        ],
    )


def _to_response(m) -> LeadResponse:
    return LeadResponse(
        id=m.id,
        hubla_subscription_id=m.hubla_subscription_id,
        payer_phone=m.payer_phone,
        payer_name=m.payer_name,
        payer_email=m.payer_email,
        payer_document=m.payer_document,
        hubla_product_id=m.hubla_product_id,
        product_name=m.product_name,
        offer_name=m.offer_name,
        amount_total_cents=m.amount_total_cents,
        payment_method=m.payment_method,
        subscription_status=m.subscription_status,
        utm_source=m.utm_source,
        utm_campaign=m.utm_campaign,
        first_seen_at=m.first_seen_at,
        activated_at=m.activated_at,
        last_event_at=m.last_event_at,
        last_event_type=m.last_event_type,
    )
```

- [ ] **Step 2: Registrar router no main.py**

```python
from interface.http.routers.admin import leads as admin_leads
# ...
app.include_router(admin_leads.router, prefix="/admin")
```

- [ ] **Step 3: Rodar lint**

```bash
cd apps/api
uv run ruff check src
uv run mypy src
```

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/
git commit -m "feat(api): endpoints GET /admin/leads, GET /admin/leads/{id}, GET /admin/leads/export"
```

---

### Task 5: Frontend — Página /leads

**Files:**
- Create: `apps/web/src/features/leads/types.ts`
- Create: `apps/web/src/features/leads/hooks/useLeads.ts`
- Create: `apps/web/src/features/leads/components/LeadTable.tsx`
- Create: `apps/web/src/features/leads/components/LeadDrawer.tsx`
- Create: `apps/web/src/app/(admin)/leads/page.tsx`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/shared/components/layout/Sidebar.tsx`

- [ ] **Step 1: Criar types.ts**

`apps/web/src/features/leads/types.ts`:

```typescript
export interface Lead {
  id: string;
  hubla_subscription_id: string;
  payer_phone: string;
  payer_name: string;
  payer_email: string;
  payer_document: string | null;
  hubla_product_id: string;
  product_name: string;
  offer_name: string | null;
  amount_total_cents: number | null;
  payment_method: string | null;
  subscription_status: string;
  utm_source: string | null;
  utm_campaign: string | null;
  first_seen_at: string;
  activated_at: string | null;
  last_event_at: string;
  last_event_type: string;
}

export interface LeadEvent {
  id: string;
  event_type: string;
  received_at: string;
  payer_phone: string;
  product_name: string;
}

export interface LeadDetail extends Lead {
  events: LeadEvent[];
}

export interface LeadListResponse {
  items: Lead[];
  total: number;
  page: number;
  page_size: number;
}

export interface LeadFilters {
  product_id?: string;
  status?: string;
  utm_source?: string;
  page?: number;
  page_size?: number;
}
```

- [ ] **Step 2: Adicionar funções de API em lib/api.ts**

```typescript
import type { LeadListResponse, LeadDetail } from "@/features/leads/types";

export async function listLeads(filters: import("@/features/leads/types").LeadFilters = {}): Promise<LeadListResponse> {
  const params = new URLSearchParams();
  if (filters.product_id) params.set("product_id", filters.product_id);
  if (filters.status) params.set("status", filters.status);
  if (filters.utm_source) params.set("utm_source", filters.utm_source);
  if (filters.page) params.set("page", String(filters.page));
  if (filters.page_size) params.set("page_size", String(filters.page_size));
  const qs = params.toString();
  return apiFetch<LeadListResponse>(`/admin/leads${qs ? "?" + qs : ""}`);
}

export async function getLead(id: string): Promise<LeadDetail> {
  return apiFetch<LeadDetail>(`/admin/leads/${id}`);
}

export function getLeadsExportUrl(filters: import("@/features/leads/types").LeadFilters = {}): string {
  const params = new URLSearchParams();
  if (filters.product_id) params.set("product_id", filters.product_id);
  if (filters.status) params.set("status", filters.status);
  if (filters.utm_source) params.set("utm_source", filters.utm_source);
  const qs = params.toString();
  return `/api/admin/leads/export${qs ? "?" + qs : ""}`;
}
```

- [ ] **Step 3: Criar LeadDrawer.tsx — timeline de eventos**

`apps/web/src/features/leads/components/LeadDrawer.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { getLead } from "@/lib/api";
import type { Lead, LeadDetail } from "../types";

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  active:    { label: "Ativado",      className: "bg-success-container text-success" },
  inactive:  { label: "Inativo",      className: "bg-warning-container text-warning" },
  abandoned: { label: "Abandonado",   className: "bg-warning-container text-warning" },
  refunded:  { label: "Reembolsado",  className: "bg-error-container text-error" },
  cancelled: { label: "Cancelado",    className: "bg-error-container text-error" },
};

const EVENT_LABELS: Record<string, string> = {
  "subscription.activated":   "Venda ativada",
  "subscription.created":     "Venda criada",
  "lead.abandoned":           "Carrinho abandonado",
  "subscription.deactivated": "Assinatura desativada",
  "invoice.refunded":         "Fatura reembolsada",
  "subscription.expiring":    "Assinatura expirando",
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, className: "bg-surface-container text-on-surface-variant" };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  );
}

interface Props {
  lead: Lead | null;
  open: boolean;
  onClose: () => void;
}

export function LeadDrawer({ lead, open, onClose }: Props) {
  const [detail, setDetail] = useState<LeadDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open && lead) {
      setLoading(true);
      getLead(lead.id)
        .then(setDetail)
        .catch(() => {})
        .finally(() => setLoading(false));
    } else {
      setDetail(null);
    }
  }, [open, lead?.id]);

  const formatDate = (d: string) =>
    new Date(d).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });

  const formatCents = (c: number | null) =>
    c != null ? `R$ ${(c / 100).toFixed(2).replace(".", ",")}` : "—";

  return (
    <Drawer open={open} onClose={onClose} title={lead?.payer_name ?? "Lead"}>
      {lead && (
        <div className="space-y-6">
          {/* Dados do lead */}
          <div className="rounded-lg border border-outline-variant bg-surface-container p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-on-surface">{lead.payer_name}</span>
              <StatusBadge status={lead.subscription_status} />
            </div>
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
              <div>
                <p className="text-on-surface-variant">Telefone</p>
                <p className="text-on-surface">{lead.payer_phone}</p>
              </div>
              <div>
                <p className="text-on-surface-variant">Email</p>
                <p className="truncate text-on-surface">{lead.payer_email || "—"}</p>
              </div>
              <div>
                <p className="text-on-surface-variant">Produto</p>
                <p className="text-on-surface">{lead.product_name}</p>
              </div>
              <div>
                <p className="text-on-surface-variant">Valor</p>
                <p className="text-on-surface">{formatCents(lead.amount_total_cents)}</p>
              </div>
              {lead.utm_source && (
                <div className="col-span-2">
                  <p className="text-on-surface-variant">UTM</p>
                  <p className="text-on-surface">{lead.utm_source} / {lead.utm_campaign ?? "—"}</p>
                </div>
              )}
            </div>
          </div>

          {/* Timeline de eventos */}
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
              Histórico de eventos
            </p>
            {loading ? (
              <div className="flex items-center gap-2 text-on-surface-variant">
                <span className="material-symbols-outlined animate-spin" style={{ fontSize: "16px" }}>
                  progress_activity
                </span>
                <span className="text-xs">Carregando...</span>
              </div>
            ) : (
              <ol className="space-y-2">
                {(detail?.events ?? []).map((e) => (
                  <li key={e.id} className="animate-fade-in flex gap-3">
                    <div className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary/60" />
                    <div>
                      <p className="text-xs font-medium text-on-surface">
                        {EVENT_LABELS[e.event_type] ?? e.event_type}
                      </p>
                      <p className="text-xs text-on-surface-variant">{formatDate(e.received_at)}</p>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}
```

- [ ] **Step 4: Criar página /leads**

`apps/web/src/app/(admin)/leads/page.tsx`:

```tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { listLeads, getLeadsExportUrl } from "@/lib/api";
import { LeadDrawer } from "@/features/leads/components/LeadDrawer";
import type { Lead, LeadFilters } from "@/features/leads/types";

const STATUS_OPTIONS = [
  { value: "", label: "Todos os status" },
  { value: "active", label: "Ativado" },
  { value: "inactive", label: "Inativo" },
  { value: "abandoned", label: "Abandonado" },
  { value: "refunded", label: "Reembolsado" },
  { value: "cancelled", label: "Cancelado" },
];

const STATUS_BADGE: Record<string, string> = {
  active:    "bg-success-container text-success",
  inactive:  "bg-warning-container text-warning",
  abandoned: "bg-warning-container text-warning",
  refunded:  "bg-error-container text-error",
  cancelled: "bg-error-container text-error",
};

function formatCents(c: number | null) {
  if (c == null) return "—";
  return `R$ ${(c / 100).toFixed(2).replace(".", ",")}`;
}

function formatDate(d: string) {
  return new Date(d).toLocaleDateString("pt-BR");
}

export default function LeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<LeadFilters>({ page: 1, page_size: 25 });
  const [utmInput, setUtmInput] = useState("");
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const load = useCallback(async (f: LeadFilters) => {
    setLoading(true);
    try {
      const res = await listLeads(f);
      setLeads(res.items);
      setTotal(res.total);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(filters); }, [filters]);

  const updateFilter = (patch: Partial<LeadFilters>) => {
    setFilters((prev) => ({ ...prev, ...patch, page: 1 }));
  };

  const totalPages = Math.ceil(total / (filters.page_size ?? 25));

  return (
    <div className="space-y-5 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-h2 font-semibold text-on-surface">Leads</h1>
          <p className="mt-1 text-sm text-on-surface-variant">
            {total > 0 ? `${total.toLocaleString("pt-BR")} lead(s) registrado(s)` : ""}
          </p>
        </div>
        <a
          href={getLeadsExportUrl(filters)}
          className="flex items-center gap-2 rounded-lg border border-outline-variant px-4 py-2.5 text-sm font-medium text-on-surface transition-colors hover:bg-surface-container"
        >
          <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>download</span>
          Exportar CSV
        </a>
      </div>

      {/* Filtros */}
      <div className="flex flex-wrap items-center gap-3">
        <select
          value={filters.status ?? ""}
          onChange={(e) => updateFilter({ status: e.target.value || undefined })}
          className="field-select !w-auto min-w-[180px]"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <input
          type="text"
          placeholder="Filtrar por UTM source..."
          value={utmInput}
          onChange={(e) => setUtmInput(e.target.value)}
          onBlur={() => updateFilter({ utm_source: utmInput || undefined })}
          onKeyDown={(e) => e.key === "Enter" && updateFilter({ utm_source: utmInput || undefined })}
          className="field-input !w-56"
        />
        {(filters.status || filters.utm_source) && (
          <button
            onClick={() => { setUtmInput(""); setFilters({ page: 1, page_size: 25 }); }}
            className="text-xs text-primary hover:underline"
          >
            Limpar filtros
          </button>
        )}
      </div>

      {/* Tabela */}
      <div className="overflow-hidden rounded-lg border border-outline-variant">
        <table className="w-full text-sm">
          <thead className="bg-surface-container-low">
            <tr>
              {["Nome", "Telefone", "Produto", "Valor", "Status", "UTM", "Data"].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-on-surface-variant">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm text-on-surface-variant">
                  Carregando...
                </td>
              </tr>
            ) : leads.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm text-on-surface-variant">
                  Nenhum lead encontrado.
                </td>
              </tr>
            ) : (
              leads.map((lead) => (
                <tr
                  key={lead.id}
                  onClick={() => { setSelectedLead(lead); setDrawerOpen(true); }}
                  className="cursor-pointer border-t border-outline-variant/50 transition-colors hover:bg-surface-container-low"
                >
                  <td className="px-4 py-3 font-medium text-on-surface">{lead.payer_name || "—"}</td>
                  <td className="px-4 py-3 font-mono text-on-surface-variant">{lead.payer_phone}</td>
                  <td className="max-w-[160px] truncate px-4 py-3 text-on-surface-variant">{lead.product_name}</td>
                  <td className="px-4 py-3 text-on-surface">{formatCents(lead.amount_total_cents)}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_BADGE[lead.subscription_status] ?? "bg-surface-container text-on-surface-variant"}`}>
                      {lead.subscription_status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-on-surface-variant">{lead.utm_source ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-on-surface-variant">{formatDate(lead.last_event_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Paginação */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-xs text-on-surface-variant">
            Página {filters.page} de {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              disabled={(filters.page ?? 1) <= 1}
              onClick={() => setFilters((p) => ({ ...p, page: (p.page ?? 1) - 1 }))}
              className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Anterior
            </button>
            <button
              disabled={(filters.page ?? 1) >= totalPages}
              onClick={() => setFilters((p) => ({ ...p, page: (p.page ?? 1) + 1 }))}
              className="rounded-lg border border-outline-variant px-3 py-1.5 text-xs disabled:opacity-40"
            >
              Próxima
            </button>
          </div>
        </div>
      )}

      <LeadDrawer
        lead={selectedLead}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
      />
    </div>
  );
}
```

- [ ] **Step 5: Adicionar item Leads na Sidebar**

Em `apps/web/src/shared/components/layout/Sidebar.tsx`:

```typescript
const NAV_ITEMS = [
  { label: "Painel",               href: "/dashboard",  icon: "dashboard" },
  { label: "Base de Conhecimento", href: "/kb",         icon: "database" },
  { label: "Contas",               href: "/accounts",   icon: "group" },
  { label: "Produtos",             href: "/products",   icon: "inventory_2" },
  { label: "Leads",                href: "/leads",      icon: "person_search" },  // ← novo
  { label: "Follow-up",            href: "/followup",   icon: "schedule_send" },
  { label: "Templates",            href: "/templates",  icon: "sms" },
  { label: "Configurações",        href: "/settings",   icon: "settings", exact: true },
] as const;
```

- [ ] **Step 6: Verificar build**

```bash
cd apps/web
npm run build
```

Esperado: build limpo.

- [ ] **Step 7: Commit final**

```bash
git add apps/web/src/
git commit -m "feat(web): página /leads com tabela paginada, filtros, exportação CSV e drawer de timeline"
```
