from unittest.mock import AsyncMock

import pytest

from nexoia.application.capabilities.access import AccessState, node_check_platform_scope


def make_state(last_user_message: str, **kwargs) -> AccessState:
    base = dict(
        account_id=1, correlation_id="corr-1",
        messages=[{"role": "user", "content": last_user_message}],
        access_case_id="ac-1", student_email="joao@email.com",
        student_cpf="123.456.789-00", student_name="João",
        student_phone="+5511999999999", cademi_student=None,
        search_attempts=0, cpf_asked=False, access_link=None,
        out_of_scope=False, email_mismatch_pending=False,
    )
    base.update(kwargs)
    return base  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_scope_passes_through_when_message_is_about_access():
    handoff = AsyncMock()
    result = await node_check_platform_scope(
        make_state("não consigo entrar no curso, esqueci a senha"), handoff_fn=handoff,
    )
    assert result.get("out_of_scope", False) is False
    handoff.assert_not_called()


@pytest.mark.asyncio
async def test_scope_detects_shopee_and_handoffs():
    handoff = AsyncMock()
    result = await node_check_platform_scope(
        make_state("meu cadastro shopee não tá aprovado"), handoff_fn=handoff,
    )
    assert result["out_of_scope"] is True
    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "shopee_or_kyc_out_of_scope"


@pytest.mark.asyncio
async def test_scope_detects_kyc_case_insensitive():
    handoff = AsyncMock()
    result = await node_check_platform_scope(
        make_state("to travado no KYC, me ajuda"), handoff_fn=handoff,
    )
    assert result["out_of_scope"] is True
    handoff.assert_awaited_once()


@pytest.mark.asyncio
async def test_scope_detects_shopee_case_insensitive():
    handoff = AsyncMock()
    result = await node_check_platform_scope(
        make_state("problema no SHOPEE ID"), handoff_fn=handoff,
    )
    assert result["out_of_scope"] is True


@pytest.mark.asyncio
async def test_scope_skipped_when_lookup_failed():
    handoff = AsyncMock()
    result = await node_check_platform_scope(
        make_state("não consigo entrar", access_case_id=None), handoff_fn=handoff,
    )
    assert result.get("out_of_scope", False) is False
    handoff.assert_not_called()


@pytest.mark.asyncio
async def test_scope_uses_last_user_message_only():
    handoff = AsyncMock()
    state = make_state("agora: não consigo acessar o curso")
    state["messages"] = [
        {"role": "user", "content": "antes: falei de shopee"},
        {"role": "assistant", "content": "resposta anterior"},
        {"role": "user", "content": "agora: não consigo acessar o curso"},
    ]
    result = await node_check_platform_scope(state, handoff_fn=handoff)
    assert result.get("out_of_scope", False) is False
    handoff.assert_not_called()
