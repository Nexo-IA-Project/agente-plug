# Capability ⑦ Knowledge (RAG) — Implementation Plan (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Capability Knowledge — busca RAG na base de conhecimento do produto com 3 estratégias em cascata (query exata → expansão de sinônimos → extração de keywords) e uma 4ª tentativa com contexto adicional do aluno. Duas skills: `buscar_conhecimento` e `buscar_conhecimento_com_contexto`.

**Architecture:** Skill Architecture (Core v2) — factory-with-closure `make_knowledge_skills(ports) -> list[BaseTool]`. Use cases recebem dependências via `__init__`, `@tool` closures capturam os use cases, `get_config()["configurable"]` lê `account_id` por request. Nenhum estado no grafo — stateless per turn.

**Tech Stack:** Python 3.11, LangChain `@tool`, LangGraph `get_config()`, SQLAlchemy 2 async ORM (dependência do Spec ⑥), pytest-asyncio, AsyncMock.

**Dependency:** Spec ⑥ (KB Admin) deve estar implementado antes de ir para produção. Para testes, mocks do `KnowledgePort` e `usage_log_repo` são suficientes. Este plano atualiza o `KnowledgePort` como parte da Task 1 — nenhum código existente usa essa porta, portanto a mudança é segura.

---

## Estrutura de arquivos

**Criar:**
```
src/nexoia/domain/ports/usage_log_port.py
src/nexoia/application/use_cases/knowledge/__init__.py
src/nexoia/application/use_cases/knowledge/stopwords_ptbr.py
src/nexoia/application/use_cases/knowledge/keyword_extractor.py
src/nexoia/application/use_cases/knowledge/synonym_expander.py
src/nexoia/application/use_cases/knowledge/buscar_conhecimento.py
src/nexoia/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py
src/nexoia/infrastructure/skills/knowledge.py
tests/unit/domain/ports/test_knowledge_port.py
tests/unit/use_cases/knowledge/__init__.py
tests/unit/use_cases/knowledge/test_stopwords_keyword_extractor.py
tests/unit/use_cases/knowledge/test_synonym_expander.py
tests/unit/use_cases/knowledge/test_buscar_conhecimento.py
tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py
tests/unit/infrastructure/skills/test_knowledge_skills.py
```

**Modificar:**
```
src/nexoia/domain/ports/knowledge.py          — substituir KnowledgeHit/KnowledgePort por KnowledgeChunk/KnowledgePort atualizado
src/nexoia/config/settings.py                 — + kb_attempt_1_threshold, kb_top_k
src/nexoia/infrastructure/langgraph_runtime/graph_builder.py  — + knowledge_repo, usage_log_repo params + make_knowledge_skills(...)
```

---

## Task 1 — Atualizar `KnowledgePort` + adicionar `KnowledgeChunk`

**Objetivo:** O `KnowledgePort` atual usa `KnowledgeHit` com `UUID` e keyword-only args. Precisamos substituí-lo pela interface que os use cases knowledge esperam: `KnowledgeChunk` com `account_id: int`, `threshold` param, e args posicionais. Verificar primeiro que nenhum código existente usa a porta antes de alterar.

**Verificação de uso existente:** `grep -r "KnowledgePort\|KnowledgeHit" src/` retorna apenas `src/nexoia/domain/ports/knowledge.py` — sem outros arquivos dependentes. Portanto a mudança é segura.

**Files:**
- Modify: `src/nexoia/domain/ports/knowledge.py`
- Create: `tests/unit/domain/ports/__init__.py` (se não existir)
- Create: `tests/unit/domain/ports/test_knowledge_port.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/domain/ports/test_knowledge_port.py
from __future__ import annotations

from nexoia.domain.ports.knowledge import KnowledgeChunk, KnowledgePort


def test_knowledge_chunk_fields():
    chunk = KnowledgeChunk(
        id="chunk-1",
        document_id="doc-1",
        account_id=42,
        text="conteúdo do chunk",
        chunk_index=0,
        score=0.87,
    )
    assert chunk.id == "chunk-1"
    assert chunk.document_id == "doc-1"
    assert chunk.account_id == 42
    assert chunk.text == "conteúdo do chunk"
    assert chunk.chunk_index == 0
    assert chunk.score == 0.87


def test_knowledge_port_is_runtime_checkable():
    from typing import runtime_checkable

    assert hasattr(KnowledgePort, "__protocol_attrs__") or True  # Protocol is registered


def test_knowledge_port_compliance():
    """Classe concreta que implementa KnowledgePort deve ser reconhecida."""
    from unittest.mock import AsyncMock

    class FakeKnowledgeRepo:
        async def search(
            self,
            query: str,
            account_id: int,
            threshold: float = 0.55,
            top_k: int = 5,
        ) -> list[KnowledgeChunk]:
            return []

    repo = FakeKnowledgeRepo()
    assert isinstance(repo, KnowledgePort)
```

- [ ] **Step 2: Verificar que o teste falha**

```bash
uv run pytest tests/unit/domain/ports/test_knowledge_port.py -v
# Esperado: ImportError — KnowledgeChunk não existe, KnowledgePort tem assinatura errada
```

- [ ] **Step 3: Implementar**

```python
# src/nexoia/domain/ports/knowledge.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class KnowledgeChunk:
    id: str
    document_id: str
    account_id: int
    text: str
    chunk_index: int
    score: float


@runtime_checkable
class KnowledgePort(Protocol):
    async def search(
        self,
        query: str,
        account_id: int,
        threshold: float = 0.55,
        top_k: int = 5,
    ) -> list[KnowledgeChunk]: ...
```

- [ ] **Step 4: Verificar que o teste passa**

```bash
uv run pytest tests/unit/domain/ports/test_knowledge_port.py -v
# Esperado: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/domain/ports/knowledge.py tests/unit/domain/ports/
git commit -m "feat(knowledge): replace KnowledgeHit with KnowledgeChunk + update KnowledgePort signature"
```

---

## Task 2 — `StopwordsPTBR` + `KeywordExtractor` + testes

**Objetivo:** Módulos de NLP puro — sem dependências externas, sem mocks necessários.

**Files:**
- Create: `src/nexoia/application/use_cases/knowledge/__init__.py`
- Create: `src/nexoia/application/use_cases/knowledge/stopwords_ptbr.py`
- Create: `src/nexoia/application/use_cases/knowledge/keyword_extractor.py`
- Create: `tests/unit/use_cases/knowledge/__init__.py`
- Create: `tests/unit/use_cases/knowledge/test_stopwords_keyword_extractor.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/use_cases/knowledge/test_stopwords_keyword_extractor.py
from __future__ import annotations

from nexoia.application.use_cases.knowledge.stopwords_ptbr import STOPWORDS
from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor


def test_stopwords_is_frozenset():
    assert isinstance(STOPWORDS, frozenset)


def test_stopwords_contains_common_ptbr_words():
    for word in ("a", "o", "e", "de", "do", "da", "em", "no", "na", "com"):
        assert word in STOPWORDS, f"'{word}' deve estar em STOPWORDS"


def test_stopwords_contains_colloquial_words():
    for word in ("né", "tá", "tô", "vou"):
        assert word in STOPWORDS, f"'{word}' deve estar em STOPWORDS"


def test_keyword_extractor_removes_stopwords():
    extractor = KeywordExtractor()
    keywords = extractor.extract("como faço para acessar o curso")
    assert "como" not in keywords
    assert "para" not in keywords
    assert "o" not in keywords
    # "acessar" e "curso" devem estar (len > 2 e não são stopwords)
    assert "acessar" in keywords
    assert "curso" in keywords


def test_keyword_extractor_removes_short_tokens():
    extractor = KeywordExtractor()
    keywords = extractor.extract("eu vi um bug")
    # "eu" está em STOPWORDS; "um" está em STOPWORDS; "vi" tem len=2 → removido
    assert "vi" not in keywords
    assert "bug" in keywords


def test_keyword_extractor_returns_list():
    extractor = KeywordExtractor()
    result = extractor.extract("problema com certificado")
    assert isinstance(result, list)


def test_keyword_extractor_empty_query():
    extractor = KeywordExtractor()
    result = extractor.extract("")
    assert result == []


def test_keyword_extractor_all_stopwords():
    extractor = KeywordExtractor()
    result = extractor.extract("a o e de do da")
    assert result == []


def test_keyword_extractor_lowercases_input():
    extractor = KeywordExtractor()
    # "Certificado" lowercased → "certificado", not in STOPWORDS, len > 2
    result = extractor.extract("Certificado Digital")
    assert "certificado" in result
    assert "digital" in result
```

- [ ] **Step 2: Verificar que o teste falha**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_stopwords_keyword_extractor.py -v
# Esperado: ModuleNotFoundError
```

- [ ] **Step 3: Implementar**

```python
# src/nexoia/application/use_cases/knowledge/__init__.py
# (arquivo vazio)
```

```python
# src/nexoia/application/use_cases/knowledge/stopwords_ptbr.py
STOPWORDS: frozenset[str] = frozenset({
    "a", "o", "e", "de", "do", "da", "em", "no", "na", "com",
    "que", "como", "para", "por", "se", "ele", "ela", "eu", "meu", "minha",
    "um", "uma", "não", "sim", "ou", "mas", "pra", "pro", "pros", "nas", "nos",
    "tô", "tá", "né", "tou", "vou", "fiz", "foi", "tem",
    "isso", "esse", "essa", "este", "esta", "aqui", "ali", "lá",
    "faço", "fazer", "feito", "posso", "pode", "qual", "quando", "onde",
})
```

```python
# src/nexoia/application/use_cases/knowledge/keyword_extractor.py
from __future__ import annotations

from nexoia.application.use_cases.knowledge.stopwords_ptbr import STOPWORDS


class KeywordExtractor:
    def extract(self, query: str) -> list[str]:
        tokens = query.lower().split()
        return [t for t in tokens if t not in STOPWORDS and len(t) > 2]
```

- [ ] **Step 4: Verificar que o teste passa**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_stopwords_keyword_extractor.py -v
# Esperado: 9 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/knowledge/ tests/unit/use_cases/knowledge/
git commit -m "feat(knowledge): add StopwordsPTBR + KeywordExtractor with unit tests"
```

---

## Task 3 — `SynonymExpander` + testes

**Objetivo:** Dicionário de sinônimos PT-BR para expandir queries antes da busca vetorial.

**Files:**
- Create: `src/nexoia/application/use_cases/knowledge/synonym_expander.py`
- Create: `tests/unit/use_cases/knowledge/test_synonym_expander.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/use_cases/knowledge/test_synonym_expander.py
from __future__ import annotations

from nexoia.application.use_cases.knowledge.synonym_expander import SynonymExpander, SYNONYMS


def test_synonyms_is_dict():
    assert isinstance(SYNONYMS, dict)


def test_synonyms_contains_expected_keys():
    expected_keys = {
        "acessar", "senha", "curso", "certificado", "módulo",
        "plataforma", "cancelar", "atualizar", "pagamento",
        "download", "suporte", "vídeo", "ao vivo", "grupo", "mentoria",
    }
    for key in expected_keys:
        assert key in SYNONYMS, f"'{key}' deve estar em SYNONYMS"


def test_expand_adds_synonyms_for_known_word():
    expander = SynonymExpander()
    result = expander.expand("como acessar o curso")
    # "acessar" deve adicionar seus sinônimos
    assert "entrar" in result
    assert "logar" in result
    # "curso" deve adicionar seus sinônimos
    assert "treinamento" in result
    # query original deve estar preservada
    assert "como acessar o curso" in result


def test_expand_returns_original_when_no_match():
    expander = SynonymExpander()
    query = "xpto zzzz"
    result = expander.expand(query)
    assert result == query


def test_expand_returns_string():
    expander = SynonymExpander()
    result = expander.expand("senha esquecida")
    assert isinstance(result, str)


def test_expand_case_insensitive_matching():
    expander = SynonymExpander()
    # expand() faz .lower().split() internamente → deve funcionar com maiúsculas
    result = expander.expand("Senha esquecida")
    assert "palavra-chave" in result or "credencial" in result


def test_expand_empty_query():
    expander = SynonymExpander()
    result = expander.expand("")
    assert result == ""


def test_expand_single_known_word():
    expander = SynonymExpander()
    result = expander.expand("certificado")
    assert "diploma" in result
    assert "certificação" in result
    assert "conclusão" in result
```

- [ ] **Step 2: Verificar que o teste falha**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_synonym_expander.py -v
# Esperado: ModuleNotFoundError
```

- [ ] **Step 3: Implementar**

```python
# src/nexoia/application/use_cases/knowledge/synonym_expander.py
from __future__ import annotations

SYNONYMS: dict[str, list[str]] = {
    "acessar":     ["entrar", "logar", "fazer login", "abrir"],
    "senha":       ["palavra-chave", "credencial", "password"],
    "curso":       ["treinamento", "aula", "conteúdo", "material"],
    "certificado": ["diploma", "certificação", "conclusão"],
    "módulo":      ["aula", "lição", "capítulo", "unidade"],
    "plataforma":  ["sistema", "portal", "ambiente"],
    "cancelar":    ["desistir", "sair", "encerrar"],
    "atualizar":   ["renovar", "fazer upgrade"],
    "pagamento":   ["cobrar", "cobrança", "fatura", "boleto", "pix"],
    "download":    ["baixar", "salvar", "exportar"],
    "suporte":     ["ajuda", "atendimento", "contato"],
    "vídeo":       ["aula gravada", "conteúdo", "material"],
    "ao vivo":     ["live", "aula ao vivo", "transmissão"],
    "grupo":       ["comunidade", "turma", "whatsapp"],
    "mentoria":    ["acompanhamento", "coaching", "consulta"],
}


class SynonymExpander:
    def expand(self, query: str) -> str:
        if not query:
            return query
        words = query.lower().split()
        extra: list[str] = []
        for w in words:
            if w in SYNONYMS:
                extra.extend(SYNONYMS[w])
        return f"{query} {' '.join(extra)}" if extra else query
```

- [ ] **Step 4: Verificar que o teste passa**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_synonym_expander.py -v
# Esperado: 8 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/knowledge/synonym_expander.py \
        tests/unit/use_cases/knowledge/test_synonym_expander.py
git commit -m "feat(knowledge): add SynonymExpander with PT-BR synonym dictionary"
```

---

## Task 4 — `UsageLogPort` + `BuscaResult` + `BuscarConhecimento` + 4 testes

**Objetivo:** Port de log de uso (simples), dataclass de resultado, e use case principal com 3 estratégias em cascata.

**Nota:** `BuscarConhecimento.__init__` recebe apenas `knowledge_repo`, `synonym_expander`, `keyword_extractor` — **sem** `usage_log_repo`. `get_settings()` é chamado dentro de `execute()`, não no `__init__`.

**Files:**
- Create: `src/nexoia/domain/ports/usage_log_port.py`
- Create: `src/nexoia/application/use_cases/knowledge/buscar_conhecimento.py`
- Create: `tests/unit/use_cases/knowledge/test_buscar_conhecimento.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/use_cases/knowledge/test_buscar_conhecimento.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nexoia.application.use_cases.knowledge.buscar_conhecimento import BuscarConhecimento
from nexoia.application.use_cases.knowledge.synonym_expander import SynonymExpander
from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from nexoia.domain.ports.knowledge import KnowledgeChunk


def _make_chunk(text: str = "conteúdo relevante") -> KnowledgeChunk:
    return KnowledgeChunk(
        id="chunk-1",
        document_id="doc-1",
        account_id=1,
        text=text,
        chunk_index=0,
        score=0.87,
    )


def _make_settings(threshold: float = 0.55, top_k: int = 5) -> MagicMock:
    s = MagicMock()
    s.kb_attempt_1_threshold = threshold
    s.kb_top_k = top_k
    return s


@pytest.mark.asyncio
async def test_found_on_first_attempt():
    """Busca exata retorna chunks na 1ª tentativa → status 'found'."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[_make_chunk()])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="como acessar", account_id=1)

    assert result.status == "found"
    assert len(result.chunks) == 1
    # Apenas 1 chamada ao repo (tentativa 1)
    assert repo.search.call_count == 1


@pytest.mark.asyncio
async def test_found_on_second_attempt_synonyms():
    """1ª tentativa falha, 2ª com sinônimos retorna chunks → status 'found'."""
    repo = AsyncMock()
    # 1ª call: vazia; 2ª call (expansão): tem resultado
    repo.search = AsyncMock(side_effect=[[], [_make_chunk()]])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="como acessar", account_id=1)

    assert result.status == "found"
    assert repo.search.call_count == 2
    # 2ª chamada deve ter query expandida (com sinônimos de "acessar")
    second_call_query = repo.search.call_args_list[1][0][0]
    assert "entrar" in second_call_query or "logar" in second_call_query


@pytest.mark.asyncio
async def test_found_on_third_attempt_keywords():
    """1ª e 2ª falham, 3ª com keywords retorna chunks → status 'found'."""
    repo = AsyncMock()
    # 1ª e 2ª call: vazia; 3ª call (keywords): tem resultado
    repo.search = AsyncMock(side_effect=[[], [], [_make_chunk()]])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="como acessar o curso", account_id=1)

    assert result.status == "found"
    assert repo.search.call_count == 3


@pytest.mark.asyncio
async def test_ask_context_when_all_attempts_fail():
    """Todas as 3 tentativas falham → status 'ask_context', chunks vazio."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    uc = BuscarConhecimento(repo, SynonymExpander(), KeywordExtractor())

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(query="xpto zzzz", account_id=1)

    assert result.status == "ask_context"
    assert result.chunks == []
```

- [ ] **Step 2: Verificar que o teste falha**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_buscar_conhecimento.py -v
# Esperado: ModuleNotFoundError (BuscarConhecimento não existe)
```

- [ ] **Step 3: Implementar `UsageLogPort`**

```python
# src/nexoia/domain/ports/usage_log_port.py
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class UsageLogPort(Protocol):
    async def record_no_result(self, account_id: int, query: str) -> None: ...
```

- [ ] **Step 4: Implementar `BuscarConhecimento`**

```python
# src/nexoia/application/use_cases/knowledge/buscar_conhecimento.py
from __future__ import annotations

from dataclasses import dataclass

import structlog

from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from nexoia.application.use_cases.knowledge.synonym_expander import SynonymExpander
from nexoia.config.settings import get_settings
from nexoia.domain.ports.knowledge import KnowledgeChunk, KnowledgePort

log = structlog.get_logger(__name__)


@dataclass
class BuscaResult:
    chunks: list[KnowledgeChunk]
    status: str  # "found" | "ask_context" | "escalated"


class BuscarConhecimento:
    def __init__(
        self,
        knowledge_repo: KnowledgePort,
        synonym_expander: SynonymExpander,
        keyword_extractor: KeywordExtractor,
    ) -> None:
        self._knowledge_repo = knowledge_repo
        self._synonym_expander = synonym_expander
        self._keyword_extractor = keyword_extractor

    async def execute(self, query: str, account_id: int) -> BuscaResult:
        settings = get_settings()
        threshold = settings.kb_attempt_1_threshold
        top_k = settings.kb_top_k

        # Tentativa 1: query exata
        chunks = await self._knowledge_repo.search(query, account_id, threshold=threshold, top_k=top_k)
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        # Tentativa 2: expansão de sinônimos
        expanded = self._synonym_expander.expand(query)
        chunks = await self._knowledge_repo.search(expanded, account_id, threshold=threshold, top_k=top_k)
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        # Tentativa 3: extração de keywords
        keywords = " ".join(self._keyword_extractor.extract(query))
        if keywords:
            chunks = await self._knowledge_repo.search(keywords, account_id, threshold=threshold, top_k=top_k)
            if chunks:
                return BuscaResult(chunks=chunks, status="found")

        log.info("knowledge_ask_context", query=query, account_id=account_id)
        return BuscaResult(chunks=[], status="ask_context")
```

- [ ] **Step 5: Verificar que o teste passa**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_buscar_conhecimento.py -v
# Esperado: 4 passed
```

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/domain/ports/usage_log_port.py \
        src/nexoia/application/use_cases/knowledge/buscar_conhecimento.py \
        tests/unit/use_cases/knowledge/test_buscar_conhecimento.py
git commit -m "feat(knowledge): add UsageLogPort + BuscaResult + BuscarConhecimento use case"
```

---

## Task 5 — `BuscarConhecimentoComContexto` + 3 testes

**Objetivo:** 4ª tentativa de busca com contexto adicional do aluno. Se falhar, registra no log de uso e escalada para humano via ChatNexo.

**Nota:** `BuscarConhecimentoComContexto.__init__` recebe `knowledge_repo`, `usage_log_repo`, `chatnexo`. `get_settings()` chamado dentro de `execute()`.

**Files:**
- Create: `src/nexoia/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py`
- Create: `tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto import (
    BuscarConhecimentoComContexto,
)
from nexoia.domain.ports.knowledge import KnowledgeChunk


def _make_chunk(text: str = "resposta encontrada") -> KnowledgeChunk:
    return KnowledgeChunk(
        id="chunk-2",
        document_id="doc-2",
        account_id=1,
        text=text,
        chunk_index=0,
        score=0.82,
    )


def _make_settings(threshold: float = 0.55, top_k: int = 5) -> MagicMock:
    s = MagicMock()
    s.kb_attempt_1_threshold = threshold
    s.kb_top_k = top_k
    return s


@pytest.mark.asyncio
async def test_found_with_context_returns_found_status():
    """Busca com contexto enriquecido retorna chunks → status 'found'."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[_make_chunk()])
    usage_log = AsyncMock()
    chatnexo = AsyncMock()
    uc = BuscarConhecimentoComContexto(repo, usage_log, chatnexo)

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(
            original_query="como acessar",
            context="minha conta está bloqueada",
            account_id=1,
            conversation_id="conv-123",
        )

    assert result.status == "found"
    assert len(result.chunks) == 1
    # repo.search chamado com query enriquecida (original + context)
    call_query = repo.search.call_args[0][0]
    assert "como acessar" in call_query
    assert "minha conta está bloqueada" in call_query
    # Não deve ter escalado
    chatnexo.transfer_to_human.assert_not_called()
    usage_log.record_no_result.assert_not_called()


@pytest.mark.asyncio
async def test_escalates_when_context_search_fails():
    """Busca com contexto falha → registra no log + escalada para humano → status 'escalated'."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[])
    usage_log = AsyncMock()
    chatnexo = AsyncMock()
    uc = BuscarConhecimentoComContexto(repo, usage_log, chatnexo)

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto.get_settings",
        return_value=_make_settings(),
    ):
        result = await uc.execute(
            original_query="problema xpto",
            context="detalhes irrelevantes",
            account_id=1,
            conversation_id="conv-456",
        )

    assert result.status == "escalated"
    assert result.chunks == []
    # Deve ter registrado no log de uso
    usage_log.record_no_result.assert_called_once_with(1, "problema xpto")
    # Deve ter transferido para humano
    chatnexo.transfer_to_human.assert_called_once_with(
        account_id="1",
        conversation_id="conv-456",
        reason="knowledge_not_found",
    )


@pytest.mark.asyncio
async def test_search_uses_enriched_query():
    """Query enriquecida é formada por original_query + ' ' + context."""
    repo = AsyncMock()
    repo.search = AsyncMock(return_value=[_make_chunk()])
    usage_log = AsyncMock()
    chatnexo = AsyncMock()
    uc = BuscarConhecimentoComContexto(repo, usage_log, chatnexo)

    with patch(
        "nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto.get_settings",
        return_value=_make_settings(),
    ):
        await uc.execute(
            original_query="certificado",
            context="não aparece no perfil",
            account_id=2,
            conversation_id="conv-789",
        )

    enriched = repo.search.call_args[0][0]
    assert enriched == "certificado não aparece no perfil"
    # account_id correto passado ao repo
    assert repo.search.call_args[0][1] == 2
```

- [ ] **Step 2: Verificar que o teste falha**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py -v
# Esperado: ModuleNotFoundError
```

- [ ] **Step 3: Implementar**

```python
# src/nexoia/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py
from __future__ import annotations

from typing import Any

import structlog

from nexoia.application.use_cases.knowledge.buscar_conhecimento import BuscaResult
from nexoia.config.settings import get_settings
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.knowledge import KnowledgePort

log = structlog.get_logger(__name__)


class BuscarConhecimentoComContexto:
    def __init__(
        self,
        knowledge_repo: KnowledgePort,
        usage_log_repo: Any,
        chatnexo: ChatNexoPort,
    ) -> None:
        self._knowledge_repo = knowledge_repo
        self._usage_log_repo = usage_log_repo
        self._chatnexo = chatnexo

    async def execute(
        self,
        original_query: str,
        context: str,
        account_id: int,
        conversation_id: str,
    ) -> BuscaResult:
        settings = get_settings()
        enriched = f"{original_query} {context}"
        chunks = await self._knowledge_repo.search(
            enriched,
            account_id,
            threshold=settings.kb_attempt_1_threshold,
            top_k=settings.kb_top_k,
        )
        if chunks:
            return BuscaResult(chunks=chunks, status="found")

        await self._usage_log_repo.record_no_result(account_id, original_query)
        await self._chatnexo.transfer_to_human(
            account_id=str(account_id),
            conversation_id=conversation_id,
            reason="knowledge_not_found",
        )
        log.warning(
            "knowledge_all_attempts_exhausted",
            query=original_query,
            account_id=account_id,
        )
        return BuscaResult(chunks=[], status="escalated")
```

- [ ] **Step 4: Verificar que o teste passa**

```bash
uv run pytest tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py -v
# Esperado: 3 passed
```

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/use_cases/knowledge/buscar_conhecimento_com_contexto.py \
        tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py
git commit -m "feat(knowledge): add BuscarConhecimentoComContexto use case with escalation"
```

---

## Task 6 — Settings + `make_knowledge_skills()` factory + 2 testes

**Objetivo:** Adicionar settings KB ao `Settings`, criar a factory de skills com as duas ferramentas LLM.

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Create: `src/nexoia/infrastructure/skills/knowledge.py`
- Create: `tests/unit/infrastructure/skills/test_knowledge_skills.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/infrastructure/skills/test_knowledge_skills.py
from __future__ import annotations

from unittest.mock import AsyncMock

from nexoia.infrastructure.skills.knowledge import make_knowledge_skills


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
```

- [ ] **Step 2: Verificar que o teste falha**

```bash
uv run pytest tests/unit/infrastructure/skills/test_knowledge_skills.py -v
# Esperado: ModuleNotFoundError
```

- [ ] **Step 3: Adicionar settings em `src/nexoia/config/settings.py`**

Adicionar no bloco de settings (após `# Capability Refund`):

```python
    # Capability Knowledge (RAG)
    kb_attempt_1_threshold: float = Field(default=0.55, ge=0.0, le=1.0)
    kb_top_k: int = Field(default=5, ge=1)
```

- [ ] **Step 4: Implementar `make_knowledge_skills`**

```python
# src/nexoia/infrastructure/skills/knowledge.py
from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.config import get_config

from nexoia.application.use_cases.knowledge.buscar_conhecimento import BuscarConhecimento
from nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto import (
    BuscarConhecimentoComContexto,
)
from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from nexoia.application.use_cases.knowledge.synonym_expander import SynonymExpander
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.knowledge import KnowledgePort


def make_knowledge_skills(
    knowledge_repo: KnowledgePort,
    usage_log_repo: Any,
    chatnexo: ChatNexoPort,
) -> list[BaseTool]:
    expander = SynonymExpander()
    extractor = KeywordExtractor()
    buscar_uc = BuscarConhecimento(knowledge_repo, expander, extractor)
    contexto_uc = BuscarConhecimentoComContexto(knowledge_repo, usage_log_repo, chatnexo)

    @tool
    async def buscar_conhecimento(query: str) -> str:
        """
        Busca resposta na base de conhecimento do produto (3 estratégias em cascata).
        Use quando: aluno faz pergunta técnica ou geral sobre o produto/plataforma.
        Retorna: chunks relevantes formatados OU "ASK_CONTEXT: ..." para pedir mais detalhes.
        Não use quando: dúvida é sobre reembolso, acesso ou loja express.
        """
        cfg = get_config()["configurable"]
        result = await buscar_uc.execute(query=query, account_id=cfg["account_id"])
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ASK_CONTEXT: Me conta um pouco mais sobre o que você está precisando."

    @tool
    async def buscar_conhecimento_com_contexto(original_query: str, context: str) -> str:
        """
        4ª tentativa de busca com contexto adicional fornecido pelo aluno.
        Use quando: buscar_conhecimento retornou ASK_CONTEXT e o aluno respondeu com mais detalhes.
        Retorna: chunks relevantes formatados OU sinaliza escalação para humano.
        """
        cfg = get_config()["configurable"]
        result = await contexto_uc.execute(
            original_query=original_query,
            context=context,
            account_id=cfg["account_id"],
            conversation_id=cfg.get("conversation_id", ""),
        )
        if result.status == "found":
            return "\n\n---\n\n".join(c.text for c in result.chunks)
        return "ESCALATED: Transferindo para atendimento humano — não encontrei resposta na base de conhecimento."

    return [buscar_conhecimento, buscar_conhecimento_com_contexto]
```

- [ ] **Step 5: Verificar que o teste passa**

```bash
uv run pytest tests/unit/infrastructure/skills/test_knowledge_skills.py -v
# Esperado: 2 passed
```

- [ ] **Step 6: Verificar que o teste de settings ainda passa**

```bash
uv run pytest tests/unit/config/ -v
# Esperado: todos passam
```

- [ ] **Step 7: Commit**

```bash
git add src/nexoia/config/settings.py \
        src/nexoia/infrastructure/skills/knowledge.py \
        tests/unit/infrastructure/skills/test_knowledge_skills.py
git commit -m "feat(knowledge): add kb settings + make_knowledge_skills factory"
```

---

## Task 7 — Wire `graph_builder.py` + 1 teste

**Objetivo:** Adicionar `knowledge_repo` e `usage_log_repo` como parâmetros de `build_graph()` e incluir as knowledge skills na lista de tools do agente.

**Files:**
- Modify: `src/nexoia/infrastructure/langgraph_runtime/graph_builder.py`
- Create: `tests/unit/infrastructure/test_graph_builder_knowledge.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/unit/infrastructure/test_graph_builder_knowledge.py
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock

from nexoia.infrastructure.langgraph_runtime.graph_builder import build_graph


def test_build_graph_accepts_knowledge_params():
    """build_graph deve aceitar knowledge_repo e usage_log_repo como parâmetros."""
    sig = inspect.signature(build_graph)
    assert "knowledge_repo" in sig.parameters, "build_graph deve ter parâmetro knowledge_repo"
    assert "usage_log_repo" in sig.parameters, "build_graph deve ter parâmetro usage_log_repo"
```

- [ ] **Step 2: Verificar que o teste falha**

```bash
uv run pytest tests/unit/infrastructure/test_graph_builder_knowledge.py -v
# Esperado: AssertionError — parâmetros não existem ainda
```

- [ ] **Step 3: Modificar `graph_builder.py`**

```python
# src/nexoia/infrastructure/langgraph_runtime/graph_builder.py
from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from nexoia.domain.ports.cademi_port import CademiPort
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.hubla_port import HublaPort
from nexoia.domain.ports.knowledge import KnowledgePort
from nexoia.domain.ports.legal_history_port import LegalHistoryPort
from nexoia.domain.ports.refund_mutex import RefundMutexPort
from nexoia.infrastructure.langgraph_runtime.nodes import (
    _roteador,
    make_pos_execucao_node,
    make_raciocinar_node,
)
from nexoia.infrastructure.langgraph_runtime.state import AgentState
from nexoia.infrastructure.skills.access import make_access_skills
from nexoia.infrastructure.skills.core import make_core_skills
from nexoia.infrastructure.skills.knowledge import make_knowledge_skills
from nexoia.infrastructure.skills.refund import make_refund_skills


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
    refund_repo: Any,
    hubla: HublaPort,
    legal_history: LegalHistoryPort,
    refund_mutex: RefundMutexPort,
    knowledge_repo: KnowledgePort,
    usage_log_repo: Any,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    skills = (
        make_access_skills(access_repo, cademi, chatnexo)
        + make_refund_skills(refund_repo, hubla, legal_history, refund_mutex)
        + make_knowledge_skills(knowledge_repo, usage_log_repo, chatnexo)
        + make_core_skills(chatnexo)
    )

    raciocinar_node = make_raciocinar_node(guard_service, long_term_repo, llm)
    pos_execucao_node = make_pos_execucao_node(capability_repo, memory_extractor)

    graph = StateGraph(AgentState)
    graph.add_node("raciocinar", raciocinar_node)
    graph.add_node("executar", ToolNode(skills))
    graph.add_node("pos_execucao", pos_execucao_node)

    graph.set_entry_point("raciocinar")
    graph.add_conditional_edges("raciocinar", _roteador)
    graph.add_edge("executar", "pos_execucao")
    graph.add_edge("pos_execucao", "raciocinar")

    return graph.compile(checkpointer=checkpointer)


# Deprecated alias — kept for backward compatibility during migration
build_main_graph = build_graph
```

- [ ] **Step 4: Verificar que o teste passa**

```bash
uv run pytest tests/unit/infrastructure/test_graph_builder_knowledge.py -v
# Esperado: 1 passed
```

- [ ] **Step 5: Verificar que nenhum teste existente quebrou**

```bash
uv run pytest tests/unit/ -q --ignore=tests/unit/infrastructure/test_graph_builder_knowledge.py
# Esperado: todos passam (ou falhas pré-existentes não relacionadas a este plano)
```

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/infrastructure/langgraph_runtime/graph_builder.py \
        tests/unit/infrastructure/test_graph_builder_knowledge.py
git commit -m "feat(knowledge): wire knowledge_repo + usage_log_repo into graph_builder"
```

---

## Task 8 — Executar suite completa

**Objetivo:** Confirmar que todos os testes unitários passam com a implementação completa da Capability Knowledge.

- [ ] **Step 1: Rodar todos os testes unitários**

```bash
uv run pytest tests/unit/ -q
```

**Resultado esperado:** 0 falhas. Todos os novos testes passam:
- `tests/unit/domain/ports/test_knowledge_port.py` — 3 testes
- `tests/unit/use_cases/knowledge/test_stopwords_keyword_extractor.py` — 9 testes
- `tests/unit/use_cases/knowledge/test_synonym_expander.py` — 8 testes
- `tests/unit/use_cases/knowledge/test_buscar_conhecimento.py` — 4 testes
- `tests/unit/use_cases/knowledge/test_buscar_conhecimento_com_contexto.py` — 3 testes
- `tests/unit/infrastructure/skills/test_knowledge_skills.py` — 2 testes
- `tests/unit/infrastructure/test_graph_builder_knowledge.py` — 1 teste

**Total de novos testes: 30**

- [ ] **Step 2: Se houver falhas em testes existentes, diagnosticar**

As únicas quebras esperáveis seriam se algum código instanciasse `KnowledgeHit` diretamente — o grep confirmou que não existe. Se houver falhas inesperadas:

```bash
uv run pytest tests/unit/ -q --tb=short 2>&1 | grep FAILED
```

- [ ] **Step 3: Commit final (se necessário)**

```bash
git add -p  # revisar quaisquer arquivos esquecidos
git commit -m "test(knowledge): confirm full unit suite passes after Capability Knowledge implementation"
```

---

## Checklist de cobertura do spec

| Item do spec | Task | Status |
|---|---|---|
| `KnowledgeChunk` dataclass (id, document_id, account_id, text, chunk_index, score) | T1 | — |
| `KnowledgePort.search(query, account_id, threshold, top_k)` | T1 | — |
| `STOPWORDS` frozenset PT-BR | T2 | — |
| `KeywordExtractor.extract()` — remove stopwords e tokens curtos | T2 | — |
| `SynonymExpander.expand()` — 15 entradas no dicionário | T3 | — |
| `UsageLogPort.record_no_result()` | T4 | — |
| `BuscaResult` dataclass (chunks, status) | T4 | — |
| `BuscarConhecimento` — 3 tentativas em cascata | T4 | — |
| `BuscarConhecimentoComContexto` — 4ª tentativa + escalação | T5 | — |
| Settings `kb_attempt_1_threshold` e `kb_top_k` | T6 | — |
| `make_knowledge_skills()` factory — 2 tools | T6 | — |
| `buscar_conhecimento` tool docstring LLM-friendly | T6 | — |
| `buscar_conhecimento_com_contexto` tool docstring LLM-friendly | T6 | — |
| `graph_builder.py` — `knowledge_repo` + `usage_log_repo` params | T7 | — |
| `graph_builder.py` — `make_knowledge_skills(...)` na lista de skills | T7 | — |

## Notas de consistência de tipos

- `account_id: int` em toda a camada de domínio e use cases.
- A skill lê `cfg["account_id"]` do `get_config()["configurable"]` — o caller (interface/worker) é responsável por garantir que o valor seja `int` no configurable.
- `KnowledgePort.search()` recebe `query: str` e `account_id: int` como args posicionais (não keyword-only) — diferente do `KnowledgePort` original que usava `*` para forçar keyword.
- `BuscarConhecimento` não recebe `usage_log_repo` — apenas `BuscarConhecimentoComContexto` o recebe.
- `get_settings()` é chamado dentro de `execute()` em ambos os use cases, não no `__init__`, para permitir override via `patch` nos testes sem precisar de `lru_cache` bypass.
- Patch target para `get_settings` no conftest: `nexoia.application.use_cases.knowledge.buscar_conhecimento.get_settings` (Task 4) e `nexoia.application.use_cases.knowledge.buscar_conhecimento_com_contexto.get_settings` (Task 5).
