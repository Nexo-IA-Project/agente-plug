from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nexoia.domain.policies.guards import GuardResult
from nexoia.infrastructure.langgraph_runtime.nodes import make_raciocinar_node, make_pos_execucao_node


def fake_config(account_id: str = "t1", phone: str = "5511999", conv_id: str = "c1"):
    return {"configurable": {"account_id": account_id, "phone": phone, "conversation_id": conv_id}}


def base_state(messages=None, skill_em_andamento=None, mensagens_pendentes=None):
    return {
        "messages": messages or [HumanMessage("oi")],
        "skill_em_andamento": skill_em_andamento,
        "mensagens_pendentes": mensagens_pendentes or [],
    }


@pytest.mark.asyncio
async def test_raciocinar_guard_with_forced_instruction_calls_llm_with_system_message():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(
        blocked=True,
        reason="legal_mention",
        forced_instruction="INSTRUÇÃO CRÍTICA: chame escalar_para_humano.",
    )
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage(
        content="",
        tool_calls=[{"name": "escalar_para_humano", "args": {}, "id": "t1", "type": "tool_call"}],
    )
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state([HumanMessage("vou acionar o Procon")]), fake_config())
    llm.ainvoke.assert_called_once()
    msgs_used = llm.ainvoke.call_args[0][0]
    assert isinstance(msgs_used[0], SystemMessage)
    assert "INSTRUÇÃO CRÍTICA" in msgs_used[0].content
    assert result.get("skill_em_andamento") == "escalar_para_humano"


@pytest.mark.asyncio
async def test_raciocinar_guard_blocked_no_forced_instruction_returns_response():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(
        blocked=True, reason="x", response="Mensagem direta ao aluno."
    )
    llm = AsyncMock()
    long_term_repo = AsyncMock()
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state([HumanMessage("msg")]), fake_config())
    llm.ainvoke.assert_not_called()
    assert result["messages"][-1].content == "Mensagem direta ao aluno."


@pytest.mark.asyncio
async def test_raciocinar_invokes_llm_when_guard_passes():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(blocked=False)
    llm = AsyncMock()
    llm.ainvoke.return_value = AIMessage("Olá, como posso ajudar?")
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state(), fake_config())
    llm.ainvoke.assert_called_once()
    assert "messages" in result


@pytest.mark.asyncio
async def test_raciocinar_queues_message_when_skill_in_progress():
    guard_service = MagicMock()
    llm = AsyncMock()
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    state = base_state(
        messages=[HumanMessage("nova mensagem")],
        skill_em_andamento="buscar_aluno_cademi",
    )
    result = await node(state, fake_config())
    llm.ainvoke.assert_not_called()
    assert "mensagens_pendentes" in result


@pytest.mark.asyncio
async def test_pos_execucao_clears_skill_em_andamento():
    cap_repo = AsyncMock()
    mem_extractor = AsyncMock()
    node = make_pos_execucao_node(cap_repo, mem_extractor)
    state = base_state(skill_em_andamento="buscar_aluno_cademi")
    result = await node(state, fake_config())
    assert result["skill_em_andamento"] is None
