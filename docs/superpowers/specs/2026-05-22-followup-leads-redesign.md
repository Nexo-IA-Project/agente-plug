# Design: Follow-up Redesign + Sistema de Leads Hubla

**Data:** 2026-05-22  
**Branch de origem:** feat/favicon-logo-session  
**Status:** Aprovado

---

## 1. Contexto

Esta spec cobre quatro iniciativas relacionadas:

1. **Bug fix** — Variáveis de template ignoradas no `StepVariableEditor` (regex incorreto)
2. **Design system global** — Ajustes de altura e border-radius + transições suaves em toda a UI *(já implementado)*
3. **Rename Cursos → Produtos** — Em toda a stack (UI + rotas + API + banco)
4. **Sistema de Leads Hubla** — Captura de todos os eventos da Hubla, novo subsistema de leads com UTMs, valores e página de listagem/exportação

---

## 2. Bug Fix — Variáveis de Template

**Arquivo:** `apps/web/src/features/followup/components/StepVariableEditor.tsx`

**Problema:** O regex `/\{\{(\d+)\}\}/g` detecta apenas variáveis numéricas (`{{0}}`, `{{1}}`). Templates que usam `{{name}}`, `{{produto}}` etc. retornam "Este template não tem variáveis dinâmicas."

**Fix aplicado:** Regex alterado para `/\{\{([^}]+)\}\}/g` — detecta qualquer nome de variável.

**Status:** ✅ Implementado

---

## 3. Design System Global — Ajustes de UI

**Arquivo:** `apps/web/src/app/globals.css` *(fonte única de verdade)*

### 3.1 Dimensões dos campos
| Propriedade | Antes | Depois |
|---|---|---|
| Height (`.field-*`) | 44px | 48px |
| Border-radius (`.field-*`) | 10px | 8px |

### 3.2 Animação `.animate-fade-in` (global)
```css
@keyframes nx-fade-in {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
  animation: nx-fade-in 260ms cubic-bezier(0.16, 1, 0.3, 1) both;
}
```

**Regra de uso:** Aplicar `.animate-fade-in` a **todo elemento que aparece condicionalmente** na UI — formulários revelados, campos com show/hide, seções expandíveis, inputs dinâmicos. Isso inclui qualquer feature futura.

### 3.3 Componentes atualizados
- `StepVariableEditor` — labels com `text-primary` para variáveis, `field-select` / `field-input` padronizados
- `StepInlineForm` — seções template/texto com `key` prop para re-mount + `animate-fade-in`
- `StepItem` — número proeminente com círculo `bg-primary/10 ring-primary/20`, ações visíveis ao hover
- `FlowDrawer` — checkbox customizado, transições, labels em uppercase com tracking
- `Sidebar` — "Cursos" → "Produtos", icon `school` → `inventory_2`

**Status:** ✅ Implementado

---

## 4. Rename: Cursos → Produtos

### Escopo completo

**Frontend (Partial — labels visuais já feitos):**
- [x] Sidebar: label + ícone
- [x] `FlowDrawer`: todos os labels "curso/Curso" → "produto/Produto"
- [x] `StepVariableEditor`: "Nome do curso" → "Nome do produto"
- [ ] Página `/courses/page.tsx` — título, headers, labels internos
- [ ] `CourseDrawer.tsx` — todos os labels
- [ ] `CourseCard.tsx` — se houver referência a "curso"
- [ ] Rota: `/courses` → `/products` (nova página + redirect 301 de `/courses`)
- [ ] `FlowDrawer`: link "Cadastre primeiro" → `/products`

**Backend:**
- [ ] Migration Alembic: renomeia tabela `courses` → `products`
- [ ] Migration: renomeia FK `course_id` → `product_id` em `followup_flows` (único lugar com essa FK)
- [ ] Nota: `followup_enrollments.product_name` já usa esse nome — sem alteração necessária
- [ ] Router `/admin/courses` → `/admin/products`
- [ ] Model `CourseModel` → `ProductModel`, `courses` → `products`
- [ ] Repository `course_repo.py` → `product_repo.py`
- [ ] `purchase_handler.py`, `followup_enrollment_repo.py`, demais referências internas
- [ ] Schemas Pydantic: `CourseResponse`, `CreateCourseInput` etc.

**API Client (frontend):**
- [ ] `lib/api.ts`: funções `listCourses` → `listProducts`, endpoints `/admin/products`
- [ ] Types: `Course` → `Product`, `CourseSummary` → `ProductSummary`
- [ ] Hooks: `useCourses` → `useProducts`

**Atenção:** A migration de renomear tabela é destrutiva. Usar `ALTER TABLE courses RENAME TO products` dentro de uma transação. Testar com `alembic upgrade heads` em ambiente de staging antes de produção.

---

## 5. Arquitetura de Triggers — Follow-up por Evento

### 5.0 Visão Geral

O sistema atual é rígido: um flow sempre dispara em `subscription.activated`. A nova arquitetura é **orientada a triggers**: cada Flow declara qual evento Hubla o dispara. Isso é configurável via UI.

**Modelo de dados:**
```
Produto + Evento Hubla  →  FollowupFlow  →  FollowupSteps
(trigger_event_type)
```

**Mudança no modelo `FollowupFlow`:**
- Adicionar campo `trigger_event_type` (varchar, default `subscription.activated`)
- Backward compat: flows existentes continuam funcionando sem alteração

**Lógica do handler unificado:**
```
POST /webhook/hubla → qualquer evento Hubla
  1. Log → hubla_events
  2. Upsert → leads (com UTMs, valor, etc.)
  3. Resolve produto pelo hubla_product_id
  4. Busca FollowupFlows WHERE product_id = ? AND trigger_event_type = event.type AND is_active = true
  5. Para cada flow → enroll o contato:
       a. Resolve/cria Contact pelo telefone
       b. Verifica se contact tem conversa ABERTA no ChatNexo
          - Se sim → usa conversation_id existente
          - Se não → cria nova conversa no ChatNexo
       c. Cria FollowupEnrollment com conversation_id
  6. Agenda steps (jobs)
```

**Endpoint único:** `POST /webhook/hubla` substitui `/webhook/purchase` funcionalmente.
`/webhook/purchase` mantido como alias (backward compat).

**UI — FlowDrawer:**
- Novo campo "Evento disparador" (select): `subscription.activated`, `subscription.created`, `lead.abandoned`, `subscription.deactivated`, `subscription.expiring`, `invoice.refunded`, outros
- Exemplos de uso:
  | Produto | Evento | Flow |
  |---|---|---|
  | MVS Shopee | `subscription.activated` | Boas-vindas MVS |
  | MVS Shopee | `lead.abandoned` | Recuperação de carrinho |
  | Comunidade Pro | `subscription.deactivated` | Retenção — volte |

---

## 6. Sistema de Leads Hubla

### 6.1 Motivação

A Hubla envia dezenas de tipos de eventos (533+ páginas de logs observadas). O sistema atual processa apenas `subscription.activated` e descarta dados valiosos:
- UTMs de campanha (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`)
- Dados financeiros (`lastInvoice.amount.totalCents`, método de pagamento)
- Facebook Pixel ID (`firstPaymentSession.cookies.fbp`)
- IP, User Agent, URL completa da sessão de compra
- Status history (`statusAt` array)
- Dados de offer/cohort

### 6.2 Novo Endpoint

**`POST /webhook/hubla`** — aceita todos os event types da Hubla.  
Autenticação idêntica ao `/webhook/purchase` (header `x-hubla-token`).

`/webhook/purchase` **mantido** para compatibilidade retroativa — internamente chama o mesmo handler.

**Deduplicação:** por `(event_type, subscription_id)` — mesmo evento não processado duas vezes.

### 6.3 Tabela `hubla_events`

Log imutável de cada evento recebido. Uma linha por evento.

| Campo | Tipo | Fonte |
|---|---|---|
| `id` | UUID PK | gerado |
| `account_id` | UUID | FK accounts |
| `event_type` | varchar(80) | `subscription.created`, `subscription.activated`, `lead.abandoned`, etc. |
| `hubla_subscription_id` | varchar(100) | `subscription.id` |
| `hubla_product_id` | varchar(100) | `product.id` |
| `product_name` | varchar(300) | `product.name` |
| `payer_phone` | varchar(30) | `payer.phone` |
| `payer_email` | varchar(200) | `payer.email` |
| `payer_name` | varchar(200) | `payer.firstName + lastName` |
| `contact_id` | UUID nullable | FK contacts (resolvido se existir contato com mesmo telefone) |
| `payload` | JSONB | payload bruto completo |
| `received_at` | datetime | NOW() |
| `processed_at` | datetime nullable | quando processado pelo worker |

**Índices:** `(account_id, event_type)`, `(account_id, hubla_subscription_id)`, `(contact_id)`

### 6.4 Tabela `leads`

Visão materializada do lead — atualizada via upsert a cada evento relevante.

| Campo | Tipo | Fonte |
|---|---|---|
| `id` | UUID PK | gerado |
| `account_id` | UUID | FK accounts |
| `hubla_subscription_id` | varchar(100) | unique per account |
| `contact_id` | UUID nullable | FK contacts |
| `payer_phone` | varchar(30) | `payer.phone` |
| `payer_name` | varchar(200) | `payer.firstName + lastName` |
| `payer_email` | varchar(200) | `payer.email` |
| `payer_document` | varchar(20) nullable | CPF/CNPJ |
| `hubla_product_id` | varchar(100) | |
| `product_name` | varchar(300) | |
| `offer_id` | varchar(100) nullable | `products[].offers[].id` |
| `offer_name` | varchar(300) nullable | `products[].offers[].name` |
| `amount_total_cents` | integer nullable | `lastInvoice.amount.totalCents` |
| `amount_subtotal_cents` | integer nullable | `lastInvoice.amount.subtotalCents` |
| `payment_method` | varchar(50) nullable | `credit_card`, `pix`, etc. |
| `subscription_status` | varchar(30) | `active`, `inactive`, `refunded`, `cancelled` |
| `utm_source` | varchar(200) nullable | `firstPaymentSession.utm.source` |
| `utm_medium` | varchar(200) nullable | `firstPaymentSession.utm.medium` |
| `utm_campaign` | varchar(500) nullable | `firstPaymentSession.utm.campaign` |
| `utm_content` | varchar(500) nullable | `firstPaymentSession.utm.content` |
| `utm_term` | varchar(200) nullable | `firstPaymentSession.utm.term` |
| `session_ip` | varchar(50) nullable | `firstPaymentSession.ip` |
| `session_url` | text nullable | `firstPaymentSession.url` |
| `fbp` | varchar(100) nullable | `firstPaymentSession.cookies.fbp` |
| `first_seen_at` | datetime | timestamp do primeiro evento |
| `activated_at` | datetime nullable | quando `subscription.activated` chegou |
| `last_event_at` | datetime | atualizado a cada evento |
| `last_event_type` | varchar(80) | tipo do evento mais recente |
| `created_at` | datetime | |
| `updated_at` | datetime | |

**Unique:** `(account_id, hubla_subscription_id)`  
**Índices:** `(account_id, payer_phone)`, `(account_id, subscription_status)`, `(account_id, utm_source)`, `(account_id, activated_at)`

### 6.5 Lógica de Processamento por Tipo de Evento

Todos os eventos passam pelo mesmo fluxo no handler:

```
1. Cria HublaEvent (log imutável)
2. Upsert Lead (UTMs, valor, status)
3. Resolve Contact por telefone (cria se não existir)
4. Busca FollowupFlows WHERE product_id = ? AND trigger_event_type = event.type AND is_active = true
5. Para cada flow:
     a. Verifica se contact tem conversa ABERTA no ChatNexo
        → Se sim: usa conversation_id existente
        → Se não: cria nova conversa no ChatNexo agora
     b. Cria FollowupEnrollment com o conversation_id resolvido
     c. Agenda FollowupSteps como jobs
```

Se o evento for `subscription.activated`, além do fluxo acima também executa o `PurchaseHandler` existente (welcome message, access case).

**Campo adicional em `FollowupFlow`:**
- `trigger_event_type` varchar(80), default `'subscription.activated'`, NOT NULL
- Migration: `ALTER TABLE followup_flows ADD COLUMN trigger_event_type VARCHAR(80) NOT NULL DEFAULT 'subscription.activated'`

**Novo handler:** `src/interface/worker/handlers/hubla_event.py`  
**Novo job kind:** `"hubla_event"` (o job `"purchase"` continua como alias para backward compat)

### 6.6 Endpoints Admin

```
GET  /admin/leads               → lista paginada
     params: product_id, status, utm_source, date_from, date_to, page, page_size
     response: [LeadListItem] + total, page info

GET  /admin/leads/{id}          → detalhe do lead
     inclui: dados completos + lista de hubla_events ordenada por received_at

GET  /admin/leads/export        → CSV download
     params: mesmos filtros do GET /admin/leads
     Content-Disposition: attachment; filename="leads-{date}.csv"
     Campos CSV: nome, telefone, email, cpf, produto, valor_total, status,
                 utm_source, utm_campaign, data_primeiro_evento, data_ativacao
```

### 6.7 Página `/leads` no Admin

**Rota:** `/(admin)/leads/page.tsx`

**Layout:**
- Header: título "Leads" + botão "Exportar CSV"
- Filtros: select produto, select status (ativado / abandonado / cancelado / todos), date range, input UTM source
- Tabela: nome, telefone, produto, valor (formatado em R$), status badge, utm_source, data
- Paginação
- Click em linha → drawer lateral com timeline de eventos (`hubla_events`) daquele lead

**Status badges:**
- `active` → verde "Ativado"
- `inactive` / `abandoned` → amarelo "Abandonado"
- `refunded` → laranja "Reembolsado"
- `cancelled` → vermelho "Cancelado"

---

## 7. Ordem de Implementação Recomendada (Opção B)

| PR | Conteúdo | Risco |
|---|---|---|
| PR 1 | Bug fix regex + design system global (já implementado nesta session) | ✅ Feito |
| PR 2 | Rename Cursos → Produtos (migration + API + frontend completo) | Médio |
| PR 3 | Trigger-based follow-up: `trigger_event_type` no Flow + `FlowDrawer` atualizado + handler unificado `/webhook/hubla` | Médio-Alto |
| PR 4 | Sistema de Leads — tabelas `hubla_events` + `leads`, upsert no handler | Médio |
| PR 5 | Frontend `/leads` — página paginada, filtros, exportação CSV, drawer timeline | Baixo |

---

## 8. Impacto em Testes

- `tests/unit/` — verificar regex novo detecta `{{name}}` e `{{0}}`
- Novos testes unitários: `HublaEventParser.parse()` com payload `subscription.created` completo (UTMs, invoice, offers)
- Teste do handler unificado: evento `subscription.activated` ainda cria contato + conversa + enrollment
- Teste: evento `lead.abandoned` sem conversa existente → cria conversa → enrollment
- Teste: `GET /admin/leads` com filtros e exportação CSV
- Teste migration: `followup_flows.trigger_event_type` default `subscription.activated` em rows existentes
