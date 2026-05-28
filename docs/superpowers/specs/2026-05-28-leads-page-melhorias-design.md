# Melhorias da página de Leads

**Data:** 2026-05-28
**Branch base:** `fix/edit-pending-and-loading-overlay`
**Escopo:** 6 melhorias na página `/leads` agrupadas em 5 frentes técnicas.

---

## Contexto

A página `/leads` (`apps/web/src/app/(admin)/leads/page.tsx`) lista leads vindos de eventos Hubla. Hoje:

- Filtros funcionam via REST polling sem real-time.
- Drawer compartilhado (`shared/components/Drawer.tsx`) é usado por Leads, Products e Onboarding Flows e apresenta um gap visual no topo.
- Não existe link para a conversa do contato no ChatNexo.
- Datepicker é `<input type="date">` nativo, inconsistente entre browsers.
- Lista mostra só data, sem hora.

A spec cobre 6 itens do usuário:

1. WebSocket/SSE em tempo real na lista e no drawer.
2. Link "Abrir conversa" no drawer apontando pra ChatNexo.
3. Drawer com top/bottom realmente zerados.
4. Drawer com seta de voltar no lugar do X e fechamento por clique fora.
5. Filtros funcionando + UI nova de filtros (modal com `/frontend-design`, datepicker bonito).
6. Data + hora na coluna "Último evento".

---

## Frente A — Real-time via SSE

### Backend

**Novo endpoint:** `GET /admin/leads/stream` em `apps/api/src/interface/http/routers/admin/leads.py`.

- Auth: cookie JWT existente (`require_admin`).
- Response: `text/event-stream`.
- Query params idênticos ao `GET /admin/leads`: `product_id`, `status`, `utm_source`, `date_from`, `date_to`.
- Heartbeat: comentário SSE (`: ping`) a cada 25s pra manter conexão atrás de proxy.

**Pub/sub via Redis** (já disponível em `shared/adapters/redis/`):

- Canal por conta: `leads:events:{account_id}`.
- Envelope JSON publicado:
  ```json
  {
    "type": "lead.upserted" | "lead.event.appended" | "lead.enrollment.updated",
    "is_new": true,
    "lead": { /* LeadSummary completo */ },
    "event": { /* opcional: LeadEventResponse */ },
    "enrollment": { /* opcional: snapshot do enrollment afetado */ }
  }
  ```

**Publisher injetado** no `HublaEventHandler` (`shared/application/hubla_event_handler.py`):

- Após `upsert_lead` + insert em `hubla_events` (mesma transação ou logo após o commit), publica envelope.
- `is_new` é determinado comparando `created_at == updated_at` do lead após o upsert.
- Quando enrollment step muda status (em `worker/handlers/scheduled.py` ou no `OnboardingDispatcher`), publica `lead.enrollment.updated`.

**Filtragem server-side:**

O endpoint mantém em memória os filtros da conexão. Para cada envelope recebido do Redis, avalia:

- `product_id` == `lead.hubla_product_id`
- `status` == `lead.subscription_status`
- `utm_source` substring case-insensitive em `lead.utm_source`
- `lead.last_event_at` entre `date_from` e `date_to` (inclusive)

Se passar, escreve no stream. Se não, descarta silenciosamente.

### Frontend

**Novo hook:** `apps/web/src/features/leads/hooks/useLeadsStream.ts`.

```ts
useLeadsStream(filters: LeadFilters, handlers: {
  onLeadUpserted: (lead: Lead, isNew: boolean) => void;
  onEventAppended: (leadId: string, event: LeadEvent) => void;
  onEnrollmentUpdated: (leadId: string, enrollment: FollowupEnrollment) => void;
}): { status: "connecting" | "open" | "reconnecting" | "closed" }
```

- Constrói URL com query params dos filtros.
- Abre `EventSource(url)`.
- `addEventListener` por tipo.
- Re-conecta automaticamente quando filtros mudam (fecha + reabre).
- Auto-reconnect built-in do EventSource trata desconexões.

**Integração em `page.tsx`:**

- `onLeadUpserted`: se `isNew`, insere no topo da lista local. Se não, encontra por `id` e substitui. Triggera fade highlight de 600ms via classe CSS condicional.
- Indicador no header: ponto verde piscando com tooltip do `status` do hook.

**Integração em `LeadDrawer.tsx`:**

- Mesmo hook (ou um derivado) escuta `lead.event.appended` e `lead.enrollment.updated` filtrados por `leadId` aberto.
- Atualiza `detail.events` (prepend) e `detail.enrollments` (substitui por id).

---

## Frente B — Drawer compartilhado

**Arquivo:** `apps/web/src/shared/components/Drawer.tsx`.

### Mudanças

1. **Z-indices subidos:**
   - Backdrop: `z-40` → `z-60`.
   - Painel: `z-50` → `z-70`.
   - Razão: a `TopBar` é `sticky top-0 z-40` e cria stacking context próprio. Em alguns browsers a TopBar fica visível "por cima" do painel, dando impressão de `top` afastado. Subir z-indices garante cobertura full-height.

2. **Ícone do botão de fechar:** `close` → `arrow_back`, com `aria-label="Voltar"`. Comportamento inalterado (chama `onClose`).

3. **Clique fora:** já implementado no backdrop (`onClick={onClose}`). Verificar e documentar — nenhuma mudança de código.

4. **Transição:** mantém `duration-300 ease-out`.

### Impacto colateral

Os 3 callers (`LeadDrawer`, `ProductDrawer`, `FlowDrawer`) herdam todas as mudanças sem alteração no call site.

---

## Frente C — Modal de filtros novo

### Header da página

Substitui a barra inline de filtros (`page.tsx:140-222`) por:

- **Botão "Filtros"** com ícone `filter_list` e badge contando filtros ativos (ex.: `Filtros · 3`).
- **Chips de filtros ativos** ao lado, cada um com X individual pra remover sem abrir o modal.

### Componente novo: `LeadFiltersModal.tsx`

Localização: `apps/web/src/features/leads/components/LeadFiltersModal.tsx`.

- Modal centralizado (NÃO drawer): cresce do centro com `scale-from-center`, ~640px de largura, animação 200ms.
- Fecha por ESC, clique fora, ou botão "Cancelar".
- Layout interno desenhado com `/frontend-design` no momento da implementação.
- Conteúdo:
  - **Produto** — `<select>` com produtos da conta (do `useProducts`).
  - **Status** — radio group com chips coloridos usando `getLeadStatusBadge`.
  - **Período** — date range com `DatePicker` custom (ver abaixo).
  - **UTM source** — input texto + sugestões dos últimos 10 UTMs vistos.
  - **Rodapé:** "Limpar tudo" (esquerda) + "Cancelar" / "Aplicar filtros" (direita).
- Aplica filtros só ao clicar "Aplicar" — não muda estado da lista enquanto o modal está aberto.

### Componente novo: `DatePicker.tsx` (reutilizável)

Localização: `apps/web/src/shared/components/DatePicker.tsx`.

- Substitui `<input type="date">` em todos os usos futuros.
- Lib: **`react-day-picker`** (~10kb, headless).
- Click no input abre popover com calendário de mês/ano.
- Modo range: clica início, clica fim. Visual de ponta + faixa colorida.
- Atalhos: "Hoje", "Últimos 7 dias", "Últimos 30 dias", "Este mês".
- Saída: dois `Date | undefined` (from, to).

### Backend novo (opcional, para sugestões de UTM)

`GET /admin/leads/utm-sources/suggest?q=`:

- Retorna até 10 valores distintos de `leads.utm_source` da conta, ordenados por frequência.
- Filtro opcional por substring `q` para autocompletion.

### Fix dos filtros que não filtram

Verificar e corrigir na implementação:

- **`product_id`**: o frontend hoje envia `p.hubla_id` (ex.: `"prod_abc"`) mas o backend espera string que é comparada com `lead.hubla_product_id`. Confirmar se está alinhado; se não, ajustar.
- **`date_from/date_to`**: hoje usa `.toISOString()` que converte pro UTC. Em fuso BR (UTC−3), um dia escolhido pode virar dia anterior. Solução: enviar ISO com offset `-03:00` explícito ou enviar só a data (`YYYY-MM-DD`) e parsear no backend usando timezone da conta.
- **`status`**: mapeia direto pra `subscription_status`; verificar se valores estão alinhados após o redesign.
- **`utm_source`**: validar case-insensitive no backend (`ILIKE`).

---

## Frente D — Botão "Abrir conversa" no drawer

### Backend

**Mudança em `LeadDetail` response** (em `apps/api/src/interface/http/routers/admin/leads.py`):

- Novo campo: `chatnexo_conversation_url: str | None`.

**Mudança em `LeadRepository.find_by_id()`** (`apps/api/src/shared/adapters/db/repositories/lead_repo.py`):

- JOIN com `conversations` por `contact_id`, pegando a mais recente (`ORDER BY created_at DESC LIMIT 1`).
- Carrega `AccountConfig` da conta atual (já temos repository).
- Monta a URL:
  ```python
  url = (
    f"{config.integration.chatnexo_base_url}"
    f"/app/accounts/{config.integration.chatnexo_account_id}"
    f"/inbox/{config.integration.chatnexo_inbox_id}"
    f"/conversations/{conversation.chatnexo_conversation_id}"
  )
  ```
- Se o lead não tem `contact_id` ou não tem conversa, retorna `None`.

### Frontend

**Em `LeadDrawer.tsx`** (após o card header, antes do grid de info):

- Botão "Abrir conversa no ChatNexo" com ícones `chat` + `open_in_new`.
- Renderiza só se `detail?.chatnexo_conversation_url` existir.
- Markup: `<a href={url} target="_blank" rel="noopener noreferrer" className="...">`.
- Se não existir conversa: botão **desabilitado** com tooltip "Aguardando primeira mensagem".

---

## Frente E — Data + hora na lista

**Arquivo:** `apps/web/src/app/(admin)/leads/page.tsx:26-28`.

Trocar:

```ts
function formatDate(d: string): string {
  return new Date(d).toLocaleDateString("pt-BR");
}
```

Por (mesmo padrão de `LeadDrawer.formatDateTime`):

```ts
function formatDateTime(d: string): string {
  return new Date(d).toLocaleString("pt-BR", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}
```

Aplica na coluna "Último evento" da tabela.

---

## Arquivos afetados (resumo)

### Backend (`apps/api/`)

- `src/interface/http/routers/admin/leads.py` — endpoint `/stream`, sugestão de UTMs, campo `chatnexo_conversation_url` no detail.
- `src/shared/application/hubla_event_handler.py` — publica envelope no Redis após upsert.
- `src/shared/adapters/db/repositories/lead_repo.py` — JOIN com conversations + monta URL no `find_by_id`.
- `src/shared/adapters/redis/` — possível novo helper de pub/sub se necessário.
- `src/interface/worker/handlers/scheduled.py` ou `OnboardingDispatcher` — publica `lead.enrollment.updated` quando step muda.

### Frontend (`apps/web/`)

- `src/app/(admin)/leads/page.tsx` — chips de filtros, botão "Filtros", `formatDateTime`, integração com `useLeadsStream`, fade highlight.
- `src/shared/components/Drawer.tsx` — z-indices, ícone `arrow_back`.
- `src/features/leads/components/LeadDrawer.tsx` — botão "Abrir conversa", integração com SSE para timeline/enrollments.
- `src/features/leads/components/LeadFiltersModal.tsx` — **novo**.
- `src/features/leads/hooks/useLeadsStream.ts` — **novo**.
- `src/shared/components/DatePicker.tsx` — **novo**.
- `src/features/leads/types.ts` — campo `chatnexo_conversation_url` em `LeadDetail`.
- `src/lib/api.ts` — endpoint de sugestão de UTMs.
- `package.json` — adicionar `react-day-picker`.

---

## Decisões registradas

- **SSE > WebSocket**: feed é unidirecional servidor→cliente, EventSource tem auto-reconnect built-in, sem libs.
- **Filtro server-side**: cada conexão SSE avalia filtros em memória; envelope carrega `LeadSummary` completo.
- **Modal centralizado para filtros**, não drawer: distingue ação efêmera de filtragem de uma "edição" persistente.
- **Datepicker custom com `react-day-picker`**: substitui `<input type="date">` em todos os usos futuros.
- **Z-index do Drawer 60/70**: cobre `TopBar sticky z-40` de forma consistente entre browsers.
- **Link ChatNexo no detail response**: backend tem todos os dados (`chatnexo_base_url/account_id/inbox_id` em `AccountConfig` + `chatnexo_conversation_id` em `conversations`); frontend só renderiza.

---

## Fora de escopo

- Página interna `/conversations/[id]` (ficou explícito como tarefa separada futura).
- Migração de outros usos de `<input type="date">` pra `DatePicker` (criar o componente nesta spec, mas migrar outros lugares fica como tarefa separada).
- Notificação desktop / toast para novos leads em tempo real.
- Persistência de filtros no localStorage (pode entrar em iteração futura).
