from __future__ import annotations

from nexoia.application.use_cases.knowledge.synonym_expander import SYNONYMS, SynonymExpander


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
    assert "entrar" in result
    assert "logar" in result
    assert "treinamento" in result
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
