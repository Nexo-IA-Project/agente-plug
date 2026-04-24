from __future__ import annotations
import pytest
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage, HumanMessage

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
async def test_raciocinar_guard_blocks_llm():
    guard_service = MagicMock()
    guard_service.check.return_value = GuardResult(
        blocked=True, reason="legal_mention", skill_override="escalar_para_humano"
    )
    llm = AsyncMock()
    long_term_repo = AsyncMock()
    long_term_repo.load.return_value = []
    node = make_raciocinar_node(guard_service, long_term_repo, llm)
    result = await node(base_state([HumanMessage("vou acionar o Procon")]), fake_config())
    llm.ainvoke.assert_not_called()
    last_msg = result["messages"][-1]
    assert hasattr(last_msg, "tool_calls") and last_msg.tool_calls


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
