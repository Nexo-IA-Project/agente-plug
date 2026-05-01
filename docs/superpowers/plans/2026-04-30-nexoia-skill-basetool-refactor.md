# NexoIA — Skill BaseTool Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all skills from `@tool` closures to `BaseTool` classes with Pydantic schemas, and replace `GuardResult.skill_override` with `forced_instruction` (SystemMessage injection instead of synthetic tool_calls).

**Architecture:** Skills become `BaseTool` subclasses with `args_schema` and injected ports; factories return instances instead of closures. Guards that block now set `forced_instruction` (a SystemMessage the LLM reads) instead of fabricating `tool_calls`, preserving pure ReAct flow. The `FrustrationGuard` stub is deleted.

**Tech Stack:** LangChain `BaseTool`, Pydantic v2 `BaseModel`/`ConfigDict`, `langgraph.config.get_config`, pytest-asyncio

---

## File Structure

**Modified:**
- `src/nexoia/domain/policies/guards/__init__.py` — `GuardResult`: remove `skill_override`, add `forced_instruction`; remove `FrustrationGuard` from exports
- `src/nexoia/domain/policies/guards/legal_mention.py` — emit `forced_instruction` instead of `skill_override`
- `src/nexoia/domain/policies/guards/loop_detector.py` — emit `forced_instruction` instead of `skill_override`
- `src/nexoia/infrastructure/langgraph_runtime/nodes.py` — when guard blocks with `forced_instruction`, prepend SystemMessage and call LLM; remove synthetic `tool_calls` injection
- `src/nexoia/infrastructure/skills/access.py` — 3 closures → 3 `BaseTool` classes + factory
- `src/nexoia/infrastructure/skills/refund.py` — 3 closures → 3 `BaseTool` classes + factory
- `src/nexoia/infrastructure/skills/knowledge.py` — 2 closures → 2 `BaseTool` classes + factory
- `src/nexoia/infrastructure/skills/core.py` — 1 closure → 1 `BaseTool` class + factory
- `tests/unit/domain/policies/test_guards.py` — remove `FrustrationGuard` test; assert `forced_instruction` not `skill_override`
- `tests/unit/infrastructure/langgraph_runtime/test_nodes.py` — update for new guard path (LLM is called with SystemMessage)
- `tests/unit/infrastructure/skills/test_access_skills.py` — add direct class instantiation test
- `tests/unit/infrastructure/skills/test_refund_skills.py` — add direct class instantiation test
- `tests/unit/infrastructure/skills/test_knowledge_skills.py` — add direct class instantiation test

**Created:**
- `tests/unit/infrastructure/skills/test_core_skills.py` — tests for `EscalarParaHumanoTool`

**Deleted:**
- `src/nexoia/domain/policies/guards/frustration.py`

---

## Task 1: GuardResult + Guard Implementations + Guard Tests

**Files:**
- Modify: `src/nexoia/domain/policies/guards/__init__.py`
- Modify: `src/nexoia/domain/policies/guards/legal_mention.py`
- Modify: `src/nexoia/domain/policies/guards/loop_detector.py`
- Delete: `src/nexoia/domain/policies/guards/frustration.py`
- Modify: `tests/unit/domain/policies/test_guards.py`

- [ ] **Step 1: Write failing tests for the new guard API**

Open `tests/unit/domain/policies/test_guards.py` and replace the entire file:

```python
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from nexoia.domain.policies.guards import (
    GuardResult,
    GuardService,
    LegalMentionGuard,
    LoopDetectorGuard,
)


def _state(messages: list) -> dict:
    return {"messages": messages, "skill_em_andamento": None, "mensagens_pendentes": []}


def test_legal_mention_guard_blocks_on_procon():
    result = LegalMentionGuard().check("vou acionar o Procon!", _state([]))
    assert result.blocked is True
    assert result.reason == "legal_mention"
    assert result.forced_instruction
    assert "escalar_para_humano" in result.forced_instruction


def test_legal_mention_guard_blocks_on_advogado():
    result = LegalMentionGuard().check("vou chamar meu advogado", _state([]))
    assert result.blocked is True
    assert result.forced_instruction


def test_legal_mention_guard_passes_normal_message():
    result = LegalMentionGuard().check("quero acessar meu curso", _state([]))
    assert result.blocked is False


def test_loop_detector_blocks_when_ai_repeats():
    repeated = AIMessage("Olá! Como posso ajudar?")
    state = _state([repeated, repeated, repeated])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is True
    assert result.reason == "loop_detected"
    assert result.forced_instruction
    assert "escalar_para_humano" in result.forced_instruction


def test_loop_detector_passes_varied_messages():
    state = _state([AIMessage("Mensagem 1"), AIMessage("Mensagem 2"), AIMessage("Mensagem 3")])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is False


def test_guard_service_returns_first_blocked():
    service = GuardService([LegalMentionGuard(), LoopDetectorGuard()])
    result = service.check("acionar o Procon", _state([]))
    assert result.blocked is True
    assert result.reason == "legal_mention"


def test_guard_service_passes_clean_message():
    service = GuardService([LegalMentionGuard(), LoopDetectorGuard()])
    result = service.check("preciso de ajuda", _state([AIMessage("Ok"), AIMessage("Tudo bem?")]))
    assert result.blocked is False


def test_loop_detector_does_not_block_below_threshold():
    repeated = AIMessage("Olá! Como posso ajudar?")
    state = _state([repeated, repeated])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is False


def test_loop_detector_blocks_on_tail_not_full_window():
    different = AIMessage("Mensagem diferente")
    repeated = AIMessage("Resposta em loop")
    state = _state([different, repeated, repeated, repeated])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is True


def test_guard_result_has_no_skill_override_field():
    result = GuardResult(blocked=False)
    assert not hasattr(result, "skill_override")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/fabio/www/agente-plug
python -m pytest tests/unit/domain/policies/test_guards.py -v 2>&1 | tail -20
```

Expected: several FAILED because `skill_override` is still there and `forced_instruction` is not.

- [ ] **Step 3: Update GuardResult dataclass in `guards/__init__.py`**

Replace the full file:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    response: str = ""
    reason: str = ""
    forced_instruction: str = ""


class Guard(Protocol):
    def check(self, message: str, state: dict) -> GuardResult: ...


class GuardService:
    def __init__(self, guards: list[Guard]) -> None:
        self._guards = guards

    def check(self, message: str, state: dict) -> GuardResult:
        for guard in self._guards:
            result = guard.check(message, state)
            if result.blocked:
                return result
        return GuardResult(blocked=False)


# Deferred imports to avoid circular dependency (submodules import GuardResult from here)
from nexoia.domain.policies.guards.legal_mention import LegalMentionGuard  # noqa: E402
from nexoia.domain.policies.guards.loop_detector import LoopDetectorGuard  # noqa: E402

__all__ = [
    "GuardResult",
    "GuardService",
    "LegalMentionGuard",
    "LoopDetectorGuard",
]
```

- [ ] **Step 4: Update `legal_mention.py` to emit `forced_instruction`**

Replace the full file:

```python
from __future__ import annotations

import re

from nexoia.domain.policies.guards import GuardResult

_KEYWORDS = [
    "procon",
    "advogad",
    "processo judicial",
    "ação judicial",
    "jurídic",
    "juridic",
    "reclame aqui",
    "justiça",
    "consumidor.gov",
]
_PATTERN = re.compile("|".join(_KEYWORDS), re.IGNORECASE)


class LegalMentionGuard:
    def check(self, message: str, state: dict) -> GuardResult:
        if _PATTERN.search(message):
            return GuardResult(
                blocked=True,
                reason="legal_mention",
                forced_instruction=(
                    "INSTRUÇÃO CRÍTICA: O aluno mencionou ação legal ou órgão de defesa do consumidor. "
                    "Você DEVE chamar imediatamente a skill escalar_para_humano. "
                    "Não responda por texto — use a skill."
                ),
            )
        return GuardResult(blocked=False)
```

- [ ] **Step 5: Update `loop_detector.py` to emit `forced_instruction`**

Replace the full file:

```python
from __future__ import annotations

from langchain_core.messages import AIMessage

from nexoia.domain.policies.guards import GuardResult

_THRESHOLD = 3


class LoopDetectorGuard:
    def check(self, message: str, state: dict) -> GuardResult:
        recent_ai = [
            str(m.content)
            for m in state.get("messages", [])[-6:]
            if isinstance(m, AIMessage)
        ]
        tail = recent_ai[-_THRESHOLD:]
        if len(tail) >= _THRESHOLD and len(set(tail)) == 1:
            return GuardResult(
                blocked=True,
                reason="loop_detected",
                forced_instruction=(
                    "INSTRUÇÃO CRÍTICA: Foi detectado um loop de respostas repetidas. "
                    "Você DEVE chamar imediatamente a skill escalar_para_humano. "
                    "Não responda por texto — use a skill."
                ),
            )
        return GuardResult(blocked=False)
```

- [ ] **Step 6: Delete `frustration.py`**

```bash
rm src/nexoia/domain/policies/guards/frustration.py
```

- [ ] **Step 7: Run guard tests to verify they pass**

```bash
python -m pytest tests/unit/domain/policies/test_guards.py -v
```

Expected: all PASSED

- [ ] **Step 8: Commit**

```bash
git add src/nexoia/domain/policies/guards/__init__.py \
        src/nexoia/domain/policies/guards/legal_mention.py \
        src/nexoia/domain/policies/guards/loop_detector.py \
        tests/unit/domain/policies/test_guards.py
git rm src/nexoia/domain/policies/guards/frustration.py
git commit -m "refactor(guards): replace skill_override with forced_instruction; delete FrustrationGuard stub"
```

---

## Task 2: Update `make_raciocinar_node` for `forced_instruction`

**Files:**
- Modify: `src/nexoia/infrastructure/langgraph_runtime/nodes.py`
- Modify: `tests/unit/infrastructure/langgraph_runtime/test_nodes.py`

- [ ] **Step 1: Write failing tests for the new node behavior**

Replace the full `tests/unit/infrastructure/langgraph_runtime/test_nodes.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nexoia.domain.policies.guards import GuardResult
from nexoia.infrastructure.langgraph_runtime.nodes import make_raciocinar_node, make_pos_execucao_node


def fake_config(account_id: str = "t1", phone: str = "5511999", conv_id: str = "c1"):
    return {"configurable": {"account_id": account_id, "phone": phone, "conversation_id": conv_id}}


def base_state(messages=None, skill_em_andamento=None, mensagens_pendentes=None):
    return {
        "messages": messages or [HumanMessage("oi")],
        "skill_em_andamento": skill_em_andamento,
        "mensagens_pendentes": mensagens_pendentes or [],
    }


@pytest.mark.asyncio
async def test_raciocinar_guard_with_forced_instruction_calls_llm_with_system_message():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(
        blocked=True,
        reason="legal_mention",
        forced_instruction="INSTRUÇÃO CRÍTICA: chame escalar_para_humano.",
    )
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage(
        content="",
        tool_calls=[{"name": "escalar_para_humano", "args": {}, "id": "t1", "type": "tool_call"}],
    )
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state([HumanMessage("vou acionar o Procon")]), fake_config())
    llm.ainvoke.assert_called_once()
    msgs_used = llm.ainvoke.call_args[0][0]
    assert isinstance(msgs_used[0], SystemMessage)
    assert "INSTRUÇÃO CRÍTICA" in msgs_used[0].content
    assert result.get("skill_em_andamento") == "escalar_para_humano"


@pytest.mark.asyncio
async def test_raciocinar_guard_blocked_no_forced_instruction_returns_response():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(
        blocked=True, reason="x", response="Mensagem direta ao aluno."
    )
    llm = AsyncMock()
    long_term_repo = AsyncMock()
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state([HumanMessage("msg")]), fake_config())
    llm.ainvoke.assert_not_called()
    assert result["messages"][-1].content == "Mensagem direta ao aluno."


@pytest.mark.asyncio
async def test_raciocinar_invokes_llm_when_guard_passes():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(blocked=False)
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage("Olá, como posso ajudar?")
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state(), fake_config())
    llm.ainvoke.assert_called_once()
    assert "messages" in result


@pytest.mark.asyncio
async def test_raciocinar_queues_message_when_skill_in_progress():
    guard_service = MagicMock()
    llm = AsyncMock()
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    state = base_state(
        messages=[HumanMessage("nova mensagem")],
        skill_em_andamento="buscar_aluno_cademi",
    )
    result = await node(state, fake_config())
    llm.ainvoke.assert_not_called()
    assert "mensagens_pendentes" in result


@pytest.mark.asyncio
async def test_pos_execucao_clears_skill_em_andamento():
    cap_repo = AsyncMock()
    mem_extractor = AsyncMock()
    node = make_pos_execucao_node(cap_repo, mem_extractor)
    state = base_state(skill_em_andamento="buscar_aluno_cademi")
    result = await node(state, fake_config())
    assert result["skill_em_andamento"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/unit/infrastructure/langgraph_runtime/test_nodes.py -v 2>&1 | tail -20
```

Expected: `test_raciocinar_guard_with_forced_instruction_calls_llm_with_system_message` FAILED (old code injects tool_call without LLM); `test_raciocinar_guard_blocked_no_forced_instruction_returns_response` FAILED.

- [ ] **Step 3: Update `make_raciocinar_node` in `nodes.py`**

Replace only the guard block inside the `raciocinar` function (lines 55–72). The new block:

```python
        # 1. Guards pré-LLM
        guard_result = guard_service.check(ultima.content, state)
        if guard_result.blocked:
            if guard_result.forced_instruction:
                msgs = [SystemMessage(guard_result.forced_instruction), *state["messages"]]
                response = await llm.ainvoke(msgs, config)
                update: dict = {"messages": [response]}
                if getattr(response, "tool_calls", None):
                    update["skill_em_andamento"] = response.tool_calls[0]["name"]
                return update
            return {"messages": [AIMessage(guard_result.response or _FALLBACK_MESSAGE)]}
```

Full updated `nodes.py`:

```python
from __future__ import annotations

import asyncio
import contextlib
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.config import RunnableConfig

from nexoia.domain.policies.communication_rules import CommunicationRules
from nexoia.domain.policies.guards import GuardService
from nexoia.infrastructure.langgraph_runtime.state import AgentState
from nexoia.infrastructure.llm.system_prompt import build_system_prompt

log = structlog.get_logger(__name__)

_CANCEL_WORDS = ("cancela", "para", "esquece", "desiste")
_FALLBACK_MESSAGE = "Desculpe, não consegui processar sua solicitação. Um humano vai te ajudar em breve."
_communication_rules = CommunicationRules()


def _is_cancel(content: str) -> bool:
    return any(w in content.lower() for w in _CANCEL_WORDS)


def _roteador(state: AgentState) -> str:
    """Routes after raciocinar: execute tool if LLM made a tool call, else END."""
    from langgraph.graph import END
    last = state["messages"][-1]
    return "executar" if getattr(last, "tool_calls", None) else END


def make_raciocinar_node(
    guard_service: GuardService,
    long_term_repo: Any,
    llm: Any,
):
    async def raciocinar(state: AgentState, config: RunnableConfig) -> dict:
        cfg = config["configurable"]
        ultima = state["messages"][-1]

        # Fila inteligente — aguarda skill em andamento
        if state.get("skill_em_andamento"):
            if _is_cancel(ultima.content):
                return {
                    "skill_em_andamento": None,
                    "messages": [AIMessage("Ok, cancelei. Como posso ajudar?")],
                }
            return {
                "mensagens_pendentes": [*state.get("mensagens_pendentes", []), ultima.content],
                "messages": [AIMessage("Já estou resolvendo isso, um momentinho!")],
            }

        # 1. Guards pré-LLM
        guard_result = guard_service.check(ultima.content, state)
        if guard_result.blocked:
            if guard_result.forced_instruction:
                msgs = [SystemMessage(guard_result.forced_instruction), *state["messages"]]
                response = await llm.ainvoke(msgs, config)
                update: dict = {"messages": [response]}
                if getattr(response, "tool_calls", None):
                    update["skill_em_andamento"] = response.tool_calls[0]["name"]
                return update
            return {"messages": [AIMessage(guard_result.response or _FALLBACK_MESSAGE)]}

        # 2. Long-term facts → system prompt dinâmico
        facts = await long_term_repo.load(cfg["account_id"], cfg["phone"])
        system_prompt = build_system_prompt(long_term_facts=facts)

        # 3. LLM
        msgs = [SystemMessage(system_prompt), *state["messages"]]
        response = await llm.ainvoke(msgs, config)

        # 4. CommunicationRules — valida resposta (só para texto livre, não tool_call)
        if not getattr(response, "tool_calls", None):
            for _ in range(2):
                validated = _communication_rules.validate(response.content)
                if validated.ok:
                    break
                correction_msgs = [*msgs, SystemMessage(validated.correction_hint)]
                response = await llm.ainvoke(correction_msgs, config)
            else:
                validated = _communication_rules.validate(response.content)
                if not validated.ok:
                    response = AIMessage(_FALLBACK_MESSAGE)

        update: dict = {"messages": [response]}
        if getattr(response, "tool_calls", None):
            update["skill_em_andamento"] = response.tool_calls[0]["name"]
        return update

    return raciocinar


def make_pos_execucao_node(capability_repo: Any, memory_extractor: Any):
    async def pos_execucao(state: AgentState, config: RunnableConfig) -> dict:
        cfg = config["configurable"]
        skill_name = state.get("skill_em_andamento")
        update: dict = {"skill_em_andamento": None, "mensagens_pendentes": []}

        # Background tasks — fire-and-forget; stored only to satisfy RUF006
        _bg_tasks: list[asyncio.Task] = []

        # Registra analytics em background
        if skill_name and capability_repo:
            with contextlib.suppress(RuntimeError):
                _bg_tasks.append(asyncio.create_task(
                    capability_repo.record(
                        conversation_id=cfg["conversation_id"],
                        skill_name=skill_name,
                    )
                ))

        # Extrai long_term_facts em background
        if memory_extractor:
            with contextlib.suppress(RuntimeError):
                _bg_tasks.append(asyncio.create_task(
                    memory_extractor.extract_and_save(
                        account_id=cfg["account_id"],
                        phone=cfg["phone"],
                        messages=state["messages"],
                    )
                ))

        # Reinjeta mensagens pendentes para o próximo turno de raciocinar
        pending = state.get("mensagens_pendentes") or []
        if pending:
            joined = " | ".join(pending)
            update["messages"] = [HumanMessage(f"[mensagens_pendentes]: {joined}")]

        return update

    return pos_execucao
```

- [ ] **Step 4: Run node tests to verify they pass**

```bash
python -m pytest tests/unit/infrastructure/langgraph_runtime/test_nodes.py -v
```

Expected: all PASSED

- [ ] **Step 5: Run the full guard + node test suites together**

```bash
python -m pytest tests/unit/domain/policies/test_guards.py tests/unit/infrastructure/langgraph_runtime/test_nodes.py -v
```

Expected: all PASSED

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/infrastructure/langgraph_runtime/nodes.py \
        tests/unit/infrastructure/langgraph_runtime/test_nodes.py
git commit -m "refactor(nodes): handle forced_instruction via SystemMessage injection; remove synthetic tool_calls"
```

---

## Task 3: Migrate Access Skills to BaseTool

**Files:**
- Modify: `src/nexoia/infrastructure/skills/access.py`
- Modify: `tests/unit/infrastructure/skills/test_access_skills.py`

- [ ] **Step 1: Write a failing test for direct class instantiation**

Add to `tests/unit/infrastructure/skills/test_access_skills.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from nexoia.infrastructure.skills.access import (
    make_access_skills,
    BuscarAlunoCademiTool,
    EnviarLinkAcessoTool,
    VerificarCasoAcessoTool,
)


def test_make_access_skills_returns_three_tools():
    tools = make_access_skills(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    assert len(tools) == 3
    names = {t.name for t in tools}
    assert "verificar_caso_acesso" in names
    assert "buscar_aluno_cademi" in names
    assert "enviar_link_acesso" in names


@pytest.mark.asyncio
async def test_buscar_aluno_cademi_tool_direct_instantiation():
    buscar_uc = AsyncMock()
    buscar_uc.execute.return_value = "ESCALADO"
    tool = BuscarAlunoCademiTool(buscar_uc=buscar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.access.get_config", return_value=fake_cfg):
        result = await tool._arun(email="test@example.com", cpf=None)
    buscar_uc.execute.assert_called_once_with(
        account_id="t1", phone="5511999", email="test@example.com", cpf=None
    )
    assert result == "ESCALADO"


@pytest.mark.asyncio
async def test_verificar_caso_acesso_tool_direct_instantiation():
    verificar_uc = AsyncMock()
    verificar_uc.execute.return_value = "ESCALADO"
    tool = VerificarCasoAcessoTool(verificar_uc=verificar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.access.get_config", return_value=fake_cfg):
        result = await tool._arun(last_message="quero acesso")
    verificar_uc.execute.assert_called_once_with(
        account_id="t1", phone="5511999", last_message="quero acesso"
    )
    assert result == "ESCALADO"


@pytest.mark.asyncio
async def test_enviar_link_acesso_tool_direct_instantiation():
    enviar_uc = AsyncMock()
    enviar_uc.execute.return_value = "LINK_ENVIADO: http://cademi.com/x"
    tool = EnviarLinkAcessoTool(enviar_uc=enviar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.access.get_config", return_value=fake_cfg):
        result = await tool._arun(student_id="s1", student_name="João", within_24h_window=True)
    enviar_uc.execute.assert_called_once_with(
        account_id="t1",
        phone="5511999",
        student_id="s1",
        student_name="João",
        within_24h_window=True,
        conversation_id="c1",
    )
    assert "LINK_ENVIADO" in result
```

- [ ] **Step 2: Run to verify the tests fail (classes not exported yet)**

```bash
python -m pytest tests/unit/infrastructure/skills/test_access_skills.py -v 2>&1 | tail -15
```

Expected: ImportError or AttributeError on `BuscarAlunoCademiTool` etc.

- [ ] **Step 3: Replace `access.py` with BaseTool classes**

```python
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from nexoia.application.use_cases.access.buscar_aluno_cademi import BuscarAlunoCademi
from nexoia.application.use_cases.access.enviar_link_acesso import EnviarLinkAcesso
from nexoia.application.use_cases.access.verificar_caso import VerificarCasoAcesso
from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort


class VerificarCasoAcessoInput(BaseModel):
    last_message: str = ""


class VerificarCasoAcessoTool(BaseTool):
    name: str = "verificar_caso_acesso"
    description: str = (
        "Verifica se existe caso de acesso aberto para o aluno.\n"
        "Use quando: aluno relata problema de acesso ao produto.\n"
        "Retorna: CASO_ENCONTRADO com detalhes, ou ESCALADO se não houver caso.\n"
        "Não use quando: acesso já foi verificado nesta conversa."
    )
    args_schema: Type[BaseModel] = VerificarCasoAcessoInput

    verificar_uc: VerificarCasoAcesso

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, last_message: str = "") -> str:
        cfg = get_config()["configurable"]
        return await self.verificar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            last_message=last_message,
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class BuscarAlunoCademiInput(BaseModel):
    email: str | None = None
    cpf: str | None = None


class BuscarAlunoCademiTool(BaseTool):
    name: str = "buscar_aluno_cademi"
    description: str = (
        "Busca aluno na Cademi por email ou CPF (cascata: email → CPF → nome+telefone).\n"
        "Use quando: precisa localizar cadastro para enviar acesso. Tente email primeiro, CPF se falhar.\n"
        "Retorna: ENCONTRADO com nome e student_id, SOLICITAR_CPF, ou ESCALADO.\n"
        "Não use quando: aluno já foi localizado (student_id disponível)."
    )
    args_schema: Type[BaseModel] = BuscarAlunoCademiInput

    buscar_uc: BuscarAlunoCademi

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, email: str | None = None, cpf: str | None = None) -> str:
        cfg = get_config()["configurable"]
        return await self.buscar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            email=email,
            cpf=cpf,
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class EnviarLinkAcessoInput(BaseModel):
    student_id: str
    student_name: str
    within_24h_window: bool = True


class EnviarLinkAcessoTool(BaseTool):
    name: str = "enviar_link_acesso"
    description: str = (
        "Envia link de acesso ao aluno após localização na Cademi.\n"
        "Use quando: aluno foi localizado (ENCONTRADO) e está sem acesso ao produto.\n"
        "Não use quando: aluno ainda não foi localizado — use buscar_aluno_cademi antes.\n"
        "Retorna: LINK_ENVIADO com a URL, ou ERRO."
    )
    args_schema: Type[BaseModel] = EnviarLinkAcessoInput

    enviar_uc: EnviarLinkAcesso

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(
        self, student_id: str, student_name: str, within_24h_window: bool = True
    ) -> str:
        cfg = get_config()["configurable"]
        return await self.enviar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            student_id=student_id,
            student_name=student_name,
            within_24h_window=within_24h_window,
            conversation_id=cfg.get("conversation_id"),
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_access_skills(
    access_repo: object,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    return [
        VerificarCasoAcessoTool(
            verificar_uc=VerificarCasoAcesso(repo=access_repo, chatnexo=chatnexo),
        ),
        BuscarAlunoCademiTool(
            buscar_uc=BuscarAlunoCademi(repo=access_repo, cademi=cademi),
        ),
        EnviarLinkAcessoTool(
            enviar_uc=EnviarLinkAcesso(repo=access_repo, cademi=cademi, chatnexo=chatnexo),
        ),
    ]
```

- [ ] **Step 4: Run access skill tests**

```bash
python -m pytest tests/unit/infrastructure/skills/test_access_skills.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/skills/access.py \
        tests/unit/infrastructure/skills/test_access_skills.py
git commit -m "refactor(skills): migrate access skills from @tool closures to BaseTool classes"
```

---

## Task 4: Migrate Refund Skills to BaseTool

**Files:**
- Modify: `src/nexoia/infrastructure/skills/refund.py`
- Modify: `tests/unit/infrastructure/skills/test_refund_skills.py`

- [ ] **Step 1: Write failing tests for direct class instantiation**

Replace `tests/unit/infrastructure/skills/test_refund_skills.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from nexoia.infrastructure.skills.refund import (
    make_refund_skills,
    VerificarElegibilidadeReembolsoTool,
    OfereceRetencaoTool,
    ProcessarReembolsoTool,
)


def test_make_refund_skills_returns_three_tools():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    assert len(skills) == 3


def test_make_refund_skills_tool_names():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    names = {s.name for s in skills}
    assert names == {
        "verificar_elegibilidade_reembolso",
        "oferecer_retencao",
        "processar_reembolso",
    }


@pytest.mark.asyncio
async def test_verificar_elegibilidade_tool_calls_use_case():
    verificar_uc = AsyncMock()
    verificar_uc.execute.return_value = "ELEGIVEL"
    tool = VerificarElegibilidadeReembolsoTool(verificar_uc=verificar_uc)
    fake_cfg = {"configurable": {"account_id": 1, "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.refund.get_config", return_value=fake_cfg):
        result = await tool._arun(motivo="arrependimento", email="a@b.com", cpf="12345678901")
    verificar_uc.execute.assert_called_once_with(1, "5511999", "c1", "arrependimento", "a@b.com", "12345678901")
    assert result == "ELEGIVEL"


@pytest.mark.asyncio
async def test_oferecer_retencao_tool_calls_use_case():
    reter_uc = AsyncMock()
    reter_uc.execute.return_value = "Oferta N1: ..."
    tool = OfereceRetencaoTool(reter_uc=reter_uc)
    fake_cfg = {"configurable": {"account_id": 1, "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.refund.get_config", return_value=fake_cfg):
        result = await tool._arun()
    reter_uc.execute.assert_called_once_with(1, "5511999")
    assert "Oferta" in result


@pytest.mark.asyncio
async def test_processar_reembolso_tool_calls_use_case():
    processar_uc = AsyncMock()
    processar_uc.execute.return_value = "Tô processando seu reembolso agora!"
    tool = ProcessarReembolsoTool(processar_uc=processar_uc)
    fake_cfg = {"configurable": {"account_id": 1, "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.refund.get_config", return_value=fake_cfg):
        result = await tool._arun()
    processar_uc.execute.assert_called_once_with(1, "5511999")
    assert "reembolso" in result.lower()
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/unit/infrastructure/skills/test_refund_skills.py -v 2>&1 | tail -15
```

Expected: ImportError on `VerificarElegibilidadeReembolsoTool` etc.

- [ ] **Step 3: Replace `refund.py` with BaseTool classes**

```python
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from nexoia.application.use_cases.refund.iniciar_retencao import IniciarRetencao
from nexoia.application.use_cases.refund.processar_reembolso import ProcessarReembolso
from nexoia.application.use_cases.refund.verificar_elegibilidade import VerificarElegibilidadeReembolso
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.domain.ports.legal_history_port import LegalHistoryPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort


class VerificarElegibilidadeInput(BaseModel):
    motivo: str
    email: str
    cpf: str


class VerificarElegibilidadeReembolsoTool(BaseTool):
    name: str = "verificar_elegibilidade_reembolso"
    description: str = (
        "Verifica elegibilidade do aluno para reembolso (CDC 7 dias).\n"
        "Use quando: aluno solicita reembolso e forneceu motivo + email + CPF.\n"
        "Não use quando: dados incompletos — colete-os conversacionalmente antes.\n"
        "Retorna: ELEGIVEL / INELEGIVEL com data / COMPRA_DUPLICADA."
    )
    args_schema: Type[BaseModel] = VerificarElegibilidadeInput

    verificar_uc: VerificarElegibilidadeReembolso

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, motivo: str, email: str, cpf: str) -> str:
        cfg = get_config()["configurable"]
        return await self.verificar_uc.execute(
            cfg["account_id"], cfg["phone"], cfg.get("conversation_id", ""), motivo, email, cpf
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class EmptyInput(BaseModel):
    pass


class OfereceRetencaoTool(BaseTool):
    name: str = "oferecer_retencao"
    description: str = (
        "Oferece retenção N1 ou N2 ao aluno elegível para reembolso.\n"
        "Use quando: aluno é elegível (dentro do prazo, não duplicada) e ainda não recusou N2.\n"
        "Não use quando: compra duplicada, N2 já recusado, ou aluno fora do prazo.\n"
        "Retorna: texto da oferta N1/N2 ou RETENCAO_ESGOTADA."
    )
    args_schema: Type[BaseModel] = EmptyInput

    reter_uc: IniciarRetencao

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self) -> str:
        cfg = get_config()["configurable"]
        return await self.reter_uc.execute(cfg["account_id"], cfg["phone"])

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class ProcessarReembolsoTool(BaseTool):
    name: str = "processar_reembolso"
    description: str = (
        "Processa o reembolso após dupla recusa de retenção ou compra duplicada.\n"
        "Use quando: aluno recusou N1 e N2, OU compra duplicada confirmada.\n"
        "Não use quando: N2 ainda não foi oferecido — invariante bloqueará e retornará erro.\n"
        "Retorna: mensagem padrão de processamento (PRD 7.3)."
    )
    args_schema: Type[BaseModel] = EmptyInput

    processar_uc: ProcessarReembolso

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self) -> str:
        cfg = get_config()["configurable"]
        return await self.processar_uc.execute(cfg["account_id"], cfg["phone"])

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_refund_skills(
    refund_repo: object,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
) -> list[BaseTool]:
    return [
        VerificarElegibilidadeReembolsoTool(
            verificar_uc=VerificarElegibilidadeReembolso(refund_repo, hubla, legal_history),
        ),
        OfereceRetencaoTool(
            reter_uc=IniciarRetencao(refund_repo),
        ),
        ProcessarReembolsoTool(
            processar_uc=ProcessarReembolso(refund_repo, hubla, refund_mutex),
        ),
    ]
```

> **Note:** `ProcessarReembolso` already performs the mutex check internally (with `purchase_id`). The `refund_mutex` port interface requires `(account_id, contact_id, product_id)`, so the tool cannot do an early gate check without `product_id`. The mutex invariant is upheld by the use case — calling `_arun` triggers it.

- [ ] **Step 4: Run refund skill tests**

```bash
python -m pytest tests/unit/infrastructure/skills/test_refund_skills.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/skills/refund.py \
        tests/unit/infrastructure/skills/test_refund_skills.py
git commit -m "refactor(skills): migrate refund skills from @tool closures to BaseTool classes"
```

---

## Task 5: Migrate Knowledge Skills to BaseTool

**Files:**
- Modify: `src/nexoia/infrastructure/skills/knowledge.py`
- Modify: `tests/unit/infrastructure/skills/test_knowledge_skills.py`

- [ ] **Step 1: Write failing tests for direct class instantiation**

Replace `tests/unit/infrastructure/skills/test_knowledge_skills.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nexoia.infrastructure.skills.knowledge import (
    make_knowledge_skills,
    BuscarConhecimentoTool,
    BuscarConhecimentoComContextoTool,
)


def test_make_knowledge_skills_returns_two_tools():
    skills = make_knowledge_skills(
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    assert len(skills) == 2


def test_make_knowledge_skills_tool_names():
    skills = make_knowledge_skills(
        knowledge_repo=AsyncMock(),
        usage_log_repo=AsyncMock(),
        chatnexo=AsyncMock(),
    )
    names = {s.name for s in skills}
    assert names == {"buscar_conhecimento", "buscar_conhecimento_com_contexto"}


@pytest.mark.asyncio
async def test_buscar_conhecimento_tool_returns_chunks_when_found():
    buscar_uc = AsyncMock()
    chunk = MagicMock()
    chunk.text = "Resposta aqui."
    result_obj = MagicMock()
    result_obj.status = "found"
    result_obj.chunks = [chunk]
    buscar_uc.execute.return_value = result_obj
    tool = BuscarConhecimentoTool(buscar_uc=buscar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.knowledge.get_config", return_value=fake_cfg):
        result = await tool._arun(query="como acesso o curso?")
    assert result == "Resposta aqui."


@pytest.mark.asyncio
async def test_buscar_conhecimento_tool_returns_ask_context_when_not_found():
    buscar_uc = AsyncMock()
    result_obj = MagicMock()
    result_obj.status = "ask_context"
    result_obj.chunks = []
    buscar_uc.execute.return_value = result_obj
    tool = BuscarConhecimentoTool(buscar_uc=buscar_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999"}}
    with patch("nexoia.infrastructure.skills.knowledge.get_config", return_value=fake_cfg):
        result = await tool._arun(query="algo vago")
    assert result.startswith("ASK_CONTEXT:")


@pytest.mark.asyncio
async def test_buscar_conhecimento_com_contexto_tool_calls_use_case():
    contexto_uc = AsyncMock()
    result_obj = MagicMock()
    result_obj.status = "escalated"
    result_obj.chunks = []
    contexto_uc.execute.return_value = result_obj
    tool = BuscarConhecimentoComContextoTool(contexto_uc=contexto_uc)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.knowledge.get_config", return_value=fake_cfg):
        result = await tool._arun(original_query="pergunta", context="contexto adicional")
    contexto_uc.execute.assert_called_once_with(
        original_query="pergunta",
        context="contexto adicional",
        account_id="t1",
        conversation_id="c1",
    )
    assert "ESCALATED" in result
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/unit/infrastructure/skills/test_knowledge_skills.py -v 2>&1 | tail -15
```

Expected: ImportError on `BuscarConhecimentoTool` etc.

- [ ] **Step 3: Replace `knowledge.py` with BaseTool classes**

```python
from __future__ import annotations

from typing import Any, Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from nexoia.application.use_cases.knowledge.buscar_conhecimento import BuscarConhecimento
from nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto import (
    BuscarConhecimentoComContexto,
)
from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from nexoia.application.use_cases.knowledge.synonym_expander import SynonymExpander
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.knowledge import KnowledgePort


class BuscarConhecimentoInput(BaseModel):
    query: str


class BuscarConhecimentoTool(BaseTool):
    name: str = "buscar_conhecimento"
    description: str = (
        "Busca resposta na base de conhecimento do produto (3 estratégias em cascata).\n"
        "Use quando: aluno faz pergunta técnica ou geral sobre o produto/plataforma.\n"
        "Retorna: chunks relevantes formatados OU \"ASK_CONTEXT: ...\" para pedir mais detalhes.\n"
        "Não use quando: dúvida é sobre reembolso, acesso ou loja express."
    )
    args_schema: Type[BaseModel] = BuscarConhecimentoInput

    buscar_uc: BuscarConhecimento

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, query: str) -> str:
        cfg = get_config()["configurable"]
        result = await self.buscar_uc.execute(query=query, account_id=cfg["account_id"])
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ASK_CONTEXT: Me conta um pouco mais sobre o que você está precisando."

    def _run(self, **_: object) -> str:
        raise NotImplementedError


class BuscarConhecimentoComContextoInput(BaseModel):
    original_query: str
    context: str


class BuscarConhecimentoComContextoTool(BaseTool):
    name: str = "buscar_conhecimento_com_contexto"
    description: str = (
        "4ª tentativa de busca com contexto adicional fornecido pelo aluno.\n"
        "Use quando: buscar_conhecimento retornou ASK_CONTEXT e o aluno respondeu com mais detalhes.\n"
        "Retorna: chunks relevantes formatados OU sinaliza escalação para humano."
    )
    args_schema: Type[BaseModel] = BuscarConhecimentoComContextoInput

    contexto_uc: BuscarConhecimentoComContexto

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, original_query: str, context: str) -> str:
        cfg = get_config()["configurable"]
        result = await self.contexto_uc.execute(
            original_query=original_query,
            context=context,
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id", ""),
        )
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ESCALATED: Transferindo para atendimento humano — não encontrei resposta na base de conhecimento."

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_knowledge_skills(
    knowledge_repo: KnowledgePort,
    usage_log_repo: Any,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    expander = SynonymExpander()
    extractor = KeywordExtractor()
    return [
        BuscarConhecimentoTool(
            buscar_uc=BuscarConhecimento(knowledge_repo, expander, extractor),
        ),
        BuscarConhecimentoComContextoTool(
            contexto_uc=BuscarConhecimentoComContexto(knowledge_repo, usage_log_repo, chatnexo),
        ),
    ]
```

- [ ] **Step 4: Run knowledge skill tests**

```bash
python -m pytest tests/unit/infrastructure/skills/test_knowledge_skills.py -v
```

Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/skills/knowledge.py \
        tests/unit/infrastructure/skills/test_knowledge_skills.py
git commit -m "refactor(skills): migrate knowledge skills from @tool closures to BaseTool classes"
```

---

## Task 6: Migrate Core Skill to BaseTool

**Files:**
- Modify: `src/nexoia/infrastructure/skills/core.py`
- Create: `tests/unit/infrastructure/skills/test_core_skills.py`

- [ ] **Step 1: Write failing tests for `EscalarParaHumanoTool`**

Create `tests/unit/infrastructure/skills/test_core_skills.py`:

```python
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from nexoia.infrastructure.skills.core import make_core_skills, EscalarParaHumanoTool


def test_make_core_skills_returns_one_tool():
    tools = make_core_skills(chatnexo=AsyncMock())
    assert len(tools) == 1
    assert tools[0].name == "escalar_para_humano"


@pytest.mark.asyncio
async def test_escalar_para_humano_tool_calls_chatnexo():
    chatnexo = AsyncMock()
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.core.get_config", return_value=fake_cfg):
        result = await tool._arun(reason="legal_mention")
    chatnexo.transfer_to_human.assert_called_once_with(
        account_id="t1",
        conversation_id="c1",
        reason="legal_mention",
    )
    assert "TRANSFERIDO" in result
    assert "legal_mention" in result


@pytest.mark.asyncio
async def test_escalar_para_humano_tool_default_reason():
    chatnexo = AsyncMock()
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.core.get_config", return_value=fake_cfg):
        result = await tool._arun()
    chatnexo.transfer_to_human.assert_called_once_with(
        account_id="t1",
        conversation_id="c1",
        reason="solicitado_pelo_usuario",
    )
    assert "TRANSFERIDO" in result
```

- [ ] **Step 2: Run to verify tests fail**

```bash
python -m pytest tests/unit/infrastructure/skills/test_core_skills.py -v 2>&1 | tail -15
```

Expected: ImportError on `EscalarParaHumanoTool`.

- [ ] **Step 3: Replace `core.py` with BaseTool class**

```python
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from nexoia.domain.ports.chatnexo import ChatNexoPort


class EscalarParaHumanoInput(BaseModel):
    reason: str = "solicitado_pelo_usuario"


class EscalarParaHumanoTool(BaseTool):
    name: str = "escalar_para_humano"
    description: str = (
        "Transfere o atendimento para um humano.\n"
        "Use quando: aluno pede falar com humano, ou situação não pode ser resolvida automaticamente.\n"
        "Retorna: confirmação de transferência."
    )
    args_schema: Type[BaseModel] = EscalarParaHumanoInput

    chatnexo: ChatNexoPort

    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, reason: str = "solicitado_pelo_usuario") -> str:
        cfg = get_config()["configurable"]
        await self.chatnexo.transfer_to_human(
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id"),
            reason=reason,
        )
        return f"TRANSFERIDO: Atendimento transferido para humano. Motivo: {reason}"

    def _run(self, **_: object) -> str:
        raise NotImplementedError


def make_core_skills(chatnexo: ChatNexoPort) -> list[BaseTool]:
    return [EscalarParaHumanoTool(chatnexo=chatnexo)]
```

- [ ] **Step 4: Run core skill tests**

```bash
python -m pytest tests/unit/infrastructure/skills/test_core_skills.py -v
```

Expected: all PASSED

- [ ] **Step 5: Run full unit test suite to catch regressions**

```bash
python -m pytest tests/unit/ -v --tb=short 2>&1 | tail -30
```

Expected: all PASSED. If anything fails, the error message will point to the culprit.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/infrastructure/skills/core.py \
        tests/unit/infrastructure/skills/test_core_skills.py
git commit -m "refactor(skills): migrate core skill (escalar_para_humano) from @tool closure to BaseTool class"
```
