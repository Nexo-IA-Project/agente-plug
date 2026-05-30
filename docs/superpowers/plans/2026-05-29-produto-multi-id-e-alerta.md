# Múltiplos hubla_id por produto + alerta de não-mapeado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Um produto pode ter vários `hubla_id` (offers viram aliases) e eventos com produto não reconhecido viram alerta visível/acionável — nunca um drop silencioso.

**Architecture:** Tabela `product_hubla_aliases` (id principal continua em `products.hubla_id`); `find_active_by_hubla_id` resolve principal OU alias. `leads.product_unmatched` marca eventos sem produto. `_route` marca a flag + dispara log ERROR/métrica/alerta ChatNexo. Aba de pendências (derivada de leads) com resolver (cria alias) + reprocessar (re-enfileira `hubla_events`).

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, asyncpg, pytest (asyncio_mode=auto, testcontainers), Next.js 15 (App Router), Prometheus client.

**Spec:** `docs/superpowers/specs/2026-05-29-produto-multi-id-e-alerta-nao-mapeado-design.md`

---

## File Structure

**Backend (`apps/api/`):**
- Create: `migrations/versions/<rev>_product_aliases_and_unmatched.py` — migration
- Modify: `src/shared/adapters/db/models.py` — `ProductHublaAliasModel` + `LeadModel.product_unmatched`
- Modify: `src/shared/adapters/db/repositories/product_repo.py` — resolução por alias + métodos de alias
- Modify: `src/shared/adapters/db/repositories/lead_repo.py` — `set_product_unmatched`, `list_unmapped`, `events_for_unmapped`
- Modify: `src/shared/application/hubla_event_handler.py` — veredito matched/unmatched + alerta
- Create: `src/shared/application/use_cases/admin/unmapped_products.py` — list/resolve/reprocess
- Create: `src/interface/http/routers/admin/unmapped_products.py` — endpoints
- Modify: `src/main.py` — registrar router
- Modify: `src/shared/adapters/observability/metrics.py` — counter
- Modify: settings/IntegrationConfig — `alert_whatsapp_target`
- Tests: `tests/unit/...`, `tests/integration/...`

**Frontend (`apps/web/`):**
- Create: `src/app/(admin)/onboarding/pendencias/page.tsx` + `src/features/unmapped/`
- Modify: `src/features/leads/` (marcador + filtro) e `src/lib/api.ts`
- Modify: settings page (campo do número de alerta)

---

## Task 1: Migration — tabela de aliases + coluna unmatched

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Create: `apps/api/migrations/versions/<rev>_product_aliases_and_unmatched.py`

- [ ] **Step 1: Adicionar models em `models.py`** (após `ProductModel`, ~linha 285)

```python
class ProductHublaAliasModel(Base):
    __tablename__ = "product_hubla_aliases"
    __table_args__ = (
        UniqueConstraint("account_id", "hubla_id", name="uq_product_alias_account_hubla"),
        Index("ix_product_alias_account_hubla", "account_id", "hubla_id"),
        Index("ix_product_alias_product", "product_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    hubla_id: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sa_text("NOW()"), nullable=False
    )
```

E em `LeadModel` (após `hubla_product_id`):
```python
    product_unmatched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: Gerar a migration manualmente** (não autogenerate — multi-head). Criar arquivo com `down_revision` = head atual de leads/onboarding.

Run: `cd apps/api && uv run alembic heads` → anotar o head a usar como `down_revision`.

```python
"""product aliases + lead.product_unmatched"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "<gerar: ex p1a2b3c4d5e6>"
down_revision = "<head atual>"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "product_hubla_aliases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", UUID(as_uuid=True), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hubla_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("NOW()"), nullable=False),
        sa.UniqueConstraint("account_id", "hubla_id", name="uq_product_alias_account_hubla"),
    )
    op.create_index("ix_product_alias_account_hubla", "product_hubla_aliases", ["account_id", "hubla_id"])
    op.create_index("ix_product_alias_product", "product_hubla_aliases", ["product_id"])
    op.add_column("leads", sa.Column("product_unmatched", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade() -> None:
    op.drop_column("leads", "product_unmatched")
    op.drop_index("ix_product_alias_product", table_name="product_hubla_aliases")
    op.drop_index("ix_product_alias_account_hubla", table_name="product_hubla_aliases")
    op.drop_table("product_hubla_aliases")
```

- [ ] **Step 3: Aplicar e validar**

Run: `cd apps/api && uv run alembic upgrade heads`
Expected: sem erro; `\d product_hubla_aliases` existe, `leads.product_unmatched` existe.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/adapters/db/models.py apps/api/migrations/versions/
git commit -m "feat(db): product_hubla_aliases + leads.product_unmatched"
```

---

## Task 2: Resolução por alias no ProductRepository

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/product_repo.py`
- Test: `apps/api/tests/unit/test_product_repo_aliases.py`

- [ ] **Step 1: Teste falhando** (`tests/unit/test_product_repo_aliases.py`)

```python
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
import pytest
from shared.adapters.db.repositories.product_repo import SqlProductRepository


def _prod(name="P"):
    m = MagicMock(); m.id=uuid4(); m.account_id=uuid4(); m.name=name
    m.hubla_id="primary"; m.is_active=True; m.created_at=None; m.updated_at=None
    return m


@pytest.mark.asyncio
async def test_resolves_by_primary_first():
    session = AsyncMock()
    r = MagicMock(); r.scalar_one_or_none.return_value=_prod()
    session.execute = AsyncMock(return_value=r)
    repo = SqlProductRepository(session=session)
    p = await repo.find_active_by_hubla_id(uuid4(), "primary")
    assert p is not None and p.hubla_id == "primary"
    assert session.execute.await_count == 1  # achou no principal, não consulta alias


@pytest.mark.asyncio
async def test_resolves_by_alias_when_primary_misses():
    session = AsyncMock()
    miss = MagicMock(); miss.scalar_one_or_none.return_value=None
    alias_hit = MagicMock(); alias_hit.scalar_one_or_none.return_value=_prod()
    session.execute = AsyncMock(side_effect=[miss, alias_hit])
    repo = SqlProductRepository(session=session)
    p = await repo.find_active_by_hubla_id(uuid4(), "offer-id")
    assert p is not None
    assert session.execute.await_count == 2  # principal falhou → consultou alias
```

- [ ] **Step 2: Rodar — falha**

Run: `cd apps/api && uv run pytest tests/unit/test_product_repo_aliases.py -q`
Expected: FAIL (alias lookup ainda não existe).

- [ ] **Step 3: Implementar resolução por alias** em `product_repo.py`. Substituir `find_active_by_hubla_id`:

```python
    async def find_active_by_hubla_id(self, account_id: UUID, hubla_id: str) -> Product | None:
        # 1) id principal
        stmt = select(ProductModel).where(
            ProductModel.account_id == account_id,
            ProductModel.hubla_id == hubla_id,
            ProductModel.is_active.is_(True),
        )
        m = (await self.session.execute(stmt)).scalar_one_or_none()
        if m:
            return _to_entity(m)
        # 2) alias → produto ativo
        alias_stmt = (
            select(ProductModel)
            .join(ProductHublaAliasModel, ProductHublaAliasModel.product_id == ProductModel.id)
            .where(
                ProductHublaAliasModel.account_id == account_id,
                ProductHublaAliasModel.hubla_id == hubla_id,
                ProductModel.is_active.is_(True),
            )
        )
        am = (await self.session.execute(alias_stmt)).scalar_one_or_none()
        return _to_entity(am) if am else None

    async def add_alias(self, *, account_id: UUID, product_id: UUID, hubla_id: str) -> None:
        from shared.adapters.db.models import ProductHublaAliasModel as _A
        self.session.add(_A(id=uuid4(), account_id=account_id, product_id=product_id, hubla_id=hubla_id))
        await self.session.flush()
```

Adicionar import: `from shared.adapters.db.models import OnboardingFlowModel, ProductHublaAliasModel, ProductModel`.

- [ ] **Step 4: Rodar — passa**

Run: `cd apps/api && uv run pytest tests/unit/test_product_repo_aliases.py -q`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/product_repo.py apps/api/tests/unit/test_product_repo_aliases.py
git commit -m "feat(products): resolução de hubla_id por alias + add_alias"
```

---

## Task 3: LeadRepository — flag + consultas de não-mapeados

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/lead_repo.py`
- Test: `apps/api/tests/integration/test_lead_unmatched.py`

- [ ] **Step 1: Implementar métodos** em `lead_repo.py` (usar os nomes de coluna do `LeadModel`):

```python
    async def set_product_unmatched(self, *, lead_id: UUID, value: bool) -> None:
        await self.session.execute(
            update(LeadModel).where(LeadModel.id == lead_id).values(product_unmatched=value)
        )

    async def list_unmapped(self, account_id: UUID) -> list[dict]:
        stmt = (
            select(
                LeadModel.hubla_product_id,
                func.max(LeadModel.product_name).label("product_name"),
                func.count(LeadModel.id).label("affected_leads"),
                func.min(LeadModel.first_seen_at).label("first_seen"),
                func.max(LeadModel.last_event_at).label("last_seen"),
            )
            .where(LeadModel.account_id == account_id, LeadModel.product_unmatched.is_(True))
            .group_by(LeadModel.hubla_product_id)
            .order_by(func.max(LeadModel.last_event_at).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "hubla_product_id": r.hubla_product_id,
                "product_name": r.product_name,
                "affected_leads": int(r.affected_leads),
                "first_seen": r.first_seen,
                "last_seen": r.last_seen,
            }
            for r in rows
        ]

    async def count_unmapped_by_product(self, account_id: UUID, hubla_product_id: str) -> int:
        stmt = select(func.count(LeadModel.id)).where(
            LeadModel.account_id == account_id,
            LeadModel.hubla_product_id == hubla_product_id,
            LeadModel.product_unmatched.is_(True),
        )
        return int((await self.session.execute(stmt)).scalar_one())
```

Garantir imports: `from sqlalchemy import func, select, update`.

- [ ] **Step 2: Teste de integração** (`tests/integration/test_lead_unmatched.py`) — seguir padrão `_apply_migrations` + `db_session` de `test_followup_enrollment_repo_v2.py`. Seedar 1 account + 2 leads (mesmo hubla_product_id, product_unmatched=True) e 1 matched; afirmar `list_unmapped` retorna 1 grupo com `affected_leads==2`; `set_product_unmatched` muda o valor; `count_unmapped_by_product` == 2.

```python
# (cabeçalho de migrations idêntico a test_scheduler_runner_commit.py)
async def test_list_and_set_unmatched(engine):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from shared.adapters.db.models import AccountModel, LeadModel
    from shared.adapters.db.repositories.lead_repo import SqlLeadRepository  # confirmar nome real da classe
    import uuid
    from datetime import UTC, datetime
    maker = async_sessionmaker(engine, expire_on_commit=False)
    acc = uuid.uuid4(); now = datetime(2026,5,29,tzinfo=UTC)
    async with maker() as s:
        from sqlalchemy import delete
        await s.execute(delete(LeadModel)); await s.execute(delete(AccountModel))
        s.add(AccountModel(id=acc, name="t"))
        for i,(sub,unm) in enumerate([("s1",True),("s2",True),("s3",False)]):
            s.add(LeadModel(id=uuid.uuid4(), account_id=acc, hubla_subscription_id=sub,
                payer_phone=f"+551199999000{i}", payer_name="N", payer_email="e@e.com",
                hubla_product_id=("X" if unm else "Y"), product_name="LE", product_unmatched=unm,
                first_seen_at=now, last_event_at=now))
        await s.commit()
    async with maker() as s:
        repo = SqlLeadRepository(session=s)
        groups = await repo.list_unmapped(acc)
        assert len(groups)==1 and groups[0]["hubla_product_id"]=="X" and groups[0]["affected_leads"]==2
```

> NOTA p/ o executor: confirmar o nome real da classe do repo de leads (`grep -n "class .*LeadRepository" src/shared/adapters/db/repositories/lead_repo.py`) e os campos NOT NULL do `LeadModel` (preencher os obrigatórios no seed).

- [ ] **Step 3: Rodar**

Run: `cd apps/api && uv run pytest tests/integration/test_lead_unmatched.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/lead_repo.py apps/api/tests/integration/test_lead_unmatched.py
git commit -m "feat(leads): set_product_unmatched + list_unmapped"
```

---

## Task 4: Settings — alert_whatsapp_target

**Files:**
- Modify: arquivo do `IntegrationConfig` (rodar `grep -rn "class IntegrationConfig" src/`) e o schema de settings em `interface/http/schemas/`.

- [ ] **Step 1: Adicionar campo** `alert_whatsapp_target: str | None = None` ao `IntegrationConfig` (dataclass/pydantic) e ao mapeamento de leitura/escrita do JSONB `accounts.settings` (seguir o padrão de `meta_waba_id`, que já é editável via UI — `grep -rn "meta_waba_id" src/` mostra todos os pontos a espelhar).

- [ ] **Step 2: Expor no schema de GET/PUT `/admin/settings`** (espelhar `meta_waba_id`).

- [ ] **Step 3: Teste** — estender o teste existente de settings (`grep -rn "meta_waba_id" tests/`) para cobrir round-trip do novo campo.

- [ ] **Step 4: Rodar + Commit**

Run: `cd apps/api && uv run pytest -k settings -q`
```bash
git commit -am "feat(settings): alert_whatsapp_target editável"
```

---

## Task 5: _route — veredito matched/unmatched + alerta

**Files:**
- Modify: `apps/api/src/shared/adapters/observability/metrics.py` — counter
- Modify: `apps/api/src/shared/application/hubla_event_handler.py`
- Test: `apps/api/tests/unit/test_hubla_event_handler.py`

- [ ] **Step 1: Counter em `metrics.py`** (seguir padrão de `WEBHOOK_RECEIVED`):

```python
HUBLA_UNMAPPED_PRODUCT = Counter(
    "hubla_unmapped_product_total",
    "Eventos Hubla cujo produto não casou nenhum cadastro",
    ["product_name"],
)
```

- [ ] **Step 2: Teste falhando** em `tests/unit/test_hubla_event_handler.py` — produto não casa (id e nome None) → `lead_repo.set_product_unmatched(value=True)` chamado, `enroll_uc.execute` NÃO chamado, e se houver `alert_sender` configurado, alerta disparado.

```python
@pytest.mark.asyncio
async def test_unmapped_product_marks_lead_and_alerts():
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)
    product_repo.find_active_by_name = AsyncMock(return_value=None)
    contact_repo = AsyncMock(); contact_repo.upsert = AsyncMock(return_value=_make_contact())
    lead_repo = AsyncMock(); lead_repo.upsert = AsyncMock(return_value=MagicMock(id=uuid4()))
    hubla_event_repo = AsyncMock(); hubla_event_repo.insert = AsyncMock(return_value=MagicMock(id=uuid4())); hubla_event_repo.mark_processed = AsyncMock()
    alert = AsyncMock()
    enroll_uc = AsyncMock()
    handler = HublaEventHandler(
        product_repo=product_repo, flow_repo=AsyncMock(), contact_repo=contact_repo,
        chatnexo=AsyncMock(), enroll_contact_uc=enroll_uc, purchase_handler=AsyncMock(),
        lead_repo=lead_repo, hubla_event_repo=hubla_event_repo, unmapped_alert=alert,
    )
    await handler.handle(_make_event("customer.member_added"))
    lead_repo.set_product_unmatched.assert_awaited_with(lead_id=ANY, value=True)
    enroll_uc.execute.assert_not_called()
    alert.assert_awaited_once()
```

(import `from unittest.mock import ANY`).

- [ ] **Step 3: Implementar** em `hubla_event_handler.py`:
  - Adicionar dependência opcional `unmapped_alert: Callable | None = None` no `__init__` (um callable async que recebe contexto e dispara o ChatNexo; injetado no worker).
  - `handle()` já tem `lead_entity`/`lead_id` após o upsert. Passar `lead_id` para `_route` (novo parâmetro) **ou** capturar o retorno de `_route` (bool matched) e setar a flag em `handle()`. Escolha: `_route` retorna `bool` (matched) e `handle()` chama `lead_repo.set_product_unmatched(lead_id, not matched)` quando `lead_repo` e `lead_id` existem.
  - No ramo "produto não encontrado" (após fallback por nome): `HUBLA_UNMAPPED_PRODUCT.labels(product_name=product_name or "?").inc()`, `log.error("hubla_event_product_unmapped", ...)`, e `if self._unmapped_alert: await self._unmapped_alert(product_name, hubla_product_id, payer_full_name, payer_phone)` (try/except defensivo — alerta nunca derruba o evento). Continua o comportamento atual (purchase handler legado se PURCHASE_EVENT_TYPES) e retorna matched=False.
  - Ramo "casou": retorna matched=True.

- [ ] **Step 4: Rodar a suíte do handler + suíte unit completa**

Run: `cd apps/api && uv run pytest tests/unit/test_hubla_event_handler.py tests/unit/application/test_hubla_event_handler_25_types.py -q`
Expected: PASS (adicionar `unmapped_alert`/`lead_repo` mocks onde necessário; o teste dos 25 tipos usa `lead_repo` mock — garantir `set_product_unmatched=AsyncMock`).

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/application/hubla_event_handler.py apps/api/src/shared/adapters/observability/metrics.py apps/api/tests/unit/
git commit -m "feat(onboarding): marca lead.product_unmatched + alerta/metric/log no não-mapeado"
```

---

## Task 6: Alerta ChatNexo (sender) + wiring no worker

**Files:**
- Create: `apps/api/src/shared/application/unmapped_alert.py` — fábrica do sender
- Modify: `apps/api/src/interface/worker/handlers/hubla_event.py` — injetar `unmapped_alert` no handler
- Test: `apps/api/tests/unit/test_unmapped_alert.py`

- [ ] **Step 1: Teste** — sender pula quando `target` vazio; quando há target, chama `chatnexo.send_message` com texto contendo o id e o nome.

```python
@pytest.mark.asyncio
async def test_alert_skipped_without_target():
    chatnexo = AsyncMock()
    from shared.application.unmapped_alert import make_unmapped_alert
    alert = make_unmapped_alert(chatnexo=chatnexo, account_id="1", target="")
    await alert("LE", "offer-1", "Cissa", "+5511...")
    chatnexo.send_message.assert_not_called()

@pytest.mark.asyncio
async def test_alert_sends_when_target():
    chatnexo = AsyncMock()
    from shared.application.unmapped_alert import make_unmapped_alert
    alert = make_unmapped_alert(chatnexo=chatnexo, account_id="1", target="+5534999999999")
    await alert("LE", "offer-1", "Cissa", "+5511...")
    chatnexo.send_message.assert_awaited_once()
```

- [ ] **Step 2: Implementar** `unmapped_alert.py`:

```python
from __future__ import annotations
from collections.abc import Awaitable, Callable
import structlog
log = structlog.get_logger(__name__)

def make_unmapped_alert(*, chatnexo, account_id: str, target: str | None) -> Callable[..., Awaitable[None]]:
    async def _alert(product_name: str, hubla_product_id: str, payer_name: str, payer_phone: str) -> None:
        if not target:
            return
        text = (
            "⚠️ Produto não reconhecido no onboarding\n"
            f"Produto: {product_name or '(sem nome)'}\n"
            f"ID Hubla não cadastrado: {hubla_product_id}\n"
            f"Lead: {payer_name} {payer_phone}\n"
            "Cadastre esse ID em Produtos (ou na aba Pendências) para destravar o funil."
        )
        try:
            conv = await chatnexo.get_open_conversation(account_id=account_id, contact_phone=target)
            if conv is None:
                conv = await chatnexo.create_conversation(account_id=account_id, contact_phone=target, inbox_id=...)
            await chatnexo.send_message(account_id=account_id, conversation_id=str(conv), text=text)
        except Exception as exc:  # alerta nunca derruba o pipeline
            log.warning("unmapped_alert_failed", error=str(exc))
    return _alert
```

> NOTA executor: confirmar a assinatura real de `chatnexo.send_message`/`create_conversation` (já usadas no `_route`) e de onde vem `inbox_id` (config). Reusar o mesmo padrão do `hubla_event.py`.

- [ ] **Step 3: Wiring** em `interface/worker/handlers/hubla_event.py` — montar `unmapped_alert=make_unmapped_alert(chatnexo=..., account_id=..., target=config.integration.alert_whatsapp_target)` e passar ao `HublaEventHandler`.

- [ ] **Step 4: Rodar + Commit**

Run: `cd apps/api && uv run pytest tests/unit/test_unmapped_alert.py -q`
```bash
git add apps/api/src/shared/application/unmapped_alert.py apps/api/src/interface/worker/handlers/hubla_event.py apps/api/tests/unit/test_unmapped_alert.py
git commit -m "feat(onboarding): alerta ChatNexo de produto não reconhecido"
```

---

## Task 7: Use cases + router de pendências (list/resolve/reprocess)

**Files:**
- Create: `apps/api/src/shared/application/use_cases/admin/unmapped_products.py`
- Create: `apps/api/src/interface/http/routers/admin/unmapped_products.py`
- Modify: `apps/api/src/main.py` (registrar router)
- Test: `apps/api/tests/integration/admin/test_unmapped_products_router.py`

- [ ] **Step 1: Use cases** (`unmapped_products.py`):
  - `list_unmapped(account_id)` → `lead_repo.list_unmapped`.
  - `resolve(account_id, hubla_product_id, product_id)` → `product_repo.add_alias(...)` + retorna `count_unmapped_by_product`. (Idempotente: capturar IntegrityError do unique → alias já existe, segue.)
  - `reprocess(account_id, hubla_product_id, schedule_mode)` → buscar `hubla_events` com aquele `hubla_product_id` cujos leads estão unmatched; para cada, `queue.enqueue({"kind":"hubla_event","payload": {**payload, "_schedule_mode": schedule_mode}})`. Retorna nº enfileirado.

- [ ] **Step 2: Router** (`unmapped_products.py`) com `Depends(require_admin_role)`:
  - `GET /admin/unmapped-products`
  - `POST /admin/unmapped-products/resolve` (body `{hubla_product_id, product_id}`)
  - `POST /admin/unmapped-products/reprocess` (body `{hubla_product_id, schedule_mode}` com `schedule_mode: Literal["from_now","original"] = "from_now"`)
  Registrar em `main.py` no mesmo bloco dos outros admin routers.

- [ ] **Step 3: schedule_mode no handler** — em `hubla_event_handler.handle()`, se `payload.get("_schedule_mode")=="from_now"`, usar `clock.now()` como `purchase_time`/`activated_at` ao enrollar (em vez do `activatedAt` do payload). Default (ausente ou `original`) = comportamento atual. Adicionar teste unit cobrindo os dois modos.

- [ ] **Step 4: Teste de integração do router** (testcontainers): seed leads unmatched + hubla_events; `GET` lista 1 grupo; `resolve` cria alias (confere em `product_hubla_aliases`); `reprocess` enfileira N jobs (mockar/contar a `queue`).

- [ ] **Step 5: Rodar + Commit**

Run: `cd apps/api && uv run pytest tests/integration/admin/test_unmapped_products_router.py -q`
```bash
git add apps/api/src/shared/application/use_cases/admin/unmapped_products.py apps/api/src/interface/http/routers/admin/unmapped_products.py apps/api/src/main.py apps/api/tests/
git commit -m "feat(admin): endpoints de pendências (list/resolve/reprocess)"
```

---

## Task 8: Leads — expor product_unmatched (API + SSE)

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/leads.py` (LeadResponse + filtro)
- Modify: `apps/api/src/shared/application/hubla_event_handler.py` (`_lead_to_dict` inclui `product_unmatched`)
- Test: ajustar testes de leads existentes

- [ ] **Step 1:** Incluir `product_unmatched` no `LeadResponse` e no `_lead_to_dict` (envelope SSE), e adicionar query param `unmatched: bool | None` no `GET /admin/leads` (filtra `LeadModel.product_unmatched.is_(True)`).

- [ ] **Step 2:** Ajustar/adicionar teste de `GET /admin/leads?unmatched=true`.

- [ ] **Step 3: Rodar + Commit**

Run: `cd apps/api && uv run pytest -k lead -q` (rodar por arquivo se houver coleta órfã)
```bash
git commit -am "feat(leads): campo product_unmatched + filtro unmatched"
```

---

## Task 9: Frontend — aba de Pendências

**Files:**
- Create: `apps/web/src/app/(admin)/onboarding/pendencias/page.tsx`
- Create: `apps/web/src/features/unmapped/{types.ts,components/UnmappedTable.tsx,components/ResolveDrawer.tsx}`
- Modify: `apps/web/src/lib/api.ts` (`listUnmapped`, `resolveUnmapped`, `reprocessUnmapped`)
- Modify: Sidebar (item "Pendências" sob Onboarding)

- [ ] **Step 1:** `api.ts` — funções tipadas para os 3 endpoints (seguir padrão `apiFetch`).
- [ ] **Step 2:** `UnmappedTable` — lista (nome, id, nº leads, visto em) com botão "Associar a produto".
- [ ] **Step 3:** `ResolveDrawer` (usa `shared/components/Drawer`) — dropdown de produtos ativos (`listProducts`) → `resolveUnmapped` → mostra "N leads afetados" → botão "Reprocessar" com escolha `from_now`/`original` (radio) → `reprocessUnmapped`. Toasts via `useToast`.
- [ ] **Step 4:** Item no Sidebar + rota. Usar tokens NexoIA (sem hex).
- [ ] **Step 5: Verificar build de tipos**

Run: `cd apps/web && npx tsc --noEmit`
Expected: sem erros.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/app/(admin)/onboarding/pendencias apps/web/src/features/unmapped apps/web/src/lib/api.ts apps/web/src/shared/components/layout/
git commit -m "feat(web): aba de Pendências (produtos não reconhecidos)"
```

---

## Task 10: Frontend — marcador no painel de Leads

**Files:**
- Modify: `apps/web/src/features/leads/` (tipo Lead + tabela + filtro), `src/app/(admin)/leads/page.tsx`

- [ ] **Step 1:** Adicionar `product_unmatched: boolean` ao tipo `Lead`.
- [ ] **Step 2:** Na linha da tabela, quando `product_unmatched`, mostrar badge `⚠️ Produto não reconhecido` (tom amber, tokens NexoIA) ao lado do status.
- [ ] **Step 3:** Filtro "Só não reconhecidos" (passa `unmatched=true` ao listar) + contador no topo.
- [ ] **Step 4:** O `useLeadsStream` já recebe o envelope; garantir que `product_unmatched` do envelope atualiza a linha.
- [ ] **Step 5: Verificar + Commit**

Run: `cd apps/web && npx tsc --noEmit`
```bash
git commit -am "feat(web): marcador e filtro de produto não reconhecido em Leads"
```

---

## Task 11: Frontend — campo de alerta em Settings

**Files:**
- Modify: settings feature (`apps/web/src/features/settings/`) + `lib/api.ts` (se necessário)

- [ ] **Step 1:** Adicionar campo "Número de alerta (WhatsApp interno)" no formulário de Settings, ligado a `alert_whatsapp_target` (espelhar `meta_waba_id`).
- [ ] **Step 2: Verificar + Commit**

Run: `cd apps/web && npx tsc --noEmit`
```bash
git commit -am "feat(web): campo de número de alerta interno em Settings"
```

---

## Verificação final (antes do PR)

- `cd apps/api && uv run ruff check src tests && uv run ruff format --check src tests`
- `cd apps/api && uv run pytest tests/unit -q` (gate do CI) + integração dos arquivos novos
- `cd apps/web && npx tsc --noEmit`
- Abrir PR para `main`. Pós-deploy: validar em prod que um id de offer não cadastrado marca o lead como unmatched, aparece na aba Pendências, resolve → alias → reprocess enrolla.

## Notas de execução
- Confirmar nome real da classe do repo de leads (`SqlLeadRepository`?) e campos NOT NULL do `LeadModel` antes do seed (Task 3).
- Confirmar assinaturas de `chatnexo.send_message`/`create_conversation`/`inbox_id` (Task 6) reusando o padrão de `interface/worker/handlers/hubla_event.py`.
- `down_revision` da migration = saída de `alembic heads` (Task 1).
