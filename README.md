# NexoIA Agent

Agente de suporte ao cliente com IA integrado ao WhatsApp via ChatNexo — monorepo com backend Python (FastAPI + OpenAI function calling) e frontend Next.js 15 (painel admin).

---

## URLs

| Ambiente | Serviço | URL |
|----------|---------|-----|
| **Produção** | API (backend) | `https://api-iag2.ianexo.com.br` |
| **Produção** | Painel admin (frontend) | `https://panel-iag2.ianexo.com.br` |
| **Dev (tunnel)** | API | `https://api-iag2-dev.ianexo.com.br` |
| **Dev (tunnel)** | Painel admin | `https://panel-iag2-dev.ianexo.com.br` |
| **Dev local** | API | `http://localhost:8000` |
| **Dev local** | Painel admin | `http://localhost:3001` |
| **Dev local** | API docs (Swagger) | `http://localhost:8000/docs` |
| **Dev local** | Métricas Prometheus | `http://localhost:8000/metrics` |

---

## Fluxo de mensagem

```
WhatsApp (aluno)
      │
      ▼
 ChatNexo
      │  POST /webhooks/message
      ▼
 FastAPI (API)
      │  valida, deduplica (Redis), grava evento
      │  enfileira job no PostgreSQL (FOR UPDATE SKIP LOCKED)
      ▼
 Worker (asyncio)
      │  lê job da fila
      │  adquire lead lock (Redis mutex — evita concorrência por lead)
      ▼
 handle_message()
      │
      ├─► GuardService
      │       LegalMentionGuard → bloqueia menções a Procon/advogado
      │       LoopDetectorGuard → detecta respostas repetidas
      │
      ├─► run_agent() ◄── OpenAI function calling loop
      │       │
      │       │  loop (até 10 iterações):
      │       │    1. build_system_prompt (identidade + regras + skills + facts)
      │       │    2. POST /chat/completions → OpenAI gpt-4o
      │       │    3. Se finish_reason = tool_calls:
      │       │         dispatch concurrent tool calls → Skills
      │       │    4. Se finish_reason = stop:
      │       │         retorna texto final
      │       │
      │       └── ConversationHistory (PostgreSQL)
      │               load(thread_id) / save(thread_id, messages)
      │
      ├─► Skills (function calling tools):
      │       buscar_aluno_cademi          → Cademi API
      │       verificar_caso_acesso        → PostgreSQL
      │       enviar_link_acesso           → Cademi API
      │       verificar_elegibilidade_reembolso → PostgreSQL + Hubla
      │       processar_reembolso          → Hubla API
      │       oferecer_retencao            → PostgreSQL
      │       buscar_conhecimento          → pgvector (RAG)
      │       buscar_conhecimento_com_contexto → pgvector (RAG)
      │       escalar_para_humano          → ChatNexo API (transfer)
      │
      └─► ChatNexo API
              send_message(account_id, conversation_id, text)
                    │
                    ▼
             WhatsApp (aluno recebe resposta)
```

### Fluxo de compra (Hubla webhook)

```
Hubla
  │  POST /webhooks/purchase
  ▼
FastAPI → valida token → enfileira job "purchase"
  ▼
Worker → handle_purchase() → cria AccessCase, boas-vindas WhatsApp
```

### Fluxo de idle check (scheduler)

```
Worker (SchedulerLoop, tick 10s)
  │  verifica jobs agendados em PostgreSQL
  ▼
IDLE_PING (30 min sem resposta) → envia ping ao aluno
IDLE_CLOSE (20 min após ping)   → encerra conversa
```

---

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.11, FastAPI, uv |
| LLM | OpenAI GPT-4o (function calling nativo) |
| Fila de jobs | PostgreSQL (FOR UPDATE SKIP LOCKED) |
| Histórico de conversa | PostgreSQL (JSONB) |
| RAG / embeddings | pgvector + text-embedding-3-small |
| Lead lock / dedup | Redis |
| Frontend | Next.js 15, TypeScript, Tailwind |
| Infra | Hetzner (2 VMs: app + db), Cloudflare Tunnel |
| CI/CD | GitHub Actions → GHCR → self-hosted runner |
| Observabilidade | Prometheus, structlog |

---

## Estrutura do monorepo

```
nexo-flow/
├── apps/
│   ├── api/            # Backend Python
│   │   ├── src/
│   │   │   ├── agent/          # runner, skills, guards, prompt
│   │   │   ├── interface/      # HTTP routers, worker handlers
│   │   │   └── shared/         # adapters, domain, config
│   │   └── tests/
│   └── web/            # Frontend Next.js (painel admin)
│       └── src/features/       # feature modules por domínio
├── docs/superpowers/   # specs e planos de arquitetura
└── docker-compose.yml  # dev local (postgres + redis)
```

---

## Dev local

### Pré-requisitos

- Python 3.11+ e `uv`
- Node.js 20+
- Docker e Docker Compose

### Backend

```bash
# Subir infra (postgres + redis)
docker compose up postgres redis -d

# Instalar dependências
cd apps/api
uv sync

# Migrations
uv run alembic upgrade head

# API (porta 8000)
uv run uvicorn main:app --reload

# Worker (outro terminal)
uv run python -m worker
```

### Frontend

```bash
cd apps/web
npm install
npm run dev        # porta 3000
```

### Variáveis de ambiente

```bash
cp .env.example .env.local   # preenche com valores reais
```

Variáveis obrigatórias:

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL async (asyncpg) |
| `REDIS_URL` | Redis connection string |
| `OPENAI_API_KEY` | Chave OpenAI |
| `CHATNEXO_BASE_URL` | URL base da plataforma ChatNexo |
| `CHATNEXO_API_KEY` | API key ChatNexo |
| `HUBLA_WEBHOOK_SECRET` | Secret para validar webhooks Hubla |
| `ADMIN_API_KEY` | Chave para rotas `/admin/*` |

---

## Testes

```bash
cd apps/api

uv run pytest                        # todos os testes
uv run pytest tests/unit             # só unitários (rápidos, sem infra)
uv run pytest tests/integration      # requer postgres + redis rodando
uv run pytest -k "runner"            # filtro por nome
uv run pytest --cov=src              # com cobertura
uv run ruff check src tests          # linting
uv run mypy src                      # type checking
```

---

## Deploy

O deploy é automático via GitHub Actions ao fazer push na `main`:

1. Build das imagens Docker (API + Web) → push para GHCR
2. SSH no servidor Hetzner (self-hosted runner)
3. `git pull` + `docker compose pull`
4. `alembic upgrade heads` (migrations)
5. `docker compose up -d --force-recreate api worker web`

As imagens ficam em:
- `ghcr.io/nexo-ia-project/nexo-flow-api:latest`
- `ghcr.io/nexo-ia-project/nexo-flow-web:latest`

---

## Endpoints principais

| Método | Path | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Métricas Prometheus |
| `POST` | `/webhooks/message` | Recebe mensagens do ChatNexo |
| `POST` | `/webhooks/purchase` | Recebe compras do Hubla |
| `GET` | `/admin/documents` | Lista documentos da KB |
| `POST` | `/admin/documents` | Upload de documento para KB |
| `GET` | `/admin/search` | Busca semântica na KB |
| `GET` | `/admin/dlq` | Lista entradas do dead-letter queue |
| `DELETE` | `/admin/dlq/{id}` | Remove entrada do DLQ |
| `POST` | `/admin/dlq/{id}/requeue` | Reenfileira job do DLQ |
| `POST` | `/admin/dlq/requeue-all` | Reenfileira todos os jobs do DLQ |
