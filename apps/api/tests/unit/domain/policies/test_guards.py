from __future__ import annotations

from agent.guards import (
    GuardResult,
    GuardService,
    LegalMentionGuard,
    LoopDetectorGuard,
)


def _ai_msg(content: str) -> dict:
    return {"role": "assistant", "content": content}


def _state(messages: list) -> dict:
    return {"messages": messages}


def test_legal_mention_guard_blocks_on_procon():
    result = LegalMentionGuard().check("vou acionar o Procon!", _state([]))
    assert result.blocked is True
    assert result.reason == "legal_mention"
    assert result.forced_instruction
    assert "escalar_para_humano" in result.forced_instruction


def test_legal_mention_guard_blocks_on_advogado():
    result = LegalMentionGuard().check("vou chamar meu advogado", _state([]))
    assert result.blocked is True
    assert result.forced_instruction


def test_legal_mention_guard_passes_normal_message():
    result = LegalMentionGuard().check("quero acessar meu curso", _state([]))
    assert result.blocked is False


def test_loop_detector_blocks_when_ai_repeats():
    repeated = _ai_msg("Olá! Como posso ajudar?")
    state = _state([repeated, repeated, repeated])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is True
    assert result.reason == "loop_detected"
    assert result.forced_instruction
    assert "escalar_para_humano" in result.forced_instruction


def test_loop_detector_passes_varied_messages():
    state = _state([_ai_msg("Mensagem 1"), _ai_msg("Mensagem 2"), _ai_msg("Mensagem 3")])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is False


def test_guard_service_returns_first_blocked():
    service = GuardService([LegalMentionGuard(), LoopDetectorGuard()])
    result = service.check("acionar o Procon", _state([]))
    assert result.blocked is True
    assert result.reason == "legal_mention"


def test_guard_service_passes_clean_message():
    service = GuardService([LegalMentionGuard(), LoopDetectorGuard()])
    result = service.check("preciso de ajuda", _state([_ai_msg("Ok"), _ai_msg("Tudo bem?")]))
    assert result.blocked is False


def test_loop_detector_does_not_block_below_threshold():
    repeated = _ai_msg("Olá! Como posso ajudar?")
    state = _state([repeated, repeated])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is False


def test_loop_detector_blocks_on_tail_not_full_window():
    different = _ai_msg("Mensagem diferente")
    repeated = _ai_msg("Resposta em loop")
    state = _state([different, repeated, repeated, repeated])
    result = LoopDetectorGuard().check("oi", state)
    assert result.blocked is True


def test_guard_result_has_no_skill_override_field():
    result = GuardResult(blocked=False)
    assert not hasattr(result, "skill_override")
