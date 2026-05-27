from shared.domain.value_objects.hubla_event_type import (
    ALL_HUBLA_EVENT_TYPES,
    PURCHASE_EVENT_TYPES,
    is_valid_hubla_event_type,
)


def test_all_hubla_event_types_has_25_values() -> None:
    # Nota: o título da task fala em "24 valores" mas a enumeração explicita
    # 1 (lead) + 2 (member) + 6 (subscription) + 6 (invoice) + 6 (installment)
    # + 4 (refund_request) = 25 eventos. Mantemos os 25 listados; o test_categories_complete
    # garante a cobertura por categoria.
    assert len(ALL_HUBLA_EVENT_TYPES) == 25


def test_purchase_event_types_is_subset() -> None:
    assert PURCHASE_EVENT_TYPES <= ALL_HUBLA_EVENT_TYPES
    assert "subscription.activated" in PURCHASE_EVENT_TYPES


def test_is_valid_known() -> None:
    assert is_valid_hubla_event_type("subscription.activated") is True
    assert is_valid_hubla_event_type("member.access_granted") is True
    assert is_valid_hubla_event_type("invoice.payment_failed") is True


def test_is_valid_unknown() -> None:
    assert is_valid_hubla_event_type("subscription.expiring") is False  # nome antigo
    assert is_valid_hubla_event_type("foo.bar") is False
    assert is_valid_hubla_event_type("") is False


def test_categories_complete() -> None:
    """Garantia mínima de cobertura por categoria."""
    expected_per_category = {
        "lead": 1,
        "member": 2,
        "subscription": 6,
        "invoice": 6,
        "installment": 6,
        "refund_request": 4,
    }
    for cat, count in expected_per_category.items():
        matching = [t for t in ALL_HUBLA_EVENT_TYPES if t.startswith(cat + ".")]
        assert len(matching) == count, f"categoria {cat}: esperava {count}, achei {len(matching)}"
