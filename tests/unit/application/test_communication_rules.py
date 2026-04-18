import pytest
from nexoia.application.communication_rules import CommunicationRules, ViolationType


def test_detects_too_long():
    text = "a" * 301
    violations = CommunicationRules().check(text)
    assert ViolationType.TOO_LONG in violations


def test_accepts_exactly_300():
    text = "a" * 300
    violations = CommunicationRules().check(text)
    assert ViolationType.TOO_LONG not in violations


def test_detects_forbidden_word_putz():
    violations = CommunicationRules().check("putz, que situação")
    assert ViolationType.FORBIDDEN_WORD in violations


def test_detects_forbidden_word_claro():
    violations = CommunicationRules().check("Claro! posso ajudar")
    assert ViolationType.FORBIDDEN_WORD in violations


def test_detects_markdown_bullet():
    violations = CommunicationRules().check("- item 1\n- item 2")
    assert ViolationType.MARKDOWN in violations


def test_detects_markdown_bold():
    violations = CommunicationRules().check("texto **negrito** aqui")
    assert ViolationType.MARKDOWN in violations


def test_detects_ia_reveal():
    violations = CommunicationRules().check("sou uma inteligência artificial aqui pra ajudar")
    assert ViolationType.IA_REVEAL in violations


def test_clean_text_has_no_violations():
    violations = CommunicationRules().check("oi, como posso te ajudar hoje?")
    assert violations == []
