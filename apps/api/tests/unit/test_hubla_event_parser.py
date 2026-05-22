from __future__ import annotations

import pytest

from shared.adapters.hubla.event_parser import HublaEventParser, ParsedPurchaseEvent

PAYLOAD = {
    "type": "subscription.activated",
    "version": "2.0.0",
    "event": {
        "product": {"id": "QaIlGtff9tlU94JjDKSq", "name": "MVS"},
        "products": [{"id": "QaIlGtff9tlU94JjDKSq", "name": "MVS"}],
        "subscription": {
            "id": "9a92f819-490b-4679-976d-820c1eadaf91",
            "payer": {
                "firstName": "Cleide",
                "lastName": "Barros",
                "document": "01810507812",
                "email": "test@example.com",
                "phone": "+5513997160759",
            },
            "activatedAt": "2026-05-02T02:59:25.256Z",
        },
        "user": {"id": "u1", "email": "test@example.com", "phone": "+5513997160759"},
    },
}


def test_parses_single_product():
    parsed = HublaEventParser().parse(PAYLOAD)
    assert isinstance(parsed, ParsedPurchaseEvent)
    assert parsed.purchase_id == "9a92f819-490b-4679-976d-820c1eadaf91"
    assert len(parsed.products) == 1
    assert parsed.products[0].hubla_id == "QaIlGtff9tlU94JjDKSq"
    assert parsed.payer_phone == "+5513997160759"
    assert parsed.payer_full_name == "Cleide Barros"
    assert parsed.activated_at.isoformat().startswith("2026-05-02T02:59:25")


def test_parses_multiple_products():
    payload = dict(PAYLOAD)
    payload["event"] = {
        **PAYLOAD["event"],
        "products": [
            {"id": "p1", "name": "P1"},
            {"id": "p2", "name": "P2"},
        ],
    }
    parsed = HublaEventParser().parse(payload)
    assert {p.hubla_id for p in parsed.products} == {"p1", "p2"}


def test_rejects_other_event_types():
    with pytest.raises(ValueError, match="unsupported event type"):
        HublaEventParser().parse({"type": "subscription.canceled", "event": {}})


def test_falls_back_to_event_product_if_products_missing():
    payload = dict(PAYLOAD)
    payload["event"] = {k: v for k, v in PAYLOAD["event"].items() if k != "products"}
    parsed = HublaEventParser().parse(payload)
    assert len(parsed.products) == 1
    assert parsed.products[0].hubla_id == "QaIlGtff9tlU94JjDKSq"
