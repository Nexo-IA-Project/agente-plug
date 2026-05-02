# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Monorepo com backend Python (FastAPI + LangGraph) e frontend Next.js 15. O produto é um agente de IA para suporte ao cliente integrado ao WhatsApp via ChatNexo.

- `apps/api/` — Backend Python, porta 8000
- `apps/web/` — Frontend Next.js 15, porta 3000

---

## Backend (`apps/api/`)

### Comandos

```bash
# Instalar dependências
uv sync

# Dev server
uv run uvicorn nexoia.main:app --reload

# Worker (em outro terminal, necessário para processar jobs)
cd apps/api && uv run python -m worker

# Migrations
uv run alembic upgrade head

# Testes
uv run pytest                        # todos
uv run pytest tests/unit             # apenas unitários
uv run pytest tests/integration      # requer postgres+redis rodando
uv run pytest -k "nome_do_teste"     # filtrar por nome
uv run pytest --cov=nexoia           # com cobertura

# Linting e formatação
uv run ruff check src tests
uv run ruff format src tests
uv run mypy src
```

### Arquitetura

O backend segue Clean Architecture em camadas:

```
domain      → entidades, ports (interfaces), value objects
adapters    → implementações concretas (DB, Redis, APIs externas)
application → casos de uso, handlers de jobs, scheduler
interface   → routers HTTP, handlers de worker, schemas Pydantic
```

**Fluxo de mensagem:**
1. ChatNexo envia webhook POST `/webhooks/message`
2. Handler valida, cria job na fila Redis
3. Worker desencoda o job e despacha para o handler correspondente
4. Handler invoca `graph.py` (LangGraph ReAct) que seleciona e executa skills
5. Resposta é enviada de volta via ChatNexo API

**Configuração:** `src/shared/config/settings.py` usa Pydantic BaseSettings. Lê de `.env.local` com fallback para `.env`. Toda nova variável de ambiente vai em `.env.local` primeiro.

**Skills:** Cada skill é uma pasta em `src/agent/skills/<nome>/` com `skill.py`, `use_case.py`, `preconditions.py`, `instructions.md`. O `skill_loader.py` descobre e carrega skills dinamicamente.

### Serviços externos

| Serviço | Variável | Propósito |
|---|---|---|
| OpenAI | `OPENAI_API_KEY` | LLM inference + embeddings (RAG) |
| ChatNexo | `CHATNEXO_BASE_URL` + `CHATNEXO_API_KEY` | Plataforma de webhook/resposta |
| Hubla | `HUBLA_WEBHOOK_SECRET` | Webhook de compras |
| Cademi | `CADEMI_API_URL` + `CADEMI_API_KEY` | LMS (acesso de alunos) |
| Meta | `META_API_KEY` | WhatsApp |

---

## Frontend (`apps/web/`)

### Comandos

```bash
cd apps/web
npm run dev      # Turbopack, porta 3000
npm run build    # build de produção
npm run lint     # ESLint
```

### Arquitetura

**Feature Modules** — cada domínio é autocontido em `src/features/<domínio>/`:
```
features/<domínio>/
  components/   ← componentes React do domínio
  types.ts      ← tipos TypeScript
  data/         ← mocks (substituir por chamadas API quando disponível)
```

Layout e hooks compartilhados em `src/shared/` (Sidebar, TopBar, ThemeToggle, useToast).

**Design system NexoIA:**
- Tokens de cor definidos como CSS custom properties em `globals.css` (`:root` light / `.dark` dark)
- Referenciados no Tailwind via `var(--color-*)` em `tailwind.config.ts`
- Usar sempre tokens semânticos (`bg-surface-container`, `text-on-surface`) — nunca hex hardcoded
- Tema dark/light via `next-themes` com `defaultTheme="dark"`
- Toasts via hook `useToast` (wrapa sonner): `toast.success()`, `toast.error()`, `toast.warning()`, `toast.info()`
- Ícones: Material Symbols Outlined via CSS import em `globals.css`

**Obs:** `/kb/page.tsx` (lista de documentos) usa o estilo antigo — ainda não migrada para o design system NexoIA.

---

## Docker Compose (desenvolvimento local)

```bash
docker compose up          # sobe postgres, redis, api, worker
docker compose up postgres redis   # só infra (para rodar api local)
```

Serviços: postgres (5432), redis (6379), api (8000), worker.

---

## Documentação de arquitetura

`docs/superpowers/specs/` — design docs por subsistema  
`docs/superpowers/plans/` — planos de implementação com tasks detalhadas  
`docs/superpowers/INDEX.md` — índice dos 7 subsistemas do produto
