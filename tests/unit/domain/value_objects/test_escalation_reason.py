import pytest
from nexoia.domain.value_objects.escalation_reason import EscalationReason


def test_all_8_reasons_defined():
    reasons = list(EscalationReason)
    assert len(reasons) == 8


def test_reason_values_are_strings():
    for r in EscalationReason:
        assert isinstance(r.value, str)


def test_specific_reasons_exist():
    assert EscalationReason.HUMAN_REQUESTED_3X
    assert EscalationReason.LEGAL_MENTION
    assert EscalationReason.LOJA_EXPRESS_BLOCKED
