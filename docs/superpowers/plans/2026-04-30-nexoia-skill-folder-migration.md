# NexoIA — Skill Folder Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all skills from flat files (`access.py`, `refund.py`, `knowledge.py`, `core.py`) into individual skill folders, each self-contained with `skill.py`, `use_case.py`, `preconditions.py`, `instructions.md`, `__init__.py`, and `tests/`. Replace manual factory wiring in `graph.py` with a dynamic `skill_loader.py` that discovers and loads all skills automatically.

**Architecture:** Each skill folder is a fully self-contained unit. The `skill.py` file holds a single `BaseTool` subclass. The `use_case.py` holds the domain logic (moved out of `shared/application/use_cases/`). The `__init__.py` exposes a `make_skill(adapters: Adapters) -> BaseTool` factory function. The skill loader auto-discovers folders, imports each `__init__.py`, and calls `make_skill`. The `graph.py` replaces all manual skill factory calls with one `load_skills(adapters)` call.

**Tech Stack:** Python 3.11, LangChain `BaseTool`, Pydantic v2 `BaseModel`, `importlib`, `pathlib.Path`, pytest, pytest-asyncio

**Prerequisite:** Plan 1 (monorepo restructure) must be complete. Skills already use `BaseTool` (BaseTool refactor spec was applied before this plan).

---

## File Map

### Create
```
apps/api/src/agent/skills/_utils.py
apps/api/src/agent/skill_loader.py
apps/api/src/agent/skills/buscar_aluno_cademi/__init__.py
apps/api/src/agent/skills/buscar_aluno_cademi/skill.py
apps/api/src/agent/skills/buscar_aluno_cademi/use_case.py
apps/api/src/agent/skills/buscar_aluno_cademi/preconditions.py
apps/api/src/agent/skills/buscar_aluno_cademi/instructions.md
apps/api/src/agent/skills/buscar_aluno_cademi/tests/__init__.py
apps/api/src/agent/skills/buscar_aluno_cademi/tests/test_skill.py
apps/api/src/agent/skills/verificar_caso_acesso/__init__.py
apps/api/src/agent/skills/verificar_caso_acesso/skill.py
apps/api/src/agent/skills/verificar_caso_acesso/use_case.py
apps/api/src/agent/skills/verificar_caso_acesso/preconditions.py
apps/api/src/agent/skills/verificar_caso_acesso/instructions.md
apps/api/src/agent/skills/verificar_caso_acesso/tests/__init__.py
apps/api/src/agent/skills/verificar_caso_acesso/tests/test_skill.py
apps/api/src/agent/skills/enviar_link_acesso/__init__.py
apps/api/src/agent/skills/enviar_link_acesso/skill.py
apps/api/src/agent/skills/enviar_link_acesso/use_case.py
apps/api/src/agent/skills/enviar_link_acesso/preconditions.py
apps/api/src/agent/skills/enviar_link_acesso/instructions.md
apps/api/src/agent/skills/enviar_link_acesso/tests/__init__.py
apps/api/src/agent/skills/enviar_link_acesso/tests/test_skill.py
apps/api/src/agent/skills/verificar_elegibilidade_reembolso/__init__.py
apps/api/src/agent/skills/verificar_elegibilidade_reembolso/skill.py
apps/api/src/agent/skills/verificar_elegibilidade_reembolso/use_case.py
apps/api/src/agent/skills/verificar_elegibilidade_reembolso/preconditions.py
apps/api/src/agent/skills/verificar_elegibilidade_reembolso/instructions.md
apps/api/src/agent/skills/verificar_elegibilidade_reembolso/tests/__init__.py
apps/api/src/agent/skills/verificar_elegibilidade_reembolso/tests/test_skill.py
apps/api/src/agent/skills/oferecer_retencao/__init__.py
apps/api/src/agent/skills/oferecer_retencao/skill.py
apps/api/src/agent/skills/oferecer_retencao/use_case.py
apps/api/src/agent/skills/oferecer_retencao/preconditions.py
apps/api/src/agent/skills/oferecer_retencao/instructions.md
apps/api/src/agent/skills/oferecer_retencao/tests/__init__.py
apps/api/src/agent/skills/oferecer_retencao/tests/test_skill.py
apps/api/src/agent/skills/processar_reembolso/__init__.py
apps/api/src/agent/skills/processar_reembolso/skill.py
apps/api/src/agent/skills/processar_reembolso/use_case.py
apps/api/src/agent/skills/processar_reembolso/preconditions.py
apps/api/src/agent/skills/processar_reembolso/instructions.md
apps/api/src/agent/skills/processar_reembolso/tests/__init__.py
apps/api/src/agent/skills/processar_reembolso/tests/test_skill.py
apps/api/src/agent/skills/buscar_conhecimento/__init__.py
apps/api/src/agent/skills/buscar_conhecimento/skill.py
apps/api/src/agent/skills/buscar_conhecimento/use_case.py
apps/api/src/agent/skills/buscar_conhecimento/keyword_extractor.py
apps/api/src/agent/skills/buscar_conhecimento/synonym_expander.py
apps/api/src/agent/skills/buscar_conhecimento/stopwords_ptbr.py
apps/api/src/agent/skills/buscar_conhecimento/preconditions.py
apps/api/src/agent/skills/buscar_conhecimento/instructions.md
apps/api/src/agent/skills/buscar_conhecimento/tests/__init__.py
apps/api/src/agent/skills/buscar_conhecimento/tests/test_skill.py
apps/api/src/agent/skills/buscar_conhecimento_com_contexto/__init__.py
apps/api/src/agent/skills/buscar_conhecimento_com_contexto/skill.py
apps/api/src/agent/skills/buscar_conhecimento_com_contexto/use_case.py
apps/api/src/agent/skills/buscar_conhecimento_com_contexto/preconditions.py
apps/api/src/agent/skills/buscar_conhecimento_com_contexto/instructions.md
apps/api/src/agent/skills/buscar_conhecimento_com_contexto/tests/__init__.py
apps/api/src/agent/skills/buscar_conhecimento_com_contexto/tests/test_skill.py
apps/api/src/agent/skills/escalar_para_humano/__init__.py
apps/api/src/agent/skills/escalar_para_humano/skill.py
apps/api/src/agent/skills/escalar_para_humano/preconditions.py
apps/api/src/agent/skills/escalar_para_humano/instructions.md
apps/api/src/agent/skills/escalar_para_humano/tests/__init__.py
apps/api/src/agent/skills/escalar_para_humano/tests/test_skill.py
```

### Modify
```
apps/api/src/agent/graph.py      — replace manual factory calls with load_skills(adapters)
```

### Delete
```
apps/api/src/agent/skills/access.py
apps/api/src/agent/skills/refund.py
apps/api/src/agent/skills/knowledge.py
apps/api/src/agent/skills/core.py
apps/api/src/shared/application/use_cases/access/buscar_aluno_cademi.py
apps/api/src/shared/application/use_cases/access/verificar_caso.py
apps/api/src/shared/application/use_cases/access/enviar_link_acesso.py
apps/api/src/shared/application/use_cases/refund/verificar_elegibilidade.py
apps/api/src/shared/application/use_cases/refund/iniciar_retencao.py
apps/api/src/shared/application/use_cases/refund/processar_reembolso.py
apps/api/src/shared/application/use_cases/knowledge/buscar_conhecimento.py
apps/api/src/shared/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py
apps/api/src/shared/application/use_cases/knowledge/keyword_extractor.py
apps/api/src/shared/application/use_cases/knowledge/synonym_expander.py
apps/api/src/shared/application/use_cases/knowledge/stopwords_ptbr.py
```

---

## Task 1 — Create `skills/_utils.py` and `agent/skill_loader.py`

**Files:**
- Create: `apps/api/src/agent/skills/_utils.py`
- Create: `apps/api/src/agent/skill_loader.py`

- [ ] **Step 1: Create `skills/_utils.py`**

```python
# apps/api/src/agent/skills/_utils.py
"""Shared helpers used by every skill folder."""
from __future__ import annotations

from pathlib import Path


def _load_instructions(skill_file: str) -> str:
    """Load the instructions.md sitting next to the calling skill.py.

    Usage inside any skill.py:
        from agent.skills._utils import _load_instructions
        description = _load_instructions(__file__)
    """
    instructions_path = Path(skill_file).parent / "instructions.md"
    return instructions_path.read_text(encoding="utf-8").strip()
```

- [ ] **Step 2: Create `agent/skill_loader.py`**

```python
# apps/api/src/agent/skill_loader.py
"""Dynamic skill loader — discovers all skill folders and wires adapters."""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import BaseTool

from shared.domain.ports.cademi_port import CademiPort
from shared.domain.ports.chatnexo import ChatNexoPort
from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.knowledge import KnowledgePort
from shared.domain.ports.legal_history_port import LegalHistoryPort
from shared.domain.ports.refund_mutex import RefundMutexPort


@dataclass
class Adapters:
    access_repo: object
    cademi: CademiPort
    chatnexo: ChatNexoPort
    refund_repo: object
    hubla: HublaPort
    legal_history: LegalHistoryPort
    refund_mutex: RefundMutexPort
    knowledge_repo: KnowledgePort
    usage_log_repo: object


def load_skills(adapters: Adapters) -> list[BaseTool]:
    """Auto-discover every skill folder under agent/skills/ and instantiate it.

    Folders whose names start with '_' are ignored (e.g. _utils.py is not a
    folder, but the pattern guards future helper packages as well).
    """
    skills_dir = Path(__file__).parent / "skills"
    skills: list[BaseTool] = []
    for folder in sorted(skills_dir.iterdir()):
        if folder.is_dir() and not folder.name.startswith("_"):
            module = importlib.import_module(f"agent.skills.{folder.name}")
            skills.append(module.make_skill(adapters))
    return skills
```

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/agent/skills/_utils.py apps/api/src/agent/skill_loader.py
git commit -m "feat(skills): add _load_instructions helper and dynamic skill_loader"
```

---

## Task 2 — Skill: `buscar_aluno_cademi`

**Source use case:** `apps/api/src/shared/application/use_cases/access/buscar_aluno_cademi.py`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/buscar_aluno_cademi/tests
touch apps/api/src/agent/skills/buscar_aluno_cademi/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# buscar_aluno_cademi

Busca os dados de um aluno na plataforma Cademi a partir do número de telefone.

Use esta skill quando precisar identificar o aluno antes de realizar qualquer
operação de acesso (verificar caso, enviar link). A skill retorna o nome, e-mail
e status de matrícula do aluno.

**Parâmetros:**
- `phone`: número de telefone do aluno no formato internacional (ex: 5511999998888)

**Retorno:** dados do aluno (nome, email, cursos ativos) ou mensagem de erro
se o aluno não for encontrado.
```

- [ ] **Step 3: Write `use_case.py`** (moved from `shared/application/use_cases/access/buscar_aluno_cademi.py`)

```python
# apps/api/src/agent/skills/buscar_aluno_cademi/use_case.py
from __future__ import annotations

from shared.domain.ports.cademi_port import CademiPort


class BuscarAlunoCademi:
    def __init__(self, cademi: CademiPort) -> None:
        self._cademi = cademi

    async def execute(self, phone: str, account_id: str) -> dict:
        aluno = await self._cademi.buscar_aluno(phone=phone, account_id=account_id)
        if aluno is None:
            return {"encontrado": False, "mensagem": "Aluno não encontrado na base Cademi."}
        return {
            "encontrado": True,
            "nome": aluno.nome,
            "email": aluno.email,
            "cursos": aluno.cursos_ativos,
        }
```

- [ ] **Step 4: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/buscar_aluno_cademi/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 5: Write `skill.py`**

```python
# apps/api/src/agent/skills/buscar_aluno_cademi/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.buscar_aluno_cademi.preconditions import PRECONDITIONS
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    phone: str


class BuscarAlunoCademiTool(BaseTool):
    name: str = "buscar_aluno_cademi"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: BuscarAlunoCademi

    def __init__(self, use_case: BuscarAlunoCademi) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, phone: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, phone: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(phone=phone, account_id=account_id)
        if not result["encontrado"]:
            return result["mensagem"]
        return (
            f"Aluno encontrado: {result['nome']} ({result['email']}). "
            f"Cursos ativos: {', '.join(result['cursos']) or 'nenhum'}."
        )
```

- [ ] **Step 6: Write `__init__.py`**

```python
# apps/api/src/agent/skills/buscar_aluno_cademi/__init__.py
from agent.skill_loader import Adapters
from agent.skills.buscar_aluno_cademi.skill import BuscarAlunoCademiTool
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


def make_skill(adapters: Adapters) -> BuscarAlunoCademiTool:
    use_case = BuscarAlunoCademi(cademi=adapters.cademi)
    return BuscarAlunoCademiTool(use_case=use_case)
```

- [ ] **Step 7: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/buscar_aluno_cademi/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.buscar_aluno_cademi.skill import BuscarAlunoCademiTool
from agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi


def _make_tool() -> BuscarAlunoCademiTool:
    use_case = MagicMock(spec=BuscarAlunoCademi)
    return BuscarAlunoCademiTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "buscar_aluno_cademi"
    assert tool.description  # loaded from instructions.md


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "phone" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_returns_aluno_data():
    use_case = AsyncMock(spec=BuscarAlunoCademi)
    use_case.execute.return_value = {
        "encontrado": True,
        "nome": "João Silva",
        "email": "joao@email.com",
        "cursos": ["Curso A"],
    }
    tool = BuscarAlunoCademiTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1", "phone": "5511999998888"}}
    with patch("agent.skills.buscar_aluno_cademi.skill.get_config", return_value=fake_config):
        result = await tool._arun(phone="5511999998888")
    assert "João Silva" in result
    assert "joao@email.com" in result


@pytest.mark.asyncio
async def test_arun_returns_not_found_message():
    use_case = AsyncMock(spec=BuscarAlunoCademi)
    use_case.execute.return_value = {
        "encontrado": False,
        "mensagem": "Aluno não encontrado na base Cademi.",
    }
    tool = BuscarAlunoCademiTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1", "phone": "5511000000000"}}
    with patch("agent.skills.buscar_aluno_cademi.skill.get_config", return_value=fake_config):
        result = await tool._arun(phone="5511000000000")
    assert "não encontrado" in result
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/agent/skills/buscar_aluno_cademi/
git commit -m "feat(skills): add buscar_aluno_cademi skill folder"
```

---

## Task 3 — Skill: `verificar_caso_acesso`

**Source use case:** `apps/api/src/shared/application/use_cases/access/verificar_caso.py`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/verificar_caso_acesso/tests
touch apps/api/src/agent/skills/verificar_caso_acesso/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# verificar_caso_acesso

Verifica se o aluno já possui um caso de acesso aberto no sistema e qual é
o seu status atual.

Use esta skill após `buscar_aluno_cademi` para determinar se existe um caso
em andamento antes de criar um novo ou enviar um link de acesso. Evita
duplicação de atendimentos.

**Parâmetros:**
- `email`: e-mail do aluno obtido via `buscar_aluno_cademi`

**Retorno:** status do caso atual (aberto, fechado, inexistente) e ID do caso
se existir.
```

- [ ] **Step 3: Write `use_case.py`** (moved from `shared/application/use_cases/access/verificar_caso.py`)

```python
# apps/api/src/agent/skills/verificar_caso_acesso/use_case.py
from __future__ import annotations


class VerificarCasoAcesso:
    def __init__(self, access_repo: object) -> None:
        self._repo = access_repo

    async def execute(self, email: str, account_id: str) -> dict:
        caso = await self._repo.buscar_por_email(email=email, account_id=account_id)
        if caso is None:
            return {"tem_caso": False, "status": "inexistente", "caso_id": None}
        return {"tem_caso": True, "status": caso.status, "caso_id": str(caso.id)}
```

- [ ] **Step 4: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/verificar_caso_acesso/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 5: Write `skill.py`**

```python
# apps/api/src/agent/skills/verificar_caso_acesso/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.verificar_caso_acesso.preconditions import PRECONDITIONS
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str


class VerificarCasoAcessoTool(BaseTool):
    name: str = "verificar_caso_acesso"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: VerificarCasoAcesso

    def __init__(self, use_case: VerificarCasoAcesso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(email=email, account_id=account_id)
        if not result["tem_caso"]:
            return "Nenhum caso de acesso encontrado para este aluno."
        return f"Caso encontrado. Status: {result['status']}. ID: {result['caso_id']}."
```

- [ ] **Step 6: Write `__init__.py`**

```python
# apps/api/src/agent/skills/verificar_caso_acesso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.verificar_caso_acesso.skill import VerificarCasoAcessoTool
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


def make_skill(adapters: Adapters) -> VerificarCasoAcessoTool:
    use_case = VerificarCasoAcesso(access_repo=adapters.access_repo)
    return VerificarCasoAcessoTool(use_case=use_case)
```

- [ ] **Step 7: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/verificar_caso_acesso/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.verificar_caso_acesso.skill import VerificarCasoAcessoTool
from agent.skills.verificar_caso_acesso.use_case import VerificarCasoAcesso


def _make_tool() -> VerificarCasoAcessoTool:
    use_case = MagicMock(spec=VerificarCasoAcesso)
    return VerificarCasoAcessoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "verificar_caso_acesso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_returns_caso_encontrado():
    use_case = AsyncMock(spec=VerificarCasoAcesso)
    use_case.execute.return_value = {
        "tem_caso": True,
        "status": "aberto",
        "caso_id": "caso-123",
    }
    tool = VerificarCasoAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.verificar_caso_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com")
    assert "aberto" in result
    assert "caso-123" in result


@pytest.mark.asyncio
async def test_arun_returns_nenhum_caso():
    use_case = AsyncMock(spec=VerificarCasoAcesso)
    use_case.execute.return_value = {
        "tem_caso": False,
        "status": "inexistente",
        "caso_id": None,
    }
    tool = VerificarCasoAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.verificar_caso_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="inexistente@email.com")
    assert "Nenhum caso" in result
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/agent/skills/verificar_caso_acesso/
git commit -m "feat(skills): add verificar_caso_acesso skill folder"
```

---

## Task 4 — Skill: `enviar_link_acesso`

**Source use case:** `apps/api/src/shared/application/use_cases/access/enviar_link_acesso.py`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/enviar_link_acesso/tests
touch apps/api/src/agent/skills/enviar_link_acesso/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# enviar_link_acesso

Envia um link de acesso ao curso para o aluno via ChatNexo (WhatsApp).

Use esta skill como etapa final do fluxo de acesso, após confirmar que o aluno
existe (`buscar_aluno_cademi`) e verificar o status do caso (`verificar_caso_acesso`).
Só envie o link se o caso estiver aberto ou inexistente — nunca reenvie se o
status já for "resolvido".

**Parâmetros:**
- `email`: e-mail do aluno
- `phone`: telefone do aluno para entrega da mensagem

**Retorno:** confirmação de envio ou descrição do erro.
```

- [ ] **Step 3: Write `use_case.py`** (moved from `shared/application/use_cases/access/enviar_link_acesso.py`)

```python
# apps/api/src/agent/skills/enviar_link_acesso/use_case.py
from __future__ import annotations

from shared.domain.ports.cademi_port import CademiPort
from shared.domain.ports.chatnexo import ChatNexoPort


class EnviarLinkAcesso:
    def __init__(self, cademi: CademiPort, chatnexo: ChatNexoPort) -> None:
        self._cademi = cademi
        self._chatnexo = chatnexo

    async def execute(self, email: str, phone: str, account_id: str) -> dict:
        link = await self._cademi.gerar_link_acesso(email=email, account_id=account_id)
        if link is None:
            return {"enviado": False, "mensagem": "Não foi possível gerar o link de acesso."}
        await self._chatnexo.enviar_mensagem(
            phone=phone,
            account_id=account_id,
            mensagem=f"Aqui está seu link de acesso: {link}",
        )
        return {"enviado": True, "link": link}
```

- [ ] **Step 4: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/enviar_link_acesso/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 5: Write `skill.py`**

```python
# apps/api/src/agent/skills/enviar_link_acesso/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.enviar_link_acesso.preconditions import PRECONDITIONS
from agent.skills.enviar_link_acesso.use_case import EnviarLinkAcesso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    phone: str


class EnviarLinkAcessoTool(BaseTool):
    name: str = "enviar_link_acesso"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: EnviarLinkAcesso

    def __init__(self, use_case: EnviarLinkAcesso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str, phone: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str, phone: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(email=email, phone=phone, account_id=account_id)
        if not result["enviado"]:
            return result["mensagem"]
        return f"Link de acesso enviado com sucesso para {phone}."
```

- [ ] **Step 6: Write `__init__.py`**

```python
# apps/api/src/agent/skills/enviar_link_acesso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.enviar_link_acesso.skill import EnviarLinkAcessoTool
from agent.skills.enviar_link_acesso.use_case import EnviarLinkAcesso


def make_skill(adapters: Adapters) -> EnviarLinkAcessoTool:
    use_case = EnviarLinkAcesso(cademi=adapters.cademi, chatnexo=adapters.chatnexo)
    return EnviarLinkAcessoTool(use_case=use_case)
```

- [ ] **Step 7: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/enviar_link_acesso/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.enviar_link_acesso.skill import EnviarLinkAcessoTool
from agent.skills.enviar_link_acesso.use_case import EnviarLinkAcesso


def _make_tool() -> EnviarLinkAcessoTool:
    use_case = MagicMock(spec=EnviarLinkAcesso)
    return EnviarLinkAcessoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "enviar_link_acesso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "phone" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_link_enviado():
    use_case = AsyncMock(spec=EnviarLinkAcesso)
    use_case.execute.return_value = {"enviado": True, "link": "https://cademi.com/acesso/abc"}
    tool = EnviarLinkAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.enviar_link_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", phone="5511999998888")
    assert "enviado com sucesso" in result


@pytest.mark.asyncio
async def test_arun_falha_gerar_link():
    use_case = AsyncMock(spec=EnviarLinkAcesso)
    use_case.execute.return_value = {
        "enviado": False,
        "mensagem": "Não foi possível gerar o link de acesso.",
    }
    tool = EnviarLinkAcessoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.enviar_link_acesso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", phone="5511999998888")
    assert "Não foi possível" in result
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/agent/skills/enviar_link_acesso/
git commit -m "feat(skills): add enviar_link_acesso skill folder"
```

---

## Task 5 — Skill: `verificar_elegibilidade_reembolso`

**Source use case:** `apps/api/src/shared/application/use_cases/refund/verificar_elegibilidade.py`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/verificar_elegibilidade_reembolso/tests
touch apps/api/src/agent/skills/verificar_elegibilidade_reembolso/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# verificar_elegibilidade_reembolso

Verifica se o aluno é elegível para solicitar reembolso com base nas políticas
de reembolso vigentes e no histórico de compras.

Use esta skill como primeiro passo do fluxo de reembolso, antes de oferecer
retenção ou processar o reembolso. A elegibilidade considera: prazo desde a
compra, tipo de produto, e se já houve reembolso anterior.

**Parâmetros:**
- `email`: e-mail do aluno
- `produto_id`: identificador do produto para o qual o reembolso é solicitado

**Retorno:** elegível (booleano), motivo em caso de inelegibilidade, e prazo
restante para reembolso se elegível.
```

- [ ] **Step 3: Write `use_case.py`** (moved from `shared/application/use_cases/refund/verificar_elegibilidade.py`)

```python
# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/use_case.py
from __future__ import annotations

from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.legal_history_port import LegalHistoryPort


class VerificarElegibilidadeReembolso:
    def __init__(self, hubla: HublaPort, legal_history: LegalHistoryPort) -> None:
        self._hubla = hubla
        self._legal_history = legal_history

    async def execute(self, email: str, produto_id: str, account_id: str) -> dict:
        compra = await self._hubla.buscar_compra(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if compra is None:
            return {"elegivel": False, "motivo": "Compra não encontrada na plataforma Hubla."}

        historico = await self._legal_history.buscar(email=email, account_id=account_id)
        if historico and historico.teve_reembolso:
            return {"elegivel": False, "motivo": "Aluno já utilizou o direito de reembolso anteriormente."}

        if not compra.dentro_prazo_reembolso:
            return {
                "elegivel": False,
                "motivo": f"Prazo de reembolso expirado. Compra realizada em {compra.data_compra}.",
            }

        return {
            "elegivel": True,
            "motivo": None,
            "dias_restantes": compra.dias_restantes_reembolso,
            "valor": compra.valor,
        }
```

- [ ] **Step 4: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 5: Write `skill.py`**

```python
# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.verificar_elegibilidade_reembolso.preconditions import PRECONDITIONS
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class VerificarElegibilidadeReembolsoTool(BaseTool):
    name: str = "verificar_elegibilidade_reembolso"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: VerificarElegibilidadeReembolso

    def __init__(self, use_case: VerificarElegibilidadeReembolso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str, produto_id: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str, produto_id: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if not result["elegivel"]:
            return f"Reembolso não elegível: {result['motivo']}"
        return (
            f"Aluno elegível para reembolso. "
            f"Valor: R$ {result['valor']:.2f}. "
            f"Prazo restante: {result['dias_restantes']} dias."
        )
```

- [ ] **Step 6: Write `__init__.py`**

```python
# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.verificar_elegibilidade_reembolso.skill import VerificarElegibilidadeReembolsoTool
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


def make_skill(adapters: Adapters) -> VerificarElegibilidadeReembolsoTool:
    use_case = VerificarElegibilidadeReembolso(
        hubla=adapters.hubla, legal_history=adapters.legal_history
    )
    return VerificarElegibilidadeReembolsoTool(use_case=use_case)
```

- [ ] **Step 7: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/verificar_elegibilidade_reembolso/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.verificar_elegibilidade_reembolso.skill import VerificarElegibilidadeReembolsoTool
from agent.skills.verificar_elegibilidade_reembolso.use_case import VerificarElegibilidadeReembolso


def _make_tool() -> VerificarElegibilidadeReembolsoTool:
    use_case = MagicMock(spec=VerificarElegibilidadeReembolso)
    return VerificarElegibilidadeReembolsoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "verificar_elegibilidade_reembolso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "produto_id" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_elegivel():
    use_case = AsyncMock(spec=VerificarElegibilidadeReembolso)
    use_case.execute.return_value = {
        "elegivel": True,
        "motivo": None,
        "dias_restantes": 5,
        "valor": 297.00,
    }
    tool = VerificarElegibilidadeReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch(
        "agent.skills.verificar_elegibilidade_reembolso.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "elegível" in result
    assert "297" in result


@pytest.mark.asyncio
async def test_arun_inelegivel():
    use_case = AsyncMock(spec=VerificarElegibilidadeReembolso)
    use_case.execute.return_value = {
        "elegivel": False,
        "motivo": "Prazo de reembolso expirado.",
    }
    tool = VerificarElegibilidadeReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch(
        "agent.skills.verificar_elegibilidade_reembolso.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "não elegível" in result
    assert "Prazo" in result
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/agent/skills/verificar_elegibilidade_reembolso/
git commit -m "feat(skills): add verificar_elegibilidade_reembolso skill folder"
```

---

## Task 6 — Skill: `oferecer_retencao`

**Source use case:** `apps/api/src/shared/application/use_cases/refund/iniciar_retencao.py`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/oferecer_retencao/tests
touch apps/api/src/agent/skills/oferecer_retencao/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# oferecer_retencao

Oferece uma alternativa ao reembolso para tentar reter o aluno — por exemplo,
uma pausa na assinatura, acesso a suporte prioritário, ou desconto em renovação.

Use esta skill após confirmar elegibilidade (`verificar_elegibilidade_reembolso`)
mas ANTES de processar o reembolso. A oferta de retenção deve ser apresentada
como uma opção, nunca como imposição. Se o aluno recusar, prossiga com
`processar_reembolso`.

**Parâmetros:**
- `email`: e-mail do aluno
- `produto_id`: produto para o qual o reembolso está sendo solicitado

**Retorno:** oferta de retenção gerada ou indicação de que não há oferta
disponível para este perfil.
```

- [ ] **Step 3: Write `use_case.py`** (moved from `shared/application/use_cases/refund/iniciar_retencao.py`)

```python
# apps/api/src/agent/skills/oferecer_retencao/use_case.py
from __future__ import annotations

from shared.domain.ports.hubla_port import HublaPort


class OfereceRetencao:
    def __init__(self, hubla: HublaPort, refund_repo: object) -> None:
        self._hubla = hubla
        self._refund_repo = refund_repo

    async def execute(self, email: str, produto_id: str, account_id: str) -> dict:
        oferta = await self._hubla.buscar_oferta_retencao(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if oferta is None:
            return {"tem_oferta": False}

        await self._refund_repo.registrar_tentativa_retencao(
            email=email, produto_id=produto_id, account_id=account_id, oferta_id=oferta.id
        )
        return {
            "tem_oferta": True,
            "descricao": oferta.descricao,
            "valor_desconto": oferta.valor_desconto,
            "tipo": oferta.tipo,
        }
```

- [ ] **Step 4: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/oferecer_retencao/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 5: Write `skill.py`**

```python
# apps/api/src/agent/skills/oferecer_retencao/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.oferecer_retencao.preconditions import PRECONDITIONS
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class OfereceRetencaoTool(BaseTool):
    name: str = "oferecer_retencao"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: OfereceRetencao

    def __init__(self, use_case: OfereceRetencao) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str, produto_id: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str, produto_id: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if not result["tem_oferta"]:
            return "Nenhuma oferta de retenção disponível para este perfil."
        return (
            f"Oferta de retenção disponível: {result['descricao']}. "
            f"Tipo: {result['tipo']}. "
            f"Desconto: R$ {result['valor_desconto']:.2f}."
        )
```

- [ ] **Step 6: Write `__init__.py`**

```python
# apps/api/src/agent/skills/oferecer_retencao/__init__.py
from agent.skill_loader import Adapters
from agent.skills.oferecer_retencao.skill import OfereceRetencaoTool
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


def make_skill(adapters: Adapters) -> OfereceRetencaoTool:
    use_case = OfereceRetencao(hubla=adapters.hubla, refund_repo=adapters.refund_repo)
    return OfereceRetencaoTool(use_case=use_case)
```

- [ ] **Step 7: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/oferecer_retencao/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.oferecer_retencao.skill import OfereceRetencaoTool
from agent.skills.oferecer_retencao.use_case import OfereceRetencao


def _make_tool() -> OfereceRetencaoTool:
    use_case = MagicMock(spec=OfereceRetencao)
    return OfereceRetencaoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "oferecer_retencao"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "produto_id" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_tem_oferta():
    use_case = AsyncMock(spec=OfereceRetencao)
    use_case.execute.return_value = {
        "tem_oferta": True,
        "descricao": "Pausa de 30 dias na assinatura",
        "tipo": "pausa",
        "valor_desconto": 0.0,
    }
    tool = OfereceRetencaoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.oferecer_retencao.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "Pausa de 30 dias" in result
    assert "pausa" in result


@pytest.mark.asyncio
async def test_arun_sem_oferta():
    use_case = AsyncMock(spec=OfereceRetencao)
    use_case.execute.return_value = {"tem_oferta": False}
    tool = OfereceRetencaoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.oferecer_retencao.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "Nenhuma oferta" in result
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/agent/skills/oferecer_retencao/
git commit -m "feat(skills): add oferecer_retencao skill folder"
```

---

## Task 7 — Skill: `processar_reembolso`

**Source use case:** `apps/api/src/shared/application/use_cases/refund/processar_reembolso.py`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/processar_reembolso/tests
touch apps/api/src/agent/skills/processar_reembolso/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# processar_reembolso

Processa a solicitação de reembolso do aluno junto à plataforma Hubla.

Use esta skill somente após confirmar elegibilidade (`verificar_elegibilidade_reembolso`)
e após o aluno ter recusado ou não haver oferta de retenção (`oferecer_retencao`).
O mutex garante que o mesmo aluno não processe dois reembolsos simultaneamente.

**Parâmetros:**
- `email`: e-mail do aluno
- `produto_id`: produto a ser reembolsado

**Retorno:** confirmação do reembolso com número do protocolo ou descrição
do motivo de falha.
```

- [ ] **Step 3: Write `use_case.py`** (moved from `shared/application/use_cases/refund/processar_reembolso.py`)

```python
# apps/api/src/agent/skills/processar_reembolso/use_case.py
from __future__ import annotations

from shared.domain.ports.hubla_port import HublaPort
from shared.domain.ports.refund_mutex import RefundMutexPort


class ProcessarReembolso:
    def __init__(self, hubla: HublaPort, refund_mutex: RefundMutexPort) -> None:
        self._hubla = hubla
        self._mutex = refund_mutex

    async def execute(self, email: str, produto_id: str, account_id: str) -> dict:
        lock_key = f"{account_id}:{email}:{produto_id}"
        async with self._mutex.lock(lock_key):
            resultado = await self._hubla.processar_reembolso(
                email=email, produto_id=produto_id, account_id=account_id
            )
            if not resultado.sucesso:
                return {"processado": False, "motivo": resultado.motivo_falha}
            return {
                "processado": True,
                "protocolo": resultado.protocolo,
                "valor": resultado.valor,
                "prazo_estorno": resultado.prazo_estorno,
            }
```

- [ ] **Step 4: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/processar_reembolso/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 5: Write `skill.py`**

```python
# apps/api/src/agent/skills/processar_reembolso/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.processar_reembolso.preconditions import PRECONDITIONS
from agent.skills.processar_reembolso.use_case import ProcessarReembolso


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str
    produto_id: str


class ProcessarReembolsoTool(BaseTool):
    name: str = "processar_reembolso"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: ProcessarReembolso

    def __init__(self, use_case: ProcessarReembolso) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, email: str, produto_id: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, email: str, produto_id: str) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            email=email, produto_id=produto_id, account_id=account_id
        )
        if not result["processado"]:
            return f"Reembolso não processado: {result['motivo']}"
        return (
            f"Reembolso processado com sucesso. "
            f"Protocolo: {result['protocolo']}. "
            f"Valor: R$ {result['valor']:.2f}. "
            f"Prazo de estorno: {result['prazo_estorno']}."
        )
```

- [ ] **Step 6: Write `__init__.py`**

```python
# apps/api/src/agent/skills/processar_reembolso/__init__.py
from agent.skill_loader import Adapters
from agent.skills.processar_reembolso.skill import ProcessarReembolsoTool
from agent.skills.processar_reembolso.use_case import ProcessarReembolso


def make_skill(adapters: Adapters) -> ProcessarReembolsoTool:
    use_case = ProcessarReembolso(hubla=adapters.hubla, refund_mutex=adapters.refund_mutex)
    return ProcessarReembolsoTool(use_case=use_case)
```

- [ ] **Step 7: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/processar_reembolso/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.processar_reembolso.skill import ProcessarReembolsoTool
from agent.skills.processar_reembolso.use_case import ProcessarReembolso


def _make_tool() -> ProcessarReembolsoTool:
    use_case = MagicMock(spec=ProcessarReembolso)
    return ProcessarReembolsoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "processar_reembolso"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "email" in schema["properties"]
    assert "produto_id" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_reembolso_processado():
    use_case = AsyncMock(spec=ProcessarReembolso)
    use_case.execute.return_value = {
        "processado": True,
        "protocolo": "RMB-20260430-001",
        "valor": 297.00,
        "prazo_estorno": "5 a 10 dias úteis",
    }
    tool = ProcessarReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.processar_reembolso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "RMB-20260430-001" in result
    assert "297" in result


@pytest.mark.asyncio
async def test_arun_reembolso_falhou():
    use_case = AsyncMock(spec=ProcessarReembolso)
    use_case.execute.return_value = {
        "processado": False,
        "motivo": "Erro na plataforma Hubla.",
    }
    tool = ProcessarReembolsoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "acc1"}}
    with patch("agent.skills.processar_reembolso.skill.get_config", return_value=fake_config):
        result = await tool._arun(email="joao@email.com", produto_id="prod-1")
    assert "não processado" in result
    assert "Hubla" in result
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/agent/skills/processar_reembolso/
git commit -m "feat(skills): add processar_reembolso skill folder"
```

---

## Task 8 — Skill: `buscar_conhecimento`

**Source use cases:** `apps/api/src/shared/application/use_cases/knowledge/{buscar_conhecimento.py, keyword_extractor.py, synonym_expander.py, stopwords_ptbr.py}`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/buscar_conhecimento/tests
touch apps/api/src/agent/skills/buscar_conhecimento/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# buscar_conhecimento

Busca informações na base de conhecimento do produto usando estratégia em
cascata: query exata → expansão de sinônimos → extração de keywords.

Use esta skill para responder dúvidas sobre o produto, conteúdo dos cursos,
políticas e FAQs antes de escalar para um humano. Retorna os trechos mais
relevantes encontrados ou indica que nenhuma informação foi localizada.

**Parâmetros:**
- `query`: pergunta ou tópico a ser pesquisado na base de conhecimento

**Retorno:** trechos relevantes da base de conhecimento ou mensagem indicando
que a informação não foi encontrada.
```

- [ ] **Step 3: Move `stopwords_ptbr.py`** (from `shared/application/use_cases/knowledge/`)

```python
# apps/api/src/agent/skills/buscar_conhecimento/stopwords_ptbr.py
"""Stopwords em português brasileiro para uso no keyword extractor."""
from __future__ import annotations

STOPWORDS: frozenset[str] = frozenset({
    "a", "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo",
    "as", "até", "com", "como", "da", "das", "de", "dela", "delas", "dele",
    "deles", "depois", "do", "dos", "e", "ela", "elas", "ele", "eles", "em",
    "entre", "era", "essa", "essas", "esse", "esses", "esta", "estas", "este",
    "estes", "eu", "foi", "for", "foram", "há", "isso", "isto", "já", "lhe",
    "lhes", "mais", "mas", "me", "mesmo", "meu", "meus", "minha", "minhas",
    "muito", "na", "nas", "nem", "no", "nos", "nós", "num", "numa", "o", "os",
    "ou", "para", "pela", "pelas", "pelo", "pelos", "por", "qual", "quando",
    "que", "quem", "se", "seu", "seus", "só", "sua", "suas", "também", "te",
    "tem", "têm", "teu", "teus", "tua", "tuas", "um", "uma", "umas", "uns",
    "você", "vocês",
})
```

- [ ] **Step 4: Move `keyword_extractor.py`** (from `shared/application/use_cases/knowledge/`)

```python
# apps/api/src/agent/skills/buscar_conhecimento/keyword_extractor.py
"""Extrai keywords relevantes de uma query em português brasileiro."""
from __future__ import annotations

import re

from agent.skills.buscar_conhecimento.stopwords_ptbr import STOPWORDS

_MIN_LENGTH = 3


def extract_keywords(query: str) -> list[str]:
    """Remove stopwords e retorna tokens únicos com >= 3 caracteres."""
    tokens = re.findall(r"\b[a-záéíóúàâêôãõüç]+\b", query.lower())
    seen: set[str] = set()
    keywords: list[str] = []
    for tok in tokens:
        if tok not in STOPWORDS and len(tok) >= _MIN_LENGTH and tok not in seen:
            seen.add(tok)
            keywords.append(tok)
    return keywords
```

- [ ] **Step 5: Move `synonym_expander.py`** (from `shared/application/use_cases/knowledge/`)

```python
# apps/api/src/agent/skills/buscar_conhecimento/synonym_expander.py
"""Expande keywords com sinônimos para melhorar o recall da busca RAG."""
from __future__ import annotations

_SYNONYMS: dict[str, list[str]] = {
    "acesso": ["login", "entrar", "acessar", "senha"],
    "reembolso": ["devolução", "estorno", "cancelamento", "devolver"],
    "curso": ["treinamento", "aula", "módulo", "conteúdo"],
    "certificado": ["diploma", "certificação"],
    "pagamento": ["cobrança", "fatura", "boleto", "pix", "cartão"],
    "suporte": ["ajuda", "atendimento", "assistência"],
}


def expand_synonyms(keywords: list[str]) -> list[str]:
    """Retorna os keywords originais mais seus sinônimos conhecidos, sem duplicatas."""
    expanded: list[str] = list(keywords)
    seen = set(keywords)
    for kw in keywords:
        for syn in _SYNONYMS.get(kw, []):
            if syn not in seen:
                seen.add(syn)
                expanded.append(syn)
    return expanded
```

- [ ] **Step 6: Write `use_case.py`** (moved from `shared/application/use_cases/knowledge/buscar_conhecimento.py`)

```python
# apps/api/src/agent/skills/buscar_conhecimento/use_case.py
from __future__ import annotations

from shared.domain.ports.knowledge import KnowledgePort

from agent.skills.buscar_conhecimento.keyword_extractor import extract_keywords
from agent.skills.buscar_conhecimento.synonym_expander import expand_synonyms


class BuscarConhecimento:
    def __init__(self, knowledge_repo: KnowledgePort, usage_log_repo: object) -> None:
        self._knowledge = knowledge_repo
        self._usage_log = usage_log_repo

    async def execute(self, query: str, account_id: int) -> dict:
        # Tentativa 1: query exata
        chunks = await self._knowledge.search(query=query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="exact", found=True)
            return {"encontrado": True, "chunks": [c.text for c in chunks], "strategy": "exact"}

        # Tentativa 2: expansão de sinônimos
        keywords = extract_keywords(query)
        expanded = expand_synonyms(keywords)
        expanded_query = " ".join(expanded)
        chunks = await self._knowledge.search(query=expanded_query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="synonyms", found=True)
            return {"encontrado": True, "chunks": [c.text for c in chunks], "strategy": "synonyms"}

        # Tentativa 3: keywords isoladas
        if keywords:
            keyword_query = " ".join(keywords)
            chunks = await self._knowledge.search(query=keyword_query, account_id=account_id)
            if chunks:
                await self._log(account_id, query, strategy="keywords", found=True)
                return {"encontrado": True, "chunks": [c.text for c in chunks], "strategy": "keywords"}

        await self._log(account_id, query, strategy="all_failed", found=False)
        return {"encontrado": False, "chunks": [], "strategy": "all_failed"}

    async def _log(self, account_id: int, query: str, strategy: str, found: bool) -> None:
        if self._usage_log:
            try:
                await self._usage_log.registrar(
                    account_id=account_id, query=query, strategy=strategy, found=found
                )
            except Exception:
                pass
```

- [ ] **Step 7: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 8: Write `skill.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.buscar_conhecimento.preconditions import PRECONDITIONS
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class BuscarConhecimentoTool(BaseTool):
    name: str = "buscar_conhecimento"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: BuscarConhecimento

    def __init__(self, use_case: BuscarConhecimento) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, query: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, query: str) -> str:
        cfg = get_config()["configurable"]
        account_id: int = int(cfg["account_id"])

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(query=query, account_id=account_id)
        if not result["encontrado"]:
            return "Não encontrei informações sobre este tópico na base de conhecimento."
        return "\n\n".join(result["chunks"])
```

- [ ] **Step 9: Write `__init__.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento/__init__.py
from agent.skill_loader import Adapters
from agent.skills.buscar_conhecimento.skill import BuscarConhecimentoTool
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


def make_skill(adapters: Adapters) -> BuscarConhecimentoTool:
    use_case = BuscarConhecimento(
        knowledge_repo=adapters.knowledge_repo,
        usage_log_repo=adapters.usage_log_repo,
    )
    return BuscarConhecimentoTool(use_case=use_case)
```

- [ ] **Step 10: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.buscar_conhecimento.skill import BuscarConhecimentoTool
from agent.skills.buscar_conhecimento.use_case import BuscarConhecimento


def _make_tool() -> BuscarConhecimentoTool:
    use_case = MagicMock(spec=BuscarConhecimento)
    return BuscarConhecimentoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "buscar_conhecimento"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "query" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_encontrado():
    use_case = AsyncMock(spec=BuscarConhecimento)
    use_case.execute.return_value = {
        "encontrado": True,
        "chunks": ["O acesso ao curso é feito pelo link enviado por e-mail."],
        "strategy": "exact",
    }
    tool = BuscarConhecimentoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch("agent.skills.buscar_conhecimento.skill.get_config", return_value=fake_config):
        result = await tool._arun(query="como acessar o curso")
    assert "acesso ao curso" in result


@pytest.mark.asyncio
async def test_arun_nao_encontrado():
    use_case = AsyncMock(spec=BuscarConhecimento)
    use_case.execute.return_value = {
        "encontrado": False,
        "chunks": [],
        "strategy": "all_failed",
    }
    tool = BuscarConhecimentoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch("agent.skills.buscar_conhecimento.skill.get_config", return_value=fake_config):
        result = await tool._arun(query="topico desconhecido xyz")
    assert "Não encontrei" in result
```

- [ ] **Step 11: Commit**

```bash
git add apps/api/src/agent/skills/buscar_conhecimento/
git commit -m "feat(skills): add buscar_conhecimento skill folder with keyword extractor and synonym expander"
```

---

## Task 9 — Skill: `buscar_conhecimento_com_contexto`

**Source use case:** `apps/api/src/shared/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py`

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/buscar_conhecimento_com_contexto/tests
touch apps/api/src/agent/skills/buscar_conhecimento_com_contexto/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# buscar_conhecimento_com_contexto

Busca informações na base de conhecimento enriquecendo a query com dados
contextuais do aluno (nome, cursos ativos) para melhorar a relevância.

Use esta skill como fallback após `buscar_conhecimento` não encontrar
resultados com a query original. O contexto adicional permite que a busca
vetorial encontre trechos mais específicos para o perfil do aluno.

**Parâmetros:**
- `query`: pergunta ou tópico original
- `contexto_aluno`: dados do aluno para enriquecer a busca (nome, cursos, etc.)

**Retorno:** trechos relevantes da base de conhecimento ou mensagem indicando
que nenhuma informação foi localizada mesmo com contexto adicional. Se ainda
não encontrar, a skill sinaliza para escalar para humano.
```

- [ ] **Step 3: Write `use_case.py`** (moved from `shared/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py`)

```python
# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/use_case.py
from __future__ import annotations

from shared.domain.ports.knowledge import KnowledgePort

from agent.skills.buscar_conhecimento.keyword_extractor import extract_keywords
from agent.skills.buscar_conhecimento.synonym_expander import expand_synonyms


class BuscarConhecimentoComContexto:
    def __init__(self, knowledge_repo: KnowledgePort, usage_log_repo: object) -> None:
        self._knowledge = knowledge_repo
        self._usage_log = usage_log_repo

    async def execute(self, query: str, contexto_aluno: str, account_id: int) -> dict:
        enriched_query = f"{query} {contexto_aluno}".strip()

        # Tentativa 1: query enriquecida com contexto
        chunks = await self._knowledge.search(query=enriched_query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="context_enriched", found=True)
            return {
                "encontrado": True,
                "chunks": [c.text for c in chunks],
                "strategy": "context_enriched",
                "escalar": False,
            }

        # Tentativa 2: keywords do contexto enriquecido
        keywords = extract_keywords(enriched_query)
        expanded = expand_synonyms(keywords)
        expanded_query = " ".join(expanded)
        chunks = await self._knowledge.search(query=expanded_query, account_id=account_id)
        if chunks:
            await self._log(account_id, query, strategy="context_keywords", found=True)
            return {
                "encontrado": True,
                "chunks": [c.text for c in chunks],
                "strategy": "context_keywords",
                "escalar": False,
            }

        await self._log(account_id, query, strategy="context_failed", found=False)
        return {
            "encontrado": False,
            "chunks": [],
            "strategy": "context_failed",
            "escalar": True,
        }

    async def _log(self, account_id: int, query: str, strategy: str, found: bool) -> None:
        if self._usage_log:
            try:
                await self._usage_log.registrar(
                    account_id=account_id, query=query, strategy=strategy, found=found
                )
            except Exception:
                pass
```

- [ ] **Step 4: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 5: Write `skill.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.buscar_conhecimento_com_contexto.preconditions import PRECONDITIONS
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    contexto_aluno: str


class BuscarConhecimentoComContextoTool(BaseTool):
    name: str = "buscar_conhecimento_com_contexto"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _use_case: BuscarConhecimentoComContexto

    def __init__(self, use_case: BuscarConhecimentoComContexto) -> None:
        super().__init__()
        self._use_case = use_case

    def _run(self, query: str, contexto_aluno: str) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self, query: str, contexto_aluno: str) -> str:
        cfg = get_config()["configurable"]
        account_id: int = int(cfg["account_id"])

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        result = await self._use_case.execute(
            query=query, contexto_aluno=contexto_aluno, account_id=account_id
        )
        if not result["encontrado"]:
            if result.get("escalar"):
                return (
                    "Não encontrei informações suficientes na base de conhecimento. "
                    "Vou escalar para um especialista humano."
                )
            return "Não encontrei informações sobre este tópico mesmo com contexto adicional."
        return "\n\n".join(result["chunks"])
```

- [ ] **Step 6: Write `__init__.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/__init__.py
from agent.skill_loader import Adapters
from agent.skills.buscar_conhecimento_com_contexto.skill import BuscarConhecimentoComContextoTool
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


def make_skill(adapters: Adapters) -> BuscarConhecimentoComContextoTool:
    use_case = BuscarConhecimentoComContexto(
        knowledge_repo=adapters.knowledge_repo,
        usage_log_repo=adapters.usage_log_repo,
    )
    return BuscarConhecimentoComContextoTool(use_case=use_case)
```

- [ ] **Step 7: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/buscar_conhecimento_com_contexto/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.buscar_conhecimento_com_contexto.skill import BuscarConhecimentoComContextoTool
from agent.skills.buscar_conhecimento_com_contexto.use_case import BuscarConhecimentoComContexto


def _make_tool() -> BuscarConhecimentoComContextoTool:
    use_case = MagicMock(spec=BuscarConhecimentoComContexto)
    return BuscarConhecimentoComContextoTool(use_case=use_case)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "buscar_conhecimento_com_contexto"
    assert tool.description


def test_tool_has_correct_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    assert "query" in schema["properties"]
    assert "contexto_aluno" in schema["properties"]


@pytest.mark.asyncio
async def test_arun_encontrado_com_contexto():
    use_case = AsyncMock(spec=BuscarConhecimentoComContexto)
    use_case.execute.return_value = {
        "encontrado": True,
        "chunks": ["Alunos do Curso A acessam via app mobile."],
        "strategy": "context_enriched",
        "escalar": False,
    }
    tool = BuscarConhecimentoComContextoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch(
        "agent.skills.buscar_conhecimento_com_contexto.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(query="como acessar", contexto_aluno="Curso A")
    assert "app mobile" in result


@pytest.mark.asyncio
async def test_arun_nao_encontrado_escalar():
    use_case = AsyncMock(spec=BuscarConhecimentoComContexto)
    use_case.execute.return_value = {
        "encontrado": False,
        "chunks": [],
        "strategy": "context_failed",
        "escalar": True,
    }
    tool = BuscarConhecimentoComContextoTool(use_case=use_case)
    fake_config = {"configurable": {"account_id": "1"}}
    with patch(
        "agent.skills.buscar_conhecimento_com_contexto.skill.get_config",
        return_value=fake_config,
    ):
        result = await tool._arun(query="topico obscuro", contexto_aluno="Curso B")
    assert "escalar" in result.lower()
```

- [ ] **Step 8: Commit**

```bash
git add apps/api/src/agent/skills/buscar_conhecimento_com_contexto/
git commit -m "feat(skills): add buscar_conhecimento_com_contexto skill folder"
```

---

## Task 10 — Skill: `escalar_para_humano`

This skill has no `use_case.py` — it calls the `ChatNexoPort` directly.

- [ ] **Step 1: Create folder and files**

```bash
mkdir -p apps/api/src/agent/skills/escalar_para_humano/tests
touch apps/api/src/agent/skills/escalar_para_humano/tests/__init__.py
```

- [ ] **Step 2: Write `instructions.md`**

```markdown
# escalar_para_humano

Escala o atendimento para um agente humano via ChatNexo.

Use esta skill quando:
- O aluno solicitar falar com um humano explicitamente
- Nenhuma outra skill conseguir resolver o problema após tentativas
- Um guard disparar (menção legal, loop detectado)
- `buscar_conhecimento_com_contexto` retornar sinal de escalação

Após chamar esta skill, o atendimento sai do controle do agente de IA.
Não tente continuar o atendimento após a escalação.

**Parâmetros:** nenhum

**Retorno:** confirmação de que o atendimento foi escalado.
```

- [ ] **Step 3: Write `preconditions.py`**

```python
# apps/api/src/agent/skills/escalar_para_humano/preconditions.py
from agent.contracts import Precondition

PRECONDITIONS: list[Precondition] = []
```

- [ ] **Step 4: Write `skill.py`**

```python
# apps/api/src/agent/skills/escalar_para_humano/skill.py
from __future__ import annotations

from typing import Type

from langchain_core.tools import BaseTool
from langgraph.config import get_config
from pydantic import BaseModel, ConfigDict

from agent.skills._utils import _load_instructions
from agent.skills.escalar_para_humano.preconditions import PRECONDITIONS
from shared.domain.ports.chatnexo import ChatNexoPort


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EscalarParaHumanoTool(BaseTool):
    name: str = "escalar_para_humano"
    description: str = _load_instructions(__file__)
    args_schema: Type[BaseModel] = _Input

    _chatnexo: ChatNexoPort

    def __init__(self, chatnexo: ChatNexoPort) -> None:
        super().__init__()
        self._chatnexo = chatnexo

    def _run(self) -> str:  # pragma: no cover
        raise NotImplementedError("Use async")

    async def _arun(self) -> str:
        cfg = get_config()["configurable"]
        account_id: str = cfg["account_id"]
        phone: str = cfg["phone"]
        conversation_id: str = cfg["conversation_id"]

        for pre in PRECONDITIONS:
            if not pre.passed:
                return pre.block_message

        await self._chatnexo.escalar_para_humano(
            phone=phone, account_id=account_id, conversation_id=conversation_id
        )
        return "Atendimento escalado para um agente humano. Em breve alguém entrará em contato."
```

- [ ] **Step 5: Write `__init__.py`**

```python
# apps/api/src/agent/skills/escalar_para_humano/__init__.py
from agent.skill_loader import Adapters
from agent.skills.escalar_para_humano.skill import EscalarParaHumanoTool


def make_skill(adapters: Adapters) -> EscalarParaHumanoTool:
    return EscalarParaHumanoTool(chatnexo=adapters.chatnexo)
```

- [ ] **Step 6: Write `tests/test_skill.py`**

```python
# apps/api/src/agent/skills/escalar_para_humano/tests/test_skill.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent.skills.escalar_para_humano.skill import EscalarParaHumanoTool
from shared.domain.ports.chatnexo import ChatNexoPort


def _make_tool() -> EscalarParaHumanoTool:
    chatnexo = MagicMock(spec=ChatNexoPort)
    return EscalarParaHumanoTool(chatnexo=chatnexo)


def test_tool_instantiation():
    tool = _make_tool()
    assert tool.name == "escalar_para_humano"
    assert tool.description


def test_tool_has_empty_schema():
    tool = _make_tool()
    schema = tool.args_schema.model_json_schema()
    # No required parameters
    assert schema.get("properties", {}) == {} or not schema.get("required")


@pytest.mark.asyncio
async def test_arun_escala_e_retorna_confirmacao():
    chatnexo = AsyncMock(spec=ChatNexoPort)
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_config = {
        "configurable": {
            "account_id": "acc1",
            "phone": "5511999998888",
            "conversation_id": "conv-123",
        }
    }
    with patch("agent.skills.escalar_para_humano.skill.get_config", return_value=fake_config):
        result = await tool._arun()
    chatnexo.escalar_para_humano.assert_called_once_with(
        phone="5511999998888", account_id="acc1", conversation_id="conv-123"
    )
    assert "escalado" in result


@pytest.mark.asyncio
async def test_arun_chatnexo_recebe_parametros_corretos():
    chatnexo = AsyncMock(spec=ChatNexoPort)
    tool = EscalarParaHumanoTool(chatnexo=chatnexo)
    fake_config = {
        "configurable": {
            "account_id": "tenant-42",
            "phone": "5521988887777",
            "conversation_id": "c-abc",
        }
    }
    with patch("agent.skills.escalar_para_humano.skill.get_config", return_value=fake_config):
        await tool._arun()
    call_kwargs = chatnexo.escalar_para_humano.call_args.kwargs
    assert call_kwargs["account_id"] == "tenant-42"
    assert call_kwargs["phone"] == "5521988887777"
```

- [ ] **Step 7: Commit**

```bash
git add apps/api/src/agent/skills/escalar_para_humano/
git commit -m "feat(skills): add escalar_para_humano skill folder"
```

---

## Task 11 — Update `graph.py` to use `load_skills`

**File:** `apps/api/src/agent/graph.py`

- [ ] **Step 1: Open `graph.py` and locate the skill wiring section**

Find the block where individual skill factories are called (e.g. `make_access_skills(...)`, `make_refund_skills(...)`, `make_knowledge_skills(...)`, `make_core_skills(...)`). Replace the entire skill construction block with `load_skills(adapters)`.

The new signature and wiring block:

```python
# apps/api/src/agent/graph.py  — relevant excerpt (replace existing skill block)
from agent.skill_loader import Adapters, load_skills

# Inside build_graph() or equivalent factory function:
adapters = Adapters(
    access_repo=access_repo,
    cademi=cademi,
    chatnexo=chatnexo,
    refund_repo=refund_repo,
    hubla=hubla,
    legal_history=legal_history,
    refund_mutex=refund_mutex,
    knowledge_repo=knowledge_repo,
    usage_log_repo=usage_log_repo,
)
tools = load_skills(adapters)
```

Remove all previous imports of `make_access_skills`, `make_refund_skills`, `make_knowledge_skills`, `make_core_skills` (and the flat skill modules `agent.skills.access`, `agent.skills.refund`, etc.).

- [ ] **Step 2: Run the existing graph tests to verify nothing broke**

```bash
cd /home/fabio/www/agente-plug
python -m pytest apps/api/tests/unit/agent/test_graph.py -v 2>&1 | tail -30
```

Expected: all tests pass. If test file path differs, locate with `find apps/api/tests -name "test_graph*"`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/src/agent/graph.py
git commit -m "refactor(graph): replace manual skill factories with load_skills(adapters)"
```

---

## Task 12 — Delete old flat skill files and orphaned use cases

- [ ] **Step 1: Delete old flat skill files**

```bash
git rm apps/api/src/agent/skills/access.py
git rm apps/api/src/agent/skills/refund.py
git rm apps/api/src/agent/skills/knowledge.py
git rm apps/api/src/agent/skills/core.py
```

- [ ] **Step 2: Delete use case files moved into skill folders**

```bash
git rm apps/api/src/shared/application/use_cases/access/buscar_aluno_cademi.py
git rm apps/api/src/shared/application/use_cases/access/verificar_caso.py
git rm apps/api/src/shared/application/use_cases/access/enviar_link_acesso.py
git rm apps/api/src/shared/application/use_cases/refund/verificar_elegibilidade.py
git rm apps/api/src/shared/application/use_cases/refund/iniciar_retencao.py
git rm apps/api/src/shared/application/use_cases/refund/processar_reembolso.py
git rm apps/api/src/shared/application/use_cases/knowledge/buscar_conhecimento.py
git rm apps/api/src/shared/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py
git rm apps/api/src/shared/application/use_cases/knowledge/keyword_extractor.py
git rm apps/api/src/shared/application/use_cases/knowledge/synonym_expander.py
git rm apps/api/src/shared/application/use_cases/knowledge/stopwords_ptbr.py
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore(skills): delete flat skill files and use cases moved into skill folders"
```

---

## Task 13 — Final verification

- [ ] **Step 1: Run all skill tests**

```bash
cd /home/fabio/www/agente-plug
python -m pytest apps/api/src/agent/skills/ -v 2>&1 | tail -40
```

Expected: all PASSED across all 9 skill folders.

- [ ] **Step 2: Run the full test suite**

```bash
python -m pytest apps/api/tests/ -v 2>&1 | tail -40
```

Expected: all PASSED. No import errors referencing the deleted flat files.

- [ ] **Step 3: Smoke-check skill discovery**

```python
# Quick Python snippet to verify loader finds exactly 9 skills:
from pathlib import Path
skills_dir = Path("apps/api/src/agent/skills")
folders = [f for f in sorted(skills_dir.iterdir()) if f.is_dir() and not f.name.startswith("_")]
print(len(folders), [f.name for f in folders])
# Expected: 9 ['buscar_aluno_cademi', 'buscar_conhecimento', 'buscar_conhecimento_com_contexto',
#              'enviar_link_acesso', 'escalar_para_humano', 'oferecer_retencao',
#              'processar_reembolso', 'verificar_caso_acesso', 'verificar_elegibilidade_reembolso']
```

- [ ] **Step 4: Final commit if any cleanup was needed**

```bash
git add -A
git commit -m "chore(skills): skill folder migration complete — 9 self-contained skill packages"
```
