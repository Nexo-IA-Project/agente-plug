"""Testes do VariableResolver com Strategy Pattern."""

from __future__ import annotations

from shared.application.use_cases.followup.variable_resolver import (
    ConventionStrategy,
    EmptyFallbackStrategy,
    ExplicitBindingStrategy,
    ResolutionContext,
    VariableResolver,
)


def _ctx(**overrides) -> ResolutionContext:
    defaults: dict[str, object] = {
        "customer_name": "João Silva",
        "product_name": "MVS Shopee",
        "contact_phone": "+5511999990000",
        "contact_email": "joao@email.com",
    }
    defaults.update(overrides)
    return ResolutionContext(**defaults)  # type: ignore[arg-type]


# ─────────────────────────────────────────────────────────────────────────────
# ExplicitBindingStrategy
# ─────────────────────────────────────────────────────────────────────────────


def test_explicit_binding_customer_name():
    from shared.domain.value_objects.step_variable_binding import StepVariableBinding

    binding = StepVariableBinding.from_dict({"source": "customer_name"})
    out = ExplicitBindingStrategy().try_resolve("nome", binding, _ctx())
    assert out == "João Silva"


def test_explicit_binding_static_value():
    from shared.domain.value_objects.step_variable_binding import StepVariableBinding

    binding = StepVariableBinding.from_dict({"source": "static", "value": "Olá!"})
    out = ExplicitBindingStrategy().try_resolve("greeting", binding, _ctx())
    assert out == "Olá!"


def test_explicit_binding_none_returns_none():
    out = ExplicitBindingStrategy().try_resolve("name", None, _ctx())
    assert out is None


# ─────────────────────────────────────────────────────────────────────────────
# ConventionStrategy
# ─────────────────────────────────────────────────────────────────────────────


def test_convention_name_resolves_customer_name():
    out = ConventionStrategy().try_resolve("name", None, _ctx())
    assert out == "João Silva"


def test_convention_nome_caseinsensitive():
    out = ConventionStrategy().try_resolve("Nome", None, _ctx())
    assert out == "João Silva"


def test_convention_produto_resolves_product_name():
    out = ConventionStrategy().try_resolve("produto", None, _ctx())
    assert out == "MVS Shopee"


def test_convention_email_resolves_contact_email():
    out = ConventionStrategy().try_resolve("email", None, _ctx())
    assert out == "joao@email.com"


def test_convention_telefone_resolves_contact_phone():
    out = ConventionStrategy().try_resolve("telefone", None, _ctx())
    assert out == "+5511999990000"


def test_convention_unknown_var_returns_none():
    out = ConventionStrategy().try_resolve("cpf_do_aluno", None, _ctx())
    assert out is None


def test_convention_email_when_none_returns_empty_string():
    out = ConventionStrategy().try_resolve("email", None, _ctx(contact_email=None))
    assert out == ""


# ─────────────────────────────────────────────────────────────────────────────
# EmptyFallbackStrategy
# ─────────────────────────────────────────────────────────────────────────────


def test_empty_fallback_always_returns_empty():
    out = EmptyFallbackStrategy().try_resolve("cpf", None, _ctx())
    assert out == ""


# ─────────────────────────────────────────────────────────────────────────────
# VariableResolver.resolve_template_vars (orquestração)
# ─────────────────────────────────────────────────────────────────────────────


def test_resolve_uses_explicit_binding_when_configured():
    """User mapeou no FlowDrawer → ignora convenção."""
    resolved = VariableResolver().resolve_template_vars(
        var_names=["foo"],
        configured={"foo": {"source": "product_name"}},  # ← user mapeou foo → product
        ctx=_ctx(),
    )
    assert resolved == {"foo": "MVS Shopee"}


def test_resolve_falls_back_to_convention_when_unmapped():
    """User esqueceu de mapear → convenção pega via nome."""
    resolved = VariableResolver().resolve_template_vars(
        var_names=["name", "produto"],
        configured={},  # ← nada configurado
        ctx=_ctx(),
    )
    assert resolved == {"name": "João Silva", "produto": "MVS Shopee"}


def test_resolve_empty_for_unknown_var_no_exception():
    """Var desconhecida → string vazia (não levanta exceção)."""
    resolved = VariableResolver().resolve_template_vars(
        var_names=["aluno_cpf"],
        configured={},
        ctx=_ctx(),
    )
    assert resolved == {"aluno_cpf": ""}


def test_resolve_mixed_explicit_and_convention():
    """Combinação: 1 mapeada + 1 por convenção + 1 sem nada."""
    resolved = VariableResolver().resolve_template_vars(
        var_names=["greeting", "name", "cpf"],
        configured={"greeting": {"source": "static", "value": "Bem-vindo!"}},
        ctx=_ctx(),
    )
    assert resolved == {
        "greeting": "Bem-vindo!",  # via ExplicitBindingStrategy
        "name": "João Silva",  # via ConventionStrategy
        "cpf": "",  # via EmptyFallbackStrategy
    }


def test_resolve_empty_var_names_returns_empty_dict():
    resolved = VariableResolver().resolve_template_vars(
        var_names=[],
        configured={},
        ctx=_ctx(),
    )
    assert resolved == {}


def test_resolve_guarantees_param_count_for_meta_api():
    """Regressão do bug #132000: TODAS as vars do body precisam estar no
    resultado mesmo que vazias, senão Meta rejeita."""
    resolved = VariableResolver().resolve_template_vars(
        var_names=["name", "produto", "var_desconhecida"],
        configured={},
        ctx=_ctx(),
    )
    assert len(resolved) == 3
    assert set(resolved.keys()) == {"name", "produto", "var_desconhecida"}
