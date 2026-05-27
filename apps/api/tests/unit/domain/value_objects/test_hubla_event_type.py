from shared.domain.value_objects.hubla_event_type import (
    ALL_HUBLA_EVENT_TYPES,
    LEGACY_EVENT_TYPE_MAP,
    PURCHASE_EVENT_TYPES,
    is_valid_hubla_event_type,
    normalize_event_type,
)


def test_all_hubla_event_types_has_25_values() -> None:
    # 1 (lead) + 2 (customer) + 6 (subscription) + 6 (invoice) + 6 (smart_installment)
    # + 4 (refund_request) = 25 eventos. Bate com a doc oficial Hubla v2.
    assert len(ALL_HUBLA_EVENT_TYPES) == 25


def test_purchase_event_types_is_subset() -> None:
    assert PURCHASE_EVENT_TYPES <= ALL_HUBLA_EVENT_TYPES
    assert "subscription.activated" in PURCHASE_EVENT_TYPES


def test_is_valid_known() -> None:
    # Nomes técnicos oficiais Hubla v2.
    assert is_valid_hubla_event_type("subscription.activated") is True
    assert is_valid_hubla_event_type("customer.member_added") is True
    assert is_valid_hubla_event_type("invoice.payment_failed") is True
    assert is_valid_hubla_event_type("lead.abandoned_checkout") is True


def test_is_valid_unknown() -> None:
    # Nomes legados do enum antigo NÃO são mais válidos — caem em normalize_event_type.
    assert is_valid_hubla_event_type("member.access_granted") is False
    assert is_valid_hubla_event_type("lead.abandoned_cart") is False
    assert is_valid_hubla_event_type("foo.bar") is False
    assert is_valid_hubla_event_type("") is False


def test_categories_complete() -> None:
    """Garantia mínima de cobertura por categoria conforme doc Hubla v2."""
    expected_per_category = {
        "lead": 1,
        "customer": 2,
        "subscription": 6,
        "invoice": 6,
        "smart_installment": 6,
        "refund_request": 4,
    }
    for cat, count in expected_per_category.items():
        matching = [t for t in ALL_HUBLA_EVENT_TYPES if t.startswith(cat + ".")]
        assert len(matching) == count, (
            f"categoria {cat}: esperava {count}, achei {len(matching)}"
        )


def test_normalize_event_type_maps_legacy_to_canonical() -> None:
    # Cada nome legado mapeia pro nome correto Hubla v2.
    assert normalize_event_type("member.access_granted") == "customer.member_added"
    assert normalize_event_type("lead.abandoned_cart") == "lead.abandoned_checkout"
    assert normalize_event_type("subscription.expired") == "subscription.expiring"
    assert (
        normalize_event_type("subscription.auto_renewal_disabled")
        == "subscription.renewal_disabled"
    )
    assert normalize_event_type("invoice.payment_completed") == "invoice.payment_succeeded"
    assert normalize_event_type("installment.failed") == "smart_installment.aborted"


def test_normalize_event_type_passes_through_canonical_and_unknown() -> None:
    # Nome já correto passa adiante.
    assert normalize_event_type("subscription.activated") == "subscription.activated"
    # Nome desconhecido também passa (handler loga como hubla_unknown_event).
    assert normalize_event_type("foo.bar") == "foo.bar"
    assert normalize_event_type("") == ""


def test_legacy_map_targets_are_all_canonical() -> None:
    """Sanity: todo target do mapa LEGACY → CANONICAL é um tipo válido."""
    for legacy, canonical in LEGACY_EVENT_TYPE_MAP.items():
        assert canonical in ALL_HUBLA_EVENT_TYPES, (
            f"{legacy} aponta pra {canonical} que NÃO está no enum"
        )
        assert legacy not in ALL_HUBLA_EVENT_TYPES, (
            f"{legacy} ainda está no enum — deveria ter sido removido"
        )
