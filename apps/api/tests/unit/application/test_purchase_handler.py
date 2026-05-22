from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from shared.application.purchase_handler import PurchaseHandler
from shared.domain.events.purchase_received import PurchaseReceived


def fake_event(
    product_id: str = "prod-mentoria",
    product_name: str = "Mentoria de Tráfego",
) -> PurchaseReceived:
    return PurchaseReceived(
        purchase_id="p-1",
        account_id=UUID("00000000-0000-0000-0000-000000000001"),
        customer_name="João Silva",
        contact_email="joao@test.com",
        contact_phone="5511999990000",
        product_id=product_id,
        product_name=product_name,
        amount_brl=49700,
        occurred_at=datetime.now(UTC),
    )


def _make_handler(
    *,
    course_repo: AsyncMock | None = None,
    flow_repo: AsyncMock | None = None,
    enroll_uc: AsyncMock | None = None,
    contact_repo: AsyncMock | None = None,
    chatnexo: AsyncMock | None = None,
    access_case_repo: AsyncMock | None = None,
    scheduler: AsyncMock | None = None,
) -> PurchaseHandler:
    contact_repo = contact_repo or AsyncMock()
    if not contact_repo.upsert.return_value:
        contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = chatnexo or AsyncMock()
    if (
        chatnexo.get_open_conversation.return_value is None
        and not chatnexo.create_conversation.return_value
    ):
        chatnexo.create_conversation.return_value = "conv-1"
    return PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo or AsyncMock(),
        scheduler=scheduler or AsyncMock(),
        course_repo=course_repo or AsyncMock(),
        flow_repo=flow_repo or AsyncMock(),
        enroll_contact_uc=enroll_uc or AsyncMock(),
    )


@pytest.mark.asyncio
async def test_creates_contact_and_access_case():
    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = None
    chatnexo.create_conversation.return_value = "conv-1"
    access_case_repo = AsyncMock()
    course_repo = AsyncMock()
    course_repo.find_active_by_hubla_id.return_value = None
    handler = _make_handler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=access_case_repo,
        course_repo=course_repo,
    )
    await handler.execute(fake_event())
    contact_repo.upsert.assert_called_once()
    access_case_repo.save.assert_called_once()


@pytest.mark.asyncio
async def test_sends_welcome_template():
    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "existing-conv"
    course_repo = AsyncMock()
    course_repo.find_active_by_hubla_id.return_value = None
    handler = _make_handler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        course_repo=course_repo,
    )
    await handler.execute(fake_event())
    chatnexo.send_template.assert_called_once()
    call_kwargs = chatnexo.send_template.call_args.kwargs
    assert call_kwargs["template_name"] == "welcome_purchase"


@pytest.mark.asyncio
async def test_purchase_with_known_course_enrolls_in_all_active_flows():
    course_id = uuid4()
    flow_id_1 = uuid4()
    flow_id_2 = uuid4()
    course_repo = AsyncMock()
    flow_repo = AsyncMock()
    enroll_uc = AsyncMock()
    course_repo.find_active_by_hubla_id.return_value = SimpleNamespace(id=course_id, name="Mkt 360")
    flow_repo.list_active_by_product.return_value = [
        SimpleNamespace(id=flow_id_1),
        SimpleNamespace(id=flow_id_2),
    ]

    contact_id = uuid4()
    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id=contact_id, phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-1"

    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=AsyncMock(),
        scheduler=AsyncMock(),
        course_repo=course_repo,
        flow_repo=flow_repo,
        enroll_contact_uc=enroll_uc,
    )
    event = fake_event(product_id="prod-mkt-360", product_name="Mkt 360")
    await handler.execute(event)

    assert enroll_uc.execute.await_count == 2
    flow_ids_passed = {call.kwargs["flow_id"] for call in enroll_uc.execute.await_args_list}
    assert flow_ids_passed == {flow_id_1, flow_id_2}
    # Verifica que customer_name e product_name são passados
    first_call_kwargs = enroll_uc.execute.await_args_list[0].kwargs
    assert "customer_name" in first_call_kwargs
    assert "product_name" in first_call_kwargs


@pytest.mark.asyncio
async def test_purchase_with_unknown_course_logs_warning_and_skips_enrollment(capsys):
    course_repo = AsyncMock()
    flow_repo = AsyncMock()
    enroll_uc = AsyncMock()
    course_repo.find_active_by_hubla_id.return_value = None

    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-1"

    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=AsyncMock(),
        scheduler=AsyncMock(),
        course_repo=course_repo,
        flow_repo=flow_repo,
        enroll_contact_uc=enroll_uc,
    )

    await handler.execute(fake_event(product_id="prod-unknown", product_name="Unknown"))

    enroll_uc.execute.assert_not_awaited()
    flow_repo.list_active_by_product.assert_not_called()
    # Course not found deve logar warning (structlog renderiza no stdout via ConsoleRenderer).
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert "course_not_found" in output
    assert "warning" in output.lower()


@pytest.mark.asyncio
async def test_purchase_with_known_course_but_no_flows_does_not_enroll():
    course_repo = AsyncMock()
    flow_repo = AsyncMock()
    enroll_uc = AsyncMock()
    course_repo.find_active_by_hubla_id.return_value = SimpleNamespace(id=uuid4(), name="Mkt 360")
    flow_repo.list_active_by_product.return_value = []

    contact_repo = AsyncMock()
    contact_repo.upsert.return_value = MagicMock(id="contact-1", phone="5511999990000")
    chatnexo = AsyncMock()
    chatnexo.get_open_conversation.return_value = "conv-1"

    handler = PurchaseHandler(
        contact_repo=contact_repo,
        chatnexo=chatnexo,
        access_case_repo=AsyncMock(),
        scheduler=AsyncMock(),
        course_repo=course_repo,
        flow_repo=flow_repo,
        enroll_contact_uc=enroll_uc,
    )
    await handler.execute(fake_event())
    enroll_uc.execute.assert_not_awaited()
