"""Testa o normalizador de payloads Hubla v1.0.0 → v2.0.0."""

from __future__ import annotations

from shared.adapters.hubla.v1_normalizer import (
    is_v1_payload,
    normalize_v1_payload,
)


def _v1_new_sale_payload() -> dict:
    """Payload real capturado em produção (Hubla v1.0.0, type=NewSale)."""
    return {
        "type": "NewSale",
        "version": "1.0.0",
        "event": {
            "paidAt": "2026-05-27T22:01:31.170Z",
            "userId": "94bwfCeHoWUcv3iiCTXLMxVH56E3",
            "groupId": "6AtRet4UQlB7T2hWDKlt",
            "sellerId": "2S29IZo4qsQ3H85ABpJ4BMKKn803",
            "userName": "Cristiane Oliveira dos santos",
            "createdAt": "2026-05-27T22:01:22.113Z",
            "groupName": "MVS | Máquina de Vendas: Shopee",
            "recurring": "one_time_purchased",
            "userEmail": "cristianeods2011@hotmail.com",
            "userPhone": "+5511951674825",
            "totalAmount": 368.64,
            "userDocument": "35117579836",
            "paymentMethod": "credit_card",
            "transactionId": "3eb9aba6-52b5-488e-b1d7-107d5c001f6d",
        },
    }


def test_is_v1_payload_detects_version_string() -> None:
    assert is_v1_payload({"version": "1.0.0"}) is True
    assert is_v1_payload({"version": "1.5.2"}) is True
    assert is_v1_payload({"version": "2.0.0"}) is False
    assert is_v1_payload({}) is False
    assert is_v1_payload({"version": ""}) is False


def test_v2_payload_passes_through_unchanged() -> None:
    v2 = {
        "type": "subscription.activated",
        "version": "2.0.0",
        "event": {"subscription": {"id": "sub-123"}},
    }
    assert normalize_v1_payload(v2) is v2  # mesma referência


def test_v1_new_sale_converts_to_subscription_activated() -> None:
    out = normalize_v1_payload(_v1_new_sale_payload())

    assert out["type"] == "subscription.activated"
    assert out["version"] == "1.0.0-normalized"

    sub = out["event"]["subscription"]
    assert sub["id"] == "3eb9aba6-52b5-488e-b1d7-107d5c001f6d"
    assert sub["activatedAt"] == "2026-05-27T22:01:31.170Z"
    assert sub["status"] == "active"
    assert sub["paymentMethod"] == "credit_card"

    payer = sub["payer"]
    assert payer["phone"] == "+5511951674825"
    assert payer["email"] == "cristianeods2011@hotmail.com"
    assert payer["firstName"] == "Cristiane"
    assert payer["lastName"] == "Oliveira dos santos"
    assert payer["document"] == "35117579836"

    # totalAmount 368.64 → 36864 cents
    amount = sub["lastInvoice"]["amount"]
    assert amount["totalCents"] == 36864
    assert amount["subtotalCents"] == 36864

    product = out["event"]["product"]
    assert product["id"] == "6AtRet4UQlB7T2hWDKlt"
    assert product["name"] == "MVS | Máquina de Vendas: Shopee"


def test_v1_renewal_also_activates_subscription() -> None:
    payload = _v1_new_sale_payload()
    payload["type"] = "Renewal"
    out = normalize_v1_payload(payload)
    assert out["type"] == "subscription.activated"
    assert out["event"]["subscription"]["status"] == "active"


def test_v1_canceled_maps_to_deactivated() -> None:
    payload = _v1_new_sale_payload()
    payload["type"] = "Canceled"
    out = normalize_v1_payload(payload)
    assert out["type"] == "subscription.deactivated"
    assert out["event"]["subscription"]["status"] == "canceled"


def test_v1_expired_maps_to_expired() -> None:
    payload = _v1_new_sale_payload()
    payload["type"] = "Expired"
    out = normalize_v1_payload(payload)
    assert out["type"] == "subscription.expired"
    assert out["event"]["subscription"]["status"] == "expired"


def test_v1_chargeback_maps_to_refunded() -> None:
    payload = _v1_new_sale_payload()
    payload["type"] = "ChargedBack"
    out = normalize_v1_payload(payload)
    assert out["type"] == "invoice.refunded"
    assert out["event"]["subscription"]["status"] == "chargeback"


def test_v1_refund_maps_to_refunded() -> None:
    payload = _v1_new_sale_payload()
    payload["type"] = "Refund"
    out = normalize_v1_payload(payload)
    assert out["type"] == "invoice.refunded"
    assert out["event"]["subscription"]["status"] == "refunded"


def test_v1_abandoned_cart_maps_to_lead() -> None:
    payload = _v1_new_sale_payload()
    payload["type"] = "AbandonedCart"
    out = normalize_v1_payload(payload)
    assert out["type"] == "lead.abandoned_cart"
    assert out["event"]["subscription"]["status"] == "abandoned"


def test_v1_with_unknown_type_passes_through() -> None:
    payload = _v1_new_sale_payload()
    payload["type"] = "SomeWeirdNewEventType"
    out = normalize_v1_payload(payload)
    # Mantém o type original — handler vai logar como hubla_unknown_event
    assert out is payload
    assert out["type"] == "SomeWeirdNewEventType"


def test_v1_userName_with_single_word_works() -> None:
    payload = _v1_new_sale_payload()
    payload["event"]["userName"] = "Madonna"
    out = normalize_v1_payload(payload)
    payer = out["event"]["subscription"]["payer"]
    assert payer["firstName"] == "Madonna"
    assert payer["lastName"] == ""


def test_v1_missing_userName_does_not_crash() -> None:
    payload = _v1_new_sale_payload()
    del payload["event"]["userName"]
    out = normalize_v1_payload(payload)
    payer = out["event"]["subscription"]["payer"]
    assert payer["firstName"] == ""
    assert payer["lastName"] == ""


def test_v1_missing_totalAmount_keeps_cents_None() -> None:
    payload = _v1_new_sale_payload()
    del payload["event"]["totalAmount"]
    out = normalize_v1_payload(payload)
    amount = out["event"]["subscription"]["lastInvoice"]["amount"]
    assert amount["totalCents"] is None


def test_v1_invalid_totalAmount_keeps_cents_None() -> None:
    payload = _v1_new_sale_payload()
    payload["event"]["totalAmount"] = "not a number"
    out = normalize_v1_payload(payload)
    amount = out["event"]["subscription"]["lastInvoice"]["amount"]
    assert amount["totalCents"] is None


def test_v1_totalAmount_zero_converts_to_zero_cents() -> None:
    payload = _v1_new_sale_payload()
    payload["event"]["totalAmount"] = 0
    out = normalize_v1_payload(payload)
    amount = out["event"]["subscription"]["lastInvoice"]["amount"]
    assert amount["totalCents"] == 0


def test_v1_float_rounding_handles_cent_precision() -> None:
    payload = _v1_new_sale_payload()
    payload["event"]["totalAmount"] = 99.995  # bordo do arredondamento
    out = normalize_v1_payload(payload)
    amount = out["event"]["subscription"]["lastInvoice"]["amount"]
    # 99.995 * 100 = 9999.5 → round → 10000
    assert amount["totalCents"] == 10000
