# NexoIA — Skill Refactor: BaseTool + Guards-inside-Skills

## Contexto

O projeto já implementa ReAct corretamente — o LLM seleciona skills, skills executam, resultado volta pro LLM. O problema é que o nó `raciocinar` carrega lógica que não é dele:

1. **Skills como closures `@tool`**: ports capturados por closure, sem injeção explícita, sem schema Pydantic.
2. **Guards pré-LLM com `skill_override`**: guards injetam um `AIMessage` com `tool_calls` fabricado, bypassando o LLM completamente.

Este spec define a refatoração para o padrão de mercado ReAct: skills como `BaseTool`, guards com responsabilidade clara.

---

## Objetivos

- Skills viram classes `BaseTool` com `args_schema` Pydantic e `_arun` explícito.
- Invariantes de compliance (mutex, CDC) vivem dentro do `_arun` da skill relevante.
- Guards de segurança (menção legal, loop) param de injetar `tool_calls` falsos — passam a injetar `SystemMessage` de instrução para o LLM.
- `GuardResult.skill_override` é removido; substituído por `forced_instruction`.
- `make_raciocinar_node` mantém `guard_service` mas não usa mais `skill_override` — usa `forced_instruction` para injetar `SystemMessage`.
- Nada muda no loop ReAct, nos use-cases, nem no KB Admin.

---

## Anatomia padrão de uma skill

```python
class BuscarAlunoCademiInput(BaseModel):
    email: str | None = None
    cpf:   str | None = None


class BuscarAlunoCademiTool(BaseTool):
    name: str = "buscar_aluno_cademi"
    description: str = """
    Busca aluno na Cademi por email ou CPF.
    Use quando: precisa localizar cadastro para enviar acesso.
    Retorna: ENCONTRADO com nome e student_id, SOLICITAR_CPF, ou ESCALADO.
    Não use quando: aluno já foi localizado (student_id disponível).
    """
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
```

**Regras:**
- Um `Input(BaseModel)` por skill, mesmo que vazio (`EmptyInput(BaseModel): pass`).
- Ports injetados via `__init__` pelo Pydantic (campo de classe).
- `model_config = ConfigDict(arbitrary_types_allowed=True)` obrigatório.
- Context runtime (`account_id`, `phone`, `conversation_id`) sempre via `get_config()["configurable"]` — não é injetado no `__init__`.
- `_run` sempre levanta `NotImplementedError` — sistema é async-only.

---

## Factories (sem mudança de interface)

```python
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

`build_graph()` não muda sua assinatura pública além de remover `guard_service`.

---

## Invariantes de compliance dentro das skills

### `ProcessarReembolsoTool`

```python
async def _arun(self) -> str:
    cfg = get_config()["configurable"]
    if not await self.refund_mutex.acquire(cfg["account_id"], cfg["phone"]):
        return "BLOQUEADO: Reembolso já em processamento para este aluno."
    return await self.processar_uc.execute(cfg["account_id"], cfg["phone"])
```

### `VerificarElegibilidadeReembolsoTool`

O use-case `VerificarElegibilidadeReembolso` já verifica CDC 7 dias internamente e retorna `INELEGIVEL` com data. Nenhuma mudança de lógica — só migração de closure para classe.

---

## Guards de segurança: de `skill_override` para `SystemMessage`

Os guards `LegalMentionGuard` e `LoopDetectorGuard` detectam condições críticas (menção legal, loop de respostas). Atualmente injetam um `AIMessage` com `tool_calls` fabricado, bypassando o LLM.

**Novo comportamento:** quando bloqueado, o guard injeta um `SystemMessage` de instrução. O LLM lê a instrução e chama `escalar_para_humano` por conta própria.

```python
# GuardResult — skill_override removido
@dataclass(frozen=True)
class GuardResult:
    blocked: bool
    response: str = ""        # resposta direta (sem LLM), quando aplicável
    reason: str = ""
    forced_instruction: str = ""  # SystemMessage a injetar (novo)
```

```python
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

No nó `raciocinar`, quando `guard_result.blocked` e há `forced_instruction`:

```python
if guard_result.forced_instruction:
    msgs = [SystemMessage(guard_result.forced_instruction), *state["messages"]]
    response = await llm.ainvoke(msgs, config)
    # LLM vai emitir tool_call para escalar_para_humano
    update = {"messages": [response]}
    if getattr(response, "tool_calls", None):
        update["skill_em_andamento"] = response.tool_calls[0]["name"]
    return update
```

O LLM continua tomando a decisão (ReAct puro). A instrução é uma orientação forte, não um bypass.

**`FrustrationGuard`**: stub sem lógica — deletado (YAGNI).

---

## Nó `raciocinar` após refatoração

```python
def make_raciocinar_node(
    guard_service: GuardService,   # permanece — ainda detecta condições críticas
    long_term_repo: Any,
    llm: Any,
):
```

Responsabilidades que permanecem no nó:
- Fila inteligente (`skill_em_andamento`)
- Aplicar `forced_instruction` do guard como `SystemMessage`
- `CommunicationRules` pós-LLM (validação de tom, não regra de negócio)
- Long-term facts no system prompt

---

## Arquivos modificados

| Arquivo | Mudança |
|---------|---------|
| `infrastructure/skills/access.py` | 3 closures → 3 classes BaseTool |
| `infrastructure/skills/refund.py` | 3 closures → 3 classes BaseTool; mutex guard em `ProcessarReembolsoTool._arun` |
| `infrastructure/skills/knowledge.py` | 2 closures → 2 classes BaseTool |
| `infrastructure/skills/core.py` | 1 closure → 1 classe BaseTool |
| `domain/policies/guards/__init__.py` | `GuardResult`: remove `skill_override`, adiciona `forced_instruction`; deleta `FrustrationGuard` |
| `domain/policies/guards/legal_mention.py` | Usa `forced_instruction` em vez de `skill_override` |
| `domain/policies/guards/loop_detector.py` | Usa `forced_instruction` em vez de `skill_override` |
| `domain/policies/guards/frustration.py` | Deletado |
| `langgraph_runtime/nodes.py` | Remove lógica de `skill_override`; aplica `forced_instruction` como `SystemMessage` |
| `langgraph_runtime/graph_builder.py` | Sem mudança de assinatura — `guard_service` permanece |

**Não modificados:** use-cases, domain entities, KB Admin, routers, workers, migrations, testes de integração existentes.

---

## Testes

Cada `XTool` é testável de forma isolada:

```python
async def test_processar_reembolso_bloqueado_por_mutex():
    mutex = AsyncMock()
    mutex.acquire.return_value = False
    tool = ProcessarReembolsoTool(
        processar_uc=AsyncMock(),
        refund_mutex=mutex,
    )
    with patch("nexoia.infrastructure.skills.refund.get_config",
               return_value={"configurable": {"account_id": 1, "phone": "5511999"}}):
        result = await tool._arun()
    assert result.startswith("BLOQUEADO:")
```

Cada guard é testável sem LLM:

```python
def test_legal_mention_guard_retorna_forced_instruction():
    guard = LegalMentionGuard()
    result = guard.check("vou levar pro procon", {})
    assert result.blocked
    assert result.forced_instruction
    assert not result.response  # sem resposta direta — LLM decide
```

---

## O que NÃO muda

- Loop ReAct: `raciocinar → _roteador → executar (ToolNode) → pos_execucao`
- `ToolNode(skills)` — recebe `list[BaseTool]`, igual antes
- Use-cases em `application/use_cases/`
- `get_config()["configurable"]` para context runtime
- KB Admin (FastAPI, pgvector) — subsistema independente
- `CommunicationRules` — permanece no nó como validação de tom
