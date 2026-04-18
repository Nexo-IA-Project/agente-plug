"""
Integração end-to-end da Capability Access (spec ③).

Cenários cobertos:
  1) Happy path — cascade resolve no email (1ª tentativa) dentro da janela 24h.
  2) Fallback por CPF stored — email miss, CPF do AccessCase resolve.
  3) CPF pedido ao aluno — student_cpf=None, aluno responde, segue.
  4) Escalation — 3 tentativas falham; status vira REACTIVE_ESCALATED.
  5) Out of scope — aluno menciona Shopee; handoff silencioso e sem update.
  6) No access case — aluno sem AccessCase → handoff silencioso.
"""
import pytest
from unittest.mock import AsyncMock

from nexoia.application.capabilities.access import (
    AccessState,
    node_lookup_access_case,
    node_check_platform_scope,
    node_search_cademi_cascade,
    node_send_access,
    node_update_access_case,
)
from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.domain.ports.cademi_port import CademiStudent
from nexoia.infrastructure.db.repositories.access_case_repo import AccessCaseRepository
from tests.fakes.fake_cademi_client import FakeCademiClient
from tests.fakes.fake_chatnexo_client import FakeChatNexoClient


async def _seed_access_case(db_session, *, cpf: str | None, phone: str) -> str:
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id=phone,
        conversation_id="conv-seed",
        purchase_id=f"purchase-seed-{phone}",
        product_name="Curso Python",
        student_cpf=cpf,
        status=AccessCaseStatus.LINK_SENT,
    )
    await repo.save(case)
    return case.id


def _make_state(
    phone: str,
    *,
    email: str,
    cpf: str | None,
    last_message: str,
    within_24h: bool = True,
    conversation_id: str = "conv-seed",
) -> AccessState:
    return {  # type: ignore[typeddict-item]
        "account_id": 1,
        "correlation_id": "corr-access-int",
        "messages": [{"role": "user", "content": last_message}],
        "access_case_id": None,
        "student_email": email,
        "student_cpf": cpf,
        "student_name": "João Silva",
        "student_phone": phone,
        "cademi_student": None,
        "search_attempts": 0,
        "cpf_asked": False,
        "access_link": None,
        "out_of_scope": False,
        "email_mismatch_pending": False,
        "conversation_id": conversation_id,
        "purchase_id": f"purchase-seed-{phone}",
        "product_name": "Curso Python",
        "within_24h_window": within_24h,
    }


async def _run_subgraph(
    state: AccessState,
    *,
    repo,
    cademi,
    chatnexo,
    handoff,
) -> AccessState:
    updates = await node_lookup_access_case(
        state, access_case_repo=repo, chatnexo_port=chatnexo, handoff_fn=handoff
    )
    state.update(updates)
    updates = await node_check_platform_scope(state, handoff_fn=handoff)
    state.update(updates)
    updates = await node_search_cademi_cascade(
        state, cademi_port=cademi, chatnexo_port=chatnexo, handoff_fn=handoff
    )
    state.update(updates)
    updates = await node_send_access(
        state, cademi_port=cademi, chatnexo_port=chatnexo
    )
    state.update(updates)
    updates = await node_update_access_case(state, access_case_repo=repo)
    state.update(updates)
    return state


@pytest.mark.integration
@pytest.mark.asyncio
async def test_happy_path_email_within_24h(db_session):
    phone = "+5511900000001"
    await _seed_access_case(db_session, cpf="11122233344", phone=phone)
    repo = AccessCaseRepository(db_session)

    alice = CademiStudent(id="s1", name="João Silva", email="joao@e.com", phone=phone)
    cademi = FakeCademiClient(
        students_by_email={"joao@e.com": alice},
        access_link="https://cademi.com.br/auto-login/nominal-alice",
    )
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf="11122233344",
        last_message="não consigo entrar no curso",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    assert state["cademi_student"] == alice
    assert state["access_link"] == "https://cademi.com.br/auto-login/nominal-alice"
    assert chatnexo.last_sent_text is not None
    assert "https://cademi.com.br/auto-login/nominal-alice" in chatnexo.last_sent_text
    handoff.assert_not_called()

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.REACTIVE_LINK_SENT
    assert saved.search_attempts == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_found_by_cpf_stored(db_session):
    phone = "+5511900000002"
    await _seed_access_case(db_session, cpf="22233344455", phone=phone)
    repo = AccessCaseRepository(db_session)

    bob = CademiStudent(id="s2", name="João Silva", email="joao@e.com", phone=phone)
    cademi = FakeCademiClient(
        students_by_email={},
        students_by_cpf={"22233344455": bob},
        access_link="https://cademi.com.br/auto-login/nominal-bob",
    )
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf=None,
        last_message="esqueci senha, não consigo",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )
    assert state["cademi_student"] == bob
    assert state["search_attempts"] == 2

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.REACTIVE_LINK_SENT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cpf_asked_when_none_in_access_case(db_session):
    phone = "+5511900000003"
    await _seed_access_case(db_session, cpf=None, phone=phone)
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient(students_by_email={})
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf=None,
        last_message="não consigo acessar, help",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    assert state["cpf_asked"] is True
    assert state["cademi_student"] is None
    assert chatnexo.last_sent_text is not None
    assert "cpf" in chatnexo.last_sent_text.lower()

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.LINK_SENT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_escalation_after_3_attempts(db_session):
    phone = "+5511900000004"
    await _seed_access_case(db_session, cpf="33344455566", phone=phone)
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient(
        students_by_email={},
        students_by_cpf={},
        name_phone_supported=False,
    )
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf="33344455566",
        last_message="não consigo entrar",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    assert state["cademi_student"] is None
    assert state["search_attempts"] == 3
    handoff.assert_awaited()
    assert handoff.await_args.kwargs["reason"] == "cademi_not_found_after_3_attempts"

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.REACTIVE_ESCALATED
    assert saved.search_attempts == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test_out_of_scope_shopee(db_session):
    phone = "+5511900000005"
    await _seed_access_case(db_session, cpf="44455566677", phone=phone)
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient()
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone, email="joao@e.com", cpf="44455566677",
        last_message="meu cadastro shopee tá travado, help!",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    assert state["out_of_scope"] is True
    assert cademi.email_calls == 0
    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "shopee_or_kyc_out_of_scope"

    saved = await repo.find_by_phone(account_id=1, phone=phone)
    assert saved.status == AccessCaseStatus.LINK_SENT


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_access_case_handoff(db_session):
    phone_unknown = "+5511900000999"
    repo = AccessCaseRepository(db_session)

    cademi = FakeCademiClient()
    chatnexo = FakeChatNexoClient()
    handoff = AsyncMock()

    state = _make_state(
        phone_unknown, email="ghost@e.com", cpf=None,
        last_message="não consigo entrar",
    )
    state = await _run_subgraph(
        state, repo=repo, cademi=cademi, chatnexo=chatnexo, handoff=handoff,
    )

    handoff.assert_awaited_once()
    assert handoff.await_args.kwargs["reason"] == "no_access_case"
    assert state["access_case_id"] is None
    assert cademi.email_calls == 0
    assert chatnexo.last_sent_text is None
