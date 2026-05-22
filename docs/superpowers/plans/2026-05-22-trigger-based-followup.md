# Trigger-based Follow-up + Webhook Unificado — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cada `FollowupFlow` declara qual evento Hubla o dispara (`trigger_event_type`). Um único endpoint `/webhook/hubla` recebe todos os eventos e enrola o contato nos flows correspondentes. Se não existir conversa, cria antes de enrolar.

**Architecture:** Campo `trigger_event_type` adicionado em `followup_flows` (default `subscription.activated`). O handler de evento unificado (`HublaEventHandler`) substitui o `PurchaseHandler` como ponto de entrada, mas chama o `PurchaseHandler` internamente quando o evento é `subscription.activated`. O flow_repo ganha método `list_active_by_product_and_event`. O endpoint legado `/webhook/purchase` vira alias.

**Tech Stack:** FastAPI (webhook), SQLAlchemy/Alembic (migration), asyncio (handler), Next.js (UI — FlowDrawer)

> **Pré-requisito:** Este plano assume que o rename Cursos → Produtos (plano `2026-05-22-rename-cursos-produtos.md`) já foi aplicado. Referências usam `product_id` e `ProductModel`.

---

## File Map

**Backend — create:**
- `apps/api/migrations/versions/<hash>_add_trigger_event_type_to_flows.py`
- `apps/api/src/interface/http/routers/webhook_hubla.py`
- `apps/api/src/shared/application/hubla_event_handler.py`
- `apps/api/src/interface/worker/handlers/hubla_event.py`

**Backend — modify:**
- `apps/api/src/shared/adapters/db/models.py` — add `trigger_event_type` to `FollowupFlowModel`
- `apps/api/src/shared/domain/entities/followup.py` — add field to `FollowupFlow`
- `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py` — add query method
- `apps/api/src/interface/http/schemas/followup.py` — add field to request/response schemas
- `apps/api/src/interface/http/routers/admin/followup.py` — expose field
- `apps/api/src/interface/worker/__main__.py` (ou onde jobs são registrados) — novo kind
- `apps/api/src/main.py` — registrar novo webhook route

**Frontend — modify:**
- `apps/web/src/features/followup/types.ts` — add `trigger_event_type`
- `apps/web/src/features/followup/components/FlowDrawer.tsx` — add select field
- `apps/web/src/lib/api.ts` — update CreateFlowInput / UpdateFlowInput

---

### Task 1: Migration — trigger_event_type

**Files:**
- Create: `apps/api/migrations/versions/<hash>_add_trigger_event_type_to_flows.py`

- [ ] **Step 1: Escrever migration**

```bash
cd apps/api
uv run alembic revision -m "add_trigger_event_type_to_flows"
```

Substituir o conteúdo pelo seguinte:

```python
"""add trigger_event_type to followup_flows

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
    op.add_column(
        "followup_flows",
        sa.Column(
            "trigger_event_type",
            sa.String(80),
            nullable=False,
            server_default="subscription.activated",
        ),
    )
    op.create_index(
        "ix_followup_flows_trigger_event_type",
        "followup_flows",
        ["trigger_event_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_followup_flows_trigger_event_type", table_name="followup_flows")
    op.drop_column("followup_flows", "trigger_event_type")
```

- [ ] **Step 2: Aplicar migration**

```bash
cd apps/api
uv run alembic upgrade heads
```

Esperado: `Running upgrade ... → <rev>, add_trigger_event_type_to_flows`

- [ ] **Step 3: Verificar coluna**

```bash
uv run python -c "
import asyncio
from shared.adapters.db.session import get_sessionmaker
from sqlalchemy import text

async def check():
    async with get_sessionmaker()() as s:
        r = await s.execute(text(\"SELECT column_name, column_default FROM information_schema.columns WHERE table_name='followup_flows' AND column_name='trigger_event_type'\"))
        print(r.fetchall())

asyncio.run(check())
"
```

Esperado: `[('trigger_event_type', \"'subscription.activated'\")]`

- [ ] **Step 4: Commit**

```bash
git add apps/api/migrations/
git commit -m "feat(db): adiciona trigger_event_type em followup_flows (default subscription.activated)"
```

---

### Task 2: Backend — Model + Entity + Repository

**Files:**
- Modify: `apps/api/src/shared/adapters/db/models.py`
- Modify: `apps/api/src/shared/domain/entities/followup.py`
- Modify: `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py`

- [ ] **Step 1: Adicionar campo ao FollowupFlowModel**

Em `apps/api/src/shared/adapters/db/models.py`, localizar `class FollowupFlowModel` e adicionar campo:

```python
trigger_event_type: Mapped[str] = mapped_column(
    String(80),
    nullable=False,
    default="subscription.activated",
    server_default="subscription.activated",
)
```

- [ ] **Step 2: Adicionar campo à entidade FollowupFlow**

Em `apps/api/src/shared/domain/entities/followup.py`:

```python
@dataclass(slots=True)
class FollowupFlow:
    id: UUID
    account_id: UUID
    product_id: UUID
    name: str
    trigger_event_type: str = "subscription.activated"
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

- [ ] **Step 3: Escrever teste para o novo método do repositório**

Criar `apps/api/tests/unit/test_followup_flow_repo_trigger.py`:

```python
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.adapters.db.repositories.followup_flow_repo import SqlFollowupFlowRepository


@pytest.mark.asyncio
async def test_list_active_by_product_and_event_returns_matching_flows():
    session = AsyncMock()
    product_id = uuid4()

    mock_flow = MagicMock()
    mock_flow.id = uuid4()
    mock_flow.account_id = uuid4()
    mock_flow.product_id = product_id
    mock_flow.name = "Boas-vindas"
    mock_flow.trigger_event_type = "subscription.activated"
    mock_flow.is_active = True
    mock_flow.created_at = None
    mock_flow.updated_at = None

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [mock_flow]
    session.execute = AsyncMock(return_value=result_mock)

    repo = SqlFollowupFlowRepository(session=session)
    flows = await repo.list_active_by_product_and_event(
        product_id=product_id, event_type="subscription.activated"
    )

    assert len(flows) == 1
    assert flows[0].trigger_event_type == "subscription.activated"
```

- [ ] **Step 4: Rodar teste — verificar que falha**

```bash
cd apps/api
uv run pytest tests/unit/test_followup_flow_repo_trigger.py -v
```

Esperado: `FAILED` com `AttributeError: 'SqlFollowupFlowRepository' object has no attribute 'list_active_by_product_and_event'`

- [ ] **Step 5: Adicionar método ao repositório**

Em `apps/api/src/shared/adapters/db/repositories/followup_flow_repo.py`:

Atualizar `_to_entity` para incluir `trigger_event_type`:
```python
def _to_entity(m: FollowupFlowModel) -> FollowupFlow:
    return FollowupFlow(
        id=m.id,
        account_id=m.account_id,
        product_id=m.product_id,
        name=m.name,
        trigger_event_type=m.trigger_event_type,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )
```

Adicionar método (junto com `list_active_by_product` existente):
```python
async def list_active_by_product_and_event(
    self, product_id: uuid.UUID, event_type: str
) -> list[FollowupFlow]:
    stmt = select(FollowupFlowModel).where(
        FollowupFlowModel.product_id == product_id,
        FollowupFlowModel.trigger_event_type == event_type,
        FollowupFlowModel.is_active.is_(True),
    )
    rows = (await self.session.execute(stmt)).scalars().all()
    return [_to_entity(m) for m in rows]
```

Atualizar `create` para incluir `trigger_event_type`:
```python
async def create(
    self,
    *,
    account_id: uuid.UUID,
    product_id: uuid.UUID,
    name: str,
    trigger_event_type: str = "subscription.activated",
    is_active: bool = True,
) -> FollowupFlow:
    now = datetime.now(UTC)
    model = FollowupFlowModel(
        id=uuid4(),
        account_id=account_id,
        product_id=product_id,
        name=name,
        trigger_event_type=trigger_event_type,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )
    self.session.add(model)
    await self.session.flush()
    return _to_entity(model)
```

Atualizar `update` para incluir campo opcional:
```python
async def update(
    self,
    flow_id: uuid.UUID,
    *,
    name: str | None = None,
    product_id: uuid.UUID | None = None,
    trigger_event_type: str | None = None,
    is_active: bool | None = None,
) -> FollowupFlow | None:
    ...
    if trigger_event_type is not None:
        model.trigger_event_type = trigger_event_type
    ...
```

- [ ] **Step 6: Rodar teste — verificar que passa**

```bash
cd apps/api
uv run pytest tests/unit/test_followup_flow_repo_trigger.py -v
```

Esperado: `PASSED`

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/ apps/api/tests/
git commit -m "feat(api): adiciona trigger_event_type ao model, entity e repo de followup_flows"
```

---

### Task 3: Backend — Schemas + Admin Router

**Files:**
- Modify: `apps/api/src/interface/http/schemas/followup.py`
- Modify: `apps/api/src/interface/http/routers/admin/followup.py`

- [ ] **Step 1: Atualizar schemas**

Em `apps/api/src/interface/http/schemas/followup.py`:

```python
# Adicionar em FollowupFlowResponse:
trigger_event_type: str

# Adicionar em CreateFlowRequest:
trigger_event_type: str = "subscription.activated"

# Adicionar em UpdateFlowRequest:
trigger_event_type: str | None = None
```

- [ ] **Step 2: Atualizar router de followup**

Em `apps/api/src/interface/http/routers/admin/followup.py`:

No endpoint de criação (`POST /followup/flows`), passar `trigger_event_type`:
```python
flow = await flow_repo.create(
    account_id=account_uuid,
    product_id=body.product_id,
    name=body.name,
    trigger_event_type=body.trigger_event_type,
    is_active=body.is_active,
)
```

No endpoint de atualização (`PUT /followup/flows/{flow_id}`), passar campo:
```python
flow = await flow_repo.update(
    flow_id,
    name=body.name,
    product_id=body.product_id,
    trigger_event_type=body.trigger_event_type,
    is_active=body.is_active,
)
```

No response, incluir o campo:
```python
FollowupFlowResponse(
    ...
    trigger_event_type=flow.trigger_event_type,
    ...
)
```

- [ ] **Step 3: Rodar lint**

```bash
cd apps/api
uv run ruff check src
uv run mypy src
```

Esperado: sem erros.

- [ ] **Step 4: Commit**

```bash
git add apps/api/src/interface/
git commit -m "feat(api): expõe trigger_event_type nos schemas e routers de followup"
```

---

### Task 4: Backend — HublaEventHandler + Webhook Unificado

**Files:**
- Create: `apps/api/src/shared/application/hubla_event_handler.py`
- Create: `apps/api/src/interface/http/routers/webhook_hubla.py`
- Create: `apps/api/src/interface/worker/handlers/hubla_event.py`
- Modify: `apps/api/src/main.py`

- [ ] **Step 1: Escrever teste para HublaEventHandler**

Criar `apps/api/tests/unit/test_hubla_event_handler.py`:

```python
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from shared.application.hubla_event_handler import HublaEventHandler


def _make_event(event_type: str = "subscription.activated"):
    return {
        "type": event_type,
        "event": {
            "product": {"id": "prod-hubla-123", "name": "Produto X"},
            "products": [{"id": "prod-hubla-123", "name": "Produto X", "offers": []}],
            "subscription": {
                "id": "sub-uuid-001",
                "payer": {
                    "firstName": "João",
                    "lastName": "Silva",
                    "document": "12345678901",
                    "email": "joao@email.com",
                    "phone": "+5511999990000",
                },
                "activatedAt": "2026-05-22T12:00:00Z",
                "paymentMethod": "credit_card",
                "type": "one_time",
                "status": "active",
            },
        },
        "version": "2.0.0",
    }


@pytest.mark.asyncio
async def test_subscription_activated_enrolls_matching_flows():
    product_repo = AsyncMock()
    flow_repo = AsyncMock()
    contact_repo = AsyncMock()
    chatnexo = AsyncMock()
    enroll_uc = AsyncMock()
    purchase_handler = AsyncMock()

    product = MagicMock()
    product.id = uuid4()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=product)

    flow = MagicMock()
    flow.id = uuid4()
    flow.trigger_event_type = "subscription.activated"
    flow_repo.list_active_by_product_and_event = AsyncMock(return_value=[flow])

    contact = MagicMock()
    contact.id = uuid4()
    contact.phone = "+5511999990000"
    contact_repo.upsert = AsyncMock(return_value=contact)

    chatnexo.get_open_conversation = AsyncMock(return_value=None)
    chatnexo.create_conversation = AsyncMock(return_value="conv-123")

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=enroll_uc,
        purchase_handler=purchase_handler,
    )

    payload = _make_event("subscription.activated")
    await handler.handle(payload)

    enroll_uc.execute.assert_called_once()
    purchase_handler.handle_one.assert_called_once()


@pytest.mark.asyncio
async def test_lead_abandoned_enrolls_matching_flows_without_purchase_handler():
    product_repo = AsyncMock()
    flow_repo = AsyncMock()
    contact_repo = AsyncMock()
    chatnexo = AsyncMock()
    enroll_uc = AsyncMock()
    purchase_handler = AsyncMock()

    product = MagicMock()
    product.id = uuid4()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=product)

    flow = MagicMock()
    flow.id = uuid4()
    flow.trigger_event_type = "lead.abandoned"
    flow_repo.list_active_by_product_and_event = AsyncMock(return_value=[flow])

    contact = MagicMock()
    contact.id = uuid4()
    contact.phone = "+5511999990000"
    contact_repo.upsert = AsyncMock(return_value=contact)

    chatnexo.get_open_conversation = AsyncMock(return_value="conv-existing-456")

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=flow_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        enroll_contact_uc=enroll_uc,
        purchase_handler=purchase_handler,
    )

    payload = _make_event("lead.abandoned")
    await handler.handle(payload)

    enroll_uc.execute.assert_called_once()
    purchase_handler.handle_one.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_product_logs_warning_and_skips():
    product_repo = AsyncMock()
    product_repo.find_active_by_hubla_id = AsyncMock(return_value=None)

    handler = HublaEventHandler(
        product_repo=product_repo,
        flow_repo=AsyncMock(),
        contact_repo=AsyncMock(),
        chatnexo=AsyncMock(),
        enroll_contact_uc=AsyncMock(),
        purchase_handler=AsyncMock(),
    )

    payload = _make_event("subscription.activated")
    await handler.handle(payload)  # não deve lançar exceção
```

- [ ] **Step 2: Rodar testes — verificar que falham**

```bash
cd apps/api
uv run pytest tests/unit/test_hubla_event_handler.py -v
```

Esperado: `ModuleNotFoundError: No module named 'shared.application.hubla_event_handler'`

- [ ] **Step 3: Implementar HublaEventHandler**

`apps/api/src/shared/application/hubla_event_handler.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog

from shared.domain.value_objects.phone import Phone

log = structlog.get_logger(__name__)

_DEFAULT_ACCOUNT_UUID = UUID("00000000-0000-0000-0000-000000000001")

# Eventos que também disparam o PurchaseHandler (welcome + access case)
_PURCHASE_EVENT_TYPES = frozenset({"subscription.activated"})


class HublaEventHandler:
    """
    Processa qualquer evento Hubla:
    1. Resolve produto pelo hubla_product_id
    2. Busca flows com trigger_event_type = event.type
    3. Enrola o contato em cada flow (cria conversa se necessário)
    4. Se subscription.activated: também executa PurchaseHandler
    """

    def __init__(
        self,
        *,
        product_repo: Any,
        flow_repo: Any,
        contact_repo: Any,
        chatnexo: Any,
        enroll_contact_uc: Any,
        purchase_handler: Any,
        account_id: UUID | None = None,
    ) -> None:
        self._product_repo = product_repo
        self._flow_repo = flow_repo
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._enroll_contact_uc = enroll_contact_uc
        self._purchase_handler = purchase_handler
        self._account_id = account_id or _DEFAULT_ACCOUNT_UUID

    async def handle(self, payload: dict[str, Any]) -> None:
        event_type: str = payload.get("type", "")
        event = payload.get("event", {})
        subscription = event.get("subscription", {})
        payer = subscription.get("payer", {})
        products_list = event.get("products") or []
        product_data = products_list[0] if products_list else event.get("product", {})

        hubla_product_id: str = product_data.get("id", "")
        product_name: str = product_data.get("name", "")
        purchase_id: str = subscription.get("id", "")
        payer_phone: str = payer.get("phone", "")
        payer_email: str = payer.get("email", "")
        payer_name: str = (
            (payer.get("firstName", "") + " " + payer.get("lastName", "")).strip()
        )
        payer_document: str = payer.get("document", "")
        activated_at_raw: str = subscription.get("activatedAt", "")
        try:
            activated_at = datetime.fromisoformat(activated_at_raw.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            activated_at = datetime.now(timezone.utc)

        account_id = self._account_id
        account_id_str = str(account_id)

        if not payer_phone:
            log.warning("hubla_event_no_phone", event_type=event_type, purchase_id=purchase_id)
            return

        # Resolve produto
        product = await self._product_repo.find_active_by_hubla_id(account_id, hubla_product_id)
        if product is None:
            log.warning(
                "hubla_event_product_not_found",
                event_type=event_type,
                hubla_product_id=hubla_product_id,
            )
            # Ainda executa purchase_handler para subscription.activated (retrocompat)
            if event_type in _PURCHASE_EVENT_TYPES:
                await self._purchase_handler.handle_one(
                    hubla_product_id=hubla_product_id,
                    product_name=product_name,
                    purchase_id=purchase_id,
                    activated_at=activated_at,
                    payer_phone=payer_phone,
                    payer_email=payer_email,
                    payer_full_name=payer_name,
                    payer_document=payer_document,
                    account_id=account_id,
                )
            return

        # Resolve/cria contato
        contact = await self._contact_repo.upsert(
            account_id=account_id,
            phone=Phone.parse(payer_phone),
            name=payer_name,
            email=payer_email,
        )

        # Busca flows configurados para este evento
        flows = await self._flow_repo.list_active_by_product_and_event(
            product_id=product.id, event_type=event_type
        )

        for flow in flows:
            # Resolve conversa (usa existente ou cria nova)
            conversation_id = await self._chatnexo.get_open_conversation(
                account_id=account_id_str, contact_phone=contact.phone
            )
            if conversation_id is None:
                conversation_id = await self._chatnexo.create_conversation(
                    account_id=account_id_str, contact_phone=contact.phone
                )

            await self._enroll_contact_uc.execute(
                account_id=account_id,
                contact_id=UUID(str(contact.id)),
                conversation_id=str(conversation_id),
                contact_phone=payer_phone,
                purchase_id=purchase_id,
                flow_id=flow.id,
                customer_name=payer_name,
                product_name=product_name,
                purchase_time=activated_at,
            )

        log.info(
            "hubla_event_flows_enrolled",
            event_type=event_type,
            product_id=str(product.id),
            flows=len(flows),
            purchase_id=purchase_id,
        )

        # Para subscription.activated, executa também o PurchaseHandler legado
        if event_type in _PURCHASE_EVENT_TYPES:
            await self._purchase_handler.handle_one(
                hubla_product_id=hubla_product_id,
                product_name=product_name,
                purchase_id=purchase_id,
                activated_at=activated_at,
                payer_phone=payer_phone,
                payer_email=payer_email,
                payer_full_name=payer_name,
                payer_document=payer_document,
                account_id=account_id,
            )
```

- [ ] **Step 4: Rodar testes — verificar que passam**

```bash
cd apps/api
uv run pytest tests/unit/test_hubla_event_handler.py -v
```

Esperado: `3 passed`

- [ ] **Step 5: Criar webhook_hubla router**

`apps/api/src/interface/http/routers/webhook_hubla.py`:

```python
from __future__ import annotations

import hashlib
import hmac

import structlog
from fastapi import APIRouter, Header, HTTPException, Request, status

from shared.adapters.db.queue import PostgresJobQueue
from shared.adapters.db.session import session_scope
from shared.adapters.redis import get_redis
from shared.adapters.db.repositories.webhook_event import SqlWebhookEventRepository
from shared.config.settings import get_settings

router = APIRouter(tags=["webhook-hubla"])
log = structlog.get_logger(__name__)


def _verify_hubla_signature(body: bytes, token: str, expected_secret: str) -> bool:
    """Valida x-hubla-token (comparação segura)."""
    return hmac.compare_digest(token, expected_secret)


@router.post("/webhook/hubla", status_code=status.HTTP_202_ACCEPTED)
async def hubla_webhook(
    request: Request,
    x_hubla_token: str = Header(..., alias="x-hubla-token"),
) -> dict:
    settings = get_settings()
    if not _verify_hubla_signature(b"", x_hubla_token, settings.hubla_webhook_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    payload = await request.json()
    event_type: str = payload.get("type", "unknown")
    subscription_id: str = payload.get("event", {}).get("subscription", {}).get("id", "")
    external_id = f"{event_type}:{subscription_id}" if subscription_id else event_type

    async with session_scope() as session:
        redis = await get_redis()
        webhook_repo = SqlWebhookEventRepository(session=session, redis=redis)
        inserted = await webhook_repo.insert_if_new(
            source="hubla",
            external_id=external_id,
            payload=payload,
        )
        if not inserted:
            log.info("hubla_webhook_duplicate", event_type=event_type, external_id=external_id)
            return {"status": "duplicate"}

        queue = PostgresJobQueue(session=session)
        await queue.enqueue(kind="hubla_event", payload={"event": payload})

    log.info("hubla_webhook_enqueued", event_type=event_type, external_id=external_id)
    return {"status": "accepted"}
```

- [ ] **Step 6: Criar worker handler hubla_event.py**

`apps/api/src/interface/worker/handlers/hubla_event.py`:

```python
from __future__ import annotations

from typing import Any

import structlog

from shared.adapters.db.repositories.contact import SqlContactRepository
from shared.adapters.db.repositories.followup_flow_repo import SqlFollowupFlowRepository
from shared.adapters.db.repositories.product_repo import SqlProductRepository
from shared.adapters.db.session import session_scope
from shared.adapters.chatnexo import ChatNexoClient
from shared.application.hubla_event_handler import HublaEventHandler
from shared.application.purchase_handler import PurchaseHandler
from shared.application.use_cases.followup.enroll_contact import EnrollContactUseCase
from shared.config.settings import get_settings

log = structlog.get_logger(__name__)


async def handle_hubla_event(job_payload: dict[str, Any]) -> None:
    """Processa um evento Hubla de qualquer tipo."""
    payload: dict = job_payload.get("event", {})
    settings = get_settings()

    async with session_scope() as session:
        product_repo = SqlProductRepository(session=session)
        flow_repo = SqlFollowupFlowRepository(session=session)
        contact_repo = SqlContactRepository(session=session)
        chatnexo = ChatNexoClient(
            base_url=settings.chatnexo_base_url,
            api_key=settings.chatnexo_api_key,
        )

        # Reutiliza os demais repos que o PurchaseHandler precisa
        from shared.adapters.db.repositories.access_case_repo import SqlAccessCaseRepository
        from shared.adapters.db.repositories.scheduled_job import SqlScheduledJobRepository

        access_case_repo = SqlAccessCaseRepository(session=session)
        scheduler = SqlScheduledJobRepository(session=session)
        enroll_uc = EnrollContactUseCase(
            flow_repo=flow_repo,
            scheduler=scheduler,
            session=session,
        )
        purchase_handler = PurchaseHandler(
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            access_case_repo=access_case_repo,
            scheduler=scheduler,
            product_repo=product_repo,
            flow_repo=flow_repo,
            enroll_contact_uc=enroll_uc,
        )
        handler = HublaEventHandler(
            product_repo=product_repo,
            flow_repo=flow_repo,
            contact_repo=contact_repo,
            chatnexo=chatnexo,
            enroll_contact_uc=enroll_uc,
            purchase_handler=purchase_handler,
        )
        await handler.handle(payload)
```

- [ ] **Step 7: Registrar novo job kind no worker**

Localizar onde o worker registra handlers por `kind` (geralmente em `apps/api/src/interface/worker/__main__.py` ou similar). Adicionar:

```python
from interface.worker.handlers.hubla_event import handle_hubla_event

# No dict de handlers:
HANDLERS = {
    "message": handle_message,
    "purchase": handle_purchase,
    "scheduled_welcome": handle_scheduled,
    "followup_step": handle_scheduled,
    "hubla_event": handle_hubla_event,   # ← novo
}
```

- [ ] **Step 8: Registrar rota no main.py**

Em `apps/api/src/main.py`, após os imports de webhooks existentes:

```python
from interface.http.routers import webhook_hubla

# Na função de lifespan ou setup:
app.include_router(webhook_hubla.router)
```

- [ ] **Step 9: Rodar todos os testes**

```bash
cd apps/api
uv run pytest tests/unit -v -x
```

Esperado: todos passando.

- [ ] **Step 10: Smoke test manual com webhook-sim**

```bash
# Simular subscription.activated via novo endpoint
cd scripts/webhook-sim
uv run python send_purchase.py --endpoint /webhook/hubla
```

Esperado: `202 Accepted`, job enfileirado.

- [ ] **Step 11: Commit**

```bash
git add apps/api/src/ apps/api/tests/
git commit -m "feat(api): HublaEventHandler + /webhook/hubla + worker handler hubla_event"
```

---

### Task 5: Frontend — trigger_event_type no FlowDrawer

**Files:**
- Modify: `apps/web/src/features/followup/types.ts`
- Modify: `apps/web/src/features/followup/components/FlowDrawer.tsx`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: Atualizar types.ts**

Em `apps/web/src/features/followup/types.ts`, adicionar campo:

```typescript
export interface FollowupFlow {
  id: string;
  name: string;
  is_active: boolean;
  trigger_event_type: string;   // ← novo
  product: ProductSummary;
  steps_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateFlowInput {
  name: string;
  product_id: string;
  is_active?: boolean;
  trigger_event_type?: string;   // ← novo (default "subscription.activated")
}

export interface UpdateFlowInput {
  name?: string;
  product_id?: string;
  is_active?: boolean;
  trigger_event_type?: string;   // ← novo
}
```

- [ ] **Step 2: Adicionar select de evento no FlowDrawer**

Em `apps/web/src/features/followup/components/FlowDrawer.tsx`:

Adicionar state:
```typescript
const [triggerEventType, setTriggerEventType] = useState(
  flow?.trigger_event_type ?? "subscription.activated"
);
```

No `useEffect` de reset ao abrir:
```typescript
setTriggerEventType(flow?.trigger_event_type ?? "subscription.activated");
```

Adicionar as opções de evento (constante no topo do arquivo):
```typescript
const HUBLA_EVENT_OPTIONS = [
  { value: "subscription.activated", label: "Venda ativada (subscription.activated)" },
  { value: "subscription.created",   label: "Venda criada / pendente (subscription.created)" },
  { value: "lead.abandoned",         label: "Carrinho abandonado (lead.abandoned)" },
  { value: "subscription.deactivated", label: "Assinatura desativada (subscription.deactivated)" },
  { value: "subscription.expiring",  label: "Assinatura expirando (subscription.expiring)" },
  { value: "invoice.refunded",       label: "Fatura reembolsada (invoice.refunded)" },
];
```

Adicionar o campo no formulário (dentro de `showFormFields`, após o checkbox "Ativo"):
```tsx
<div className="animate-fade-in flex flex-col gap-2">
  <span className="text-xs font-medium uppercase tracking-wide text-on-surface-variant">
    Evento disparador
  </span>
  <select
    value={triggerEventType}
    onChange={(e) => setTriggerEventType(e.target.value)}
    className="field-select"
  >
    {HUBLA_EVENT_OPTIONS.map((opt) => (
      <option key={opt.value} value={opt.value}>
        {opt.label}
      </option>
    ))}
  </select>
  <span className="text-xs text-on-surface-variant">
    O flow será disparado quando este evento for recebido da Hubla.
  </span>
</div>
```

Incluir `trigger_event_type` no submit:
```typescript
// Em handleSubmit, no onCreate:
await onCreate({
  name,
  product_id: courseId,
  is_active: isActive,
  trigger_event_type: triggerEventType,
});

// No onUpdate:
await onUpdate(activeFlow.id, {
  name,
  product_id: courseId,
  is_active: isActive,
  trigger_event_type: triggerEventType,
});
```

- [ ] **Step 3: Verificar build**

```bash
cd apps/web
npm run build
```

Esperado: build limpo.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/
git commit -m "feat(web): adiciona seletor de evento disparador no FlowDrawer"
```
