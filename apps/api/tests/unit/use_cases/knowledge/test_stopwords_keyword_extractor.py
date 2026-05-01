from __future__ import annotations

from nexoia.application.use_cases.knowledge.keyword_extractor import KeywordExtractor
from nexoia.application.use_cases.knowledge.stopwords_ptbr import STOPWORDS


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
    assert "acessar" in keywords
    assert "curso" in keywords


def test_keyword_extractor_removes_short_tokens():
    extractor = KeywordExtractor()
    keywords = extractor.extract("eu vi um bug")
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
    result = extractor.extract("Certificado Digital")
    assert "certificado" in result
    assert "digital" in result
