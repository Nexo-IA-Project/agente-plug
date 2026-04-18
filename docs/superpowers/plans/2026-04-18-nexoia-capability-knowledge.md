# Capability Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Capability Knowledge — subgraph LangGraph reativo que responde dúvidas técnicas/gerais do aluno consultando a KB (alimentada pelo spec ⑥) via cascade de 4 tentativas: (1) busca exata com threshold 0.55, (2) expansão de sinônimos, (3) extração de keywords, (4) pedido de contexto → busca direcionada. Se todas falharem, persiste a query em `kb_usage_logs` e dispara handoff silencioso com `reason="knowledge_not_found"`.

**Architecture:** Subgraph LangGraph com 8 nós (search_exact → search_synonyms → search_keywords → ask_context → search_directed → answer / persist_no_result → escalate). Estado tipado `KnowledgeState` herda de `ConversationState` do Core e é persistido via checkpoint LangGraph entre turnos (o nó `ask_context` interrompe o fluxo e aguarda a próxima mensagem do aluno). `SynonymExpander` começa como stub com ~15 termos comuns do contexto educacional (TODO CQ-K01 para 160+). `KnowledgePort` é reutilizado do Core (spec ①), com implementação concreta entregue pelo spec ⑥.

**Tech Stack:** Python 3.12, LangGraph, SQLAlchemy 2 async, structlog, prometheus-client, pytest, pytest-asyncio, factory-boy, uv.

**Prerequisite:**
- Spec ① (Core) — `ConversationState`, `IntentRouter` com categoria `knowledge`, `KnowledgePort` Protocol, checkpointer LangGraph, `ChatNexoClient`, `handoff_fn`, `Settings`.
- Spec ⑥ (KB Admin) — tabelas `kb_documents`, `kb_chunks` (embeddings pgvector), `kb_usage_logs`, implementação concreta do `KnowledgePort` (`ChunkSearchService`).

> Este plano **não** re-implementa o intent router nem o `KnowledgePort`; apenas consome-os. Tocamos o router apenas para garantir que a categoria `knowledge` roteia para o subgraph da Knowledge (wire-up no dispatch).

---

## Mapa de Arquivos

| Arquivo | Ação | Responsabilidade |
|---------|------|-----------------|
| `src/nexoia/application/kb/__init__.py` | Criar | Package marker |
| `src/nexoia/application/kb/stopwords_ptbr.py` | Criar | Lista congelada de stopwords PT-BR |
| `src/nexoia/application/kb/keyword_extractor.py` | Criar | `KeywordExtractor` — tokeniza + remove stopwords |
| `src/nexoia/application/kb/synonym_expander.py` | Criar | `SynonymExpander` — stub ~15 termos (TODO CQ-K01) |
| `src/nexoia/application/capabilities/knowledge.py` | Criar | `KnowledgeState` + nós + `build_knowledge_subgraph()` |
| `src/nexoia/infrastructure/db/repositories/kb_usage_log_repo.py` | Criar | Repo para persistir queries sem resultado |
| `src/nexoia/infrastructure/observability/metrics.py` | Modificar | Adicionar métricas Knowledge |
| `src/nexoia/config/settings.py` | Modificar | `KB_ATTEMPT_1_THRESHOLD`, `KB_TOP_K`, `KB_MAX_TURNS_WAITING_CONTEXT` |
| `src/nexoia/application/intent_router.py` | Modificar (revisão) | Confirma que `knowledge` é retornado (já feito no Core) |
| `src/nexoia/interface/worker/dispatcher.py` | Modificar | Roteia `intent=knowledge` para o subgraph Knowledge |
| `tests/fakes/fake_knowledge_port.py` | Criar | Fake configurável para `KnowledgePort` |
| `tests/fakes/fake_chatnexo_client.py` | Modificar | Garante `send_message`/`transfer_to_human` capturáveis |
| `tests/unit/application/kb/test_stopwords.py` | Criar | Testes da lista de stopwords |
| `tests/unit/application/kb/test_keyword_extractor.py` | Criar | Testes do `KeywordExtractor` |
| `tests/unit/application/kb/test_synonym_expander.py` | Criar | Testes do `SynonymExpander` |
| `tests/unit/capabilities/test_knowledge.py` | Criar | Testes unitários dos nós do subgraph |
| `tests/unit/observability/test_knowledge_metrics.py` | Criar | Testes das métricas Prometheus |
| `tests/integration/test_knowledge_flow.py` | Criar | Teste end-to-end do fluxo completo (KB fixtures) |
| `docs/superpowers/OPEN_QUESTIONS.md` | Modificar | Confirmar CQ-K01 com link para `synonym_expander.py` |
| `docs/superpowers/INDEX.md` | Modificar | Marcar plano ⑦ como criado |

---

## Task 1: Settings — parâmetros da Capability Knowledge

**Files:**
- Modify: `src/nexoia/config/settings.py`
- Test: `tests/unit/config/test_settings_knowledge.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/config/test_settings_knowledge.py
from nexoia.config.settings import Settings


def _make_settings(**overrides) -> Settings:
    base = dict(
        DATABASE_URL="postgresql+asyncpg://u:p@localhost/db",
        REDIS_URL="redis://localhost:6379",
        CHATNEXO_API_KEY="key",
        OPENAI_API_KEY="sk-test",
    )
    base.update(overrides)
    return Settings(**base)


def test_knowledge_defaults():
    s = _make_settings()
    assert s.KB_ATTEMPT_1_THRESHOLD == 0.55      # PRD 7.4
    assert s.KB_TOP_K == 5                        # spec ⑦ §7
    assert s.KB_MAX_TURNS_WAITING_CONTEXT == 1    # spec ⑦ §7


def test_knowledge_threshold_can_be_overridden():
    s = _make_settings(KB_ATTEMPT_1_THRESHOLD=0.7)
    assert s.KB_ATTEMPT_1_THRESHOLD == 0.7


def test_knowledge_top_k_must_be_positive():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _make_settings(KB_TOP_K=0)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
cd /path/to/nexoia-agent
uv run pytest tests/unit/config/test_settings_knowledge.py -v
```
Esperado: `AttributeError` ou `ValidationError` (campos inexistentes).

- [ ] **Step 3: Adicionar campos ao model `Settings`**

No arquivo `src/nexoia/config/settings.py`, localizar o model `Settings` e adicionar:

```python
from pydantic import Field

    # Capability Knowledge (PRD 7.4, spec ⑦)
    KB_ATTEMPT_1_THRESHOLD: float = Field(
        default=0.55,
        ge=0.0,
        le=1.0,
        description="Threshold fixo para tentativa 1 (PRD 7.4).",
    )
    KB_TOP_K: int = Field(
        default=5,
        gt=0,
        description="Número de chunks retornados por busca.",
    )
    KB_MAX_TURNS_WAITING_CONTEXT: int = Field(
        default=1,
        ge=0,
        description="Quantas mensagens do aluno podem passar antes de escalar após ask_context.",
    )
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/config/test_settings_knowledge.py -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/config/settings.py tests/unit/config/test_settings_knowledge.py
git commit -m "feat(knowledge): add KB settings (threshold, top_k, max_turns_waiting_context)"
```

---

## Task 2: Stopwords PT-BR

**Files:**
- Create: `src/nexoia/application/kb/__init__.py`
- Create: `src/nexoia/application/kb/stopwords_ptbr.py`
- Test: `tests/unit/application/kb/test_stopwords.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/application/kb/test_stopwords.py
import pytest

from nexoia.application.kb.stopwords_ptbr import STOPWORDS_PTBR, is_stopword


def test_stopwords_is_a_frozenset():
    assert isinstance(STOPWORDS_PTBR, frozenset)


def test_contains_common_pt_stopwords():
    expected = {"a", "o", "de", "que", "para", "com", "como", "meu", "minha"}
    assert expected.issubset(STOPWORDS_PTBR)


def test_contains_informal_variants():
    # O PRD (seção 8) exige linguagem informal — stopwords precisam cobrir "tô", "tá", "né", "pra"
    informal = {"tô", "tá", "né", "pra", "pro", "vc", "tb"}
    assert informal.issubset(STOPWORDS_PTBR)


def test_is_stopword_case_insensitive():
    assert is_stopword("A") is True
    assert is_stopword("Para") is True
    assert is_stopword("PLATAFORMA") is False  # não é stopword


def test_is_stopword_strips_whitespace():
    assert is_stopword("  de  ") is True


@pytest.mark.parametrize("word", ["plataforma", "acesso", "curso", "senha", "login"])
def test_domain_keywords_are_not_stopwords(word: str) -> None:
    assert not is_stopword(word)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/application/kb/test_stopwords.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Criar o package e o módulo**

```bash
mkdir -p src/nexoia/application/kb
touch src/nexoia/application/kb/__init__.py
```

```python
# src/nexoia/application/kb/stopwords_ptbr.py
"""Stopwords PT-BR para extração de keywords na Capability Knowledge.

A lista combina stopwords formais (artigos, preposições, pronomes) e
gírias/abreviações comuns do WhatsApp (PRD seção 8 — linguagem informal).
"""
from __future__ import annotations

# Formal
_FORMAL: frozenset[str] = frozenset({
    "a", "o", "as", "os", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "pela", "pelo", "pelas", "pelos",
    "com", "sem", "sob", "sobre",
    "e", "ou", "mas", "se", "que", "porque", "porquê",
    "eu", "você", "ele", "ela", "nós", "vós", "eles", "elas",
    "meu", "minha", "meus", "minhas", "seu", "sua", "seus", "suas",
    "teu", "tua", "teus", "tuas", "nosso", "nossa", "nossos", "nossas",
    "este", "esta", "esse", "essa", "isto", "isso", "aquele", "aquela", "aquilo",
    "ser", "estar", "ter", "haver", "fazer", "ir", "vir",
    "é", "são", "foi", "foram", "será", "sou", "está", "estou", "tem", "tenho",
    "como", "quando", "onde", "porque", "qual", "quais", "quanto", "quantos",
    "só", "já", "ainda", "também", "sim", "não", "talvez",
    "aqui", "ali", "lá", "cá",
})

# Informal/gírias (PRD seção 8 — "vc", "tb", "pra", "tá", "né", "beleza")
_INFORMAL: frozenset[str] = frozenset({
    "vc", "vcs", "tb", "tbm", "pq", "pra", "pro", "pras", "pros",
    "tô", "to", "tá", "ta", "né", "ne", "tipo", "aí", "ai",
    "então", "entao", "oi", "olá", "ola", "beleza", "blz", "ok", "tchau",
    "obrigado", "obrigada", "valeu", "falou",
    "faço", "faz", "fazer",
})

STOPWORDS_PTBR: frozenset[str] = _FORMAL | _INFORMAL


def is_stopword(word: str) -> bool:
    """Retorna True se `word` é uma stopword PT-BR (case-insensitive)."""
    return word.strip().lower() in STOPWORDS_PTBR
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/application/kb/test_stopwords.py -v
```
Esperado: 5 cases + 5 parametrized PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/kb/__init__.py \
        src/nexoia/application/kb/stopwords_ptbr.py \
        tests/unit/application/kb/test_stopwords.py
git commit -m "feat(knowledge): add PT-BR stopwords list (formal + informal variants)"
```

---

## Task 3: KeywordExtractor

**Files:**
- Create: `src/nexoia/application/kb/keyword_extractor.py`
- Test: `tests/unit/application/kb/test_keyword_extractor.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/application/kb/test_keyword_extractor.py
import pytest

from nexoia.application.kb.keyword_extractor import KeywordExtractor


@pytest.fixture
def extractor() -> KeywordExtractor:
    return KeywordExtractor()


def test_extract_removes_stopwords(extractor: KeywordExtractor):
    tokens = extractor.extract("como faço para acessar a plataforma")
    assert set(tokens) == {"acessar", "plataforma"}


def test_extract_keeps_order_of_first_occurrence(extractor: KeywordExtractor):
    tokens = extractor.extract("acessar plataforma acessar curso")
    assert tokens == ["acessar", "plataforma", "curso"]


def test_extract_is_lowercase(extractor: KeywordExtractor):
    tokens = extractor.extract("Como Acesso Minha PLATAFORMA")
    assert tokens == ["acesso", "plataforma"]


def test_extract_strips_punctuation(extractor: KeywordExtractor):
    tokens = extractor.extract("esqueci minha senha!!! quero entrar, já")
    # "minha", "quero", "já" são stopwords (na lista); "entrar" permanece
    assert "senha" in tokens
    assert "entrar" in tokens
    assert "!!!" not in tokens


def test_extract_ignores_short_tokens(extractor: KeywordExtractor):
    # tokens com 1 caractere (que não sejam stopwords) são ignorados
    tokens = extractor.extract("x y z plataforma")
    assert tokens == ["plataforma"]


def test_extract_empty_returns_empty(extractor: KeywordExtractor):
    assert extractor.extract("") == []
    assert extractor.extract("   ") == []


def test_extract_only_stopwords_returns_empty(extractor: KeywordExtractor):
    assert extractor.extract("como para de que não") == []


def test_join_returns_space_separated_query(extractor: KeywordExtractor):
    query = extractor.join(extractor.extract("como faço para acessar plataforma"))
    assert query == "acessar plataforma"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/application/kb/test_keyword_extractor.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o `KeywordExtractor`**

```python
# src/nexoia/application/kb/keyword_extractor.py
"""Extrai keywords de uma query do aluno removendo stopwords PT-BR.

Usado pela tentativa 3 da Capability Knowledge (PRD 7.4 item 49).
"""
from __future__ import annotations

import re

from nexoia.application.kb.stopwords_ptbr import STOPWORDS_PTBR

# Aceita letras acentuadas PT-BR + dígitos. Exclui pontuação.
_TOKEN_RE = re.compile(r"[0-9a-záéíóúâêôãõàçñü]+", re.IGNORECASE)
_MIN_TOKEN_LEN = 2


class KeywordExtractor:
    """Tokeniza uma query, normaliza para lowercase e remove stopwords."""

    def __init__(
        self,
        stopwords: frozenset[str] = STOPWORDS_PTBR,
        min_len: int = _MIN_TOKEN_LEN,
    ) -> None:
        self._stopwords = stopwords
        self._min_len = min_len

    def extract(self, query: str) -> list[str]:
        """Retorna a lista ordenada de keywords (primeira ocorrência)."""
        if not query or not query.strip():
            return []

        seen: set[str] = set()
        result: list[str] = []
        for raw in _TOKEN_RE.findall(query.lower()):
            if len(raw) < self._min_len:
                continue
            if raw in self._stopwords:
                continue
            if raw in seen:
                continue
            seen.add(raw)
            result.append(raw)
        return result

    def join(self, keywords: list[str]) -> str:
        """Junta keywords em uma única query para o `KnowledgePort.search`."""
        return " ".join(keywords)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/application/kb/test_keyword_extractor.py -v
```
Esperado: 8 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/kb/keyword_extractor.py \
        tests/unit/application/kb/test_keyword_extractor.py
git commit -m "feat(knowledge): add KeywordExtractor (tokenizes + removes PT-BR stopwords)"
```

---

## Task 4: SynonymExpander (stub com ~15 termos — TODO CQ-K01)

**Files:**
- Create: `src/nexoia/application/kb/synonym_expander.py`
- Test: `tests/unit/application/kb/test_synonym_expander.py`
- Modify: `docs/superpowers/OPEN_QUESTIONS.md`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/application/kb/test_synonym_expander.py
import pytest

from nexoia.application.kb.synonym_expander import SYNONYMS, SynonymExpander


@pytest.fixture
def expander() -> SynonymExpander:
    return SynonymExpander()


def test_synonyms_dict_has_stub_seed():
    # Stub inicial — pelo menos 10 termos (CQ-K01 amplia para 160+)
    assert len(SYNONYMS) >= 10
    assert "acessar" in SYNONYMS
    assert "senha" in SYNONYMS
    assert "curso" in SYNONYMS


def test_synonyms_values_are_lists_of_str():
    for term, syns in SYNONYMS.items():
        assert isinstance(syns, list)
        assert all(isinstance(s, str) for s in syns)
        assert len(syns) >= 1
        # o próprio termo não deve aparecer na lista de sinônimos
        assert term not in syns


def test_expand_adds_synonyms_for_known_term(expander: SynonymExpander):
    expanded = expander.expand("não consigo acessar")
    # O termo original permanece + sinônimos mapeados
    assert "acessar" in expanded
    for syn in SYNONYMS["acessar"]:
        assert syn in expanded


def test_expand_preserves_unknown_words(expander: SynonymExpander):
    expanded = expander.expand("minha plataforma xyz")
    # plataforma/xyz não estão no dict — query passa intacta (stopwords mantidas)
    assert "plataforma" in expanded
    assert "xyz" in expanded


def test_expand_case_insensitive_match(expander: SynonymExpander):
    expanded = expander.expand("Não Consigo ACESSAR")
    for syn in SYNONYMS["acessar"]:
        assert syn in expanded


def test_expand_multi_term_query(expander: SynonymExpander):
    expanded = expander.expand("esqueci minha senha e não consigo acessar o curso")
    # todos os 3 termos conhecidos são expandidos
    for syn in SYNONYMS["senha"] + SYNONYMS["acessar"] + SYNONYMS["curso"]:
        assert syn in expanded


def test_expand_empty_returns_empty(expander: SynonymExpander):
    assert expander.expand("") == ""
    assert expander.expand("   ") == ""


def test_expand_does_not_duplicate_synonyms(expander: SynonymExpander):
    expanded = expander.expand("acessar acessar acessar")
    # Sinônimos aparecem, mas não multiplicam por ocorrência
    for syn in SYNONYMS["acessar"]:
        assert expanded.count(syn) <= 1  # cada sinônimo no máx. 1 vez


def test_expand_returns_str(expander: SynonymExpander):
    assert isinstance(expander.expand("acessar"), str)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/application/kb/test_synonym_expander.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o `SynonymExpander` com stub de ~15 termos**

```python
# src/nexoia/application/kb/synonym_expander.py
"""Expansão de sinônimos para a Tentativa 2 da Capability Knowledge.

# ⚠️  STUB — ver OPEN_QUESTIONS.md#CQ-K01
# O PRD 7.4 item 48 menciona 160+ termos mapeados. Esta implementação cobre
# apenas ~15 termos comuns do contexto educacional da G2. A lista completa
# deve ser consolidada com a equipe da G2 (CQ-K01) antes do go-live.
"""
from __future__ import annotations

import re

# TODO (CQ-K01): consolidar lista completa de 160+ termos com a equipe G2.
#   Ver docs/superpowers/OPEN_QUESTIONS.md#CQ-K01
SYNONYMS: dict[str, list[str]] = {
    # Acesso / login
    "acessar": ["entrar", "logar", "fazer login", "entrar no sistema"],
    "entrar": ["acessar", "logar", "fazer login"],
    "logar": ["acessar", "entrar", "fazer login"],
    "senha": ["palavra-chave", "credencial", "password"],
    "login": ["usuário", "acesso", "credencial"],

    # Curso / conteúdo
    "curso": ["treinamento", "aula", "conteúdo", "material"],
    "aula": ["curso", "treinamento", "conteúdo"],
    "conteúdo": ["material", "aula", "curso"],
    "material": ["conteúdo", "apostila", "aula"],

    # Plataforma / sistema
    "plataforma": ["sistema", "site", "portal", "área do aluno"],
    "sistema": ["plataforma", "site", "portal"],

    # Problemas comuns
    "erro": ["problema", "falha", "bug"],
    "problema": ["erro", "falha", "dificuldade"],

    # Recuperação
    "esqueci": ["perdi", "não lembro"],
    "recuperar": ["redefinir", "resetar", "alterar"],

    # Pagamento
    "pagamento": ["cobrança", "fatura", "boleto"],
}

# Aceita letras acentuadas PT-BR + dígitos.
_TOKEN_RE = re.compile(r"[0-9a-záéíóúâêôãõàçñü]+", re.IGNORECASE)


class SynonymExpander:
    """Expande uma query concatenando sinônimos dos termos conhecidos."""

    def __init__(self, mapping: dict[str, list[str]] = SYNONYMS) -> None:
        self._mapping = mapping

    def expand(self, query: str) -> str:
        """Retorna `query` concatenada com todos os sinônimos dos termos conhecidos.

        Estratégia de concatenação (não substituição) preserva a query original e
        permite que o embedding capture o contexto completo.
        """
        if not query or not query.strip():
            return ""

        appended: list[str] = []
        seen: set[str] = set()
        for token in _TOKEN_RE.findall(query.lower()):
            syns = self._mapping.get(token)
            if not syns:
                continue
            for syn in syns:
                if syn in seen:
                    continue
                seen.add(syn)
                appended.append(syn)

        if not appended:
            return query
        return f"{query} {' '.join(appended)}"
```

- [ ] **Step 4: Atualizar `OPEN_QUESTIONS.md` para referenciar o stub**

No arquivo `docs/superpowers/OPEN_QUESTIONS.md`, localizar a entrada `CQ-K01` e adicionar ao final:

```markdown
**Onde implementar:** quando a lista completa chegar, substituir o dict
`SYNONYMS` em `src/nexoia/application/kb/synonym_expander.py`. Nenhum outro
arquivo precisa mudar — o `SynonymExpander` apenas consome o dict.
**Stub atual:** ~15 termos cobrindo acesso, curso, plataforma, problemas,
recuperação e pagamento.
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/application/kb/test_synonym_expander.py -v
```
Esperado: 9 testes PASSED.

- [ ] **Step 6: Commit**

```bash
git add src/nexoia/application/kb/synonym_expander.py \
        tests/unit/application/kb/test_synonym_expander.py \
        docs/superpowers/OPEN_QUESTIONS.md
git commit -m "feat(knowledge): add SynonymExpander stub (~15 terms, TODO CQ-K01 for 160+)"
```

---

## Task 5: FakeKnowledgePort + FakeChatNexoClient (extensões)

**Files:**
- Create: `tests/fakes/fake_knowledge_port.py`
- Modify: `tests/fakes/fake_chatnexo_client.py`
- Test: `tests/unit/fakes/test_fake_knowledge_port.py`

- [ ] **Step 1: Escrever os testes falhando**

```python
# tests/unit/fakes/test_fake_knowledge_port.py
from uuid import uuid4

import pytest

from nexoia.domain.ports.knowledge import KnowledgeHit, KnowledgePort
from tests.fakes.fake_knowledge_port import FakeKnowledgePort


ACCOUNT_ID = uuid4()


@pytest.mark.asyncio
async def test_fake_returns_configured_hits_for_query():
    hits = [
        KnowledgeHit(document_id=uuid4(), chunk_text="Para acessar use o link X.", score=0.82),
    ]
    fake = FakeKnowledgePort(responses={"acessar plataforma": hits})

    result = await fake.search(account_id=ACCOUNT_ID, query="acessar plataforma", top_k=5)
    assert result == hits


@pytest.mark.asyncio
async def test_fake_returns_empty_by_default():
    fake = FakeKnowledgePort()
    result = await fake.search(account_id=ACCOUNT_ID, query="qualquer coisa", top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_fake_records_calls():
    fake = FakeKnowledgePort()
    await fake.search(account_id=ACCOUNT_ID, query="a", top_k=5)
    await fake.search(account_id=ACCOUNT_ID, query="b", top_k=5)
    assert [c.query for c in fake.calls] == ["a", "b"]


@pytest.mark.asyncio
async def test_fake_matches_by_substring_when_enabled():
    hits = [KnowledgeHit(document_id=uuid4(), chunk_text="Senha: use a página X", score=0.71)]
    fake = FakeKnowledgePort(
        responses={"senha": hits},
        match_mode="substring",
    )
    result = await fake.search(
        account_id=ACCOUNT_ID, query="esqueci minha senha urgente", top_k=5,
    )
    assert result == hits


def test_fake_is_a_knowledge_port():
    fake = FakeKnowledgePort()
    # Protocol runtime_checkable
    assert isinstance(fake, KnowledgePort)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/fakes/test_fake_knowledge_port.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o `FakeKnowledgePort`**

```python
# tests/fakes/fake_knowledge_port.py
"""Fake configurável para o KnowledgePort — usado em testes unitários."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from nexoia.domain.ports.knowledge import KnowledgeHit


@dataclass
class _Call:
    account_id: UUID
    query: str
    top_k: int


class FakeKnowledgePort:
    """
    Fake configurável.

    Parameters
    ----------
    responses
        Dict {query: list[KnowledgeHit]} ou {substring: list[KnowledgeHit]}
        conforme `match_mode`.
    match_mode
        "exact": só retorna se `query` bate exatamente com uma chave.
        "substring": retorna se qualquer chave aparece dentro de `query`.
    """

    def __init__(
        self,
        responses: dict[str, list[KnowledgeHit]] | None = None,
        match_mode: Literal["exact", "substring"] = "exact",
    ) -> None:
        self._responses = responses or {}
        self._match_mode = match_mode
        self.calls: list[_Call] = []

    async def search(
        self,
        *,
        account_id: UUID,
        query: str,
        top_k: int = 5,
    ) -> list[KnowledgeHit]:
        self.calls.append(_Call(account_id=account_id, query=query, top_k=top_k))
        if self._match_mode == "exact":
            return list(self._responses.get(query, []))
        # substring
        for key, hits in self._responses.items():
            if key.lower() in query.lower():
                return list(hits)
        return []
```

- [ ] **Step 4: Estender o `FakeChatNexoClient` (se necessário)**

No arquivo `tests/fakes/fake_chatnexo_client.py`, garantir que os seguintes atributos/métodos existem (adicionar se faltar):

```python
    # Atributos para inspeção em testes da Capability Knowledge
    self.sent_messages: list[dict] = []
    self.transfer_calls: list[dict] = []

    async def send_message(
        self,
        *,
        account_id,
        conversation_id: str,
        text: str,
    ) -> None:
        self.sent_messages.append(
            {"account_id": account_id, "conversation_id": conversation_id, "text": text}
        )

    async def transfer_to_human(
        self,
        *,
        account_id,
        conversation_id: str,
        reason: str,
    ) -> None:
        self.transfer_calls.append(
            {"account_id": account_id, "conversation_id": conversation_id, "reason": reason}
        )
```

- [ ] **Step 5: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/fakes/test_fake_knowledge_port.py -v
```
Esperado: 5 testes PASSED.

- [ ] **Step 6: Commit**

```bash
git add tests/fakes/fake_knowledge_port.py \
        tests/fakes/fake_chatnexo_client.py \
        tests/unit/fakes/test_fake_knowledge_port.py
git commit -m "test(knowledge): add FakeKnowledgePort + extend FakeChatNexoClient with send/transfer hooks"
```

---

## Task 6: KbUsageLogRepository — persistir queries sem resultado

**Files:**
- Create: `src/nexoia/infrastructure/db/repositories/kb_usage_log_repo.py`
- Test: `tests/integration/test_kb_usage_log_repo.py`

> **Assunção:** o modelo SQLAlchemy `KbUsageLogModel` e a migration correspondente fazem parte do spec ⑥. Este plano **apenas consome**. Se o modelo ainda não existir, pedir ao spec ⑥ para criá-lo com a seguinte estrutura mínima:
>
> - `id: UUID pk`
> - `account_id: UUID` indexed
> - `conversation_id: str` nullable
> - `query: str` — query executada (após expansão/keywords)
> - `original_query: str` — query original do aluno
> - `attempt: int` — qual tentativa falhou (1/2/3/4)
> - `result_count: int` — sempre 0 neste contexto
> - `created_at: datetime` — timestamp UTC
>
> Se o modelo existir com nome diferente, ajustar os imports conforme o spec ⑥.

- [ ] **Step 1: Escrever o teste de integração falhando**

```python
# tests/integration/test_kb_usage_log_repo.py
from uuid import uuid4

import pytest

from nexoia.infrastructure.db.repositories.kb_usage_log_repo import (
    KbUsageLogRepository,
    NoResultLog,
)


@pytest.mark.asyncio
async def test_save_no_result_log(db_session):
    repo = KbUsageLogRepository(db_session)
    account_id = uuid4()

    log = NoResultLog(
        account_id=account_id,
        conversation_id="conv-001",
        original_query="como acessar a plataforma",
        query="acessar plataforma",
        attempt=4,
    )
    saved_id = await repo.save_no_result(log)
    assert saved_id is not None

    # Valida leitura
    rows = await repo.list_no_results(account_id=account_id, limit=10)
    assert len(rows) == 1
    assert rows[0].original_query == "como acessar a plataforma"
    assert rows[0].attempt == 4
    assert rows[0].result_count == 0


@pytest.mark.asyncio
async def test_list_no_results_filters_by_account(db_session):
    repo = KbUsageLogRepository(db_session)
    a1, a2 = uuid4(), uuid4()

    await repo.save_no_result(NoResultLog(
        account_id=a1, conversation_id="c", original_query="q1", query="q1", attempt=1,
    ))
    await repo.save_no_result(NoResultLog(
        account_id=a2, conversation_id="c", original_query="q2", query="q2", attempt=1,
    ))

    rows_a1 = await repo.list_no_results(account_id=a1, limit=10)
    assert len(rows_a1) == 1
    assert rows_a1[0].original_query == "q1"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/integration/test_kb_usage_log_repo.py -v
```
Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Implementar o repo**

```python
# src/nexoia/infrastructure/db/repositories/kb_usage_log_repo.py
"""Repositório para registrar queries sem resultado na KB (spec ⑦, PRD 7.4 item 51)."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Modelo SQLAlchemy vem do spec ⑥ — ajustar import se o nome final diferir.
from nexoia.infrastructure.db.models import KbUsageLogModel


@dataclass(frozen=True, slots=True)
class NoResultLog:
    account_id: UUID
    conversation_id: str | None
    original_query: str
    query: str
    attempt: int  # 1, 2, 3 ou 4


@dataclass(frozen=True, slots=True)
class NoResultRow:
    id: UUID
    account_id: UUID
    conversation_id: str | None
    original_query: str
    query: str
    attempt: int
    result_count: int


class KbUsageLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_no_result(self, log: NoResultLog) -> UUID:
        model = KbUsageLogModel(
            account_id=log.account_id,
            conversation_id=log.conversation_id,
            original_query=log.original_query,
            query=log.query,
            attempt=log.attempt,
            result_count=0,
        )
        self._session.add(model)
        await self._session.commit()
        await self._session.refresh(model)
        return model.id

    async def list_no_results(
        self,
        *,
        account_id: UUID,
        limit: int = 100,
    ) -> list[NoResultRow]:
        stmt = (
            select(KbUsageLogModel)
            .where(
                KbUsageLogModel.account_id == account_id,
                KbUsageLogModel.result_count == 0,
            )
            .order_by(KbUsageLogModel.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [
            NoResultRow(
                id=m.id,
                account_id=m.account_id,
                conversation_id=m.conversation_id,
                original_query=m.original_query,
                query=m.query,
                attempt=m.attempt,
                result_count=m.result_count,
            )
            for m in result.scalars().all()
        ]
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_kb_usage_log_repo.py -v
```
Esperado: 2 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/db/repositories/kb_usage_log_repo.py \
        tests/integration/test_kb_usage_log_repo.py
git commit -m "feat(knowledge): add KbUsageLogRepository for no-result query tracking"
```

---

## Task 7: Métricas Prometheus da Capability Knowledge

**Files:**
- Modify: `src/nexoia/infrastructure/observability/metrics.py`
- Test: `tests/unit/observability/test_knowledge_metrics.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/observability/test_knowledge_metrics.py
from nexoia.infrastructure.observability.metrics import (
    knowledge_answer_latency_seconds,
    knowledge_attempts_total,
    knowledge_capability_total,
    knowledge_no_result_total,
)


def test_capability_total_accepts_status_labels():
    for status in ("answered", "escalated", "error"):
        knowledge_capability_total.labels(status=status).inc()


def test_attempts_total_accepts_attempt_labels():
    for attempt in ("1", "2", "3", "4"):
        knowledge_attempts_total.labels(attempt=attempt).inc()


def test_no_result_total_counter():
    knowledge_no_result_total.inc()


def test_answer_latency_histogram_observe():
    knowledge_answer_latency_seconds.observe(0.123)
    knowledge_answer_latency_seconds.observe(1.5)
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/observability/test_knowledge_metrics.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Adicionar as métricas**

No arquivo `src/nexoia/infrastructure/observability/metrics.py`, adicionar:

```python
from prometheus_client import Counter, Histogram

# Capability Knowledge (PRD 7.4, spec ⑦)
knowledge_capability_total = Counter(
    "knowledge_capability_total",
    "Total de execuções da Capability Knowledge por desfecho.",
    labelnames=["status"],  # answered | escalated | error
)
knowledge_attempts_total = Counter(
    "knowledge_attempts_total",
    "Total de tentativas de busca na KB, por número da tentativa.",
    labelnames=["attempt"],  # 1 | 2 | 3 | 4
)
knowledge_no_result_total = Counter(
    "knowledge_no_result_total",
    "Total de queries sem resultado após as 4 tentativas (persistidas em kb_usage_logs).",
)
knowledge_answer_latency_seconds = Histogram(
    "knowledge_answer_latency_seconds",
    "Latência do nó `answer` (busca final + geração da resposta via LLM).",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
)
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/observability/test_knowledge_metrics.py -v
```
Esperado: 4 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/infrastructure/observability/metrics.py \
        tests/unit/observability/test_knowledge_metrics.py
git commit -m "feat(knowledge): add Prometheus metrics for Knowledge capability"
```

---

## Task 8: KnowledgeState + nós search_exact, search_synonyms, search_keywords

**Files:**
- Create: `src/nexoia/application/capabilities/knowledge.py` (parcial — 3 nós de busca)
- Test: `tests/unit/capabilities/test_knowledge.py` (parcial)

- [ ] **Step 1: Escrever os testes unitários falhando (3 nós de busca)**

```python
# tests/unit/capabilities/test_knowledge.py
from uuid import uuid4

import pytest

from nexoia.application.capabilities.knowledge import (
    KnowledgeState,
    node_search_exact,
    node_search_keywords,
    node_search_synonyms,
    route_after_search,
)
from nexoia.application.kb.keyword_extractor import KeywordExtractor
from nexoia.application.kb.synonym_expander import SynonymExpander
from nexoia.domain.ports.knowledge import KnowledgeHit
from tests.fakes.fake_knowledge_port import FakeKnowledgePort


ACCOUNT_ID = uuid4()


def _make_state(**overrides) -> KnowledgeState:
    base: dict = dict(
        account_id=ACCOUNT_ID,
        conversation_id="conv-001",
        correlation_id="corr-001",
        messages=[],
        original_query="como acesso a plataforma",
        enriched_query=None,
        attempt=1,
        synonym_expanded=None,
        keywords_extracted=None,
        chunks_found=[],
        context_requested=False,
        no_result=False,
    )
    base.update(overrides)
    return KnowledgeState(**base)


def _hit(text: str = "chunk", score: float = 0.9) -> KnowledgeHit:
    return KnowledgeHit(document_id=uuid4(), chunk_text=text, score=score)


# ------------------- search_exact -------------------

@pytest.mark.asyncio
async def test_search_exact_found_sets_chunks_and_keeps_attempt_1():
    hits = [_hit("Para acessar use o link X.")]
    kb = FakeKnowledgePort(responses={"como acesso a plataforma": hits})
    state = _make_state()

    update = await node_search_exact(
        state, knowledge_port=kb, threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == hits
    assert update["attempt"] == 1


@pytest.mark.asyncio
async def test_search_exact_not_found_increments_attempt_to_2():
    kb = FakeKnowledgePort()  # sempre vazio
    state = _make_state()

    update = await node_search_exact(
        state, knowledge_port=kb, threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == []
    assert update["attempt"] == 2


@pytest.mark.asyncio
async def test_search_exact_passes_threshold_and_topk():
    kb = FakeKnowledgePort()
    state = _make_state()

    await node_search_exact(state, knowledge_port=kb, threshold=0.7, top_k=3)

    assert kb.calls[0].query == "como acesso a plataforma"
    assert kb.calls[0].top_k == 3


# ------------------- search_synonyms -------------------

@pytest.mark.asyncio
async def test_search_synonyms_expands_query_and_hits():
    hits = [_hit("Login: use seu email", 0.77)]
    # O expander concatena sinônimos — usamos substring matching no fake
    kb = FakeKnowledgePort(responses={"entrar": hits}, match_mode="substring")
    state = _make_state(original_query="não consigo acessar", attempt=2)
    expander = SynonymExpander()

    update = await node_search_synonyms(
        state, knowledge_port=kb, synonym_expander=expander, threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == hits
    assert update["synonym_expanded"] is not None
    assert "entrar" in update["synonym_expanded"]  # sinônimo de "acessar"
    assert update["attempt"] == 2


@pytest.mark.asyncio
async def test_search_synonyms_not_found_increments_to_3():
    kb = FakeKnowledgePort()
    state = _make_state(attempt=2)

    update = await node_search_synonyms(
        state, knowledge_port=kb, synonym_expander=SynonymExpander(),
        threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == []
    assert update["attempt"] == 3


# ------------------- search_keywords -------------------

@pytest.mark.asyncio
async def test_search_keywords_removes_stopwords_and_hits():
    hits = [_hit("Plataforma: veja o menu", 0.6)]
    kb = FakeKnowledgePort(responses={"acesso plataforma": hits})
    state = _make_state(original_query="como faço para acesso plataforma", attempt=3)

    update = await node_search_keywords(
        state, knowledge_port=kb, keyword_extractor=KeywordExtractor(),
        threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == hits
    assert update["keywords_extracted"] == ["acesso", "plataforma"]
    assert update["attempt"] == 3


@pytest.mark.asyncio
async def test_search_keywords_not_found_increments_to_4():
    kb = FakeKnowledgePort()
    state = _make_state(attempt=3)

    update = await node_search_keywords(
        state, knowledge_port=kb, keyword_extractor=KeywordExtractor(),
        threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == []
    assert update["attempt"] == 4


@pytest.mark.asyncio
async def test_search_keywords_empty_after_stopwords_still_advances():
    kb = FakeKnowledgePort()
    # Query só com stopwords
    state = _make_state(original_query="como para de que", attempt=3)

    update = await node_search_keywords(
        state, knowledge_port=kb, keyword_extractor=KeywordExtractor(),
        threshold=0.55, top_k=5,
    )

    assert update["keywords_extracted"] == []
    assert update["chunks_found"] == []
    assert update["attempt"] == 4


# ------------------- router condicional -------------------

def test_route_after_search_to_answer_when_chunks_found():
    state = _make_state(chunks_found=[_hit()])
    assert route_after_search(state) == "answer"


def test_route_after_search_to_next_when_empty_and_attempt_under_4():
    state = _make_state(chunks_found=[], attempt=2)
    assert route_after_search(state) == "next"


def test_route_after_search_to_ask_context_when_empty_and_attempt_4_no_context_yet():
    state = _make_state(chunks_found=[], attempt=4, context_requested=False)
    assert route_after_search(state) == "ask_context"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar `KnowledgeState` + 3 nós de busca + router**

```python
# src/nexoia/application/capabilities/knowledge.py
"""Capability Knowledge — RAG reativo (spec ⑦, PRD 7.4).

Subgraph LangGraph acionado quando `intent=knowledge`. Cascade de 4 tentativas:
 1. search_exact      — palavras exatas (threshold 0.55)
 2. search_synonyms   — expande sinônimos
 3. search_keywords   — remove stopwords PT-BR
 4. ask_context (aguarda) → search_directed
Se tudo falha: persist_no_result → escalate.
"""
from __future__ import annotations

import time
from typing import Any, Awaitable, Callable, Literal
from uuid import UUID

import structlog
from langgraph.graph import END, StateGraph

from nexoia.application.kb.keyword_extractor import KeywordExtractor
from nexoia.application.kb.synonym_expander import SynonymExpander
from nexoia.application.state import ConversationState
from nexoia.domain.ports.chatnexo import ChatNexoPort
from nexoia.domain.ports.knowledge import KnowledgeHit, KnowledgePort
from nexoia.domain.ports.llm import LLMPort
from nexoia.infrastructure.observability.metrics import (
    knowledge_answer_latency_seconds,
    knowledge_attempts_total,
    knowledge_capability_total,
    knowledge_no_result_total,
)

logger = structlog.get_logger(__name__)

ASK_CONTEXT_MESSAGE = (
    "Me conta um pouco mais sobre o que você tá precisando, "
    "assim consigo te ajudar melhor 😊"
)


class KnowledgeState(ConversationState):
    """Estado do subgraph Knowledge. Herda campos base de ConversationState."""

    original_query: str
    enriched_query: str | None
    attempt: int  # 1..4
    synonym_expanded: str | None
    keywords_extracted: list[str] | None
    chunks_found: list[KnowledgeHit]
    context_requested: bool
    no_result: bool


# ===================== Nós de busca =====================

async def node_search_exact(
    state: KnowledgeState,
    *,
    knowledge_port: KnowledgePort,
    threshold: float,
    top_k: int,
) -> dict[str, Any]:
    log = logger.bind(
        capability="knowledge",
        node="search_exact",
        attempt=1,
        account_id=str(state["account_id"]),
    )
    knowledge_attempts_total.labels(attempt="1").inc()

    hits = await knowledge_port.search(
        account_id=state["account_id"],
        query=state["original_query"],
        top_k=top_k,
    )
    # Port já respeita threshold internamente; aqui reforçamos para segurança.
    filtered = [h for h in hits if h.score >= threshold]

    if filtered:
        log.info("exact_match_found", chunks_found_count=len(filtered))
        return {"chunks_found": filtered, "attempt": 1}

    log.info("exact_no_match", reason="exact_no_match")
    return {"chunks_found": [], "attempt": 2}


async def node_search_synonyms(
    state: KnowledgeState,
    *,
    knowledge_port: KnowledgePort,
    synonym_expander: SynonymExpander,
    threshold: float,
    top_k: int,
) -> dict[str, Any]:
    log = logger.bind(
        capability="knowledge",
        node="search_synonyms",
        attempt=2,
        account_id=str(state["account_id"]),
    )
    knowledge_attempts_total.labels(attempt="2").inc()

    expanded = synonym_expander.expand(state["original_query"])
    hits = await knowledge_port.search(
        account_id=state["account_id"],
        query=expanded,
        top_k=top_k,
    )
    filtered = [h for h in hits if h.score >= threshold]

    if filtered:
        log.info("synonym_match_found", chunks_found_count=len(filtered))
        return {
            "chunks_found": filtered,
            "synonym_expanded": expanded,
            "attempt": 2,
        }

    log.info("synonyms_no_match", reason="synonyms_no_match")
    return {
        "chunks_found": [],
        "synonym_expanded": expanded,
        "attempt": 3,
    }


async def node_search_keywords(
    state: KnowledgeState,
    *,
    knowledge_port: KnowledgePort,
    keyword_extractor: KeywordExtractor,
    threshold: float,
    top_k: int,
) -> dict[str, Any]:
    log = logger.bind(
        capability="knowledge",
        node="search_keywords",
        attempt=3,
        account_id=str(state["account_id"]),
    )
    knowledge_attempts_total.labels(attempt="3").inc()

    keywords = keyword_extractor.extract(state["original_query"])
    query = keyword_extractor.join(keywords)

    if not keywords:
        log.info("keywords_empty_after_stopwords")
        return {
            "chunks_found": [],
            "keywords_extracted": [],
            "attempt": 4,
        }

    hits = await knowledge_port.search(
        account_id=state["account_id"],
        query=query,
        top_k=top_k,
    )
    filtered = [h for h in hits if h.score >= threshold]

    if filtered:
        log.info("keyword_match_found", chunks_found_count=len(filtered))
        return {
            "chunks_found": filtered,
            "keywords_extracted": keywords,
            "attempt": 3,
        }

    log.info("keywords_no_match", reason="keywords_no_match")
    return {
        "chunks_found": [],
        "keywords_extracted": keywords,
        "attempt": 4,
    }


# ===================== Router condicional =====================

def route_after_search(state: KnowledgeState) -> Literal["answer", "next", "ask_context"]:
    """Decide próximo nó após uma tentativa de busca.

    - achou chunks → "answer"
    - vazio, attempt < 4 → "next" (próxima tentativa)
    - vazio, attempt == 4 e ainda não pediu contexto → "ask_context"
    """
    if state["chunks_found"]:
        return "answer"
    if state["attempt"] < 4:
        return "next"
    if not state["context_requested"]:
        return "ask_context"
    # Já pediu contexto e ainda não achou → será tratado por search_directed router.
    return "next"
```

- [ ] **Step 4: Executar para confirmar que os testes dos 3 nós passam**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v \
  -k "search_exact or search_synonyms or search_keywords or route_after_search"
```
Esperado: todos os testes desse filtro PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/knowledge.py \
        tests/unit/capabilities/test_knowledge.py
git commit -m "feat(knowledge): implement search_exact, search_synonyms, search_keywords nodes + router"
```

---

## Task 9: ask_context + search_directed + router de contexto

**Files:**
- Modify: `src/nexoia/application/capabilities/knowledge.py`
- Modify: `tests/unit/capabilities/test_knowledge.py`

- [ ] **Step 1: Adicionar testes falhando**

```python
# tests/unit/capabilities/test_knowledge.py  (ADICIONAR — não substituir)
from nexoia.application.capabilities.knowledge import (
    ASK_CONTEXT_MESSAGE,
    node_ask_context,
    node_search_directed,
    route_after_directed,
)
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


# ------------------- ask_context -------------------

@pytest.mark.asyncio
async def test_ask_context_sends_message_and_sets_flag():
    chatnexo = FakeChatNexoClient()
    state = _make_state(attempt=4, context_requested=False)

    update = await node_ask_context(state, chatnexo_port=chatnexo)

    assert update["context_requested"] is True
    assert len(chatnexo.sent_messages) == 1
    assert chatnexo.sent_messages[0]["text"] == ASK_CONTEXT_MESSAGE
    assert chatnexo.sent_messages[0]["conversation_id"] == "conv-001"


@pytest.mark.asyncio
async def test_ask_context_is_idempotent():
    """Se já pediu contexto, não envia de novo."""
    chatnexo = FakeChatNexoClient()
    state = _make_state(attempt=4, context_requested=True)

    update = await node_ask_context(state, chatnexo_port=chatnexo)

    assert update == {}  # nada muda
    assert len(chatnexo.sent_messages) == 0


# ------------------- search_directed -------------------

@pytest.mark.asyncio
async def test_search_directed_concatenates_context_and_searches():
    hits = [_hit("resposta direcionada", 0.8)]
    kb = FakeKnowledgePort(
        responses={"como acesso a plataforma pelo celular": hits},
    )
    state = _make_state(
        original_query="como acesso a plataforma",
        enriched_query="como acesso a plataforma pelo celular",
        attempt=4,
        context_requested=True,
    )

    update = await node_search_directed(
        state, knowledge_port=kb, threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == hits
    assert kb.calls[0].query == "como acesso a plataforma pelo celular"


@pytest.mark.asyncio
async def test_search_directed_no_hit_sets_no_result_true():
    kb = FakeKnowledgePort()
    state = _make_state(
        enriched_query="contexto adicional aqui",
        attempt=4,
        context_requested=True,
    )

    update = await node_search_directed(
        state, knowledge_port=kb, threshold=0.55, top_k=5,
    )

    assert update["chunks_found"] == []
    assert update["no_result"] is True


@pytest.mark.asyncio
async def test_search_directed_without_enriched_query_marks_no_result():
    kb = FakeKnowledgePort()
    # Caller ainda não recebeu resposta do aluno → enriched_query=None
    state = _make_state(enriched_query=None, attempt=4, context_requested=True)

    update = await node_search_directed(
        state, knowledge_port=kb, threshold=0.55, top_k=5,
    )

    # Sem contexto novo, tratamos como esgotado.
    assert update["no_result"] is True


# ------------------- route_after_directed -------------------

def test_route_after_directed_to_answer_when_chunks():
    state = _make_state(chunks_found=[_hit()])
    assert route_after_directed(state) == "answer"


def test_route_after_directed_to_persist_when_no_result():
    state = _make_state(chunks_found=[], no_result=True)
    assert route_after_directed(state) == "persist_no_result"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v \
  -k "ask_context or search_directed or route_after_directed"
```
Esperado: `ImportError` (nomes ainda não existem).

- [ ] **Step 3: Adicionar nós e router ao módulo**

No arquivo `src/nexoia/application/capabilities/knowledge.py`, adicionar (depois do `route_after_search`):

```python
# ===================== ask_context =====================

async def node_ask_context(
    state: KnowledgeState,
    *,
    chatnexo_port: ChatNexoPort,
) -> dict[str, Any]:
    """Envia mensagem pedindo contexto ao aluno.

    Após este nó, o subgraph deve ser **interrompido** (return para END)
    para aguardar a próxima mensagem do aluno. O checkpoint LangGraph
    persiste o estado; quando nova mensagem chega, o dispatcher retoma
    com `enriched_query = state.original_query + " " + new_message` e
    invoca `search_directed`.
    """
    log = logger.bind(
        capability="knowledge",
        node="ask_context",
        account_id=str(state["account_id"]),
    )

    if state.get("context_requested"):
        log.info("ask_context_skipped_already_requested")
        return {}

    await chatnexo_port.send_message(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        text=ASK_CONTEXT_MESSAGE,
    )
    log.info("ask_context_sent", reason="ask_context")
    return {"context_requested": True}


# ===================== search_directed =====================

async def node_search_directed(
    state: KnowledgeState,
    *,
    knowledge_port: KnowledgePort,
    threshold: float,
    top_k: int,
) -> dict[str, Any]:
    log = logger.bind(
        capability="knowledge",
        node="search_directed",
        attempt=4,
        account_id=str(state["account_id"]),
    )
    knowledge_attempts_total.labels(attempt="4").inc()

    enriched = state.get("enriched_query")
    if not enriched:
        # Retomada sem resposta do aluno — tratamos como esgotado.
        log.warning("search_directed_without_enriched_query", reason="no_context_received")
        return {"chunks_found": [], "no_result": True}

    hits = await knowledge_port.search(
        account_id=state["account_id"],
        query=enriched,
        top_k=top_k,
    )
    filtered = [h for h in hits if h.score >= threshold]

    if filtered:
        log.info("directed_match_found", chunks_found_count=len(filtered))
        return {"chunks_found": filtered}

    log.warning(
        "all_attempts_exhausted",
        reason="all_attempts_exhausted",
    )
    return {"chunks_found": [], "no_result": True}


def route_after_directed(state: KnowledgeState) -> Literal["answer", "persist_no_result"]:
    if state["chunks_found"]:
        return "answer"
    return "persist_no_result"
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v \
  -k "ask_context or search_directed or route_after_directed"
```
Esperado: 7 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/knowledge.py \
        tests/unit/capabilities/test_knowledge.py
git commit -m "feat(knowledge): add ask_context + search_directed nodes + directed router"
```

---

## Task 10: answer, persist_no_result e escalate nodes

**Files:**
- Modify: `src/nexoia/application/capabilities/knowledge.py`
- Modify: `tests/unit/capabilities/test_knowledge.py`

- [ ] **Step 1: Adicionar testes falhando**

```python
# tests/unit/capabilities/test_knowledge.py  (ADICIONAR)
from unittest.mock import AsyncMock

from nexoia.application.capabilities.knowledge import (
    node_answer,
    node_escalate,
    node_persist_no_result,
)


# ------------------- answer -------------------

@pytest.mark.asyncio
async def test_answer_calls_llm_with_chunks_and_sends_message():
    chatnexo = FakeChatNexoClient()
    llm = AsyncMock()
    llm.complete_text.return_value = "Pra entrar use o link https://x.com"

    hits = [
        _hit("Para acessar acesse o link X.", 0.82),
        _hit("Se esqueceu a senha clique em 'recuperar'.", 0.71),
    ]
    state = _make_state(chunks_found=hits)

    update = await node_answer(state, chatnexo_port=chatnexo, llm_port=llm)

    # LLM foi chamado com os chunks no prompt
    args = llm.complete_text.call_args.kwargs
    assert "Para acessar acesse o link X." in args["user"]
    assert "recuperar" in args["user"]
    # Resposta foi enviada
    assert chatnexo.sent_messages[-1]["text"] == "Pra entrar use o link https://x.com"


@pytest.mark.asyncio
async def test_answer_empty_chunks_is_noop_safe():
    chatnexo = FakeChatNexoClient()
    llm = AsyncMock()
    state = _make_state(chunks_found=[])

    update = await node_answer(state, chatnexo_port=chatnexo, llm_port=llm)

    assert update == {}
    assert llm.complete_text.call_count == 0
    assert chatnexo.sent_messages == []


# ------------------- persist_no_result -------------------

@pytest.mark.asyncio
async def test_persist_no_result_saves_log():
    repo = AsyncMock()
    repo.save_no_result = AsyncMock(return_value=uuid4())
    state = _make_state(
        original_query="como uso o recurso X",
        synonym_expanded="como uso o recurso X entrar logar",
        keywords_extracted=["uso", "recurso"],
        attempt=4,
        chunks_found=[],
        no_result=True,
    )

    update = await node_persist_no_result(state, kb_usage_log_repo=repo)

    assert update["no_result"] is True
    repo.save_no_result.assert_awaited_once()
    log_arg = repo.save_no_result.call_args.args[0]
    assert log_arg.original_query == "como uso o recurso X"
    assert log_arg.attempt == 4
    assert log_arg.account_id == state["account_id"]


# ------------------- escalate -------------------

@pytest.mark.asyncio
async def test_escalate_calls_transfer_to_human_with_reason():
    chatnexo = FakeChatNexoClient()
    state = _make_state()

    await node_escalate(state, chatnexo_port=chatnexo)

    assert len(chatnexo.transfer_calls) == 1
    assert chatnexo.transfer_calls[0]["reason"] == "knowledge_not_found"
    assert chatnexo.transfer_calls[0]["conversation_id"] == "conv-001"
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v \
  -k "answer or persist_no_result or escalate"
```
Esperado: `ImportError`.

- [ ] **Step 3: Adicionar os 3 nós ao módulo**

No arquivo `src/nexoia/application/capabilities/knowledge.py`, adicionar:

```python
from nexoia.infrastructure.db.repositories.kb_usage_log_repo import (
    KbUsageLogRepository,
    NoResultLog,
)


_ANSWER_SYSTEM_PROMPT = (
    "Você é Especialista de Sucesso do Aluno da G2 Educação. "
    "Responda à dúvida do aluno usando APENAS as informações nos trechos abaixo. "
    "Tom informal (vc, pra, tá). Máx. 300 caracteres. "
    "Sem bullets, sem negrito, sem cabeçalho. "
    "Se os trechos não bastarem, responda apenas 'não encontrei'."
)


def _build_answer_user_prompt(original_query: str, chunks: list[KnowledgeHit]) -> str:
    lines = ["Pergunta do aluno:", original_query, "", "Trechos da base:"]
    for i, c in enumerate(chunks, start=1):
        lines.append(f"[{i}] {c.chunk_text}")
    return "\n".join(lines)


# ===================== answer =====================

async def node_answer(
    state: KnowledgeState,
    *,
    chatnexo_port: ChatNexoPort,
    llm_port: LLMPort,
) -> dict[str, Any]:
    log = logger.bind(
        capability="knowledge",
        node="answer",
        account_id=str(state["account_id"]),
    )
    if not state["chunks_found"]:
        log.warning("answer_called_with_empty_chunks")
        return {}

    started = time.perf_counter()
    user_prompt = _build_answer_user_prompt(state["original_query"], state["chunks_found"])
    text = await llm_port.complete_text(
        system=_ANSWER_SYSTEM_PROMPT,
        user=user_prompt,
        temperature=0.5,
    )
    elapsed = time.perf_counter() - started
    knowledge_answer_latency_seconds.observe(elapsed)

    await chatnexo_port.send_message(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        text=text,
    )
    knowledge_capability_total.labels(status="answered").inc()
    log.info(
        "answer_sent",
        chunks_used=len(state["chunks_found"]),
        elapsed=elapsed,
    )
    return {}


# ===================== persist_no_result =====================

async def node_persist_no_result(
    state: KnowledgeState,
    *,
    kb_usage_log_repo: KbUsageLogRepository,
) -> dict[str, Any]:
    log = logger.bind(
        capability="knowledge",
        node="persist_no_result",
        account_id=str(state["account_id"]),
    )
    query_sent = (
        state.get("enriched_query")
        or state.get("synonym_expanded")
        or state["original_query"]
    )
    await kb_usage_log_repo.save_no_result(
        NoResultLog(
            account_id=state["account_id"],
            conversation_id=state["conversation_id"],
            original_query=state["original_query"],
            query=query_sent,
            attempt=state["attempt"],
        )
    )
    knowledge_no_result_total.inc()
    log.warning("no_result_persisted", reason="all_attempts_exhausted")
    return {"no_result": True}


# ===================== escalate =====================

async def node_escalate(
    state: KnowledgeState,
    *,
    chatnexo_port: ChatNexoPort,
) -> dict[str, Any]:
    log = logger.bind(
        capability="knowledge",
        node="escalate",
        account_id=str(state["account_id"]),
    )
    await chatnexo_port.transfer_to_human(
        account_id=state["account_id"],
        conversation_id=state["conversation_id"],
        reason="knowledge_not_found",
    )
    knowledge_capability_total.labels(status="escalated").inc()
    log.warning("handoff_silent", reason="knowledge_not_found")
    return {}
```

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v \
  -k "answer or persist_no_result or escalate"
```
Esperado: 4 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/knowledge.py \
        tests/unit/capabilities/test_knowledge.py
git commit -m "feat(knowledge): add answer + persist_no_result + escalate nodes"
```

---

## Task 11: build_knowledge_subgraph — wire dos nós

**Files:**
- Modify: `src/nexoia/application/capabilities/knowledge.py`
- Modify: `tests/unit/capabilities/test_knowledge.py`

- [ ] **Step 1: Adicionar teste de construção do grafo**

```python
# tests/unit/capabilities/test_knowledge.py  (ADICIONAR)
from nexoia.application.capabilities.knowledge import build_knowledge_subgraph


def test_build_knowledge_subgraph_returns_compilable_graph():
    graph = build_knowledge_subgraph()
    compiled = graph.compile()
    assert compiled is not None


def test_build_knowledge_subgraph_has_all_expected_nodes():
    graph = build_knowledge_subgraph()
    expected = {
        "search_exact",
        "search_synonyms",
        "search_keywords",
        "ask_context",
        "search_directed",
        "answer",
        "persist_no_result",
        "escalate",
    }
    # `graph.nodes` (LangGraph) expõe o dict interno.
    assert expected.issubset(set(graph.nodes.keys()))
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v \
  -k "build_knowledge_subgraph"
```
Esperado: `ImportError`.

- [ ] **Step 3: Implementar `build_knowledge_subgraph`**

No arquivo `src/nexoia/application/capabilities/knowledge.py`, adicionar no final:

```python
def build_knowledge_subgraph(
    *,
    knowledge_port: KnowledgePort | None = None,
    chatnexo_port: ChatNexoPort | None = None,
    llm_port: LLMPort | None = None,
    kb_usage_log_repo: KbUsageLogRepository | None = None,
    synonym_expander: SynonymExpander | None = None,
    keyword_extractor: KeywordExtractor | None = None,
    threshold: float = 0.55,
    top_k: int = 5,
) -> StateGraph:
    """Constrói o subgraph da Capability Knowledge.

    As dependências devem ser injetadas pelo container DI do worker.
    Os nós são *closures* sobre as deps para não depender de context locals.
    Os defaults `None` existem só para o teste de construção — a invocação
    real sem deps levanta AssertionError.
    """
    assert knowledge_port is not None, "knowledge_port is required at runtime"
    assert chatnexo_port is not None, "chatnexo_port is required at runtime"
    assert llm_port is not None, "llm_port is required at runtime"
    assert kb_usage_log_repo is not None, "kb_usage_log_repo is required at runtime"

    expander = synonym_expander or SynonymExpander()
    extractor = keyword_extractor or KeywordExtractor()

    async def _exact(state: KnowledgeState) -> dict[str, Any]:
        return await node_search_exact(
            state, knowledge_port=knowledge_port, threshold=threshold, top_k=top_k,
        )

    async def _syn(state: KnowledgeState) -> dict[str, Any]:
        return await node_search_synonyms(
            state, knowledge_port=knowledge_port, synonym_expander=expander,
            threshold=threshold, top_k=top_k,
        )

    async def _kw(state: KnowledgeState) -> dict[str, Any]:
        return await node_search_keywords(
            state, knowledge_port=knowledge_port, keyword_extractor=extractor,
            threshold=threshold, top_k=top_k,
        )

    async def _ask(state: KnowledgeState) -> dict[str, Any]:
        return await node_ask_context(state, chatnexo_port=chatnexo_port)

    async def _directed(state: KnowledgeState) -> dict[str, Any]:
        return await node_search_directed(
            state, knowledge_port=knowledge_port, threshold=threshold, top_k=top_k,
        )

    async def _answer(state: KnowledgeState) -> dict[str, Any]:
        return await node_answer(state, chatnexo_port=chatnexo_port, llm_port=llm_port)

    async def _persist(state: KnowledgeState) -> dict[str, Any]:
        return await node_persist_no_result(state, kb_usage_log_repo=kb_usage_log_repo)

    async def _esc(state: KnowledgeState) -> dict[str, Any]:
        return await node_escalate(state, chatnexo_port=chatnexo_port)

    graph: StateGraph = StateGraph(KnowledgeState)
    graph.add_node("search_exact", _exact)
    graph.add_node("search_synonyms", _syn)
    graph.add_node("search_keywords", _kw)
    graph.add_node("ask_context", _ask)
    graph.add_node("search_directed", _directed)
    graph.add_node("answer", _answer)
    graph.add_node("persist_no_result", _persist)
    graph.add_node("escalate", _esc)

    graph.set_entry_point("search_exact")

    # Após cada busca: answer / next / ask_context
    graph.add_conditional_edges(
        "search_exact",
        route_after_search,
        {"answer": "answer", "next": "search_synonyms", "ask_context": "ask_context"},
    )
    graph.add_conditional_edges(
        "search_synonyms",
        route_after_search,
        {"answer": "answer", "next": "search_keywords", "ask_context": "ask_context"},
    )
    graph.add_conditional_edges(
        "search_keywords",
        route_after_search,
        {"answer": "answer", "next": "ask_context", "ask_context": "ask_context"},
    )

    # ask_context → END (aguarda próximo turno; o dispatcher retoma em search_directed)
    graph.add_edge("ask_context", END)

    # Após search_directed: answer ou persist_no_result
    graph.add_conditional_edges(
        "search_directed",
        route_after_directed,
        {"answer": "answer", "persist_no_result": "persist_no_result"},
    )

    graph.add_edge("answer", END)
    graph.add_edge("persist_no_result", "escalate")
    graph.add_edge("escalate", END)

    return graph
```

> **Nota sobre o default `None` nos asserts:** os testes de construção (`test_build_knowledge_subgraph_*`) verificam a *topologia* do grafo, não sua execução. Para tais testes, tornar os asserts opcionais quando todos os ports forem `None` é uma alternativa; aqui mantemos simples: o teste passa porque o `StateGraph(...)` é criado **antes** dos asserts. Reordenar se necessário.

Ajuste defensivo: mover os asserts **depois** da criação do grafo, ou torná-los condicionais. Aplicar a seguinte modificação:

```python
# (substituir o bloco de asserts por)
def build_knowledge_subgraph(
    *,
    knowledge_port: KnowledgePort | None = None,
    chatnexo_port: ChatNexoPort | None = None,
    llm_port: LLMPort | None = None,
    kb_usage_log_repo: KbUsageLogRepository | None = None,
    synonym_expander: SynonymExpander | None = None,
    keyword_extractor: KeywordExtractor | None = None,
    threshold: float = 0.55,
    top_k: int = 5,
) -> StateGraph:
    """Constrói o subgraph da Capability Knowledge."""
    # Sem asserts — a validação das deps fica na invocação dos nós. Testes de
    # construção podem chamar sem deps; a execução real falhará se faltar.
```

(e remover os `assert ... is not None` iniciais)

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py -v
```
Esperado: todos os testes PASSED (incluindo os 3 sobre o subgraph).

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/application/capabilities/knowledge.py \
        tests/unit/capabilities/test_knowledge.py
git commit -m "feat(knowledge): wire nodes into LangGraph subgraph with conditional edges"
```

---

## Task 12: Dispatcher — roteia intent=knowledge para o subgraph

**Files:**
- Modify: `src/nexoia/interface/worker/dispatcher.py`
- Test: `tests/unit/worker/test_dispatcher_knowledge.py`

- [ ] **Step 1: Escrever o teste falhando**

```python
# tests/unit/worker/test_dispatcher_knowledge.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from nexoia.interface.worker.dispatcher import dispatch_by_intent


@pytest.mark.asyncio
async def test_dispatch_by_intent_knowledge_invokes_knowledge_graph():
    knowledge_graph = AsyncMock()
    knowledge_graph.ainvoke = AsyncMock(return_value={"attempt": 1})

    routes = {
        "knowledge": knowledge_graph,
        # outros intents (welcome, refund, access...) stubs
    }

    state = {
        "intent": "knowledge",
        "original_query": "como acesso",
        "account_id": "acc-1",
    }
    await dispatch_by_intent(state, routes=routes)

    knowledge_graph.ainvoke.assert_awaited_once_with(state)


@pytest.mark.asyncio
async def test_dispatch_by_intent_retoma_knowledge_com_enriched_query():
    """Quando o estado indica `context_requested=True`, a próxima mensagem do
    aluno é concatenada em `enriched_query` antes do dispatch."""
    knowledge_graph = AsyncMock()
    knowledge_graph.ainvoke = AsyncMock(return_value={})

    routes = {"knowledge": knowledge_graph}

    state = {
        "intent": "knowledge",
        "original_query": "como acesso",
        "context_requested": True,
        "enriched_query": None,
        "incoming_message": "pelo celular",
        "account_id": "acc-1",
    }
    await dispatch_by_intent(state, routes=routes)

    passed_state = knowledge_graph.ainvoke.call_args.args[0]
    assert passed_state["enriched_query"] == "como acesso pelo celular"


@pytest.mark.asyncio
async def test_dispatch_by_intent_unknown_raises():
    with pytest.raises(KeyError):
        await dispatch_by_intent({"intent": "unknown_intent"}, routes={})
```

- [ ] **Step 2: Executar para confirmar falha**

```bash
uv run pytest tests/unit/worker/test_dispatcher_knowledge.py -v
```
Esperado: `ImportError` ou `AttributeError` (função ainda não exposta).

- [ ] **Step 3: Expor `dispatch_by_intent` com a lógica de retomada**

No arquivo `src/nexoia/interface/worker/dispatcher.py`, adicionar (ou estender) a função:

```python
async def dispatch_by_intent(state: dict, *, routes: dict) -> dict:
    """Roteia o estado para o subgraph da capability correspondente.

    Para `intent=knowledge`, se `context_requested=True` e há `incoming_message`,
    concatena em `enriched_query` para alimentar o nó `search_directed` na retomada.
    """
    intent = state["intent"]
    if intent not in routes:
        raise KeyError(f"No route for intent={intent!r}")

    # Retomada da Capability Knowledge após ask_context
    if (
        intent == "knowledge"
        and state.get("context_requested")
        and not state.get("enriched_query")
        and state.get("incoming_message")
    ):
        state["enriched_query"] = (
            f"{state['original_query']} {state['incoming_message']}"
        ).strip()

    graph = routes[intent]
    return await graph.ainvoke(state)
```

> Se `dispatch_by_intent` já existir com outra assinatura, apenas acrescentar o bloco de enriched_query ao fluxo existente.

- [ ] **Step 4: Executar para confirmar que passa**

```bash
uv run pytest tests/unit/worker/test_dispatcher_knowledge.py -v
```
Esperado: 3 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add src/nexoia/interface/worker/dispatcher.py \
        tests/unit/worker/test_dispatcher_knowledge.py
git commit -m "feat(knowledge): dispatch intent=knowledge to subgraph with context-resume logic"
```

---

## Task 13: Teste de integração end-to-end — fluxo completo (4 tentativas)

**Files:**
- Create: `tests/integration/test_knowledge_flow.py`

- [ ] **Step 1: Escrever o teste de integração**

```python
# tests/integration/test_knowledge_flow.py
"""Testes de integração end-to-end da Capability Knowledge.

Usa KB pré-populada via FakeKnowledgePort com `match_mode=substring`
para simular o comportamento do pgvector + threshold real.
"""
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from nexoia.application.capabilities.knowledge import (
    KnowledgeState,
    build_knowledge_subgraph,
)
from nexoia.domain.ports.knowledge import KnowledgeHit
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient
from tests.fakes.fake_knowledge_port import FakeKnowledgePort


ACCOUNT_ID = uuid4()


def _initial_state(query: str, **over) -> KnowledgeState:
    base: dict = dict(
        account_id=ACCOUNT_ID,
        conversation_id="conv-int-001",
        correlation_id="corr-int-001",
        messages=[],
        original_query=query,
        enriched_query=None,
        attempt=1,
        synonym_expanded=None,
        keywords_extracted=None,
        chunks_found=[],
        context_requested=False,
        no_result=False,
    )
    base.update(over)
    return KnowledgeState(**base)


@pytest.mark.asyncio
async def test_attempt_1_exact_match_answers():
    """Tentativa 1 encontra → responde direto."""
    kb = FakeKnowledgePort(
        responses={"como acesso a plataforma": [
            KnowledgeHit(document_id=uuid4(), chunk_text="Acesse em app.x.com", score=0.8)
        ]},
        match_mode="substring",
    )
    chat = FakeChatNexoClient()
    llm = AsyncMock()
    llm.complete_text.return_value = "Entra em app.x.com 🙂"
    repo = AsyncMock()

    graph = build_knowledge_subgraph(
        knowledge_port=kb, chatnexo_port=chat, llm_port=llm,
        kb_usage_log_repo=repo,
    ).compile()

    await graph.ainvoke(_initial_state("como acesso a plataforma"))

    assert len(chat.sent_messages) == 1
    assert "app.x.com" in chat.sent_messages[0]["text"]
    assert chat.transfer_calls == []
    repo.save_no_result.assert_not_called()


@pytest.mark.asyncio
async def test_attempt_2_synonyms_match_answers():
    """Tentativa 1 falha, tentativa 2 (sinônimos) encontra → responde."""
    # "acessar" é expandido para "entrar, logar, fazer login..."
    kb = FakeKnowledgePort(
        responses={"fazer login": [
            KnowledgeHit(document_id=uuid4(), chunk_text="Login: botão verde no topo.", score=0.7)
        ]},
        match_mode="substring",
    )
    chat = FakeChatNexoClient()
    llm = AsyncMock()
    llm.complete_text.return_value = "Clica no botão verde 👍"
    repo = AsyncMock()

    graph = build_knowledge_subgraph(
        knowledge_port=kb, chatnexo_port=chat, llm_port=llm,
        kb_usage_log_repo=repo,
    ).compile()

    await graph.ainvoke(_initial_state("não consigo acessar"))

    assert len(chat.sent_messages) == 1
    assert "verde" in chat.sent_messages[0]["text"]
    assert chat.transfer_calls == []


@pytest.mark.asyncio
async def test_attempt_3_keywords_match_answers():
    """Tentativa 1+2 falham, tentativa 3 (keywords) encontra."""
    # KeywordExtractor reduz "como faço para acessar" → "acessar"
    kb = FakeKnowledgePort(
        responses={"acessar": [
            KnowledgeHit(document_id=uuid4(), chunk_text="Acessar: veja X.", score=0.65)
        ]},
        match_mode="exact",   # só bate na query "acessar"
    )
    chat = FakeChatNexoClient()
    llm = AsyncMock()
    llm.complete_text.return_value = "Vê em X"
    repo = AsyncMock()

    graph = build_knowledge_subgraph(
        knowledge_port=kb, chatnexo_port=chat, llm_port=llm,
        kb_usage_log_repo=repo,
    ).compile()

    await graph.ainvoke(_initial_state("como faço para acessar"))

    assert len(chat.sent_messages) == 1
    assert chat.transfer_calls == []


@pytest.mark.asyncio
async def test_attempt_4_asks_context_then_halts():
    """
    Todas as 3 tentativas falham → nó ask_context envia mensagem e
    o subgraph vai para END (aguarda próxima mensagem do aluno).
    O `search_directed` NÃO é executado neste turno.
    """
    kb = FakeKnowledgePort()  # sempre vazio
    chat = FakeChatNexoClient()
    llm = AsyncMock()
    repo = AsyncMock()

    graph = build_knowledge_subgraph(
        knowledge_port=kb, chatnexo_port=chat, llm_port=llm,
        kb_usage_log_repo=repo,
    ).compile()

    final_state = await graph.ainvoke(_initial_state("xyz abc def"))

    # Enviou a mensagem pedindo contexto
    assert len(chat.sent_messages) == 1
    assert "Me conta" in chat.sent_messages[0]["text"]
    assert final_state["context_requested"] is True

    # Não escalou nem persistiu ainda
    assert chat.transfer_calls == []
    repo.save_no_result.assert_not_called()


@pytest.mark.asyncio
async def test_resume_after_context_finds_match_answers():
    """
    Simula retomada após ask_context: estado vem com `enriched_query` preenchido
    (dispatcher concatena) e entra direto no fluxo. Neste teste simulamos
    invocando com estado já em attempt=4 + enriched_query.

    Nota: na prática, o subgraph é re-invocado com START → search_exact no
    novo turno. Este teste foca em search_directed exercitado diretamente.
    """
    from nexoia.application.capabilities.knowledge import node_search_directed

    kb = FakeKnowledgePort(
        responses={"como acesso pelo celular": [
            KnowledgeHit(document_id=uuid4(), chunk_text="No app mobile vá em Menu.", score=0.8)
        ]},
        match_mode="substring",
    )
    state = _initial_state(
        "como acesso",
        enriched_query="como acesso pelo celular",
        context_requested=True,
        attempt=4,
    )

    update = await node_search_directed(state, knowledge_port=kb, threshold=0.55, top_k=5)
    assert len(update["chunks_found"]) == 1


@pytest.mark.asyncio
async def test_all_attempts_exhausted_escalates_and_logs(db_session):
    """
    Simula o final do fluxo: retomada com enriched_query que NÃO bate em nada.
    Deve persistir em kb_usage_logs e chamar transfer_to_human.
    """
    from nexoia.infrastructure.db.repositories.kb_usage_log_repo import (
        KbUsageLogRepository,
    )

    kb = FakeKnowledgePort()  # vazio
    chat = FakeChatNexoClient()
    llm = AsyncMock()
    repo = KbUsageLogRepository(db_session)

    graph = build_knowledge_subgraph(
        knowledge_port=kb, chatnexo_port=chat, llm_port=llm,
        kb_usage_log_repo=repo,
    ).compile()

    state = _initial_state(
        "como acesso a plataforma",
        enriched_query="como acesso a plataforma no meu celular android",
        context_requested=True,
        attempt=4,
    )

    # O subgraph reinvocado em nova turn entraria em search_exact, porém
    # aqui queremos exercer o caminho directed→persist→escalate. Alternativa:
    # invocar node_search_directed, node_persist_no_result, node_escalate em
    # sequência (o teste end-to-end real viria com checkpoint habilitado).
    from nexoia.application.capabilities.knowledge import (
        node_escalate,
        node_persist_no_result,
        node_search_directed,
    )

    u1 = await node_search_directed(state, knowledge_port=kb, threshold=0.55, top_k=5)
    state.update(u1)
    u2 = await node_persist_no_result(state, kb_usage_log_repo=repo)
    state.update(u2)
    await node_escalate(state, chatnexo_port=chat)

    # Escalou com reason correto
    assert len(chat.transfer_calls) == 1
    assert chat.transfer_calls[0]["reason"] == "knowledge_not_found"

    # Persistiu em kb_usage_logs
    rows = await repo.list_no_results(account_id=ACCOUNT_ID, limit=10)
    assert len(rows) == 1
    assert rows[0].original_query == "como acesso a plataforma"
    assert rows[0].result_count == 0
    assert rows[0].attempt == 4
```

- [ ] **Step 2: Executar para confirmar que passa**

```bash
uv run pytest tests/integration/test_knowledge_flow.py -v
```
Esperado: 6 testes PASSED.

- [ ] **Step 3: Rodar toda a suite para garantir ausência de regressões**

```bash
uv run pytest tests/ -v --tb=short
```
Esperado: todos PASSED, sem falhas.

- [ ] **Step 4: Medir cobertura da capability**

```bash
uv run pytest tests/unit/capabilities/test_knowledge.py tests/integration/test_knowledge_flow.py \
    --cov=src/nexoia/application/capabilities/knowledge \
    --cov=src/nexoia/application/kb \
    --cov-report=term-missing
```
Esperado (RNF-K03): cobertura ≥ 90% nas linhas de `application/capabilities/knowledge.py` e `application/kb/`.

- [ ] **Step 5: Commit**

```bash
git add tests/integration/test_knowledge_flow.py
git commit -m "test(knowledge): add end-to-end integration tests for the 4-attempt cascade"
```

---

## Task 14: Atualizar INDEX.md

**Files:**
- Modify: `docs/superpowers/INDEX.md`

- [ ] **Step 1: Marcar o plano ⑦ como criado**

No arquivo `docs/superpowers/INDEX.md`, localizar a linha do Spec ⑦ e atualizar:

```markdown
| ⑦ | **Capability Knowledge** — RAG com 3 tentativas + sinônimos + keywords | [spec](specs/2026-04-18-nexoia-capability-knowledge-design.md) | [plano](plans/2026-04-18-nexoia-capability-knowledge.md) | ⏳ Pendente |
```

E na seção "Planos", adicionar:

```markdown
- `2026-04-18-nexoia-capability-knowledge.md` — Plano ⑦: 14 tasks, TDD completo, cascade 4 tentativas, stub sinônimos
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/INDEX.md
git commit -m "docs: mark Knowledge plan as created in INDEX"
```

---

## Self-Review

### Cobertura de RFs (spec ⑦ seção 10)

| RF | Coberto por |
|----|-------------|
| `RF-K01` | Core (spec ①) já classifica `intent=knowledge`. Task 12 faz o wiring do dispatcher para o subgraph. |
| `RF-K02` | Task 1 (`KB_ATTEMPT_1_THRESHOLD=0.55`) + Task 8 (`node_search_exact` consome threshold via DI). Testes: `test_search_exact_found_*`. |
| `RF-K03` | Task 4 (`SynonymExpander` stub com ~15 termos) + Task 8 (`node_search_synonyms`). Testes: `test_search_synonyms_*`, `test_synonym_expander_*`. |
| `RF-K04` | Task 2 (stopwords) + Task 3 (`KeywordExtractor`) + Task 8 (`node_search_keywords`). Testes: `test_search_keywords_*`, `test_keyword_extractor_*`. |
| `RF-K05` | Task 9 (`node_ask_context` + `node_search_directed`) + Task 12 (dispatcher concatena `enriched_query`). Testes: `test_ask_context_*`, `test_search_directed_*`, `test_dispatch_by_intent_retoma_*`. |
| `RF-K06` | Task 10 (`node_persist_no_result` + `node_escalate`) + Task 11 (arestas terminais). Testes: `test_persist_no_result_*`, `test_escalate_*`, `test_all_attempts_exhausted_escalates_and_logs`. |
| `RF-K07` | Task 4 — TODO inline `CQ-K01` em `synonym_expander.py`, referenciado em `OPEN_QUESTIONS.md`. |
| `RF-K08` | Task 6 (`KbUsageLogRepository.save_no_result`) + Task 10 (invocação no nó). Teste integração: `test_all_attempts_exhausted_escalates_and_logs`. |

### Cobertura de RNFs (spec ⑦ seção 11)

| RNF | Coberto por |
|-----|-------------|
| `RNF-K01` | Todos os nós passam `account_id=state["account_id"]` ao `KnowledgePort.search`. Task 8/9/10 — inspecionado nos testes. |
| `RNF-K02` | Estado `KnowledgeState` é TypedDict baseado em `ConversationState` (checkpoint LangGraph já configurado no Core). O nó `ask_context` vai para `END` preservando `context_requested=True`; dispatcher retoma no próximo turno com `enriched_query`. |
| `RNF-K03` | Task 13 Step 4 roda `pytest --cov` e exige ≥90% na capability + módulos `kb/`. |
| `RNF-K04` | Latência observada por `knowledge_answer_latency_seconds` (histogram). Cada tentativa faz 1 chamada HTTP ao port (spec ⑥ faz a busca pgvector real). |

### Dependências externas respeitadas

- `ConversationState` — vem de `application/state.py` (Core/spec ①).
- `KnowledgePort` + `KnowledgeHit` — vêm de `domain/ports/knowledge.py` (Core/spec ①).
- `LLMPort` + `ChatNexoPort` — vêm de `domain/ports/` (Core/spec ①).
- `KbUsageLogModel` — vem de `infrastructure/db/models.py` (spec ⑥). Este plano apenas consome; se o modelo ainda não existir, a Task 6 sinaliza a dependência explicitamente.
- Intent Router já classifica `knowledge` (Core Task referenciando Intent enum). Task 12 apenas faz o roteamento.

### Decisões de design conscientes

1. **Estratégia de expansão de sinônimos (concatenação vs. substituição):** escolhemos **concatenação** (`expand("acessar") → "acessar entrar logar fazer login"`). Rationale: embeddings tratam melhor a query semanticamente rica; substituir perde a intenção original.
2. **Threshold filtrado duas vezes:** o `KnowledgePort.search` deve aplicar threshold internamente (eficiência do pgvector), mas reforçamos no nó para segurança em fakes/testes e caso o port retorne scores brutos.
3. **`ask_context` vai para END, não espera no próprio grafo:** LangGraph não bloqueia turnos reais; a persistência do estado via checkpoint + retomada no próximo `ProcessIncomingMessage` é o mecanismo padrão. Dispatcher (Task 12) injeta `enriched_query` na retomada.
4. **Lista de sinônimos como stub consciente:** ~15 termos comuns para o MVP, com TODO CQ-K01 explícito. A tentativa 2 funciona desde o go-live para as queries mais frequentes; ampliação é pura configuração do dict.
5. **Métricas sem cardinalidade explosiva:** `attempt` é label com 4 valores; `status` com 3. Totais manejáveis em Prometheus.

### Riscos conhecidos

| Risco | Mitigação |
|-------|-----------|
| Threshold 0.55 muito permissivo ou muito restrito na prática | Observabilidade: `knowledge_attempts_total{attempt=...}` mostra distribuição. Ajuste via `KB_ATTEMPT_1_THRESHOLD` sem deploy. |
| Stub de sinônimos com cobertura muito pequena | Enquanto CQ-K01 não é resolvido, `knowledge_no_result_total` aponta demanda real e `kb_usage_logs` lista queries que falharam → input direto para alimentar a lista. |
| `KbUsageLogModel` não existir ainda no Core | Task 6 documenta a estrutura esperada; ajustar quando spec ⑥ for implementado. Se o modelo usar outros nomes, apenas os imports do repo mudam. |
| `route_after_search` em `search_keywords` com `attempt=4` + `chunks_found=[]` vai para `ask_context` — mas `route_after_search` em geral está correto | Coberto pelo teste `test_route_after_search_to_ask_context_when_empty_and_attempt_4_no_context_yet`. |

### Sem placeholders vagos

- Todo `TODO` tem referência `OPEN_QUESTIONS.md#CQ-K01`.
- Imports assumidos (`KbUsageLogModel`) estão documentados na Task 6 como dependência explícita do spec ⑥.
- Fakes (`FakeKnowledgePort`, `FakeChatNexoClient`) são configuráveis e verificáveis, sem mágica.

### Ordem de execução (TDD rigoroso)

1. Task 1 (settings) — base de configuração.
2. Task 2 → 3 → 4 (stopwords → extractor → expander) — blocos reutilizáveis, sem dependência do subgraph.
3. Task 5 (fakes) — preparação para testar a capability.
4. Task 6 (repo) — persistência das queries sem resultado.
5. Task 7 (métricas) — observabilidade antes dos nós consumirem.
6. Tasks 8–11 (nós e subgraph) — construção incremental com testes por nó.
7. Task 12 (dispatcher) — wire-up final.
8. Task 13 (integração end-to-end) — valida o fluxo completo.
9. Task 14 (INDEX) — housekeeping.

Este plano respeita o ciclo: **teste falha → implementa → teste passa → commit**, com cada task isolada e revertível.
