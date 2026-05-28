# Melhorias da página de Leads — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplicar 6 melhorias na página `/leads`: drawer com top/bottom zero + arrow_back, data+hora, link "Abrir conversa" no ChatNexo, filtros corrigidos com modal novo, datepicker custom, e tempo real via SSE com filtro server-side.

**Architecture:** 5 frentes independentes (B/E primeiro pela simplicidade; depois D, C, A). Backend FastAPI com Redis pub/sub para SSE; frontend Next.js com EventSource. TDD onde aplicável (lógica de repository, builder de URL, filtros server-side). Mudanças visuais (CSS, ícone) são verificadas com `npm run dev`.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2 async, Redis (pub/sub), Pydantic v2, pytest
- Frontend: Next.js 15 (App Router), React 19, `react-day-picker`, Tailwind

**Spec:** `docs/superpowers/specs/2026-05-28-leads-page-melhorias-design.md`

---

## Frente B — Drawer compartilhado

### Task 1: Subir z-indices e trocar X por arrow_back

**Files:**
- Modify: `apps/web/src/shared/components/Drawer.tsx`

Não há TDD aqui — é mudança visual + atributos. Validação por `npm run dev`.

- [ ] **Step 1: Editar `Drawer.tsx`**

Em `apps/web/src/shared/components/Drawer.tsx`, alterar:

1. Backdrop (linha ~38): substituir `z-40` por `z-60`.
2. Painel (linha ~50): substituir `z-50` por `z-70`.
3. Botão fechar (linha ~63): substituir `close` por `arrow_back`.
4. Botão fechar (linha ~61): substituir `aria-label="Fechar"` por `aria-label="Voltar"`.

Trecho final do header deve ficar:

```tsx
<button
  type="button"
  onClick={onClose}
  className="rounded-md p-2 text-on-surface-variant hover:bg-surface-container-high"
  aria-label="Voltar"
>
  <span className="material-symbols-outlined">arrow_back</span>
</button>
```

E os className dos elementos `fixed`:

```tsx
// Backdrop
className={`fixed inset-0 z-60 cursor-pointer bg-black/40 transition-opacity duration-200 ${...}`}

// Painel
className={`fixed inset-y-0 right-0 z-70 flex flex-col bg-surface-container shadow-2xl transition-transform duration-300 ease-out ${...}`}
```

- [ ] **Step 2: Validar visualmente**

Rodar `cd apps/web && npm run dev`. Abrir `/leads`, clicar num lead. Confirmar:
- Drawer cobre top até bottom encostado na sidebar.
- TopBar não aparece "por cima".
- Botão de fechar agora é seta esquerda.
- ESC fecha. Clique no backdrop fecha.
- Repetir em `/products` e `/onboarding` (qualquer flow) — mesmo comportamento.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shared/components/Drawer.tsx
git commit -m "fix(drawer): z-index e arrow_back no botão de fechar"
```

---

## Frente E — Data + hora na lista

### Task 2: formatDateTime na coluna "Último evento"

**Files:**
- Modify: `apps/web/src/app/(admin)/leads/page.tsx:26-28,327-329`

- [ ] **Step 1: Substituir `formatDate` por `formatDateTime`**

Em `page.tsx`, substituir a função na linha 26-28:

```ts
function formatDateTime(d: string): string {
  return new Date(d).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
```

Trocar a única chamada na linha 328 de `formatDate(lead.last_event_at)` para `formatDateTime(lead.last_event_at)`.

- [ ] **Step 2: Validar**

`npm run dev`, `/leads`. Confirmar que coluna "Último evento" exibe `27/05/2026 14:32`.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/app/\(admin\)/leads/page.tsx
git commit -m "feat(leads): exibir hora além da data na coluna Último evento"
```

---

## Frente D — Link "Abrir conversa no ChatNexo"

### Task 3: LeadRepository devolve chatnexo_conversation_url no find_by_id

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/lead_repo.py`
- Modify: `apps/api/src/shared/domain/entities/lead.py` (adicionar campo)
- Test: `apps/api/tests/integration/test_lead_repo.py`

- [ ] **Step 1: Adicionar campo opcional na entity Lead**

Em `apps/api/src/shared/domain/entities/lead.py`, adicionar ao final dos campos do dataclass:

```python
chatnexo_conversation_url: str | None = None
```

- [ ] **Step 2: Escrever o teste de integração que falha**

Criar/editar `apps/api/tests/integration/test_lead_repo.py` adicionando:

```python
import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from shared.adapters.db.models import (
    AccountModel, ContactModel, ConversationModel, LeadModel
)
from shared.adapters.db.repositories.lead_repo import SqlLeadRepository


@pytest.mark.asyncio
async def test_find_by_id_includes_chatnexo_url_when_conversation_exists(
    db_session: AsyncSession,
):
    # Setup: account com chatnexo config
    account = AccountModel(
        id=uuid4(),
        name="Test",
        settings={
            "integration": {
                "chatnexo_base_url": "https://chatnexo.com.br",
                "chatnexo_account_id": 5,
                "chatnexo_inbox_id": 111,
            }
        },
    )
    db_session.add(account)
    await db_session.flush()

    # Contact + conversation no chatnexo
    contact = ContactModel(
        id=uuid4(), account_id=account.id, phone="+5511999999999", name="X"
    )
    conv = ConversationModel(
        id=uuid4(),
        account_id=account.id,
        contact_id=contact.id,
        chatnexo_conversation_id=16401,
        status="open",
    )
    db_session.add_all([contact, conv])
    await db_session.flush()

    # Lead
    lead = LeadModel(
        id=uuid4(),
        account_id=account.id,
        hubla_subscription_id="sub_1",
        contact_id=contact.id,
        payer_phone="+5511999999999",
        last_event_type="subscription.activated",
    )
    db_session.add(lead)
    await db_session.commit()

    repo = SqlLeadRepository(session=db_session)
    found = await repo.find_by_id(lead.id, account.id)

    assert found is not None
    assert found.chatnexo_conversation_url == (
        "https://chatnexo.com.br/app/accounts/5/inbox/111/conversations/16401"
    )


@pytest.mark.asyncio
async def test_find_by_id_url_is_none_when_no_conversation(db_session: AsyncSession):
    account = AccountModel(id=uuid4(), name="T", settings={})
    db_session.add(account)
    await db_session.flush()

    lead = LeadModel(
        id=uuid4(),
        account_id=account.id,
        hubla_subscription_id="sub_2",
        contact_id=None,
        payer_phone="",
        last_event_type="lead.abandoned",
    )
    db_session.add(lead)
    await db_session.commit()

    repo = SqlLeadRepository(session=db_session)
    found = await repo.find_by_id(lead.id, account.id)

    assert found is not None
    assert found.chatnexo_conversation_url is None
```

- [ ] **Step 3: Rodar e ver falhar**

```bash
cd apps/api && uv run pytest tests/integration/test_lead_repo.py::test_find_by_id_includes_chatnexo_url_when_conversation_exists -v
```

Expected: FAIL com `chatnexo_conversation_url is None` (porque o repo ainda não preenche).

- [ ] **Step 4: Implementar JOIN + builder de URL no `find_by_id`**

Em `lead_repo.py`, modificar `find_by_id`:

```python
async def find_by_id(self, lead_id: UUID, account_id: UUID) -> Lead | None:
    from shared.adapters.db.models import (
        AccountModel, ConversationModel
    )

    stmt = select(LeadModel).where(
        LeadModel.id == lead_id,
        LeadModel.account_id == account_id,
    )
    res = await self.session.execute(stmt)
    m = res.scalar_one_or_none()
    if m is None:
        return None

    entity = _to_lead_entity(m)

    # Carrega conversation mais recente (se houver contact)
    if m.contact_id is not None:
        conv_stmt = (
            select(ConversationModel)
            .where(
                ConversationModel.account_id == account_id,
                ConversationModel.contact_id == m.contact_id,
            )
            .order_by(ConversationModel.created_at.desc())
            .limit(1)
        )
        conv_res = await self.session.execute(conv_stmt)
        conv = conv_res.scalar_one_or_none()

        if conv is not None:
            acc_res = await self.session.execute(
                select(AccountModel).where(AccountModel.id == account_id)
            )
            acc = acc_res.scalar_one_or_none()
            settings = (acc.settings or {}) if acc else {}
            integration = settings.get("integration") or {}
            base = integration.get("chatnexo_base_url")
            acc_id = integration.get("chatnexo_account_id")
            inbox_id = integration.get("chatnexo_inbox_id")
            if base and acc_id and inbox_id:
                entity = replace(
                    entity,
                    chatnexo_conversation_url=(
                        f"{base.rstrip('/')}/app/accounts/{acc_id}"
                        f"/inbox/{inbox_id}/conversations/{conv.chatnexo_conversation_id}"
                    ),
                )

    return entity
```

Adicionar no topo do arquivo `from dataclasses import replace` se ainda não houver.

- [ ] **Step 5: Rodar testes e ver passar**

```bash
cd apps/api && uv run pytest tests/integration/test_lead_repo.py -v
```

Expected: PASS em ambos.

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/lead_repo.py apps/api/src/shared/domain/entities/lead.py apps/api/tests/integration/test_lead_repo.py
git commit -m "feat(leads-repo): find_by_id devolve chatnexo_conversation_url"
```

---

### Task 4: Exposição da URL no LeadDetailResponse

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/leads.py`
- Test: `apps/api/tests/integration/test_admin_leads_router.py`

- [ ] **Step 1: Teste de endpoint que verifica o campo no detail**

Adicionar em `tests/integration/test_admin_leads_router.py` (criar se não existir):

```python
@pytest.mark.asyncio
async def test_get_lead_returns_chatnexo_conversation_url(
    client, admin_token, account_with_chatnexo, lead_with_conversation
):
    response = await client.get(
        f"/admin/leads/{lead_with_conversation.id}",
        cookies={"admin_token": admin_token},
    )
    assert response.status_code == 200
    body = response.json()
    assert "chatnexo_conversation_url" in body
    assert body["chatnexo_conversation_url"] == (
        "https://chatnexo.com.br/app/accounts/5/inbox/111/conversations/16401"
    )
```

Se as fixtures `account_with_chatnexo` e `lead_with_conversation` ainda não existem em `conftest.py`, criá-las espelhando o setup da Task 3 Step 2.

- [ ] **Step 2: Rodar e ver falhar**

```bash
uv run pytest tests/integration/test_admin_leads_router.py::test_get_lead_returns_chatnexo_conversation_url -v
```

Expected: FAIL (campo ausente no schema).

- [ ] **Step 3: Adicionar campo no schema Pydantic**

Em `apps/api/src/interface/http/routers/admin/leads.py`, em `LeadResponse` (linha 21):

```python
class LeadResponse(BaseModel):
    # ... campos existentes ...
    last_event_type: str
    chatnexo_conversation_url: str | None = None  # <-- novo
```

E em `_to_response` (linha 85), adicionar:

```python
def _to_response(m: Lead) -> LeadResponse:
    return LeadResponse(
        # ... campos existentes ...
        last_event_type=m.last_event_type,
        chatnexo_conversation_url=m.chatnexo_conversation_url,
    )
```

- [ ] **Step 4: Rodar e ver passar**

```bash
uv run pytest tests/integration/test_admin_leads_router.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/interface/http/routers/admin/leads.py apps/api/tests/integration/test_admin_leads_router.py
git commit -m "feat(leads-api): expor chatnexo_conversation_url no detail"
```

---

### Task 5: Frontend — botão "Abrir conversa no ChatNexo"

**Files:**
- Modify: `apps/web/src/features/leads/types.ts`
- Modify: `apps/web/src/features/leads/components/LeadDrawer.tsx`

- [ ] **Step 1: Adicionar campo no tipo `LeadDetail`**

Em `apps/web/src/features/leads/types.ts`, no tipo `LeadDetail`:

```ts
export interface LeadDetail extends Lead {
  events: LeadEvent[];
  enrollments: FollowupEnrollment[];
  chatnexo_conversation_url: string | null;
}
```

- [ ] **Step 2: Adicionar botão "Abrir conversa" no LeadDrawer**

Em `LeadDrawer.tsx`, após o card header (após a linha 117), adicionar:

```tsx
{/* CTA: abrir conversa no ChatNexo */}
{detail?.chatnexo_conversation_url ? (
  <a
    href={detail.chatnexo_conversation_url}
    target="_blank"
    rel="noopener noreferrer"
    className="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 transition-colors hover:bg-surface-container"
  >
    <span className="flex items-center gap-2 text-sm font-medium text-on-surface">
      <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
        chat
      </span>
      Abrir conversa no ChatNexo
    </span>
    <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "16px" }}>
      open_in_new
    </span>
  </a>
) : (
  <div
    className="flex cursor-not-allowed items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-4 py-3 text-sm text-on-surface-variant/60"
    title="Aguardando primeira mensagem"
  >
    <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
      chat
    </span>
    Aguardando primeira mensagem
  </div>
)}
```

- [ ] **Step 3: Validar visualmente**

`npm run dev`, abrir `/leads`, clicar num lead que tem mensagem trocada. Confirmar:
- Botão aparece.
- Clique abre em nova aba a URL `https://chatnexo.com.br/app/accounts/.../conversations/...`.
- Para lead sem conversation: bloco desabilitado com texto "Aguardando primeira mensagem".

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/leads/
git commit -m "feat(leads): botão Abrir conversa no ChatNexo no drawer"
```

---

## Frente C — Filtros: fixes + modal novo

### Task 6: Investigar e corrigir bugs dos filtros existentes

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/lead_repo.py` (método `paginate`)
- Modify: `apps/web/src/app/(admin)/leads/page.tsx` (envio de date_from/date_to)
- Test: `apps/api/tests/integration/test_lead_repo.py`

- [ ] **Step 1: Testes de filtro no repo**

Adicionar em `test_lead_repo.py`:

```python
@pytest.mark.asyncio
async def test_paginate_filters_by_product_id(db_session, seed_leads):
    repo = SqlLeadRepository(session=db_session)
    items, total = await repo.paginate(
        seed_leads.account_id,
        product_id="prod_abc",
        status=None, utm_source=None, date_from=None, date_to=None,
        page=1, page_size=10,
    )
    assert total > 0
    assert all(l.hubla_product_id == "prod_abc" for l in items)


@pytest.mark.asyncio
async def test_paginate_filters_utm_source_case_insensitive(db_session, seed_leads):
    repo = SqlLeadRepository(session=db_session)
    items, _ = await repo.paginate(
        seed_leads.account_id,
        product_id=None, status=None, utm_source="FACEBOOK",
        date_from=None, date_to=None, page=1, page_size=10,
    )
    assert all((l.utm_source or "").lower() == "facebook" for l in items)


@pytest.mark.asyncio
async def test_paginate_filters_by_date_range(db_session, seed_leads):
    from datetime import datetime, timezone
    repo = SqlLeadRepository(session=db_session)
    df = datetime(2026, 5, 27, 0, 0, 0, tzinfo=timezone.utc)
    dt = datetime(2026, 5, 27, 23, 59, 59, tzinfo=timezone.utc)
    items, _ = await repo.paginate(
        seed_leads.account_id,
        product_id=None, status=None, utm_source=None,
        date_from=df, date_to=dt, page=1, page_size=10,
    )
    assert all(df <= l.last_event_at <= dt for l in items)
```

Adicionar fixture `seed_leads` no `conftest.py` que cria 5+ leads com produtos variados, UTMs variados e datas variadas.

- [ ] **Step 2: Rodar e ver quais falham**

```bash
uv run pytest tests/integration/test_lead_repo.py -k "paginate_filters" -v
```

Anotar quais passam e quais falham.

- [ ] **Step 3: Inspecionar `paginate` atual**

Ler `lead_repo.py:169-202` (método `paginate`). Verificar:
- `product_id`: compara com `LeadModel.hubla_product_id`? Confirmar.
- `utm_source`: usa `ILIKE` ou `==`?
- `date_from/date_to`: campo correto (`last_event_at`)?

- [ ] **Step 4: Corrigir o que estiver errado**

Padrão alvo do método (substitui o existente):

```python
async def paginate(
    self,
    account_id: UUID,
    *,
    product_id: str | None,
    status: str | None,
    utm_source: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
    page: int,
    page_size: int,
) -> tuple[list[Lead], int]:
    stmt = select(LeadModel).where(LeadModel.account_id == account_id)

    if product_id:
        stmt = stmt.where(LeadModel.hubla_product_id == product_id)
    if status:
        stmt = stmt.where(LeadModel.subscription_status == status)
    if utm_source:
        stmt = stmt.where(LeadModel.utm_source.ilike(f"%{utm_source}%"))
    if date_from:
        stmt = stmt.where(LeadModel.last_event_at >= date_from)
    if date_to:
        stmt = stmt.where(LeadModel.last_event_at <= date_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await self.session.execute(count_stmt)).scalar_one()

    stmt = (
        stmt.order_by(LeadModel.last_event_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await self.session.execute(stmt)).scalars().all()
    return [_to_lead_entity(r) for r in rows], total
```

- [ ] **Step 5: Rodar todos os testes do repo e ver passar**

```bash
uv run pytest tests/integration/test_lead_repo.py -v
```

Expected: PASS em todos.

- [ ] **Step 6: Fix date envio no frontend (timezone BR)**

Em `apps/web/src/app/(admin)/leads/page.tsx`, substituir `toIsoStartOfDay` e `toIsoEndOfDay`:

```ts
function toIsoStartOfDay(dateStr: string): string | undefined {
  if (!dateStr) return undefined;
  // Mantém fuso BR (-03:00) — envia como UTC equivalente
  return new Date(dateStr + "T00:00:00-03:00").toISOString();
}

function toIsoEndOfDay(dateStr: string): string | undefined {
  if (!dateStr) return undefined;
  return new Date(dateStr + "T23:59:59.999-03:00").toISOString();
}
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/lead_repo.py apps/api/tests/integration/ apps/web/src/app/\(admin\)/leads/page.tsx
git commit -m "fix(leads): filtros de produto/UTM/data funcionando server-side"
```

---

### Task 7: Endpoint de sugestão de UTM sources

**Files:**
- Modify: `apps/api/src/shared/adapters/db/repositories/lead_repo.py`
- Modify: `apps/api/src/interface/http/routers/admin/leads.py`
- Test: `apps/api/tests/integration/test_admin_leads_router.py`

- [ ] **Step 1: Teste de endpoint**

```python
@pytest.mark.asyncio
async def test_utm_sources_suggest_returns_top_distinct(
    client, admin_token, seed_leads_with_utms
):
    res = await client.get(
        "/admin/leads/utm-sources/suggest",
        cookies={"admin_token": admin_token},
    )
    assert res.status_code == 200
    body = res.json()
    assert isinstance(body, list)
    assert len(body) <= 10
    assert all(isinstance(v, str) for v in body)


@pytest.mark.asyncio
async def test_utm_sources_suggest_filters_by_q(
    client, admin_token, seed_leads_with_utms,
):
    res = await client.get(
        "/admin/leads/utm-sources/suggest?q=face",
        cookies={"admin_token": admin_token},
    )
    assert res.status_code == 200
    body = res.json()
    assert all("face" in v.lower() for v in body)
```

Fixture `seed_leads_with_utms` cria leads com `utm_source` em ["facebook", "google", "instagram", "tiktok", "Facebook Ads"].

- [ ] **Step 2: Rodar e ver falhar (404)**

```bash
uv run pytest tests/integration/test_admin_leads_router.py -k "utm_sources_suggest" -v
```

- [ ] **Step 3: Repository method**

Em `lead_repo.py`:

```python
async def suggest_utm_sources(
    self, account_id: UUID, q: str | None, limit: int = 10
) -> list[str]:
    stmt = (
        select(LeadModel.utm_source, func.count().label("c"))
        .where(
            LeadModel.account_id == account_id,
            LeadModel.utm_source.isnot(None),
        )
    )
    if q:
        stmt = stmt.where(LeadModel.utm_source.ilike(f"%{q}%"))
    stmt = (
        stmt.group_by(LeadModel.utm_source)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = (await self.session.execute(stmt)).all()
    return [r[0] for r in rows if r[0]]
```

- [ ] **Step 4: Endpoint**

Em `routers/admin/leads.py`:

```python
@router.get("/leads/utm-sources/suggest", response_model=list[str])
async def suggest_utm_sources(
    q: str | None = Query(default=None),
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> list[str]:
    async with session_scope() as session:
        account_uuid = await get_default_account_uuid(session)
        repo = SqlLeadRepository(session=session)
        return await repo.suggest_utm_sources(account_uuid, q=q)
```

- [ ] **Step 5: Rodar e ver passar**

```bash
uv run pytest tests/integration/test_admin_leads_router.py -k "utm_sources_suggest" -v
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/adapters/db/repositories/lead_repo.py apps/api/src/interface/http/routers/admin/leads.py apps/api/tests/integration/test_admin_leads_router.py
git commit -m "feat(leads-api): GET /admin/leads/utm-sources/suggest"
```

---

### Task 8: Instalar `react-day-picker`

**Files:**
- Modify: `apps/web/package.json`

- [ ] **Step 1: Instalar**

```bash
cd apps/web && npm install react-day-picker date-fns
```

- [ ] **Step 2: Verificar versão**

`grep react-day-picker apps/web/package.json` — espera-se `^9.x`.

- [ ] **Step 3: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json
git commit -m "chore(web): instalar react-day-picker"
```

---

### Task 9: Componente DatePicker reutilizável

**Files:**
- Create: `apps/web/src/shared/components/DatePicker.tsx`

Sem testes unitários — é componente visual. Validação por uso no modal de filtros (Task 11).

- [ ] **Step 1: Criar arquivo `DatePicker.tsx`**

```tsx
"use client";

import { useState, useRef, useEffect } from "react";
import { DayPicker, type DateRange } from "react-day-picker";
import { ptBR } from "date-fns/locale";
import "react-day-picker/dist/style.css";

interface Props {
  value: DateRange | undefined;
  onChange: (range: DateRange | undefined) => void;
  placeholder?: string;
}

function formatRange(r: DateRange | undefined): string {
  if (!r?.from) return "";
  const f = r.from.toLocaleDateString("pt-BR");
  if (!r.to) return f;
  const t = r.to.toLocaleDateString("pt-BR");
  return `${f} → ${t}`;
}

function preset(name: "today" | "7d" | "30d" | "this-month"): DateRange {
  const now = new Date();
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  if (name === "today") return { from: start, to: start };
  if (name === "7d") {
    const from = new Date(start);
    from.setDate(from.getDate() - 6);
    return { from, to: start };
  }
  if (name === "30d") {
    const from = new Date(start);
    from.setDate(from.getDate() - 29);
    return { from, to: start };
  }
  // this-month
  const from = new Date(now.getFullYear(), now.getMonth(), 1);
  return { from, to: start };
}

export function DatePicker({ value, onChange, placeholder = "Selecionar período" }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2 text-left text-sm text-on-surface"
      >
        <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: "18px" }}>
          calendar_month
        </span>
        <span className={value?.from ? "text-on-surface" : "text-on-surface-variant"}>
          {formatRange(value) || placeholder}
        </span>
      </button>

      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 rounded-xl border border-outline-variant bg-surface-container p-3 shadow-xl">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {[
              { label: "Hoje", key: "today" },
              { label: "7 dias", key: "7d" },
              { label: "30 dias", key: "30d" },
              { label: "Este mês", key: "this-month" },
            ].map((p) => (
              <button
                key={p.key}
                type="button"
                onClick={() => onChange(preset(p.key as never))}
                className="rounded-full border border-outline-variant px-2.5 py-1 text-xs text-on-surface hover:bg-surface-container-high"
              >
                {p.label}
              </button>
            ))}
          </div>
          <DayPicker
            mode="range"
            selected={value}
            onSelect={onChange}
            locale={ptBR}
            weekStartsOn={0}
            className="text-sm"
          />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: sem erros.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/shared/components/DatePicker.tsx
git commit -m "feat(shared): DatePicker reutilizável com range e atalhos"
```

---

### Task 10: Componente Modal centralizado

**Files:**
- Create: `apps/web/src/shared/components/Modal.tsx`

- [ ] **Step 1: Criar Modal.tsx**

```tsx
"use client";

import { useEffect } from "react";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: "sm" | "md" | "lg";
}

const SIZE: Record<NonNullable<Props["size"]>, string> = {
  sm: "max-w-md",
  md: "max-w-2xl",
  lg: "max-w-4xl",
};

export function Modal({ open, onClose, title, children, footer, size = "md" }: Props) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  return (
    <>
      <div
        onClick={onClose}
        className={`fixed inset-0 z-60 cursor-pointer bg-black/40 transition-opacity duration-200 ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`pointer-events-none fixed inset-0 z-70 flex items-center justify-center p-4 transition-all duration-200 ${
          open ? "opacity-100" : "opacity-0"
        }`}
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className={`pointer-events-auto w-full ${SIZE[size]} rounded-2xl border border-outline-variant bg-surface-container shadow-2xl transition-transform duration-200 ${
            open ? "scale-100" : "scale-95"
          }`}
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
          <div className="px-6 py-5">{children}</div>
          {footer && (
            <footer className="border-t border-outline-variant px-6 py-4">{footer}</footer>
          )}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/shared/components/Modal.tsx
git commit -m "feat(shared): componente Modal centralizado"
```

---

### Task 11: LeadFiltersModal

**Files:**
- Create: `apps/web/src/features/leads/components/LeadFiltersModal.tsx`
- Modify: `apps/web/src/lib/api.ts` (adicionar `suggestUtmSources`)

- [ ] **Step 1: Função de API**

Em `apps/web/src/lib/api.ts`, adicionar:

```ts
export async function suggestUtmSources(q?: string): Promise<string[]> {
  const qs = q ? `?q=${encodeURIComponent(q)}` : "";
  return apiFetch(`/admin/leads/utm-sources/suggest${qs}`);
}
```

- [ ] **Step 2: Criar `LeadFiltersModal.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import type { DateRange } from "react-day-picker";

import { Modal } from "@/shared/components/Modal";
import { DatePicker } from "@/shared/components/DatePicker";
import { useProducts } from "@/features/products/hooks/useProducts";
import { suggestUtmSources } from "@/lib/api";
import { getLeadStatusBadge } from "../lib/statusBadges";
import type { LeadFilters } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  initial: LeadFilters;
  onApply: (filters: LeadFilters) => void;
}

const STATUS_OPTIONS = [
  { value: "", label: "Todos" },
  { value: "active", label: "Ativado" },
  { value: "inactive", label: "Inativo" },
  { value: "abandoned", label: "Abandonado" },
  { value: "refunded", label: "Reembolsado" },
  { value: "cancelled", label: "Cancelado" },
];

function toIso(d: Date | undefined, end = false): string | undefined {
  if (!d) return undefined;
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const suffix = end ? "T23:59:59.999-03:00" : "T00:00:00-03:00";
  return new Date(`${yyyy}-${mm}-${dd}${suffix}`).toISOString();
}

function fromIso(s: string | undefined): Date | undefined {
  return s ? new Date(s) : undefined;
}

export function LeadFiltersModal({ open, onClose, initial, onApply }: Props) {
  const { products } = useProducts();
  const [productId, setProductId] = useState<string>(initial.product_id ?? "");
  const [statusValue, setStatusValue] = useState<string>(initial.status ?? "");
  const [range, setRange] = useState<DateRange | undefined>({
    from: fromIso(initial.date_from),
    to: fromIso(initial.date_to),
  });
  const [utm, setUtm] = useState<string>(initial.utm_source ?? "");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);

  useEffect(() => {
    if (!open) return;
    setProductId(initial.product_id ?? "");
    setStatusValue(initial.status ?? "");
    setRange({
      from: fromIso(initial.date_from),
      to: fromIso(initial.date_to),
    });
    setUtm(initial.utm_source ?? "");
  }, [open, initial]);

  useEffect(() => {
    if (!open) return;
    suggestUtmSources(utm || undefined)
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [open, utm]);

  const apply = () => {
    onApply({
      ...initial,
      product_id: productId || undefined,
      status: statusValue || undefined,
      date_from: toIso(range?.from),
      date_to: toIso(range?.to, true),
      utm_source: utm || undefined,
      page: 1,
    });
    onClose();
  };

  const clearAll = () => {
    setProductId("");
    setStatusValue("");
    setRange(undefined);
    setUtm("");
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Filtros"
      size="md"
      footer={
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={clearAll}
            className="text-sm text-on-surface-variant hover:underline"
          >
            Limpar tudo
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-outline-variant px-4 py-2 text-sm text-on-surface hover:bg-surface-container-high"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={apply}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:opacity-90"
            >
              Aplicar filtros
            </button>
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        {/* Produto */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Produto
          </label>
          <select
            value={productId}
            onChange={(e) => setProductId(e.target.value)}
            className="field-select w-full"
          >
            <option value="">Todos os produtos</option>
            {products.map((p) => (
              <option key={p.id} value={p.hubla_id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>

        {/* Status */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Status
          </label>
          <div className="flex flex-wrap gap-2">
            {STATUS_OPTIONS.map((opt) => {
              const badge = opt.value
                ? getLeadStatusBadge(opt.value)
                : { className: "border-outline-variant text-on-surface" };
              const selected = statusValue === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setStatusValue(opt.value)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    selected ? badge.className : "border-outline-variant text-on-surface-variant hover:bg-surface-container-high"
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Período */}
        <div>
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            Período
          </label>
          <DatePicker value={range} onChange={setRange} />
        </div>

        {/* UTM */}
        <div className="relative">
          <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-on-surface-variant">
            UTM source
          </label>
          <input
            type="text"
            value={utm}
            onChange={(e) => {
              setUtm(e.target.value);
              setShowSuggestions(true);
            }}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 150)}
            placeholder="Ex.: facebook"
            className="field-input w-full"
          />
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute left-0 right-0 z-10 mt-1 max-h-40 overflow-auto rounded-lg border border-outline-variant bg-surface-container-low shadow-lg">
              {suggestions.map((s) => (
                <li
                  key={s}
                  onMouseDown={() => {
                    setUtm(s);
                    setShowSuggestions(false);
                  }}
                  className="cursor-pointer px-3 py-1.5 text-sm hover:bg-surface-container"
                >
                  {s}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Modal>
  );
}
```

- [ ] **Step 3: Type-check**

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/leads/components/LeadFiltersModal.tsx apps/web/src/lib/api.ts
git commit -m "feat(leads): LeadFiltersModal centralizado com DatePicker e sugestão UTM"
```

---

### Task 12: Integrar modal na page de leads (substituir barra inline)

**Files:**
- Modify: `apps/web/src/app/(admin)/leads/page.tsx`

- [ ] **Step 1: Substituir a barra de filtros por botão + chips**

Em `page.tsx`, remover o bloco inteiro de filtros inline (linhas ~140-222) e substituir por:

```tsx
{/* Filter trigger + chips */}
<div className="flex items-center gap-3">
  <button
    type="button"
    onClick={() => setFiltersOpen(true)}
    className="flex items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2 text-sm text-on-surface hover:bg-surface-container"
  >
    <span className="material-symbols-outlined" style={{ fontSize: "18px" }}>
      filter_list
    </span>
    Filtros
    {activeFilterCount > 0 && (
      <span className="rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-on-primary">
        {activeFilterCount}
      </span>
    )}
  </button>

  {/* Chips */}
  <div className="flex flex-wrap gap-1.5">
    {filters.product_id && (
      <FilterChip
        label={`Produto: ${products.find((p) => p.hubla_id === filters.product_id)?.name ?? filters.product_id}`}
        onRemove={() => updateFilter({ product_id: undefined })}
      />
    )}
    {filters.status && (
      <FilterChip
        label={`Status: ${STATUS_OPTIONS.find((s) => s.value === filters.status)?.label ?? filters.status}`}
        onRemove={() => updateFilter({ status: undefined })}
      />
    )}
    {(filters.date_from || filters.date_to) && (
      <FilterChip
        label={`Período: ${filters.date_from ? new Date(filters.date_from).toLocaleDateString("pt-BR") : "..."} → ${filters.date_to ? new Date(filters.date_to).toLocaleDateString("pt-BR") : "..."}`}
        onRemove={() => updateFilter({ date_from: undefined, date_to: undefined })}
      />
    )}
    {filters.utm_source && (
      <FilterChip
        label={`UTM: ${filters.utm_source}`}
        onRemove={() => updateFilter({ utm_source: undefined })}
      />
    )}
  </div>

  {hasActiveFilters && (
    <button
      onClick={clearFilters}
      className="ml-auto text-xs text-primary hover:underline"
    >
      Limpar todos
    </button>
  )}
</div>
```

Adicionar antes do `return`:

```tsx
const [filtersOpen, setFiltersOpen] = useState(false);
const activeFilterCount = [
  filters.product_id, filters.status, filters.utm_source,
  filters.date_from, filters.date_to,
].filter(Boolean).length;
```

E o sub-componente `FilterChip` (ao final do arquivo, fora do default export):

```tsx
function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-outline-variant bg-surface-container-low px-2.5 py-0.5 text-xs text-on-surface">
      {label}
      <button onClick={onRemove} className="text-on-surface-variant hover:text-on-surface" aria-label="Remover filtro">
        <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>close</span>
      </button>
    </span>
  );
}
```

- [ ] **Step 2: Renderizar o `LeadFiltersModal`**

Junto com o `<LeadDrawer ... />`, ao final do return:

```tsx
<LeadFiltersModal
  open={filtersOpen}
  onClose={() => setFiltersOpen(false)}
  initial={filters}
  onApply={(f) => setFilters(f)}
/>
```

E remover imports não usados (`utmInput`, `dateFromInput`, `dateToInput` e suas funções).

- [ ] **Step 3: Validar visualmente**

`npm run dev`, `/leads`:
- Clica em "Filtros" → modal abre centralizado.
- Aplica produto + status → chips aparecem ao lado do botão.
- Remove chip individual → atualiza lista.
- Datepicker abre popover ao clicar.
- UTM source mostra autocomplete enquanto digita.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/\(admin\)/leads/page.tsx
git commit -m "feat(leads): trocar barra de filtros por botão + modal centralizado + chips"
```

---

## Frente A — Real-time via SSE

### Task 13: Helper de pub/sub no Redis

**Files:**
- Create: `apps/api/src/shared/adapters/redis/leads_pubsub.py`
- Test: `apps/api/tests/integration/test_leads_pubsub.py`

- [ ] **Step 1: Teste de pub/sub**

```python
import asyncio
import json
import pytest
from uuid import uuid4

from shared.adapters.redis.client import get_redis
from shared.adapters.redis.leads_pubsub import LeadsPubSub


@pytest.mark.asyncio
async def test_publish_and_subscribe_roundtrip():
    redis = get_redis()
    account_id = uuid4()
    bus = LeadsPubSub(redis)

    received = []
    async def consume():
        async for env in bus.subscribe(account_id):
            received.append(env)
            break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.1)  # esperar subscribe
    await bus.publish(account_id, {"type": "lead.upserted", "lead": {"id": "x"}})
    await asyncio.wait_for(task, timeout=2.0)

    assert received[0]["type"] == "lead.upserted"
    assert received[0]["lead"]["id"] == "x"
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
uv run pytest tests/integration/test_leads_pubsub.py -v
```

- [ ] **Step 3: Implementar `LeadsPubSub`**

```python
# apps/api/src/shared/adapters/redis/leads_pubsub.py
from __future__ import annotations

import json
from typing import Any, AsyncIterator
from uuid import UUID

from redis.asyncio import Redis as AsyncRedis
from redis import Redis as SyncRedis

import structlog

log = structlog.get_logger(__name__)


def _channel(account_id: UUID) -> str:
    return f"leads:events:{account_id}"


class LeadsPubSub:
    def __init__(self, redis: SyncRedis) -> None:
        # redis-py sync client compartilhado; abrimos cliente async pra subscribe
        self._sync = redis
        self._async_url = redis.connection_pool.connection_kwargs
        # Reaproveita as creds via from_url:
        from shared.config.settings import get_settings
        self._async = AsyncRedis.from_url(get_settings().redis_url, decode_responses=True)

    async def publish(self, account_id: UUID, envelope: dict[str, Any]) -> None:
        try:
            await self._async.publish(_channel(account_id), json.dumps(envelope, default=str))
        except Exception as e:
            log.warning("leads_pubsub.publish_failed", error=str(e))

    async def subscribe(self, account_id: UUID) -> AsyncIterator[dict[str, Any]]:
        pubsub = self._async.pubsub()
        await pubsub.subscribe(_channel(account_id))
        try:
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                data = message.get("data")
                if not data:
                    continue
                try:
                    yield json.loads(data)
                except json.JSONDecodeError:
                    continue
        finally:
            await pubsub.unsubscribe(_channel(account_id))
            await pubsub.close()
```

- [ ] **Step 4: Rodar e ver passar**

```bash
uv run pytest tests/integration/test_leads_pubsub.py -v
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/shared/adapters/redis/leads_pubsub.py apps/api/tests/integration/test_leads_pubsub.py
git commit -m "feat(redis): LeadsPubSub helper pra leads events"
```

---

### Task 14: Publisher no HublaEventHandler

**Files:**
- Modify: `apps/api/src/shared/application/hubla_event_handler.py`
- Test: `apps/api/tests/integration/test_hubla_event_handler.py`

- [ ] **Step 1: Teste de publish após upsert**

```python
@pytest.mark.asyncio
async def test_handler_publishes_lead_upserted_envelope(
    db_session, sample_hubla_payload, fake_leads_pubsub
):
    handler = HublaEventHandler(
        session=db_session,
        leads_pubsub=fake_leads_pubsub,
        # ... outras deps existentes ...
    )
    await handler.handle(sample_hubla_payload)

    assert len(fake_leads_pubsub.published) == 1
    env = fake_leads_pubsub.published[0]
    assert env["type"] == "lead.upserted"
    assert env["lead"]["hubla_subscription_id"] == sample_hubla_payload["subscription_id"]
    assert "event" in env  # também carrega o HublaEvent inserido
    assert "is_new" in env
```

`fake_leads_pubsub` é fixture com `.published: list` e método `async publish(account_id, env)` que dá append.

- [ ] **Step 2: Rodar e ver falhar**

```bash
uv run pytest tests/integration/test_hubla_event_handler.py -k publishes -v
```

- [ ] **Step 3: Injetar `leads_pubsub` no `HublaEventHandler` e publicar**

Em `hubla_event_handler.py`:

1. Adicionar `leads_pubsub` no `__init__` (opcional para retro-compat).
2. Após o `commit` do upsert + insert do `hubla_events`, montar o envelope e publicar.

```python
# trecho conceitual; adaptar à estrutura atual do handler

is_new = lead.created_at == lead.updated_at
envelope = {
    "type": "lead.upserted",
    "is_new": is_new,
    "lead": _lead_to_summary_dict(lead),
    "event": _hubla_event_to_dict(hubla_event),
}
if self._leads_pubsub:
    await self._leads_pubsub.publish(account_id, envelope)
```

Os helpers `_lead_to_summary_dict` e `_hubla_event_to_dict` devolvem dicts no MESMO shape do `LeadResponse` / `HublaEventResponse` do router (chaves snake_case, UUID/datetime serializados como string).

- [ ] **Step 4: Onde construir o handler — wire-up**

Em `apps/api/src/interface/worker/handlers/hubla_event.py`, no factory do handler, criar uma instância de `LeadsPubSub(get_redis())` e passar pro construtor.

- [ ] **Step 5: Rodar e ver passar**

```bash
uv run pytest tests/integration/test_hubla_event_handler.py -v
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/application/hubla_event_handler.py apps/api/src/interface/worker/handlers/hubla_event.py apps/api/tests/integration/test_hubla_event_handler.py
git commit -m "feat(hubla): publica lead.upserted no Redis após upsert"
```

---

### Task 15: Publisher no DispatchOnboardingStep

**Files:**
- Modify: `apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py`
- Test: `apps/api/tests/integration/test_dispatch_onboarding_step.py`

- [ ] **Step 1: Teste do publish**

```python
@pytest.mark.asyncio
async def test_dispatch_publishes_enrollment_updated(
    db_session, seed_pending_step, fake_leads_pubsub
):
    use_case = DispatchOnboardingStep(
        enrollment_repo=...,
        contact_repo=...,
        chatnexo=fake_chatnexo,
        conversation_history=fake_history,
        meta_template_repo=...,
        leads_pubsub=fake_leads_pubsub,
    )
    await use_case.execute(
        enrollment_id=seed_pending_step.enrollment_id,
        step_id=seed_pending_step.step_id,
    )

    assert any(
        e["type"] == "lead.enrollment.updated" for e in fake_leads_pubsub.published
    )
    env = next(e for e in fake_leads_pubsub.published if e["type"] == "lead.enrollment.updated")
    assert env["enrollment"]["id"] == str(seed_pending_step.enrollment_id)
```

- [ ] **Step 2: Rodar e ver falhar**

```bash
uv run pytest tests/integration/test_dispatch_onboarding_step.py -k publishes -v
```

- [ ] **Step 3: Adicionar `leads_pubsub` (opcional) e publicar**

Em `dispatch_onboarding_step.py`, adicionar `leads_pubsub` ao `__init__` (default `None`). Após persistir o novo status do step (sucesso ou falha):

```python
if self._leads_pubsub is not None:
    # Resolve lead_id via contact (enrollment.contact_id → leads.contact_id)
    from shared.adapters.db.models import LeadModel
    from sqlalchemy import select
    lead_row = await self._session.execute(
        select(LeadModel.id)
        .where(
            LeadModel.account_id == enrollment.account_id,
            LeadModel.contact_id == enrollment.contact_id,
        )
        .order_by(LeadModel.last_event_at.desc())
        .limit(1)
    )
    lead_id = lead_row.scalar_one_or_none()

    envelope = {
        "type": "lead.enrollment.updated",
        "lead_id": str(lead_id) if lead_id else None,
        "enrollment": {
            "id": str(enrollment.id),
            "status": enrollment.status.value,
            "step_id": str(step.id),
            "step_status": result.status.value,
            "step_label": result.label,
        },
    }
    await self._leads_pubsub.publish(enrollment.account_id, envelope)
```

`account_id` vem de `enrollment.account_id`. `_session` é a session injetada (caso o use case ainda não tenha, adicionar no construtor).

- [ ] **Step 4: Wire-up no worker**

No `worker/handlers/scheduled.py` onde o use case é instanciado, passar `leads_pubsub=LeadsPubSub(get_redis())`.

- [ ] **Step 5: Rodar e ver passar**

```bash
uv run pytest tests/integration/test_dispatch_onboarding_step.py -v
```

- [ ] **Step 6: Commit**

```bash
git add apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py apps/api/src/interface/worker/handlers/scheduled.py apps/api/tests/integration/test_dispatch_onboarding_step.py
git commit -m "feat(onboarding): publica lead.enrollment.updated no Redis"
```

---

### Task 16: Endpoint SSE /admin/leads/stream

**Files:**
- Modify: `apps/api/src/interface/http/routers/admin/leads.py`
- Test: `apps/api/tests/integration/test_admin_leads_router.py`

- [ ] **Step 1: Teste do endpoint**

```python
@pytest.mark.asyncio
async def test_leads_stream_emits_events(client, admin_token, account_uuid):
    from shared.adapters.redis.leads_pubsub import LeadsPubSub
    from shared.adapters.redis.client import get_redis

    bus = LeadsPubSub(get_redis())

    async with client.stream(
        "GET", "/admin/leads/stream",
        cookies={"admin_token": admin_token},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        # publica envelope passando filtros vazios — deve emitir
        await bus.publish(account_uuid, {
            "type": "lead.upserted",
            "is_new": True,
            "lead": {"id": "abc", "subscription_status": "active", "utm_source": "facebook", "last_event_at": "2026-05-28T12:00:00Z", "hubla_product_id": "prod_x"},
        })

        # ler primeiro evento do stream
        async for line in response.aiter_lines():
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
                assert payload["lead"]["id"] == "abc"
                break
```

- [ ] **Step 2: Rodar e ver falhar (404)**

```bash
uv run pytest tests/integration/test_admin_leads_router.py -k stream -v
```

- [ ] **Step 3: Implementar endpoint SSE**

Em `routers/admin/leads.py`:

```python
import asyncio
from fastapi.responses import StreamingResponse


def _envelope_matches_filters(
    envelope: dict,
    *,
    product_id: str | None,
    status: str | None,
    utm_source: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> bool:
    lead = envelope.get("lead") or {}
    if product_id and lead.get("hubla_product_id") != product_id:
        return False
    if status and lead.get("subscription_status") != status:
        return False
    if utm_source:
        src = (lead.get("utm_source") or "").lower()
        if utm_source.lower() not in src:
            return False
    if date_from or date_to:
        raw = lead.get("last_event_at")
        if raw:
            try:
                ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                return False
            if date_from and ts < date_from:
                return False
            if date_to and ts > date_to:
                return False
    return True


@router.get("/leads/stream")
async def stream_leads(
    product_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    utm_source: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),  # noqa: B008
    date_to: datetime | None = Query(default=None),  # noqa: B008
    auth: AdminAuth = Depends(require_admin),  # noqa: B008
) -> StreamingResponse:
    from shared.adapters.redis.client import get_redis
    from shared.adapters.redis.leads_pubsub import LeadsPubSub
    from shared.config.single_tenant import get_default_account_uuid

    async def gen():
        async with session_scope() as session:
            account_uuid = await get_default_account_uuid(session)

        bus = LeadsPubSub(get_redis())
        last_ping = asyncio.get_event_loop().time()

        sub_iter = bus.subscribe(account_uuid).__aiter__()

        while True:
            try:
                env = await asyncio.wait_for(sub_iter.__anext__(), timeout=25.0)
                if _envelope_matches_filters(
                    env,
                    product_id=product_id,
                    status=status_filter,
                    utm_source=utm_source,
                    date_from=date_from,
                    date_to=date_to,
                ):
                    event_name = env.get("type", "message")
                    yield f"event: {event_name}\ndata: {json.dumps(env, default=str)}\n\n"
            except asyncio.TimeoutError:
                # heartbeat
                yield ": ping\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
```

Adicionar `import json` no topo.

- [ ] **Step 4: Rodar e ver passar**

```bash
uv run pytest tests/integration/test_admin_leads_router.py -k stream -v
```

- [ ] **Step 5: Commit**

```bash
git add apps/api/src/interface/http/routers/admin/leads.py apps/api/tests/integration/test_admin_leads_router.py
git commit -m "feat(leads-api): GET /admin/leads/stream SSE com filtro server-side"
```

---

### Task 17: Hook useLeadsStream

**Files:**
- Create: `apps/web/src/features/leads/hooks/useLeadsStream.ts`

Sem testes unitários (depende de EventSource). Validação via integração na page.

- [ ] **Step 1: Criar hook**

```ts
// apps/web/src/features/leads/hooks/useLeadsStream.ts
"use client";

import { useEffect, useRef, useState } from "react";
import type { Lead, LeadEvent, LeadFilters } from "../types";

type ConnectionStatus = "connecting" | "open" | "reconnecting" | "closed";

interface Handlers {
  onLeadUpserted?: (lead: Lead, isNew: boolean) => void;
  onEventAppended?: (leadId: string, event: LeadEvent) => void;
  onEnrollmentUpdated?: (leadId: string, enrollment: {
    id: string; status: string; step_id: string; step_status: string;
  }) => void;
}

function buildUrl(filters: LeadFilters): string {
  const qs = new URLSearchParams();
  if (filters.product_id) qs.set("product_id", filters.product_id);
  if (filters.status) qs.set("status", filters.status);
  if (filters.utm_source) qs.set("utm_source", filters.utm_source);
  if (filters.date_from) qs.set("date_from", filters.date_from);
  if (filters.date_to) qs.set("date_to", filters.date_to);
  return `/admin/leads/stream?${qs.toString()}`;
}

export function useLeadsStream(filters: LeadFilters, handlers: Handlers) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    const es = new EventSource(buildUrl(filters));
    setStatus("connecting");

    es.onopen = () => setStatus("open");
    es.onerror = () => setStatus("reconnecting");

    es.addEventListener("lead.upserted", (e) => {
      try {
        const env = JSON.parse((e as MessageEvent).data);
        handlersRef.current.onLeadUpserted?.(env.lead, env.is_new);
        // Quando o envelope carrega evento Hubla recém-criado, também triggera
        // o handler de "event appended" pro drawer atualizar a timeline.
        if (env.event) {
          handlersRef.current.onEventAppended?.(env.lead.id, env.event);
        }
      } catch {}
    });
    es.addEventListener("lead.enrollment.updated", (e) => {
      try {
        const env = JSON.parse((e as MessageEvent).data);
        handlersRef.current.onEnrollmentUpdated?.(env.lead_id ?? "", env.enrollment);
      } catch {}
    });

    return () => {
      es.close();
      setStatus("closed");
    };
  }, [
    filters.product_id, filters.status, filters.utm_source,
    filters.date_from, filters.date_to,
  ]);

  return { status };
}
```

- [ ] **Step 2: Type-check**

```bash
cd apps/web && npx tsc --noEmit
```

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/leads/hooks/useLeadsStream.ts
git commit -m "feat(leads): hook useLeadsStream com filtros via query string"
```

---

### Task 18: Integrar SSE na lista (page.tsx)

**Files:**
- Modify: `apps/web/src/app/(admin)/leads/page.tsx`

- [ ] **Step 1: Plug do hook + handlers**

Em `LeadsPage` (após o `useState` de leads e antes do JSX):

```ts
const [highlightId, setHighlightId] = useState<string | null>(null);

const { status: streamStatus } = useLeadsStream(filters, {
  onLeadUpserted: (lead, isNew) => {
    setLeads((prev) => {
      const idx = prev.findIndex((l) => l.id === lead.id);
      if (idx >= 0) {
        const copy = [...prev];
        copy[idx] = lead;
        return copy;
      }
      if (isNew) {
        setTotal((t) => t + 1);
        return [lead, ...prev];
      }
      return prev;
    });
    setHighlightId(lead.id);
    setTimeout(() => setHighlightId(null), 600);
  },
});
```

Importar o hook no topo: `import { useLeadsStream } from "@/features/leads/hooks/useLeadsStream";`

- [ ] **Step 2: Indicador "ao vivo" no header**

Adicionar próximo ao título:

```tsx
<div className="flex items-center gap-1.5 text-xs text-on-surface-variant" title={streamStatus}>
  <span
    className={`h-2 w-2 rounded-full ${
      streamStatus === "open" ? "animate-pulse bg-emerald-500" :
      streamStatus === "reconnecting" ? "bg-amber-500" : "bg-on-surface-variant/40"
    }`}
  />
  {streamStatus === "open" ? "Ao vivo" : streamStatus === "reconnecting" ? "Reconectando..." : "Offline"}
</div>
```

- [ ] **Step 3: Highlight visual nas linhas**

Na linha do `<tr ...>` (no map de leads), adicionar:

```tsx
className={`cursor-pointer border-t border-outline-variant/50 transition-colors hover:bg-surface-container ${
  highlightId === lead.id ? "bg-emerald-500/10" : ""
}`}
```

- [ ] **Step 4: Validar visualmente**

`npm run dev`, dois browsers (ou um browser e curl ao webhook):
- Bater webhook `/webhook/hubla` com payload de teste.
- Confirmar: novo lead aparece no topo da lista, com fade verde por ~600ms.
- Toggle status no banco; confirmar atualização in-place.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/app/\(admin\)/leads/page.tsx
git commit -m "feat(leads): lista em tempo real via SSE + indicador ao vivo"
```

---

### Task 19: Integrar SSE no LeadDrawer

**Files:**
- Modify: `apps/web/src/features/leads/components/LeadDrawer.tsx`

- [ ] **Step 1: Adicionar handlers no Drawer**

No `LeadDrawer.tsx`, adicionar handlers que reagem aos eventos do hook do `LeadsPage`. Como o hook já está em `LeadsPage`, expor um callback ao Drawer:

Em `page.tsx`, alterar a chamada do hook pra incluir `onEventAppended` e `onEnrollmentUpdated`:

```ts
const drawerHandlersRef = useRef<{
  onEvent?: (event: LeadEvent) => void;
  onEnrollment?: (enrollment: any) => void;
}>({});

useLeadsStream(filters, {
  onLeadUpserted: (...) => { ... },  // já existente
  onEventAppended: (leadId, event) => {
    if (selectedLead?.id === leadId) drawerHandlersRef.current.onEvent?.(event);
  },
  onEnrollmentUpdated: (leadId, enrollment) => {
    if (selectedLead?.id === leadId) drawerHandlersRef.current.onEnrollment?.(enrollment);
  },
});

// Passar ref pro drawer:
<LeadDrawer
  lead={selectedLead}
  open={drawerOpen}
  onClose={() => setDrawerOpen(false)}
  onRegisterStreamHandlers={(h) => { drawerHandlersRef.current = h; }}
/>
```

- [ ] **Step 2: Atualizar `LeadDrawer` pra aceitar e usar handlers**

```tsx
interface Props {
  lead: Lead | null;
  open: boolean;
  onClose: () => void;
  onRegisterStreamHandlers?: (h: {
    onEvent: (event: LeadEvent) => void;
    onEnrollment: (enrollment: { id: string; step_id: string; step_status: string }) => void;
  }) => void;
}

// dentro do componente:
useEffect(() => {
  if (!open || !onRegisterStreamHandlers) return;
  onRegisterStreamHandlers({
    onEvent: (event) => {
      setDetail((prev) => prev ? { ...prev, events: [event, ...prev.events] } : prev);
    },
    onEnrollment: (env) => {
      setDetail((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          enrollments: prev.enrollments.map((e) =>
            e.id !== env.id ? e : {
              ...e,
              steps: e.steps.map((s) =>
                s.id !== env.step_id ? s : { ...s, status: env.step_status as never },
              ),
            }
          ),
        };
      });
    },
  });
  return () => onRegisterStreamHandlers({ onEvent: () => {}, onEnrollment: () => {} });
}, [open, onRegisterStreamHandlers]);
```

- [ ] **Step 3: Validar visualmente**

`npm run dev`. Abrir drawer de um lead. Bater novo evento Hubla pro mesmo lead. Confirmar:
- Timeline ganha novo item no topo sem reload.
- Step de enrollment muda status (sent/failed) sem reload.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/features/leads/components/LeadDrawer.tsx apps/web/src/app/\(admin\)/leads/page.tsx
git commit -m "feat(leads): drawer atualiza timeline e enrollments em tempo real"
```

---

## Verificação final

- [ ] **Step 1: Rodar todos os testes do backend**

```bash
cd apps/api && uv run pytest -v
```

Expected: tudo passando.

- [ ] **Step 2: Lint + typecheck do backend**

```bash
cd apps/api && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src
```

- [ ] **Step 3: Typecheck do frontend**

```bash
cd apps/web && npx tsc --noEmit && npm run lint
```

- [ ] **Step 4: Validação manual end-to-end**

`docker compose up postgres redis` em um terminal, `uv run uvicorn main:app --reload` em outro, `uv run python -m worker` em outro, `cd apps/web && npm run dev` em outro.

Fluxo:
1. Abrir `/leads` em browser.
2. Conferir badge "Ao vivo" verde piscando.
3. Aplicar filtros via modal → lista atualiza, chips aparecem.
4. Clicar num lead → drawer abre com top:0, seta de voltar funciona.
5. Botão "Abrir conversa no ChatNexo" abre nova aba se houver conversation.
6. Disparar webhook Hubla:
   ```bash
   curl -X POST 'http://localhost:8000/webhook/hubla?token=...' \
     -H 'Content-Type: application/json' \
     -d '{...payload válido...}'
   ```
7. Confirmar: novo lead aparece no topo da lista com fade verde.
8. Coluna "Último evento" mostra `dd/mm/yyyy hh:mm`.

- [ ] **Step 5: Limpar commits se necessário e abrir PR**

```bash
git log --oneline fix/edit-pending-and-loading-overlay
gh pr create --title "feat(leads): real-time SSE, filtros modal, link ChatNexo e UX do drawer" --body "$(cat <<'EOF'
## Summary
- Drawer com z-index ajustado (cobre TopBar) e botão voltar (arrow_back)
- Coluna "Último evento" com data+hora
- Botão "Abrir conversa no ChatNexo" no drawer
- Filtros corrigidos server-side, modal novo com DatePicker custom (react-day-picker) e sugestão de UTMs
- SSE em /admin/leads/stream com filtragem server-side; lista e drawer atualizam em tempo real

Spec: docs/superpowers/specs/2026-05-28-leads-page-melhorias-design.md
Plan: docs/superpowers/plans/2026-05-28-leads-page-melhorias.md

## Test plan
- [ ] pytest backend completo passa
- [ ] tsc + lint frontend passa
- [ ] Manual: webhook Hubla → lead aparece na lista em tempo real
- [ ] Manual: drawer recebe novo evento sem reload
- [ ] Manual: modal de filtros aplica + chips removem individualmente
- [ ] Manual: ChatNexo link abre em nova aba
EOF
)"
```

---

## Resumo de arquivos

**Backend criados:**
- `apps/api/src/shared/adapters/redis/leads_pubsub.py`
- `apps/api/tests/integration/test_leads_pubsub.py`
- `apps/api/tests/integration/test_lead_repo.py` (se ainda não existir)
- `apps/api/tests/integration/test_admin_leads_router.py` (se ainda não existir)

**Backend modificados:**
- `apps/api/src/shared/domain/entities/lead.py`
- `apps/api/src/shared/adapters/db/repositories/lead_repo.py`
- `apps/api/src/interface/http/routers/admin/leads.py`
- `apps/api/src/shared/application/hubla_event_handler.py`
- `apps/api/src/shared/application/use_cases/onboarding/dispatch_onboarding_step.py`
- `apps/api/src/interface/worker/handlers/hubla_event.py`
- `apps/api/src/interface/worker/handlers/scheduled.py`

**Frontend criados:**
- `apps/web/src/features/leads/hooks/useLeadsStream.ts`
- `apps/web/src/features/leads/components/LeadFiltersModal.tsx`
- `apps/web/src/shared/components/DatePicker.tsx`
- `apps/web/src/shared/components/Modal.tsx`

**Frontend modificados:**
- `apps/web/src/shared/components/Drawer.tsx`
- `apps/web/src/app/(admin)/leads/page.tsx`
- `apps/web/src/features/leads/components/LeadDrawer.tsx`
- `apps/web/src/features/leads/types.ts`
- `apps/web/src/lib/api.ts`
- `apps/web/package.json`
