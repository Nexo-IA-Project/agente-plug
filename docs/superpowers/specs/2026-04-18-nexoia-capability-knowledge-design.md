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
  → Intent Router classifica intent = "knowledge"
    → Worker invoca subgraph Knowledge
      → Tentativa 1: palavras exatas (threshold 0.55)
        → Tentativa 2: expansão de sinônimos (160+ termos)
          → Tentativa 3: extração de keywords (remove stopwords)
            → 4ª: pede contexto ao aluno → busca direcionada
              → Persistir sem resultado: escala silenciosa
```

---

## 2. Escopo

### O que faz

- Subgraph LangGraph reativo, acionado quando `intent = "knowledge"`
- 3 estratégias de busca em cascata na KB (via `KnowledgePort` do Core ou spec ⑥)
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
src/nexoia/application/capabilities/knowledge.py
src/nexoia/application/kb/synonym_expander.py       # 160+ termos mapeados
src/nexoia/application/kb/keyword_extractor.py      # remove stopwords PT-BR
src/nexoia/application/kb/stopwords_ptbr.py         # lista stopwords
tests/unit/capabilities/test_knowledge.py
tests/integration/test_knowledge_flow.py
```

### Modificados
```
src/nexoia/application/intent_router.py             # + intent "knowledge"
src/nexoia/config/settings.py                       # + KB_ATTEMPT_1_THRESHOLD, KB_MAX_TURNS
src/nexoia/infrastructure/db/repositories/usage_log_repo.py  # + registra queries sem resultado
docs/superpowers/OPEN_QUESTIONS.md                  # + CQ-K01 (lista de sinônimos)
```

---

## 4. Subgraph LangGraph

### Grafo de nós

```
START
  │
  ▼
search_exact            ← tentativa 1: palavras exatas do aluno (threshold 0.55)
  │ achou → answer → END
  ▼
search_synonyms         ← tentativa 2: expande sinônimos e busca
  │ achou → answer → END
  ▼
search_keywords         ← tentativa 3: extrai keywords, remove stopwords e busca
  │ achou → answer → END
  ▼
ask_context             ← envia "Me conta um pouco mais, quero te ajudar melhor"
  │ recebe resposta → search_directed
  ▼
search_directed         ← 4ª tentativa com contexto adicional
  │ achou → answer → END
  ▼
persist_no_result       ← registra query em kb_usage_logs
  │
  ▼
escalate                ← handoff silencioso (reason="knowledge_not_found")
  │
  ▼
END
```

### Estado do subgraph

```python
class KnowledgeState(ConversationState):
    original_query: str                 # mensagem original do aluno
    enriched_query: str | None          # query após contexto do aluno
    attempt: int                        # 1, 2, 3 ou 4
    synonym_expanded: str | None
    keywords_extracted: list[str] | None
    chunks_found: list[KnowledgeChunk]  # resultado da última busca
    context_requested: bool             # True se já pedimos contexto
    no_result: bool                     # True se todas as tentativas falharam
```

### Nó `search_exact`

1. Chama `KnowledgePort.search(query=state.original_query, threshold=KB_ATTEMPT_1_THRESHOLD=0.55, top_k=5)`
2. Se retornou ≥ 1 chunk: `state.chunks_found = resultado`, vai para `answer`
3. Senão: `state.attempt = 2`, vai para `search_synonyms`

### Nó `search_synonyms`

1. Chama `SynonymExpander.expand(query)` — substitui termos pelos sinônimos mapeados (160+ termos — ver CQ-K01)
2. Exemplo: "não consigo entrar" → "não consigo acessar / fazer login / entrar no sistema"
3. Chama `KnowledgePort.search(query=expanded, threshold=0.55, top_k=5)`
4. Se achou: vai para `answer`. Senão: `attempt=3`, vai para `search_keywords`

### Nó `search_keywords`

1. Chama `KeywordExtractor.extract(query)` — remove stopwords PT-BR
2. Exemplo: "como faço para acessar a plataforma" → `["acessar", "plataforma"]`
3. Chama `KnowledgePort.search(query=keywords_joined, threshold=0.55, top_k=5)`
4. Se achou: vai para `answer`. Senão: `attempt=4`, vai para `ask_context`

### Nó `ask_context`

1. Envia mensagem pedindo contexto: *"Me conta um pouco mais sobre o que você tá precisando, assim consigo te ajudar melhor 😊"*
2. Seta `state.context_requested = True`
3. Aguarda resposta do aluno (próxima mensagem retoma em `search_directed`)

### Nó `search_directed`

1. Concatena `enriched_query = f"{original_query} {student_context}"`
2. Chama `KnowledgePort.search(query=enriched_query, threshold=0.55, top_k=5)`
3. Se achou: vai para `answer`. Senão: vai para `persist_no_result` → `escalate`

### Nó `answer`

1. Monta resposta com base nos chunks encontrados via LLM
2. Prompt inclui os chunks + regras de comunicação (max 300 chars, informal, etc. — aplicado pelo Response Composer)
3. Envia via `ChatNexoClient.send_message(...)`

### Nó `persist_no_result`

1. Registra em `kb_usage_logs` com `result_count = 0`
2. Permite ao time identificar lacunas na KB

### Nó `escalate`

1. `ChatNexoClient.transfer_to_human(reason="knowledge_not_found")`

---

## 5. Componentes

### `SynonymExpander` (`application/kb/synonym_expander.py`)

```python
SYNONYMS: dict[str, list[str]] = {
    "acessar": ["entrar", "logar", "fazer login", "entrar no sistema"],
    "senha": ["palavra-chave", "credencial", "password"],
    "curso": ["treinamento", "aula", "conteúdo", "material"],
    # ... 160+ termos — ver CQ-K01
}

class SynonymExpander:
    def expand(self, query: str) -> str:
        # substitui cada termo por (termo | sinônimo1 | sinônimo2 ...)
        ...
```

> **TODO — CQ-K01:** Consolidar lista completa de 160+ termos e sinônimos com a equipe da G2.

### `KeywordExtractor` (`application/kb/keyword_extractor.py`)

```python
class KeywordExtractor:
    def extract(self, query: str) -> list[str]:
        # tokeniza, remove stopwords PT-BR, retorna tokens relevantes
        ...
```

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

Implementação concreta fica em `application/kb/search.py` (spec ⑥), que chama `chunk_repo.similarity_search()` com pgvector.

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

### Unitários (`tests/unit/capabilities/test_knowledge.py`)

| Teste | Cenário |
|-------|---------|
| `test_exact_match_succeeds` | Tentativa 1 encontra → responde |
| `test_synonym_expansion_succeeds` | T1 falha, T2 (sinônimos) encontra → responde |
| `test_keyword_extraction_succeeds` | T1+T2 falham, T3 (keywords) encontra → responde |
| `test_directed_search_with_context` | T1+T2+T3 falham, pede contexto, T4 encontra → responde |
| `test_all_attempts_exhausted_escalates` | 4 tentativas falham → handoff + log |
| `test_synonym_expander_basic` | "acessar" → expande com "entrar, logar, fazer login" |
| `test_keyword_extractor_removes_stopwords` | "como faço para acessar" → `["acessar"]` |
| `test_persist_no_result_log` | Query sem resultado registrada em `kb_usage_logs` |

### Integração (`tests/integration/test_knowledge_flow.py`)

- KB pré-populada (via fixtures) com chunks conhecidos
- Valida busca com threshold 0.55
- Valida fluxo completo: pergunta → 3 tentativas → ask_context → directed search
- Valida `kb_usage_logs` registrado em queries sem resultado

---

## 10. Requisitos Funcionais

| ID | Requisito |
|----|-----------|
| `RF-K01` | Intent Router classifica `intent = knowledge` para perguntas gerais/técnicas. |
| `RF-K02` | Tentativa 1: busca com palavras exatas do aluno, threshold 0.55 (PRD 7.4). |
| `RF-K03` | Tentativa 2: expansão de sinônimos (160+ termos). |
| `RF-K04` | Tentativa 3: extração de keywords (remove stopwords PT-BR). |
| `RF-K05` | Tentativa 4: pede contexto objetivo ao aluno → busca direcionada com contexto. |
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
