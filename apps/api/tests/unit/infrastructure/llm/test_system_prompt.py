from __future__ import annotations
from agent.prompt import build_system_prompt


def test_build_system_prompt_returns_string():
    prompt = build_system_prompt(long_term_facts=[])
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_build_system_prompt_includes_facts():
    facts = ["Aluno prefere resposta curta", "Produto: Mentoria de Tráfego"]
    prompt = build_system_prompt(long_term_facts=facts)
    assert "Mentoria de Tráfego" in prompt
    assert "resposta curta" in prompt


def test_build_system_prompt_no_facts_still_valid():
    prompt = build_system_prompt(long_term_facts=[])
    assert "WhatsApp" in prompt  # instruções base sempre presentes
