"""Tests for the professional prompt builder (Task 18)."""

from __future__ import annotations

from agent.prompt import build_system_prompt


def test_prompt_contains_identity():
    prompt = build_system_prompt([])
    assert "Nia" in prompt or "G2 Educação" in prompt


def test_prompt_contains_formatting_rules():
    prompt = build_system_prompt([])
    # Prompt Mestre usa "300 caracteres" como regra de tamanho
    assert "300 caracteres" in prompt


def test_prompt_contains_skills_section():
    prompt = build_system_prompt([])
    assert "escalar_para_humano" in prompt


def test_facts_are_included_when_provided():
    facts = ["João comprou o curso de Python em jan/2025", "Preferência: suporte rápido"]
    prompt = build_system_prompt(facts)
    assert "João comprou o curso de Python" in prompt
    assert "Preferência: suporte rápido" in prompt


def test_no_facts_section_when_empty():
    prompt = build_system_prompt([])
    assert "Informações conhecidas" not in prompt


def test_forced_instruction_is_appended():
    prompt = build_system_prompt([], forced_instruction="ESCALE AGORA")
    assert "ESCALE AGORA" in prompt
    assert "INSTRUÇÃO PRIORITÁRIA" in prompt


def test_no_forced_instruction_when_none():
    prompt = build_system_prompt([])
    assert "INSTRUÇÃO PRIORITÁRIA" not in prompt


def test_forced_instruction_and_facts_both_present():
    prompt = build_system_prompt(["fato 1"], forced_instruction="agir agora")
    assert "fato 1" in prompt
    assert "agir agora" in prompt
