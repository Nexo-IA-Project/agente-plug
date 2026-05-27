# Spec: Onboarding Stepper + 24 Eventos Hubla + UX Fixes

**Data:** 2026-05-27
**Status:** Em design — aguardando aprovação do usuário
**Branch alvo:** novo branch a partir de `fix/parameter-format-detection-and-sync-button`

---

## Contexto

Cinco demandas relacionadas que tocam os mesmos módulos (`/onboarding`, `/products`, `/templates`, `Drawer` compartilhado e o pipeline de eventos Hubla):

1. Toast/Dialog de confirmação ao excluir em **produtos** (templates já tem).
2. **Editar template** Meta direto no modal de criação.
3. Click fora do drawer (inclusive sidebar) fecha o modal de `/onboarding`.
4. Salvar fecha o drawer automaticamente.
5. **Reformulação completa do FlowDrawer** em stepper vertical de 3 passos + suporte aos **25 eventos** oficiais da Hubla v2 (atualmente apenas 6).

Optamos por entregar tudo em uma spec única porque (a) compartilham o `Drawer` e o `TemplateModal`, (b) os ajustes UX são pré-requisito para a reformulação ficar coesa, e (c) a expansão dos eventos exige que o stepper já esteja redesenhado pra acomodar 25 cards agrupados por categoria.

Este documento substitui (avança) a parte 1 da spec `2026-05-26-hubla-events-expansion-and-meta-template-autosync.md`. A parte 2 daquela spec (auto-sync Meta) **permanece backlog** e fica fora desta entrega.

---

## Objetivos e não-objetivos

### Objetivos
- Reescrever `FlowDrawer` em stepper vertical de 3 passos (Produto → Eventos → Mensagens) com rail lateral de círculos numerados e transição animada.
- Suportar os 25 eventos Hubla v2 como `trigger_event_type` válido em flows, com agrupamento por categoria via tabs.
- Corrigir 2 nomes divergentes via migration (`lead.abandoned` → `lead.abandoned_cart`, `subscription.expiring` → `subscription.expired`).
- Trocar `confirm()` nativo por `useConfirm()` na exclusão de produtos.
- Habilitar edição de templates Meta **em status não-aprovado** reutilizando o `TemplateModal`.
- Backdrop do `Drawer` compartilhado cobrir tela inteira (incluindo sidebar).
- Drawer/Modal fecham automaticamente após salvar com sucesso.

### Não-objetivos
- **Não implementa** auto-sync de templates Meta (continua manual via botão existente).
- **Não migra dados** de `hubla_events` antigos — só corrige `followup_flows`. Log imutável preserva nomes antigos.
- **Não automatiza** criação de templates Meta — fluxo de criação continua igual.
- **Não muda** o backend de steps de mensagem (`StepList`, `StepInlineForm`, drag-reorder, `VariableResolver` permanecem como estão).
- **Não implementa** edição de templates aprovados (limitação da Meta API — botão Editar fica oculto nesse caso).

---

## Arquitetura

### Frontend

```
apps/web/src/
├── features/
│   ├── onboarding/
│   │   ├── components/
│   │   │   ├── FlowDrawer.tsx           ← reescrito: orquestra steps + state machine
│   │   │   ├── steps/                   ← NOVO diretório
│   │   │   │   ├── StepRail.tsx         ← rail lateral (círculos, conectores, click)
│   │   │   │   ├── StepProductPicker.tsx
│   │   │   │   ├── StepEventPicker.tsx  ← tabs por categoria + grid de EventCard
│   │   │   │   └── StepMessageBuilder.tsx ← wrapper de StepList existente
│   │   │   ├── EventCard.tsx            ← NOVO: 1 card de evento
│   │   │   ├── FlowCard.tsx             ← mantido (lista de flows)
│   │   │   ├── StepList.tsx             ← mantido (mensagens + reorder)
│   │   │   ├── StepItem.tsx             ← mantido
│   │   │   ├── StepInlineForm.tsx       ← mantido
│   │   │   ├── StepVariableEditor.tsx   ← mantido
│   │   │   └── DelayBadge.tsx           ← mantido
│   │   └── lib/
│   │       └── triggerEvents.ts         ← expandido de 6 → 25 entries + agrupamento
│   ├── products/
│   │   └── components/                  ← inalterado
│   └── templates/
│       └── components/
│           ├── TemplateModal.tsx        ← aceita prop `template?: MetaTemplate` (modo edit)
│           └── TemplateForm.tsx         ← aceita `initialValues?` para preencher
├── app/(admin)/
│   ├── products/page.tsx                ← troca confirm() por useConfirm()
│   └── templates/page.tsx               ← passa template selecionado ao modal em edit
└── shared/components/
    └── Drawer.tsx                       ← backdrop a `inset-0`, fecha por click na sidebar
```

### Backend

```
apps/api/src/
├── shared/
│   ├── domain/
│   │   └── value_objects/
│   │       └── hubla_event_type.py      ← NOVO: Literal de 25 valores + helpers
│   ├── application/
│   │   ├── hubla_event_handler.py       ← aceita 25 tipos; só activated chama PurchaseHandler
│   │   └── use_cases/
│   │       └── admin/
│   │           └── meta_templates/
│   │               └── edit_template.py ← NOVO use case (PATCH não-aprovados)
│   └── adapters/
│       └── meta/
│           └── client.py                ← novo método edit_template() se não existir
├── interface/http/routers/admin/
│   └── meta_templates.py                ← novo PATCH /admin/meta-templates/{id}
└── migrations/versions/
    └── <rev>_rename_divergent_hubla_event_types.py  ← NOVO
```

---

## Detalhamento por demanda

### 1. `useConfirm()` em produtos

**Arquivo:** `apps/web/src/app/(admin)/products/page.tsx`

Substituir o `confirm()` nativo do browser (linha ~46):

```ts
// antes
if (!confirm(`Remover o produto "${p.name}"?`)) return;

// depois
const ok = await confirm({
  title: "Excluir produto",
  description: `Tem certeza que deseja remover "${p.name}"? Esta ação não pode ser desfeita.`,
  confirmLabel: "Excluir",
  variant: "danger",
});
if (!ok) return;
```

Adicionar import de `useConfirm` do `@/shared/components/confirm`. Comportamento idêntico ao da página de templates.

### 2. Editar templates Meta

**Restrição da Meta:** templates aprovados (`status === "APPROVED"`) só permitem alterar `category` via API — corpo, header, footer, botões são imutáveis. Para evitar UX confuso, edição completa fica restrita a templates em `PENDING`, `REJECTED` ou estados similares não-finais. Templates aprovados mostram tooltip explicando a limitação.

#### Frontend

- `TemplateModal.tsx` aceita prop opcional `template?: MetaTemplate`. Quando presente:
  - Título muda de "Novo template" para "Editar template — {name}".
  - Botão muda de "Criar" para "Salvar alterações".
  - `TemplateForm` recebe `initialValues` derivados do template (name read-only ao editar, demais campos preenchidos).
  - `onSubmit` chama `editMetaTemplate(template.id, data)` em vez de `createMetaTemplate(data)`.
  - Modal fecha automaticamente após sucesso (já é o comportamento atual).
- Lista `/templates` (page.tsx): cada `TemplateCard` ganha botão "Editar" — só renderiza quando `template.status !== "APPROVED"`. Em aprovados, tooltip: "Templates aprovados pela Meta não podem ser editados. Crie um novo com nome diferente."

#### Backend

- Endpoint `PATCH /admin/meta-templates/{id}` (router `meta_templates.py`):
  - Retorna `409 Conflict` se template está `APPROVED` (com `code: "template_approved_immutable"`).
  - Para outros status: chama `MetaClient.edit_template(template_id, components, category)` (verificar se método existe em `apps/api/src/shared/adapters/meta/client.py`; se não, adicionar — a rota Graph é `POST /{template_id}` com body de componentes).
  - Atualiza `meta_templates` no banco com os novos valores + `updated_at`.
- Schema Pydantic `EditMetaTemplateRequest` — mesmos campos do create mas todos opcionais.
- `apps/web/src/lib/api.ts` ganha `editMetaTemplate(id, payload)`.

### 3. Click fora fecha (Drawer compartilhado)

**Arquivo:** `apps/web/src/shared/components/Drawer.tsx`

Hoje o backdrop começa em `left: var(--sidebar-width, 240px)` (linha 41) — clicar na sidebar não dispara `onClose`. Fix:

- Remover `style={{ left: SIDEBAR_WIDTH }}` do backdrop (linha 41). Usar `fixed inset-0` direto.
- Manter `aside` (painel) com `left: SIDEBAR_WIDTH` ou ajustar para `left: 0` — TBD em plan-time conforme o efeito visual desejado. Padrão proposto: sidebar fica visualmente escurecida sob o backdrop, drawer continua à direita.
- `cursor-pointer` no backdrop pra sinalizar que é clicável.

Comportamento esperado:
- Click em qualquer ponto fora do `aside` (incluindo sidebar) → `onClose`.
- ESC → `onClose` (já funciona).
- Click dentro do `aside` → não fecha.

**Aplicação retroativa:** mudança no `Drawer` compartilhado afeta automaticamente `FlowDrawer`, `ProductDrawer` e `LeadDrawer`. Verificar visualmente cada um após o fix.

### 4. Fecha após salvar

**Arquivo:** `apps/web/src/features/onboarding/components/FlowDrawer.tsx`

Após sucesso em `onCreate` ou `onUpdate`:
- Toast de sucesso.
- `onClose()` chamado imediatamente.

Mesma regra aplica ao novo botão "Concluir" do step 3 (fecha sem necessariamente persistir nada — steps individuais já salvam inline).

`TemplateModal` já fecha após sucesso (`onClose()` dentro do callback `onCreate` na linha ~76). Estender o mesmo padrão pro `onEdit`.

`ProductDrawer` já fecha após sucesso (linha 37) — sem mudança.

### 5. Stepper de 3 passos + 25 eventos Hubla

#### Stepper

**Estado (state machine local do `FlowDrawer`):**

```ts
type StepperState = {
  current: 1 | 2 | 3;
  productId: string;           // step 1
  triggerEventType: HublaEventType; // step 2
  isActive: boolean;           // step 2
  flowId: string | null;       // existe após step 2 ser persistido
  direction: "forward" | "backward"; // controla animação
};
```

**Regras de navegação:**
- Novo flow:
  - Step 1: botão "Próximo" habilitado quando `productId` está setado. Avança pra step 2 (sem chamada API).
  - Step 2: botão "Salvar e continuar" → `POST /admin/onboarding/flows` com `{ product_id, trigger_event_type, is_active, name: \`Produto: \${product.name}\` }`. Resposta retorna `flow.id` → grava em `flowId` → avança pra step 3.
  - Step 3: usa `StepList` existente (steps de mensagem com drag-reorder). Cada step adicionado/editado/removido faz sua própria chamada API (comportamento atual). Botão "Concluir" no rodapé fecha o drawer.
- Editar flow existente:
  - `flowId` já vem do `flow.id` na prop.
  - Rail lateral é clicável livre — usuário pode ir direto em qualquer step.
  - Step 1 e Step 2 têm botão "Salvar alterações" no rodapé → `PUT /admin/onboarding/flows/{id}` → toast sucesso + fecha drawer.
  - Step 3 mantém comportamento atual (CRUD inline). "Concluir" fecha sem extra request.

**Animação entre steps:**

Crossfade + slide horizontal curto, ~200ms, ease-out (`cubic-bezier(0.16, 1, 0.3, 1)`).

- Avançar: step que sai fade-out + `translateX(-8px)`; step que entra fade-in + `translateX(8px → 0)`.
- Voltar: direções invertidas.
- Implementação: `key={current}` no container do step + classe de animação aplicada via `direction`. CSS keyframes em `globals.css` (ou módulo CSS scoped). Não introduzir nova dependência (framer-motion etc.).
- Drag-reorder dos steps de mensagem (Step 3) **não muda** — continua via biblioteca atual.

**Rail lateral (`StepRail.tsx`):**

```
[●1] ──── Produto         ✓
  │
[●2] ──── Eventos         (atual)
  │
[ 3] ──── Mensagens       (pendente)
```

- Círculo numerado (40px, `rounded-full`) com 3 estados: `done` (verde + check), `current` (azul + número), `pending` (cinza + número).
- Conector vertical 2px entre círculos. Cor: verde se step anterior `done`, cinza caso contrário.
- Click no número: ao criar = só permite voltar (steps anteriores) ou avançar se válido; ao editar = todos clicáveis.
- Tokens NexoIA: `bg-primary` (current), `bg-emerald-500` (done — equivalente semântico de sucesso no tema), `bg-surface-container-high` (pending), `text-on-primary` / `text-on-surface-variant`.

#### 24 Eventos Hubla

**Catálogo completo (label PT-BR + descrição curta):**

| Evento técnico | Label PT-BR | Categoria | Descrição (tooltip/card) |
|---|---|---|---|
| `lead.abandoned_cart` | Carrinho abandonado | Lead | Cliente preencheu email/telefone no checkout mas não concluiu compra em 20 minutos |
| `member.access_granted` | Acesso concedido | Membro | Cliente recebeu acesso ao produto / área de membros |
| `member.access_removed` | Acesso removido | Membro | Acesso foi revogado (cancelamento, banimento, expiração) |
| `subscription.created` | Assinatura criada | Assinatura | Checkout iniciado — aguardando pagamento (PIX, boleto, cartão pendente) |
| `subscription.activated` | Venda ativada | Assinatura | Pagamento confirmado — assinatura ativa |
| `subscription.expired` | Assinatura expirada | Assinatura | Data fim atingida sem renovação |
| `subscription.deactivated` | Assinatura desativada | Assinatura | Cancelada manualmente, fraude, etc |
| `subscription.auto_renewal_disabled` | Renovação automática desligada | Assinatura | Cliente desabilitou renovação — risco de churn |
| `subscription.auto_renewal_enabled` | Renovação automática ligada | Assinatura | Cliente reativou renovação automática |
| `invoice.created` | Fatura emitida | Fatura | Fatura criada — aguardando pagamento |
| `invoice.status_updated` | Status da fatura mudou | Fatura | Mudança genérica no status da fatura |
| `invoice.payment_completed` | Pagamento confirmado | Fatura | Fatura paga com sucesso |
| `invoice.payment_failed` | Pagamento falhou | Fatura | Cartão recusado, PIX não confirmado — dunning |
| `invoice.expired` | Fatura vencida | Fatura | Fatura venceu sem pagamento |
| `invoice.refunded` | Fatura reembolsada | Fatura | Valor devolvido ao cliente |
| `installment.created` | Parcelamento criado | Parcelamento | Parcelamento inteligente iniciado |
| `installment.failed` | Cobrança de parcela falhou | Parcelamento | Tentativa de cobrança de uma parcela falhou |
| `installment.in_progress` | Parcelamento em andamento | Parcelamento | Parcelamento ativo, sem problemas |
| `installment.overdue` | Parcela em atraso | Parcelamento | Uma ou mais parcelas estão atrasadas |
| `installment.cancelled` | Parcelamento cancelado | Parcelamento | Parcelamento foi cancelado |
| `installment.completed` | Parcelamento concluído | Parcelamento | Todas as parcelas foram pagas |
| `refund_request.created` | Pedido de reembolso aberto | Reembolso | Cliente solicitou reembolso — última chance antes de aprovar |
| `refund_request.accepted` | Reembolso aprovado | Reembolso | Solicitação aceita — reembolso será processado |
| `refund_request.cancelled` | Pedido de reembolso cancelado | Reembolso | Cliente cancelou a solicitação |
| `refund_request.rejected` | Pedido de reembolso negado | Reembolso | Solicitação recusada |

**Paleta por categoria (tokens NexoIA / Tailwind):**

| Categoria | Cor principal | Uso |
|---|---|---|
| Lead | amber-500 | Tab pill + ícone + ring |
| Membro | teal-500 | Tab pill + ícone + ring |
| Assinatura | emerald-500 | Tab pill + ícone + ring |
| Fatura | violet-500 | Tab pill + ícone + ring |
| Parcelamento | blue-500 | Tab pill + ícone + ring |
| Reembolso | rose-500 | Tab pill + ícone + ring |

Ícones via Material Symbols Outlined (já no projeto). Mapeamento exato dos 24 ícones fica no plano de implementação.

**Layout do step 2 (`StepEventPicker.tsx`):**

```
┌──────────────────────────────────────────────┐
│ [Lead 1] [Membro 2] [Assinatura 6] [Fatura 6]│
│ [Parcelamento 6] [Reembolso 4]              │ ← tabs com badge
├──────────────────────────────────────────────┤
│                                              │
│  ┌──────────────┐ ┌──────────────┐          │
│  │ ✅ Venda      │ │ ⏳ Criada    │          │  ← grid 2 cols
│  │ ativada      │ │              │          │     de EventCard
│  │ Pgto confirm │ │ Aguardando   │          │
│  └──────────────┘ └──────────────┘          │
│  ... mais 4 cards da categoria ...           │
└──────────────────────────────────────────────┘
```

- Tabs horizontais (wrap em telas pequenas) com pill colorida por categoria + badge de contagem.
- Tab ativa: fundo da cor da categoria com `text-white`. Inativa: transparent + `text-on-surface-variant`.
- Grid de `EventCard` na tab ativa (2 colunas em md+, 1 coluna em mobile).
- Card selecionado: ring de 2px na cor da categoria + bg sutil (10% alpha).
- Animação ao trocar tab: fade rápido (~150ms) — mesma família do crossfade dos steps.

**`triggerEvents.ts` expandido:**

```ts
export type HublaEventCategory =
  | "lead" | "member" | "subscription"
  | "invoice" | "installment" | "refund";

export type HublaEventType =
  | "lead.abandoned_cart"
  | "member.access_granted" | "member.access_removed"
  | "subscription.created" | "subscription.activated" | "subscription.expired"
  | "subscription.deactivated" | "subscription.auto_renewal_disabled"
  | "subscription.auto_renewal_enabled"
  | "invoice.created" | "invoice.status_updated" | "invoice.payment_completed"
  | "invoice.payment_failed" | "invoice.expired" | "invoice.refunded"
  | "installment.created" | "installment.failed" | "installment.in_progress"
  | "installment.overdue" | "installment.cancelled" | "installment.completed"
  | "refund_request.created" | "refund_request.accepted"
  | "refund_request.cancelled" | "refund_request.rejected";

export interface TriggerEventMeta {
  value: HublaEventType;
  label: string;          // PT-BR curto
  technical: string;      // = value
  description: string;    // PT-BR longo (tooltip)
  category: HublaEventCategory;
  categoryLabel: string;  // ex: "Assinatura"
  icon: string;           // material symbols name
  tone: TriggerEventTone; // mantido — usado pelo LeadDrawer
}

export const TRIGGER_EVENTS: readonly TriggerEventMeta[] = [ /* 25 entries */ ];
export const TRIGGER_EVENT_CATEGORIES: readonly HublaEventCategory[] = [
  "lead", "member", "subscription", "invoice", "installment", "refund",
];
export const CATEGORY_META: Record<HublaEventCategory, { label: string; tone: TriggerEventTone }>;

export function getTriggerEventMeta(value: string): TriggerEventMeta | undefined;
export function getEventsByCategory(cat: HublaEventCategory): TriggerEventMeta[];
```

**Compatibilidade:** o `LeadDrawer` consome `getTriggerEventMeta(event_type)` pra desenhar a timeline. Eventos antigos (`lead.abandoned`, `subscription.expiring`) que ainda existem em `hubla_events` precisam de fallback — adicionar entries marcadas como `deprecated: true` que fazem alias visual para o equivalente novo. Decisão alternativa: `getTriggerEventMeta` retorna `undefined` e o `LeadDrawer` cai em tone neutro (já preparado para isso). **Escolhido:** entries alias internamente — mais limpo.

#### Backend — Validação e roteamento

**Value object (`apps/api/src/shared/domain/value_objects/hubla_event_type.py`):**

```python
from typing import Literal, get_args

HublaEventType = Literal[
    # ... 25 valores idênticos ao frontend ...
]

ALL_HUBLA_EVENT_TYPES: frozenset[str] = frozenset(get_args(HublaEventType))

PURCHASE_EVENT_TYPES: frozenset[str] = frozenset({"subscription.activated"})
"""Eventos que disparam o pipeline legado de PurchaseHandler (welcome + access_case)."""
```

**`HublaEventHandler` (`apps/api/src/shared/application/hubla_event_handler.py`):**

Hoje (linha 14): `_PURCHASE_EVENT_TYPES = frozenset({"subscription.activated"})`. Substituir por import do novo módulo.

Hoje (linha 57): `event_type: str = payload.get("type", "")`. Adicionar validação:

```python
event_type = payload.get("type", "")
if event_type not in ALL_HUBLA_EVENT_TYPES:
    log.warning("hubla_unknown_event", event_type=event_type, payload_id=payload.get("id"))
    # ainda persistir em hubla_events pra log forense — não retornar erro
```

Pipeline atual permanece:
1. Persistir em `hubla_events` (log imutável — sempre, mesmo eventos desconhecidos).
2. Upsert em `leads` (só pra tipos que tem `subscription` no payload — invoice/installment podem não ter; verificar no plan-time).
3. Lookup `followup_flows WHERE product_id = ? AND trigger_event_type = ?`.
4. Enrollar contato nos flows encontrados via `EnrollContact` use case.
5. Se `event_type in PURCHASE_EVENT_TYPES`: chamar `PurchaseHandler` para welcome + access_case.

**Webhook router (`apps/api/src/interface/http/routers/webhook_hubla.py`):**

Já aceita qualquer `type` como string — sem mudança. Aceitação no schema mantém `event_type: str` (não `Literal`) pra ser resiliente a payloads futuros da Hubla.

**Migration (`migrations/versions/<rev>_rename_divergent_hubla_event_types.py`):**

```python
def upgrade() -> None:
    op.execute("""
        UPDATE followup_flows SET trigger_event_type = 'lead.abandoned_cart'
        WHERE trigger_event_type = 'lead.abandoned';
    """)
    op.execute("""
        UPDATE followup_flows SET trigger_event_type = 'subscription.expired'
        WHERE trigger_event_type = 'subscription.expiring';
    """)

def downgrade() -> None:
    op.execute("""
        UPDATE followup_flows SET trigger_event_type = 'lead.abandoned'
        WHERE trigger_event_type = 'lead.abandoned_cart';
    """)
    op.execute("""
        UPDATE followup_flows SET trigger_event_type = 'subscription.expiring'
        WHERE trigger_event_type = 'subscription.expired';
    """)
```

`hubla_events.event_type` **não é tocado** — log preserva o que foi recebido.

---

## Data flow consolidado

### Fluxo de criação de flow (novo)

```
Usuário clica "Novo flow" em /onboarding
  → FlowDrawer abre em step 1 (productId vazio, flowId null)
  → Usuário escolhe Produto → "Próximo"
    → state.current = 2 (animação slide-left)
  → Usuário escolhe categoria (tab) → escolhe Evento (card) → "Salvar e continuar"
    → POST /admin/onboarding/flows { product_id, trigger_event_type, is_active, name }
    → resposta: flow.id → state.flowId = ID, state.current = 3
  → Step 3 carrega StepList (vazio) — usuário adiciona steps de mensagem (cada add/edit/remove é chamada API individual já existente)
  → Usuário clica "Concluir"
    → onClose() → drawer fecha
```

### Fluxo de webhook Hubla (qualquer evento)

```
Hubla → POST /webhook/hubla (x-hubla-token validado)
  → WebhookEventRepository (dedup Redis)
  → job_queue.enqueue(kind="hubla_event", payload)
  → Worker → handle_hubla_event(payload)
    → HublaEventHandler.handle(payload)
      → event_type = payload["type"]
      → validar contra ALL_HUBLA_EVENT_TYPES (warn se desconhecido, segue)
      → resolver contact (cria se novo)
      → persistir hubla_events (log)
      → upsert leads (se aplicável)
      → product = resolver via hubla_id
      → flows = repo.find_by(product_id, trigger_event_type=event_type)
      → para cada flow: EnrollContact.execute(contact, flow)
      → se event_type em PURCHASE_EVENT_TYPES: PurchaseHandler.handle(payload) (welcome + access)
    → mark_processed
```

---

## Error handling

- **Click "Salvar e continuar" no step 2 falha:** mostra toast de erro, mantém usuário no step 2, não avança. `flowId` permanece null.
- **Backend `PATCH /admin/meta-templates/{id}` em template aprovado:** retorna `409 Conflict` `{ code: "template_approved_immutable" }`. Frontend já não mostra botão Editar nesse caso — defesa em profundidade.
- **Webhook Hubla com `event_type` desconhecido:** log warning + persistir em `hubla_events` mesmo assim + retornar `202` (não derrubar a Hubla com 4xx).
- **`getTriggerEventMeta` retorna alias deprecated** (ex: `lead.abandoned` em evento antigo): timeline do LeadDrawer renderiza com a nova label sem flag visual de deprecation — UX limpo.

---

## Testing

### Backend
- **Unit tests `HublaEventHandler`** parametrizados nos 25 tipos: cada caso garante `hubla_events` persistido + lookup de flows. Caso especial `subscription.activated` valida chamada a `PurchaseHandler`.
- **Migration test:** seed `followup_flows` com `lead.abandoned` e `subscription.expiring` → `alembic upgrade head` → assert valores renomeados.
- **Unit test `EditMetaTemplate` use case:** mock `MetaClient`, assert 409 em `APPROVED`, assert PATCH em outros status.

### Frontend
- **Smoke do reducer do stepper:** transições válidas (1→2, 2→3, 3→2→1) com gating (não avança step 1 sem product, não avança step 2 sem trigger).
- **Smoke do `TemplateModal` em modo edit:** prop `template` preenche form, botão "Editar" some em status APPROVED.
- **Visual review manual:**
  - Click na sidebar com FlowDrawer aberto → fecha.
  - Click no backdrop com TemplateModal aberto → fecha (já funciona).
  - Exclusão de produto mostra `ConfirmDialog` (igual templates).
  - Transição entre steps suave (~200ms slide+fade).
  - Reordenação de steps de mensagem segue funcional (drag-reorder).

### Manual end-to-end (após implementar)
- Disparar webhook Hubla fake (curl ou Postman) com cada um dos 6 event_types de cada categoria → verificar que `hubla_events` registra todos.
- Criar flow novo via UI completando os 3 steps → verificar que `POST /admin/onboarding/flows` é chamado uma vez.
- Editar flow existente → mudar trigger → salvar → verificar no banco.

---

## Riscos e mitigações

| Risco | Severidade | Mitigação |
|---|---|---|
| `MetaClient.edit_template` ainda não existe | Média | Verificar em plan-time antes de implementar o use case. Se não existe, adicionar (rota Graph `POST /{template_id}`). |
| Sidebar escurecida sob backdrop pode confundir usuário | Baixa | `cursor-pointer` no backdrop + animação curta. Validação visual no review. |
| 25 cards no step 2 podem cansar visualmente | Baixa | Tabs reduzem o que aparece de uma vez (~6 cards por tab). Validar UX após implementar. |
| Eventos antigos em `hubla_events` (`lead.abandoned`, `subscription.expiring`) podem aparecer no LeadDrawer | Baixa | `triggerEvents.ts` mantém entries alias internas com label nova. |
| Reordenação de steps quebrar com nova estrutura | Baixa | Step 3 (`StepMessageBuilder`) reusa `StepList` sem mudança — drag-reorder permanece igual. Adicionar smoke test. |
| Animação CSS conflitar com transição do Drawer (translateX) | Média | Animação aplicada ao container interno do step (`<div key={current}>`), não no `<aside>` raiz — não interfere com `translate-x-full` do drawer. |

---

## Critérios de aceite

### Item 1 — Confirmação produtos
- [ ] Clicar "Excluir" em um produto abre `ConfirmDialog` (Material Dialog modal — não `confirm()` nativo).
- [ ] Cancelar não exclui; confirmar exclui e mostra toast de sucesso.

### Item 2 — Editar templates
- [ ] Botão "Editar" aparece em templates `PENDING`, `REJECTED`.
- [ ] Botão não aparece em `APPROVED` (tooltip explica).
- [ ] Click em "Editar" abre `TemplateModal` preenchido.
- [ ] "Salvar alterações" persiste via `PATCH /admin/meta-templates/{id}` e fecha modal.
- [ ] `PATCH` em template aprovado retorna 409.

### Item 3 — Click fora fecha drawer
- [ ] Click em qualquer ponto da sidebar com FlowDrawer aberto fecha o drawer.
- [ ] Click no backdrop entre sidebar e drawer fecha.
- [ ] Click dentro do drawer não fecha.
- [ ] ESC fecha (já funcionava).

### Item 4 — Fecha após salvar
- [ ] FlowDrawer fecha após "Salvar alterações" / "Salvar e continuar" / "Concluir" com sucesso.
- [ ] TemplateModal fecha após "Criar" / "Salvar alterações" com sucesso (criar já fecha).

### Item 5 — Stepper + 25 eventos
- [ ] FlowDrawer renderiza rail lateral com 3 círculos numerados conectados.
- [ ] Novo flow: navegação sequencial (1→2→3 com gating).
- [ ] Editar flow: rail clicável livre.
- [ ] Transição entre steps com slide+fade (~200ms).
- [ ] Step 2: tabs por categoria (Lead 1, Membro 2, Assinatura 6, Fatura 6, Parcelamento 6, Reembolso 4).
- [ ] Cada um dos 25 eventos selecionável como `trigger_event_type`.
- [ ] Webhook `/webhook/hubla` aceita qualquer um dos 25 tipos sem erro.
- [ ] Flow com trigger novo (ex: `member.access_granted`) é encontrado e enrollado quando o evento chega.
- [ ] Migration renomeia `lead.abandoned` → `lead.abandoned_cart` e `subscription.expiring` → `subscription.expired` em flows existentes (idempotente).
- [ ] LeadDrawer mantém timeline visual funcionando (com alias para eventos antigos).
- [ ] Step 3 mantém drag-reorder e CRUD inline de mensagens.

---

## Plano de plan-time (próximos passos após aprovação)

1. Verificar se `MetaClient.edit_template` existe; se não, adicionar.
2. Confirmar mapeamento de ícones Material Symbols pros 25 eventos.
3. Definir exatamente o que entra em `leads` para eventos `invoice.*` / `installment.*` (campo `subscription_id` pode não existir nesses payloads — pode precisar fallback ou skip do upsert de `leads` pra esses tipos).
4. Decidir entre `aside` com `left: SIDEBAR_WIDTH` vs `left: 0` (visual a confirmar no Drawer fix).

Esses pontos viram tarefas detalhadas no plano de implementação (próximo skill: `writing-plans`).
