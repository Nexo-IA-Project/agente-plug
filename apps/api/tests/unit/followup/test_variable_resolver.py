from __future__ import annotations

from shared.application.use_cases.onboarding.variable_resolver import (
    ResolutionContext,
    VariableResolver,
)
from shared.domain.value_objects.step_variable_binding import StepVariableBinding


def ctx(**kwargs):
    defaults = {
        "customer_name": "Fabio",
        "product_name": "Marketing 360",
        "contact_phone": "+5511999999999",
        "contact_email": "fabio@example.com",
    }
    defaults.update(kwargs)
    return ResolutionContext(**defaults)


def test_resolves_customer_name():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="customer_name"), ctx()) == "Fabio"


def test_resolves_product_name():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="product_name"), ctx()) == "Marketing 360"


def test_resolves_contact_phone():
    resolver = VariableResolver()
    assert resolver.resolve(StepVariableBinding(source="contact_phone"), ctx()) == "+5511999999999"


def test_resolves_contact_email():
    resolver = VariableResolver()
    assert (
        resolver.resolve(StepVariableBinding(source="contact_email"), ctx()) == "fabio@example.com"
    )


def test_resolves_static():
    resolver = VariableResolver()
    binding = StepVariableBinding(source="static", value="promoção limitada")
    assert resolver.resolve(binding, ctx()) == "promoção limitada"


def test_resolves_email_missing_returns_empty_string():
    resolver = VariableResolver()
    assert (
        resolver.resolve(StepVariableBinding(source="contact_email"), ctx(contact_email=None)) == ""
    )


def test_resolve_all_returns_dict_keyed_by_var_name():
    resolver = VariableResolver()
    raw = {
        "1": {"source": "customer_name"},
        "2": {"source": "static", "value": "Olá"},
    }
    out = resolver.resolve_all(raw, ctx())
    assert out == {"1": "Fabio", "2": "Olá"}


def test_resolve_all_skips_unknown_keys_silently():
    resolver = VariableResolver()
    out = resolver.resolve_all({}, ctx())
    assert out == {}
