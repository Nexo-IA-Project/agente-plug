import pytest
from pydantic import ValidationError

from interface.http.schemas.onboarding import (
    HUBLA_EVENT_TYPES,
    CreateFlowRequest,
    UpdateFlowRequest,
)


def test_hubla_event_types_constant_has_25_values():
    """Após Hubla v2 (Task 4): catálogo expandido para 25 eventos oficiais.

    Inclui renomes: lead.abandoned → lead.abandoned_cart,
    subscription.expiring → subscription.expired.
    """
    assert len(HUBLA_EVENT_TYPES) == 25
    assert "subscription.activated" in HUBLA_EVENT_TYPES
    assert "lead.abandoned_cart" in HUBLA_EVENT_TYPES
    assert "subscription.expired" in HUBLA_EVENT_TYPES
    assert "member.access_granted" in HUBLA_EVENT_TYPES
    # nomes antigos NÃO devem mais aparecer
    assert "lead.abandoned" not in HUBLA_EVENT_TYPES
    assert "subscription.expiring" not in HUBLA_EVENT_TYPES


def test_create_flow_request_accepts_valid_trigger():
    for event_type in HUBLA_EVENT_TYPES:
        req = CreateFlowRequest(
            name="Test",
            product_id="00000000-0000-0000-0000-000000000001",
            trigger_event_type=event_type,
        )
        assert req.trigger_event_type == event_type


def test_create_flow_request_rejects_unknown_trigger():
    with pytest.raises(ValidationError):
        CreateFlowRequest(
            name="Test",
            product_id="00000000-0000-0000-0000-000000000001",
            trigger_event_type="random.garbage",
        )


def test_create_flow_request_default_is_subscription_activated():
    req = CreateFlowRequest(
        name="Test",
        product_id="00000000-0000-0000-0000-000000000001",
    )
    assert req.trigger_event_type == "subscription.activated"


def test_update_flow_request_allows_none():
    req = UpdateFlowRequest(trigger_event_type=None)
    assert req.trigger_event_type is None


def test_update_flow_request_rejects_unknown_trigger():
    with pytest.raises(ValidationError):
        UpdateFlowRequest(trigger_event_type="lol.invalid")
