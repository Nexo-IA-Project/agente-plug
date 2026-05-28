# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Regra de Credenciais (OBRIGATÓRIO)

**Toda credencial, chave de API, URL de serviço ou variável de ambiente DEVE estar em `.env.local`.** O `.env.example` é o modelo público (sem valores reais). Sempre que adicionar uma variável nova:
1. Adicionar com valor real em `.env.local` (ignorado pelo git)
2. Adicionar a chave sem valor em `.env.example` (commitado como documentação)
3. Nunca hardcodar valores no código Python ou TypeScript

> Razão: as configurações são editáveis via página de settings da IA no frontend.

---

## Overview

Monorepo com backend Python (FastAPI + OpenAI function calling) e frontend Next.js 15. O produto é um agente de IA para suporte ao cliente integrado ao WhatsApp via ChatNexo.

- `apps/api/` — Backend Python, porta 8000
- `apps/web/` — Frontend Next.js 15, porta 3000

**13 subsistemas implementados (todos ✅ Concluídos):**  
Core · Capability Welcome · Capability Access · Capability Refund · Product Catalog · KB Admin · Capability Knowledge · Account Settings · Follow-up Engine (trigger-based) · Follow-up Flow Manager · Meta Template Manager · Hubla Event Bus · Lead System

**Branch `feat/favicon-logo-session` (Rename + Trigger + Leads):**
- **Rename Cursos → Produtos** em toda a stack: tabela `courses` → `products`, FK `course_id` → `product_id` em `followup_flows`, entidade `Course` → `Product`, hooks `useCourses` → `useProducts`, rota `/courses` → `/products` (redirect 301), pasta `features/courses/` → `features/products/`
- **Trigger-based follow-up**: `FollowupFlow` ganha `trigger_event_type` (Literal de 6 eventos Hubla: `subscription.activated`, `subscription.created`, `lead.abandoned`, `subscription.deactivated`, `subscription.expiring`, `invoice.refunded`); FlowDrawer mostra radio-grid colorido por semântica do funil; FlowCard tem trigger pill
- **`/webhook/hubla` unificado**: novo endpoint recebe TODOS os tipos de evento Hubla; `/webhook/purchase` mantido como alias (delegando para o mesmo pipeline); `HublaEventHandler` é único dono de enrollment (busca flows por `(product_id, trigger_event_type)`); `PurchaseHandler` reduzido a welcome + access case
- **Sistema de Leads Hubla**: novas tabelas `hubla_events` (log imutável, payload JSONB) e `leads` (visão materializada com UTMs/Pixel/IP/valor, upsert por `(account_id, hubla_subscription_id)`); página `/leads` no admin com tabela paginada, 5 filtros (produto, status, date range, UTM source), export CSV com BOM UTF-8 e drawer com timeline visual
- **Domain layer expandido**: novos `Lead` + `HublaEvent` entities + `LeadRepository` + `HublaEventRepository` Protocols
- **Constante single-tenant**: `shared/config/single_tenant.py::DEFAULT_ACCOUNT_UUID` substitui anti-pattern `select.limit(1)` em routers admin

**Branch anterior `feat/dynamic-followup-meta-templates`:**
- `FollowupStep` suporta `message_text` (texto livre) como alternativa ao template Meta
- Variáveis dinâmicas em `FollowupStep`: cada variável usa `StepVariableBinding` com 4 sources dinâmicos (`customer_name`, `product_name`, `contact_phone`, `contact_email`) ou `static` (valor fixo)
- Capability `Loja Express` foi descontinuada — Loja Express agora é apenas mais um produto no catálogo (sem D+0/D+1/D+3/D+5/D+7 hardcoded); seed migration converte os flows existentes
- `meta_waba_id` editável em Account Settings (não só .env)
- `/templates`: listagem full-width + modal de criação com efeito scale-from-center
- `/followup` e `/products`: usam **Drawer compartilhado** (`shared/components/Drawer`) — substitui o modal anterior

---

## Backend (`apps/api/`)

### Comandos

```bash
# Instalar dependências (executar de apps/api/)
uv sync

# Dev server (executar de apps/api/)
uv run uvicorn main:app --reload

# Worker (em outro terminal, executar de apps/api/)
uv run python -m worker

# Migrations (executar de apps/api/)
uv run alembic upgrade heads   # ← heads (plural) — histórico multi-branch

# Testes
uv run pytest                        # todos
uv run pytest tests/unit             # apenas unitários
uv run pytest tests/integration      # requer postgres+redis rodando
uv run pytest -k "nome_do_teste"     # filtrar por nome
uv run pytest --cov=src              # com cobertura

# Linting e formatação
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

### Arquitetura Clean Architecture

```
apps/api/src/
├── main.py                      # FastAPI app factory + lifespan
├── agent/
│   ├── guards/                  # Guards de validação (reembolso, retenção)
│   └── skills/                  # 8 skills do agente (ver seção Skills)
├── interface/
│   ├── http/
│   │   ├── routers/
│   │   │   ├── admin/           # 9 routers: auth, settings, api_tokens, documents,
│   │   │   │                    #   search, meta_templates, followup, products, leads, dlq
│   │   │   ├── webhook_message.py
│   │   │   ├── webhook_purchase.py
│   │   │   ├── metrics.py
│   │   │   └── health.py
│   │   ├── deps/                # AdminAuth, require_admin
│   │   └── errors.py            # Error handlers
│   └── worker/
│       └── handlers/            # Handlers de jobs (message, purchase, scheduled)
├── shared/
│   ├── adapters/
│   │   ├── cademi/              # CademiClient — API de alunos LMS
│   │   ├── chatnexo/            # ChatNexoClient — envio de mensagens WhatsApp
│   │   ├── clock/               # Abstração de tempo (testável)
│   │   ├── crypto/              # Fernet encryption para credenciais
│   │   ├── db/
│   │   │   ├── models.py        # Todos os SQLAlchemy models
│   │   │   ├── session.py       # session_scope, get_sessionmaker
│   │   │   ├── queue.py         # PostgresJobQueue
│   │   │   └── repositories/   # 1 repo por aggregate root
│   │   ├── hubla/               # Parsing de payload de compra
│   │   ├── kb/                  # Chunking, embedding, pgvector search
│   │   ├── llm/                 # OpenAI client wrapper
│   │   ├── meta/                # MetaClient — templates e envio
│   │   ├── observability/       # Structured logging, Prometheus metrics
│   │   └── redis/               # RedisDedup, get_redis
│   ├── application/
│   │   ├── use_cases/
│   │   │   ├── admin/           # Use cases de admin (KB upload, settings)
│   │   │   ├── knowledge/       # RAG: busca 4 tentativas + sinônimos
│   │   │   ├── refund/          # Reembolso + CDC + retenção
│   │   │   └── followup/        # EnrollContact, DispatchFollowupStep, VariableResolver
│   │   ├── message_dispatcher.py # Roteamento de mensagens recebidas
│   │   ├── purchase_handler.py   # Processamento de compras Hubla
│   │   └── lifecycle_handler.py  # Idle ping / close de conversas
│   ├── config/
│   │   └── settings.py          # Pydantic BaseSettings — lê .env.local → .env
│   └── domain/
│       ├── entities/            # Contact, Conversation, Message, etc.
│       ├── events/              # Domain events
│       ├── policies/            # Regras de negócio (ex: eligibility)
│       ├── ports/               # Interfaces (abstrações) para adapters
│       └── value_objects/       # Phone, Email, etc.
```

**Camadas:**
- `domain` — entidades, ports (interfaces), value objects — zero dependências externas
- `shared/adapters` — implementações concretas (DB, Redis, APIs)
- `shared/application` — casos de uso, handlers de jobs
- `interface` — routers HTTP (FastAPI), handlers de worker, schemas Pydantic

### Fluxo de Mensagem

```
ChatNexo → POST /webhook/message
  → WebhookEventRepository (dedup Redis + save)
  → PostgresJobQueue.enqueue(kind="message")
  → Worker.poll() → handle_message()
    → OpenAI agent loop (function calling)
      → skills selecionadas pelo LLM
        → use cases / repositories
    → ChatNexoClient.send_message()
```

O agente usa **OpenAI function calling** (não LangGraph). O `message_dispatcher.py` monta o contexto, chama a API OpenAI em loop até o LLM não emitir mais tool calls, e acumula a resposta.

### Skills do Agente

Cada skill: `src/agent/skills/<nome>/skill.py` (definição), `use_case.py` (lógica), `preconditions.py` (guards), `instructions.md` (system prompt). O `skill_loader.py` descobre dinamicamente.

| Skill | Propósito |
|---|---|
| `buscar_aluno_cademi` | Busca dados do aluno na API Cademi por CPF/email |
| `buscar_conhecimento` | RAG: busca no KB com keyword extraction (4 tentativas) |
| `buscar_conhecimento_com_contexto` | RAG com contexto da conversa atual |
| `enviar_link_acesso` | Envia link de acesso ao produto por email |
| `escalar_para_humano` | Escala conversa para agente humano |
| `oferecer_retencao` | Oferece retenção (bônus/extensão) antes do reembolso |
| `processar_reembolso` | Processa reembolso com Guards + CDC 7 dias |
| `verificar_elegibilidade_reembolso` | Verifica elegibilidade (CDC, duplicata, status) |

### Banco de Dados — Tabelas

| Tabela | Propósito |
|---|---|
| `accounts` | Tenants multi-tenant |
| `contacts` | Clientes (phone único por account) |
| `conversations` | Sessões de conversa WhatsApp |
| `messages` | Histórico de mensagens |
| `webhook_events` | Dedup e log de webhooks recebidos |
| `scheduled_jobs` | Jobs agendados (D+1, D+3, etc.) |
| `job_queue` | Fila de jobs (processamento async) |
| `job_dlq` | Dead-letter queue |
| `capability_executions` | Log de execuções de skills |
| `audit_events` | Auditoria de ações admin |
| `users` | Usuários do painel — roles `admin`/`operator`, avatar bytea, `must_change_password`, `is_active`, `last_login_at` |
| `smtp_config` | Configuração SMTP por conta — senha criptografada Fernet, 1 registro por conta |
| `integration_configs` | Credenciais de integrações (Fernet encrypted) |
| `knowledge_documents` | Metadados de documentos KB |
| `knowledge_chunks` | Chunks com embedding pgvector (1536 dims) |
| `kb_usage_logs` | Log de buscas no KB |
| `access_cases` | Casos de acesso a produto |
| `refund_cases` | Casos de reembolso |
| `products` | Catálogo de produtos (`name`, `hubla_id`, `is_active`) — vincula flows a produtos |
| `hubla_events` | Log imutável de cada evento Hubla recebido (payload JSONB, FK contact_id) |
| `leads` | Visão materializada de lead — upsert por `(account_id, hubla_subscription_id)`, captura UTMs/Pixel/IP/valor/método |
| `conversation_messages` | Thread OpenAI por conversa (JSONB) |
| `api_tokens` | Tokens de API (hash + prefix `nxia_XXXX`) |
| `meta_templates` | Templates WhatsApp aprovados na Meta |
| `followup_flows` | Flows de follow-up (name, `product_id` FK, `trigger_event_type`, is_active) |
| `followup_steps` | Steps de um flow (delay_hours, template ou message_text para texto livre, template_variables com `StepVariableBinding`) |
| `followup_enrollments` | Inscrição de contato em um flow |
| `followup_enrollment_steps` | Execução de cada step do enrollment |

**Migrations:** `apps/api/migrations/versions/` — 20 arquivos. Usar `alembic upgrade heads` (plural, dois heads ativos por merge de branches).

**token_prefix:** Campo em `api_tokens` armazena os primeiros 9 chars do token raw (`nxia_XXXX`) para exibição no painel. Tokens existentes antes da migration `c4d5e6f7a8b9` têm prefix `null` e mostram "—".

**meta_waba_id:** Agora é campo de `IntegrationConfig` (armazenado no JSONB `accounts.settings`), editável na UI de Settings. O fallback ainda lê `META_WABA_ID` do `.env.local` se não configurado na UI.

**FollowupStep.message_text:** Campo nullable adicionado na migration `d1e2f3a4b5c6`. Steps com `message_text` enviam texto livre via `send_message`; steps com `meta_template_name` enviam template.

**Product catalog (`b5c6d7e8f9a0_dynamic_followup_by_course` + `42c2b623d919_rename_courses_to_products`):** Cria tabela `products` (originalmente `courses`, renomeada em `42c2b623d919`), dropa `loja_express_cases`, remove `product_tags`/`position` de `followup_flows` e adiciona `product_id` (FK NOT NULL com `ON DELETE RESTRICT`). Snapshots de `product_name`/`step_meta_template_name`/`step_message_text` em `followup_enrollments`/`followup_enrollment_steps` mantêm histórico mesmo após edições.

**Trigger-based follow-up (`2c5504aac687_add_trigger_event_type_to_flows`):** Adiciona `trigger_event_type` (VARCHAR(80), NOT NULL, server_default `'subscription.activated'`) em `followup_flows`. Cada flow declara qual evento Hubla o dispara. Validação via Pydantic `Literal[HublaEventType]` dos 6 eventos suportados.

**Sistema de Leads Hubla (`83ff9745e1a6` + `db857b9fe716` + `4fce596ca642`):** Cria `hubla_events` (log imutável, payload JSONB, FK contact_id) e `leads` (visão materializada, unique key `(account_id, hubla_subscription_id)`). Captura UTMs (source/medium/campaign/content/term), valores (totalCents/subtotalCents), sessão (IP/URL/fbp), payment_method, subscription_status. Upsert preserva UTMs originais; só atualiza status/contact_id/activated_at/last_event_*. Índices: `(account_id, event_type)`, `(account_id, hubla_subscription_id)`, `(contact_id)`, `(account_id, payer_phone)`, `(account_id, subscription_status)`, `(account_id, utm_source)`, `(account_id, activated_at)`.

**StepVariableBinding:** `followup_steps.template_variables` agora é um dict `{nome_variavel: {source, value?}}` onde `source` é um dos 4 dinâmicos (`customer_name`, `product_name`, `contact_phone`, `contact_email`) ou `static` (com `value` obrigatório). Resolvido em runtime pelo `VariableResolver` ao despachar o step.


### Endpoints HTTP

**Auth Admin (`/admin`)**
```
POST /admin/auth/login          → JWT cookie (HttpOnly) + payload inclui role, user_id, must_change_password
POST /admin/auth/logout         → deleta cookie
```

**Usuários (`/admin`) — require_admin_role para ações de gestão**
```
GET    /admin/users                    → UserListResponse (paginado)
POST   /admin/users                    → UserResponse (201) — gera senha, envia email
PUT    /admin/users/{id}               → UserResponse — edita name/role/is_active
DELETE /admin/users/{id}               → 204 — não pode deletar si mesmo nem último admin
POST   /admin/users/{id}/reset-password → 204 — gera nova senha, envia email

GET    /admin/me                → perfil do usuário logado
PUT    /admin/me                → atualiza nome (email imutável)
PUT    /admin/me/avatar         → recebe base64 JPEG → salva bytea
GET    /admin/me/avatar         → serve bytea como image/jpeg
PUT    /admin/me/password       → troca senha (requer senha atual)
```

**SMTP Config (`/admin`) — require_admin_role**
```
GET    /admin/smtp-config        → config (sem senha) ou null
PUT    /admin/smtp-config        → upsert — senha criptografada Fernet
POST   /admin/smtp-config/test   → envia email de teste
```

**Account Settings (`/admin`)**
```
GET  /admin/settings            → AccountSettings
PUT  /admin/settings            → AccountSettings (atualiza)
```

**API Tokens (`/admin`)**
```
POST   /admin/api-tokens        → {id, name, raw_token, created_at} (201)
GET    /admin/api-tokens        → [TokenListItem] (sem raw_token)
DELETE /admin/api-tokens/{id}   → 204 | 404
```

**Knowledge Base (`/admin`)**
```
GET    /admin/documents                     → lista com paginação
POST   /admin/documents/upload              → 202 Accepted (async)
GET    /admin/documents/{id}                → detalhes
DELETE /admin/documents/{id}                → 204
POST   /admin/documents/{id}/reindex        → 501 Not Implemented
POST   /admin/search/test                   → busca teste no KB
```

**Courses (`/admin`)**
```
GET    /admin/products          → [Product] (com flow_count)
POST   /admin/products          → Product (201) | 409 se hubla_id duplicado
PUT    /admin/products/{id}     → Product | 404
DELETE /admin/products/{id}     → 204 | 409 se houver flows vinculados
```

**Follow-up (`/admin`)**
```
GET    /admin/followup/flows                → [FollowupFlow] (inclui product summary + trigger_event_type)
POST   /admin/followup/flows               → FollowupFlow (201) — exige product_id e trigger_event_type
PUT    /admin/followup/flows/{id}          → FollowupFlow
DELETE /admin/followup/flows/{id}          → 204
GET    /admin/followup/flows/{id}/steps    → [FollowupStep]
POST   /admin/followup/flows/{id}/steps   → FollowupStep (201)
PUT    /admin/followup/flows/{id}/steps/{step_id}   → FollowupStep
DELETE /admin/followup/flows/{id}/steps/{step_id}   → 204
PATCH  /admin/followup/flows/{id}/steps/reorder     → 204
```

**Meta Templates (`/admin`)**
```
GET  /admin/meta-templates      → [MetaTemplate]
POST /admin/meta-templates      → MetaTemplate (cria na Meta API)
```

**Dead-Letter Queue (`/admin`)**
```
GET    /admin/dlq               → lista com paginação
DELETE /admin/dlq/{id}          → 204
POST   /admin/dlq/{id}/requeue  → move back para job_queue
POST   /admin/dlq/requeue-all   → requeue em batch
```

**Leads (`/admin`)**
```
GET    /admin/leads             → LeadListResponse (paginado)
                                  params: product_id, status, utm_source, date_from, date_to, page, page_size
GET    /admin/leads/{id}        → LeadDetailResponse (com timeline de hubla_events)
GET    /admin/leads/export      → CSV download (UTF-8 com BOM, Content-Disposition attachment)
                                  mesmos filtros da listagem
```

**Webhooks**
```
POST /webhook/message           → 202 (ChatNexo, Bearer token)
POST /webhook/hubla             → 202 (Hubla, token query string) — endpoint unificado, qualquer event type
POST /webhook/purchase          → 202 (Hubla, token query string) — alias legado, delega para handle_hubla_event
```

**Infra**
```
GET /health                     → {"status": "ok"}
GET /metrics                    → Prometheus text/plain
```

### Worker — Tipos de Jobs

O worker (`python -m worker`) faz poll na `job_queue` e despacha por `kind`:

| `kind` | Handler | Descrição |
|---|---|---|
| `message` | `handle_message` | Processa mensagem recebida: agent loop + resposta |
| `hubla_event` | `handle_hubla_event` | **Pipeline unificado** de eventos Hubla: grava `hubla_events` (log) + upsert `leads` (UTMs/Pixel/IP/valor) + resolve `Product` por `hubla_id` + enrolla em flows com `trigger_event_type` matching + `mark_processed` em `finally` |
| `purchase` | `handle_purchase` | **Alias legado** — delega para `handle_hubla_event` sintetizando `type=subscription.activated` quando ausente |
| `scheduled_welcome` | `handle_scheduled` | Welcome D+1 para novos alunos |
| `followup_step` | `handle_scheduled` | Despacha step de followup flow (Meta template ou texto livre) com variáveis resolvidas pelo `VariableResolver` |
| `resync_flow` | `handle_resync_flow` | Re-sincroniza enrollments de um flow após edição de steps |

### Configuração — Settings

`src/shared/config/settings.py` (Pydantic BaseSettings, lê `.env.local` → `.env`)

**Obrigatórias:**
```
DATABASE_URL, REDIS_URL, OPENAI_API_KEY
CHATNEXO_BASE_URL, CHATNEXO_API_KEY
HUBLA_WEBHOOK_SECRET
ADMIN_API_KEY, META_API_KEY
INTEGRATION_CREDENTIALS_KEY (Fernet key)
JWT_SECRET
```

**Comportamento do agente:**
```
IDLE_PING_MINUTES=30, IDLE_CLOSE_MINUTES=20
INTENT_CONFIDENCE_THRESHOLD=0.7
MESSAGE_BUFFER_WAIT_SECONDS=0
```

**Cademi:**
```
CADEMI_API_URL, CADEMI_API_KEY
CADEMI_MAX_RETRIES=3, CADEMI_RETRY_BASE_SECONDS=1.0
```

**Knowledge Base:**
```
KB_CHUNK_SIZE=512, KB_CHUNK_OVERLAP=50
KB_TOP_K=5, KB_THRESHOLD=0.55
KB_EMBEDDING_MODEL=text-embedding-3-small
KB_MAX_FILE_SIZE_MB=20
```

**Capabilities:**
```
WELCOME_CHECK_DELAY_HOURS=1, WELCOME_D1_DELAY_HOURS=24
REFUND_DEADLINE_DAYS=7, REFUND_MUTEX_TTL_SECONDS=3600
```

**JWT:** `JWT_EXPIRE_MINUTES=60`

**Meta:** `META_WABA_ID` (obrigatório para envio de templates)

### Serviços externos

| Serviço | Variável | Propósito |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | LLM inference (agent loop) + embeddings (RAG) |
| ChatNexo | `CHATNEXO_BASE_URL` + `CHATNEXO_API_KEY` | Webhook de entrada + envio de mensagens |
| Hubla | `HUBLA_WEBHOOK_SECRET` | Webhook de compras |
| Cademi | `CADEMI_API_URL` + `CADEMI_API_KEY` | LMS: busca de alunos por CPF/email |
| Meta | `META_API_KEY` + `META_WABA_ID` | WhatsApp: criação e envio de templates |

---

## Frontend (`apps/web/`)

### Comandos

```bash
cd apps/web
npm run dev      # Turbopack, porta 3000
npm run build    # build de produção (Next.js standalone output)
npm run lint     # ESLint
```

### Páginas (App Router)

```
/                                → redireciona para /dashboard (ou /login)
/(auth)/login                    → login com JWT cookie

/(admin)/dashboard               → painel principal
/(admin)/accounts                → gerenciar contas
/(admin)/kb                      → Knowledge Base (lista documentos)
/(admin)/products                → catálogo de produtos (CRUD com drawer)
/(admin)/courses                 → redirect 301 → /products (backward compat)
/(admin)/leads                   → leads paginados com 5 filtros, CSV export, drawer com timeline visual
/(admin)/followup                → lista de followup flows (filtrável por produto)
/(admin)/followup/[id]           → editor de flow + steps inline
/(admin)/settings                → configurações da conta (OPENAI_API_KEY, ChatNexo, etc) + SMTP (só admin)
/(admin)/settings/tokens         → gerenciar API tokens (criar, listar, revogar)
/(admin)/users                   → lista de usuários (só admin) com CRUD, reset de senha e toggle ativo/inativo
/(admin)/profile                 → perfil do usuário logado: nome, avatar com crop, troca de senha
/(admin)/change-password         → troca obrigatória de senha no primeiro login (bloqueio até concluir)
/(admin)/templates               → lista de Meta templates
/(admin)/templates/new           → criar novo template
```

### Feature Modules

Cada feature é autocontida em `src/features/<domínio>/`:
```
features/
  accounts/     → Gerenciar contas da plataforma
  products/     → Catálogo de produtos (CRUD via drawer, vincula flows a produtos Hubla)
  leads/        → Listagem/detalhe/export de leads + drawer com timeline (consome `getTriggerEventMeta` do followup)
  dashboard/    → Dashboard com estatísticas
  followup/     → Criar/editar flows e steps (drag-and-drop de steps, variáveis dinâmicas)
  kb/           → Upload e busca de documentos KB
  settings/     → Configurações de integração e comportamento da IA
  templates/    → CRUD de Meta WhatsApp templates com preview ao vivo
```

Componente compartilhado **`shared/components/Drawer`**: drawer modal único usado pelas features `products`, `followup` e `leads` (substitui modais antigos). Cresce do centro com efeito scale-from-center, fecha por ESC ou clique fora.

**Identidade visual de eventos Hubla:** `features/followup/lib/triggerEvents.ts` é single source of truth — define cor, ícone Material Symbols, label PT-BR e descrição para cada um dos 6 eventos (`subscription.activated`=emerald, `subscription.created`=sky, `lead.abandoned`=amber, `subscription.deactivated`=rose, `subscription.expiring`=orange, `invoice.refunded`=violet). Consumido por `FlowDrawer` (radio-grid 2×3), `FlowCard` (trigger pill) e `LeadDrawer` (timeline com bolinhas coloridas).

Estrutura padrão por feature:
```
features/<domínio>/
  components/   ← componentes React do domínio
  types.ts      ← tipos TypeScript (DTOs, interfaces)
  hooks/        ← custom hooks (se necessário)
```

Layout e componentes compartilhados: `src/shared/components/layout/` (Sidebar, TopBar, ThemeToggle)

### Design System NexoIA

- **Tokens de cor:** CSS custom properties em `globals.css` (`:root` light / `.dark` dark)
- **Tailwind:** referencia via `var(--color-*)` em `tailwind.config.ts`
- **Regra:** usar sempre tokens semânticos — `bg-surface-container`, `text-on-surface`, `text-on-surface-variant`, `border-outline-variant`, etc. **Nunca hex hardcoded.**
- **Tema:** dark/light via `next-themes` com `defaultTheme="dark"`
- **Toasts:** `useToast` (wrapa sonner) — `toast.success()`, `toast.error()`, `toast.warning()`, `toast.info()`
- **Ícones:** Material Symbols Outlined via CSS import em `globals.css` — usar `<span className="material-symbols-outlined">{nome_do_icone}</span>`

**Atenção:** `/kb/page.tsx` usa estilo antigo — ainda não migrada para o design system NexoIA.

### API Client (`src/lib/api.ts`)

Toda comunicação com o backend passa por `apiFetch()` que:
- Adiciona `Authorization: Bearer <token>` automático
- Adiciona `Content-Type: application/json` para body strings
- Trata 204 (retorna `undefined`)
- Lança `Error` para status não-ok

Funções exportadas: `listDocuments`, `uploadDocument`, `deleteDocument`, `listApiTokens`, `createApiToken`, `revokeApiToken`, `getAccountSettings`, `updateAccountSettings`, `listFollowupFlows`, `createFollowupFlow`, `updateFollowupFlow`, `deleteFollowupFlow`, `listFollowupSteps`, `createFollowupStep`, `updateFollowupStep`, `deleteFollowupStep`, `reorderFollowupSteps`, `listProducts`, `createProduct`, `updateProduct`, `deleteProduct`, `listLeads`, `getLead`, `downloadLeadsCsv`, `listMetaTemplates`, `createMetaTemplate`, `deleteMetaTemplate`, `uploadTemplateMedia`

---

## Docker Compose

**Desenvolvimento local:**
```bash
docker compose up                          # sobe postgres, redis, api, worker
docker compose up postgres redis           # só infra (para rodar api local com uv)
```

Serviços: `postgres` (5432), `redis` (6379), `api` (8000), `worker`

**Produção:** compose separado com perfis e variáveis de `.env.local`. Imagens buildadas pelo CI e pushadas para `ghcr.io`.

---

## CI/CD (GitHub Actions — `.github/workflows/deploy.yml`)

**Gates em todo push/PR:**

| Gate | Ferramenta |
|---|---|
| Lint & Format (api) | `ruff check` + `ruff format --check` |
| Type Check (api) | `mypy src` |
| Type Check (web) | `tsc --noEmit` |
| Tests (api) | `pytest tests/unit` + postgres/redis up |
| Security Audit (api) | `pip-audit` |
| Security Audit (web) | `npm audit` |
| Docker Build | build api + worker + web (smoke test) |

**Push para `main` (após gates):**
1. Build e push de imagens Docker → `ghcr.io` (tags: `sha-{short}`, `latest`)
2. Deploy no self-hosted runner:
   - `git pull` + `docker pull`
   - `alembic upgrade heads`
   - `docker compose up -d api worker web`
   - Health check do API (90s timeout)
   - Smoke test via Cloudflare Tunnel

---

## Documentação de Arquitetura

```
docs/superpowers/specs/    → design docs por subsistema (11 specs)
docs/superpowers/plans/    → planos de implementação com tasks detalhadas (14 planos)
docs/superpowers/INDEX.md  → índice dos 11 subsistemas (todos ✅ Concluídos)
```

Subsistemas documentados: Core, Welcome, Access, Refund, Course Catalog, KB Admin, Capability Knowledge, Account Settings, Follow-up Engine, Follow-up Flow Manager, Meta Template Manager.

---

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
