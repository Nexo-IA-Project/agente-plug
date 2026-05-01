from datetime import UTC, datetime, timedelta
from uuid import uuid4

from shared.domain.entities.conversation import Conversation, ConversationStatus


def _make_conv(last_activity: datetime | None = None) -> Conversation:
    return Conversation(
        id=uuid4(),
        account_id=uuid4(),
        contact_id=uuid4(),
        chatnexo_conversation_id=123,
        status=ConversationStatus.ACTIVE,
        last_activity_at=last_activity or datetime.now(UTC),
        window_expires_at=datetime.now(UTC) + timedelta(hours=24),
        handoff_reason=None,
    )


def test_conversation_is_inside_meta_window_when_not_expired() -> None:
    conv = _make_conv()
    assert conv.is_inside_meta_window(now=datetime.now(UTC)) is True


def test_conversation_outside_window_when_expired() -> None:
    conv = _make_conv()
    now = conv.window_expires_at + timedelta(seconds=1)
    assert conv.is_inside_meta_window(now=now) is False


def test_conversation_can_send_free_text_only_if_active_and_in_window() -> None:
    conv = _make_conv()
    assert conv.can_send_free_text(now=datetime.now(UTC)) is True

    conv_handed = _make_conv()
    conv_handed.status = ConversationStatus.HANDED_OFF
    assert conv_handed.can_send_free_text(now=datetime.now(UTC)) is False


def test_mark_handed_off_sets_status_and_reason() -> None:
    conv = _make_conv()
    conv.mark_handed_off(reason="legal_mention")
    assert conv.status == ConversationStatus.HANDED_OFF
    assert conv.handoff_reason == "legal_mention"
