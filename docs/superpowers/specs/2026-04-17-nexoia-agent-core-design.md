# Spec ① — nexoia-agent Core

**Data:** 2026-04-17
**Fase:** 1 (Clean Architecture · SOLID · LangGraph)
**Repositório alvo:** `nexoia-agent` (novo repositório Python)
**Status:** Design aprovado — aguardando execução

---

## 1. Contexto e Objetivo

O `nexoia-agent` é o backend Python da NexoIA — a camada que roda toda a inteligência artificial de suporte, integrada ao painel operacional **ChatNexo** (Node.js, já existente) e aos canais WhatsApp via **Meta Business API**.

Este spec define o **Core do agente** — a fundação sobre a qual todas as capabilities (Welcome, Access, Refund, Loja Express) e o KB Admin serão construídos em specs subsequentes.

O Core é o que todas as capabilities importam. Adicionar uma capability nova **não toca o Core** — só cria um novo módulo em `capabilities/`.

### Subsistemas do projeto completo (para contexto)

| # | Spec | Status |
|---|---|---|
| ① | **Core do nexoia-agent** | este documento |
| ② | Capability Welcome (webhook Hubla → boas-vindas) | a brainstormar |
| ③ | Capability Access | a brainstormar |
| ④ | Capability Refund (CDC + Guards) | a brainstormar |
| ⑤ | Capability Loja Express (D+1/D+3/D+7) | a brainstormar |
| ⑥ | KB Admin | a brainstormar |

PostgreSQL e Redis são **serviços externos** — o agente apenas se conecta via connection string. Não fazem parte do escopo de construção.

---

## 2. Escopo do Core

### O que o Core FAZ

- Expõe endpoints HTTP:
  - `POST /webhook/purchase` — webhook da Hubla
  - `POST /webhook/message` — webhook do ChatNexo (mensagem recebida)
  - `GET /health` — liveness/readiness
  - `/api/v1/admin/*` — reservado para o KB Admin (spec ⑥ preenche)
  - `/metrics` — métricas Prometheus
- Autentica requisições:
  - **Webhook Hubla** → header `X-Hubla-Token` (valor em `HUBLA_WEBHOOK_SECRET`)
  - **Webhook ChatNexo e admin API** → header `X-Api-Key` (valor em `CHATNEXO_API_KEY` ou `ADMIN_API_KEY`)
  - HTTPS obrigatório em produção
- Valida payloads com **Pydantic v2**
- Enfileira trabalho em fila Redis (interna) com idempotência por `external_id` via `SETNX`
- Roda um **Worker Pool** que consome a fila e executa LangGraph
- Hospeda o **Intent Router** — classificador que decide qual capability atende
- Gerencia **checkpoints LangGraph** em PostgreSQL (`AsyncPostgresSaver`)
- Gerencia **memória longa** do contato em PostgreSQL (`long_term_facts` JSONB)
- Expõe `ChatNexoClient`, `OpenAIClient`, `MetaClient` como infra compartilhada
- Scheduler interno para follow-ups (idle check, D+1, follow-ups custom)
- Conversation Lifecycle Manager (comportamento idle — some por 30 min → "tá aí?" → encerra se não voltar)
- Logging estruturado com `correlation_id` propagado em toda a cadeia
- Circuit breaker + retry em chamadas externas
- Escalonamento para humano (handoff)

### O que o Core NÃO FAZ

- Regras de negócio específicas das capabilities → specs ②–⑤
- Integração Playwright com Hubla (usado por Refund) → spec ④
- Cliente REST Cademi (usado por Welcome) → spec ②
- Painel KB Admin (upload/chunking/pgvector/JWT) → spec ⑥

---

## 3. Decisões Arquiteturais

| Decisão | Opção escolhida | Razão |
|---|---|---|
| Deployment | Servidor dedicado separado, comunicação HTTP | Isolamento e escalabilidade do agente. |
| Auth entre serviços | `X-Api-Key` estático + HTTPS | Padrão server-to-server, simples e auditável. Rotação via env. |
| Multi-tenancy | Single DB com `account_id` (modelo Chatwoot: `account_id` + `conversation_id` + `contact_id`) | Espelha o modelo do ChatNexo/Chatwoot — facilita integração. |
| Checkpointer LangGraph | PostgreSQL (`AsyncPostgresSaver`) | Estado crítico (reembolso, acesso) precisa ser durável. Suporte oficial LangGraph. |
| Redis | Apenas dedup (`SETNX`), mutex, circuit breaker, fila, cache de sessão | Volátil e rápido para dados recalculáveis. |
| Estrutura de repositório | Monorepo Python, pastas por camada Clean Architecture | Padrão claro, domain isolado, capabilities como submódulos. |
| Gerenciador de pacotes | `uv` | Rápido, lockfile confiável, padrão moderno. |
| Lint/Format | `ruff` | Substitui black + isort + flake8. |
| Processamento de webhook | Assíncrono: handler retorna 202 + enqueue Redis + worker consome | Garante SLA <60s, tolera picos, permite retry. |
| Fila de prioridade | **Estrutura pronta, mas desativada** na Fase 1 (`ENABLE_PRIORITY_QUEUE=false`) | Upstream já classifica antes de chegar. Enums e tiers existem no código mas tudo entra FIFO. |
| Scheduler interno | Tabela `scheduled_jobs` (PostgreSQL) + worker poller | Durável, evita perder follow-ups em restart. Usado pelo idle check e pelo D+1 do Welcome. |

---

## 4. Estrutura de Pastas

```
nexoia-agent/
├── pyproject.toml              # uv + ruff + pytest config
├── Dockerfile                  # multi-stage (builder + runtime)
├── docker-compose.yml          # dev local
├── .env.example
├── alembic.ini
│
├── src/nexoia/
│   ├── __init__.py
│   ├── main.py                 # FastAPI bootstrap
│   ├── worker.py               # entrypoint do worker pool
│   │
│   ├── domain/                 # NÚCLEO — zero dependência de framework
│   │   ├── entities/           # Conversation, Contact, Account, Message, ScheduledJob…
│   │   ├── value_objects/      # Phone, Intent, Sentiment, CorrelationId, Priority
│   │   ├── events/             # PurchaseReceived, MessageReceived, HandoffRequested, IdleDetected
│   │   ├── ports/              # Interfaces Protocol: ChatNexoPort, MetaPort, CademiPort, KnowledgePort, LLMPort
│   │   └── errors.py           # exceções de domínio
│   │
│   ├── application/            # Use cases — orquestra domain + ports
│   │   ├── intent_router.py    # classifica intent e despacha pra capability
│   │   ├── response_composer.py # monta resposta final (regras comunicação PRD 8)
│   │   ├── memory/
│   │   │   ├── short_term.py   # thin wrapper sobre o checkpoint LangGraph
│   │   │   ├── long_term.py    # repository-backed, Contact facts
│   │   │   └── legal_history.py # Art. 49 CDC — busca canais anteriores
│   │   ├── sentiment.py        # detector de sentimento
│   │   ├── context_builder.py  # separa mensagens humano×IA, monta contexto
│   │   ├── conversation/
│   │   │   └── lifecycle.py    # idle check, close-by-timeout, handoff
│   │   ├── scheduler/
│   │   │   └── runner.py       # processa scheduled_jobs (poller)
│   │   ├── guards/
│   │   │   ├── base.py         # Guard ABC
│   │   │   ├── loop_detector.py
│   │   │   ├── frustration.py
│   │   │   └── legal_mention.py
│   │   └── capabilities/
│   │       └── base.py         # Capability ABC + CapabilityResult
│   │
│   ├── infrastructure/         # Adapters concretos (implementam ports)
│   │   ├── db/
│   │   │   ├── session.py      # SQLAlchemy 2 async engine
│   │   │   ├── models.py       # SQLAlchemy models
│   │   │   └── repositories/   # ConversationRepo, ContactRepo, AuditRepo, ScheduledJobRepo…
│   │   ├── redis/
│   │   │   ├── client.py
│   │   │   ├── queue.py        # PriorityQueue (ZSET) — prioridade desativável
│   │   │   ├── dedup.py        # SetNX
│   │   │   └── mutex.py        # lock distribuído
│   │   ├── llm/
│   │   │   ├── openai_client.py    # GPT-4.1-mini, Whisper, embeddings
│   │   │   ├── fake_client.py      # usado em testes
│   │   │   └── prompts/            # templates versionados
│   │   ├── chatnexo/
│   │   │   ├── client.py       # Action API client
│   │   │   └── schemas.py
│   │   ├── meta/
│   │   │   └── templates.py    # registry de templates aprovados
│   │   ├── langgraph_runtime/
│   │   │   ├── checkpointer.py # AsyncPostgresSaver
│   │   │   └── graph_builder.py
│   │   ├── crypto/
│   │   │   └── fernet.py       # encryption de credentials
│   │   └── observability/
│   │       ├── logger.py       # structlog + correlationId
│   │       └── metrics.py      # prometheus_client
│   │
│   ├── interface/              # Entry points HTTP e worker
│   │   ├── http/
│   │   │   ├── deps.py         # FastAPI dependencies
│   │   │   ├── middleware.py   # X-Api-Key, correlationId, tenant injection
│   │   │   ├── errors.py       # exception handlers
│   │   │   └── routers/
│   │   │       ├── health.py
│   │   │       ├── metrics.py
│   │   │       ├── webhook_purchase.py
│   │   │       ├── webhook_message.py
│   │   │       └── admin/      # reservado spec ⑥
│   │   └── worker/
│   │       ├── dispatcher.py   # pega job da fila → roteia
│   │       ├── scheduler.py    # poller de scheduled_jobs
│   │       └── handlers/
│   │
│   └── config/
│       └── settings.py         # Pydantic BaseSettings
│
├── migrations/                 # Alembic
│
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

**Regra de dependência (Clean Architecture):**

```
interface ─► application ─► domain
                               ▲
infrastructure ────────────────┘
```

- `domain/` **nunca** importa de outras camadas.
- `infrastructure/` implementa as Ports definidas em `domain/ports/`.
- `application/` só depende de `domain/`.
- `interface/` injeta implementações de `infrastructure/` nos use cases de `application/`.

---

## 5. Componentes Principais

### 5.1 Intent Router (`application/intent_router.py`)

- Recebe: `(message, conversation_context, long_term_memory)`
- Chama OpenAI com prompt estruturado + JSON Schema output
- Classifica intent em: `access | refund | loja_express | knowledge | welcome_response | unknown | escalate` (PRD 7.1-7.6 — 6+ categorias)
- Classifica sentimento em: `neutro | positivo | frustrado | irritado | ansioso | hostil` (PRD seção 8 — 5+ categorias)
- Devolve: `IntentDecision(capability, confidence, reasoning, sentiment)`
- **Regra:** `confidence < 0.7` → handoff silencioso para humano
- É use case puro: nunca chama infrastructure diretamente, recebe ports injetadas

### 5.2 LangGraph Runtime (`infrastructure/langgraph_runtime/`)

- **Main Graph**: `entry → context_builder → sentiment → intent_router → dispatch → capability_subgraph → response → save_memory`
- **Subgraph por capability**: cada capability (welcome/access/refund/loja_express) é um `StateGraph` independente, plugado como subgraph
- **Checkpointer**: `AsyncPostgresSaver` com `thread_id = f"{account_id}:{conversation_id}"`
- **State schema base** (`ConversationState`):
  - `messages: list[Message]`
  - `intent: Intent | None`
  - `sentiment: Sentiment`
  - `handoff_requested: bool`
  - `attempts: int`
  - `capability_state: dict[str, Any]` — bag de estado da capability ativa
  - `correlation_id: str`

### 5.3 Worker Dispatcher (`interface/worker/dispatcher.py`)

- Loop de consumo: `BLPOP`/`BZPOPMIN` da queue Redis
- Para cada job:
  1. Injeta `correlation_id` no contexto
  2. Carrega checkpoint LangGraph
  3. Executa o grafo
  4. Publica resposta no ChatNexo via Action API
- Tipos de job: `ProcessPurchaseWebhook`, `ProcessIncomingMessage`, `SendScheduledFollowUp`, `IdleCheck`
- Escalonável: N workers em paralelo (processos separados)
- Shutdown graceful: SIGTERM termina job atual antes de morrer (timeout 30s)

### 5.4 Scheduler (`application/scheduler/runner.py` + `interface/worker/scheduler.py`)

- Poller que roda a cada 10s consultando `scheduled_jobs WHERE status='PENDING' AND run_at <= NOW() ORDER BY run_at LIMIT N`
- Move jobs prontos para a fila Redis ativa
- Jobs são idempotentes (dedup via `external_id` ou `scheduled_job.id`)
- Suporta cancelamento: API interna `scheduler.cancel(job_id)` muda status para `CANCELLED`
- Lock distribuído em Redis garante que só um scheduler roda ao mesmo tempo mesmo com múltiplos workers

### 5.5 Conversation Lifecycle Manager (`application/conversation/lifecycle.py`)

Gerencia comportamento idle e handoff.

**Idle check — thresholds:**
- **Após 30 min** sem resposta do aluno → envia **Ping 1** ("Olá, {nome}, você está por aí ainda?") — variação rotativa
- **Após +20 min** sem resposta → envia **mensagem de encerramento** ("Como não vi mais sua resposta...") — variação rotativa — marca conversa como `CLOSED_BY_TIMEOUT`

**Pool de variações (para evitar sensação robótica):**

Ping 1:
- "Olá, {nome}, você está por aí ainda?"
- "Ei {nome}, ainda tá comigo?"
- "{nome}, tudo certo? Continuo aqui se quiser seguir."

Encerramento:
- "Como não vi mais sua resposta, vou encerrar a conversa por aqui. Se quiser retomar, é só me chamar. 🙂"
- "Sem resposta por aqui, então vou encerrando. Qualquer coisa me avisa que a gente continua."
- "Vou finalizar por aqui por enquanto, {nome}. Quando quiser retomar, é só mandar mensagem."

Variação é escolhida por hash(`conversation_id + stage`) para ser determinística e reproduzível em teste.

**Guards (quando NÃO disparar idle check):**
- Conversa em status `HANDED_OFF` (humano assumiu)
- Conversa já fechada/resolvida
- Aluno respondeu (reseta timer — cancela jobs pendentes)
- Janela 24h da Meta expirou → não manda texto livre, marca `CLOSED_BY_TIMEOUT` silenciosamente

**Mecânica:** após cada mensagem out do agente, o lifecycle agenda `IDLE_PING` em +30min. Quando aluno responde, cancela o job. Quando `IDLE_PING` executa, agenda `IDLE_CLOSE` em +20min.

### 5.6 Memory Layer (`application/memory/`)

- **Short-term** (`short_term.py`): wrapper fino sobre o checkpoint LangGraph. Estado da thread, tentativas, handoff.
- **Long-term** (`long_term.py`): repository do Contact. Busca por `(account_id, contact_id)`. Campos: `email`, `produtos_comprados`, `historico_retencao`, `personalidade`, `preferencias`, `ultima_interacao`, `notas_ia`.
- **Legal History** (`legal_history.py`): busca em **todas** as conversas anteriores do contato por solicitação de reembolso dentro do prazo CDC (Art. 49 — PRD 9). Usado pelo `check_deadline` do Refund para forçar `within_deadline = True` se aluno pediu em canal anterior. Query: `SELECT * FROM messages JOIN conversations WHERE contact_id = $1 AND content ILIKE '%reembolso%' AND created_at >= purchase_date AND created_at <= purchase_date + 7 days`.
- **Context Builder** (`context_builder.py`): monta o contexto final pro LLM. **Regra crítica**: separa mensagens enviadas por operador humano vs respostas geradas pela IA — LLM não pode confundir a voz humana com a sua.

### 5.7 Guards e Circuit Breaker (`application/guards/`)

**Guards genéricos** (aplicáveis em todas as capabilities):
- `LoopDetectorGuard` — detecta 3+ respostas similares em sequência → handoff
- `FrustrationGuard` — sentimento `hostil` + 2 tentativas → handoff
- `LegalMentionGuard` — menção a Procon, advogado, ação judicial → **handoff silencioso imediato** (zero mensagem)

Guards específicos de capability ficam no módulo da capability (ex: `capabilities/refund/guards/explicit_request.py`).

### 5.7c Escalation Triggers (PRD 7.6)

Catálogo de triggers para handoff silencioso gerenciado pelo Core. Cada capability dispara via `ChatNexoClient.transfer_to_human(reason=...)`:

| Trigger | Como detectado | Reason code |
|---|---|---|
| Aluno pediu humano 3x | Contador no estado da conversa | `human_requested_3x` |
| Chargeback / contestação | Webhook específico ou menção explícita | `chargeback` |
| Bug após 3 tentativas | Retries esgotados em integração | `bug_persistent` |
| PDF / material de live | Intent Router detecta pedido de mídia específica | `media_material_request` |
| Compra não encontrada (3 buscas) | Refund/Access cascade esgotada | `purchase_not_found_3x` |
| Procon / advogado / ação judicial | `LegalMentionGuard` | `legal_mention` |
| 3ª insistência pós-deny | Contador no RefundCase | `post_deny_3rd_insistence` |
| Loja Express bloqueio operacional | Spec ⑤ D+5/D+7 | `loja_express_blocked` |

**Regras (PRD 7.6):**
- **Sempre silencioso:** nunca dizer "vou te transferir" ao aluno
- **Nunca escalar por erro de API:** usar retry + circuit breaker
- Logar `handoff_reason` em `audit_events` para rastreamento

### 5.7a Response Composer (`application/response_composer.py`)

Componente que monta a resposta final antes de enviar ao ChatNexo (PRD 3.4 step 13).

**Responsabilidades:**
- Aplica **Regras de Comunicação** da NexoIA (PRD seção 8) como validação pós-LLM
- Define `tags`, `status` e `ação` (ex: `transfer_to_human`, `add_tag`) junto à mensagem
- Trunca se mensagem exceder limite (300 caracteres — PRD seção 8)
- Valida que a resposta não contém palavras proibidas
- Adapta tom conforme sentimento detectado

### 5.7b Regras de Comunicação da IA (PRD seção 8)

Aplicadas no Response Composer e no prompt do LLM:

| Atributo | Regra |
|---|---|
| **Identidade** | Especialista de Sucesso do Aluno. Pessoa real do time. **Nunca se revela como IA** (PRD 8). |
| **Tom** | Calorosa, direta, competente. "Amiga próxima que trabalha na empresa." |
| **Linguagem** | Informal brasileira: "vc", "tb", "pra", "tá", "né", "beleza" |
| **Mensagens** | Máximo **300 caracteres**, 2-4 linhas |
| **Proibidas** | "putz", "puts", "poxa", "que chato", "Claro!", "entendo" repetido |
| **Formato** | Nunca bullets, negrito, itálico ou cabeçalhos no WhatsApp |

**Comportamento por sentimento (PRD seção 8):**

| Sentimento | Comportamento |
|---|---|
| Neutro/Positivo | Tom amigável, emoji ok |
| Frustrado | 1 frase de empatia → ação direta |
| Irritado | Sério, direto, sem emoji. Ação imediata |
| Ansioso | "Fica tranquilo(a), vou cuidar disso" |
| Hostil | Profissional e calmo. 1 tentativa → escala |

**Validação:** `Response Composer` executa um `PostResponseValidator` que rejeita a resposta gerada pelo LLM se violar qualquer regra acima. Em caso de violação: gera nova tentativa com o LLM (máx 2 retries) ou cai em fallback genérico.

### 5.8 ChatNexo Client (`infrastructure/chatnexo/client.py`)

- `send_message(account_id, conversation_id, text)`
- `send_template(account_id, conversation_id, template_name, variables)`
- `transfer_to_human(account_id, conversation_id, reason)`
- `add_tag(account_id, conversation_id, tag)`
- Retry com backoff exponencial (3 tentativas), circuit breaker por tenant
- Todas as chamadas logam `correlation_id`

### 5.9 Config (`config/settings.py`)

Pydantic `BaseSettings`. Valida envs no startup. Zero `os.getenv()` espalhado.

```python
DATABASE_URL: str
REDIS_URL: str
OPENAI_API_KEY: str
CHATNEXO_BASE_URL: str
CHATNEXO_API_KEY: str
HUBLA_WEBHOOK_SECRET: str
META_API_KEY: str
INTEGRATION_CREDENTIALS_KEY: str  # Fernet key 32 bytes base64
ENABLE_PRIORITY_QUEUE: bool = False
LOG_LEVEL: str = "INFO"
SENTRY_DSN: str | None = None
IDLE_PING_MINUTES: int = 30
IDLE_CLOSE_MINUTES: int = 20
INTENT_CONFIDENCE_THRESHOLD: float = 0.7
```

---

## 6. Fluxos de Dados

### 6.1 Fluxo Proativo (webhook Hubla)

1. **Hubla** dispara `POST /webhook/purchase` com `{purchase_id, nome, email, telefone, produto, valor, timestamp}`
2. **FastAPI** (`webhook_purchase.py`):
   - Valida header `X-Hubla-Token` contra `HUBLA_WEBHOOK_SECRET`
   - Valida payload com Pydantic
   - `SETNX` em Redis com chave `dedup:purchase:{purchase_id}` (TTL 24h)
   - Persiste em `webhook_events`
   - Enfileira job `ProcessPurchaseWebhook` na queue Redis
   - Retorna `202 Accepted` em <100ms
3. **Worker** pega o job:
   - Carrega dados complementares da Cademi (link nominal de auto-login) — *integração implementada no spec ②*
   - Busca ou cria `Contact` por (`account_id`, `phone`)
   - Cria ou obtém `Conversation` (busca no ChatNexo — via client — se já existe conversa ativa)
   - Cria `AccessCase` com status `link_enviado_proativo` — *tabela criada no spec ②*
   - Invoca **Welcome Capability** via LangGraph — *implementada no spec ②*
4. **LangGraph Welcome subgraph**:
   - Carrega checkpoint (novo na primeira vez)
   - Seleciona template `welcome_purchase` com variáveis (nome, produto, link)
   - Retorna instrução de envio
5. **Response Node** chama `ChatNexoClient.send_template(...)` → ChatNexo envia via Meta API
6. **Scheduler** agenda `FOLLOWUP_D1` em `scheduled_jobs` (run_at = now + 24h)
7. Se aluno responde antes → cancela follow-up e entra no fluxo reativo

**SLA total:** webhook → WhatsApp entregue em <60s.

### 6.2 Fluxo Reativo (mensagem do aluno)

1. **Aluno** envia mensagem no WhatsApp
2. **ChatNexo** recebe via webhook da Meta, faz Media Processing (áudio → Whisper, imagem/PDF → texto) e POSTa enriquecido em `/webhook/message`
3. **FastAPI** (`webhook_message.py`):
   - Valida `X-Api-Key`
   - Valida payload (inclui `classification_hint` do upstream — apenas logado, não usado na Fase 1)
   - `SETNX` em `dedup:message:{chatnexo_message_id}`
   - Persiste em `messages`
   - Enfileira job `ProcessIncomingMessage`
   - Retorna `202 Accepted` em <100ms
4. **Worker** pega o job e dispara o **Main Graph** do LangGraph:
   - `context_builder` carrega thread + memória longa
   - `sentiment` detecta humor do aluno
   - `intent_router` classifica e seleciona capability
   - `guards` genéricos rodam (loop, frustração, legal)
   - `dispatch` executa subgraph da capability selecionada
   - `response` publica no ChatNexo (texto livre se dentro de janela 24h, senão template)
   - `save_memory` atualiza `long_term_facts` com insights da conversa
5. **Lifecycle Manager** cancela qualquer `IDLE_PING` pendente e agenda novo para +30min

### 6.3 Fluxo Idle (conversa parada)

1. `IDLE_PING` dispara após 30 min sem resposta do aluno:
   - Verifica status da conversa (guards)
   - Se OK: envia ping via ChatNexo (texto livre — dentro de janela 24h)
   - Agenda `IDLE_CLOSE` em +20min
2. Aluno responde → cancela `IDLE_CLOSE`, volta ao fluxo reativo
3. `IDLE_CLOSE` dispara:
   - Envia encerramento via ChatNexo
   - Marca conversa como `CLOSED_BY_TIMEOUT`
   - Fim

---

## 7. Modelo de Dados

### 7.1 Tabelas do Core

| Tabela | Responsabilidade | Campos-chave |
|---|---|---|
| `accounts` | Tenant (espelha Chatwoot) | `id`, `name`, `settings` (JSONB), `created_at` |
| `contacts` | Aluno/usuário | `id`, `account_id`, `phone` (E.164 com `55`), `name`, `email`, `long_term_facts` (JSONB), `created_at`, `updated_at` |
| `conversations` | Thread de conversa | `id`, `account_id`, `contact_id`, `chatnexo_conversation_id`, `status` (ACTIVE/IDLE_PINGED/CLOSED_BY_TIMEOUT/HANDED_OFF/RESOLVED), `last_activity_at`, `idle_state`, `window_expires_at`, `handoff_reason`, `created_at`, `updated_at` |
| `messages` | Mensagens in/out | `id`, `conversation_id`, `direction` (IN/OUT), `source` (STUDENT/AGENT_IA/AGENT_HUMAN), `content`, `media_urls` (array), `classification_hint`, `correlation_id`, `created_at` |
| `webhook_events` | Auditoria de webhooks | `id`, `source` (HUBLA/CHATNEXO), `external_id` UNIQUE, `payload` (JSONB), `status`, `correlation_id`, `created_at`, `processed_at` |
| `scheduled_jobs` | Scheduler | `id`, `account_id`, `conversation_id` (nullable), `job_type` (IDLE_PING/IDLE_CLOSE/FOLLOWUP_D1/FOLLOWUP_CUSTOM), `payload` (JSONB), `run_at`, `status` (PENDING/CANCELLED/EXECUTED/FAILED), `attempts`, `correlation_id`, `created_at`, `executed_at` |pode
| `capability_executions` | Analytics | `id`, `conversation_id`, `capability_name`, `intent_confidence`, `tools_called` (JSONB), `duration_ms`, `outcome` (SUCCESS/HANDOFF/ERROR), `correlation_id`, `created_at` |
| `audit_events` | Trilha geral | `id`, `account_id`, `actor` (SYSTEM/AGENT/HUMAN), `action`, `resource_type`, `resource_id`, `metadata` (JSONB), `correlation_id`, `created_at` |
| `integration_configs` | Credenciais por tenant | `id`, `account_id`, `integration_type` (HUBLA/CADEMI/META/CHATNEXO), `credentials_encrypted`, `enabled`, `created_at`, `updated_at` |
| `meta_templates` | Templates Meta aprovados | `id`, `account_id`, `name`, `meta_template_id`, `language`, `variables_schema` (JSONB), `approved`, `last_synced_at` |

**Checkpoints LangGraph:** tabelas `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` — criadas automaticamente pelo `AsyncPostgresSaver`. Não desenhamos.

### 7.2 Índices obrigatórios

```sql
CREATE UNIQUE INDEX contacts_account_phone_idx ON contacts (account_id, phone);
CREATE UNIQUE INDEX conversations_account_chatnexo_idx ON conversations (account_id, chatnexo_conversation_id);
CREATE INDEX messages_conversation_created_idx ON messages (conversation_id, created_at DESC);
CREATE INDEX scheduled_jobs_pending_idx ON scheduled_jobs (status, run_at) WHERE status = 'PENDING';
CREATE UNIQUE INDEX webhook_events_source_external_idx ON webhook_events (source, external_id);
CREATE INDEX audit_events_account_created_idx ON audit_events (account_id, created_at DESC);
```

### 7.3 Migrations

- Alembic, um arquivo por feature
- **Nunca editar** migration já aplicada — criar nova se precisar corrigir
- Migrations rodam no startup do container `nexoia-api` com lock distribuído no Redis para evitar corrida

### 7.4 Criptografia de credenciais

`integration_configs.credentials_encrypted` usa **Fernet** (chave `INTEGRATION_CREDENTIALS_KEY` via env, 32 bytes base64).
Credenciais decriptadas **apenas em memória** no momento da chamada — nunca persistidas em claro, nunca logadas.

---

## 8. Observabilidade

### Logging

- `structlog` com output JSON em produção
- Cada log traz: `correlation_id`, `account_id`, `conversation_id`, `capability`, `intent`, `duration_ms`, `outcome`, `event`
- `correlation_id` gerado no handler do primeiro webhook, propagado via `contextvars` por todo o pipeline

### Métricas (Prometheus format em `/metrics`)

- `webhook_received_total{source, status}`
- `queue_depth{tier}`
- `worker_job_duration_seconds{job_type, outcome}` (histogram)
- `capability_outcome_total{capability, outcome}`
- `handoff_total{reason}`
- `llm_tokens_used_total{model, purpose}`
- `idle_check_fired_total{stage}`

### Error tracking

- `Sentry` opcional via `SENTRY_DSN`
- Exceções não tratadas, com contexto `correlation_id` + `account_id`

### Healthcheck

- `GET /health` valida:
  - Conexão PostgreSQL
  - Conexão Redis
  - Status do circuit breaker OpenAI
  - Ping ChatNexo (opcional, apenas readiness)
- Retorna `200` se todos OK, `503` se algum crítico está fora

---

## 9. Estratégia de Testes

### Camadas

- **Unit** (`tests/unit/`) — domain + application isolados, zero I/O. Mocks das Ports via `pytest-mock`.
- **Integration** (`tests/integration/`) — infrastructure contra PG e Redis reais (via `testcontainers-python`). Testa repositories, queue, checkpointer.
- **E2E** (`tests/e2e/`) — webhook HTTP → fila → worker → mocks de ChatNexo/Cademi/OpenAI. Usa `httpx.AsyncClient` contra a app FastAPI em fixture.

### Regras

- **Coverage mínimo:** 80% em domain + application
- **Nunca** chamar OpenAI em testes: usar `FakeOpenAIClient` com respostas canônicas mapeadas por prompt hash
- **Fixtures:** `factory-boy` para `Account`, `Contact`, `Conversation`, `Message`, `ScheduledJob`
- **Tempo controlado:** `freezegun` para testar idle/scheduler
- **Determinismo:** variações de mensagens do idle usam hash determinístico → testes reproduzíveis

### Comando padrão

```bash
pytest                          # tudo
pytest tests/unit/              # só unit
pytest -k "idle"                # filtro por nome
pytest --cov=nexoia --cov-report=term-missing
```

---

## 10. Deployment

### Dockerfile (multi-stage)

1. **Stage builder:** `uv` instala dependências em `.venv`
2. **Stage runtime:** `python:3.11-slim`, copia `.venv` e código. Imagem final ~150MB.

### Containers do mesmo image

- `nexoia-api` — entrypoint `uvicorn nexoia.main:app --host 0.0.0.0 --port 8000`
- `nexoia-worker` — entrypoint `python -m nexoia.worker` (inclui scheduler)

### docker-compose.yml (dev)

Sobe `api` + `worker` + PG local + Redis local. Produção aponta pras instâncias externas via env.

### Variáveis de ambiente mínimas

```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/nexoia
REDIS_URL=redis://host:6379/0
OPENAI_API_KEY=sk-...
CHATNEXO_BASE_URL=https://chatnexo.internal
CHATNEXO_API_KEY=<token>
HUBLA_WEBHOOK_SECRET=<secret>
ADMIN_API_KEY=<token>            # chave para endpoints /api/v1/admin/*
META_API_KEY=<token>
INTEGRATION_CREDENTIALS_KEY=<fernet-key-32-bytes-base64>
ENABLE_PRIORITY_QUEUE=false
LOG_LEVEL=INFO
SENTRY_DSN=
IDLE_PING_MINUTES=30
IDLE_CLOSE_MINUTES=20
INTENT_CONFIDENCE_THRESHOLD=0.7
```

### Graceful shutdown

- SIGTERM → API drena requests in-flight, worker termina job atual antes de sair
- Timeout: 30s

### CI/CD (sugerido)

- GitHub Actions (ou GitLab): `ruff check` + `ruff format --check` + `mypy` + `pytest --cov`
- Build Docker push pra registry
- Deploy via pipeline manual (fora do escopo deste spec)

---

## 11. Requisitos Funcionais

| ID | Requisito |
|---|---|
| CORE-RF-01 | Receber webhook `POST /webhook/purchase` com validação do header `X-Hubla-Token` contra `HUBLA_WEBHOOK_SECRET` e idempotência via `SETNX` em Redis. Retornar 202 em <100ms. |
| CORE-RF-02 | Receber webhook `POST /webhook/message` com validação de `X-Api-Key` e idempotência por `chatnexo_message_id`. Retornar 202 em <100ms. |
| CORE-RF-03 | Enfileirar jobs na queue Redis e processar via worker pool com suporte a escalonamento horizontal. |
| CORE-RF-04 | Scheduler interno lendo `scheduled_jobs` a cada 10s, com lock distribuído pra evitar execução dupla. |
| CORE-RF-05 | Intent Router classifica intent via OpenAI + JSON Schema. `confidence < 0.7` → handoff. |
| CORE-RF-06 | LangGraph com `AsyncPostgresSaver` persiste estado de cada conversa por `thread_id = "{account_id}:{conversation_id}"`. |
| CORE-RF-07 | Conversation Lifecycle Manager envia `IDLE_PING` após 30 min de silêncio e `IDLE_CLOSE` após mais 20 min. Guards bloqueiam se conversa em handoff ou fora de janela 24h. |
| CORE-RF-08 | Cliente ChatNexo com retry (3 tentativas, backoff exponencial) e circuit breaker por tenant. |
| CORE-RF-09 | Logging estruturado JSON com `correlation_id` propagado em toda a cadeia. |
| CORE-RF-10 | Healthcheck `/health` valida PG, Redis, OpenAI, ChatNexo. |
| CORE-RF-11 | Métricas Prometheus em `/metrics`. |
| CORE-RF-12 | Criptografia Fernet para `integration_configs.credentials_encrypted`. |
| CORE-RF-13 | **Intent Router** classifica 7 categorias: `access \| refund \| loja_express \| knowledge \| welcome_response \| unknown \| escalate` e 5 sentimentos. |
| CORE-RF-14 | **Response Composer** valida resposta contra Regras de Comunicação (PRD 8): máx 300 chars, sem palavras proibidas, sem bullets/bold, tom por sentimento, nunca revela ser IA. |
| CORE-RF-15 | **Legal History** busca em todas as conversas anteriores do contato por menção a reembolso dentro do prazo CDC (Art. 49 — PRD 9). |
| CORE-RF-16 | **Escalation Triggers:** catálogo PRD 7.6 — 8 triggers de handoff silencioso, sempre via `transfer_to_human(reason=...)`. |

## 12. Requisitos Não Funcionais

| ID | Requisito |
|---|---|
| CORE-RNF-01 | **Latência webhook:** <100ms da requisição ao 202. |
| CORE-RNF-02 | **SLA proativo:** compra → WhatsApp entregue em <60s (end-to-end). |
| CORE-RNF-03 | **SLA reativo:** mensagem recebida → resposta em <30s. |
| CORE-RNF-04 | **Escalabilidade:** adicionar tenant não requer migration nem deploy; adicionar capability não toca o Core. |
| CORE-RNF-05 | **Clean Architecture:** domain zero dependência externa; regra validada por teste de arquitetura (ex: `pytest-archon`). |
| CORE-RNF-06 | **SOLID:** SRP por módulo, OCP para capabilities, DI explícita em todas as integrações. |
| CORE-RNF-07 | **Compliance Meta:** nunca enviar texto livre fora da janela de 24h. Sempre template aprovado. |
| CORE-RNF-08 | **Segurança:** isolamento por tenant via `account_id`; segredos só via env; tokens de webhook validados antes de processar payload. |
| CORE-RNF-08.1 | **Tenant isolation obrigatório:** toda query em repositories deve receber `account_id` como parâmetro explícito. Queries sem filtro de `account_id` falham em revisão de código. Adicionar teste de arquitetura que busca `.filter(` sem `account_id` nos repositories. |
| CORE-RNF-09 | **Testabilidade:** coverage ≥80% em domain+application; zero chamada real de LLM em teste. |
| CORE-RNF-10 | **Observabilidade:** todo fluxo rastreável por `correlation_id`. |
| CORE-RNF-11 | **Idempotência:** webhooks duplicados não geram processamento duplo. |
| CORE-RNF-12 | **Graceful shutdown:** SIGTERM com até 30s para drenar. |

## 13. Fora de Escopo (explicitamente)

- Prioridade enforcement na queue (código pronto, flag `ENABLE_PRIORITY_QUEUE=false`)
- Playwright automation Hubla — spec ④ (Refund)
- Integração Cademi — spec ② (Welcome)
- Upload/chunking/pgvector/JWT do KB Admin — spec ⑥
- Painel web KB Admin — spec ⑥
- Analytics dashboard — fase futura
- Shadow mode / aprendizado de prompts — fase futura
- Suporte multi-canal (só WhatsApp na Fase 1)

## 14. Critérios de Aceitação

O Core está "pronto" quando:

1. Testes unitários e de integração passam com coverage ≥80% em domain+application
2. `docker-compose up` sobe API + worker + apontam pros serviços externos configurados
3. `curl POST /webhook/purchase` com payload válido retorna 202 em <100ms e cria `webhook_events` + job na queue
4. `curl POST /webhook/message` idem
5. Worker consome job e executa um LangGraph "hello world" de ponta a ponta (capability dummy)
6. `GET /health` retorna 200 com todos os checks verdes
7. `GET /metrics` retorna formato Prometheus válido
8. Scheduler agenda e executa `IDLE_PING` num teste e2e com `freezegun`
9. Migrations rodam idempotentemente
10. Logs saem em JSON com `correlation_id` presente

---

## 15. Questões em Aberto

Nenhuma crítica no momento. Revisitar após os specs das capabilities (②–⑤) caso surja necessidade de abstração compartilhada não antecipada.
