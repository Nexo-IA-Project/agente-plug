# Spec ⑦ — Capability Knowledge (RAG)

**Data:** 2026-04-18
**Fase:** 1
**Repositório alvo:** `nexoia-agent`
**Depende de:** Spec ① (Core — Intent Router, handoff), Spec ⑥ (KB Admin — chunks, embeddings, search)
**Status:** Design aprovado — aguardando plano de implementação

---

## 1. Contexto e Objetivo

A Capability Knowledge é a "dúvida técnica" do aluno. Quando o aluno faz uma pergunta geral sobre o produto, plataforma, como fazer algo, a IA consulta a KB (alimentada via spec ⑥) e responde.

**Diferença vs. spec ⑥:** o spec ⑥ é o **painel de administração** da KB (upload, indexação, CRUD). O spec ⑦ é a **capability de runtime** que usa a KB para responder ao aluno no WhatsApp.

**Resumo do fluxo (PRD 7.4):**
```
Aluno manda pergunta genérica/técnica
  → LLM identifica intenção de knowledge
    → LLM chama buscar_conhecimento(query)
      → Tentativa 1: palavras exatas (threshold 0.55)
        → Tentativa 2: expansão de sinônimos (160+ termos)
          → Tentativa 3: extração de keywords (remove stopwords)
            → Nenhum resultado: retorna sinal ao LLM pedir contexto
              → LLM chama buscar_conhecimento_com_contexto(original_query, context)
                → Sem resultado: use case escala + registra em kb_usage_logs
```

---

## 2. Escopo

### O que faz

- Capability reativa — LLM decide quando acionar as skills de knowledge com base na intenção do aluno
- 3 estratégias de busca em cascata na KB (via `KnowledgePort` implementado por spec ⑥)
- 4ª tentativa solicitando contexto objetivo ao aluno
- Escala silenciosa se todas as tentativas falharem
- Logs de queries sem resultado para enriquecer a KB posteriormente

### O que NÃO faz

- Não alimenta a KB (responsabilidade do spec ⑥)
- Não gera embeddings (spec ⑥)
- Não expõe prompts do sistema

---

## 3. Arquivos

### Novos
```
src/nexoia/application/use_cases/knowledge/
    buscar_conhecimento.py          # 3 tentativas em cascata (exact → synonyms → keywords)
    buscar_conhecimento_com_contexto.py   # 4ª tentativa com contexto enriquecido + escala
    synonym_expander.py             # 160+ termos mapeados (antes em application/kb/)
    keyword_extractor.py            # remove stopwords PT-BR (antes em application/kb/)
    stopwords_ptbr.py               # lista stopwords
src/nexoia/infrastructure/skills/knowledge.py       # make_knowledge_skills() factory
tests/unit/use_cases/test_knowledge.py
tests/integration/test_knowledge_flow.py
```

### Modificados
```
src/nexoia/infrastructure/langgraph_runtime/graph_builder.py  # + make_knowledge_skills(...)
src/nexoia/config/settings.py                       # + KB_ATTEMPT_1_THRESHOLD, KB_MAX_TURNS
src/nexoia/infrastructure/db/repositories/usage_log_repo.py  # + registra queries sem resultado
docs/superpowers/OPEN_QUESTIONS.md                  # + CQ-K01 (lista de sinônimos)
```

---

## 4. Use Cases e Skills

Sem subgraph LangGraph. Estado não precisa de classe própria — o LLM mantém contexto via
`AgentState.messages` (checkpoint). A 4ª tentativa (pedir contexto) é tratada naturalmente
pelo loop do LLM: o use case sinaliza "precisa de contexto", o LLM pede ao aluno, e na
próxima mensagem chama `buscar_conhecimento_com_contexto`.

### `BuscarConhecimento` (`application/use_cases/knowledge/buscar_conhecimento.py`)

Executa tentativas 1–3 em cascata. Recebe dependências via `__init__`.

```python
class BuscarConhecimento:
    def __init__(
        self,
        knowledge_repo: KnowledgePort,
        synonym_expander: SynonymExpander,
        keyword_extractor: KeywordExtractor,
        usage_log_repo: UsageLogRepoPort,
    ): ...

    async def execute(self, query: str, account_id: int) -> BuscaResult:
        # Tentativa 1 — palavras exatas (threshold 0.55)
        chunks = await self._knowledge_repo.search(query, account_id, threshold=0.55, top_k=5)
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        # Tentativa 2 — sinônimos (160+ termos — CQ-K01)
        expanded = self._synonym_expander.expand(query)
        chunks = await self._knowledge_repo.search(expanded, account_id, threshold=0.55, top_k=5)
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        # Tentativa 3 — keywords (remove stopwords PT-BR)
        keywords = " ".join(self._keyword_extractor.extract(query))
        chunks = await self._knowledge_repo.search(keywords, account_id, threshold=0.55, top_k=5)
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        return BuscaResult(chunks=[], status="ask_context")
```

`BuscaResult(status="found")` → LLM usa os chunks para gerar resposta.
`BuscaResult(status="ask_context")` → LLM pede contexto ao aluno (*"Me conta um pouco mais..."*).

### `BuscarConhecimentoComContexto` (`application/use_cases/knowledge/buscar_conhecimento_com_contexto.py`)

4ª tentativa — chamada quando o aluno fornece contexto após `ask_context`.

```python
async def execute(self, original_query: str, context: str, account_id: int) -> BuscaResult:
    enriched = f"{original_query} {context}"
    chunks = await self._knowledge_repo.search(enriched, account_id, threshold=0.55, top_k=5)
    if chunks:
        return BuscaResult(chunks=chunks, status="found")

    await self._usage_log_repo.record_no_result(account_id, original_query)
    await self._chatnexo.transfer_to_human(account_id, reason="knowledge_not_found")
    return BuscaResult(chunks=[], status="escalated")
```

### `SynonymExpander` e `KeywordExtractor`

Movidos de `application/kb/` → `application/use_cases/knowledge/`.
São Python puro, zero dependência externa — podem ser testados sem mocks.

```python
# synonym_expander.py
SYNONYMS: dict[str, list[str]] = {
    "acessar": ["entrar", "logar", "fazer login", "entrar no sistema"],
    "senha":   ["palavra-chave", "credencial", "password"],
    "curso":   ["treinamento", "aula", "conteúdo", "material"],
    # ... 160+ termos — ver CQ-K01
}
```

### Factory de Skills (`infrastructure/skills/knowledge.py`)

```python
def make_knowledge_skills(
    knowledge_repo: KnowledgePort,
    synonym_expander: SynonymExpander,
    keyword_extractor: KeywordExtractor,
    usage_log_repo: UsageLogRepoPort,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    buscar_uc   = BuscarConhecimento(knowledge_repo, synonym_expander, keyword_extractor, usage_log_repo)
    contexto_uc = BuscarConhecimentoComContexto(knowledge_repo, usage_log_repo, chatnexo)

    @tool
    async def buscar_conhecimento(query: str) -> str:
        """
        Busca resposta na base de conhecimento do produto (3 estratégias em cascata).
        Use quando: aluno faz pergunta técnica ou geral sobre o produto/plataforma.
        Retorna: chunks relevantes OU sinal para pedir mais contexto ao aluno.
        Não use quando: dúvida é sobre reembolso, acesso ou loja express.
        """
        cfg = get_config()["configurable"]
        result = await buscar_uc.execute(query, cfg["account_id"])
        if result.status == "found":
            return "\n\n".join(c.text for c in result.chunks)
        return "ASK_CONTEXT: Me conta um pouco mais sobre o que você tá precisando."

    @tool
    async def buscar_conhecimento_com_contexto(original_query: str, context: str) -> str:
        """
        4ª tentativa de busca com contexto adicional fornecido pelo aluno.
        Use quando: buscar_conhecimento retornou ASK_CONTEXT e o aluno respondeu com mais detalhes.
        Retorna: chunks relevantes OU sinaliza escalação para humano.
        """
        cfg = get_config()["configurable"]
        result = await contexto_uc.execute(original_query, context, cfg["account_id"])
        if result.status == "found":
            return "\n\n".join(c.text for c in result.chunks)
        return "ESCALATED: Transferindo para atendimento humano."

    return [buscar_conhecimento, buscar_conhecimento_com_contexto]

---

## 5. Componentes

`SynonymExpander` e `KeywordExtractor` ficam em `application/use_cases/knowledge/` — são helpers
do use case, Python puro, sem dependência externa. Ver seção 4 para código detalhado.

> **TODO — CQ-K01:** Consolidar lista completa de 160+ termos com a equipe da G2.

Stopwords PT-BR: "a", "o", "de", "que", "como", "faço", "para", "meu", "minha", "tô", "tá" etc.

---

## 6. Port (reutilizado do Core/spec ⑥)

```python
class KnowledgePort(Protocol):
    async def search(
        self,
        query: str,
        account_id: int,
        threshold: float = 0.55,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]: ...
```

Implementação concreta fica em `application/use_cases/kb_admin/buscar_chunks.py` (spec ⑥), que usa `ChunkRepoPort` + `EmbeddingsPort` via DI e ORM SQLAlchemy 2 — sem SQL solto.

---

## 7. Configuração

```python
KB_ATTEMPT_1_THRESHOLD: float = 0.55    # PRD 7.4 — threshold fixo
KB_TOP_K: int = 5
KB_MAX_TURNS_WAITING_CONTEXT: int = 1   # aluno só tem 1 chance de dar contexto antes de escalar
```

---

## 8. Observabilidade

### Logs estruturados

Cada nó loga: `capability=knowledge`, `node`, `attempt`, `account_id`, `chunks_found_count`

- Tentativa 1 sem resultado → `level=INFO`, `reason=exact_no_match`
- Tentativa 2 sem resultado → `level=INFO`, `reason=synonyms_no_match`
- Tentativa 3 sem resultado → `level=INFO`, `reason=keywords_no_match`
- Pediu contexto → `level=INFO`, `reason=ask_context`
- Tentativa 4 sem resultado → `level=WARNING`, `reason=all_attempts_exhausted`, handoff disparado

### Métricas Prometheus

```
knowledge_capability_total{status="answered"|"escalated"|"error"}
knowledge_attempts_total{attempt="1"|"2"|"3"|"4"}
knowledge_no_result_total           # incrementa em persist_no_result
knowledge_answer_latency_seconds (histogram)
```

---

## 9. Testes

### Unitários (`tests/unit/use_cases/test_knowledge.py`)

| Teste | Cenário |
|-------|---------|
| `test_exact_match_succeeds` | T1 encontra → `status="found"` |
| `test_synonym_expansion_succeeds` | T1 falha, T2 (sinônimos) encontra → `status="found"` |
| `test_keyword_extraction_succeeds` | T1+T2 falham, T3 (keywords) encontra → `status="found"` |
| `test_three_attempts_exhausted_returns_ask_context` | T1+T2+T3 falham → `status="ask_context"` |
| `test_directed_search_with_context_succeeds` | `BuscarComContexto` T4 encontra → `status="found"` |
| `test_all_attempts_exhausted_escalates_and_logs` | T4 falha → transfer_to_human + `kb_usage_logs` |
| `test_synonym_expander_basic` | "acessar" → expande com "entrar, logar, fazer login" |
| `test_keyword_extractor_removes_stopwords` | "como faço para acessar" → `["acessar"]` |

### Integração (`tests/integration/test_knowledge_flow.py`)

- KB pré-populada (via fixtures) com chunks conhecidos + pgvector (testcontainers)
- Valida busca com threshold 0.55
- Valida fluxo completo: skill → 3 tentativas → skill contexto → directed search
- Valida `kb_usage_logs` registrado em queries sem resultado

---

## 10. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-K01` | LLM identifica intenção de knowledge e chama `buscar_conhecimento(query)` para perguntas gerais/técnicas. |
| `RF-K02` | Tentativa 1: busca com palavras exatas do aluno, threshold 0.55 (PRD 7.4). |
| `RF-K03` | Tentativa 2: expansão de sinônimos (160+ termos). |
| `RF-K04` | Tentativa 3: extração de keywords (remove stopwords PT-BR). |
| `RF-K05` | Tentativa 4: `buscar_conhecimento` retorna `ASK_CONTEXT` → LLM pede contexto → LLM chama `buscar_conhecimento_com_contexto(original_query, context)`. |
| `RF-K06` | 4 tentativas esgotadas: handoff silencioso + registra em `kb_usage_logs`. |
| `RF-K07` | Lista de sinônimos: TODO CQ-K01 — consolidar com a equipe G2. |
| `RF-K08` | Queries sem resultado persistidas para identificar lacunas na KB. |

## 11. Requisitos Não-Funcionais

| ID | Requisito |
|----|-----------|
| `RNF-K01` | Tenant isolation: toda query filtra por `account_id`. |
| `RNF-K02` | Estado entre turnos persistido via checkpoint LangGraph (aguardando contexto). |
| `RNF-K03` | Cobertura de testes: ≥90% nas linhas da capability. |
| `RNF-K04` | Latência: cada tentativa ≤ 2s (busca pgvector + LLM answer). |
