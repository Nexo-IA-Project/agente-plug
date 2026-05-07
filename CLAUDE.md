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

**11 subsistemas implementados (todos ✅ Concluídos):**  
Core · Capability Welcome · Capability Access · Capability Refund · Capability Loja Express · KB Admin · Capability Knowledge · Account Settings · Follow-up Engine · Follow-up Flow Manager · Meta Template Manager

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
│   │   │   │                    #   search, meta_templates, followup, dlq
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
│   │   ├── loja_express/        # LojaExpressClient
│   │   ├── meta/                # MetaClient — templates e envio
│   │   ├── observability/       # Structured logging, Prometheus metrics
│   │   └── redis/               # RedisDedup, get_redis
│   ├── application/
│   │   ├── use_cases/
│   │   │   ├── admin/           # Use cases de admin (KB upload, settings)
│   │   │   ├── knowledge/       # RAG: busca 4 tentativas + sinônimos
│   │   │   ├── loja_express/    # Follow-up D+0→D+7
│   │   │   ├── refund/          # Reembolso + CDC + retenção
│   │   │   └── followup/        # EnrollContact, DispatchFollowupStep
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
| `admin_users` | Usuários do painel (JWT login) |
| `integration_configs` | Credenciais de integrações (Fernet encrypted) |
| `knowledge_documents` | Metadados de documentos KB |
| `knowledge_chunks` | Chunks com embedding pgvector (1536 dims) |
| `kb_usage_logs` | Log de buscas no KB |
| `access_cases` | Casos de acesso a produto |
| `refund_cases` | Casos de reembolso |
| `loja_express_cases` | Casos de follow-up Loja Express |
| `conversation_messages` | Thread OpenAI por conversa (JSONB) |
| `api_tokens` | Tokens de API (hash + prefix `nxia_XXXX`) |
| `meta_templates` | Templates WhatsApp aprovados na Meta |
| `followup_flows` | Flows de follow-up (name, product_tags) |
| `followup_steps` | Steps de um flow (delay_hours, template) |
| `followup_enrollments` | Inscrição de contato em um flow |
| `followup_enrollment_steps` | Execução de cada step do enrollment |

**Migrations:** `apps/api/migrations/versions/` — 14 arquivos. Usar `alembic upgrade heads` (plural, dois heads ativos por merge de branches).

**token_prefix:** Campo em `api_tokens` armazena os primeiros 9 chars do token raw (`nxia_XXXX`) para exibição no painel. Tokens existentes antes da migration `c4d5e6f7a8b9` têm prefix `null` e mostram "—".

### Endpoints HTTP

**Auth Admin (`/admin`)**
```
POST /admin/auth/login          → JWT cookie (HttpOnly)
POST /admin/auth/logout         → deleta cookie
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

**Follow-up (`/admin`)**
```
GET    /admin/followup/flows                → [FollowupFlow]
POST   /admin/followup/flows               → FollowupFlow (201)
PUT    /admin/followup/flows/{id}          → FollowupFlow
DELETE /admin/followup/flows/{id}          → 204
GET    /admin/followup/flows/{id}/steps    → [FollowupStep]
POST   /admin/followup/flows/{id}/steps   → FollowupStep (201)
PUT    /admin/followup/flows/{id}/steps/{step_id}   → FollowupStep
DELETE /admin/followup/flows/{id}/steps/{step_id}   → 204
POST   /admin/followup/flows/{id}/reorder-steps     → 200
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

**Webhooks**
```
POST /webhook/message           → 202 (ChatNexo, Bearer token)
POST /webhook/purchase          → 202 (Hubla, x-hubla-token)
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
| `purchase` | `handle_purchase` | Processa compra Hubla: cria contact/conversation, agenda welcome |
| `scheduled_welcome` | `handle_scheduled` | Welcome D+1 para novos alunos |
| `scheduled_loja_express` | `handle_scheduled` | Follow-up D+0/D+1/D+3/D+5/D+7 Loja Express |
| `followup_step` | `handle_scheduled` | Despacha step de followup flow (Meta template) |

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
LOJA_EXPRESS_PRODUCT_TAGS=["loja_express","loja-express"]
LOJA_EXPRESS_D1/D3/D5/D7_DELAY_HOURS=24/72/120/168
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
/(admin)/followup                → lista de followup flows
/(admin)/followup/[id]           → editor de flow + steps
/(admin)/settings                → configurações da conta (OPENAI_API_KEY, ChatNexo, etc)
/(admin)/settings/tokens         → gerenciar API tokens (criar, listar, revogar)
/(admin)/templates               → lista de Meta templates
/(admin)/templates/new           → criar novo template
```

### Feature Modules

Cada feature é autocontida em `src/features/<domínio>/`:
```
features/
  accounts/     → Gerenciar contas da plataforma
  dashboard/    → Dashboard com estatísticas
  followup/     → Criar/editar flows e steps (drag-and-drop reorder)
  kb/           → Upload e busca de documentos KB
  settings/     → Configurações de integração e comportamento da IA
  templates/    → CRUD de Meta WhatsApp templates com preview ao vivo
```

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

Funções exportadas: `listDocuments`, `uploadDocument`, `deleteDocument`, `listApiTokens`, `createApiToken`, `revokeApiToken`, `getAccountSettings`, `updateAccountSettings`, `listFollowupFlows`, `createFollowupFlow`, `updateFollowupFlow`, `deleteFollowupFlow`, `listFollowupSteps`, `createFollowupStep`, `updateFollowupStep`, `deleteFollowupStep`, `reorderFollowupSteps`, `listMetaTemplates`, `createMetaTemplate`

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

Subsistemas documentados: Core, Welcome, Access, Refund, Loja Express, KB Admin, Capability Knowledge, Account Settings, Follow-up Engine, Follow-up Flow Manager, Meta Template Manager.

---

## Task Master AI Instructions
**Import Task Master's development workflow commands and guidelines, treat as if import is in the main CLAUDE.md file.**
@./.taskmaster/CLAUDE.md
