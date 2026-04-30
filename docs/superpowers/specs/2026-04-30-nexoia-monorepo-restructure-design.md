# NexoIA — Monorepo Restructure + Skill Folder Pattern

## Objetivo

Reorganizar o projeto `agente-plug` em estrutura monorepo `apps/api` + `apps/web`, migrar as skills para pastas individuais autocontidas, e criar o scaffold inicial do frontend Next.js (dashboard de desempenho, KB admin).

---

## Estrutura raiz

```
agente-plug/
  apps/
    api/                    ← backend Python (FastAPI + LangGraph)
    web/                    ← frontend Next.js
  docs/
  scripts/
```

---

## `apps/api/` — Backend

### Estrutura de pacotes

```
apps/api/
  src/
    nexoia/                 ← pacote Python (nome mantido; imports existentes não quebram)
      agent/                ← NOVO: runtime do agente ReAct
        skills/             ← uma pasta por skill
        guards/             ← guards globais (LegalMention, LoopDetector)
        contracts.py        ← tipos Ok, Err, Precondition
        skill_loader.py     ← auto-descoberta de skills
        graph.py            ← era infrastructure/langgraph_runtime/graph_builder.py
        react_node.py       ← era infrastructure/langgraph_runtime/nodes.py
        state.py            ← era infrastructure/langgraph_runtime/state.py
        prompt.py           ← era infrastructure/llm/system_prompt.py
      shared/
        domain/             ← entities, ports, events, policies (sem mudança de conteúdo)
        adapters/           ← implementações concretas (cademi, hubla, redis, openai, meta, kb)
        config/             ← settings.py
      interface/            ← http routers, worker handlers (sem mudança)
      main.py
      worker.py
  tests/
  migrations/
  alembic.ini
  pyproject.toml
  Dockerfile
```

### O que muda vs. o que fica

| De | Para |
|----|------|
| `src/nexoia/infrastructure/langgraph_runtime/graph_builder.py` | `agent/graph.py` |
| `src/nexoia/infrastructure/langgraph_runtime/nodes.py` | `agent/react_node.py` |
| `src/nexoia/infrastructure/langgraph_runtime/state.py` | `agent/state.py` |
| `src/nexoia/infrastructure/llm/system_prompt.py` | `agent/prompt.py` |
| `src/nexoia/domain/policies/guards/` | `agent/guards/` |
| `src/nexoia/infrastructure/skills/*.py` | `agent/skills/<skill_name>/` (ver abaixo) |
| `src/nexoia/application/use_cases/<cap>/<uc>.py` | `agent/skills/<skill_name>/use_case.py` |
| `src/nexoia/infrastructure/llm/`, `redis/`, `kb/`, `meta/` | `shared/adapters/` |
| `src/nexoia/domain/`, `src/nexoia/config/` | `shared/domain/`, `shared/config/` |
| `src/nexoia/application/memory/` | `shared/memory/` |
| `src/nexoia/application/lifecycle_handler.py` | `shared/application/lifecycle_handler.py` |
| `src/nexoia/application/purchase_handler.py` | `shared/application/purchase_handler.py` |
| `src/nexoia/application/message_dispatcher.py` | `shared/application/message_dispatcher.py` |
| `src/nexoia/application/scheduler/` | `shared/application/scheduler/` |
| `src/nexoia/interface/` | `interface/` (sem mudança) |

---

## Anatomia de uma skill

Cada skill é uma pasta autocontida dentro de `agent/skills/`:

```
agent/skills/buscar_aluno_cademi/
  __init__.py          ← re-exporta make_skill(adapters) → BaseTool
  skill.py             ← classe BaseTool com args_schema + _arun + PRECONDITIONS
  use_case.py          ← lógica de negócio (veio de application/use_cases/)
  preconditions.py     ← PRECONDITIONS: list[Precondition] = []
  instructions.md      ← descrição rica para o LLM (use quando / não use / retornos)
  tests/
    __init__.py
    test_skill.py
```

### `__init__.py`

```python
from nexoia.agent.skills.buscar_aluno_cademi.skill import make_skill

__all__ = ["make_skill"]
```

### `skill.py` (padrão)

```python
from nexoia.agent.contracts import Precondition
from nexoia.agent.skills.buscar_aluno_cademi.preconditions import PRECONDITIONS
from nexoia.agent.skills.buscar_aluno_cademi.use_case import BuscarAlunoCademi

class BuscarAlunoCademiInput(BaseModel):
    email: str | None = None
    cpf: str | None = None

class BuscarAlunoCademiTool(BaseTool):
    name: str = "buscar_aluno_cademi"
    description: str = _load_instructions(__file__)   # carrega instructions.md
    args_schema: Type[BaseModel] = BuscarAlunoCademiInput
    buscar_uc: BuscarAlunoCademi
    model_config = ConfigDict(arbitrary_types_allowed=True)

    async def _arun(self, email: str | None = None, cpf: str | None = None) -> str:
        cfg = get_config()["configurable"]
        for check in PRECONDITIONS:
            result = check.check({"cfg": cfg})
            if isinstance(result, Err):
                return result.model_dump_json()
        return await self.buscar_uc.execute(
            account_id=cfg["account_id"], phone=cfg["phone"], email=email, cpf=cpf
        )

    def _run(self, **_: object) -> str:
        raise NotImplementedError

def make_skill(adapters) -> BaseTool:
    return BuscarAlunoCademiTool(
        buscar_uc=BuscarAlunoCademi(repo=adapters.access_repo, cademi=adapters.cademi),
    )
```

A função `_load_instructions(__file__)` lê o `instructions.md` da mesma pasta e retorna como string:

```python
# agent/_utils.py
from pathlib import Path

def _load_instructions(skill_file: str) -> str:
    return (Path(skill_file).parent / "instructions.md").read_text()
```

Cada `skill.py` importa: `from nexoia.agent._utils import _load_instructions`.

### `instructions.md` (padrão)

```markdown
# buscar_aluno_cademi

Busca aluno na Cademi por email ou CPF.

**Use quando:**
- Precisa localizar o cadastro do aluno para enviar acesso
- Tente email primeiro, CPF se falhar

**NÃO use quando:**
- Aluno já foi localizado (student_id disponível)

**Argumentos:**
- `email`: email do aluno (opcional)
- `cpf`: CPF do aluno (opcional)

**Retorno (Ok):**
- ENCONTRADO com nome e student_id

**Retorno (Err):**
- SOLICITAR_CPF: email não encontrado, peça o CPF
- ESCALADO: não foi possível localizar
```

---

## As 9 skills

| Pasta | Use case de origem |
|---|---|
| `verificar_caso_acesso/` | `use_cases/access/verificar_caso.py` |
| `buscar_aluno_cademi/` | `use_cases/access/buscar_aluno_cademi.py` |
| `enviar_link_acesso/` | `use_cases/access/enviar_link_acesso.py` |
| `verificar_elegibilidade_reembolso/` | `use_cases/refund/verificar_elegibilidade.py` |
| `oferecer_retencao/` | `use_cases/refund/iniciar_retencao.py` |
| `processar_reembolso/` | `use_cases/refund/processar_reembolso.py` |
| `buscar_conhecimento/` | `use_cases/knowledge/buscar_conhecimento.py` + `keyword_extractor.py` + `synonym_expander.py` |
| `buscar_conhecimento_com_contexto/` | `use_cases/knowledge/buscar_conhecimento_com_contexto.py` |
| `escalar_para_humano/` | sem use case (só chama `chatnexo.transfer_to_human`) |

---

## `contracts.py`

```python
# agent/contracts.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class Ok:
    data: dict = None

@dataclass(frozen=True)
class Err:
    code: str
    message: str
    hint: str = ""

    def model_dump_json(self) -> str:
        import json
        return json.dumps({"code": self.code, "message": self.message, "hint": self.hint})

class Precondition(Protocol):
    def check(self, state: dict) -> Ok | Err: ...
```

---

## `skill_loader.py`

`Adapters` é um dataclass que concentra todos os ports injetados, passado do `graph.py` para cada `make_skill`:

```python
# agent/skill_loader.py
import importlib
from dataclasses import dataclass
from pathlib import Path
from langchain_core.tools import BaseTool

from nexoia.shared.domain.ports.cademi_port import CademiPort
from nexoia.shared.domain.ports.chatnexo import ChatNexoPort
from nexoia.shared.domain.ports.hubla_port import HublaPort
from nexoia.shared.domain.ports.knowledge import KnowledgePort
from nexoia.shared.domain.ports.legal_history_port import LegalHistoryPort
from nexoia.shared.domain.ports.refund_mutex import RefundMutexPort

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
    skills_dir = Path(__file__).parent / "skills"
    skills = []
    for folder in sorted(skills_dir.iterdir()):
        if folder.is_dir() and not folder.name.startswith("_"):
            module = importlib.import_module(f"nexoia.agent.skills.{folder.name}")
            skills.append(module.make_skill(adapters))
    return skills
```

`graph.py` passa a chamar `load_skills(adapters)` em vez de listar factories manualmente.

---

## `apps/web/` — Frontend Next.js

### Stack
- **Next.js 15** (App Router)
- **Tailwind CSS**
- **shadcn/ui** (componentes)
- **TypeScript**

### Estrutura

```
apps/web/
  src/
    app/
      layout.tsx              ← sidebar com nav: Dashboard / KB Admin / Contas
      page.tsx                ← redirect → /dashboard
      dashboard/
        page.tsx              ← métricas de desempenho da IA
                                 (skills usadas, taxa escalação, conversas/dia,
                                  tempo médio resolução)
      kb/
        page.tsx              ← lista de documentos da base de conhecimento
        upload/
          page.tsx            ← upload de novos documentos
      accounts/
        page.tsx              ← lista de contas (placeholder inicial)
    components/
      ui/                     ← shadcn/ui (Button, Card, Table, etc.)
      sidebar.tsx
      metric-card.tsx
    lib/
      api.ts                  ← client HTTP → API FastAPI
  package.json
  next.config.ts
  tailwind.config.ts
  tsconfig.json
  .env.local.example          ← NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Páginas do scaffold inicial

**`/dashboard`** — cards de métricas mockadas (dados reais virão de endpoint `/admin/analytics` a implementar):
- Total de conversas (período)
- Taxa de escalação para humano
- Skills mais chamadas (top 5)
- Gráfico de conversas por dia

**`/kb`** — lista de documentos e upload, consumindo `/admin/documents` (já existe na API)

**`/accounts`** — placeholder com mensagem "Em breve"

---

## O que NÃO muda

- Loop ReAct: `raciocinar → executar → pos_execucao`
- Entidades de domínio (`RefundCase`, `AccessCase`, etc.)
- Ports/interfaces (`CademiPort`, `HublaPort`, etc.)
- Migrations e Alembic
- Routers FastAPI e worker handlers
- Testes de integração existentes
- `pyproject.toml` package name (`nexoia`)

---

## Ordem de implementação sugerida

1. Mover arquivos raiz → `apps/api/` + criar `apps/web/` scaffold Next.js
2. Criar `agent/contracts.py`
3. Mover `langgraph_runtime/` → `agent/` (renomear arquivos)
4. Mover `domain/policies/guards/` → `agent/guards/`
5. Criar as 9 pastas de skills (uma por uma, com use_case + tests)
6. Criar `skill_loader.py` e atualizar `graph.py`
7. Remover `infrastructure/skills/` e `application/use_cases/` (agora vazios)
