from datetime import UTC, datetime
from uuid import uuid4

from shared.domain.events.handoff_requested import HandoffRequested
from shared.domain.events.idle_detected import IdleDetected, IdleStage
from shared.domain.events.message_received import MessageReceived
from shared.domain.events.purchase_received import PurchaseReceived


def test_purchase_received_fields() -> None:
    event = PurchaseReceived(
        purchase_id="p-1",
        account_id=uuid4(),
        contact_name="Ana",
        contact_email="ana@test",
        contact_phone="+5511999",
        product="Curso X",
        amount_brl=19700,
        occurred_at=datetime.now(UTC),
    )
    assert event.purchase_id == "p-1"


def test_message_received_fields() -> None:
    event = MessageReceived(
        account_id=uuid4(),
        conversation_id=uuid4(),
        contact_id=uuid4(),
        chatnexo_message_id="m-1",
        text="ola",
        occurred_at=datetime.now(UTC),
    )
    assert event.text == "ola"


def test_handoff_requested_fields() -> None:
    event = HandoffRequested(
        conversation_id=uuid4(),
        reason="legal_mention",
        silent=True,
    )
    assert event.silent is True


def test_idle_detected_fields() -> None:
    event = IdleDetected(
        conversation_id=uuid4(),
        stage=IdleStage.PING,
    )
    assert event.stage == IdleStage.PING
