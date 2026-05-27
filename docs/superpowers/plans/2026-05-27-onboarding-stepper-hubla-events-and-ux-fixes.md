# Onboarding Stepper + 24 Eventos Hubla + UX Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reformular o `FlowDrawer` de `/onboarding` em stepper vertical de 3 passos (Produto → Eventos → Mensagens), expandir o catálogo de eventos Hubla de 6 para 25 tipos oficiais, habilitar edição de templates Meta não-aprovados, e corrigir 3 issues de UX (confirmação em produtos, drawer backdrop, fechar após salvar).

**Architecture:** 5 fases independentes commitáveis. Fase 1 ajusta o `Drawer` compartilhado e produtos (baixo risco). Fase 2 expande backend Hubla para os 25 eventos com migration. Fase 3 expande o catálogo de eventos no frontend (`triggerEvents.ts`). Fase 4 implementa edit template vertical slice (backend + frontend). Fase 5 reescreve o `FlowDrawer` em stepper de 3 passos com animação suave entre transições. Ordem importa: Fase 5 depende de Fase 3 (catálogo expandido).

**Tech Stack:** Next.js 15 App Router, Tailwind, `@dnd-kit/*` (já no projeto), React Hook Form, FastAPI, SQLAlchemy 2.0, Alembic, pytest.

**Spec base:** `docs/superpowers/specs/2026-05-27-onboarding-stepper-hubla-events-and-ux-fixes-design.md`

**Branch:** `feat/onboarding-stepper-hubla-events-and-ux-fixes` (já criada, spec já commitada como `99e1727`).

---

## Fase 1 — UX Fixes (Drawer + produtos + fecha após salvar)

### Task 1: Drawer compartilhado — backdrop a `inset-0` (item 3 da spec)

**Files:**
- Modify: `apps/web/src/shared/components/Drawer.tsx:36-42`

- [ ] **Step 1: Editar `Drawer.tsx` para estender backdrop**

Trocar o bloco do backdrop. O painel (`aside`) permanece com `left: SIDEBAR_WIDTH`.

```tsx
{/* Backdrop */}
<div
  aria-hidden
  onClick={onClose}
  className={`fixed inset-0 z-40 cursor-pointer bg-black/40 transition-opacity duration-200 ${
    open ? "opacity-100" : "pointer-events-none opacity-0"
  }`}
/>
```

Remover a linha `style={{ left: SIDEBAR_WIDTH }}` do backdrop. Manter `style={{ left: SIDEBAR_WIDTH }}` no `aside` painel (linha 54).

- [ ] **Step 2: Verificar manualmente em todos os Drawers**

```bash
cd apps/web && npm run dev
```

Abrir `/onboarding`, clicar em "Configurar" em qualquer flow → drawer abre.
- Clicar na sidebar → drawer fecha. ✓
- Clicar no header (TopBar) → drawer fecha. ✓
- Clicar dentro do drawer → não fecha. ✓
- ESC fecha. ✓

Repetir em `/products` (drawer de produto) e `/leads` (drawer de lead).

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shared/components/Drawer.tsx
git commit -m "fix(drawer): backdrop cobre tela inteira (click na sidebar fecha)"
```

---

### Task 2: `useConfirm()` em produtos (item 1 da spec)

**Files:**
- Modify: `apps/web/src/app/(admin)/products/page.tsx`

- [ ] **Step 1: Ler o arquivo atual**

```bash
cat apps/web/src/app/(admin)/products/page.tsx
```

Localizar `handleDelete` e o import do `useToast` (ou similar).

- [ ] **Step 2: Adicionar import e substituir `confirm()` nativo**

No topo do arquivo, adicionar:

```tsx
import { useConfirm } from "@/shared/components/confirm";
```

Dentro do componente da page, adicionar (próximo aos outros hooks):

```tsx
const confirm = useConfirm();
```

Substituir a função `handleDelete` (que hoje usa `confirm()` nativo):

```tsx
async function handleDelete(p: Product) {
  const ok = await confirm({
    title: "Excluir produto",
    description: `Tem certeza que deseja remover "${p.name}"? Esta ação não pode ser desfeita.`,
    confirmLabel: "Excluir",
    variant: "danger",
  });
  if (!ok) return;
  try {
    await deleteProduct(p.id);
    toast.success("Produto removido");
    refetch();
  } catch (err) {
    toast.error(`Erro ao remover: ${(err as Error).message}`);
  }
}
```

(Ajustar `deleteProduct`, `toast`, `refetch` aos nomes reais já usados no arquivo — se o handler atual já tem try/catch + toast, preservar a estrutura, só trocar o gate de `confirm()` nativo.)

- [ ] **Step 3: Verificar manualmente**

```bash
cd apps/web && npm run dev
```

Em `/products` clicar "Excluir" em um produto → `ConfirmDialog` modal abre (igual o de `/templates`). Cancelar não exclui. Confirmar exclui + toast.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/(admin)/products/page.tsx
git commit -m "feat(products): usar useConfirm() ao excluir (substitui confirm() nativo)"
```

---

### Task 3: FlowDrawer fecha após salvar (item 4 — fix mínimo no FlowDrawer atual antes da reescrita)

> **Nota:** este fix é mínimo e será substituído pelo comportamento novo na Task 17 (reescrita do FlowDrawer). Faço esse fix agora porque pode dar uns dias até a reescrita ficar pronta — não deixar o bug em produção.

**Files:**
- Modify: `apps/web/src/features/onboarding/components/FlowDrawer.tsx`

- [ ] **Step 1: Localizar `onSubmit` e adicionar `onClose()` após sucesso**

Na função `onSubmit` atual, após a chamada bem-sucedida de `onCreate` ou `onUpdate`, adicionar `onClose()`:

```tsx
async function onSubmit(data: FlowFormData) {
  setSaving(true);
  try {
    if (activeFlow) {
      await onUpdate(activeFlow.id, { /* ... */ });
      setActiveFlow((prev) => prev ? { ...prev, /* ... */ } : prev);
      toast.success("Flow atualizado");
    } else {
      const created = await onCreate({ /* ... */ });
      setActiveFlow(created);
      toast.success("Flow criado");
    }
    onClose(); // ← NOVO
  } catch (err) {
    toast.error(`Erro: ${(err as Error).message}`);
  } finally {
    setSaving(false);
  }
}
```

Manter toda a lógica existente; só adicionar o `onClose()` após o toast de sucesso.

- [ ] **Step 2: Verificar manualmente**

Editar um flow em `/onboarding`, clicar "Salvar alterações" → drawer fecha automaticamente. Criar novo flow → ao salvar, drawer fecha.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/onboarding/components/FlowDrawer.tsx
git commit -m "fix(onboarding): FlowDrawer fecha automaticamente após salvar"
```

---

## Fase 2 — Backend Hubla 25 eventos + migration

### Task 4: `HublaEventType` value object (25 valores)

**Files:**
- Create: `apps/api/src/shared/domain/value_objects/hubla_event_type.py`
- Test: `apps/api/tests/unit/domain/value_objects/test_hubla_event_type.py`

- [ ] **Step 1: Criar teste falhando**

```python
# apps/api/tests/unit/domain/value_objects/test_hubla_event_type.py
from shared.domain.value_objects.hubla_event_type import (
    ALL_HUBLA_EVENT_TYPES,
    PURCHASE_EVENT_TYPES,
    is_valid_hubla_event_type,
)


def test_all_hubla_event_types_has_24_values() -> None:
    assert len(ALL_HUBLA_EVENT_TYPES) == 24


def test_purchase_event_types_is_subset() -> None:
    assert PURCHASE_EVENT_TYPES <= ALL_HUBLA_EVENT_TYPES
    assert "subscription.activated" in PURCHASE_EVENT_TYPES


def test_is_valid_known() -> None:
    assert is_valid_hubla_event_type("subscription.activated") is True
    assert is_valid_hubla_event_type("member.access_granted") is True
    assert is_valid_hubla_event_type("invoice.payment_failed") is True


def test_is_valid_unknown() -> None:
    assert is_valid_hubla_event_type("subscription.expiring") is False  # nome antigo
    assert is_valid_hubla_event_type("foo.bar") is False
    assert is_valid_hubla_event_type("") is False


def test_categories_complete() -> None:
    """Garantia mínima de cobertura por categoria."""
    expected_per_category = {
        "lead": 1, "member": 2, "subscription": 6,
        "invoice": 6, "installment": 6, "refund_request": 4,
    }
    for cat, count in expected_per_category.items():
        matching = [t for t in ALL_HUBLA_EVENT_TYPES if t.startswith(cat + ".")]
        assert len(matching) == count, f"categoria {cat}: esperava {count}, achei {len(matching)}"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
cd apps/api && uv run pytest tests/unit/domain/value_objects/test_hubla_event_type.py -v
```

Esperado: ImportError ou ModuleNotFoundError em `shared.domain.value_objects.hubla_event_type`.

- [ ] **Step 3: Implementar o value object**

```python
# apps/api/src/shared/domain/value_objects/hubla_event_type.py
"""Eventos Hubla v2 — catálogo oficial dos 25 tipos."""

from typing import Literal, get_args

HublaEventType = Literal[
    # Lead (1)
    "lead.abandoned_cart",
    # Member (2)
    "member.access_granted",
    "member.access_removed",
    # Subscription (6)
    "subscription.created",
    "subscription.activated",
    "subscription.expired",
    "subscription.deactivated",
    "subscription.auto_renewal_disabled",
    "subscription.auto_renewal_enabled",
    # Invoice (6)
    "invoice.created",
    "invoice.status_updated",
    "invoice.payment_completed",
    "invoice.payment_failed",
    "invoice.expired",
    "invoice.refunded",
    # Installment (6)
    "installment.created",
    "installment.failed",
    "installment.in_progress",
    "installment.overdue",
    "installment.cancelled",
    "installment.completed",
    # Refund Request (4)
    "refund_request.created",
    "refund_request.accepted",
    "refund_request.cancelled",
    "refund_request.rejected",
]

ALL_HUBLA_EVENT_TYPES: frozenset[str] = frozenset(get_args(HublaEventType))

PURCHASE_EVENT_TYPES: frozenset[str] = frozenset({"subscription.activated"})
"""Eventos que disparam o pipeline legado de PurchaseHandler (welcome + access_case)."""


def is_valid_hubla_event_type(value: str) -> bool:
    return value in ALL_HUBLA_EVENT_TYPES
```

- [ ] **Step 4: Rodar e ver passar**

```bash
cd apps/api && uv run pytest tests/unit/domain/value_objects/test_hubla_event_type.py -v
```

Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/domain/value_objects/hubla_event_type.py apps/api/tests/unit/domain/value_objects/test_hubla_event_type.py
git commit -m "feat(hubla): HublaEventType value object com 25 eventos oficiais v2"
```

---

### Task 5: `HublaEventHandler` aceita 25 eventos + warn unknown

**Files:**
- Modify: `apps/api/src/shared/application/hubla_event_handler.py:14,57`
- Test: `apps/api/tests/unit/application/test_hubla_event_handler_24_types.py`

- [ ] **Step 1: Criar teste falhando**

```python
# apps/api/tests/unit/application/test_hubla_event_handler_24_types.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from shared.application.hubla_event_handler import HublaEventHandler
from shared.domain.value_objects.hubla_event_type import ALL_HUBLA_EVENT_TYPES


@pytest.mark.parametrize("event_type", sorted(ALL_HUBLA_EVENT_TYPES))
async def test_handler_accepts_all_24_types(event_type: str) -> None:
    """Cada um dos 25 eventos deve ser persistido em hubla_events sem erro."""
    handler = _make_handler()
    payload = _make_payload(event_type=event_type)
    await handler.handle(payload)
    handler._hubla_events_repo.save.assert_called_once()  # type: ignore[attr-defined]
    saved_call = handler._hubla_events_repo.save.call_args  # type: ignore[attr-defined]
    assert saved_call.kwargs.get("event_type") == event_type or \
           saved_call.args[0].event_type == event_type


async def test_handler_logs_warning_for_unknown_event(caplog) -> None:
    handler = _make_handler()
    payload = _make_payload(event_type="foo.bar")
    await handler.handle(payload)
    assert any("hubla_unknown_event" in r.message for r in caplog.records)
    handler._hubla_events_repo.save.assert_called_once()  # ainda persiste


async def test_handler_only_calls_purchase_for_subscription_activated() -> None:
    handler = _make_handler()
    await handler.handle(_make_payload(event_type="subscription.activated"))
    handler._purchase_handler.handle.assert_called_once()  # type: ignore[attr-defined]

    handler2 = _make_handler()
    await handler2.handle(_make_payload(event_type="member.access_granted"))
    handler2._purchase_handler.handle.assert_not_called()  # type: ignore[attr-defined]


# Helpers — adaptar à API real do HublaEventHandler/repos após Step 2
def _make_handler() -> HublaEventHandler:
    """Constrói handler com todas as deps mockadas."""
    # IMPORTANTE: depois de ler o código real do HublaEventHandler em Step 2,
    # ajustar este factory às assinaturas reais (parser, repos, etc).
    raise NotImplementedError("preencher após Step 2")


def _make_payload(event_type: str) -> dict:
    return {
        "id": "evt_test",
        "type": event_type,
        "version": "2.0.0",
        "subscription": {"id": "sub_1", "product": {"id": "prod_1", "name": "X"}},
        "user": {"name": "Test", "email": "t@x.com", "phone": "+5511999999999"},
    }
```

- [ ] **Step 2: Ler o handler atual para preencher o factory**

```bash
cat apps/api/src/shared/application/hubla_event_handler.py
```

Identificar dependências do `__init__` (parser, repos, purchase handler, etc) e ajustar `_make_handler()` no teste com `AsyncMock`/`MagicMock` para cada uma.

- [ ] **Step 3: Aplicar mudanças no `hubla_event_handler.py`**

Linha 14 — substituir o frozenset hardcoded:

```python
# antes
_PURCHASE_EVENT_TYPES = frozenset({"subscription.activated"})

# depois
from shared.domain.value_objects.hubla_event_type import (
    ALL_HUBLA_EVENT_TYPES,
    PURCHASE_EVENT_TYPES,
    is_valid_hubla_event_type,
)
```

E em todos os usos de `_PURCHASE_EVENT_TYPES`, trocar por `PURCHASE_EVENT_TYPES`.

Próximo às linhas onde `event_type` é extraído do payload (~linha 57):

```python
event_type: str = payload.get("type", "")
if not is_valid_hubla_event_type(event_type):
    log.warning(
        "hubla_unknown_event",
        event_type=event_type,
        payload_id=payload.get("id"),
    )
    # NÃO retornar — continuar pipeline para persistir o log em hubla_events
```

- [ ] **Step 4: Rodar testes**

```bash
cd apps/api && uv run pytest tests/unit/application/test_hubla_event_handler_24_types.py -v
```

Esperado: 26 passed (24 parametrizados + 2 testes específicos).

- [ ] **Step 5: Rodar testes existentes para garantir que não quebrou**

```bash
cd apps/api && uv run pytest tests/unit/application/ -v
```

Esperado: todos passam.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/application/hubla_event_handler.py apps/api/tests/unit/application/test_hubla_event_handler_24_types.py
git commit -m "feat(hubla): handler aceita os 25 event types + log warn em desconhecidos"
```

---

### Task 6: Migration rename divergent event types

**Files:**
- Create: `apps/api/migrations/versions/<rev>_rename_divergent_hubla_event_types.py`
- Test: `apps/api/tests/integration/migrations/test_rename_divergent_hubla_event_types.py`

- [ ] **Step 1: Gerar revision file**

```bash
cd apps/api && uv run alembic revision -m "rename divergent hubla event types"
```

Anotar o `<rev>` gerado e renomear o arquivo para algo legível: `<rev>_rename_divergent_hubla_event_types.py`.

- [ ] **Step 2: Implementar a migration**

```python
"""rename divergent hubla event types

Revision ID: <rev>
Revises: <previous>
Create Date: 2026-05-27

Renomeia trigger_event_type em followup_flows para alinhar com a Hubla v2:
- lead.abandoned        → lead.abandoned_cart
- subscription.expiring → subscription.expired

NÃO toca hubla_events.event_type (log imutável — histórico preservado).
"""
from __future__ import annotations

from alembic import op


revision = "<rev>"
down_revision = "<previous>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE followup_flows
        SET trigger_event_type = 'lead.abandoned_cart'
        WHERE trigger_event_type = 'lead.abandoned';
    """)
    op.execute("""
        UPDATE followup_flows
        SET trigger_event_type = 'subscription.expired'
        WHERE trigger_event_type = 'subscription.expiring';
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE followup_flows
        SET trigger_event_type = 'lead.abandoned'
        WHERE trigger_event_type = 'lead.abandoned_cart';
    """)
    op.execute("""
        UPDATE followup_flows
        SET trigger_event_type = 'subscription.expiring'
        WHERE trigger_event_type = 'subscription.expired';
    """)
```

Substituir `<rev>` e `<previous>` pelos valores reais (consultar `alembic history` para identificar o head atual).

- [ ] **Step 3: Criar teste de integração da migration**

```python
# apps/api/tests/integration/migrations/test_rename_divergent_hubla_event_types.py
"""Testa que a migration <rev>_rename_divergent_hubla_event_types renomeia corretamente."""
import pytest
from sqlalchemy import text

from alembic import command
from alembic.config import Config


@pytest.mark.asyncio
async def test_migration_renames_flows(async_engine, alembic_config: Config) -> None:
    # 1. Subir até a migration anterior
    command.downgrade(alembic_config, "<rev>^")

    # 2. Seed: criar 1 flow com cada nome antigo
    async with async_engine.connect() as conn:
        await conn.execute(text("""
            INSERT INTO followup_flows (id, account_id, product_id, name, trigger_event_type, is_active, position, created_at, updated_at)
            VALUES
              (gen_random_uuid(), :acc, :prod, 'F1', 'lead.abandoned', true, 0, now(), now()),
              (gen_random_uuid(), :acc, :prod, 'F2', 'subscription.expiring', true, 1, now(), now())
        """), {"acc": "<seed-account-uuid>", "prod": "<seed-product-uuid>"})
        await conn.commit()

    # 3. Rodar upgrade
    command.upgrade(alembic_config, "<rev>")

    # 4. Verificar valores renomeados
    async with async_engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT trigger_event_type FROM followup_flows
            WHERE name IN ('F1', 'F2')
            ORDER BY name
        """))
        rows = result.fetchall()
        assert rows[0][0] == "lead.abandoned_cart"
        assert rows[1][0] == "subscription.expired"
```

> **Nota:** este teste de integração precisa das fixtures `async_engine` e `alembic_config` existentes em `tests/integration/conftest.py`. Se as fixtures não existirem com esses nomes exatos, ajustar para os nomes reais. Se o seed de `account_id`/`product_id` exigir FK válidas, criar registros primeiro nessas tabelas.

- [ ] **Step 4: Rodar migration localmente**

```bash
docker compose up -d postgres
cd apps/api && uv run alembic upgrade heads
```

Verificar que não há erro. Inspecionar:

```bash
docker compose exec postgres psql -U postgres -d agente_plug -c "SELECT DISTINCT trigger_event_type FROM followup_flows;"
```

Não deve aparecer mais `lead.abandoned` nem `subscription.expiring`.

- [ ] **Step 5: Rodar teste de integração**

```bash
cd apps/api && uv run pytest tests/integration/migrations/test_rename_divergent_hubla_event_types.py -v
```

Esperado: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/migrations/versions/<rev>_rename_divergent_hubla_event_types.py apps/api/tests/integration/migrations/test_rename_divergent_hubla_event_types.py
git commit -m "feat(hubla): migration renomeia lead.abandoned→abandoned_cart e subscription.expiring→expired"
```

---

## Fase 3 — Frontend triggerEvents.ts expandido

### Task 7: Expandir `triggerEvents.ts` para 25 entries + categorias + alias

**Files:**
- Modify: `apps/web/src/features/onboarding/lib/triggerEvents.ts`

- [ ] **Step 1: Sobrescrever o arquivo com a versão expandida**

```ts
// apps/web/src/features/onboarding/lib/triggerEvents.ts

export type HublaEventCategory =
  | "lead"
  | "member"
  | "subscription"
  | "invoice"
  | "installment"
  | "refund";

export type HublaEventType =
  // Lead
  | "lead.abandoned_cart"
  // Member
  | "member.access_granted"
  | "member.access_removed"
  // Subscription
  | "subscription.created"
  | "subscription.activated"
  | "subscription.expired"
  | "subscription.deactivated"
  | "subscription.auto_renewal_disabled"
  | "subscription.auto_renewal_enabled"
  // Invoice
  | "invoice.created"
  | "invoice.status_updated"
  | "invoice.payment_completed"
  | "invoice.payment_failed"
  | "invoice.expired"
  | "invoice.refunded"
  // Installment
  | "installment.created"
  | "installment.failed"
  | "installment.in_progress"
  | "installment.overdue"
  | "installment.cancelled"
  | "installment.completed"
  // Refund Request
  | "refund_request.created"
  | "refund_request.accepted"
  | "refund_request.cancelled"
  | "refund_request.rejected";

export interface TriggerEventTone {
  text: string;
  bg: string;
  border: string;
  ring: string;
  bgActive: string;
}

export interface TriggerEventMeta {
  value: HublaEventType;
  label: string;
  pillLabel?: string;
  technical: string;
  description: string;
  category: HublaEventCategory;
  categoryLabel: string;
  icon: string;
  tone: TriggerEventTone;
}

const TONE_LEAD: TriggerEventTone = {
  text: "text-amber-500",
  bg: "bg-amber-500/10",
  border: "border-amber-500/30",
  ring: "ring-amber-500",
  bgActive: "bg-amber-500/15",
};
const TONE_MEMBER: TriggerEventTone = {
  text: "text-teal-500",
  bg: "bg-teal-500/10",
  border: "border-teal-500/30",
  ring: "ring-teal-500",
  bgActive: "bg-teal-500/15",
};
const TONE_SUB: TriggerEventTone = {
  text: "text-emerald-500",
  bg: "bg-emerald-500/10",
  border: "border-emerald-500/30",
  ring: "ring-emerald-500",
  bgActive: "bg-emerald-500/15",
};
const TONE_INVOICE: TriggerEventTone = {
  text: "text-violet-500",
  bg: "bg-violet-500/10",
  border: "border-violet-500/30",
  ring: "ring-violet-500",
  bgActive: "bg-violet-500/15",
};
const TONE_INSTALLMENT: TriggerEventTone = {
  text: "text-blue-500",
  bg: "bg-blue-500/10",
  border: "border-blue-500/30",
  ring: "ring-blue-500",
  bgActive: "bg-blue-500/15",
};
const TONE_REFUND: TriggerEventTone = {
  text: "text-rose-500",
  bg: "bg-rose-500/10",
  border: "border-rose-500/30",
  ring: "ring-rose-500",
  bgActive: "bg-rose-500/15",
};

export const CATEGORY_META: Record<
  HublaEventCategory,
  { label: string; tone: TriggerEventTone; icon: string }
> = {
  lead: { label: "Lead", tone: TONE_LEAD, icon: "person_add" },
  member: { label: "Membro", tone: TONE_MEMBER, icon: "badge" },
  subscription: { label: "Assinatura", tone: TONE_SUB, icon: "autorenew" },
  invoice: { label: "Fatura", tone: TONE_INVOICE, icon: "receipt_long" },
  installment: { label: "Parcelamento", tone: TONE_INSTALLMENT, icon: "credit_card" },
  refund: { label: "Reembolso", tone: TONE_REFUND, icon: "undo" },
};

export const TRIGGER_EVENT_CATEGORIES: readonly HublaEventCategory[] = [
  "lead",
  "member",
  "subscription",
  "invoice",
  "installment",
  "refund",
];

export const TRIGGER_EVENTS: readonly TriggerEventMeta[] = [
  // Lead
  {
    value: "lead.abandoned_cart",
    label: "Carrinho abandonado",
    pillLabel: "Carrinho abandonado",
    technical: "lead.abandoned_cart",
    description:
      "Cliente preencheu e-mail/telefone no checkout mas não concluiu compra em 20 minutos.",
    category: "lead",
    categoryLabel: "Lead",
    icon: "remove_shopping_cart",
    tone: TONE_LEAD,
  },
  // Member
  {
    value: "member.access_granted",
    label: "Acesso concedido",
    pillLabel: "Acesso concedido",
    technical: "member.access_granted",
    description: "Cliente recebeu acesso ao produto ou área de membros.",
    category: "member",
    categoryLabel: "Membro",
    icon: "lock_open",
    tone: TONE_MEMBER,
  },
  {
    value: "member.access_removed",
    label: "Acesso removido",
    pillLabel: "Acesso removido",
    technical: "member.access_removed",
    description: "Acesso foi revogado (cancelamento, banimento, expiração).",
    category: "member",
    categoryLabel: "Membro",
    icon: "lock",
    tone: TONE_MEMBER,
  },
  // Subscription
  {
    value: "subscription.created",
    label: "Assinatura criada",
    pillLabel: "Assinatura criada",
    technical: "subscription.created",
    description:
      "Checkout iniciado — aguardando confirmação de pagamento (PIX, boleto, cartão pendente).",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "hourglass_top",
    tone: TONE_SUB,
  },
  {
    value: "subscription.activated",
    label: "Venda ativada",
    pillLabel: "Venda ativada",
    technical: "subscription.activated",
    description: "Pagamento confirmado pela Hubla — assinatura ativa.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "shopping_cart_checkout",
    tone: TONE_SUB,
  },
  {
    value: "subscription.expired",
    label: "Assinatura expirada",
    pillLabel: "Assinatura expirada",
    technical: "subscription.expired",
    description: "Data de fim atingida sem renovação.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "schedule",
    tone: TONE_SUB,
  },
  {
    value: "subscription.deactivated",
    label: "Assinatura desativada",
    pillLabel: "Assinatura desativada",
    technical: "subscription.deactivated",
    description: "Cancelada manualmente, por fraude, ou outras razões operacionais.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "block",
    tone: TONE_SUB,
  },
  {
    value: "subscription.auto_renewal_disabled",
    label: "Renovação automática desligada",
    pillLabel: "Auto-renovação OFF",
    technical: "subscription.auto_renewal_disabled",
    description:
      "Cliente desabilitou renovação automática — risco de churn, janela de retenção.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "toggle_off",
    tone: TONE_SUB,
  },
  {
    value: "subscription.auto_renewal_enabled",
    label: "Renovação automática ligada",
    pillLabel: "Auto-renovação ON",
    technical: "subscription.auto_renewal_enabled",
    description: "Cliente reativou renovação automática.",
    category: "subscription",
    categoryLabel: "Assinatura",
    icon: "toggle_on",
    tone: TONE_SUB,
  },
  // Invoice
  {
    value: "invoice.created",
    label: "Fatura emitida",
    pillLabel: "Fatura emitida",
    technical: "invoice.created",
    description: "Fatura criada — aguardando pagamento.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "receipt",
    tone: TONE_INVOICE,
  },
  {
    value: "invoice.status_updated",
    label: "Status da fatura mudou",
    pillLabel: "Status atualizado",
    technical: "invoice.status_updated",
    description: "Mudança genérica no status da fatura.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "sync",
    tone: TONE_INVOICE,
  },
  {
    value: "invoice.payment_completed",
    label: "Pagamento confirmado",
    pillLabel: "Pagamento OK",
    technical: "invoice.payment_completed",
    description: "Fatura paga com sucesso.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "task_alt",
    tone: TONE_INVOICE,
  },
  {
    value: "invoice.payment_failed",
    label: "Pagamento falhou",
    pillLabel: "Pagamento falhou",
    technical: "invoice.payment_failed",
    description: "Cartão recusado, PIX não confirmado, etc — dunning.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "money_off",
    tone: TONE_INVOICE,
  },
  {
    value: "invoice.expired",
    label: "Fatura vencida",
    pillLabel: "Fatura vencida",
    technical: "invoice.expired",
    description: "Fatura venceu sem pagamento.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "event_busy",
    tone: TONE_INVOICE,
  },
  {
    value: "invoice.refunded",
    label: "Fatura reembolsada",
    pillLabel: "Fatura reembolsada",
    technical: "invoice.refunded",
    description: "Valor devolvido ao cliente.",
    category: "invoice",
    categoryLabel: "Fatura",
    icon: "currency_exchange",
    tone: TONE_INVOICE,
  },
  // Installment
  {
    value: "installment.created",
    label: "Parcelamento criado",
    pillLabel: "Parcelamento criado",
    technical: "installment.created",
    description: "Parcelamento inteligente iniciado.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "splitscreen",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.failed",
    label: "Cobrança de parcela falhou",
    pillLabel: "Parcela falhou",
    technical: "installment.failed",
    description: "Tentativa de cobrança de uma parcela falhou.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "warning",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.in_progress",
    label: "Parcelamento em andamento",
    pillLabel: "Em andamento",
    technical: "installment.in_progress",
    description: "Parcelamento ativo, sem problemas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "trending_up",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.overdue",
    label: "Parcela em atraso",
    pillLabel: "Em atraso",
    technical: "installment.overdue",
    description: "Uma ou mais parcelas estão atrasadas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "running_with_errors",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.cancelled",
    label: "Parcelamento cancelado",
    pillLabel: "Cancelado",
    technical: "installment.cancelled",
    description: "Parcelamento foi cancelado.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "cancel",
    tone: TONE_INSTALLMENT,
  },
  {
    value: "installment.completed",
    label: "Parcelamento concluído",
    pillLabel: "Concluído",
    technical: "installment.completed",
    description: "Todas as parcelas foram pagas.",
    category: "installment",
    categoryLabel: "Parcelamento",
    icon: "check_circle",
    tone: TONE_INSTALLMENT,
  },
  // Refund Request
  {
    value: "refund_request.created",
    label: "Pedido de reembolso aberto",
    pillLabel: "Reembolso solicitado",
    technical: "refund_request.created",
    description:
      "Cliente solicitou reembolso — última chance antes da aprovação.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "help",
    tone: TONE_REFUND,
  },
  {
    value: "refund_request.accepted",
    label: "Reembolso aprovado",
    pillLabel: "Reembolso aprovado",
    technical: "refund_request.accepted",
    description: "Solicitação aceita — reembolso será processado.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "thumb_up",
    tone: TONE_REFUND,
  },
  {
    value: "refund_request.cancelled",
    label: "Pedido de reembolso cancelado",
    pillLabel: "Cancelado pelo cliente",
    technical: "refund_request.cancelled",
    description: "Cliente cancelou a solicitação.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "undo",
    tone: TONE_REFUND,
  },
  {
    value: "refund_request.rejected",
    label: "Pedido de reembolso negado",
    pillLabel: "Negado",
    technical: "refund_request.rejected",
    description: "Solicitação recusada.",
    category: "refund",
    categoryLabel: "Reembolso",
    icon: "thumb_down",
    tone: TONE_REFUND,
  },
];

/**
 * Alias para retro-compatibilidade com flows/eventos antigos que ainda
 * estão no banco com nomes pré-migration (lead.abandoned, subscription.expiring).
 * Usado pelo getTriggerEventMeta para que o LeadDrawer renderize timeline corretamente.
 */
const DEPRECATED_ALIASES: Record<string, HublaEventType> = {
  "lead.abandoned": "lead.abandoned_cart",
  "subscription.expiring": "subscription.expired",
};

export function getTriggerEventMeta(
  value: string,
): TriggerEventMeta | undefined {
  const aliased = DEPRECATED_ALIASES[value] ?? value;
  return TRIGGER_EVENTS.find((e) => e.value === aliased);
}

export function getEventsByCategory(
  category: HublaEventCategory,
): TriggerEventMeta[] {
  return TRIGGER_EVENTS.filter((e) => e.category === category);
}
```

- [ ] **Step 2: Verificar que typescript compila**

```bash
cd apps/web && npx tsc --noEmit
```

Esperado: 0 erros.

> Se aparecerem erros em arquivos que consomem `getTriggerEventMeta` (ex: `LeadDrawer`, `FlowCard`), o tipo é compatível — qualquer warning de propriedade ausente vai ser por causa do alias retornar com nome novo. Aceitável.

- [ ] **Step 3: Verificar visualmente na UI**

```bash
cd apps/web && npm run dev
```

Em `/leads`, abrir um lead que tem `event_type = "lead.abandoned"` ou `"subscription.expiring"` (eventos antigos). A timeline deve renderizar com a label nova ("Carrinho abandonado" / "Assinatura expirada"). Em `/onboarding`, os flows existentes continuam mostrando trigger pill correto.

> **Atenção:** o `FlowDrawer` atual ainda referencia `TRIGGER_EVENTS` no radio-grid 2×3. Após esta task ele vai mostrar 25 entries naquele grid, o que **fica visualmente quebrado**. Aceitável temporariamente — Task 17 reescreve esse drawer e resolve. Anotar no commit.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/onboarding/lib/triggerEvents.ts
git commit -m "feat(onboarding): catalog de 25 eventos hubla + categorias + alias deprecated

UI do FlowDrawer atual fica visualmente quebrada (mostra 25 cards em grid 2x3) até
a reescrita da Task 17."
```

---

## Fase 4 — Edit Template (vertical slice)

### Task 8: `MetaTemplateClient.edit_template` (novo método)

**Files:**
- Modify: `apps/api/src/shared/adapters/meta/template_client.py` (após `delete_template`, linha ~166)
- Test: `apps/api/tests/unit/adapters/meta/test_template_client_edit.py`

- [ ] **Step 1: Criar teste falhando**

```python
# apps/api/tests/unit/adapters/meta/test_template_client_edit.py
import pytest
from unittest.mock import patch, AsyncMock

from shared.adapters.meta.template_client import MetaTemplateClient


@pytest.mark.asyncio
async def test_edit_template_calls_graph_post() -> None:
    client = MetaTemplateClient(api_key="fake-key")
    components = [{"type": "BODY", "text": "Hello {{1}}"}]
    with patch("httpx.AsyncClient") as mock_http:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json = lambda: {"success": True}
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        await client.edit_template(
            template_id="123456789",
            components=components,
            category="MARKETING",
        )

        called_url = mock_http.return_value.__aenter__.return_value.post.call_args.args[0]
        called_body = mock_http.return_value.__aenter__.return_value.post.call_args.kwargs["json"]
        assert called_url.endswith("/123456789")
        assert called_body["components"] == components
        assert called_body["category"] == "MARKETING"


@pytest.mark.asyncio
async def test_edit_template_raises_on_error() -> None:
    client = MetaTemplateClient(api_key="fake-key")
    with patch("httpx.AsyncClient") as mock_http:
        mock_resp = AsyncMock()
        mock_resp.status_code = 400
        mock_resp.text = "bad request"
        mock_resp.headers = {}
        mock_resp.raise_for_status = lambda: (_ for _ in ()).throw(RuntimeError("400"))
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_resp)

        with pytest.raises(RuntimeError):
            await client.edit_template(template_id="123", components=[])
```

- [ ] **Step 2: Rodar teste e ver falhar**

```bash
cd apps/api && uv run pytest tests/unit/adapters/meta/test_template_client_edit.py -v
```

Esperado: AttributeError em `edit_template`.

- [ ] **Step 3: Implementar `edit_template` em `template_client.py`**

Adicionar após o método `delete_template` (~linha 166):

```python
    async def edit_template(
        self,
        *,
        template_id: str,
        components: list[dict] | None = None,
        category: str | None = None,
    ) -> None:
        """Edita um template Meta existente (rota Graph: POST /{template_id}).

        A Meta só aceita edição de templates em status PENDING/REJECTED — para
        APPROVED só `category` pode ser alterado. Validação de status fica no
        use case que chama este método.
        """
        url = f"{_BASE_URL}/{template_id}"
        body: dict = {}
        if components is not None:
            body["components"] = components
        if category is not None:
            body["category"] = category
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                timeout=15,
            )
        if resp.status_code not in (200, 201):
            content_type = resp.headers.get("content-type", "")
            error_body = (
                resp.json()
                if content_type.startswith("application/json")
                else {"message": resp.text[:200]}
            )
            log.warning(
                "meta_edit_template_error",
                status=resp.status_code,
                template_id=template_id,
                body=error_body,
            )
            resp.raise_for_status()
```

- [ ] **Step 4: Rodar testes**

```bash
cd apps/api && uv run pytest tests/unit/adapters/meta/test_template_client_edit.py -v
```

Esperado: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/meta/template_client.py apps/api/tests/unit/adapters/meta/test_template_client_edit.py
git commit -m "feat(meta): MetaTemplateClient.edit_template (POST /{template_id})"
```

---

### Task 9: `EditMetaTemplate` use case + endpoint PATCH

**Files:**
- Create: `apps/api/src/shared/application/use_cases/meta_templates/edit_template.py`
- Modify: `apps/api/src/interface/http/routers/admin/meta_templates.py`
- Modify: `apps/api/src/interface/http/schemas/meta_templates.py`
- Test: `apps/api/tests/unit/application/use_cases/meta_templates/test_edit_template.py`

- [ ] **Step 1: Criar teste do use case**

```python
# apps/api/tests/unit/application/use_cases/meta_templates/test_edit_template.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from shared.application.use_cases.meta_templates.edit_template import (
    EditMetaTemplate,
    EditMetaTemplateInput,
    MetaTemplateApprovedError,
)


@pytest.mark.asyncio
async def test_edit_rejects_approved() -> None:
    template = MagicMock(id=uuid4(), name="t", status="APPROVED", meta_template_id="meta-1")
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=template)
    meta_client = MagicMock()
    use_case = EditMetaTemplate(repo=repo, meta_client=meta_client)

    with pytest.raises(MetaTemplateApprovedError):
        await use_case.execute(EditMetaTemplateInput(
            template_id=template.id,
            components=[{"type": "BODY", "text": "x"}],
        ))
    meta_client.edit_template.assert_not_called()


@pytest.mark.asyncio
async def test_edit_calls_meta_for_pending() -> None:
    template = MagicMock(id=uuid4(), name="t", status="PENDING", meta_template_id="meta-1")
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=template)
    repo.update = AsyncMock()
    meta_client = MagicMock()
    meta_client.edit_template = AsyncMock()
    use_case = EditMetaTemplate(repo=repo, meta_client=meta_client)

    new_components = [{"type": "BODY", "text": "novo"}]
    await use_case.execute(EditMetaTemplateInput(
        template_id=template.id,
        components=new_components,
        category="UTILITY",
    ))

    meta_client.edit_template.assert_called_once()
    call = meta_client.edit_template.call_args
    assert call.kwargs["template_id"] == "meta-1"
    assert call.kwargs["components"] == new_components
    assert call.kwargs["category"] == "UTILITY"
    repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_edit_raises_lookup_error_for_missing() -> None:
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    meta_client = MagicMock()
    use_case = EditMetaTemplate(repo=repo, meta_client=meta_client)

    with pytest.raises(LookupError):
        await use_case.execute(EditMetaTemplateInput(
            template_id=uuid4(),
            components=[],
        ))
```

- [ ] **Step 2: Implementar use case**

```python
# apps/api/src/shared/application/use_cases/meta_templates/edit_template.py
"""Use case: editar template Meta em status não-aprovado."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


class MetaTemplateApprovedError(Exception):
    """Template está APPROVED — Meta não permite editar (só `category` parcialmente)."""

    def __init__(self, template_id: UUID, status: str) -> None:
        super().__init__(f"Template {template_id} está {status} — não editável")
        self.template_id = template_id
        self.status = status


@dataclass
class EditMetaTemplateInput:
    template_id: UUID
    components: list[dict] | None = None
    category: str | None = None
    media_url: str | None = None
    media_kind: str | None = None


class EditMetaTemplate:
    def __init__(self, *, repo, meta_client) -> None:  # tipos do repo/meta_client são duck-typed
        self._repo = repo
        self._meta_client = meta_client

    async def execute(self, input_: EditMetaTemplateInput):
        template = await self._repo.get_by_id(template_id=input_.template_id)
        if template is None:
            raise LookupError(f"template {input_.template_id} not found")

        if template.status == "APPROVED":
            raise MetaTemplateApprovedError(input_.template_id, template.status)

        # Edita na Meta
        await self._meta_client.edit_template(
            template_id=template.meta_template_id,
            components=input_.components,
            category=input_.category,
        )

        # Persiste local
        await self._repo.update(
            template_id=template.id,
            components=input_.components if input_.components is not None else template.components,
            category=input_.category or template.category,
            media_url=input_.media_url if input_.media_url is not None else template.media_url,
            media_kind=input_.media_kind if input_.media_kind is not None else template.media_kind,
        )

        return await self._repo.get_by_id(template_id=input_.template_id)
```

> **Nota:** o método `repo.update(...)` provavelmente ainda não existe em `MetaTemplateRepository`. Step 3 adiciona.

- [ ] **Step 3: Adicionar método `update` no `MetaTemplateRepository`**

```bash
cat apps/api/src/shared/adapters/db/repositories/meta_template_repo.py
```

Adicionar método `update` que persiste mudanças no `MetaTemplateModel`:

```python
async def update(
    self,
    *,
    template_id: UUID,
    components: list[dict] | None = None,
    category: str | None = None,
    media_url: str | None = None,
    media_kind: str | None = None,
) -> None:
    stmt = (
        update(MetaTemplateModel)
        .where(MetaTemplateModel.id == template_id)
        .values(
            **{k: v for k, v in {
                "components": components,
                "category": category,
                "media_url": media_url,
                "media_kind": media_kind,
            }.items() if v is not None},
            updated_at=datetime.now(timezone.utc),
        )
    )
    await self._session.execute(stmt)
    await self._session.flush()
```

(Adicionar imports `update`, `datetime`, `timezone` se ausentes.)

- [ ] **Step 4: Rodar teste do use case**

```bash
cd apps/api && uv run pytest tests/unit/application/use_cases/meta_templates/test_edit_template.py -v
```

Esperado: 3 passed.

- [ ] **Step 5: Adicionar schema do request**

Em `apps/api/src/interface/http/schemas/meta_templates.py`, adicionar:

```python
class EditTemplateRequest(BaseModel):
    """Todos os campos opcionais — só atualiza o que vier preenchido."""
    components: list[dict] | None = None
    category: TemplateCategory | None = None
    media_url: str | None = None
    media_object_key: str | None = None
    media_kind: MediaKind | None = None
```

(Reusar tipos `TemplateCategory` e `MediaKind` já existentes no schema.)

- [ ] **Step 6: Adicionar endpoint `PATCH /admin/meta-templates/{template_id}`**

Em `apps/api/src/interface/http/routers/admin/meta_templates.py`, adicionar:

```python
@router.patch(
    "/meta-templates/{template_id}",
    response_model=MetaTemplateResponse,
)
async def edit_template(
    template_id: UUID,
    body: EditTemplateRequest,
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> MetaTemplateResponse:
    from shared.application.use_cases.meta_templates.edit_template import (
        EditMetaTemplate,
        EditMetaTemplateInput,
        MetaTemplateApprovedError,
    )

    client, _waba_id, _app_id = await _get_meta_client_and_waba(auth)
    async with session_scope() as session:
        repo = MetaTemplateRepository(session=session)
        use_case = EditMetaTemplate(repo=repo, meta_client=client)
        try:
            record = await use_case.execute(
                EditMetaTemplateInput(
                    template_id=template_id,
                    components=body.components,
                    category=body.category,
                    media_url=body.media_url,
                    media_kind=body.media_kind,
                )
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="META_TEMPLATE_NOT_FOUND") from exc
        except MetaTemplateApprovedError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "template_approved_immutable",
                    "message": "Templates aprovados pela Meta não podem ser editados.",
                },
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail={"code": "META_API_ERROR", "detail": str(exc)},
            ) from exc
        return _to_response(record)
```

Adicionar `EditTemplateRequest` aos imports no topo do arquivo.

- [ ] **Step 7: Rodar todos os testes do módulo**

```bash
cd apps/api && uv run pytest tests/unit/application/use_cases/meta_templates/ tests/unit/adapters/meta/ -v
```

Esperado: todos passam.

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/shared/application/use_cases/meta_templates/edit_template.py \
        apps/api/src/shared/adapters/db/repositories/meta_template_repo.py \
        apps/api/src/interface/http/routers/admin/meta_templates.py \
        apps/api/src/interface/http/schemas/meta_templates.py \
        apps/api/tests/unit/application/use_cases/meta_templates/test_edit_template.py
git commit -m "feat(meta): PATCH /admin/meta-templates/{id} — edita template não-aprovado"
```

---

### Task 10: `editMetaTemplate` no api client + `TemplateModal` em modo edit

**Files:**
- Modify: `apps/web/src/lib/api.ts` (após `createMetaTemplate`)
- Modify: `apps/web/src/features/templates/components/TemplateModal.tsx`
- Modify: `apps/web/src/features/templates/components/TemplateForm.tsx`
- Modify: `apps/web/src/app/(admin)/templates/page.tsx`

- [ ] **Step 1: Adicionar `editMetaTemplate` em `lib/api.ts`**

Após a função `createMetaTemplate`, adicionar:

```ts
export interface EditTemplateDto {
  components?: unknown[];
  category?: string;
  media_url?: string;
  media_object_key?: string;
  media_kind?: string;
}

export async function editMetaTemplate(
  id: string,
  dto: EditTemplateDto,
): Promise<MetaTemplate> {
  return apiFetch<MetaTemplate>(`/admin/meta-templates/${id}`, {
    method: "PATCH",
    body: JSON.stringify(dto),
  });
}
```

- [ ] **Step 2: Modificar `TemplateForm.tsx` para aceitar `initialValues`**

Ler o arquivo:

```bash
cat apps/web/src/features/templates/components/TemplateForm.tsx | head -80
```

Identificar como o form é estruturado. Adicionar prop opcional `initialValues?: Partial<TemplateFormData>` que pré-preenche os campos via `useForm({ defaultValues: initialValues })`. Quando `initialValues` está presente:
- Campo `name`: read-only (não permite editar — Meta exige nome estável).
- Demais campos: editáveis normalmente.

Não tocar na lógica de submit — quem decide se chama create ou edit é o `TemplateModal`.

- [ ] **Step 3: Modificar `TemplateModal.tsx` para aceitar prop `template?`**

Ler o arquivo:

```bash
cat apps/web/src/features/templates/components/TemplateModal.tsx
```

Adicionar prop opcional `template?: MetaTemplate`. Quando presente:
- Título: `"Editar template — ${template.name}"` ao invés de `"Novo template"`.
- Botão submit: `"Salvar alterações"` ao invés de `"Criar"`.
- `onSubmit` chama `editMetaTemplate(template.id, data)` em vez de `createMetaTemplate(data)`.
- `TemplateForm` recebe `initialValues` derivados do template.

```tsx
// pseudo-código guia
interface TemplateModalProps {
  open: boolean;
  onClose: () => void;
  template?: MetaTemplate; // novo
  onCreate?: (dto: CreateTemplateDto) => Promise<void>;
  onEdit?: (id: string, dto: EditTemplateDto) => Promise<void>; // novo
}

// dentro do componente:
const isEditing = !!template;
const title = isEditing ? `Editar template — ${template.name}` : "Novo template";
const submitLabel = isEditing ? "Salvar alterações" : "Criar";
const initialValues = isEditing
  ? {
      name: template.name,
      category: template.category,
      language: template.language,
      // ... derivar do template.components: header, body, footer, buttons
    }
  : undefined;

async function handleSubmit(data: TemplateFormData) {
  try {
    if (isEditing && template) {
      await onEdit!(template.id, dataToEditDto(data));
    } else {
      await onCreate!(dataToCreateDto(data));
    }
    toast.success(isEditing ? "Template atualizado" : "Template criado");
    onClose(); // já existe — confirmar
  } catch (err) {
    toast.error(`Erro: ${(err as Error).message}`);
  }
}
```

> **Nota detalhada para o helper `dataToEditDto`:** o `TemplateForm` retorna campos em formato form (header, body, footer, buttons separados). O endpoint Meta espera `components: [{type, text, ...}]`. Já existe lógica de conversão para o `createMetaTemplate` (em algum lugar do form ou modal). Reusar essa mesma conversão para edit — extrair em helper se necessário.

- [ ] **Step 4: Adicionar botão "Editar" na lista de templates**

Em `apps/web/src/app/(admin)/templates/page.tsx`:

- Adicionar state `editingTemplate: MetaTemplate | null`.
- Em cada card de template, adicionar botão "Editar" que abre o modal em modo edit, mas APENAS quando `template.status !== "APPROVED"`.
- Em templates aprovados, mostrar tooltip: "Templates aprovados pela Meta não podem ser editados."
- Passar `template={editingTemplate ?? undefined}` e `onEdit={handleEdit}` ao `TemplateModal`.

```tsx
// pseudo-código guia
const [editingTemplate, setEditingTemplate] = useState<MetaTemplate | null>(null);

async function handleEdit(id: string, dto: EditTemplateDto) {
  await editMetaTemplate(id, dto);
  setEditingTemplate(null);
  refetch();
}

// no card:
{template.status !== "APPROVED" && (
  <button
    onClick={() => setEditingTemplate(template)}
    className="..."
  >
    <span className="material-symbols-outlined">edit</span>
    Editar
  </button>
)}
{template.status === "APPROVED" && (
  <span
    className="text-on-surface-variant cursor-help"
    title="Templates aprovados pela Meta não podem ser editados. Crie um novo com nome diferente."
  >
    <span className="material-symbols-outlined">lock</span>
  </span>
)}

// modal:
<TemplateModal
  open={modalOpen || !!editingTemplate}
  onClose={() => { setModalOpen(false); setEditingTemplate(null); }}
  template={editingTemplate ?? undefined}
  onCreate={handleCreate}
  onEdit={handleEdit}
/>
```

- [ ] **Step 5: Verificar TypeScript + testar manualmente**

```bash
cd apps/web && npx tsc --noEmit && npm run dev
```

Em `/templates`:
- Template em `PENDING` ou `REJECTED`: botão "Editar" aparece. Clica → modal abre preenchido. Edita body → "Salvar alterações" → modal fecha + lista atualiza.
- Template em `APPROVED`: botão "Editar" some, ícone de cadeado com tooltip aparece.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/api.ts \
        apps/web/src/features/templates/components/TemplateModal.tsx \
        apps/web/src/features/templates/components/TemplateForm.tsx \
        apps/web/src/app/\(admin\)/templates/page.tsx
git commit -m "feat(templates): editar template não-aprovado reutilizando modal de criação"
```

---

## Fase 5 — Stepper UI (FlowDrawer reescrito)

> Esta fase quebra o FlowDrawer atual em componentes menores. Cada Task abaixo cria um componente novo. A Task 17 (final) reescreve o FlowDrawer integrando todos e substitui o existente.

### Task 11: Componente `EventCard`

**Files:**
- Create: `apps/web/src/features/onboarding/components/EventCard.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/onboarding/components/EventCard.tsx
"use client";

import type { TriggerEventMeta } from "../lib/triggerEvents";

interface EventCardProps {
  event: TriggerEventMeta;
  selected: boolean;
  onSelect: () => void;
}

export function EventCard({ event, selected, onSelect }: EventCardProps) {
  const t = event.tone;
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`flex items-start gap-3 rounded-lg border p-3 text-left transition-all
        ${selected
          ? `${t.bgActive} ${t.border} ring-2 ${t.ring}`
          : "border-outline-variant bg-surface-container hover:bg-surface-container-high"
        }`}
    >
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md ${t.bg}`}>
        <span className={`material-symbols-outlined ${t.text}`}>{event.icon}</span>
      </div>
      <div className="min-w-0 flex-1">
        <h5 className="text-sm font-semibold text-on-surface">{event.label}</h5>
        <p className="mt-0.5 text-xs leading-snug text-on-surface-variant">
          {event.description}
        </p>
      </div>
    </button>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/features/onboarding/components/EventCard.tsx
git commit -m "feat(onboarding): EventCard component para grid de eventos no stepper"
```

---

### Task 12: Componente `StepRail`

**Files:**
- Create: `apps/web/src/features/onboarding/components/steps/StepRail.tsx`

- [ ] **Step 1: Criar diretório e o componente**

```bash
mkdir -p apps/web/src/features/onboarding/components/steps
```

```tsx
// apps/web/src/features/onboarding/components/steps/StepRail.tsx
"use client";

export type StepIndex = 1 | 2 | 3;
export type StepStatus = "done" | "current" | "pending" | "locked";

export interface StepDescriptor {
  index: StepIndex;
  label: string;
  status: StepStatus;
  hint?: string;
}

interface StepRailProps {
  steps: StepDescriptor[];
  onNavigate: (index: StepIndex) => void;
}

export function StepRail({ steps, onNavigate }: StepRailProps) {
  return (
    <ol className="flex flex-col gap-0 pr-6">
      {steps.map((step, i) => (
        <li key={step.index} className="flex items-stretch gap-3">
          <div className="flex flex-col items-center">
            <NodeButton step={step} onClick={() => onNavigate(step.index)} />
            {i < steps.length - 1 && (
              <div
                className={`my-1 w-0.5 flex-1 min-h-6 ${
                  step.status === "done" ? "bg-emerald-500" : "bg-outline-variant"
                }`}
              />
            )}
          </div>
          <div className="pb-6 pt-1">
            <p className={`text-sm font-medium ${
              step.status === "current"
                ? "text-on-surface"
                : step.status === "done"
                ? "text-emerald-500"
                : "text-on-surface-variant"
            }`}>
              {step.label}
            </p>
            {step.hint && (
              <p className="mt-0.5 text-xs text-on-surface-variant">{step.hint}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

function NodeButton({
  step,
  onClick,
}: {
  step: StepDescriptor;
  onClick: () => void;
}) {
  const isLocked = step.status === "locked";
  const isDone = step.status === "done";
  const isCurrent = step.status === "current";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={isLocked}
      aria-current={isCurrent ? "step" : undefined}
      className={`flex h-10 w-10 items-center justify-center rounded-full border-2 font-semibold text-sm transition-all
        ${isCurrent
          ? "border-transparent bg-primary text-on-primary shadow-md shadow-primary/30"
          : isDone
          ? "border-transparent bg-emerald-500 text-white"
          : isLocked
          ? "cursor-not-allowed border-outline-variant bg-surface-container text-on-surface-variant opacity-60"
          : "border-outline-variant bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
        }`}
    >
      {isDone ? (
        <span className="material-symbols-outlined text-base">check</span>
      ) : (
        step.index
      )}
    </button>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/features/onboarding/components/steps/StepRail.tsx
git commit -m "feat(onboarding): StepRail component (rail lateral de 3 círculos numerados)"
```

---

### Task 13: Componente `StepProductPicker`

**Files:**
- Create: `apps/web/src/features/onboarding/components/steps/StepProductPicker.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/onboarding/components/steps/StepProductPicker.tsx
"use client";

import type { Product } from "@/features/products/types";

interface StepProductPickerProps {
  products: Product[];
  loading: boolean;
  selectedProductId: string;
  onSelect: (productId: string) => void;
  disabled?: boolean;
}

export function StepProductPicker({
  products,
  loading,
  selectedProductId,
  onSelect,
  disabled = false,
}: StepProductPickerProps) {
  if (loading) {
    return (
      <div className="text-sm text-on-surface-variant">Carregando produtos...</div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="rounded-md border border-outline-variant bg-surface-container p-4 text-sm text-on-surface-variant">
        Nenhum produto cadastrado. Cadastre um produto em <strong>/products</strong> antes de criar um flow.
      </div>
    );
  }

  return (
    <div>
      <label className="block text-sm font-medium text-on-surface" htmlFor="step-product-select">
        Selecione o produto
      </label>
      <p className="mt-1 text-xs text-on-surface-variant">
        Cada flow de onboarding está vinculado a um produto do catálogo.
      </p>
      <select
        id="step-product-select"
        value={selectedProductId}
        onChange={(e) => onSelect(e.target.value)}
        disabled={disabled}
        className="mt-3 w-full rounded-md border border-outline-variant bg-surface-container px-3 py-2 text-sm text-on-surface focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary disabled:cursor-not-allowed disabled:opacity-60"
      >
        <option value="">— Selecione —</option>
        {products.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>

      {selectedProductId && (
        <div className="mt-4 rounded-md border border-outline-variant bg-surface-container-high p-3 text-xs text-on-surface-variant">
          <span className="material-symbols-outlined align-middle text-sm">info</span>
          {" "}
          O nome do flow será gerado automaticamente como <code>Produto: {products.find(p => p.id === selectedProductId)?.name}</code>.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/features/onboarding/components/steps/StepProductPicker.tsx
git commit -m "feat(onboarding): StepProductPicker component (step 1 do stepper)"
```

---

### Task 14: Componente `StepEventPicker` (com tabs)

**Files:**
- Create: `apps/web/src/features/onboarding/components/steps/StepEventPicker.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/onboarding/components/steps/StepEventPicker.tsx
"use client";

import { useState } from "react";
import { EventCard } from "../EventCard";
import {
  CATEGORY_META,
  TRIGGER_EVENT_CATEGORIES,
  getEventsByCategory,
  type HublaEventCategory,
  type HublaEventType,
} from "../../lib/triggerEvents";

interface StepEventPickerProps {
  selectedEventType: HublaEventType;
  onSelect: (eventType: HublaEventType) => void;
  isActive: boolean;
  onToggleActive: (active: boolean) => void;
}

export function StepEventPicker({
  selectedEventType,
  onSelect,
  isActive,
  onToggleActive,
}: StepEventPickerProps) {
  // Inicializa tab na categoria do evento selecionado (ou subscription como default)
  const initialCategory: HublaEventCategory =
    TRIGGER_EVENT_CATEGORIES.find((c) =>
      getEventsByCategory(c).some((e) => e.value === selectedEventType),
    ) ?? "subscription";

  const [activeTab, setActiveTab] = useState<HublaEventCategory>(initialCategory);
  const events = getEventsByCategory(activeTab);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-on-surface">
          Qual evento da Hubla dispara este flow?
        </h3>
        <p className="mt-1 text-xs text-on-surface-variant">
          Escolha a categoria nas abas e selecione o evento. Apenas um evento por flow.
        </p>
      </div>

      {/* Tabs de categoria */}
      <div className="flex flex-wrap gap-1 border-b border-outline-variant pb-2">
        {TRIGGER_EVENT_CATEGORIES.map((cat) => {
          const meta = CATEGORY_META[cat];
          const count = getEventsByCategory(cat).length;
          const active = activeTab === cat;
          return (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveTab(cat)}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors
                ${active
                  ? `${meta.tone.bgActive} ${meta.tone.text}`
                  : "text-on-surface-variant hover:bg-surface-container-high"
                }`}
            >
              <span className="material-symbols-outlined text-sm">{meta.icon}</span>
              {meta.label}
              <span className="rounded-full bg-black/10 px-1.5 text-[10px] font-semibold dark:bg-white/10">
                {count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Grid de eventos da tab ativa */}
      <div
        key={activeTab}
        className="grid grid-cols-1 gap-2 md:grid-cols-2 onboarding-step-fade"
      >
        {events.map((event) => (
          <EventCard
            key={event.value}
            event={event}
            selected={event.value === selectedEventType}
            onSelect={() => onSelect(event.value)}
          />
        ))}
      </div>

      {/* Toggle ativo */}
      <div className="flex items-center gap-2 pt-2">
        <input
          id="flow-is-active"
          type="checkbox"
          checked={isActive}
          onChange={(e) => onToggleActive(e.target.checked)}
          className="h-4 w-4 rounded border-outline-variant accent-primary"
        />
        <label htmlFor="flow-is-active" className="text-sm text-on-surface">
          Flow ativo (recebe eventos)
        </label>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/features/onboarding/components/steps/StepEventPicker.tsx
git commit -m "feat(onboarding): StepEventPicker component (tabs por categoria + grid de eventos)"
```

---

### Task 15: Componente `StepMessageBuilder` (wrapper de `StepList`)

**Files:**
- Create: `apps/web/src/features/onboarding/components/steps/StepMessageBuilder.tsx`

- [ ] **Step 1: Criar o componente**

```tsx
// apps/web/src/features/onboarding/components/steps/StepMessageBuilder.tsx
"use client";

import { StepList } from "../StepList";
import { useOnboardingSteps } from "../../hooks/useOnboardingSteps";

interface StepMessageBuilderProps {
  flowId: string;
}

export function StepMessageBuilder({ flowId }: StepMessageBuilderProps) {
  const {
    steps,
    loading,
    create,
    update,
    remove,
    reorder,
  } = useOnboardingSteps(flowId);

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-sm font-semibold text-on-surface">
          Mensagens da sequência
        </h3>
        <p className="mt-1 text-xs text-on-surface-variant">
          Adicione as mensagens que serão enviadas após o evento gatilho. Arraste para reordenar.
        </p>
      </div>
      <StepList
        steps={steps}
        loading={loading}
        onCreate={create}
        onUpdate={update}
        onRemove={remove}
        onReorder={reorder}
      />
    </div>
  );
}
```

> **Nota:** verificar a assinatura real do `StepList` (props que aceita). Ajustar este wrapper para passar exatamente os mesmos nomes/tipos que o `FlowDrawer` atual usa hoje. O objetivo desta task é só extrair o uso atual num componente próprio para o stepper consumir.

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/features/onboarding/components/steps/StepMessageBuilder.tsx
git commit -m "feat(onboarding): StepMessageBuilder component (step 3 — wrapper de StepList)"
```

---

### Task 16: Animação CSS dos steps (slide + fade)

**Files:**
- Modify: `apps/web/src/app/globals.css`

- [ ] **Step 1: Adicionar keyframes**

No final do `globals.css`:

```css
/* Animação de transição entre steps do FlowDrawer */
@keyframes onboarding-step-slide-in-forward {
  from {
    opacity: 0;
    transform: translateX(12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes onboarding-step-slide-in-backward {
  from {
    opacity: 0;
    transform: translateX(-12px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes onboarding-step-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.onboarding-step-forward {
  animation: onboarding-step-slide-in-forward 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.onboarding-step-backward {
  animation: onboarding-step-slide-in-backward 200ms cubic-bezier(0.16, 1, 0.3, 1);
}

.onboarding-step-fade {
  animation: onboarding-step-fade 150ms ease-out;
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/app/globals.css
git commit -m "feat(onboarding): CSS keyframes para transição suave entre steps"
```

---

### Task 17: Reescrever `FlowDrawer` integrando stepper + state machine

**Files:**
- Modify: `apps/web/src/features/onboarding/components/FlowDrawer.tsx` (reescrita completa)

- [ ] **Step 1: Backup do arquivo atual (opcional — git já cobre)**

```bash
git show HEAD:apps/web/src/features/onboarding/components/FlowDrawer.tsx > /tmp/FlowDrawer.old.tsx
```

- [ ] **Step 2: Reescrever o arquivo**

```tsx
// apps/web/src/features/onboarding/components/FlowDrawer.tsx
"use client";

import { useEffect, useMemo, useState } from "react";
import { Drawer } from "@/shared/components/Drawer";
import { useProducts } from "@/features/products/hooks/useProducts";
import { useToast } from "@/shared/hooks/useToast";
import type {
  CreateFlowInput,
  OnboardingFlow,
  UpdateFlowInput,
} from "../types";
import type { HublaEventType } from "../lib/triggerEvents";
import { StepRail, type StepIndex, type StepDescriptor } from "./steps/StepRail";
import { StepProductPicker } from "./steps/StepProductPicker";
import { StepEventPicker } from "./steps/StepEventPicker";
import { StepMessageBuilder } from "./steps/StepMessageBuilder";

interface Props {
  open: boolean;
  flow: OnboardingFlow | null;
  onClose: () => void;
  onCreate: (dto: CreateFlowInput) => Promise<OnboardingFlow>;
  onUpdate: (id: string, dto: UpdateFlowInput) => Promise<void>;
}

interface StepperState {
  current: StepIndex;
  direction: "forward" | "backward";
  productId: string;
  triggerEventType: HublaEventType;
  isActive: boolean;
  flowId: string | null;
}

const INITIAL_STATE: StepperState = {
  current: 1,
  direction: "forward",
  productId: "",
  triggerEventType: "subscription.activated",
  isActive: true,
  flowId: null,
};

export function FlowDrawer({ open, flow, onClose, onCreate, onUpdate }: Props) {
  const toast = useToast();
  const { products, loading: productsLoading } = useProducts();
  const [saving, setSaving] = useState(false);
  const [state, setState] = useState<StepperState>(INITIAL_STATE);

  const isEditing = !!flow;
  const product = useMemo(
    () => products.find((p) => p.id === state.productId),
    [products, state.productId],
  );

  // Reset/hydrate ao abrir
  useEffect(() => {
    if (open) {
      if (flow) {
        setState({
          current: 1,
          direction: "forward",
          productId: flow.product.id,
          triggerEventType: (flow.trigger_event_type as HublaEventType) ?? "subscription.activated",
          isActive: flow.is_active,
          flowId: flow.id,
        });
      } else {
        setState(INITIAL_STATE);
      }
    }
  }, [flow, open]);

  function goTo(target: StepIndex) {
    setState((prev) => ({
      ...prev,
      direction: target > prev.current ? "forward" : "backward",
      current: target,
    }));
  }

  function canNavigateTo(target: StepIndex): boolean {
    if (isEditing) return true; // editar = rail livre
    // criar = sequencial com gating
    if (target === 1) return true;
    if (target === 2) return !!state.productId;
    if (target === 3) return !!state.flowId;
    return false;
  }

  async function saveStep1AndAdvance() {
    if (!state.productId) {
      toast.error("Selecione um produto antes de continuar");
      return;
    }
    if (isEditing) {
      // Em modo edit, salva o produto se mudou
      try {
        setSaving(true);
        await onUpdate(state.flowId!, {
          product_id: state.productId,
          trigger_event_type: state.triggerEventType,
          is_active: state.isActive,
          name: `Produto: ${product?.name ?? ""}`,
        });
        toast.success("Produto atualizado");
      } catch (err) {
        toast.error(`Erro: ${(err as Error).message}`);
        return;
      } finally {
        setSaving(false);
      }
    }
    goTo(2);
  }

  async function saveStep2AndAdvance() {
    if (!product) {
      toast.error("Produto não encontrado");
      return;
    }
    try {
      setSaving(true);
      if (state.flowId) {
        await onUpdate(state.flowId, {
          product_id: state.productId,
          trigger_event_type: state.triggerEventType,
          is_active: state.isActive,
          name: `Produto: ${product.name}`,
        });
        toast.success("Flow atualizado");
      } else {
        const created = await onCreate({
          product_id: state.productId,
          trigger_event_type: state.triggerEventType,
          is_active: state.isActive,
          name: `Produto: ${product.name}`,
        });
        setState((prev) => ({ ...prev, flowId: created.id }));
        toast.success("Flow criado — agora configure as mensagens");
      }
      goTo(3);
    } catch (err) {
      toast.error(`Erro ao salvar: ${(err as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  function finish() {
    onClose();
  }

  const stepDescriptors: StepDescriptor[] = [
    {
      index: 1,
      label: "Produto",
      hint: product?.name,
      status:
        state.current === 1
          ? "current"
          : state.productId
          ? "done"
          : "pending",
    },
    {
      index: 2,
      label: "Evento gatilho",
      hint: state.flowId ? state.triggerEventType : undefined,
      status:
        state.current === 2
          ? "current"
          : state.flowId
          ? "done"
          : !canNavigateTo(2)
          ? "locked"
          : "pending",
    },
    {
      index: 3,
      label: "Mensagens",
      status:
        state.current === 3
          ? "current"
          : !canNavigateTo(3)
          ? "locked"
          : "pending",
    },
  ];

  const title = isEditing ? "Editar flow" : "Novo flow de onboarding";

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <StepFooter
          current={state.current}
          saving={saving}
          isEditing={isEditing}
          canAdvance={state.current === 1 ? !!state.productId : state.current === 2}
          onBack={() => goTo((state.current - 1) as StepIndex)}
          onForward={async () => {
            if (state.current === 1) await saveStep1AndAdvance();
            else if (state.current === 2) await saveStep2AndAdvance();
            else finish();
          }}
        />
      }
    >
      <div className="flex gap-6">
        {/* Rail lateral */}
        <div className="shrink-0">
          <StepRail
            steps={stepDescriptors}
            onNavigate={(idx) => {
              if (canNavigateTo(idx)) goTo(idx);
            }}
          />
        </div>

        {/* Painel do step ativo com animação */}
        <div className="min-w-0 flex-1">
          <div
            key={state.current}
            className={
              state.direction === "forward"
                ? "onboarding-step-forward"
                : "onboarding-step-backward"
            }
          >
            {state.current === 1 && (
              <StepProductPicker
                products={products}
                loading={productsLoading}
                selectedProductId={state.productId}
                onSelect={(productId) =>
                  setState((prev) => ({ ...prev, productId }))
                }
                disabled={isEditing} // produto travado ao editar (FK)
              />
            )}
            {state.current === 2 && (
              <StepEventPicker
                selectedEventType={state.triggerEventType}
                onSelect={(triggerEventType) =>
                  setState((prev) => ({ ...prev, triggerEventType }))
                }
                isActive={state.isActive}
                onToggleActive={(isActive) =>
                  setState((prev) => ({ ...prev, isActive }))
                }
              />
            )}
            {state.current === 3 && state.flowId && (
              <StepMessageBuilder flowId={state.flowId} />
            )}
          </div>
        </div>
      </div>
    </Drawer>
  );
}

function StepFooter({
  current,
  saving,
  isEditing,
  canAdvance,
  onBack,
  onForward,
}: {
  current: StepIndex;
  saving: boolean;
  isEditing: boolean;
  canAdvance: boolean;
  onBack: () => void;
  onForward: () => Promise<void> | void;
}) {
  const forwardLabel =
    current === 3 ? "Concluir" : current === 2 ? "Salvar e continuar" : "Próximo";
  return (
    <div className="flex items-center justify-between">
      <button
        type="button"
        onClick={onBack}
        disabled={current === 1 || saving}
        className="rounded-md px-4 py-2 text-sm text-on-surface-variant hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-40"
      >
        Voltar
      </button>
      <button
        type="button"
        onClick={() => void onForward()}
        disabled={(!canAdvance && current !== 3) || saving}
        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-on-primary shadow-sm hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {saving ? "Salvando..." : forwardLabel}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Verificar TypeScript**

```bash
cd apps/web && npx tsc --noEmit
```

Esperado: 0 erros. Se aparecerem erros sobre tipos faltando em `CreateFlowInput`/`UpdateFlowInput`, verificar que o type `trigger_event_type` está como `HublaEventType` (ou `string`) em `types.ts`. Ajustar se necessário.

- [ ] **Step 4: Testar manualmente — fluxo completo de criação**

```bash
cd apps/web && npm run dev
```

Em `/onboarding`:
1. Clicar "Novo flow" → drawer abre em step 1, rail mostra "● Produto / ○ Evento / ○ Mensagens".
2. Selecionar produto → botão "Próximo" habilita → clica → animação slide+fade, vai pro step 2.
3. Tab "Assinatura" ativa por padrão → clicar tab "Membro" → grid muda com fade → clicar "Acesso concedido" → card fica selecionado.
4. Clicar "Salvar e continuar" → backend cria flow → toast sucesso → step 3 com mensagens vazias.
5. Adicionar uma mensagem (StepList existente) → drag-reorder funciona normal.
6. Clicar "Concluir" → drawer fecha.

- [ ] **Step 5: Testar manualmente — fluxo de edição**

Clicar "Configurar" em um flow existente:
1. Drawer abre em step 1 com produto pré-selecionado (disabled).
2. Rail é clicável livre — clicar "3" pula direto pra mensagens.
3. Clicar "2" volta com animação backward.
4. Trocar evento → "Salvar e continuar" → toast atualiza → fecha drawer.

- [ ] **Step 6: Testar visualmente: 25 eventos nas 6 tabs**

No step 2:
- Tab "Lead" (1 card)
- Tab "Membro" (2 cards)
- Tab "Assinatura" (6 cards) — selecionado por padrão
- Tab "Fatura" (6 cards)
- Tab "Parcelamento" (6 cards)
- Tab "Reembolso" (4 cards)

Cada categoria com sua cor correspondente. Cards selecionados com ring na cor.

- [ ] **Step 7: Verificar que click-fora fecha (item 3 já feito na Task 1)**

Com drawer aberto, clicar na sidebar → fecha. Em qualquer step.

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/features/onboarding/components/FlowDrawer.tsx
git commit -m "feat(onboarding): reescrita do FlowDrawer em stepper vertical de 3 passos

- Rail lateral com 3 círculos numerados conectados
- Step 1 Produto, Step 2 Evento (tabs por categoria com 25 eventos), Step 3 Mensagens
- Animação slide+fade entre steps (200ms)
- Sequencial ao criar com gating; livre ao editar (rail clicável)
- Drawer fecha após Concluir/salvar
- Reusa StepList existente (drag-reorder preservado)"
```

---

## Validação final

### Task 18: Validação end-to-end

**Files:** (nenhuma modificação — só checks)

- [ ] **Step 1: Subir backend completo**

```bash
docker compose up -d postgres redis
cd apps/api && uv run alembic upgrade heads
cd apps/api && uv run uvicorn main:app --reload &
cd apps/api && uv run python -m worker &
```

- [ ] **Step 2: Disparar webhook fake para cada categoria**

Usando `curl` ou Postman, mandar 1 evento de cada categoria pro `/webhook/hubla`:

```bash
# Lead
curl -X POST http://localhost:8000/webhook/hubla \
  -H "x-hubla-token: $HUBLA_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"id":"evt1","type":"lead.abandoned_cart","subscription":{"id":"s1","product":{"id":"<prod-uuid>","name":"X"}},"user":{"name":"Test","email":"t@x.com","phone":"+5511999999999"}}'

# Member
curl -X POST http://localhost:8000/webhook/hubla \
  -H "x-hubla-token: $HUBLA_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"id":"evt2","type":"member.access_granted",...}'

# Invoice payment_failed
# Installment overdue
# Refund_request created
# (etc — cobrir 6 categorias)
```

Verificar que cada um aparece em `hubla_events` (DBeaver / `psql`).

- [ ] **Step 3: Testar webhook com evento desconhecido**

```bash
curl -X POST http://localhost:8000/webhook/hubla \
  -H "x-hubla-token: $HUBLA_WEBHOOK_SECRET" \
  -H "Content-Type: application/json" \
  -d '{"id":"evt-unknown","type":"foo.bar","subscription":{...}}'
```

Verificar:
- Resposta `202`
- Logs do worker: `hubla_unknown_event event_type=foo.bar`
- `hubla_events` tem o registro com `event_type='foo.bar'`

- [ ] **Step 4: Testar criação de flow com novo trigger e disparo**

1. UI: criar flow com produto X e trigger `member.access_granted` + 1 step de mensagem.
2. Disparar webhook `member.access_granted` com payload do produto X.
3. Verificar: `followup_enrollments` tem 1 linha nova; step de mensagem é enviado (ou agendado) via worker.

- [ ] **Step 5: Testar edit template**

1. Em `/templates`, selecionar um template em `PENDING` → "Editar" → muda body → "Salvar alterações".
2. Verificar: `meta_templates.components` atualizado no banco; `updated_at` muda.
3. Verificar UI: lista atualizada; modal fechou.
4. Tentar editar template `APPROVED`: botão "Editar" não aparece, só ícone de cadeado com tooltip.

- [ ] **Step 6: Testar UX fixes**

- `/products`: clicar "Excluir" → ConfirmDialog modal (não confirm() nativo). ✓
- `/onboarding`: abrir drawer → clicar sidebar → fecha. ✓
- `/onboarding`: salvar flow → drawer fecha auto. ✓

- [ ] **Step 7: Rodar suite de testes**

```bash
cd apps/api && uv run pytest tests/unit -v
cd apps/api && uv run ruff check src tests
cd apps/api && uv run mypy src
cd apps/web && npx tsc --noEmit
cd apps/web && npm run lint
```

Esperado: todos passam, 0 erros.

- [ ] **Step 8: Push para remoto e abrir PR (após aprovação do usuário)**

```bash
git push -u origin feat/onboarding-stepper-hubla-events-and-ux-fixes
gh pr create --title "feat: onboarding stepper + 25 eventos hubla + ux fixes" --body "$(cat <<'EOF'
## Summary

- Reformula `/onboarding` FlowDrawer em stepper vertical de 3 passos (Produto → Eventos → Mensagens)
- Expande catálogo Hubla de 6 para 25 eventos oficiais v2, agrupados em 6 categorias (tabs)
- Migration renomeia 2 nomes divergentes em flows existentes (lead.abandoned, subscription.expiring)
- Adiciona edição de templates Meta em status não-aprovado (PATCH /admin/meta-templates/{id})
- Drawer compartilhado: click na sidebar fecha (backdrop a inset-0)
- /products: useConfirm() ao excluir (substitui confirm() nativo do browser)
- FlowDrawer fecha automaticamente após salvar

Spec: `docs/superpowers/specs/2026-05-27-onboarding-stepper-hubla-events-and-ux-fixes-design.md`
Plan: `docs/superpowers/plans/2026-05-27-onboarding-stepper-hubla-events-and-ux-fixes.md`

## Test plan

- [ ] Webhook Hubla recebe e persiste cada um dos 25 event types sem erro
- [ ] Webhook com event type desconhecido: 202 + log warning + persistido em hubla_events
- [ ] Criar flow novo via UI completando os 3 steps
- [ ] Editar flow existente: rail clicável livre, animação slide+fade
- [ ] Editar template PENDING/REJECTED: modal preenchido + salva + fecha
- [ ] Template APPROVED: botão "Editar" oculto, tooltip de cadeado
- [ ] Excluir produto mostra ConfirmDialog (não confirm() nativo)
- [ ] Click na sidebar com drawer aberto: fecha
- [ ] Migration upgrade idempotente em prod
- [ ] LeadDrawer renderiza timeline com label nova para eventos antigos (alias deprecated)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Pós-Plano

Após escrever este plano, foi feito review com fresh eyes:

### Cobertura da spec

| Spec requirement | Coberto em |
|---|---|
| Item 1: useConfirm em produtos | Task 2 |
| Item 2: Editar template (não-aprovados) | Tasks 8, 9, 10 |
| Item 3: Click fora fecha (sidebar) | Task 1 |
| Item 4: Fecha após salvar | Tasks 3 (fix mínimo) + 17 (definitivo) |
| Item 5a: Stepper UI 3 passos | Tasks 11, 12, 13, 14, 15, 16, 17 |
| Item 5b: 25 eventos Hubla backend | Tasks 4, 5 |
| Item 5c: Migration nomes divergentes | Task 6 |
| Item 5d: Frontend catalog 25 eventos | Task 7 |
| Animação slide+fade entre steps | Task 16 + integração Task 17 |
| Drag-reorder mensagens preservado | Task 15 (wrapper de StepList existente) |
| Alias deprecated p/ eventos antigos no LeadDrawer | Task 7 (`DEPRECATED_ALIASES`) |
| Validação end-to-end | Task 18 |

Nenhum gap detectado.

### Pontos resolvidos durante a escrita do plano

- ✅ Confirmado que `MetaTemplateClient.edit_template` não existia — adicionado em Task 8.
- ✅ Mapeamento de ícones Material Symbols incluído em Task 7 (24 ícones definidos).
- ✅ `@dnd-kit/*` já no projeto — Task 15 só envolve o `StepList`.
- ✅ Animação via CSS keyframes puras (Task 16) — sem nova dependência.

### Pontos que permanecem decisões de implementação razoáveis

- `aside` do Drawer continua com `left: SIDEBAR_WIDTH` (só o backdrop estende a `inset-0`). Visualmente cleaner que mover o aside também.
- Em fluxo de **edit** no step 1, alterar o produto chama `onUpdate` antes de avançar (defensivo — evita ficar com flow apontando pra outro produto sem persistir).
- Step 1 em modo edit deixa o produto **disabled** (FK relevante; não permite trocar o produto de um flow). Se isso for restritivo demais, ajustar em iteração futura.
