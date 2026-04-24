from unittest.mock import AsyncMock
from nexoia.infrastructure.skills.refund import make_refund_skills


def test_make_refund_skills_returns_three_tools():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    assert len(skills) == 3


def test_make_refund_skills_tool_names():
    skills = make_refund_skills(
        refund_repo=AsyncMock(),
        hubla=AsyncMock(),
        legal_history=AsyncMock(),
        refund_mutex=AsyncMock(),
    )
    names = {s.name for s in skills}
    assert names == {
        "verificar_elegibilidade_reembolso",
        "oferecer_retencao",
        "processar_reembolso",
    }
