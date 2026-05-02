# PRD: NexoIA Agent — Skills Profissionais, Workers Concorrentes & Infraestrutura Profissional

**Author:** Fabio Dias
**Date:** 2026-05-02
**Status:** Draft
**Version:** 2.0
**Taskmaster Optimized:** Yes

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Goals & Success Metrics](#goals--success-metrics)
4. [User Stories](#user-stories)
5. [Functional Requirements](#functional-requirements)
6. [Non-Functional Requirements](#non-functional-requirements)
7. [Technical Considerations](#technical-considerations)
8. [Implementation Roadmap](#implementation-roadmap)
9. [Out of Scope](#out-of-scope)
10. [Open Questions & Risks](#open-questions--risks)
11. [Validation Checkpoints](#validation-checkpoints)
12. [Appendix: Task Breakdown Hints](#appendix-task-breakdown-hints)

---

## Executive Summary

O NexoIA Agent atualmente usa uma arquitetura baseada em LangGraph + LangChain que introduz abstrações desnecessárias, dificulta manutenção e processa mensagens de forma sequencial — causando travamento quando múltiplos leads chegam simultaneamente. Além disso, o produto não possui infraestrutura de produção nem pipeline de CI/CD. Esta evolução cobre três missões: (1) migrar as skills do agente para o padrão OpenAI function calling nativo, eliminando LangChain e LangGraph; (2) reimplementar o worker com concorrência real via `asyncio.TaskGroup`; (3) provisionar infraestrutura profissional na Hetzner com duas VMs em rede privada (app + banco), Cloudflare Tunnel, firewall, backups automáticos do PostgreSQL e pipeline completo de CI/CD no GitHub Actions com proteção de branch. O resultado esperado é um agente confiável em produção com zero exposição direta de portas, pipeline automatizado de testes/deploy e banco de dados protegido com backups diários.

---

## Problem Statement

### Current Situation

O backend usa:
- **Skills** como `LangChain.BaseTool` → acopladas ao ecossistema LangChain, com `_run()`/`_arun()` e `RunnableConfig` para injetar contexto (account_id, phone) — padrão não-idiomático para o Anthropic SDK.
- **LangGraph** com `StateGraph` + `ToolNode` → orquestração desnecessariamente complexa para um ReAct loop simples; nodes separados (raciocinar / executar / pos_execucao) para o que é essencialmente um loop `while tool_calls`.
- **WorkerDispatcher** sequencial → `run_forever()` aguarda o handler completar antes de dequeuing o próximo job; um call LLM de 8s bloqueia todos os outros leads.
- **Sem retry** → jobs que falham são silenciosamente descartados (sem DLQ).
- **Sem lock por lead** → se dois webhooks chegam para o mesmo lead simultaneamente, ambos serão processados em paralelo causando respostas duplicadas.

### User Impact

- **Leads:** Ficam sem resposta ou recebem respostas atrasadas quando múltiplos leads chegam ao mesmo tempo.
- **Operadores:** Dificuldade em criar ou manter skills — padrão LangChain/LangGraph é complexo e diferente da documentação OpenAI.
- **Engenheiros:** Debugging difícil — falhas silenciosas, estado no LangGraph graph, contexto injetado via `RunnableConfig` em vez de parâmetros explícitos.

### Business Impact

- **Perda de leads:** Um worker travado não atende novos leads.
- **Custo técnico:** LangChain/LangGraph introduz ~50 transitive dependencies, updates frequentes e breaking changes.
- **Escalabilidade:** Impossível escalar horizontalmente sem resolver a concorrência first.

### Why Solve This Now?

O produto está em fase de crescimento. Resolver a concorrência agora evita reescrita emergencial sob pressão quando o volume de leads aumentar. A migração para OpenAI function calling nativo é o foundation correto antes de adicionar mais skills.

---

## Goals & Success Metrics

### Goal 1: Skills no padrão OpenAI function calling nativo

- **Description:** Skills definidas como OpenAI tool dict com `parameters` JSON Schema, loop do agente como corrotina async explícita usando `openai.AsyncOpenAI`, sem LangChain nem LangGraph.
- **Metric:** Zero imports de `langchain` ou `langgraph` em `src/agent/`
- **Baseline:** 100% das skills usam LangChain BaseTool
- **Target:** 100% das skills usam o padrão OpenAI function calling nativo
- **Timeframe:** Entrega da Fase 2
- **Measurement:** `grep -r "langchain\|langgraph" apps/api/src/agent/` retorna 0 resultados

### Goal 2: Concorrência real de leads

- **Description:** O worker processa múltiplos leads em paralelo; cada lead corre em sua própria `asyncio.Task` com isolamento de contexto.
- **Metric:** Throughput de jobs simultâneos
- **Baseline:** 1 job simultâneo (sequencial)
- **Target:** Até 50 jobs simultâneos com Semaphore configurável
- **Timeframe:** Entrega da Fase 3
- **Measurement:** Teste de carga com 20 mensagens simultâneas processando sem serialização

### Goal 3: Confiabilidade — retry + DLQ

- **Description:** Jobs que falham são tentados novamente (até 3 vezes com backoff) e movidos para Dead-Letter Queue se esgotarem as tentativas.
- **Metric:** Porcentagem de jobs perdidos silenciosamente
- **Baseline:** 100% dos jobs que falham são perdidos
- **Target:** 0% de perda silenciosa; 100% dos jobs aparecem em DLQ ou são completados
- **Timeframe:** Entrega da Fase 3
- **Measurement:** Injetar falha artificial; verificar DLQ no Redis

### Goal 5: Infraestrutura profissional em produção

- **Description:** Aplicação rodando em produção na Hetzner com Cloudflare Tunnel, firewall, banco isolado em VM separada e backups automáticos diários.
- **Metric:** `curl https://api-iag2.ianexo.com.br/health` retorna 200 em < 500ms
- **Baseline:** Sem ambiente de produção
- **Target:** Produção ativa com 99.9% uptime (Cloudflare + Hetzner SLA)
- **Timeframe:** Entrega da Fase 5
- **Measurement:** Uptime monitor via Cloudflare Analytics

### Goal 6: Pipeline CI/CD automatizado

- **Description:** Cada PR na main dispara: lint + testes + code review automatizado. Merge na main dispara deploy automático para produção.
- **Metric:** Tempo de feedback por PR < 5min; deploy automático após merge
- **Baseline:** Zero automação
- **Target:** 100% dos PRs passam pela esteira; deploy zero-downtime em < 3min após merge
- **Timeframe:** Entrega da Fase 5
- **Measurement:** GitHub Actions run history

### Goal 4: Lock por lead

- **Description:** Garantir que um lead nunca seja processado em paralelo por dois workers simultâneos.
- **Metric:** Zero respostas duplicadas para o mesmo lead
- **Baseline:** Duplicatas possíveis se dois webhooks chegam juntos
- **Target:** Redis mutex por `(account_id, phone)` com TTL 60s
- **Timeframe:** Entrega da Fase 3
- **Measurement:** Enviar 5 webhooks idênticos; verificar que apenas 1 resposta é enviada

---

## User Stories

### Story 1: OpenAI Function Calling Agent Loop

**As a** engenheiro de backend,
**I want to** ter um loop de agente limpo que usa OpenAI SDK nativo com `client.chat.completions.create(tools=[...])`,
**So that I can** debugar facilmente, criar novas skills sem aprender LangChain, e seguir a documentação oficial da OpenAI.

**Acceptance Criteria:**
- [ ] Loop do agente implementado em `src/agent/runner.py` como `async def run(messages, config) -> str`
- [ ] Sem uso de `LangChain`, `LangGraph`, `BaseTool`, `ToolNode`, `StateGraph`
- [ ] Skills registradas como OpenAI tool dict com `parameters` JSON Schema válido
- [ ] `tool_calls` blocks processados com dispatch explícito para `use_case.execute()`
- [ ] `tool` role messages construídos com `tool_call_id` correto
- [ ] Histórico de conversa mantido via `ConversationHistory` (PostgreSQL), iniciado zerado
- [ ] Context (account_id, phone, conversation_id) passado como parâmetros explícitos, não via RunnableConfig
- [ ] Todas as 9 skills existentes migradas e funcionando

**Task Breakdown Hint:**
- Task 1: Definir `AgentContext` dataclass e `ToolRegistry` (~4h)
- Task 2: Implementar `ConversationHistory` com PostgreSQL (substituir LangGraph checkpointer) (~6h)
- Task 3: Implementar `runner.py` — loop OpenAI function calling nativo (~8h)
- Task 4: Criar adaptador de skill — `SkillTool` que gera OpenAI tool dict (~4h)
- Task 5: Migrar as 9 skills existentes para novo padrão (~8h)
- Task 6: Testes unitários do runner e de cada skill (~6h)

**Dependencies:** None (pode começar imediatamente)

---

### Story 2: Worker Concorrente

**As a** lead no WhatsApp,
**I want to** receber resposta do agente rapidamente mesmo quando muitos outros leads estão sendo atendidos simultaneamente,
**So that I can** ter uma experiência fluida sem atrasos causados por outros usuários.

**Acceptance Criteria:**
- [ ] `WorkerDispatcher` usa `asyncio.TaskGroup` para processar jobs em paralelo
- [ ] `asyncio.Semaphore(max_concurrent=50)` limita concorrência máxima
- [ ] Cada job roda em sua própria Task sem bloquear o dequeue loop
- [ ] `max_concurrent` configurável via `settings.worker_max_concurrent` (default: 50)
- [ ] Teste de carga: 20 mensagens simultâneas processadas dentro de `max(latência_individual) + 2s`
- [ ] Graceful shutdown: ao receber SIGTERM, aguarda tasks em andamento completarem (timeout 30s)

**Task Breakdown Hint:**
- Task 1: Refatorar `WorkerDispatcher.run_forever()` para asyncio.TaskGroup (~6h)
- Task 2: Implementar Semaphore de concorrência com configuração via settings (~3h)
- Task 3: Implementar graceful shutdown com signal handlers (~4h)
- Task 4: Testes de integração de concorrência (~4h)

**Dependencies:** None (independente da missão de skills)

---

### Story 3: Retry + Dead-Letter Queue

**As a** operador do produto,
**I want to** ver jobs que falharam em uma DLQ no Redis e poder reinspetá-los,
**So that I can** entender por que um lead não recebeu resposta e reprocessar manualmente se necessário.

**Acceptance Criteria:**
- [ ] Jobs que falham são tentados novamente até `max_retries=3` com backoff exponencial (1s, 4s, 16s)
- [ ] Após esgotar tentativas, job movido para `queue:jobs:dlq` (Redis LPUSH)
- [ ] Cada entrada DLQ contém: `{job, error, attempts, failed_at, traceback}`
- [ ] `max_retries` configurável via `settings.worker_max_retries`
- [ ] Log estruturado em cada tentativa e ao mover para DLQ
- [ ] Endpoint admin `GET /admin/dlq` lista entradas da DLQ (paginado)

**Task Breakdown Hint:**
- Task 1: Implementar retry logic com backoff no `WorkerDispatcher` (~5h)
- Task 2: Implementar DLQ no `PriorityQueue` (Redis LPUSH para `queue:jobs:dlq`) (~3h)
- Task 3: Endpoint admin para inspecionar DLQ (~4h)
- Task 4: Testes unitários de retry e DLQ (~3h)

**Dependencies:** Story 2 (worker concorrente deve estar pronto)

---

### Story 4: Lock por Lead

**As a** lead no WhatsApp,
**I want to** receber apenas uma resposta por mensagem enviada,
**So that I can** não receber mensagens duplicadas ou contraditórias do agente.

**Acceptance Criteria:**
- [ ] Redis mutex `lock:lead:{account_id}:{phone}` adquirido antes de processar mensagem
- [ ] TTL do lock = 120s (tempo máximo esperado de resposta do agente)
- [ ] Se lock não disponível, job é reenfileirado com delay de 2s e `priority=HIGH`
- [ ] Máximo de 3 tentativas de refiileiramento antes de mover para DLQ
- [ ] Mutex liberado após resposta enviada ou em caso de exceção

**Task Breakdown Hint:**
- Task 1: Implementar `lead_lock` no `handle_message` usando `RedisMutex` existente (~4h)
- Task 2: Implementar reenfileiramento com delay no dispatcher (~4h)
- Task 3: Testes de concorrência com mesmo lead (~3h)

**Dependencies:** Story 2 (worker concorrente)

---

## Functional Requirements

### Must Have (P0) — Critical

#### REQ-001: Remover LangChain e LangGraph do agente

**Description:** Todo código em `src/agent/` deve usar apenas Anthropic SDK (`anthropic>=0.50`) e stdlib Python. Sem `langchain*`, `langgraph*`.

**Acceptance Criteria:**
- [ ] `uv remove langchain langgraph langchain-openai langchain-anthropic` executado com sucesso
- [ ] `src/agent/graph.py` removido ou substituído por `src/agent/runner.py`
- [ ] `src/agent/react_node.py` removido ou substituído
- [ ] `src/agent/state.py` substituído por `AgentContext` dataclass + `ConversationHistory`
- [ ] `src/agent/checkpointer.py` substituído por implementação própria

**Technical Specification:**
```python
# src/agent/runner.py
@dataclass
class AgentContext:
    account_id: int
    phone: str
    conversation_id: str
    thread_id: str  # f"{account_id}:{phone}"

async def run(
    user_message: str,
    context: AgentContext,
    tools: list[dict],
    tool_handlers: dict[str, ToolHandler],
    history: ConversationHistory,
    client: AsyncOpenAI,
    system_prompt: str,
) -> str:
    """
    OpenAI function calling agent loop.
    Returns final text response.
    """
    messages = await history.load(context.thread_id)
    messages.append({"role": "user", "content": user_message})

    while True:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            tools=tools,
            tool_choice="auto",
        )

        assistant_msg = response.choices[0].message
        messages.append(assistant_msg.model_dump())

        if assistant_msg.tool_calls is None:
            await history.save(context.thread_id, messages)
            return assistant_msg.content or ""

        for tool_call in assistant_msg.tool_calls:
            handler = tool_handlers.get(tool_call.function.name)
            if handler is None:
                result_content = f"Tool '{tool_call.function.name}' not found."
            else:
                try:
                    import json
                    result_content = await handler(
                        json.loads(tool_call.function.arguments), context
                    )
                except Exception as e:
                    result_content = f"Error: {e}"
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result_content,
            })
```

**Task Breakdown:**
- Definir `AgentContext`, `ToolHandler` type alias, `OpenAI tool dict builder: Small (3h)
- Implementar `runner.py` com loop completo: Medium (8h)
- Implementar `ConversationHistory` (async PostgreSQL JSONB): Medium (6h)
- Testes do runner com mock client: Small (4h)

**Dependencies:** None

---

#### REQ-002: Skill Adapter — OpenAI Tool Dict + ToolHandler

**Description:** Cada skill expõe dois artefatos: (1) um OpenAI tool dict com `function.parameters` JSON Schema, (2) um `ToolHandler` (corrotina async que recebe `input_dict` e `AgentContext`).

**Acceptance Criteria:**
- [ ] `src/agent/skill_base.py` define `class Skill(Protocol)` com `tool_definition` e `handle`
- [ ] Cada skill implementa o protocolo sem herdar de `BaseTool`
- [ ] `parameters` gerado a partir de Pydantic model usando `model.model_json_schema()`
- [ ] `preconditions.py` mantido; verificação feita no início de `handle()`
- [ ] `instructions.md` mantido; conteúdo incorporado no `description` do tool definition

**Technical Specification:**
```python
# src/agent/skill_base.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class Skill(Protocol):
    @property
    def tool_definition(self) -> dict: ...
    async def handle(self, input: dict, ctx: AgentContext) -> str: ...

# Example: buscar_conhecimento/skill.py
class BuscarConhecimentoInput(BaseModel):
    query: str = Field(description="Consulta de busca na base de conhecimento")

class BuscarConhecimentoSkill:
    def __init__(self, use_case: BuscarConhecimento):
        self._use_case = use_case

    @property
    def tool_definition(self) -> dict:
        schema = BuscarConhecimentoInput.model_json_schema()
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": "buscar_conhecimento",
                "description": INSTRUCTIONS_MD,  # Loaded from instructions.md
                "parameters": schema,
            },
        }

    async def handle(self, input: dict, ctx: AgentContext) -> str:
        args = BuscarConhecimentoInput.model_validate(input)
        for pre in PRECONDITIONS:
            if not await pre.check(ctx):
                return pre.block_message
        result = await self._use_case.execute(
            query=args.query, account_id=ctx.account_id
        )
        return "\n\n".join(result["chunks"]) if result["encontrado"] else "Conhecimento não encontrado."
```

**Task Breakdown:**
- Definir `Skill` Protocol e `AgentContext`: Small (2h)
- Criar `skill_loader.py` que retorna `list[Skill]`: Small (3h)
- Migrar cada uma das 9 skills (1.5h cada): Large (14h total)
- Testes por skill: Medium (8h total, ~1h por skill)

**Dependencies:** REQ-001

---

#### REQ-003: ConversationHistory — substituir LangGraph Checkpointer

**Description:** Implementar `ConversationHistory` que persiste o histórico de mensagens por thread no PostgreSQL, substituindo o `AsyncPostgresSaver` do LangGraph.

**Acceptance Criteria:**
- [ ] Tabela `conversation_messages` com colunas: `thread_id`, `messages` (JSONB), `updated_at`
- [ ] `load(thread_id) -> list[dict]` retorna lista de mensagens no formato Anthropic
- [ ] `save(thread_id, messages)` faz upsert JSONB
- [ ] `clear(thread_id)` exclui histórico (para testes)
- [ ] Trim automático: mantém apenas as últimas `max_messages=50` mensagens por thread (para evitar crescimento ilimitado de context)

**Technical Specification:**
```sql
-- Migration: add_conversation_messages
CREATE TABLE conversation_messages (
    thread_id TEXT PRIMARY KEY,
    messages  JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_conversation_messages_updated ON conversation_messages(updated_at);
```

```python
class ConversationHistory:
    def __init__(self, session_factory, max_messages: int = 50):
        ...

    async def load(self, thread_id: str) -> list[dict]:
        """Returns messages list in OpenAI format."""

    async def save(self, thread_id: str, messages: list[dict]) -> None:
        """Upsert with trim to max_messages."""

    async def clear(self, thread_id: str) -> None:
        """Delete conversation (for tests/admin)."""
```

**Task Breakdown:**
- Alembic migration para tabela: Small (2h)
- Implementar `ConversationHistory`: Small (4h)
- Testes de integração com PostgreSQL real: Small (3h)

**Dependencies:** None (pode ser feito em paralelo com REQ-001)

---

#### REQ-004: Worker Concorrente com asyncio.TaskGroup

**Description:** `WorkerDispatcher.run_forever()` deve desacoplar o dequeue do processamento. Cada job é despachado para uma `asyncio.Task` imediata; o dequeue continua sem aguardar o handler.

**Acceptance Criteria:**
- [ ] `WorkerDispatcher` usa `asyncio.Semaphore` para limitar concorrência
- [ ] Loop de dequeue nunca `await handler()`; sempre `asyncio.create_task()`
- [ ] Semaphore adquirido antes de criar task, liberado quando task completa
- [ ] Settings: `WORKER_MAX_CONCURRENT=50` (configurável via `.env.local`)
- [ ] Métricas logged: `worker_task_started`, `worker_task_completed`, `worker_task_failed`, `worker_semaphore_full`
- [ ] Shutdown limpo: ao sinalizar stop, aguarda tasks pendentes com timeout 30s

**Technical Specification:**
```python
# src/interface/worker/dispatcher.py
class WorkerDispatcher:
    def __init__(self, queue, handlers, max_concurrent: int = 50):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: set[asyncio.Task] = set()

    async def run_forever(self):
        while not self._stop_event.is_set():
            msg = await self._queue.dequeue(timeout=5)
            if msg is None:
                continue

            await self._semaphore.acquire()  # Backpressure
            task = asyncio.create_task(self._handle_with_semaphore(msg))
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)

    async def _handle_with_semaphore(self, msg: dict):
        try:
            kind = msg.get("kind")
            handler = self._handlers.get(kind)
            if handler:
                await handler(msg.get("payload", {}))
        finally:
            self._semaphore.release()

    async def drain(self, timeout: float = 30.0):
        """Await all active tasks with timeout."""
        if self._active_tasks:
            await asyncio.wait(self._active_tasks, timeout=timeout)
```

**Task Breakdown:**
- Refatorar `WorkerDispatcher`: Medium (6h)
- Adicionar settings `WORKER_MAX_CONCURRENT`: Small (1h)
- Graceful shutdown no `worker.py`: Small (3h)
- Testes de concorrência (mock handlers): Medium (4h)

**Dependencies:** None

---

#### REQ-005: Retry com Backoff Exponencial

**Description:** Handlers que lançam exceção são tentados novamente até `max_retries` vezes com delay exponencial. Após esgotar tentativas, job vai para DLQ.

**Acceptance Criteria:**
- [ ] Delays: tentativa 1→0s, tentativa 2→2s, tentativa 3→8s, tentativa 4→DLQ
- [ ] Erros transitórios (rede, timeout) causam retry; erros de validação (payload inválido) vão direto para DLQ
- [ ] Cada retry registrado no log com `attempt`, `error`, `delay`
- [ ] DLQ: Redis LIST `queue:jobs:dlq`, envelope: `{job, error, attempts, failed_at}`
- [ ] `WORKER_MAX_RETRIES=3` configurável

**Technical Specification:**
```python
async def _handle_with_retry(self, msg: dict, attempt: int = 1):
    kind = msg.get("kind")
    handler = self._handlers.get(kind)
    try:
        await handler(msg["payload"])
    except PermanentError:
        await self._send_to_dlq(msg, error="permanent_error", attempts=attempt)
    except Exception as e:
        if attempt >= self._max_retries:
            await self._send_to_dlq(msg, error=str(e), attempts=attempt)
            return
        delay = 2 ** (attempt - 1) * 2  # 0, 2, 8 seconds
        await asyncio.sleep(delay)
        await self._handle_with_retry(msg, attempt=attempt + 1)
```

**Task Breakdown:**
- Implementar retry logic no dispatcher: Medium (5h)
- Implementar `send_to_dlq()` no `PriorityQueue`: Small (3h)
- Endpoint `GET /admin/dlq`: Small (3h)
- Testes unitários: Small (3h)

**Dependencies:** REQ-004

---

#### REQ-006: Lead Lock — Mutex por Lead

**Description:** Antes de processar uma mensagem, o handler adquire um mutex Redis `lock:lead:{account_id}:{phone}` para garantir que o mesmo lead não é processado em paralelo.

**Acceptance Criteria:**
- [ ] Mutex `lock:lead:{account_id}:{phone}` com TTL=120s
- [ ] Se lock indisponível: job é reenfileirado com delay 2s e prioridade HIGH
- [ ] Máximo 3 tentativas de aquisição antes de DLQ com motivo `lead_lock_timeout`
- [ ] Lock liberado em `finally` (garantido mesmo com exceção)
- [ ] `lock_attempt`, `lock_acquired`, `lock_released`, `lock_failed` registrados no log

**Technical Specification:**
```python
# src/interface/worker/handlers/message.py
async def handle_message(payload: dict):
    account_id = payload["account_id"]
    phone = payload["contact_phone"]
    lock_key = f"lock:lead:{account_id}:{phone}"

    async with RedisMutex(redis, lock_key, ttl=120, timeout=0.5) as acquired:
        if not acquired:
            # Requeue with delay
            raise LeadLockBusy(f"Lead {phone} já em processamento")
        await _process_message(payload)
```

**Task Breakdown:**
- Implementar lead lock no `handle_message`: Small (4h)
- Implementar reenfileiramento com delay no dispatcher: Small (3h)
- Testes de concorrência com mesmo lead: Small (3h)

**Dependencies:** REQ-004, REQ-005

---

### Should Have (P1)

#### REQ-007: Sistema de Prompts Profissional

**Description:** Sistema de prompts refatorado com separação clara entre: system prompt base, contexto dinâmico (fatos long-term, dados da conta), e instruções de skills.

**Acceptance Criteria:**
- [ ] `src/agent/prompt_builder.py` retorna `str` com prompt completo
- [ ] Seções separadas: `IDENTIDADE`, `CAPACIDADES`, `CONTEXTO_DO_LEAD`, `REGRAS`
- [ ] Facts long-term injetados como seção dinâmica `MEMORIA_DO_LEAD`
- [ ] Instructions das skills **não** no system prompt — já estão no `tool.description`

**Task Breakdown:**
- Refatorar `prompt.py` → `prompt_builder.py`: Small (3h)
- Testes do builder: Small (2h)

**Dependencies:** REQ-001

---

#### REQ-008: Guards refatorados como Middleware

**Description:** `GuardService` refatorado como lista de guards assíncronos executados antes do loop do agente, não dentro do node.

**Acceptance Criteria:**
- [ ] Guards implementados como `async def check(message, context) -> GuardResult`
- [ ] `GuardResult` contém `blocked: bool` e `response: str | None`
- [ ] Executados no `handle_message` antes de chamar `runner.run()`
- [ ] `LegalMentionGuard` e `LoopDetectorGuard` migrados

**Task Breakdown:**
- Refatorar guards como middleware: Small (4h)
- Migrar guards existentes: Small (2h)
- Testes: Small (2h)

**Dependencies:** REQ-001

---

---

### Must Have (P0) — Infraestrutura & CI/CD

#### REQ-011: Hetzner — Rede Privada e Firewall

**Description:** As duas VMs (app-server e db-server) devem estar conectadas via Hetzner Private Network. O firewall deve bloquear todo tráfego externo nas portas de serviço interno, expondo apenas as portas necessárias.

**Acceptance Criteria:**
- [ ] Hetzner Private Network criada, ambas as VMs conectadas com IPs privados (`10.0.0.2` app-server, `10.0.0.3` db-server)
- [ ] Firewall `app-server`: porta 22 (SSH) restrita a IPs de administração; nenhuma outra porta exposta externamente
- [ ] Firewall `db-server`: porta 22 restrita a IPs admin; porta 5432 acessível apenas pelo IP privado do app-server
- [ ] Redis (6379) acessível apenas na interface local (bind 127.0.0.1) no app-server
- [ ] Regra DENY ALL de entrada por padrão; allowlist explícita
- [ ] `ufw` habilitado em ambas as VMs com política padrão `deny incoming`

**Technical Specification:**
```bash
# app-server firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow from <seu-ip-admin> to any port 22
ufw allow 80/tcp   # Cloudflared only (não exposto publicamente)
ufw enable

# db-server firewall
ufw default deny incoming
ufw default allow outgoing
ufw allow from <seu-ip-admin> to any port 22
ufw allow from 10.0.0.2 to any port 5432  # G2-EDUCACAO-IA-SUPORTE
ufw enable
```

**Task Breakdown:**
- Criar Hetzner Private Network e adicionar VMs: Small (1h)
- Configurar ufw em app-server: Small (1h)
- Configurar ufw em db-server: Small (1h)
- Testar conectividade e bloqueio: Small (1h)

**Dependencies:** VMs já criadas: G2-EDUCACAO-IA-SUPORTE (178.156.139.235, 10.0.0.2) e G2-EDUCACAO-IA-DB (178.156.253.2, 10.0.0.3), rede G2-educacao

---

#### REQ-012: Cloudflare Tunnel no app-server

**Description:** Cloudflare Tunnel expõe a aplicação (API porta 8000 + frontend porta 3000) para a internet sem expor IPs da Hetzner. Zero portas abertas publicamente.

**Acceptance Criteria:**
- [ ] `cloudflared` instalado e rodando como systemd service no app-server
- [ ] Tunnel autenticado com conta Cloudflare do projeto
- [ ] Rota `api-iag2.ianexo.com.br` → `http://localhost:8000`
- [ ] Rota `panel-iag2.ianexo.com.br` → `http://localhost:3000`
- [ ] `cloudflared service install` configurado para restart automático
- [ ] Health check da tunnel: `systemctl status cloudflared` active
- [ ] TLS terminado no Cloudflare (SSL Full Strict)

**Technical Specification:**
```bash
# /etc/cloudflared/config.yml
tunnel: <tunnel-id>
credentials-file: /etc/cloudflared/<tunnel-id>.json

ingress:
  - hostname: api-iag2.ianexo.com.br
    service: http://localhost:8000
  - hostname: panel-iag2.ianexo.com.br
    service: http://localhost:3000
  - service: http_status:404
```

**Task Breakdown:**
- Instalar cloudflared e autenticar: Small (1h)
- Criar tunnel e configurar ingress rules: Small (1h)
- Instalar como systemd service: Small (0.5h)
- Configurar DNS no Cloudflare: Small (0.5h)
- Validar TLS e health check: Small (0.5h)

**Dependencies:** REQ-011, domínio configurado no Cloudflare

---

#### REQ-013: PostgreSQL na VM de banco com backups automáticos

**Description:** PostgreSQL instalado na db-server, configurado para aceitar conexões apenas do app-server, com backups diários automáticos e rotação de 14 dias.

**Acceptance Criteria:**
- [ ] PostgreSQL 16 instalado e rodando na db-server
- [ ] `pg_hba.conf`: aceitar conexões apenas do IP privado do app-server
- [ ] `postgresql.conf`: `listen_addresses = '10.0.0.3'` (IP privado apenas)
- [ ] Database `nexoia`, user `nexoia` com senha forte criados
- [ ] Backup diário via `pg_dump` às 03:00 UTC via cron
- [ ] Backups armazenados em `/backups/postgres/YYYY-MM-DD.sql.gz`
- [ ] Rotação automática: backups com > 14 dias são deletados (cron diário)
- [ ] Backup testado: restore manual verificado com sucesso
- [ ] `POSTGRES_URL` configurado como `postgresql+asyncpg://nexoia:senha@10.0.0.3:5432/nexoia`

**Technical Specification:**
```bash
# /etc/cron.d/postgres-backup
0 3 * * * postgres pg_dump nexoia | gzip > /backups/postgres/$(date +\%Y-\%m-\%d).sql.gz

# /etc/cron.d/postgres-backup-cleanup
30 3 * * * root find /backups/postgres/ -name "*.sql.gz" -mtime +14 -delete
```

**Task Breakdown:**
- Instalar e configurar PostgreSQL 16: Small (2h)
- Criar database, user, configurar pg_hba.conf: Small (1h)
- Configurar cron de backup + cleanup: Small (1h)
- Testar restore de backup: Small (1h)
- Rodar migrations da aplicação: Small (1h)

**Dependencies:** REQ-011

---

#### REQ-014: Deploy da aplicação com Docker Compose no app-server

**Description:** Backend FastAPI e frontend Next.js deployados via Docker Compose no app-server, com restart automático e variáveis de ambiente seguras.

**Acceptance Criteria:**
- [ ] Docker e Docker Compose instalados no app-server
- [ ] `docker-compose.prod.yml` com serviços: `api`, `worker`, `web`
- [ ] Variáveis de ambiente em `.env.prod` (não commitado no git — gerenciado manualmente no servidor)
- [ ] `restart: unless-stopped` em todos os serviços
- [ ] Health checks configurados: `api` em `GET /health`; `web` em porta 3000
- [ ] Redis rodando como container no app-server (bind 127.0.0.1:6379)
- [ ] Deploy inicial validado: `curl http://localhost:8000/health` retorna `{"status":"ok"}`
- [ ] `docker compose -f docker-compose.prod.yml logs --tail=100` mostra logs limpos

**Technical Specification:**
```yaml
# docker-compose.prod.yml
services:
  api:
    image: ghcr.io/ianexo/agente-plug-api:${IMAGE_TAG}
    restart: unless-stopped
    env_file: .env.prod
    ports: ["8000:8000"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      retries: 3
  worker:
    image: ghcr.io/ianexo/agente-plug-api:${IMAGE_TAG}
    restart: unless-stopped
    env_file: .env.prod
    command: python -m worker
  web:
    image: ghcr.io/ianexo/agente-plug-web:${IMAGE_TAG}
    restart: unless-stopped
    ports: ["3000:3000"]
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --bind 127.0.0.1
```

**Task Breakdown:**
- Instalar Docker + Docker Compose no app-server: Small (1h)
- Criar `docker-compose.prod.yml`: Small (2h)
- Configurar GHCR registry access no servidor: Small (1h)
- Deploy e validação: Small (1h)

**Dependencies:** REQ-011, REQ-013, REQ-018 (GitHub Actions deve buildar imagem antes)

---

#### REQ-015: GitHub Actions — Pipeline CI (Testes + Lint + Code Review)

**Description:** Pipeline de CI que roda em todo PR para main: lint, type check, testes unitários, testes de integração e code review automatizado.

**Acceptance Criteria:**
- [ ] Workflow `.github/workflows/ci.yml` criado
- [ ] Dispara em: `pull_request` para `main` e `push` para `main`
- [ ] Jobs em paralelo onde possível: `lint`, `test-unit`, `test-integration`, `type-check`
- [ ] Job `lint`: `ruff check` + `ruff format --check` + `npm run lint` (frontend)
- [ ] Job `type-check`: `mypy src` (backend) + `npm run build` (frontend — type check via tsc)
- [ ] Job `test-unit`: `pytest tests/unit` com PostgreSQL e Redis via Docker services
- [ ] Job `test-integration`: `pytest tests/integration` com PostgreSQL e Redis reais
- [ ] Job `code-review` (P1): comentário automático no PR com análise de mudanças
- [ ] Status checks obrigatórios: todos os jobs devem passar para merge ser permitido
- [ ] Cache de dependências: `uv` cache e `node_modules` cache
- [ ] Tempo total da pipeline < 5 minutos

**Technical Specification:**
```yaml
# .github/workflows/ci.yml
name: CI
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run ruff check src tests
      - run: uv run ruff format --check src tests
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd apps/web && npm ci && npm run lint

  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run mypy src
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd apps/web && npm ci && npm run build

  test-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pytest tests/unit --cov=nexoia --cov-report=xml
      - uses: codecov/codecov-action@v4

  test-integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_DB: nexoia_test, POSTGRES_USER: nexoia, POSTGRES_PASSWORD: test }
        options: --health-cmd pg_isready
      redis:
        image: redis:7
        options: --health-cmd "redis-cli ping"
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv run pytest tests/integration
```

**Task Breakdown:**
- Criar `.github/workflows/ci.yml` com todos os jobs: Medium (4h)
- Configurar secrets no GitHub (DB_URL_TEST, etc.): Small (0.5h)
- Ajustar testes para rodarem no CI: Small (2h)
- Validar pipeline rodando com PR real: Small (1h)

**Dependencies:** Repositório no GitHub configurado

---

#### REQ-016: GitHub Actions — Pipeline CD (Deploy automático)

**Description:** Após merge na main (CI verde), pipeline de CD faz build das imagens Docker, push para GHCR e deploy no app-server via SSH.

**Acceptance Criteria:**
- [ ] Workflow `.github/workflows/cd.yml` criado
- [ ] Dispara apenas em `push` para `main` (após CI passar)
- [ ] Build de imagem Docker para `apps/api/` → `ghcr.io/ianexo/agente-plug-api:<sha>`
- [ ] Build de imagem Docker para `apps/web/` → `ghcr.io/ianexo/agente-plug-web:<sha>`
- [ ] Push para GHCR com tag `latest` e `<git-sha>`
- [ ] Deploy via SSH: `docker compose pull && docker compose up -d --no-build`
- [ ] Zero-downtime: rolling update garantido pelo Docker health check
- [ ] Notificação de falha no deploy via GitHub Actions summary
- [ ] `Dockerfile` para api e web criados e otimizados (multi-stage build, camadas de cache)

**Technical Specification:**
```yaml
# .github/workflows/cd.yml
name: CD
on:
  push:
    branches: [main]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - name: Build & push API
        uses: docker/build-push-action@v5
        with:
          context: apps/api
          push: true
          tags: |
            ghcr.io/ianexo/agente-plug-api:latest
            ghcr.io/ianexo/agente-plug-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
      - name: Build & push Web
        uses: docker/build-push-action@v5
        with:
          context: apps/web
          push: true
          tags: |
            ghcr.io/ianexo/agente-plug-web:latest
            ghcr.io/ianexo/agente-plug-web:${{ github.sha }}
      - name: Deploy to production
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.PROD_SERVER_IP }}
          username: deploy
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            cd /opt/agente-plug
            export IMAGE_TAG=${{ github.sha }}
            docker compose -f docker-compose.prod.yml pull
            docker compose -f docker-compose.prod.yml up -d --remove-orphans
            docker image prune -f
```

**Task Breakdown:**
- Criar `Dockerfile` multi-stage para api: Small (2h)
- Criar `Dockerfile` multi-stage para web: Small (2h)
- Criar `.github/workflows/cd.yml`: Medium (3h)
- Configurar secrets no GitHub (PROD_SERVER_IP, PROD_SSH_KEY): Small (0.5h)
- Criar usuário `deploy` no servidor com permissões Docker: Small (1h)
- Validar deploy ponta a ponta: Small (1h)

**Dependencies:** REQ-014, REQ-015

---

#### REQ-017: GitHub — Proteção da branch main

**Description:** A branch `main` deve ser protegida: nenhum push direto, apenas via PR aprovado com todos os checks passando.

**Acceptance Criteria:**
- [ ] Branch protection rule em `main`: `Require a pull request before merging`
- [ ] `Required approvals: 1`
- [ ] `Require status checks to pass`: lint, type-check, test-unit, test-integration todos obrigatórios
- [ ] `Require branches to be up to date before merging`
- [ ] `Restrict pushes that create matching branches`: apenas admins podem criar branches de main
- [ ] `Do not allow bypassing the above settings`: habilitado
- [ ] Configurado via GitHub API (token com permissão `repo`) para ser reproduzível

**Technical Specification:**
```bash
# Configurar via gh CLI
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["lint","type-check","test-unit","test-integration"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

**Task Breakdown:**
- Configurar branch protection via gh CLI ou GitHub UI: Small (0.5h)
- Documentar configuração em `docs/github-setup.md`: Small (0.5h)

**Dependencies:** REQ-015 (status checks devem existir antes de torná-los obrigatórios)

---

#### REQ-018: Dockerfiles de produção (multi-stage, otimizados)

**Description:** Dockerfiles para api e web otimizados com multi-stage build, layers de cache e usuário não-root.

**Acceptance Criteria:**
- [ ] `apps/api/Dockerfile`: stage `builder` (uv install), stage `runtime` (apenas runtime deps)
- [ ] `apps/web/Dockerfile`: stage `deps`, stage `builder` (next build), stage `runner`
- [ ] Usuário não-root em ambos (`USER appuser`)
- [ ] Imagem api < 500MB, imagem web < 300MB
- [ ] `.dockerignore` em ambos os apps (exclui `.git`, `node_modules`, `__pycache__`, `.env*`)
- [ ] `HEALTHCHECK` instruction em ambos

**Technical Specification:**
```dockerfile
# apps/api/Dockerfile
FROM python:3.11-slim AS builder
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM python:3.11-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY src/ src/
RUN useradd -r appuser && chown -R appuser /app
USER appuser
ENV PATH="/app/.venv/bin:$PATH"
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "nexoia.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Task Breakdown:**
- Criar `apps/api/Dockerfile` multi-stage: Small (2h)
- Criar `apps/web/Dockerfile` multi-stage: Small (2h)
- Criar `.dockerignore` para ambos: Small (0.5h)
- Testar build local e tamanho de imagem: Small (1h)

**Dependencies:** None (pode ser feito em paralelo)

---

### Nice to Have (P2)

#### REQ-009: Streaming de resposta

**Description:** Usar `client.messages.stream()` para streaming da resposta do agente, reduzindo latência percebida.

**Acceptance Criteria:**
- [ ] `runner.py` suporta modo streaming via parâmetro `stream=True`
- [ ] Callback `on_text_chunk` chamado para cada chunk de texto
- [ ] ChatNexo API é chamada com resposta final completa (streaming interno only)

**Task Breakdown:**
- Implementar modo streaming no runner: Medium (6h)

**Dependencies:** REQ-001

---

#### REQ-010: Métricas de observabilidade

**Description:** Instrumentação do agente com métricas de latência, uso de tools, e throughput de workers.

**Acceptance Criteria:**
- [ ] `agent_run_duration_seconds` — histograma por resultado (success/error)
- [ ] `agent_tool_calls_total` — counter por skill name
- [ ] `worker_jobs_total` — counter por kind e status (completed/retried/dlq)
- [ ] Exportado via `/metrics` endpoint (Prometheus format)

**Task Breakdown:**
- Adicionar instrumentação com `prometheus_client`: Medium (6h)

**Dependencies:** REQ-004

---

## Non-Functional Requirements

### Performance

- **Agent loop:** Latência p95 < 8s para resposta completa (limitado pela API LLM)
- **Throughput:** 50 mensagens simultâneas sem degradação de latência individual
- **Dequeue loop:** Tempo de dequeue + dispatch < 10ms (não bloqueia por LLM calls)
- **DB queries:** ConversationHistory load/save < 50ms

### Reliability

- **Zero perda silenciosa de jobs:** Todos os jobs terminam em completed ou DLQ
- **Lock TTL:** Nunca exceder 120s de lock por lead (mesmo em crash)
- **Graceful shutdown:** Timeout máximo de 30s para tasks em andamento
- **Retry:** Máximo 3 tentativas antes de DLQ

### Security

- **Sem mudanças de superfície de ataque:** Nenhuma nova rota pública
- **Admin endpoints:** `GET /admin/dlq` protegido com autenticação interna (header `X-Admin-Key`)
- **Contexto explícito:** account_id/phone passados como parâmetros, nunca inferidos de contexto global

### Compatibility

- **Backwards compatible:** Nenhuma mudança em schemas de webhook ou resposta ao ChatNexo
- **Migrations:** Zero-downtime (adiciona tabela, não altera existentes)
- **Python:** 3.11+ (já existente no projeto)
- **Anthropic SDK:** `openai>=1.0` com suporte a function calling e tool_calls

---

## Technical Considerations

### System Architecture

**Arquitetura Atual:**
```
WebhookRouter → Redis Queue → WorkerDispatcher (sequencial)
                                    ↓
                            handle_message()
                                    ↓
                            LangGraph.ainvoke() → StateGraph
                                    ↓
                            [raciocinar → executar → pos_execucao] loop
                                    ↓
                            LangChain.ToolNode → BaseTool._arun()
                                    ↓
                            use_case.execute()
```

**Arquitetura Proposta:**
```
WebhookRouter → Redis Queue → WorkerDispatcher (concurrent, Semaphore)
                                    ↓ asyncio.create_task()
                            handle_message()
                              ↓ acquire lead lock
                            runner.run()
                              ↓ OpenAI function calling loop
                            client.messages.create(tools=[...])
                              ↓ tool_use block
                            SkillRegistry.dispatch(tool_name, input, ctx)
                              ↓
                            use_case.execute()  [sem mudanças]
```

**Componentes novos/modificados:**

| Componente | Ação | Arquivo |
|---|---|---|
| `runner.py` | Novo | `src/agent/runner.py` |
| `skill_base.py` | Novo | `src/agent/skill_base.py` |
| `conversation_history.py` | Novo | `src/agent/conversation_history.py` |
| `prompt_builder.py` | Refatorado | `src/agent/prompt_builder.py` |
| `WorkerDispatcher` | Refatorado | `src/interface/worker/dispatcher.py` |
| `handle_message` | Refatorado | `src/interface/worker/handlers/message.py` |
| `graph.py` | Removido | `src/agent/graph.py` |
| `react_node.py` | Removido | `src/agent/react_node.py` |
| `state.py` | Removido | `src/agent/state.py` |
| `checkpointer.py` | Removido | `src/agent/checkpointer.py` |
| Cada `skill.py` | Migrado | `src/agent/skills/*/skill.py` |

### Database Schema

**Nova tabela:**
```sql
CREATE TABLE conversation_messages (
    thread_id   TEXT PRIMARY KEY,
    messages    JSONB NOT NULL DEFAULT '[]',
    updated_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_conversation_messages_updated
    ON conversation_messages(updated_at);
```

**Sem alterações:** Nenhuma tabela existente é modificada.

### Technology Stack

**Adicionado:**
- Nenhuma nova dependência — `openai` já presente; garantir versão com suporte a function calling (`openai>=1.0`)

**Removido:**
- `langchain-core`
- `langchain-anthropic`
- `langgraph`
- `langchain-openai`

### Testing Strategy

**Unitários (sem I/O):**
- `runner.py` com `AsyncOpenAI` mockado
- Cada skill com `use_case` mockado
- `WorkerDispatcher` com handlers mockados e semáforo verificado

**Integração (PostgreSQL + Redis reais):**
- `ConversationHistory` com DB real
- Retry + DLQ com Redis real
- Lead lock com Redis real
- Fluxo completo: webhook → queue → worker → runner → resposta

**Carga:**
- 20 mensagens simultâneas via worker concorrente
- Verificar que latência por mensagem não degrada com carga paralela

---

## Implementation Roadmap

### Fase 1: Fundação (Dias 1-3)
**Goal:** Estruturas base sem remover nada existente — desenvolvimento em paralelo seguro

**Tasks:**
- [ ] Task F1.1: Criar `AgentContext`, `Skill` Protocol, `ToolRegistry` em `skill_base.py`
  - Complexity: Small (3h)
  - Dependencies: None
- [ ] Task F1.2: Implementar `ConversationHistory` com migration Alembic
  - Complexity: Medium (6h)
  - Dependencies: None
- [ ] Task F1.3: Implementar `runner.py` — loop OpenAI function calling completo
  - Complexity: Medium (8h)
  - Dependencies: F1.1
- [ ] Task F1.4: Testes unitários do runner com mock client
  - Complexity: Small (4h)
  - Dependencies: F1.3

**Validation Checkpoint:** Runner retorna resposta de texto; suporta 1 tool call

---

### Fase 2: Migração de Skills (Dias 4-8)
**Goal:** Todas as 9 skills migradas para novo padrão, agente funcionando end-to-end

**Tasks:**
- [ ] Task F2.1: Migrar skill `buscar_conhecimento` (referência)
  - Complexity: Small (2h)
  - Dependencies: F1.1, F1.3
- [ ] Task F2.2: Migrar skills restantes (8 skills × 1.5h)
  - Complexity: Medium (12h)
  - Dependencies: F2.1
- [ ] Task F2.3: Refatorar `prompt_builder.py` (sem LangGraph)
  - Complexity: Small (3h)
  - Dependencies: F1.3
- [ ] Task F2.4: Refatorar guards como middleware assíncrono
  - Complexity: Small (4h)
  - Dependencies: F1.3
- [ ] Task F2.5: Refatorar `handle_message` para usar novo runner
  - Complexity: Medium (5h)
  - Dependencies: F1.3, F2.1
- [ ] Task F2.6: Testes de integração end-to-end (webhook → resposta)
  - Complexity: Medium (6h)
  - Dependencies: F2.5

**Validation Checkpoint:** Fluxo completo funcionando: mensagem WhatsApp → resposta via ChatNexo

---

### Fase 3: Worker Concorrente + Confiabilidade (Dias 9-14)
**Goal:** Worker processa múltiplos leads em paralelo com retry e DLQ

**Tasks:**
- [ ] Task F3.1: Refatorar `WorkerDispatcher` para asyncio.TaskGroup + Semaphore
  - Complexity: Medium (6h)
  - Dependencies: None (independente de Fase 1-2)
- [ ] Task F3.2: Graceful shutdown no `worker.py`
  - Complexity: Small (3h)
  - Dependencies: F3.1
- [ ] Task F3.3: Implementar retry + DLQ no dispatcher
  - Complexity: Medium (8h)
  - Dependencies: F3.1
- [ ] Task F3.4: Implementar lead lock no `handle_message`
  - Complexity: Small (4h)
  - Dependencies: F3.1, F2.5
- [ ] Task F3.5: Endpoint `GET /admin/dlq`
  - Complexity: Small (3h)
  - Dependencies: F3.3
- [ ] Task F3.6: Testes de integração de concorrência e retry
  - Complexity: Medium (6h)
  - Dependencies: F3.4
- [ ] Task F3.7: Teste de carga: 20 mensagens simultâneas
  - Complexity: Small (3h)
  - Dependencies: F3.6

**Validation Checkpoint:** 20 mensagens simultâneas processadas sem travamento; jobs falhos aparecem na DLQ

---

### Fase 5: Infraestrutura & CI/CD (Dias 15-22)
**Goal:** Produção no ar, pipeline automatizado, banco protegido, branch main segura

**Tasks:**
- [ ] Task F5.1: Criar Dockerfiles multi-stage para api e web
  - Complexity: Small (4h)
  - Dependencies: None (paralelo com Fase 1-4)
- [ ] Task F5.2: Configurar Hetzner Private Network + firewall (ufw) nas duas VMs
  - Complexity: Small (4h)
  - Dependencies: VMs já criadas: G2-EDUCACAO-IA-SUPORTE (178.156.139.235, 10.0.0.2) e G2-EDUCACAO-IA-DB (178.156.253.2, 10.0.0.3), rede G2-educacao
- [ ] Task F5.3: Instalar e configurar PostgreSQL 16 na db-server
  - Complexity: Small (5h)
  - Dependencies: F5.2
- [ ] Task F5.4: Configurar backups automáticos PostgreSQL (cron + rotação 14 dias)
  - Complexity: Small (2h)
  - Dependencies: F5.3
- [ ] Task F5.5: Instalar Cloudflare Tunnel no app-server
  - Complexity: Small (3h)
  - Dependencies: F5.2, domínio no Cloudflare
- [ ] Task F5.6: Deploy inicial da aplicação com Docker Compose no app-server
  - Complexity: Small (4h)
  - Dependencies: F5.1, F5.3, F5.5
- [ ] Task F5.7: Criar GitHub Actions CI (lint + tests + type-check)
  - Complexity: Medium (6h)
  - Dependencies: F5.1
- [ ] Task F5.8: Criar GitHub Actions CD (build imagens + deploy SSH)
  - Complexity: Medium (5h)
  - Dependencies: F5.6, F5.7
- [ ] Task F5.9: Configurar branch protection rules no GitHub
  - Complexity: Small (1h)
  - Dependencies: F5.7

**Validation Checkpoint:** `curl https://api-iag2.ianexo.com.br/health` retorna 200; PR de teste dispara CI; merge dispara CD

---

### Fase 4: Limpeza e Remoção (Dias 23-25)
**Goal:** Remover código LangChain/LangGraph e migrar testes existentes

**Tasks:**
- [ ] Task F4.1: Remover `graph.py`, `react_node.py`, `state.py`, `checkpointer.py`
  - Complexity: Small (2h)
  - Dependencies: F2.6 (todos os testes passando)
- [ ] Task F4.2: Remover dependências LangChain do `pyproject.toml`
  - Complexity: Small (1h)
  - Dependencies: F4.1
- [ ] Task F4.3: Migrar testes unitários existentes das skills
  - Complexity: Medium (6h)
  - Dependencies: F4.1
- [ ] Task F4.4: Linting e type checking limpos (`ruff`, `mypy`)
  - Complexity: Small (2h)
  - Dependencies: F4.3

**Validation Checkpoint:** `uv run pytest` verde; `mypy src` sem erros; zero imports LangChain

---

### Task Dependencies Visualization

```
Fase 1 (Fundação):
  F1.1 (Skill Protocol) → F1.3 (Runner) → F1.4 (Testes)
  F1.2 (ConvHistory)    ← independente, pode ser paralelo

Fase 2 (Skills):
  F1.3 → F2.1 (skill ref) → F2.2 (demais skills)
  F1.3 → F2.3 (prompts)
  F1.3 → F2.4 (guards)
  F2.1 + F2.4 → F2.5 (handle_message) → F2.6 (testes e2e)

Fase 3 (Worker):
  F3.1 (dispatcher) → F3.2 (shutdown)
  F3.1 → F3.3 (retry+DLQ) → F3.5 (admin endpoint)
  F3.1 + F2.5 → F3.4 (lead lock) → F3.6 (testes) → F3.7 (carga)

Fase 4 (Limpeza):
  F2.6 → F4.1 → F4.2 → F4.3 → F4.4

Critical Path: F1.1 → F1.3 → F2.1 → F2.5 → F2.6 → F4.1 → F4.4
```

---

### Effort Estimation

| Fase | Tarefas | Esforço estimado |
|---|---|---|
| Fase 1: Fundação | 4 tasks | ~21h |
| Fase 2: Migração de Skills | 6 tasks | ~32h |
| Fase 3: Worker + Confiabilidade | 7 tasks | ~33h |
| Fase 4: Limpeza | 4 tasks | ~11h |
| Fase 5: Infraestrutura & CI/CD | 9 tasks | ~34h |
| **Total** | **30 tasks** | **~131h** |

Buffer risco +20%: ~157h (~4 semanas com 1 dev)

---

## Out of Scope

1. **Kubernetes/Swarm:** Orquestração avançada — Docker Compose é suficiente para o volume atual
2. **Hetzner Load Balancer:** Sem HA nesta fase — uma VM de app única
3. **Managed Database (Hetzner DBaaS):** PostgreSQL self-managed na VM (mais controle e custo menor)
4. **Monitoramento avançado (Grafana/Prometheus):** Out of scope para v1 — logs estruturados + Cloudflare Analytics
5. **Frontend:** Nenhuma mudança no dashboard Next.js nesta fase
2. **Novos skills:** Nenhum novo skill nesta fase — apenas migração dos 9 existentes
3. **Multi-tenant isolation:** Workers compartilhados entre accounts (não isolamento por conta)
4. **Distributed workers:** Múltiplos processos worker em servidores diferentes (Celery, etc.)
5. **Streaming para o usuário final:** ChatNexo não suporta streaming; resposta enviada completa
6. **Modelo LLM:** Sem mudança de provider (continua OpenAI)
7. **RAG/Embeddings:** Sistema de busca vetorial não é alterado

---

## Open Questions & Risks

### Open Questions

#### Q1: Manter OpenAI ou migrar para Anthropic? ✅ RESOLVIDO
- **Decisão:** Manter OpenAI como LLM principal. Runner usa `openai.AsyncOpenAI` com function calling.
- `OPENAI_API_KEY` para LLM + embeddings. Sem Anthropic SDK.

#### Q2: Histórico de conversa — migrar dados existentes? ✅ RESOLVIDO
- **Decisão:** Iniciar zerado. Leads recriam histórico naturalmente. Sem migration script.
- Tabela LangGraph `checkpoints` pode ser removida após Fase 4.

#### Q3: Domínio da aplicação ✅ RESOLVIDO
- **Domínio base:** `ianexo.com.br`
- **API:** `api-iag2.ianexo.com.br` → `http://localhost:8000`
- **App:** `panel-iag2.ianexo.com.br` → `http://localhost:3000`

#### Q4: GitHub organization/repositório ✅ RESOLVIDO
- **Repo:** `ianexo/agente-plug`
- **GHCR:** `ghcr.io/ianexo/agente-plug-api` e `ghcr.io/ianexo/agente-plug-web`

#### Q5: TTL do lead lock
- **Status:** Proposta de 120s
- **Risco:** LLM calls podem levar > 120s em casos extremos de muitos tool calls
- **Opções:** (A) 120s com refresh durante execução, (B) 300s fixo
- **Owner:** Fabio
- **Deadline:** Antes de F3.4

---

### Risks & Mitigation

| Risco | Probabilidade | Impacto | Mitigação | Contingência |
|---|---|---|---|---|
| Comportamento diferente do agente após migração | Média | Alta | Testes e2e com fixtures de conversas reais | Feature flag para rollback para LangGraph |
| Histórico de conversa perdido na migração | Baixa | Média | Opção B (iniciar zerado) é segura | Migration script retroativo |
| Lead lock TTL muito curto | Baixa | Média | Iniciar com 120s e monitorar | Aumentar TTL via settings sem deploy |
| Anthropic API rate limits com 50 concurrent | Média | Alta | Semaphore limitando concurrent requests | Reduzir `WORKER_MAX_CONCURRENT` via settings |
| LangChain removal quebra imports escondidos | Baixa | Alta | Remoção em Fase 4 (após todos os testes) | Remoção incremental por módulo |

---

## Validation Checkpoints

### Checkpoint 1: Fim da Fase 1
**Critérios:**
- [ ] `runner.py` retorna texto corretamente dado histórico e tools mockados
- [ ] `ConversationHistory` salva e carrega mensagens no PostgreSQL
- [ ] Testes unitários do runner passando (cobertura ≥ 80%)
- [ ] Nenhum código existente quebrado (CI verde)

---

### Checkpoint 2: Fim da Fase 2
**Critérios:**
- [ ] Fluxo completo end-to-end: mensagem → agente (com tool call) → resposta
- [ ] Todas as 9 skills funcionando com novo padrão
- [ ] `handle_message` usando novo runner (não LangGraph)
- [ ] Testes de integração passando com Redis + PostgreSQL reais

---

### Checkpoint 3: Fim da Fase 3
**Critérios:**
- [ ] 20 mensagens simultâneas processadas sem travamento (teste de carga)
- [ ] Job com falha aparece na DLQ após 3 tentativas
- [ ] Dois webhooks para o mesmo lead → apenas 1 resposta enviada (lock funcionando)
- [ ] Graceful shutdown: `SIGTERM` → tasks completam → processo termina limpo

---

### Checkpoint 4: Fim da Fase 4 (Entrega Final)
**Critérios:**
- [ ] `grep -r "langchain\|langgraph" apps/api/src/` retorna 0 resultados
- [ ] `uv run pytest` 100% verde
- [ ] `uv run mypy src` sem erros
- [ ] `uv run ruff check src tests` sem erros
- [ ] Nenhuma dependência LangChain em `pyproject.toml`

---

## Appendix: Task Breakdown Hints

### Estrutura de Tasks Sugerida para Taskmaster (21 tasks core)

**Fase 1 — Fundação:**
1. Criar `AgentContext`, `Skill Protocol`, `ToolRegistry` (3h)
2. Criar `ConversationHistory` + migration Alembic (6h)
3. Implementar `runner.py` — OpenAI function calling loop (8h)
4. Testes unitários do runner com mock client (4h)

**Fase 2 — Skills:**
5. Migrar `buscar_conhecimento` como skill de referência (2h)
6. Migrar `buscar_conhecimento_com_contexto` (2h)
7. Migrar `buscar_aluno_cademi` (1.5h)
8. Migrar `verificar_caso_acesso` (1.5h)
9. Migrar `verificar_elegibilidade_reembolso` (1.5h)
10. Migrar `processar_reembolso` (2h)
11. Migrar `oferecer_retencao` (1.5h)
12. Migrar `enviar_link_acesso` (1.5h)
13. Migrar `escalar_para_humano` (1.5h)
14. Refatorar `prompt_builder.py` e guards como middleware (5h)
15. Refatorar `handle_message` para usar novo runner (5h)
16. Testes de integração end-to-end (6h)

**Fase 3 — Worker:**
17. Refatorar `WorkerDispatcher` para asyncio concorrente + graceful shutdown (9h)
18. Implementar retry + DLQ + endpoint admin (11h)
19. Implementar lead lock no `handle_message` (4h)
20. Testes de integração de concorrência + carga (9h)

**Fase 4 — Limpeza:**
21. Remover LangChain/LangGraph, migrar testes restantes, CI verde (11h)

### Parallelizáveis

- Tasks 1, 2 (Fase 1) → podem rodar em paralelo
- Tasks 5-13 (skills) → podem rodar em paralelo entre si após Task 3
- Tasks 17-18 (worker) → completamente independentes das Fases 1-2

### Critical Path

Task 3 → Task 5 → Task 15 → Task 16 → Task 19 → Task 20 → Task 21

---

**End of PRD**

*Este PRD é otimizado para geração de tasks via Task Master. Todos os requisitos incluem breakdown de tasks, estimativas de complexidade e mapeamento de dependências.*
