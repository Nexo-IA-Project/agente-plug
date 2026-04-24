# NexoIA Core v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate NexoIA from deterministic pipeline (`context_builder → sentiment → intent_router → capability_subgraph → response → save_memory`) to LLM-orchestrated Skill Architecture (`raciocinar → executar → pos_execucao`).

**Architecture:** 3-node LangGraph loop where the LLM decides which `@tool` to call. Skills are closures returned by factory functions (`make_<x>_skills(ports)`), injecting use cases via DI. Guards are pure-Python domain policies. Business logic lives exclusively in `application/use_cases/`. `account_id`, `phone`, and `conversation_id` travel via `RunnableConfig`, never in graph state.

**Tech Stack:** Python 3.11+, LangGraph 0.2+, LangChain Core, SQLAlchemy 2 async ORM, Redis, structlog, pytest, pytest-asyncio, AsyncMock

---

## File Map

### Create
| File | Responsibility |
|------|---------------|
| `src/nexoia/domain/policies/__init__.py` | Exports `GuardResult`, `GuardService`, `ValidationResult`, `CommunicationRules` |
| `src/nexoia/domain/policies/guards/__init__.py` | Exports all guard classes |
| `src/nexoia/domain/policies/guards/legal_mention.py` | Detect legal keywords → block pre-LLM |
| `src/nexoia/domain/policies/guards/loop_detector.py` | Detect repeated identical AI replies |
| `src/nexoia/domain/policies/guards/frustration.py` | Stub — escalates on repeated hostility |
| `src/nexoia/domain/policies/communication_rules.py` | Validate LLM output (length, words, markdown, IA reveal) |
| `src/nexoia/application/use_cases/__init__.py` | Empty |
| `src/nexoia/application/use_cases/access/__init__.py` | Empty |
| `src/nexoia/application/use_cases/access/verificar_caso.py` | Check AccessCase + platform scope |
| `src/nexoia/application/use_cases/access/buscar_aluno_cademi.py` | 3-attempt Cademi cascade |
| `src/nexoia/application/use_cases/access/enviar_link_acesso.py` | Get link + send via ChatNexo |
| `src/nexoia/infrastructure/skills/__init__.py` | Exports `make_access_skills`, `make_knowledge_skills`, `escalar_para_humano` |
| `src/nexoia/infrastructure/skills/access.py` | `make_access_skills()` factory |
| `src/nexoia/infrastructure/skills/core.py` | `escalar_para_humano` @tool |
| `src/nexoia/infrastructure/langgraph_runtime/nodes.py` | `make_raciocinar_node`, `make_pos_execucao_node`, `_roteador` |
| `src/nexoia/infrastructure/llm/system_prompt.py` | Build dynamic system prompt with long_term_facts |
| `src/nexoia/application/message_dispatcher.py` | Send text free vs. Meta template (24h window rule) |
| `src/nexoia/application/purchase_handler.py` | Process purchase event: Contact → Conversation → AccessCase → welcome template → schedule D+1 |
| `src/nexoia/application/lifecycle_handler.py` | Idle ping (30min) and close (20min) |
| `src/nexoia/application/memory/memory_extractor.py` | Background async extraction of long_term_facts |

### Modify
| File | Change |
|------|--------|
| `src/nexoia/infrastructure/langgraph_runtime/state.py` | Rewrite: `AgentState(MessagesState)` with `skill_em_andamento` + `mensagens_pendentes` |
| `src/nexoia/infrastructure/langgraph_runtime/graph_builder.py` | Rewrite: 3-node loop via `build_graph(...)` |
| `src/nexoia/interface/worker/handlers/message.py` | Wire up: load agent, invoke, dispatch reply |
| `src/nexoia/interface/worker/handlers/purchase.py` | Wire up: call `PurchaseHandler.execute()` |
| `src/nexoia/interface/worker/handlers/scheduled.py` | Wire up: call `LifecycleHandler.send_ping/send_close` |

### Delete (Task 16 — only after all tests pass)
`application/intent_router.py`, `application/context_builder.py`, `application/sentiment.py`,
`application/prompts/`, `application/capabilities/base.py`, `application/capabilities/__init__.py`,
`application/capabilities/access.py`, `application/capabilities/welcome.py`,
`application/guards/` (dir), `application/response_composer.py`,
`application/communication_rules.py`, `application/conversation/lifecycle.py`

---

## Task 1 — Domain Policies: GuardResult + Guards

**Files:**
- Create: `src/nexoia/domain/policies/__init__.py`
- Create: `src/nexoia/domain/policies/guards/__init__.py`
- Create: `src/nexoia/domain/policies/guards/legal_mention.py`
- Create: `src/nexoia/domain/policies/guards/loop_detector.py`
- Create: `src/nexoia/domain/policies/guards/frustration.py`
- Test: `tests/unit/domain/policies/test_guards.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/domain/policies/test_guards.py
from __future__ import annotations
import pytest
from langchain_core.messages import AIMessage, HumanMessage
from nexoia.domain.policies.guards import (
    GuardResult,
    GuardService,
    LegalMentionGuard,
    LoopDetectorGuard,
    FrustrationGuard,
)


def _state(messages: list) -> dict:
    return {"messages": messages, "skill_em_andamento": None, "mensagens_pendentes": []}


def test_legal_mention_guard_blocks_on_procon():
    result = LegalMentionGuard().check("vou acionar o Procon!", _state([]))
    assert result.blocked is True
    assert result.reason == "legal_mention"
    assert result.skill_override == "escalar_para_humano"


def test_legal_mention_guard_blocks_on_advogado():
    result = LegalMentionGuard().check("vou chamar meu advogado", _state([]))
    assert result.blocked is True


def test_legal_mention_guard_passes_normal_message():
    result = LegalMentionGuard().check("quero acessar meu curso", _state([]))
    assert result.blocked is False


def test_loop_detector_blocks_when_ai_repeats():
    repeated = AIMessage("Olá! Como posso ajudar?")
    state = _state([repeated, repeated, repeated])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is True
    assert result.skill_override == "escalar_para_humano"


def test_loop_detector_passes_varied_messages():
    state = _state([AIMessage("Mensagem 1"), AIMessage("Mensagem 2"), AIMessage("Mensagem 3")])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is False


def test_frustration_guard_is_stub_returns_not_blocked():
    result = FrustrationGuard().check("isso é uma bagunça!", _state([]))
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/domain/policies/test_guards.py -v
```

Expected: `ModuleNotFoundError: No module named 'nexoia.domain.policies'`

- [ ] **Step 3: Create `src/nexoia/domain/policies/__init__.py`**

```python
from __future__ import annotations

from nexoia.domain.policies.communication_rules import CommunicationRules, ValidationResult
from nexoia.domain.policies.guards import (
    FrustrationGuard,
    GuardResult,
    GuardService,
    LegalMentionGuard,
    LoopDetectorGuard,
)

__all__ = [
    "CommunicationRules",
    "ValidationResult",
    "FrustrationGuard",
    "GuardResult",
    "GuardService",
    "LegalMentionGuard",
    "LoopDetectorGuard",
]
```

- [ ] **Step 4: Create `src/nexoia/domain/policies/guards/__init__.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    response: str = ""
    reason: str = ""
    skill_override: str | None = None


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


from nexoia.domain.policies.guards.frustration import FrustrationGuard
from nexoia.domain.policies.guards.legal_mention import LegalMentionGuard
from nexoia.domain.policies.guards.loop_detector import LoopDetectorGuard

__all__ = [
    "GuardResult",
    "GuardService",
    "FrustrationGuard",
    "LegalMentionGuard",
    "LoopDetectorGuard",
]
```

- [ ] **Step 5: Create `src/nexoia/domain/policies/guards/legal_mention.py`**

```python
from __future__ import annotations

import re

from nexoia.domain.policies.guards import GuardResult

_KEYWORDS = [
    "procon",
    "advogad",
    "processo",
    "ação judicial",
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
                skill_override="escalar_para_humano",
            )
        return GuardResult(blocked=False)
```

- [ ] **Step 6: Create `src/nexoia/domain/policies/guards/loop_detector.py`**

```python
from __future__ import annotations

from langchain_core.messages import AIMessage

from nexoia.domain.policies.guards import GuardResult

_THRESHOLD = 3


class LoopDetectorGuard:
    def check(self, message: str, state: dict) -> GuardResult:
        recent_ai = [
            m.content
            for m in state.get("messages", [])[-6:]
            if isinstance(m, AIMessage)
        ]
        if len(recent_ai) >= _THRESHOLD and len(set(recent_ai)) == 1:
            return GuardResult(
                blocked=True,
                reason="loop_detected",
                skill_override="escalar_para_humano",
            )
        return GuardResult(blocked=False)
```

- [ ] **Step 7: Create `src/nexoia/domain/policies/guards/frustration.py`**

```python
from __future__ import annotations

from nexoia.domain.policies.guards import GuardResult


class FrustrationGuard:
    """Stub — lógica de detecção de hostilidade a implementar no futuro."""

    def check(self, message: str, state: dict) -> GuardResult:
        return GuardResult(blocked=False)
```

- [ ] **Step 8: Run tests and verify they pass**

```bash
uv run pytest tests/unit/domain/policies/test_guards.py -v
```

Expected: 8 tests PASSED

- [ ] **Step 9: Commit**

```bash
git add src/nexoia/domain/policies/ tests/unit/domain/policies/test_guards.py
git commit -m "feat(core-v2): add domain/policies/guards with GuardResult + GuardService"
```

---

## Task 2 — Domain Policies: CommunicationRules

**Files:**
- Create: `src/nexoia/domain/policies/communication_rules.py`
- Test: `tests/unit/domain/policies/test_communication_rules.py`

The existing `application/communication_rules.py` already has the right logic — migrating and adapting the interface from `check() -> list[ViolationType]` to `validate() -> ValidationResult`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/domain/policies/test_communication_rules.py
from __future__ import annotations
import pytest
from nexoia.domain.policies.communication_rules import CommunicationRules, ValidationResult


def test_ok_for_clean_short_message():
    result = CommunicationRules().validate("Olá, como posso ajudar?")
    assert result.ok is True


def test_fails_for_too_long_message():
    result = CommunicationRules().validate("x" * 301)
    assert result.ok is False
    assert "longa" in result.correction_hint.lower()


def test_fails_for_forbidden_word():
    result = CommunicationRules().validate("putz, que situação!")
    assert result.ok is False
    assert "proibida" in result.correction_hint.lower()


def test_fails_for_markdown():
    result = CommunicationRules().validate("**Aqui** está seu link")
    assert result.ok is False
    assert "markdown" in result.correction_hint.lower()


def test_fails_for_ia_reveal():
    result = CommunicationRules().validate("Sou uma IA e posso ajudar")
    assert result.ok is False
    assert "IA" in result.correction_hint


def test_validation_result_is_frozen():
    r = ValidationResult(ok=True)
    with pytest.raises((AttributeError, TypeError)):
        r.ok = False  # type: ignore[misc]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/domain/policies/test_communication_rules.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/domain/policies/communication_rules.py`**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

_FORBIDDEN = re.compile(
    r"(?i)\b(putz|puts|poxa|que chato|entendo entendo)\b|Claro!"
)
_MARKDOWN = re.compile(r"(\*\*|\*|__|_|#{1,6} |- |\d+\. )")
_IA_REVEAL = re.compile(
    r"\b(sou (uma? )?ia|intelig[eê]ncia artificial|sou um (rob[ôo]|bot|assistente virtual))\b",
    re.IGNORECASE,
)
MAX_CHARS = 300


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    correction_hint: str = ""


class CommunicationRules:
    def validate(self, content: str) -> ValidationResult:
        if len(content) > MAX_CHARS:
            return ValidationResult(
                ok=False,
                correction_hint=f"Resposta muito longa ({len(content)} chars). Máximo {MAX_CHARS}. Reescreva de forma mais curta.",
            )
        if _FORBIDDEN.search(content):
            return ValidationResult(
                ok=False,
                correction_hint="Palavra proibida detectada. Reescreva sem expressões informais negativas.",
            )
        if _MARKDOWN.search(content):
            return ValidationResult(
                ok=False,
                correction_hint="Sem markdown. WhatsApp não renderiza formatação. Reescreva em texto simples.",
            )
        if _IA_REVEAL.search(content):
            return ValidationResult(
                ok=False,
                correction_hint="Não revele que é uma IA. Reescreva sem mencionar inteligência artificial ou robô.",
            )
        return ValidationResult(ok=True)
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/domain/policies/test_communication_rules.py -v
```

Expected: 6 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/policies/communication_rules.py tests/unit/domain/policies/test_communication_rules.py
git commit -m "feat(core-v2): add domain/policies/communication_rules with ValidationResult"
```

---

## Task 3 — AgentState: Rewrite com MessagesState

**Files:**
- Modify: `src/nexoia/infrastructure/langgraph_runtime/state.py`
- Test: `tests/unit/infrastructure/langgraph/test_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/infrastructure/langgraph/test_state.py
from __future__ import annotations
from langchain_core.messages import HumanMessage
from nexoia.infrastructure.langgraph_runtime.state import AgentState


def test_agent_state_has_messages_field():
    state: AgentState = {"messages": [HumanMessage("oi")], "skill_em_andamento": None, "mensagens_pendentes": []}
    assert len(state["messages"]) == 1


def test_agent_state_skill_em_andamento_optional():
    state: AgentState = {"messages": [], "skill_em_andamento": None, "mensagens_pendentes": []}
    assert state["skill_em_andamento"] is None


def test_agent_state_mensagens_pendentes_list():
    state: AgentState = {"messages": [], "skill_em_andamento": "buscar_aluno_cademi", "mensagens_pendentes": ["msg1"]}
    assert state["mensagens_pendentes"] == ["msg1"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/infrastructure/langgraph/test_state.py -v
```

Expected: FAIL — `AgentState` não existe ainda com esse formato

- [ ] **Step 3: Rewrite `src/nexoia/infrastructure/langgraph_runtime/state.py`**

```python
from __future__ import annotations

from typing import Annotated

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Estado do loop LLM-orquestrado.

    - messages: herdado de MessagesState — lista de HumanMessage/AIMessage/ToolMessage
    - skill_em_andamento: nome do @tool em execução; None quando livre
    - mensagens_pendentes: textos que chegaram enquanto skill_em_andamento != None
    account_id, phone, conversation_id viajam no RunnableConfig, nunca aqui.
    """

    skill_em_andamento: str | None
    mensagens_pendentes: list[str]
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/infrastructure/langgraph/test_state.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/langgraph_runtime/state.py tests/unit/infrastructure/langgraph/test_state.py
git commit -m "feat(core-v2): rewrite AgentState extending MessagesState"
```

---

## Task 4 — System Prompt Dinâmico

**Files:**
- Create: `src/nexoia/infrastructure/llm/system_prompt.py`
- Test: `tests/unit/infrastructure/llm/test_system_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/infrastructure/llm/test_system_prompt.py
from __future__ import annotations
from nexoia.infrastructure.llm.system_prompt import build_system_prompt


def test_build_system_prompt_returns_string():
    prompt = build_system_prompt(long_term_facts=[])
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_build_system_prompt_includes_facts():
    facts = ["Aluno prefere resposta curta", "Produto: Mentoria de Tráfego"]
    prompt = build_system_prompt(long_term_facts=facts)
    assert "Mentoria de Tráfego" in prompt
    assert "resposta curta" in prompt


def test_build_system_prompt_no_facts_still_valid():
    prompt = build_system_prompt(long_term_facts=[])
    assert "WhatsApp" in prompt  # instruções base sempre presentes
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/infrastructure/llm/test_system_prompt.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/infrastructure/llm/system_prompt.py`**

```python
from __future__ import annotations

_BASE_PROMPT = """Você é a assistente virtual da G2 Educação no WhatsApp.

Regras inegociáveis:
- Nunca use markdown (**negrito**, _itálico_, # cabeçalho, listas com -). WhatsApp não renderiza.
- Máximo 300 caracteres por mensagem. Se precisar de mais, divida em mensagens.
- Nunca revele que é uma IA, robô ou assistente virtual.
- Nunca use expressões como "putz", "puts", "poxa", "Claro!", "entendo entendo".
- Seja direta, informal e empática. Trate o aluno pelo primeiro nome sempre que possível.
- Se o aluno mencionar Procon, advogado ou ação judicial: NÃO responda. A skill escalar_para_humano será acionada automaticamente.

Skills disponíveis: use-as quando o aluno demonstrar a necessidade. Nunca execute uma skill sem necessidade clara.
"""

_FACTS_HEADER = "\n\nInformações conhecidas sobre este aluno (use para personalizar):\n"


def build_system_prompt(long_term_facts: list[str]) -> str:
    if not long_term_facts:
        return _BASE_PROMPT
    facts_block = _FACTS_HEADER + "\n".join(f"- {f}" for f in long_term_facts)
    return _BASE_PROMPT + facts_block
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/infrastructure/llm/test_system_prompt.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/llm/system_prompt.py tests/unit/infrastructure/llm/test_system_prompt.py
git commit -m "feat(core-v2): add dynamic system_prompt builder with long_term_facts"
```

---

## Task 5 — Use Case: VerificarCasoAcesso

**Files:**
- Create: `src/nexoia/application/use_cases/__init__.py` (empty)
- Create: `src/nexoia/application/use_cases/access/__init__.py` (empty)
- Create: `src/nexoia/application/use_cases/access/verificar_caso.py`
- Test: `tests/unit/use_cases/access/test_verificar_caso.py`

Extrai lógica de `node_lookup_access_case` + `node_check_platform_scope` de `application/capabilities/access.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/use_cases/access/test_verificar_caso.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.use_cases.access.verificar_caso import VerificarCasoAcesso


def fake_case(case_id: str = "case-1", attempts: int = 0, email: str = "a@b.com"):
    case = MagicMock()
    case.id = case_id
    case.search_attempts = attempts
    case.student_email = email
    return case


@pytest.mark.asyncio
async def test_returns_found_when_case_exists():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=AsyncMock())
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="quero acesso")
    assert "CASO_ENCONTRADO" in result
    assert "case-1" in result


@pytest.mark.asyncio
async def test_escalates_and_returns_error_when_no_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    chatnexo = AsyncMock()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=chatnexo)
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="quero acesso")
    chatnexo.transfer_to_human.assert_called_once()
    assert "ESCALADO" in result


@pytest.mark.asyncio
async def test_escalates_on_shopee_keyword():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    chatnexo = AsyncMock()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=chatnexo)
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="comprei na shopee")
    chatnexo.transfer_to_human.assert_called_once()
    assert "ESCALADO" in result


@pytest.mark.asyncio
async def test_escalates_on_kyc_keyword():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    chatnexo = AsyncMock()
    uc = VerificarCasoAcesso(repo=repo, chatnexo=chatnexo)
    result = await uc.execute(account_id="t1", phone="5511999990000", last_message="problema com kyc")
    chatnexo.transfer_to_human.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/use_cases/access/test_verificar_caso.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/application/use_cases/access/verificar_caso.py`**

```python
from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

_OUT_OF_SCOPE_KEYWORDS = ("shopee", "kyc")


class VerificarCasoAcesso:
    def __init__(self, repo: Any, chatnexo: ChatNexoPort) -> None:
        self._repo = repo
        self._chatnexo = chatnexo

    async def execute(self, account_id: str, phone: str, last_message: str) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)

        if case is None:
            log.warning("no_access_case", account_id=account_id)
            await self._chatnexo.transfer_to_human(
                account_id=account_id,
                conversation_id=None,
                reason="no_access_case",
            )
            return "ESCALADO: Caso de acesso não encontrado para este número."

        if any(kw in last_message.lower() for kw in _OUT_OF_SCOPE_KEYWORDS):
            log.warning("out_of_scope", account_id=account_id, reason="shopee_or_kyc")
            await self._chatnexo.transfer_to_human(
                account_id=account_id,
                conversation_id=None,
                reason="shopee_or_kyc_out_of_scope",
            )
            return "ESCALADO: Solicitação fora do escopo (Shopee/KYC)."

        return (
            f"CASO_ENCONTRADO: case_id={case.id}, "
            f"tentativas={case.search_attempts}, "
            f"email_cadastrado={case.student_email}"
        )
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/use_cases/access/test_verificar_caso.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/ tests/unit/use_cases/
git commit -m "feat(core-v2): add use_cases/access/verificar_caso (migrated from capabilities/access.py)"
```

---

## Task 6 — Use Case: BuscarAlunoCademi

**Files:**
- Create: `src/nexoia/application/use_cases/access/buscar_aluno_cademi.py`
- Test: `tests/unit/use_cases/access/test_buscar_aluno_cademi.py`

Extrai a cascata de 3 tentativas de `node_search_cademi_cascade` em `capabilities/access.py`, sem chamar ChatNexo — use case retorna strings que o LLM interpreta.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/use_cases/access/test_buscar_aluno_cademi.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.use_cases.access.buscar_aluno_cademi import BuscarAlunoCademi


def fake_student(name: str = "João Silva", sid: str = "s1"):
    s = MagicMock()
    s.id = sid
    s.name = name
    return s


def fake_case(attempts: int = 0, email: str = "joao@test.com", cpf: str | None = None):
    c = MagicMock()
    c.id = "case-1"
    c.search_attempts = attempts
    c.student_email = email
    c.student_cpf = cpf
    return c


@pytest.mark.asyncio
async def test_finds_student_by_email_on_first_attempt():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = fake_student()
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="joao@test.com")
    assert "ENCONTRADO" in result
    assert "João Silva" in result


@pytest.mark.asyncio
async def test_falls_back_to_cpf_when_email_fails():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case(attempts=1)
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = None
    cademi.get_student_by_cpf.return_value = fake_student("Maria Souza")
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="x@x.com", cpf="12345678901")
    assert "ENCONTRADO" in result
    assert "Maria Souza" in result


@pytest.mark.asyncio
async def test_returns_ask_cpf_when_cpf_missing_and_email_failed():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case(attempts=1)
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = None
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="x@x.com", cpf=None)
    assert "CPF" in result


@pytest.mark.asyncio
async def test_escalates_after_max_attempts():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case(attempts=3)
    cademi = AsyncMock()
    cademi.get_student_by_email.return_value = None
    cademi.get_student_by_cpf.return_value = None
    cademi.get_student_by_name_phone.return_value = None
    uc = BuscarAlunoCademi(repo=repo, cademi=cademi)
    result = await uc.execute(account_id="t1", phone="5511999", email="x@x.com", cpf="00000000000")
    assert "ESCALADO" in result


@pytest.mark.asyncio
async def test_returns_not_found_when_case_missing():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    uc = BuscarAlunoCademi(repo=repo, cademi=AsyncMock())
    result = await uc.execute(account_id="t1", phone="5511999")
    assert "CASO_NAO_ENCONTRADO" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/use_cases/access/test_buscar_aluno_cademi.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/application/use_cases/access/buscar_aluno_cademi.py`**

```python
from __future__ import annotations

import re
from typing import Any

import structlog

from nexoia.domain.ports.cademi_port import CademiPort

log = structlog.get_logger(__name__)

_CPF_REGEX = re.compile(r"\d{3}\.?\d{3}\.?\d{3}\-?\d{2}")
CADEMI_MAX_ATTEMPTS = 3


def _normalize_cpf(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return digits if len(digits) == 11 else ""


class BuscarAlunoCademi:
    def __init__(self, repo: Any, cademi: CademiPort) -> None:
        self._repo = repo
        self._cademi = cademi

    async def execute(
        self,
        account_id: str,
        phone: str,
        email: str | None = None,
        cpf: str | None = None,
        student_name: str | None = None,
    ) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)
        if case is None:
            return "CASO_NAO_ENCONTRADO: Nenhum caso de acesso ativo para este número."

        attempts = case.search_attempts

        if attempts >= CADEMI_MAX_ATTEMPTS:
            return (
                "ESCALADO: Limite de 3 tentativas atingido. "
                "Transferindo para atendimento humano."
            )

        # Tentativa 1 — email
        if attempts < 1 and email:
            email_to_try = email or case.student_email
            if email_to_try:
                student = await self._cademi.get_student_by_email(email_to_try)
                if student:
                    await self._repo.update_status(
                        case_id=case.id,
                        status="REACTIVE_LINK_SENT",
                        search_attempts=1,
                    )
                    log.info("cademi_found_email", account_id=account_id)
                    return f"ENCONTRADO: {student.name} (email). student_id={student.id}"

        # Tentativa 2 — CPF
        if attempts < 2:
            if cpf is None:
                return "SOLICITAR_CPF: Pra eu te ajudar mais rápido, me passa seu CPF (só números, por favor)?"
            normalized = _normalize_cpf(cpf)
            if normalized:
                student = await self._cademi.get_student_by_cpf(normalized)
                if student:
                    await self._repo.update_status(
                        case_id=case.id,
                        status="REACTIVE_LINK_SENT",
                        search_attempts=2,
                    )
                    log.info("cademi_found_cpf", account_id=account_id)
                    return f"ENCONTRADO: {student.name} (cpf). student_id={student.id}"

        # Tentativa 3 — nome + telefone
        if attempts < CADEMI_MAX_ATTEMPTS:
            try:
                student = await self._cademi.get_student_by_name_phone(
                    name=student_name or "", phone=phone
                )
            except NotImplementedError:
                student = None
            if student:
                await self._repo.update_status(
                    case_id=case.id,
                    status="REACTIVE_LINK_SENT",
                    search_attempts=CADEMI_MAX_ATTEMPTS,
                )
                return f"ENCONTRADO: {student.name} (nome+telefone). student_id={student.id}"

        await self._repo.update_status(
            case_id=case.id,
            status="REACTIVE_ESCALATED",
            search_attempts=CADEMI_MAX_ATTEMPTS,
        )
        log.warning("cademi_exhausted", account_id=account_id)
        return "ESCALADO: Aluno não localizado após 3 tentativas. Transferindo para humano."
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/use_cases/access/test_buscar_aluno_cademi.py -v
```

Expected: 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/access/buscar_aluno_cademi.py tests/unit/use_cases/access/test_buscar_aluno_cademi.py
git commit -m "feat(core-v2): add use_cases/access/buscar_aluno_cademi with 3-attempt cascade"
```

---

## Task 7 — Use Case: EnviarLinkAcesso

**Files:**
- Create: `src/nexoia/application/use_cases/access/enviar_link_acesso.py`
- Test: `tests/unit/use_cases/access/test_enviar_link_acesso.py`

Extrai lógica de `node_send_access` de `capabilities/access.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/use_cases/access/test_enviar_link_acesso.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.use_cases.access.enviar_link_acesso import EnviarLinkAcesso


def fake_student(name: str = "João Silva", sid: str = "s1"):
    s = MagicMock()
    s.id = sid
    s.name = name
    return s


def fake_case(case_id: str = "case-1", product_name: str = "Mentoria", purchase_id: str = "p1"):
    c = MagicMock()
    c.id = case_id
    c.product_name = product_name
    c.purchase_id = purchase_id
    c.student_cademi_id = "s1"
    return c


@pytest.mark.asyncio
async def test_sends_free_text_within_24h_window():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/acesso"
    chatnexo = AsyncMock()
    uc = EnviarLinkAcesso(repo=repo, cademi=cademi, chatnexo=chatnexo)
    result = await uc.execute(
        account_id="t1",
        phone="5511999",
        student_id="s1",
        student_name="João Silva",
        within_24h_window=True,
    )
    chatnexo.send_message.assert_called_once()
    assert "LINK_ENVIADO" in result


@pytest.mark.asyncio
async def test_sends_template_outside_24h_window():
    repo = AsyncMock()
    repo.find_by_phone.return_value = fake_case()
    cademi = AsyncMock()
    cademi.get_access_link.return_value = "https://cademi.com.br/acesso"
    chatnexo = AsyncMock()
    uc = EnviarLinkAcesso(repo=repo, cademi=cademi, chatnexo=chatnexo)
    result = await uc.execute(
        account_id="t1",
        phone="5511999",
        student_id="s1",
        student_name="João Silva",
        within_24h_window=False,
    )
    chatnexo.send_template.assert_called_once()
    assert "LINK_ENVIADO" in result


@pytest.mark.asyncio
async def test_returns_error_when_no_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    uc = EnviarLinkAcesso(repo=repo, cademi=AsyncMock(), chatnexo=AsyncMock())
    result = await uc.execute(account_id="t1", phone="5511999", student_id="s1", student_name="João")
    assert "ERRO" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/use_cases/access/test_enviar_link_acesso.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/application/use_cases/access/enviar_link_acesso.py`**

```python
from __future__ import annotations

from typing import Any

import structlog

from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

ACCESS_FREE_TEXT = "Tudo certo! Aqui tá seu acesso, {name} — é só clicar que já entra direto: {link}"
ACCESS_RESEND_TEMPLATE = "access_reminder_d1"


class EnviarLinkAcesso:
    def __init__(self, repo: Any, cademi: CademiPort, chatnexo: ChatNexoPort) -> None:
        self._repo = repo
        self._cademi = cademi
        self._chatnexo = chatnexo

    async def execute(
        self,
        account_id: str,
        phone: str,
        student_id: str,
        student_name: str,
        within_24h_window: bool = True,
        conversation_id: str | None = None,
    ) -> str:
        case = await self._repo.find_by_phone(account_id=account_id, phone=phone)
        if case is None:
            return "ERRO: Caso de acesso não encontrado ao tentar enviar link."

        purchase_id = case.purchase_id or ""
        link = await self._cademi.get_access_link(
            student_id=student_id, product_id=purchase_id
        )

        first_name = (student_name or "").split()[0] if student_name else ""

        if within_24h_window:
            text = ACCESS_FREE_TEXT.format(name=first_name, link=link)
            await self._chatnexo.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                text=text,
            )
        else:
            await self._chatnexo.send_template(
                account_id=account_id,
                conversation_id=conversation_id,
                template_name=ACCESS_RESEND_TEMPLATE,
                variables={"1": student_name or "", "2": case.product_name or "", "3": link},
            )

        log.info("access_link_sent", account_id=account_id, within_24h=within_24h_window)
        return f"LINK_ENVIADO: {link}"
```

- [ ] **Step 4: Run all access use case tests together**

```bash
uv run pytest tests/unit/use_cases/access/ -v
```

Expected: 12 tests PASSED (5 + 4 + 3)

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/access/enviar_link_acesso.py tests/unit/use_cases/access/test_enviar_link_acesso.py
git commit -m "feat(core-v2): add use_cases/access/enviar_link_acesso"
```

---

## Task 8 — Access Skills Factory + escalar_para_humano

**Files:**
- Create: `src/nexoia/infrastructure/skills/__init__.py`
- Create: `src/nexoia/infrastructure/skills/access.py`
- Create: `src/nexoia/infrastructure/skills/core.py`
- Test: `tests/unit/infrastructure/skills/test_access_skills.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/infrastructure/skills/test_access_skills.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from nexoia.infrastructure.skills.access import make_access_skills


@pytest.mark.asyncio
async def test_make_access_skills_returns_three_tools():
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
async def test_verificar_caso_acesso_tool_calls_use_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    chatnexo = AsyncMock()
    tools = make_access_skills(repo, AsyncMock(), chatnexo)
    tool = next(t for t in tools if t.name == "verificar_caso_acesso")
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.access.get_config", return_value=fake_cfg):
        result = await tool.ainvoke({"last_message": "quero acesso"})
    assert "ESCALADO" in result or "CASO" in result


@pytest.mark.asyncio
async def test_buscar_aluno_cademi_tool_passes_email_to_use_case():
    repo = AsyncMock()
    repo.find_by_phone.return_value = None
    tools = make_access_skills(repo, AsyncMock(), AsyncMock())
    tool = next(t for t in tools if t.name == "buscar_aluno_cademi")
    fake_cfg = {"configurable": {"account_id": "t1", "phone": "5511999", "conversation_id": "c1"}}
    with patch("nexoia.infrastructure.skills.access.get_config", return_value=fake_cfg):
        result = await tool.ainvoke({"email": "test@example.com"})
    assert isinstance(result, str)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/infrastructure/skills/test_access_skills.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/infrastructure/skills/access.py`**

```python
from __future__ import annotations

from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config

from nexoia.application.use_cases.access.buscar_aluno_cademi import BuscarAlunoCademi
from nexoia.application.use_cases.access.enviar_link_acesso import EnviarLinkAcesso
from nexoia.application.use_cases.access.verificar_caso import VerificarCasoAcesso
from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort


def make_access_skills(
    access_repo: object,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    verificar_uc = VerificarCasoAcesso(repo=access_repo, chatnexo=chatnexo)
    buscar_uc = BuscarAlunoCademi(repo=access_repo, cademi=cademi)
    enviar_uc = EnviarLinkAcesso(repo=access_repo, cademi=cademi, chatnexo=chatnexo)

    @tool
    async def verificar_caso_acesso(last_message: str = "") -> str:
        """
        Verifica se existe caso de acesso aberto para o aluno.
        Use quando: aluno relata problema de acesso ao produto.
        Retorna: CASO_ENCONTRADO com detalhes, ou ESCALADO se não houver caso.
        Não use quando: acesso já foi verificado nesta conversa.
        """
        cfg = get_config()["configurable"]
        return await verificar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            last_message=last_message,
        )

    @tool
    async def buscar_aluno_cademi(
        email: str | None = None,
        cpf: str | None = None,
    ) -> str:
        """
        Busca aluno na Cademi por email ou CPF (cascata: email → CPF → nome+telefone).
        Use quando: precisa localizar cadastro para enviar acesso. Tente email primeiro, CPF se falhar.
        Retorna: ENCONTRADO com nome e student_id, SOLICITAR_CPF, ou ESCALADO.
        Não use quando: aluno já foi localizado (student_id disponível).
        """
        cfg = get_config()["configurable"]
        return await buscar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            email=email,
            cpf=cpf,
        )

    @tool
    async def enviar_link_acesso(
        student_id: str,
        student_name: str,
        within_24h_window: bool = True,
    ) -> str:
        """
        Envia link de acesso ao aluno após localização na Cademi.
        Use quando: aluno foi localizado (ENCONTRADO) e está sem acesso ao produto.
        Não use quando: aluno ainda não foi localizado — use buscar_aluno_cademi antes.
        Retorna: LINK_ENVIADO com a URL, ou ERRO.
        """
        cfg = get_config()["configurable"]
        return await enviar_uc.execute(
            account_id=cfg["account_id"],
            phone=cfg["phone"],
            student_id=student_id,
            student_name=student_name,
            within_24h_window=within_24h_window,
            conversation_id=cfg.get("conversation_id"),
        )

    return [verificar_caso_acesso, buscar_aluno_cademi, enviar_link_acesso]
```

- [ ] **Step 4: Create `src/nexoia/infrastructure/skills/core.py`**

```python
from __future__ import annotations

from langchain_core.tools import tool
from langgraph.config import get_config

from nexoia.domain.ports.chatnexo import ChatNexoPort


def make_core_skills(chatnexo: ChatNexoPort) -> list:
    @tool
    async def escalar_para_humano(reason: str = "solicitado_pelo_usuario") -> str:
        """
        Transfere o atendimento para um humano.
        Use quando: aluno pede falar com humano, ou situação não pode ser resolvida automaticamente.
        Retorna: confirmação de transferência.
        """
        cfg = get_config()["configurable"]
        await chatnexo.transfer_to_human(
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id"),
            reason=reason,
        )
        return f"TRANSFERIDO: Atendimento transferido para humano. Motivo: {reason}"

    return [escalar_para_humano]
```

- [ ] **Step 5: Create `src/nexoia/infrastructure/skills/__init__.py`**

```python
from __future__ import annotations

from nexoia.infrastructure.skills.access import make_access_skills
from nexoia.infrastructure.skills.core import make_core_skills

__all__ = ["make_access_skills", "make_core_skills"]
```

- [ ] **Step 6: Run tests and verify they pass**

```bash
uv run pytest tests/unit/infrastructure/skills/test_access_skills.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/infrastructure/skills/ tests/unit/infrastructure/skills/
git commit -m "feat(core-v2): add skills factory make_access_skills + escalar_para_humano"
```

---

## Task 9 — LangGraph Nodes: raciocinar + pos_execucao

**Files:**
- Create: `src/nexoia/infrastructure/langgraph_runtime/nodes.py`
- Test: `tests/unit/infrastructure/langgraph/test_nodes.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/infrastructure/langgraph/test_nodes.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage, HumanMessage

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
async def test_raciocinar_guard_blocks_llm():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(
        blocked=True, reason="legal_mention", skill_override="escalar_para_humano"
    )
    llm = AsyncMock()
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state([HumanMessage("vou acionar o Procon")]), fake_config())
    llm.ainvoke.assert_not_called()
    last_msg = result["messages"][-1]
    assert hasattr(last_msg, "tool_calls") and last_msg.tool_calls


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

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/infrastructure/langgraph/test_nodes.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/infrastructure/langgraph_runtime/nodes.py`**

```python
from __future__ import annotations

import asyncio
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
                "mensagens_pendentes": list(state.get("mensagens_pendentes", [])) + [ultima.content],
                "messages": [AIMessage("Já estou resolvendo isso, um momentinho!")],
            }

        # 1. Guards pré-LLM
        guard_result = guard_service.check(ultima.content, state)
        if guard_result.blocked:
            if guard_result.skill_override:
                override_msg = AIMessage(
                    content="",
                    tool_calls=[{
                        "name": guard_result.skill_override,
                        "args": {"reason": guard_result.reason},
                        "id": f"guard_{guard_result.reason}",
                        "type": "tool_call",
                    }],
                )
                return {
                    "messages": [override_msg],
                    "skill_em_andamento": guard_result.skill_override,
                }
            return {"messages": [AIMessage(guard_result.response or _FALLBACK_MESSAGE)]}

        # 2. Long-term facts → system prompt dinâmico
        facts = await long_term_repo.load(cfg["account_id"], cfg["phone"])
        system_prompt = build_system_prompt(long_term_facts=facts)

        # 3. LLM
        msgs = [SystemMessage(system_prompt)] + list(state["messages"])
        response = await llm.ainvoke(msgs, config)

        # 4. CommunicationRules — valida resposta (só para texto livre, não tool_call)
        if not getattr(response, "tool_calls", None):
            for _ in range(2):
                validated = _communication_rules.validate(response.content)
                if validated.ok:
                    break
                correction_msgs = msgs + [SystemMessage(validated.correction_hint)]
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

        # Registra analytics em background
        if skill_name and capability_repo:
            asyncio.create_task(
                capability_repo.record(
                    conversation_id=cfg["conversation_id"],
                    skill_name=skill_name,
                )
            )

        # Extrai long_term_facts em background
        if memory_extractor:
            asyncio.create_task(
                memory_extractor.extract_and_save(
                    account_id=cfg["account_id"],
                    phone=cfg["phone"],
                    messages=state["messages"],
                )
            )

        # Reinjeta mensagens pendentes para o próximo turno de raciocinar
        pending = state.get("mensagens_pendentes") or []
        if pending:
            joined = " | ".join(pending)
            update["messages"] = [HumanMessage(f"[mensagens_pendentes]: {joined}")]

        return update

    return pos_execucao
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/infrastructure/langgraph/test_nodes.py -v
```

Expected: 4 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/langgraph_runtime/nodes.py tests/unit/infrastructure/langgraph/test_nodes.py
git commit -m "feat(core-v2): add langgraph nodes make_raciocinar_node + make_pos_execucao_node"
```

---

## Task 10 — Graph Builder: Rewrite para 3-node Loop

**Files:**
- Modify: `src/nexoia/infrastructure/langgraph_runtime/graph_builder.py`
- Test: `tests/unit/infrastructure/langgraph/test_graph_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/infrastructure/langgraph/test_graph_builder.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from nexoia.infrastructure.langgraph_runtime.graph_builder import build_graph


def test_build_graph_returns_compiled_graph():
    graph = build_graph(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
        guard_service=MagicMock(),
        long_term_repo=AsyncMock(),
        llm=AsyncMock(),
        capability_repo=AsyncMock(),
        memory_extractor=AsyncMock(),
        checkpointer=None,
    )
    assert graph is not None


def test_build_graph_nodes_include_raciocinar_executar_pos_execucao():
    graph = build_graph(
        access_repo=AsyncMock(),
        cademi=AsyncMock(),
        chatnexo=AsyncMock(),
        guard_service=MagicMock(),
        long_term_repo=AsyncMock(),
        llm=AsyncMock(),
        capability_repo=AsyncMock(),
        memory_extractor=AsyncMock(),
        checkpointer=None,
    )
    node_names = set(graph.nodes.keys())
    assert "raciocinar" in node_names
    assert "executar" in node_names
    assert "pos_execucao" in node_names
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/infrastructure/langgraph/test_graph_builder.py -v
```

Expected: FAIL — `build_graph` não tem essa assinatura

- [ ] **Step 3: Rewrite `src/nexoia/infrastructure/langgraph_runtime/graph_builder.py`**

```python
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.infrastructure.langgraph_runtime.nodes import (
    _roteador,
    make_pos_execucao_node,
    make_raciocinar_node,
)
from nexoia.infrastructure.langgraph_runtime.state import AgentState
from nexoia.infrastructure.skills.access import make_access_skills
from nexoia.infrastructure.skills.core import make_core_skills


def _roteador(state: AgentState) -> str:
    last = state["messages"][-1]
    return "executar" if getattr(last, "tool_calls", None) else END


def build_graph(
    *,
    access_repo: Any,
    cademi: CademiPort,
    chatnexo: ChatNexoPort,
    guard_service: Any,
    long_term_repo: Any,
    llm: Any,
    capability_repo: Any,
    memory_extractor: Any,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    SKILLS = (
        make_access_skills(access_repo, cademi, chatnexo)
        + make_core_skills(chatnexo)
    )

    raciocinar_node = make_raciocinar_node(guard_service, long_term_repo, llm)
    pos_execucao_node = make_pos_execucao_node(capability_repo, memory_extractor)

    graph = StateGraph(AgentState)
    graph.add_node("raciocinar", raciocinar_node)
    graph.add_node("executar", ToolNode(SKILLS))
    graph.add_node("pos_execucao", pos_execucao_node)

    graph.set_entry_point("raciocinar")
    graph.add_conditional_edges("raciocinar", _roteador)
    graph.add_edge("executar", "pos_execucao")
    graph.add_edge("pos_execucao", "raciocinar")

    return graph.compile(checkpointer=checkpointer)
```

**Nota:** a função `_roteador` foi definida tanto em `nodes.py` quanto aqui localmente. Mover para `nodes.py` e importar é o correto — ajuste no próximo commit se o linter reclamar.

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/infrastructure/langgraph/ -v
```

Expected: todos PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/langgraph_runtime/graph_builder.py tests/unit/infrastructure/langgraph/test_graph_builder.py
git commit -m "feat(core-v2): rewrite graph_builder with 3-node loop (raciocinar→executar→pos_execucao)"
```

---

## Task 11 — MessageDispatcher

**Files:**
- Create: `src/nexoia/application/message_dispatcher.py`
- Test: `tests/unit/application/test_message_dispatcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/application/test_message_dispatcher.py
from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.message_dispatcher import MessageDispatcher


def fake_conv(within_window: bool):
    conv = MagicMock()
    if within_window:
        conv.window_expires_at = datetime.now(UTC) + timedelta(hours=1)
    else:
        conv.window_expires_at = datetime.now(UTC) - timedelta(hours=1)
    return conv


@pytest.mark.asyncio
async def test_sends_free_text_within_24h_window():
    chatnexo = AsyncMock()
    conv_repo = AsyncMock()
    conv_repo.find_by_chatnexo_id.return_value = fake_conv(within_window=True)
    dispatcher = MessageDispatcher(chatnexo=chatnexo, conversation_repo=conv_repo)
    await dispatcher.send(account_id="t1", conversation_id="c1", content="Olá!")
    chatnexo.send_message.assert_called_once()
    chatnexo.send_template.assert_not_called()


@pytest.mark.asyncio
async def test_sends_template_outside_24h_window():
    chatnexo = AsyncMock()
    conv_repo = AsyncMock()
    conv_repo.find_by_chatnexo_id.return_value = fake_conv(within_window=False)
    dispatcher = MessageDispatcher(chatnexo=chatnexo, conversation_repo=conv_repo)
    await dispatcher.send(account_id="t1", conversation_id="c1", content="Olá!")
    chatnexo.send_template.assert_called_once()
    chatnexo.send_message.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/application/test_message_dispatcher.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/application/message_dispatcher.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

_FALLBACK_TEMPLATE = "fallback_generic"


class MessageDispatcher:
    def __init__(self, chatnexo: ChatNexoPort, conversation_repo: Any) -> None:
        self._chatnexo = chatnexo
        self._conv_repo = conversation_repo

    async def send(self, account_id: str, conversation_id: str, content: str) -> None:
        conv = await self._conv_repo.find_by_chatnexo_id(account_id, conversation_id)
        within_window = bool(
            conv and conv.window_expires_at and conv.window_expires_at > datetime.now(UTC)
        )

        if within_window:
            await self._chatnexo.send_message(
                account_id=account_id,
                conversation_id=conversation_id,
                text=content,
            )
            log.info("message_sent_free_text", account_id=account_id)
        else:
            await self._chatnexo.send_template(
                account_id=account_id,
                conversation_id=conversation_id,
                template_name=_FALLBACK_TEMPLATE,
                variables={},
            )
            log.info("message_sent_template_fallback", account_id=account_id)
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/application/test_message_dispatcher.py -v
```

Expected: 2 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/message_dispatcher.py tests/unit/application/test_message_dispatcher.py
git commit -m "feat(core-v2): add MessageDispatcher (24h window rule: free text vs Meta template)"
```

---

## Task 12 — PurchaseHandler

**Files:**
- Create: `src/nexoia/application/purchase_handler.py`
- Test: `tests/unit/application/test_purchase_handler.py`

Migra lógica de `application/capabilities/welcome.py`. No novo design: sem Cademi na compra, sem grafo. Apenas: Contact → Conversation → AccessCase → welcome_template → schedule D+1.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/application/test_purchase_handler.py
from __future__ import annotations
import pytest
from datetime import datetime, UTC
from uuid import UUID
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.purchase_handler import PurchaseHandler
from nexoia.domain.events.purchase_received import PurchaseReceived


def fake_event():
    return PurchaseReceived(
        purchase_id="p-1",
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        contact_name="João Silva",
        contact_email="joao@test.com",
        contact_phone="5511999990000",
        product="Mentoria de Tráfego",
        amount_brl=49700,
        occurred_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_creates_contact_and_access_case():
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = None
    chatnexo.create_conversation.return_value = "conv-1"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
    )
    await handler.execute(fake_event())
    contact_repo.find_or_create.assert_called_once()
    access_case_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_sends_welcome_template():
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "existing-conv"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
    )
    await handler.execute(fake_event())
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "welcome_purchase"


@pytest.mark.asyncio
async def test_schedules_d1_followup_job():
    contact_repo = AsyncMock()
    contact_repo.find_or_create.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-1"
    access_case_repo = AsyncMock()
    scheduler = AsyncMock()
    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        scheduler=scheduler,
    )
    await handler.execute(fake_event())
    scheduler.create_job.assert_called_once()
    call_kwargs = scheduler.create_job.call_args.kwargs
    assert "FOLLOWUP_D1" in str(call_kwargs.get("job_type", ""))
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/application/test_purchase_handler.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/application/purchase_handler.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog

from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.domain.entities.scheduled_job import JobType
from nexoia.domain.events.purchase_received import PurchaseReceived
from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)


class PurchaseHandler:
    def __init__(
        self,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        access_case_repo: Any,
        scheduler: Any,
    ) -> None:
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._access_case_repo = access_case_repo
        self._scheduler = scheduler

    async def execute(self, event: PurchaseReceived) -> None:
        account_id = str(event.account_id)

        contact = await self._contact_repo.find_or_create(
            account_id=account_id,
            phone=event.contact_phone,
            name=event.contact_name,
            email=event.contact_email,
        )

        conversation_id = await self._chatnexo.get_open_conversation(
            account_id=account_id, contact_phone=contact.phone
        )
        if conversation_id is None:
            conversation_id = await self._chatnexo.create_conversation(
                account_id=account_id, contact_phone=contact.phone
            )

        case = AccessCase(
            id=str(uuid4()),
            account_id=account_id,
            contact_id=contact.id,
            conversation_id=conversation_id,
            purchase_id=event.purchase_id,
            product_name=event.product,
            student_email=event.contact_email,
            status=AccessCaseStatus.PROATIVO_ENVIADO,
        )
        await self._access_case_repo.save(case)

        await self._chatnexo.send_template(
            account_id=account_id,
            conversation_id=conversation_id,
            template_name="welcome_purchase",
            variables={"nome": event.contact_name, "produto": event.product},
        )

        await self._scheduler.create_job(
            job_type=JobType.FOLLOWUP_D1,
            account_id=account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(hours=24),
        )

        log.info(
            "purchase_handled",
            account_id=account_id,
            purchase_id=event.purchase_id,
            conversation_id=conversation_id,
        )
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/application/test_purchase_handler.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/purchase_handler.py tests/unit/application/test_purchase_handler.py
git commit -m "feat(core-v2): add PurchaseHandler (Contact→Conversation→AccessCase→template→D+1)"
```

---

## Task 13 — LifecycleHandler

**Files:**
- Create: `src/nexoia/application/lifecycle_handler.py`
- Test: `tests/unit/application/test_lifecycle_handler.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/application/test_lifecycle_handler.py
from __future__ import annotations
import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from nexoia.application.lifecycle_handler import LifecycleHandler


def fake_conv(status: str = "ACTIVE", window_ok: bool = True):
    conv = MagicMock()
    conv.status = status
    conv.window_expires_at = (
        datetime.now(UTC) + timedelta(hours=1)
        if window_ok
        else datetime.now(UTC) - timedelta(hours=1)
    )
    return conv


def fake_contact(name: str = "João"):
    c = MagicMock()
    c.name = name
    return c


@pytest.mark.asyncio
async def test_send_ping_sends_message_when_conv_active():
    conv_repo = AsyncMock()
    conv_repo.find_active.return_value = fake_conv()
    contact_repo = AsyncMock()
    contact_repo.find_by_phone.return_value = fake_contact()
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    handler = LifecycleHandler(
        conv_repo=conv_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        scheduler=scheduler,
    )
    await handler.send_ping(account_id="t1", phone="5511999", conversation_id="c1")
    chatnexo.send_message.assert_called_once()
    scheduler.create_job.assert_called_once()


@pytest.mark.asyncio
async def test_send_ping_skips_when_conv_handed_off():
    conv_repo = AsyncMock()
    conv_repo.find_active.return_value = fake_conv(status="HANDED_OFF")
    chatnexo = AsyncMock()
    scheduler = AsyncMock()
    handler = LifecycleHandler(
        conv_repo=conv_repo,
        contact_repo=AsyncMock(),
        chatnexo=chatnexo,
        scheduler=scheduler,
    )
    await handler.send_ping(account_id="t1", phone="5511999", conversation_id="c1")
    chatnexo.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_send_close_closes_conversation():
    conv_repo = AsyncMock()
    conv_repo.find_active.return_value = fake_conv(status="IDLE_PINGED")
    contact_repo = AsyncMock()
    contact_repo.find_by_phone.return_value = fake_contact("Maria")
    chatnexo = AsyncMock()
    handler = LifecycleHandler(
        conv_repo=conv_repo,
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        scheduler=AsyncMock(),
    )
    await handler.send_close(account_id="t1", phone="5511999", conversation_id="c1")
    chatnexo.send_message.assert_called_once()
    conv_repo.update_status.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/application/test_lifecycle_handler.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `src/nexoia/application/lifecycle_handler.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from nexoia.domain.ports.chatnexo import ChatNexoPort

log = structlog.get_logger(__name__)

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
_SKIP_STATUSES = {"HANDED_OFF", "CLOSED_BY_TIMEOUT"}


class LifecycleHandler:
    def __init__(
        self,
        conv_repo: Any,
        contact_repo: Any,
        chatnexo: ChatNexoPort,
        scheduler: Any,
    ) -> None:
        self._conv_repo = conv_repo
        self._contact_repo = contact_repo
        self._chatnexo = chatnexo
        self._scheduler = scheduler

    async def send_ping(self, account_id: str, phone: str, conversation_id: str) -> None:
        conv = await self._conv_repo.find_active(account_id, conversation_id)
        if conv is None or str(conv.status) in _SKIP_STATUSES:
            return
        if conv.window_expires_at <= datetime.now(UTC):
            await self._conv_repo.update_status(conv.id, "CLOSED_BY_TIMEOUT")
            return

        contact = await self._contact_repo.find_by_phone(account_id, phone)
        nome = (contact.name or "").split()[0] if contact else ""
        idx = hash(f"{conversation_id}:ping") % len(_PING_VARIATIONS)
        text = _PING_VARIATIONS[idx].format(nome=nome)

        await self._chatnexo.send_message(
            account_id=account_id, conversation_id=conversation_id, text=text
        )
        await self._conv_repo.update_status(conv.id, "IDLE_PINGED")
        await self._scheduler.create_job(
            job_type="IDLE_CLOSE",
            account_id=account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(minutes=20),
        )
        log.info("idle_ping_sent", account_id=account_id, conversation_id=conversation_id)

    async def send_close(self, account_id: str, phone: str, conversation_id: str) -> None:
        conv = await self._conv_repo.find_active(account_id, conversation_id)
        if conv is None or str(conv.status) != "IDLE_PINGED":
            return

        contact = await self._contact_repo.find_by_phone(account_id, phone)
        nome = (contact.name or "").split()[0] if contact else ""
        idx = hash(f"{conversation_id}:close") % len(_CLOSE_VARIATIONS)
        text = _CLOSE_VARIATIONS[idx].format(nome=nome)

        await self._chatnexo.send_message(
            account_id=account_id, conversation_id=conversation_id, text=text
        )
        await self._conv_repo.update_status(conv.id, "CLOSED_BY_TIMEOUT")
        log.info("idle_close_sent", account_id=account_id, conversation_id=conversation_id)

    async def schedule_idle_ping(
        self, account_id: str, phone: str, conversation_id: str
    ) -> None:
        await self._scheduler.create_job(
            job_type="IDLE_PING",
            account_id=account_id,
            conversation_id=conversation_id,
            run_at=datetime.now(UTC) + timedelta(minutes=30),
        )
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
uv run pytest tests/unit/application/test_lifecycle_handler.py -v
```

Expected: 3 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/lifecycle_handler.py tests/unit/application/test_lifecycle_handler.py
git commit -m "feat(core-v2): add LifecycleHandler (idle ping 30min + close 20min)"
```

---

## Task 14 — Wire up handle_message

**Files:**
- Modify: `src/nexoia/interface/worker/handlers/message.py`
- Test: `tests/e2e/test_message_flow.py`

Este é o handler central. O stub atual (`handle_message`) vira a integração completa: carrega dependências, invoca o grafo, envia a resposta via `MessageDispatcher`.

- [ ] **Step 1: Write the failing e2e test**

```python
# tests/e2e/test_message_flow.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage


@pytest.mark.asyncio
async def test_handle_message_invokes_agent_and_sends_reply():
    fake_agent = AsyncMock()
    fake_agent.ainvoke.return_value = {
        "messages": [AIMessage("Olá! Como posso ajudar?")]
    }
    fake_dispatcher = AsyncMock()

    with (
        patch("nexoia.interface.worker.handlers.message._get_agent", return_value=fake_agent),
        patch("nexoia.interface.worker.handlers.message._get_dispatcher", return_value=fake_dispatcher),
        patch("nexoia.interface.worker.handlers.message._get_lifecycle", return_value=AsyncMock()),
        patch("nexoia.interface.worker.handlers.message._get_scheduler", return_value=AsyncMock()),
    ):
        from nexoia.interface.worker.handlers.message import handle_message
        await handle_message({
            "account_id": "t1",
            "phone": "5511999990000",
            "conversation_id": "c1",
            "chatnexo_message_id": "msg-1",
            "text": "oi",
        })

    fake_agent.ainvoke.assert_called_once()
    fake_dispatcher.send.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/e2e/test_message_flow.py -v
```

Expected: FAIL (handle_message é stub)

- [ ] **Step 3: Rewrite `src/nexoia/interface/worker/handlers/message.py`**

```python
from __future__ import annotations

from functools import lru_cache
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage

from nexoia.application.lifecycle_handler import LifecycleHandler
from nexoia.application.message_dispatcher import MessageDispatcher
from nexoia.infrastructure.observability.logger import get_logger

log = get_logger(__name__)


def _get_agent() -> Any:
    """Monta e retorna o grafo compilado. Singleton por processo."""
    from nexoia.infrastructure.langgraph_runtime.graph_builder import build_graph
    from nexoia.config.settings import get_settings
    # TODO: injetar deps reais de infraestrutura (session factory, redis, etc.)
    # Placeholder — substituir por DI container quando disponível
    raise NotImplementedError("_get_agent: configure DI container em main.py e injete via closure")


def _get_dispatcher() -> MessageDispatcher:
    raise NotImplementedError("_get_dispatcher: configure em main.py")


def _get_lifecycle() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle: configure em main.py")


def _get_scheduler() -> Any:
    raise NotImplementedError("_get_scheduler: configure em main.py")


async def handle_message(payload: dict) -> None:
    account_id: str = payload["account_id"]
    phone: str = payload["phone"]
    conversation_id: str = payload["conversation_id"]
    text: str = payload["text"]

    log.info(
        "message_job_started",
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
    )

    agent = _get_agent()
    dispatcher = _get_dispatcher()
    lifecycle = _get_lifecycle()
    scheduler = _get_scheduler()

    # Cancela jobs de idle pendentes (nova mensagem = aluno voltou)
    await scheduler.cancel_pending_idle_jobs(account_id=account_id, phone=phone)

    config = {
        "configurable": {
            "thread_id": f"{account_id}:{phone}",
            "account_id": account_id,
            "phone": phone,
            "conversation_id": conversation_id,
        }
    }

    result = await agent.ainvoke(
        {"messages": [HumanMessage(text)]},
        config=config,
    )

    # Extrai última AIMessage sem tool_call — é a resposta ao aluno
    last_ai = next(
        (m for m in reversed(result.get("messages", []))
         if isinstance(m, AIMessage) and not getattr(m, "tool_calls", None)),
        None,
    )

    if last_ai and last_ai.content:
        await dispatcher.send(
            account_id=account_id,
            conversation_id=conversation_id,
            content=last_ai.content,
        )

    # Agenda idle check
    await lifecycle.schedule_idle_ping(
        account_id=account_id,
        phone=phone,
        conversation_id=conversation_id,
    )

    log.info("message_job_done", account_id=account_id, conversation_id=conversation_id)
```

**Nota:** `_get_agent`, `_get_dispatcher`, `_get_lifecycle`, `_get_scheduler` são stubs que lançam `NotImplementedError`. Serão substituídos por injeção de dependências em `main.py` (Task 15b). O teste e2e usa `patch` para substituí-los.

- [ ] **Step 4: Run test and verify it passes**

```bash
uv run pytest tests/e2e/test_message_flow.py -v
```

Expected: PASSED

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/interface/worker/handlers/message.py tests/e2e/test_message_flow.py
git commit -m "feat(core-v2): wire up handle_message (invoke agent + dispatch reply + idle schedule)"
```

---

## Task 15 — Wire up handle_purchase + handle_scheduled

**Files:**
- Modify: `src/nexoia/interface/worker/handlers/purchase.py`
- Modify: `src/nexoia/interface/worker/handlers/scheduled.py`
- Test: `tests/unit/worker/test_purchase_handler_wire.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/worker/test_purchase_handler_wire.py
from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_handle_purchase_calls_purchase_handler():
    mock_handler = AsyncMock()
    with patch(
        "nexoia.interface.worker.handlers.purchase._get_purchase_handler",
        return_value=mock_handler,
    ):
        from nexoia.interface.worker.handlers.purchase import handle_purchase
        await handle_purchase({
            "purchase_id": "p-1",
            "account_id": "00000000-0000-0000-0000-000000000001",
            "contact_name": "João",
            "contact_email": "joao@test.com",
            "contact_phone": "5511999990000",
            "product": "Mentoria",
            "amount_brl": 49700,
            "occurred_at": "2026-04-24T00:00:00+00:00",
        })
    mock_handler.execute.assert_called_once()


@pytest.mark.asyncio
async def test_handle_scheduled_idle_ping_calls_lifecycle():
    mock_lifecycle = AsyncMock()
    with patch(
        "nexoia.interface.worker.handlers.scheduled._get_lifecycle_handler",
        return_value=mock_lifecycle,
    ):
        from nexoia.interface.worker.handlers import scheduled
        import importlib; importlib.reload(scheduled)
        from nexoia.interface.worker.handlers.scheduled import handle_scheduled
        await handle_scheduled({
            "job_type": "IDLE_PING",
            "account_id": "t1",
            "phone": "5511999990000",
            "conversation_id": "c1",
        })
    mock_lifecycle.send_ping.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/worker/test_purchase_handler_wire.py -v
```

Expected: FAIL

- [ ] **Step 3: Update `src/nexoia/interface/worker/handlers/purchase.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from nexoia.application.purchase_handler import PurchaseHandler
from nexoia.domain.events.purchase_received import PurchaseReceived
from nexoia.infrastructure.observability.logger import get_logger

log = get_logger(__name__)


def _get_purchase_handler() -> PurchaseHandler:
    raise NotImplementedError("_get_purchase_handler: configure DI em main.py")


async def handle_purchase(payload: dict) -> None:
    handler = _get_purchase_handler()
    event = PurchaseReceived(
        purchase_id=payload["purchase_id"],
        account_id=UUID(payload["account_id"]),
        contact_name=payload["contact_name"],
        contact_email=payload["contact_email"],
        contact_phone=payload["contact_phone"],
        product=payload["product"],
        amount_brl=int(payload["amount_brl"]),
        occurred_at=datetime.fromisoformat(payload["occurred_at"]),
    )
    await handler.execute(event)
    log.info("purchase_job_done", purchase_id=payload["purchase_id"])
```

- [ ] **Step 4: Update `src/nexoia/interface/worker/handlers/scheduled.py`**

```python
from __future__ import annotations

from typing import Any

import structlog

from nexoia.application.lifecycle_handler import LifecycleHandler
from nexoia.infrastructure.observability.logger import get_logger

log = get_logger(__name__)


def _get_lifecycle_handler() -> LifecycleHandler:
    raise NotImplementedError("_get_lifecycle_handler: configure DI em main.py")


async def handle_scheduled(payload: dict) -> None:
    job_type: str = payload["job_type"]
    account_id: str = payload["account_id"]
    phone: str = payload.get("phone", "")
    conversation_id: str = payload["conversation_id"]

    lifecycle = _get_lifecycle_handler()

    if job_type == "IDLE_PING":
        await lifecycle.send_ping(account_id=account_id, phone=phone, conversation_id=conversation_id)
    elif job_type == "IDLE_CLOSE":
        await lifecycle.send_close(account_id=account_id, phone=phone, conversation_id=conversation_id)
    else:
        log.warning("unknown_job_type", job_type=job_type)
```

- [ ] **Step 5: Run all tests**

```bash
uv run pytest tests/ -v --ignore=tests/integration --ignore=tests/e2e -x
```

Expected: todos os testes unit PASSED

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/interface/worker/handlers/ tests/unit/worker/
git commit -m "feat(core-v2): wire up handle_purchase + handle_scheduled with lifecycle handler"
```

---

## Task 16 — Delete Old Code + Run Full Suite

**Files deletar:**
- `src/nexoia/application/intent_router.py`
- `src/nexoia/application/context_builder.py`
- `src/nexoia/application/sentiment.py`
- `src/nexoia/application/prompts/` (dir)
- `src/nexoia/application/capabilities/base.py`
- `src/nexoia/application/capabilities/__init__.py`
- `src/nexoia/application/capabilities/access.py`
- `src/nexoia/application/capabilities/welcome.py`
- `src/nexoia/application/guards/` (dir)
- `src/nexoia/application/response_composer.py`
- `src/nexoia/application/communication_rules.py`
- `src/nexoia/application/conversation/lifecycle.py`

- [ ] **Step 1: Verificar que nenhum arquivo novo importa os arquivos antigos**

```bash
grep -r "from nexoia.application.capabilities" src/ --include="*.py"
grep -r "from nexoia.application.guards" src/ --include="*.py"
grep -r "from nexoia.application.intent_router" src/ --include="*.py"
grep -r "from nexoia.application.response_composer" src/ --include="*.py"
grep -r "from nexoia.application.communication_rules" src/ --include="*.py"
grep -r "from nexoia.application.context_builder" src/ --include="*.py"
grep -r "from nexoia.application.sentiment" src/ --include="*.py"
```

Expected: nenhuma linha de saída (ou apenas os próprios arquivos antigos)

- [ ] **Step 2: Deletar arquivos antigos**

```bash
rm src/nexoia/application/intent_router.py
rm src/nexoia/application/context_builder.py
rm src/nexoia/application/sentiment.py
rm -rf src/nexoia/application/prompts/
rm src/nexoia/application/capabilities/base.py
rm src/nexoia/application/capabilities/__init__.py
rm src/nexoia/application/capabilities/access.py
rm src/nexoia/application/capabilities/welcome.py
rm -rf src/nexoia/application/guards/
rm src/nexoia/application/response_composer.py
rm src/nexoia/application/communication_rules.py
rm src/nexoia/application/conversation/lifecycle.py
```

- [ ] **Step 3: Rodar full suite e verificar que passa**

```bash
uv run pytest tests/unit/ -v -x
```

Expected: PASSED. Se quebrar, corrigir imports antes de continuar.

- [ ] **Step 4: Verificar que linter passa**

```bash
uv run ruff check src/
```

Expected: sem erros

- [ ] **Step 5: Commit final**

```bash
git add -A
git commit -m "chore(core-v2): delete old pipeline code (intent_router, capabilities, guards, response_composer)"
```

---

## Self-Review

### Spec coverage check

| Requisito Core v2 | Task que implementa |
|---|---|
| CORE-RF-06: Grafo 3 nós raciocinar→executar→pos_execucao | Task 10 |
| CORE-RF-07: GuardService pré-LLM com skill_override | Tasks 1 + 9 |
| CORE-RF-08: CommunicationRules ≤300 chars, retry 2x, fallback | Tasks 2 + 9 |
| CORE-RF-09: MessageDispatcher free text vs template Meta | Task 11 |
| CORE-RF-10: use_cases/ sem @tool, sem LangGraph | Tasks 5-7 |
| CORE-RF-11: @tool com zero regra de negócio | Task 8 |
| CORE-RF-12: long_term_facts no system prompt | Tasks 4 + 9 |
| CORE-RF-13: pos_execucao registra capability_executions | Task 9 |
| CORE-RF-14: cancela IDLE jobs na nova mensagem | Task 14 |
| CORE-RF-15: lifecycle_handler sem agent.ainvoke | Task 13 |
| CORE-RF-16: purchase_handler sem grafo, sem LLM | Task 12 |

**Lacunas identificadas:**
- `memory_extractor.py` — mencionado em `pos_execucao` mas não tem task dedicada. A chamada `memory_extractor.extract_and_save()` no Task 9 já existe; o stub `AsyncMock()` funciona para os testes. Implementação real é backlog.
- DI real em `main.py` — os `_get_*` são stubs com `NotImplementedError`. Wire-up real de todas as dependências de infraestrutura (session factory, Redis, LLM client) é o próximo plano após este.
- CORE-RF-05: `AsyncPostgresSaver` checkpointer — `build_graph` recebe `checkpointer=None` por ora. Configuração real do checkpointer Postgres é parte do DI em `main.py`.

Essas 3 lacunas são intencionais: dependem de infra real e são endereçadas quando o DI container for montado.
