from __future__ import annotations
import pytest
from nexoia.domain.policies.communication_rules import CommunicationRules, ValidationResult


def test_ok_for_clean_short_message():
    result = CommunicationRules().validate("Olá, como posso ajudar?")
    assert result.ok is True


def test_fails_for_too_long_message():
    result = CommunicationRules().validate("x" * 301)
    assert result.ok is False
    assert "longa" in result.correction_hint.lower()


def test_fails_for_forbidden_word():
    result = CommunicationRules().validate("putz, que situação!")
    assert result.ok is False
    assert "proibida" in result.correction_hint.lower()


def test_fails_for_markdown():
    result = CommunicationRules().validate("**Aqui** está seu link")
    assert result.ok is False
    assert "markdown" in result.correction_hint.lower()


def test_fails_for_ia_reveal():
    result = CommunicationRules().validate("Sou uma IA e posso ajudar")
    assert result.ok is False
    assert "IA" in result.correction_hint


def test_validation_result_is_frozen():
    r = ValidationResult(ok=True)
    with pytest.raises((AttributeError, TypeError)):
        r.ok = False  # type: ignore[misc]
