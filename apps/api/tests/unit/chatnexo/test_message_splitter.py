from __future__ import annotations

import pytest

from shared.adapters.chatnexo.message_splitter import split_message


def test_short_message_no_double_newline_returns_single_part():
    """Mensagem sem \\n\\n retorna sempre uma só parte, qualquer tamanho."""
    result = split_message("Olá! Como posso ajudar você hoje?")
    assert result == ["Olá! Como posso ajudar você hoje?"]


def test_two_paragraphs_returns_two_parts():
    text = "Primeiro parágrafo de teste.\n\nSegundo parágrafo de teste."
    result = split_message(text)
    assert result == ["Primeiro parágrafo de teste.", "Segundo parágrafo de teste."]


def test_long_paragraph_split_by_sentence_respects_max_chars():
    # 12 sentenças de ~36 chars cada → ~432 chars, excede max_chars=200
    sentence = "Esta é uma sentença longa. "
    text = (sentence * 12).strip()
    result = split_message(text, max_chars=200)
    assert len(result) > 1
    for part in result:
        assert len(part) <= 200


def test_short_parts_below_min_chars_discarded():
    # "ok" tem 2 chars < min_chars=80, deve ser descartado
    long_part = "a" * 85  # 85 chars, passa o filtro
    text = f"{long_part}\n\nok"
    result = split_message(text, min_chars=80)
    assert len(result) == 1
    assert result[0] == long_part


def test_whitespace_only_returns_empty_list():
    assert split_message("   \n\n   ") == []
    assert split_message("") == []
    assert split_message("\n\n\n") == []


def test_all_parts_too_short_returns_original_as_fallback():
    # Ambos os parágrafos < min_chars → retorna texto original
    text = "ab\n\ncd"
    result = split_message(text, min_chars=80)
    assert result == ["ab\n\ncd"]


def test_three_paragraphs():
    text = "Parte um.\n\nParte dois.\n\nParte três."
    result = split_message(text)
    assert result == ["Parte um.", "Parte dois.", "Parte três."]
