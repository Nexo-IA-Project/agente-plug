# Spec — Migração para Skill Architecture (LLM-Orchestrator)

**Data:** 2026-04-23
**Status:** Aprovado para implementação
**Audiência:** Desenvolvedor(es) do NexoIA

---

## 1. Contexto e Motivação

O projeto NexoIA foi iniciado com uma arquitetura de pipeline determinístico:
`context_builder → sentiment → intent_router → capability_subgraph → response → save_memory`

O PRD de Arquitetura do Agente define um modelo diferente: **LLM como orquestrador central**, usando `@tool` (skills) para execução e regra de negócio. Este spec define a migração para esse modelo, mantendo a estrutura DDD existente (`domain/`, `infrastructure/`) e eliminando código morto.

**Princípio central:** O LLM decide o fluxo. O código garante as regras de negócio.

---

## 2. Mapeamento de Camadas

O PRD define 5 camadas. Dentro da estrutura DDD do projeto:

```
PRD Camada 1 — LLM (Raciocínio e Decisão)
  └─ domain/ports/llm.py              ← mantido
  └─ infrastructure/llm/              ← mantido

PRD Camada 2 — LangGraph (Orquestração)
  └─ infrastructure/langgraph_runtime/
       ├─ state.py                     ← REESCRITO: AgentState(MessagesState)
       ├─ graph_builder.py             ← REESCRITO: loop raciocinar→executar→pos_execucao
       ├─ nodes.py                     ← NOVO: raciocinar + pos_execucao
       └─ checkpointer.py              ← mantido

PRD Camada 3 — Skills (Regra de negócio)
  └─ application/skills/
       ├─ __init__.py                  ← NOVO: SKILLS = [...] registry central
       ├─ access.py                    ← NOVO: substitui capabilities/access.py
       └─ (refund, knowledge, ...)    ← futuras capabilities

PRD Camada 4 — Clients (I/O externo)
  └─ infrastructure/cademi/           ← mantido
  └─ infrastructure/chatnexo/         ← mantido
  └─ infrastructure/meta/             ← mantido

PRD Camada 5 — Repositório (Persistência)
  └─ infrastructure/db/               ← mantido integralmente

Domain (agnóstico à arquitetura do agente)
  └─ domain/entities/                 ← mantido
  └─ domain/ports/                    ← mantido
  └─ domain/value_objects/            ← mantido
  └─ domain/events/                   ← mantido
```

**O Welcome não vira skill.** É disparado por evento de compra (webhook), não por mensagem do usuário. Migra para `application/purchase_handler.py` — função async simples, sem `@tool`, sem subgrafo LangGraph.

---

## 3. State e Grafo

### 3.1 AgentState

```python
# infrastructure/langgraph_runtime/state.py
from langgraph.graph import MessagesState

class AgentState(MessagesState):
    skill_em_andamento: str | None = None
    mensagens_pendentes: list[str] = []
```

Sem campos de domínio no estado do grafo. `account_id`, `phone` e `conversation_id` viajam pelo `RunnableConfig`, não pelo estado. O grafo só gerencia: histórico de mensagens + fila inteligente.

### 3.2 Thread ID

```python
thread_id = f"{account_id}:{phone}"
```

Isolamento garantido pelo checkpointer. Um thread por usuário por tenant.

### 3.3 Estrutura do Grafo

```python
# infrastructure/langgraph_runtime/graph_builder.py
from nexoia.infrastructure.langgraph_runtime.nodes import raciocinar, pos_execucao, _roteador

graph = StateGraph(AgentState)
graph.add_node("raciocinar",   raciocinar)
graph.add_node("executar",     ToolNode(SKILLS))
graph.add_node("pos_execucao", pos_execucao)

graph.set_entry_point("raciocinar")
graph.add_conditional_edges("raciocinar", _roteador)  # tool_call? → executar : END
graph.add_edge("executar",     "pos_execucao")
graph.add_edge("pos_execucao", "raciocinar")

return graph.compile(checkpointer=checkpointer)
```

### 3.4 Nós

```python
# infrastructure/langgraph_runtime/nodes.py

async def raciocinar(state: AgentState, config: RunnableConfig) -> dict:
    ultima = state["messages"][-1]

    if state["skill_em_andamento"]:
        if _is_cancel(ultima.content):
            return {
                "skill_em_andamento": None,
                "messages": [AIMessage("Consulta cancelada.")]
            }
        return {
            "mensagens_pendentes": state["mensagens_pendentes"] + [ultima.content],
            "messages": [AIMessage(
                f"Já estou resolvendo isso. Assim que terminar, respondo!"
            )]
        }

    msgs = [SystemMessage(SYSTEM_PROMPT)] + state["messages"]
    response = await llm.ainvoke(msgs, config)

    update: dict = {"messages": [response]}
    if response.tool_calls:
        update["skill_em_andamento"] = response.tool_calls[0]["name"]
    return update


async def pos_execucao(state: AgentState) -> dict:
    update: dict = {"skill_em_andamento": None, "mensagens_pendentes": []}
    if state["mensagens_pendentes"]:
        joined = " | ".join(state["mensagens_pendentes"])
        update["messages"] = [HumanMessage(f"[pendentes]: {joined}")]
    return update


def _roteador(state: AgentState) -> str:
    last = state["messages"][-1]
    return "executar" if getattr(last, "tool_calls", None) else END


# helper — palavras que sinalizam cancelamento pelo usuário
_CANCEL_KEYWORDS = {"cancelar", "para", "esquece", "desiste", "cancela"}

def _is_cancel(text: str) -> bool:
    return any(kw in text.lower() for kw in _CANCEL_KEYWORDS)
```

**Por que `skill_em_andamento` é setado em `raciocinar` e não na skill:**
Tools retornam `str` — não têm acesso ao estado do grafo. O nó `raciocinar` detecta o `tool_call` na resposta do LLM e registra qual skill está em andamento no retorno do próprio nó.

---

## 4. Skills

### 4.1 Regra de responsabilidade

| Onde fica | O quê |
|---|---|
| `@tool` (código) | Regras de negócio com consequência real: limite de tentativas, janela de tempo, atualização de status |
| System prompt | Persona, escopo de atendimento, orientação de fluxo ao LLM |

Business rules **nunca** vão para o system prompt. O código garante invariantes independente do que o LLM decidir.

### 4.2 Anatomia de um `@tool`

```python
from langchain_core.tools import tool
from langgraph.config import get_config

@tool
async def nome_da_skill(param: str) -> str:
    """
    O que esta skill faz em uma frase.
    Use quando: <condição específica>.
    Retorna: <descrição do retorno>.
    Não use quando: <contra-indicação>.
    """
    cfg = get_config()["configurable"]
    account_id = cfg["account_id"]
    phone = cfg["phone"]

    # regra de negócio aqui — nunca no prompt
    # retorna string — nunca dict, nunca objeto
    return "resultado legível para o LLM"
```

### 4.3 Multi-tenancy via RunnableConfig

`account_id` e `phone` chegam pelo `RunnableConfig` em toda invocação:

```python
await agent.ainvoke(
    {"messages": [HumanMessage(text)]},
    config={
        "configurable": {
            "thread_id":   f"{account_id}:{phone}",
            "account_id":  account_id,
            "phone":       phone,
            "conversation_id": conversation_id,
        }
    }
)
```

O LLM nunca vê nem passa `account_id`. Impossível vazar dados entre tenants.

### 4.4 Estado intermediário entre tools: DB como store

IDs críticos (como `cademi_student_id`) não passam pelo LLM — são armazenados no `AccessCase` no banco e recuperados pela próxima tool via `account_id` + `phone` do config.

```
verificar_caso_acesso()
  └─ lê/cria AccessCase → retorna info legível

buscar_aluno_cademi(email, cpf)
  └─ encontra aluno → salva cademi_student_id no AccessCase
  └─ retorna string de confirmação

enviar_link_acesso()
  └─ lê AccessCase (via config) → já tem cademi_student_id
  └─ envia link → atualiza status → retorna confirmação
```

### 4.5 Decomposição do Access em skills

```python
# application/skills/access.py

@tool
async def verificar_caso_acesso() -> str:
    """
    Verifica se há caso de acesso em aberto para o usuário.
    Use quando: usuário relata que não consegue acessar o produto.
    Retorna: produto e email cadastrado no caso, ou informa que não há caso.
    Não use quando: dúvida não é sobre acesso a produto digital.
    """
    # lê AccessCase pelo phone+account_id do config
    # retorna dados do caso ou mensagem de não encontrado


@tool
async def buscar_aluno_cademi(
    email: str | None = None,
    cpf: str | None = None,
) -> str:
    """
    Busca aluno na plataforma Cademi por email ou CPF.
    Use quando: precisa localizar o cadastro do aluno. Tente email primeiro, CPF se falhar.
    Retorna: confirmação de encontrado ou não localizado.
    Não use quando: aluno já foi localizado em chamada anterior.
    """
    # regra de negócio no código:
    if case.search_attempts >= 3:
        return "Limite de tentativas atingido. Escale para atendimento humano."
    # busca, incrementa attempts, salva student_id no AccessCase


@tool
async def enviar_link_acesso() -> str:
    """
    Envia o link de acesso ao produto para o aluno localizado.
    Use quando: aluno foi localizado no Cademi.
    Retorna: confirmação de envio.
    Não use quando: aluno não foi localizado.
    """
    # regra de negócio no código:
    within_24h = (datetime.now(UTC) - case.created_at) < timedelta(hours=24)
    # envia free text (24h) ou template WhatsApp (>24h)
    # atualiza AccessCase → REACTIVE_LINK_SENT


@tool
async def escalar_para_humano(motivo: str) -> str:
    """
    Registra escalada para atendimento humano.
    Use quando: problema não pôde ser resolvido automaticamente após esgotadas as tentativas.
    Retorna: confirmação de escalada.
    Não use quando: problema foi resolvido.
    """
    # atualiza AccessCase → REACTIVE_ESCALATED
    # aciona handoff via chatnexo_port
```

### 4.6 Registry central

```python
# application/skills/__init__.py
from .access import (
    verificar_caso_acesso,
    buscar_aluno_cademi,
    enviar_link_acesso,
    escalar_para_humano,
)

SKILLS: list = [
    verificar_caso_acesso,
    buscar_aluno_cademi,
    enviar_link_acesso,
    escalar_para_humano,
]
```

---

## 5. Migração Incremental (Skills-First)

### Fase 1 — Fundação (sem quebrar nada)
- Criar `application/skills/__init__.py` com `SKILLS = []`
- Criar `infrastructure/langgraph_runtime/nodes.py` (raciocinar + pos_execucao)
- Nenhum arquivo deletado

### Fase 2 — Migrar Welcome
- Criar `application/purchase_handler.py` (função async, sem `@tool`)
- Migrar testes de welcome → testar `purchase_handler` diretamente
- Deletar `application/capabilities/welcome.py`

### Fase 3 — Migrar Access
- Criar `application/skills/access.py` com os 4 tools
- Migrar testes: cada cenário de cascata → teste de `buscar_aluno_cademi` isolado
- Deletar `application/capabilities/access.py`

### Fase 4 — Trocar o grafo
- Reescrever `state.py` → `AgentState`
- Reescrever `graph_builder.py` → loop 3 nós
- Deletar arquivos listados na seção 6

### Fase 5 — Limpeza final
- Deletar `application/capabilities/` (pasta inteira)
- Verificar zero imports órfãos

---

## 6. Código Morto a Deletar

| Arquivo | Motivo |
|---|---|
| `application/capabilities/welcome.py` | Substituído por `purchase_handler.py` |
| `application/capabilities/access.py` | Substituído por `skills/access.py` |
| `application/capabilities/base.py` | `Capability` ABC sem uso após migração |
| `application/capabilities/__init__.py` | Pasta eliminada |
| `application/intent_router.py` | LLM assume o papel do IntentRouter |
| `application/context_builder.py` | `MessagesState` gerencia o histórico |
| `application/sentiment.py` | Absorvido pelo system prompt |
| `application/prompts/intent_classifier.py` | Sem IntentRouter, sem uso |
| `application/prompts/sentiment.py` | Sem sentiment node, sem uso |
| `application/prompts/__init__.py` | Pasta fica vazia após deleções acima |

---

## 7. Padrão de Testes

### 7.1 Testando uma skill isolada

```python
@pytest.mark.asyncio
async def test_buscar_aluno_cademi_por_email_encontrado():
    mock_repo = AsyncMock()
    mock_repo.find_by_phone.return_value = fake_case(attempts=0, email="joao@x.com")
    mock_cademi = AsyncMock()
    mock_cademi.get_student_by_email.return_value = fake_student(id="abc")

    result = await buscar_aluno_cademi.ainvoke(
        {"email": "joao@x.com"},
        config={"configurable": {"account_id": "t1", "phone": "5511999"}}
    )

    assert "encontrado" in result.lower()
    mock_repo.update_cademi_student.assert_called_once_with(case_id=ANY, student_id="abc")


@pytest.mark.asyncio
async def test_buscar_aluno_cademi_limite_tentativas():
    mock_repo = AsyncMock()
    mock_repo.find_by_phone.return_value = fake_case(attempts=3)

    result = await buscar_aluno_cademi.ainvoke(
        {"email": "joao@x.com"},
        config={"configurable": {"account_id": "t1", "phone": "5511999"}}
    )

    assert "limite" in result.lower()
```

### 7.2 Testando o grafo (fila inteligente)

```python
@pytest.mark.asyncio
async def test_agente_enfileira_mensagem_durante_skill():
    state = {
        "messages": [HumanMessage("não consigo acessar")],
        "skill_em_andamento": "buscar_aluno_cademi",
        "mensagens_pendentes": []
    }
    resultado = await raciocinar({**state, "messages": [HumanMessage("pode cancelar")]})

    assert resultado["skill_em_andamento"] is None
    assert "cancelada" in resultado["messages"][-1].content.lower()
```

---

## 8. Decisões Adiadas

| Decisão | Quando resolver |
|---|---|
| Checkpointer em produção (Postgres vs Redis) | Ao configurar infra de produção |
| Conteúdo completo do system prompt | Ao implementar cada capability |
| Skills de Refund, Knowledge, Loja Express | Specs individuais existentes — migrar após Access |
| Modelo de LLM por tenant | Ao implementar multi-tenancy avançado |
