# Integrações como hub de cards — Implementation Plan

> REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Só frontend (Next.js 15 + TS + Tailwind, NexoIA).

**Goal:** `/settings` vira hub de cards (ChatNexo, Pagamentos, WhatsApp); Pagamentos tem sub-hub de gateways; Hubla com URL de webhook condicional (revela suave ao salvar a chave, some ao limpar).

---

### Task 1: Componente `IntegrationCard` + hub `/settings`
**Files:** create `apps/web/src/features/settings/components/IntegrationCard.tsx`; modify `apps/web/src/app/(admin)/settings/page.tsx`.
- `IntegrationCard` props `{ icon?: string; iconSvg?: ReactNode; title; subtitle; status?: "active"|"soon"; href?: string; onClick?: () => void }`. Card quadrado/retangular: ícone em `bg-primary-container` (ou acinzentado se soon), título, subtítulo, badge "Ativo"/"Em breve". Hover sutil (`hover:border-primary/40 hover:shadow-sm`). Se `href` → `<Link>`; senão `<button onClick>`. Tokens NexoIA.
- `/settings`: dentro de `<RequirePermission perm="settings.view">`, header "Integrações" + grade `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4` com 3 cards: ChatNexo (`chat` → /settings/chatnexo), Pagamentos (`payments` → /settings/pagamentos), WhatsApp (SVG WhatsApp → /settings/whatsapp, status active). Remover render de ChatNexoSection/IntegrationSection do hub.
- [ ] tsc → commit

### Task 2: `/settings/chatnexo` e `/settings/whatsapp`
**Files:** create `apps/web/src/app/(admin)/settings/chatnexo/page.tsx`, `apps/web/src/app/(admin)/settings/whatsapp/page.tsx`.
- chatnexo: carrega getAccountSettings; header "ChatNexo" + link voltar (`/settings`); renderiza `<ChatNexoSection initial onSaved />`. Guard settings.view.
- whatsapp: carrega settings; header "WhatsApp" (ícone) + voltar; um card com os campos Meta via InlineEditField + useFieldSave: meta_api_key (secret), meta_waba_id, meta_app_id, alert_whatsapp_target (espelha os specs de IntegrationSection). Guard settings.view.
- [ ] tsc → commit

### Task 3: `/settings/pagamentos` (sub-hub) + cards "em desenvolvimento"
**Files:** create `apps/web/src/app/(admin)/settings/pagamentos/page.tsx`.
- Guard settings.view. Header "Pagamentos" + voltar (/settings). Grade de IntegrationCard: Hubla (status active, href /settings/pagamentos/hubla) + Hotmart, Kiwify, Eduzz, Asaas (status soon, onClick → toast.info "Integração em desenvolvimento"). Ícone genérico p/ cada (ex.: `payments`/`storefront`/`account_balance`), Hubla destacado.
- [ ] tsc → commit

### Task 4: `/settings/pagamentos/hubla` — config + URL condicional
**Files:** create `apps/web/src/app/(admin)/settings/pagamentos/hubla/page.tsx`; modify `apps/web/src/features/settings/components/HublaWebhookCard.tsx` (tornar a revelação controlável).
- Guard settings.view. Header "Hubla" + voltar (/settings/pagamentos). `canEdit = can("settings.edit_credentials")`.
- Card "Webhook da Hubla": explicação (texto pedido na spec) + campo `hubla_webhook_secret` (input secret) com botões **Salvar** (updateAccountSettings({hubla_webhook_secret: valor})) e **Limpar** (updateAccountSettings({hubla_webhook_secret: ""})). Estado local do valor + `saved` (a chave atual vem de getAccountSettings().hubla_webhook_secret). Se !canEdit → input read-only, sem botões.
- **Revelação condicional:** um wrapper com `overflow-hidden transition-all duration-300 ease-in-out` que fica `max-h-0 opacity-0` quando NÃO há chave salva e `max-h-[600px] opacity-100` quando há. Dentro, renderiza `<HublaWebhookCard />` (URL + copiar + instruções). Assim: salvar chave → revela suave; limpar → recolhe suave.
- `HublaWebhookCard`: remover a mensagem de erro "defina o Webhook Secret" (agora só aparece quando há chave). Pode receber prop opcional pra forçar refetch do token após salvar (ex.: key remount via `key={savedSecretPresent}` no pai) — garantir que ao salvar, o token/URL atualizem.
- [ ] tsc → commit

### Task 5: Verificação + PR
- [ ] `cd apps/web && npx tsc --noEmit` limpo.
- [ ] grep: `/settings` não renderiza mais ChatNexoSection/IntegrationSection inline; sub-rotas guardadas.
- [ ] requesting-code-review (foco: navegação, guards nas novas rotas, comportamento da URL Hubla, read-only p/ operador).
- [ ] push + PR (base main). NÃO mergear sem OK.

## Arquivos críticos
- `features/settings/components/IntegrationCard.tsx` (novo), `HublaWebhookCard.tsx`, `ChatNexoSection.tsx` (reuso)
- `app/(admin)/settings/page.tsx` + novas rotas chatnexo/whatsapp/pagamentos/pagamentos/hubla
