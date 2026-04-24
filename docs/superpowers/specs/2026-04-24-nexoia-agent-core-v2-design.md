# Spec ① v2 — nexoia-agent Core (Skill Architecture)

**Data:** 2026-04-24
**Substitui:** `2026-04-17-nexoia-agent-core-design.md`
**Status:** Design aprovado — aguardando plano de implementação
**Audiência:** Desenvolvedor(es) do NexoIA

---

## 1. Contexto e Objetivo

O Core do NexoIA passa de um pipeline determinístico
(`context_builder → sentiment → intent_router → capability_subgraph → response → save_memory`)
para um **loop LLM-orquestrado** com skills como adapters de regra de negócio.

**Princípios inegociáveis:**
- LLM decide o fluxo. O código garante as regras de negócio.
- Regras de negócio nunca no system prompt — `application/use_cases/` garante invariantes independente do modelo.
- `@tool` é adapter de infraestrutura — zero regra de negócio dentro dele.
- Todo acesso a banco via SQLAlchemy 2 ORM async — SQL solto proibido (exceção: migrations Alembic).

---

## 2. Estrutura de Camadas

```
domain/
    entities/               mantido
    ports/                  mantido
    events/                 mantido
    value_objects/          mantido
    policies/               NOVO — Python puro, zero dependência externa
        guards/
            loop_detector.py
            frustration.py
            legal_mention.py
        communication_rules.py
    errors.py

application/
    use_cases/              NOVO — regra de negócio pura, sem @tool, sem LangGraph
        access/
        refund/             (spec ④)
        knowledge/          (spec ⑦)
        loja_express/       (spec ⑤)
    purchase_handler.py     proativo — sem grafo, sem LLM, chama ChatNexoPort direto
    lifecycle_handler.py    idle/close — sem grafo, sem LLM, chama ChatNexoPort direto
    message_dispatcher.py   decide texto livre vs. template Meta (regra janela 24h)
    memory/
        short_term.py       wrapper fino sobre checkpoint LangGraph
        long_term.py        repository-backed, Contact facts
        legal_history.py    busca reembolso em conversas anteriores (Art. 49 CDC)
        memory_extractor.py extração async de insights semânticos → long_term_facts
    scheduler/
        runner.py           poller de scheduled_jobs + cancel_pending_idle_jobs()

infrastructure/
    skills/                 NOVO — adapters @tool que chamam application/use_cases
        access.py
        __init__.py         SKILLS = [...]
    langgraph_runtime/
        state.py            AgentState(MessagesState)
        nodes.py            raciocinar + pos_execucao + _roteador
        graph_builder.py    loop 3 nós, injeta GuardService + LongTermRepo + LLM
        checkpointer.py     AsyncPostgresSaver
    llm/
        openai_client.py
        fake_client.py
        system_prompt.py    NOVO — template dinâmico com long_term_facts
    db/
        session.py
        models.py
        repositories/       todos os repositories (ORM, account_id obrigatório)
    cademi/
    chatnexo/
    meta/
    redis/
    crypto/
    observability/

interface/
    http/
        routers/
            health.py
            metrics.py
            webhook_purchase.py
            webhook_message.py
            admin/           reservado spec ⑥
    worker/
        dispatcher.py
        scheduler.py
        handlers/
            message.py
            purchase.py
            scheduled.py

config/
    settings.py
```

**Regra de dependência (Clean Architecture):**

```
interface → application → domain
                             ▲
infrastructure ──────────────┘
```

- `domain/` nunca importa de outras camadas.
- `application/` depende apenas de `domain/`.
- `infrastructure/` implementa as Ports de `domain/ports/`.
- `interface/` injeta implementações de `infrastructure/` nos handlers.

---

## 3. Runtime LangGraph

### 3.1 AgentState

```python
# infrastructure/langgraph_runtime/state.py
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    skill_em_andamento: str | None = None
    mensagens_pendentes: list[str] = []
```

Sem campos de domínio no estado do grafo. `account_id`, `phone` e `conversation_id`
viajam pelo `RunnableConfig` — nunca pelo estado.

### 3.2 Thread ID

```python
thread_id = f"{account_id}:{phone}"
```

Um thread por aluno por tenant. Memória de curto prazo persiste entre conversas
do mesmo aluno — o LangGraph checkpoint é amarrado ao telefone, não ao `conversation_id`.

### 3.3 Grafo

```
raciocinar ──tool_call──► executar (ToolNode) ──► pos_execucao ──► raciocinar
     │                                                                   │
  resposta direta                                                     (loop)
     │
    END
```

```python
# infrastructure/langgraph_runtime/graph_builder.py
def build_graph(guard_service, long_term_repo, llm,
                capability_repo, memory_extractor, checkpointer) -> CompiledGraph:
    raciocinar_node  = make_raciocinar_node(guard_service, long_term_repo, llm)
    pos_execucao_node = make_pos_execucao_node(capability_repo, memory_extractor)

    graph = StateGraph(AgentState)
    graph.add_node("raciocinar",   raciocinar_node)
    graph.add_node("executar",     ToolNode(SKILLS))
    graph.add_node("pos_execucao", pos_execucao_node)

    graph.set_entry_point("raciocinar")
    graph.add_conditional_edges("raciocinar", _roteador)
    graph.add_edge("executar",     "pos_execucao")
    graph.add_edge("pos_execucao", "raciocinar")

    return graph.compile(checkpointer=checkpointer)
```

### 3.4 Nó `raciocinar`

```python
# infrastructure/langgraph_runtime/nodes.py
def make_raciocinar_node(guard_service, long_term_repo, llm):
    async def raciocinar(state: AgentState, config: RunnableConfig) -> dict:
        cfg = config["configurable"]
        ultima = state["messages"][-1]

        # fila inteligente — skill em andamento
        if state["skill_em_andamento"]:
            if _is_cancel(ultima.content):
                return {"skill_em_andamento": None,
                        "messages": [AIMessage("Consulta cancelada.")]}
            return {
                "mensagens_pendentes": state["mensagens_pendentes"] + [ultima.content],
                "messages": [AIMessage("Já estou resolvendo isso, um momento!")]
            }

        # 1. Guards (domain/policies) — pré-LLM
        guard_result = guard_service.check(ultima.content, state)
        if guard_result.blocked:
            if guard_result.skill_override:
                # handoff silencioso: injeta tool_call sintético, sem mensagem ao aluno
                override_msg = AIMessage(
                    content="",
                    tool_calls=[{"name": guard_result.skill_override,
                                 "args": {}, "id": "guard_override"}]
                )
                return {"messages": [override_msg],
                        "skill_em_andamento": guard_result.skill_override}
            return {"messages": [AIMessage(guard_result.response)]}

        # 2. Long-term facts → system prompt dinâmico
        facts = await long_term_repo.load(cfg["account_id"], cfg["phone"])
        system_prompt = build_system_prompt(facts)

        # 3. LLM
        msgs = [SystemMessage(system_prompt)] + state["messages"]
        response = await llm.ainvoke(msgs, config)

        # 4. CommunicationRules — pós-LLM
        validated = communication_rules.validate(response.content)
        if not validated.ok:
            for _ in range(2):                          # retry máx 2x
                response = await llm.ainvoke(
                    msgs + [SystemMessage(validated.correction_hint)], config)
                validated = communication_rules.validate(response.content)
                if validated.ok:
                    break
            else:
                response = AIMessage(FALLBACK_MESSAGE)  # fallback genérico

        update: dict = {"messages": [response]}
        if response.tool_calls:
            update["skill_em_andamento"] = response.tool_calls[0]["name"]
        return update

    return raciocinar
```

### 3.5 Nó `pos_execucao`

Criado via factory para permitir DI, igual ao `raciocinar`.

```python
def make_pos_execucao_node(capability_repo, memory_extractor):
    async def pos_execucao(state: AgentState, config: RunnableConfig) -> dict:
        cfg = config["configurable"]
        update: dict = {"skill_em_andamento": None, "mensagens_pendentes": []}

        # registra analytics (background)
        asyncio.create_task(
            capability_repo.record(
                conversation_id=cfg["conversation_id"],
                skill_name=state["skill_em_andamento"],   # lido antes de limpar
            )
        )

        # extrai insights para long_term_facts (background, não bloqueia)
        asyncio.create_task(
            memory_extractor.extract_and_save(
                account_id=cfg["account_id"],
                phone=cfg["phone"],
                messages=state["messages"],
            )
        )

        # injeta mensagens pendentes na próxima raciocinar
        if state["mensagens_pendentes"]:
            joined = " | ".join(state["mensagens_pendentes"])
            update["messages"] = [HumanMessage(f"[pendentes]: {joined}")]

        return update
    return pos_execucao
```

### 3.6 Roteador

```python
def _roteador(state: AgentState) -> str:
    last = state["messages"][-1]
    return "executar" if getattr(last, "tool_calls", None) else END
```

---

## 4. Domain Policies

### 4.1 Guards (`domain/policies/guards/`)

Guards são políticas de domínio puras — Python puro, zero framework.

```python
@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    response: str = ""
    reason: str = ""
    skill_override: str | None = None


class LegalMentionGuard:
    _KEYWORDS = {"procon", "advogado", "ação judicial", "consumidor.gov"}

    def check(self, message: str, state: AgentState) -> GuardResult:
        if any(kw in message.lower() for kw in self._KEYWORDS):
            return GuardResult(blocked=True, reason="legal_mention",
                               skill_override="escalar_para_humano")
        return GuardResult(blocked=False)


class LoopDetectorGuard:
    _THRESHOLD = 3

    def check(self, message: str, state: AgentState) -> GuardResult:
        recent = [m.content for m in state["messages"][-6:] if isinstance(m, AIMessage)]
        if len(recent) >= self._THRESHOLD and len(set(recent)) == 1:
            return GuardResult(blocked=True, reason="loop_detected",
                               skill_override="escalar_para_humano")
        return GuardResult(blocked=False)


class FrustrationGuard:
    def check(self, message: str, state: AgentState) -> GuardResult:
        # detecta hostilidade combinada com múltiplas tentativas
        # lógica baseada em keywords + contagem de mensagens hostis consecutivas
        return GuardResult(blocked=False)


class GuardService:
    def __init__(self, guards: list):
        self._guards = guards

    def check(self, message: str, state: AgentState) -> GuardResult:
        for guard in self._guards:
            result = guard.check(message, state)
            if result.blocked:
                return result
        return GuardResult(blocked=False)
```

### 4.2 CommunicationRules (`domain/policies/communication_rules.py`)

```python
@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    correction_hint: str = ""

PROHIBITED_WORDS = {"putz", "puts", "poxa", "que chato", "Claro!"}
MAX_CHARS = 300

class CommunicationRules:
    def validate(self, content: str) -> ValidationResult:
        if len(content) > MAX_CHARS:
            return ValidationResult(ok=False,
                correction_hint=f"Resposta muito longa ({len(content)} chars). Máximo {MAX_CHARS}.")
        for word in PROHIBITED_WORDS:
            if word.lower() in content.lower():
                return ValidationResult(ok=False,
                    correction_hint=f"Palavra proibida detectada: '{word}'. Reescreva.")
        if any(c in content for c in ["**", "__", "##", "- "]):
            return ValidationResult(ok=False,
                correction_hint="Sem markdown. WhatsApp não renderiza formatação.")
        return ValidationResult(ok=True)
```

---

## 5. Application Layer

### 5.1 Use Cases (`application/use_cases/`)

Regra de negócio pura. Nenhuma dependência de LangGraph ou `@tool`.
Cada use case recebe suas dependências via `__init__` (DI explícita).

```python
# application/use_cases/access/buscar_aluno_cademi.py
class BuscarAlunoCademi:
    def __init__(self, repo: AccessCaseRepo, cademi: CademiPort):
        self._repo = repo
        self._cademi = cademi

    async def execute(self, account_id: str, phone: str,
                      email: str | None = None, cpf: str | None = None) -> str:
        case = await self._repo.find_by_phone(account_id, phone)
        if not case:
            return "Nenhum caso de acesso encontrado."

        if case.search_attempts >= 3:
            return "Limite de tentativas atingido. Escalando para atendimento humano."

        student = None
        if email:
            student = await self._cademi.get_student_by_email(email)
        if not student and cpf:
            student = await self._cademi.get_student_by_cpf(cpf)

        if student:
            await self._repo.update_cademi_student(case.id, student.id)
            return f"Aluno encontrado: {student.name}."

        await self._repo.increment_attempts(case.id)
        return "Aluno não localizado. Tente com outro e-mail ou CPF."
```

### 5.2 Skills — Adapters `@tool` (`infrastructure/skills/`)

O `@tool` é adapter. Zero regra de negócio dentro dele. Dependências são injetadas via factory
— nunca instanciadas dentro do `@tool`. Isso garante portabilidade: trocar infraestrutura
(banco, cliente HTTP, microservice) exige apenas uma nova implementação de porta, nunca
editar o corpo do `@tool`.

```python
# infrastructure/skills/access.py
from langchain_core.tools import tool
from langchain_core.tools import BaseTool
from langgraph.config import get_config

def make_access_skills(
    access_repo: AccessCaseRepoPort,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    buscar_uc  = BuscarAlunoCademi(repo=access_repo, cademi=cademi)
    enviar_uc  = EnviarLinkAcesso(repo=access_repo, chatnexo=chatnexo)
    verificar_uc = VerificarCasoAcesso(repo=access_repo)

    @tool
    async def verificar_caso_acesso() -> str:
        """
        Verifica se existe caso de acesso aberto para o aluno.
        Use quando: aluno relata problema de acesso ao produto.
        Retorna: status do caso e próxima ação recomendada.
        """
        cfg = get_config()["configurable"]
        return await verificar_uc.execute(cfg["account_id"], cfg["phone"])

    @tool
    async def buscar_aluno_cademi(email: str | None = None, cpf: str | None = None) -> str:
        """
        Busca aluno na plataforma Cademi por email ou CPF.
        Use quando: precisa localizar o cadastro do aluno. Tente email primeiro, CPF se falhar.
        Retorna: confirmação de encontrado ou não localizado.
        Não use quando: aluno já foi localizado em chamada anterior.
        """
        cfg = get_config()["configurable"]
        return await buscar_uc.execute(cfg["account_id"], cfg["phone"], email=email, cpf=cpf)

    @tool
    async def enviar_link_acesso() -> str:
        """
        Envia link de acesso ao aluno após localização na Cademi.
        Use quando: aluno foi localizado e está sem acesso.
        Não use quando: aluno ainda não foi localizado (use buscar_aluno_cademi antes).
        """
        cfg = get_config()["configurable"]
        return await enviar_uc.execute(cfg["account_id"], cfg["phone"])

    return [verificar_caso_acesso, buscar_aluno_cademi, enviar_link_acesso]
```

```python
# infrastructure/skills/__init__.py
# SKILLS é montado pelo graph_builder com DI explícita — nunca como lista estática.
# Cada factory recebe as ports necessárias; o @tool fecha sobre o use case já instanciado.

from .access import make_access_skills
from .refund import make_refund_skills
from .knowledge import make_knowledge_skills

# Exportar escalar_para_humano separadamente — é skill Core, usada por todas as capabilities
from .core import escalar_para_humano
```

```python
# infrastructure/langgraph_runtime/graph_builder.py (trecho relevante)
def build_graph(
    access_repo, cademi, chatnexo,
    refund_repo, hubla, legal_history, refund_mutex,
    knowledge_repo, synonym_expander, keyword_extractor, usage_log_repo,
    guard_service, long_term_repo, llm,
    capability_repo, memory_extractor, checkpointer,
) -> CompiledGraph:

    SKILLS = (
        make_access_skills(access_repo, cademi, chatnexo) +
        make_refund_skills(refund_repo, hubla, legal_history, refund_mutex) +
        make_knowledge_skills(knowledge_repo, synonym_expander, keyword_extractor, usage_log_repo) +
        [escalar_para_humano]
    )

    raciocinar_node   = make_raciocinar_node(guard_service, long_term_repo, llm)
    pos_execucao_node = make_pos_execucao_node(capability_repo, memory_extractor)

    graph = StateGraph(AgentState)
    graph.add_node("raciocinar",   raciocinar_node)
    graph.add_node("executar",     ToolNode(SKILLS))
    graph.add_node("pos_execucao", pos_execucao_node)
    # ... edges
    return graph.compile(checkpointer=checkpointer)
```

**Portabilidade:** para usar uma capability em outro projeto ou extraí-la como microservice,
basta implementar as ports correspondentes e passar para a factory. O `@tool` não muda.

### 5.3 MessageDispatcher (`application/message_dispatcher.py`)

```python
class MessageDispatcher:
    def __init__(self, chatnexo: ChatNexoPort, conversation_repo: ConversationRepo):
        self._chatnexo = chatnexo
        self._conv_repo = conversation_repo

    async def send(self, account_id: str, conversation_id: str, content: str) -> None:
        conv = await self._conv_repo.find_by_chatnexo_id(account_id, conversation_id)
        within_window = conv.window_expires_at > datetime.now(UTC)

        if within_window:
            await self._chatnexo.send_message(account_id, conversation_id, content)
        else:
            await self._chatnexo.send_template(
                account_id, conversation_id, "fallback_generic", {}
            )
```

### 5.4 PurchaseHandler (`application/purchase_handler.py`)

Processa compra proativamente. Sem grafo, sem LLM.

```python
class PurchaseHandler:
    async def execute(self, event: PurchaseReceived) -> None:
        contact = await self._contact_repo.find_or_create(
            event.account_id, event.phone, event.name, event.email
        )
        conversation_id = await self._chatnexo.find_or_create_conversation(
            event.account_id, contact.phone
        )
        await self._access_case_repo.create(
            account_id=event.account_id,
            contact_id=contact.id,
            conversation_id=conversation_id,
            product_name=event.product_name,
            student_email=event.email,
        )
        await self._chatnexo.send_template(
            event.account_id, conversation_id, "welcome_purchase",
            {"nome": event.name, "produto": event.product_name}
        )
        await self._scheduler.create_job(
            job_type=JobType.FOLLOWUP_D1,
            account_id=event.account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(hours=24),
        )
```

### 5.5 LifecycleHandler (`application/lifecycle_handler.py`)

Idle check e encerramento. Sem grafo, sem LLM.

```python
class LifecycleHandler:
    _PING_VARIATIONS = [
        "Olá, {nome}, você está por aí ainda?",
        "Ei {nome}, ainda tá comigo?",
        "{nome}, tudo certo? Continuo aqui se quiser seguir.",
    ]
    _CLOSE_VARIATIONS = [
        "Como não vi mais sua resposta, vou encerrar por aqui. Qualquer coisa me chama!",
        "Sem resposta por aqui, então vou encerrando. Quando quiser retomar é só mandar mensagem.",
        "Vou finalizar por enquanto, {nome}. Quando quiser retomar, é só me chamar.",
    ]

    async def send_ping(self, account_id: str, phone: str, conversation_id: str) -> None:
        conv = await self._conv_repo.find_active(account_id, conversation_id)
        if not conv or conv.status in (ConversationStatus.HANDED_OFF, ConversationStatus.CLOSED_BY_TIMEOUT):
            return
        if conv.window_expires_at <= datetime.now(UTC):
            await self._conv_repo.update_status(conv.id, ConversationStatus.CLOSED_BY_TIMEOUT)
            return

        contact = await self._contact_repo.find_by_phone(account_id, phone)
        idx = hash(f"{conversation_id}:ping") % len(self._PING_VARIATIONS)
        text = self._PING_VARIATIONS[idx].format(nome=contact.name or "")
        await self._chatnexo.send_message(account_id, conversation_id, text)
        await self._scheduler.create_job(
            JobType.IDLE_CLOSE, account_id, conversation_id,
            run_at=datetime.now(UTC) + timedelta(minutes=20)
        )

    async def send_close(self, account_id: str, phone: str, conversation_id: str) -> None:
        conv = await self._conv_repo.find_active(account_id, conversation_id)
        if not conv or conv.status != ConversationStatus.IDLE_PINGED:
            return
        contact = await self._contact_repo.find_by_phone(account_id, phone)
        idx = hash(f"{conversation_id}:close") % len(self._CLOSE_VARIATIONS)
        text = self._CLOSE_VARIATIONS[idx].format(nome=contact.name or "")
        await self._chatnexo.send_message(account_id, conversation_id, text)
        await self._conv_repo.update_status(conv.id, ConversationStatus.CLOSED_BY_TIMEOUT)

    async def schedule_idle_ping(self, account_id: str, phone: str,
                                  conversation_id: str) -> None:
        await self._scheduler.create_job(
            JobType.IDLE_PING, account_id, conversation_id,
            run_at=datetime.now(UTC) + timedelta(minutes=30)
        )
```

---

## 6. Fluxos de Dados

### 6.1 Fluxo Reativo (mensagem do aluno)

```
Aluno → WhatsApp → ChatNexo
  → POST /webhook/message
    → FastAPI: valida X-Api-Key, dedup SETNX, persiste em messages, enfileira job
      → worker.handle_message(job)
          → scheduler.cancel_pending_idle_jobs(account_id, phone)
          → agent.ainvoke(
                {"messages": [HumanMessage(text)]},
                config={"configurable": {
                    "thread_id":       f"{account_id}:{phone}",
                    "account_id":      account_id,
                    "phone":           phone,
                    "conversation_id": conversation_id,
                }}
            )
              → raciocinar
                  → guard_service.check() → se bloqueado: retorna AIMessage direta
                  → long_term_repo.load() → system_prompt dinâmico
                  → LLM invocado
                  → communication_rules.validate() → retry/fallback se inválido
              → executar (ToolNode) se tool_call
              → pos_execucao
                  → registra capability_executions (background)
                  → extrai long_term_facts (background)
              → (loop ou END)
          → última AIMessage sem tool_call
          → message_dispatcher.send(account_id, conversation_id, content)
          → lifecycle_handler.schedule_idle_ping(account_id, phone, conversation_id)
```

### 6.2 Fluxo Proativo (compra Hubla)

```
Hubla → POST /webhook/purchase
  → FastAPI: valida X-Hubla-Token, dedup, persiste em webhook_events, enfileira job
    → worker.handle_purchase(job)
        → purchase_handler.execute(event)
            → cria/busca Contact e Conversation
            → cria AccessCase (status=PROATIVO_ENVIADO)
            → ChatNexoPort.send_template(welcome_purchase, vars)
            → scheduler.create_job(FOLLOWUP_D1, run_at=now+24h)
```

### 6.3 Fluxo Idle

```
job IDLE_PING dispara (30min após última mensagem do agente)
  → worker.handle_scheduled(job)
      → lifecycle_handler.send_ping()
          → Guard: HANDED_OFF ou CLOSED? → cancela
          → janela 24h expirada? → CLOSED_BY_TIMEOUT silencioso
          → ChatNexoPort.send_message(ping rotativo)
          → scheduler.create_job(IDLE_CLOSE, run_at=now+20min)

job IDLE_CLOSE dispara (20min depois)
  → lifecycle_handler.send_close()
      → Guard: status != IDLE_PINGED? → cancela (aluno respondeu)
      → ChatNexoPort.send_message(encerramento rotativo)
      → conversation.status = CLOSED_BY_TIMEOUT
```

---

## 7. Modelo de Dados

### 7.1 Tabelas do Core

Todas as tabelas da spec anterior são mantidas com um ajuste:

**`capability_executions`** — `capability_name` renomeado para `skill_name`:

```python
# infrastructure/db/models.py (SQLAlchemy ORM — sem SQL solto)
class CapabilityExecution(Base):
    __tablename__ = "capability_executions"

    id              = Column(UUID, primary_key=True, default=uuid4)
    conversation_id = Column(Text, nullable=False)
    skill_name      = Column(Text, nullable=False)
    tools_called    = Column(JSONB, nullable=False, default=list)
    duration_ms     = Column(Integer)
    outcome         = Column(Text, nullable=False)   # SUCCESS | HANDOFF | ERROR
    correlation_id  = Column(Text)
    created_at      = Column(TIMESTAMPTZ, nullable=False, default=func.now())
```

Responsável por escrever: `pos_execucao` ao limpar `skill_em_andamento`.

### 7.2 Regra ORM

Todo acesso a banco passa pelo SQLAlchemy 2 ORM async via repositories em
`infrastructure/db/repositories/`. Cada método de repository recebe `account_id`
como parâmetro explícito — queries sem filtro de tenant falham em revisão de código.

Pgvector (spec ⑥) usa `pgvector-sqlalchemy` para manter queries de similaridade
dentro do ORM:

```python
# Exemplo (spec ⑥) — sem SQL solto
stmt = (
    select(KnowledgeChunk)
    .where(KnowledgeChunk.account_id == account_id)
    .order_by(KnowledgeChunk.embedding.cosine_distance(query_vector))
    .limit(top_k)
)
```

### 7.3 Thread ID e Checkpointer

`thread_id = f"{account_id}:{phone}"` — computado em runtime, nunca armazenado.
LangGraph cria automaticamente `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`
via `AsyncPostgresSaver`.

### 7.4 Índices obrigatórios

```python
# Todos gerenciados via Alembic migrations — sem DDL solto no código
# contacts_account_phone_idx          UNIQUE (account_id, phone)
# conversations_account_chatnexo_idx  UNIQUE (account_id, chatnexo_conversation_id)
# messages_conversation_created_idx   (conversation_id, created_at DESC)
# scheduled_jobs_pending_idx          (status, run_at) WHERE status = 'PENDING'
# webhook_events_source_external_idx  UNIQUE (source, external_id)
# capability_executions_conversation_idx (conversation_id, created_at DESC)
```

---

## 8. Código Eliminado

| Arquivo | Motivo |
|---|---|
| `application/intent_router.py` | LLM assume o papel do IntentRouter |
| `application/context_builder.py` | MessagesState gerencia o histórico |
| `application/sentiment.py` | Absorvido pelo system prompt |
| `application/prompts/` | Sem IntentRouter, sem uso |
| `application/capabilities/base.py` | Capability ABC substituído por use_cases/ |
| `application/capabilities/__init__.py` | Pasta eliminada |
| `application/guards/` | Movido para domain/policies/guards/ |
| `application/response_composer.py` | Dividido em domain/policies/communication_rules.py + application/message_dispatcher.py |
| `application/conversation/lifecycle.py` | Substituído por application/lifecycle_handler.py |

---

## 9. Observabilidade

### Logging

`structlog` com output JSON. Cada log: `correlation_id`, `account_id`,
`conversation_id`, `skill_name`, `duration_ms`, `outcome`, `event`.

### Métricas Prometheus (`/metrics`)

```
webhook_received_total{source, status}
queue_depth{tier}
worker_job_duration_seconds{job_type, outcome}    histogram
skill_outcome_total{skill, outcome}
handoff_total{reason}
llm_tokens_used_total{model, purpose}
idle_check_fired_total{stage}
guard_triggered_total{guard, reason}
communication_rules_violation_total{rule}
```

### Healthcheck (`/health`)

Valida: PostgreSQL, Redis, circuit breaker OpenAI, ping ChatNexo (readiness).
Retorna 200 se OK, 503 se crítico offline.

---

## 10. Estratégia de Testes

### Pirâmide

| Camada | Localização | Ferramenta |
|---|---|---|
| Unit (policies + use_cases) | `tests/unit/` | pytest, AsyncMock, zero I/O |
| Integration (infrastructure) | `tests/integration/` | testcontainers (PG + Redis) |
| E2E (interface) | `tests/e2e/` | httpx.AsyncClient, FakeLLMClient |

### Regras inegociáveis

- Zero chamada real à OpenAI — `FakeLLMClient` com respostas mapeadas por hash de prompt
- `freezegun` para testar idle/scheduler com tempo controlado
- Coverage ≥ 80% em `domain/` + `application/`
- Coverage ≥ 90% em use cases individuais
- Guards testados como Python puro — sem fixture de LangGraph

### Exemplos de teste

```python
# Unit — policy pura
def test_legal_mention_guard_triggers():
    result = LegalMentionGuard().check("vou acionar o Procon", fake_state())
    assert result.blocked is True
    assert result.reason == "legal_mention"

# Unit — use case com mocks
@pytest.mark.asyncio
async def test_buscar_aluno_limite_tentativas():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case(attempts=3)
    result = await BuscarAlunoCademi(repo, AsyncMock()).execute("t1", "5511999", email="x@x.com")
    assert "limite" in result.lower()

# Unit — skill como adapter
@pytest.mark.asyncio
async def test_skill_repassa_config_para_use_case():
    with patch("infrastructure.skills.access.BuscarAlunoCademi") as MockUC:
        MockUC.return_value.execute = AsyncMock(return_value="ok")
        await buscar_aluno_cademi.ainvoke(
            {"email": "x@x.com"},
            config={"configurable": {"account_id": "t1", "phone": "5511"}}
        )
    MockUC.return_value.execute.assert_called_once_with(
        account_id="t1", phone="5511", email="x@x.com", cpf=None
    )

# Unit — guard bloqueia antes do LLM
@pytest.mark.asyncio
async def test_raciocinar_guard_bloqueia_llm(mock_llm):
    state = {"messages": [HumanMessage("vou acionar o Procon")],
             "skill_em_andamento": None, "mensagens_pendentes": []}
    node = make_raciocinar_node(guard_service, long_term_repo, mock_llm)
    await node(state, fake_config())
    mock_llm.ainvoke.assert_not_called()
```

---

## 11. Requisitos Funcionais

| ID | Requisito |
|---|---|
| CORE-RF-01 | `POST /webhook/purchase` — valida `X-Hubla-Token`, dedup `SETNX`, persiste, retorna 202 <100ms |
| CORE-RF-02 | `POST /webhook/message` — valida `X-Api-Key`, dedup, persiste, retorna 202 <100ms |
| CORE-RF-03 | Worker pool consome fila Redis, escalável horizontalmente, graceful shutdown 30s |
| CORE-RF-04 | Scheduler lê `scheduled_jobs` a cada 10s com lock Redis distribuído |
| CORE-RF-05 | LangGraph com `AsyncPostgresSaver`, `thread_id = "{account_id}:{phone}"` |
| CORE-RF-06 | Grafo 3 nós: `raciocinar → executar (ToolNode) → pos_execucao` |
| CORE-RF-07 | `GuardService` injetado em `raciocinar` via closure. Guards rodam pré-LLM. Se dispararem, retornam `AIMessage` direta sem invocar modelo |
| CORE-RF-08 | `CommunicationRules` valida resposta do LLM (≤300 chars, palavras proibidas, sem markdown). Retry máx 2x, fallback genérico |
| CORE-RF-09 | `MessageDispatcher` decide texto livre (janela 24h aberta) vs. template Meta aprovado |
| CORE-RF-10 | `application/use_cases/` contém toda regra de negócio — Python puro, sem `@tool`, sem LangGraph |
| CORE-RF-11 | `infrastructure/skills/` contém apenas adapters `@tool` que chamam use cases — zero regra de negócio |
| CORE-RF-12 | `raciocinar` carrega `long_term_facts` e injeta no system prompt dinamicamente antes de invocar LLM |
| CORE-RF-13 | `pos_execucao` registra `capability_executions` e dispara background update de `long_term_facts` |
| CORE-RF-14 | Worker cancela jobs `IDLE_PING`/`IDLE_CLOSE` pendentes antes de processar nova mensagem |
| CORE-RF-15 | `lifecycle_handler.py` envia ping (30min) e encerramento (20min) via `ChatNexoPort` — sem `agent.ainvoke` |
| CORE-RF-16 | `purchase_handler.py` processa compra proativamente — sem grafo, sem LLM |
| CORE-RF-17 | ChatNexo client com retry 3x backoff exponencial e circuit breaker por tenant |
| CORE-RF-18 | Legal History busca conversas anteriores por menção a reembolso dentro do prazo CDC (Art. 49) |
| CORE-RF-19 | Escalation Triggers: catálogo de 8 triggers de handoff silencioso via `ChatNexoPort.transfer_to_human(reason=...)` |
| CORE-RF-20 | Logging estruturado JSON com `correlation_id` propagado em toda a cadeia |
| CORE-RF-21 | `/health` valida PG, Redis, OpenAI, ChatNexo. `/metrics` expõe formato Prometheus |
| CORE-RF-22 | Fernet para `integration_configs.credentials_encrypted` |

---

## 12. Requisitos Não-Funcionais

| ID | Requisito |
|---|---|
| CORE-RNF-01 | Latência webhook: <100ms |
| CORE-RNF-02 | SLA proativo: compra → WhatsApp em <60s |
| CORE-RNF-03 | SLA reativo: mensagem → resposta em <30s |
| CORE-RNF-04 | Clean Architecture: `domain/` zero dependência externa. `application/` nunca importa `infrastructure/`. Validado por teste de arquitetura |
| CORE-RNF-05 | `@tool` nunca contém regra de negócio — apenas repassa para `application/use_cases/`. Regras de negócio nunca no system prompt |
| CORE-RNF-06 | ORM obrigatório: todo acesso a banco via SQLAlchemy 2 ORM async. SQL solto proibido — exceção apenas em migrations Alembic |
| CORE-RNF-07 | Tenant isolation: toda query em repository recebe `account_id` explícito. Teste de arquitetura valida ausência de queries sem filtro |
| CORE-RNF-08 | Compliance Meta: nunca enviar texto livre fora da janela 24h |
| CORE-RNF-09 | Segurança: segredos apenas via env, tokens de webhook validados antes de processar payload |
| CORE-RNF-10 | Testabilidade: coverage ≥80% em `domain/` + `application/`, ≥90% em use cases. Zero chamada real à OpenAI em testes |
| CORE-RNF-11 | Idempotência: webhooks duplicados não geram processamento duplo |
| CORE-RNF-12 | Graceful shutdown: SIGTERM com até 30s para drenar |
| CORE-RNF-13 | Observabilidade: todo fluxo rastreável por `correlation_id` |

---

## 13. Decisões Adiadas

| Decisão | Quando resolver |
|---|---|
| Conteúdo completo do system prompt (persona, tom, skills disponíveis) | Ao iniciar implementação do Core |
| Modelo de LLM por tenant (GPT-4.1-mini padrão) | Ao implementar multi-tenancy avançado |
| Checkpointer em produção (Postgres vs Redis) | Ao configurar infra de produção |
| Skills de Refund, Knowledge, Loja Express | Specs individuais existentes — reescrever após Core |
| Lógica completa de FrustrationGuard (threshold de hostilidade) | Ao implementar os guards |
