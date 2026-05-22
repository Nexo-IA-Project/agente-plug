from __future__ import annotations

from shared.adapters.chatnexo.message_splitter import split_message


def test_short_message_no_double_newline_returns_single_part():
    """Mensagem sem \\n\\n retorna sempre uma só parte, qualquer tamanho."""
    result = split_message("Olá! Como posso ajudar você hoje?")
    assert result == ["Olá! Como posso ajudar você hoje?"]


def test_two_paragraphs_returns_two_parts():
    first = "Este é o primeiro parágrafo com texto suficiente para passar no filtro padrão de oitenta caracteres."
    second = "Este é o segundo parágrafo com texto suficiente para passar no filtro padrão de oitenta caracteres."
    text = f"{first}\n\n{second}"
    result = split_message(text)
    assert result == [first, second]


def test_long_paragraph_split_by_sentence_respects_max_chars():
    # Parágrafo longo (>200 chars) com \n\n separa de outro
    # O parágrafo longo deve ser dividido por sentença
    sentence = "Esta é uma sentença longa. "
    long_para = (sentence * 8).strip()  # ~288 chars, excede max_chars=200
    short_para = "b" * 90  # 90 chars >= min_chars=80
    text = f"{long_para}\n\n{short_para}"
    result = split_message(text, max_chars=200)
    # long_para foi dividido em múltiplas partes, short_para também
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
    p1 = "a" * 85
    p2 = "b" * 85
    p3 = "c" * 85
    text = f"{p1}\n\n{p2}\n\n{p3}"
    result = split_message(text)
    assert result == [p1, p2, p3]
