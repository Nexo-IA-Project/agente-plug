"""Resolver de variáveis de template do follow-up.

Aplica Strategy Pattern + Chain of Responsibility: para cada variável `{{var}}`
encontrada no body do template, percorre uma lista ordenada de estratégias e
usa a primeira que conseguir resolver. Isso permite estender o comportamento
(adicionar novas convenções, integrar novas fontes de dados) sem mudar o
chamador.

Estratégias em ordem:
  1. ExplicitBindingStrategy — usa o binding configurado pelo user no FlowDrawer
  2. ConventionStrategy      — auto-detect por nome (`{{name}}` → customer_name)
  3. EmptyFallbackStrategy   — último recurso: string vazia + warning log

Princípios SOLID respeitados:
  - SRP: cada strategy faz UMA coisa
  - OCP: novas estratégias são adicionadas sem modificar VariableResolver
  - LSP: todas as strategies seguem o mesmo Protocol VariableStrategy
  - ISP: o Protocol expõe APENAS o método try_resolve
  - DIP: VariableResolver depende da abstração VariableStrategy, não de impls
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import structlog

from shared.domain.value_objects.step_variable_binding import StepVariableBinding

log = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Contexto de resolução
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    """Snapshot dos dados disponíveis pra preencher variáveis do template."""

    customer_name: str
    product_name: str
    contact_phone: str
    contact_email: str | None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy Protocol
# ─────────────────────────────────────────────────────────────────────────────


class VariableStrategy(Protocol):
    """Estratégia de resolução de uma variável.

    Retorna o valor resolvido OU None se não souber resolver. None sinaliza
    "passa pra próxima strategy" (chain of responsibility).
    """

    def try_resolve(
        self,
        var_name: str,
        configured: StepVariableBinding | None,
        ctx: ResolutionContext,
    ) -> str | None: ...


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 1: Binding explícito do FlowDrawer
# ─────────────────────────────────────────────────────────────────────────────


class ExplicitBindingStrategy:
    """Resolve via configuração explícita do user (StepVariableBinding)."""

    def try_resolve(
        self,
        var_name: str,
        configured: StepVariableBinding | None,
        ctx: ResolutionContext,
    ) -> str | None:
        _ = var_name  # não usa — chave já foi resolvida pelo caller
        if configured is None:
            return None

        if configured.source == "static":
            return configured.value or ""
        if configured.source == "customer_name":
            return ctx.customer_name
        if configured.source == "product_name":
            return ctx.product_name
        if configured.source == "contact_phone":
            return ctx.contact_phone
        if configured.source == "contact_email":
            return ctx.contact_email or ""

        log.warning(
            "variable_resolver_unknown_source",
            source=configured.source,
        )
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 2: Convenção de nome
# ─────────────────────────────────────────────────────────────────────────────


class ConventionStrategy:
    """Auto-detect por convenção de nome (case-insensitive, sem acento).

    Mapeamento `nome_da_var → função(ctx) → str`. Adicionar novas convenções
    aqui — qualquer nome listado em uma tupla vira alias do mesmo getter.
    """

    _CONVENTIONS: tuple[tuple[tuple[str, ...], str], ...] = (
        # Aliases de customer_name
        (
            ("name", "nome", "customer", "cliente", "first_name", "firstname"),
            "customer_name",
        ),
        # Aliases de product_name
        (
            ("produto", "product", "curso", "course", "product_name"),
            "product_name",
        ),
        # Aliases de contact_email
        (
            ("email", "e-mail", "mail", "contact_email"),
            "contact_email",
        ),
        # Aliases de contact_phone
        (
            ("phone", "telefone", "whatsapp", "celular", "contact_phone"),
            "contact_phone",
        ),
    )

    def try_resolve(
        self,
        var_name: str,
        _configured: StepVariableBinding | None,
        ctx: ResolutionContext,
    ) -> str | None:
        key = var_name.lower().strip()
        for aliases, target in self._CONVENTIONS:
            if key in aliases:
                value = self._get_from_ctx(target, ctx)
                log.info(
                    "variable_resolver_convention_match",
                    var_name=var_name,
                    convention=target,
                )
                return value
        return None

    @staticmethod
    def _get_from_ctx(target: str, ctx: ResolutionContext) -> str:
        if target == "customer_name":
            return ctx.customer_name
        if target == "product_name":
            return ctx.product_name
        if target == "contact_phone":
            return ctx.contact_phone
        if target == "contact_email":
            return ctx.contact_email or ""
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Strategy 3: Empty fallback (último recurso)
# ─────────────────────────────────────────────────────────────────────────────


class EmptyFallbackStrategy:
    """Último recurso: emite warning e retorna string vazia.

    Isso evita que o disparo falhe com Meta error #132000 (número de
    parâmetros não bate) — Meta exige TODAS as variáveis do body.
    """

    def try_resolve(
        self,
        var_name: str,
        _configured: StepVariableBinding | None,
        _ctx: ResolutionContext,
    ) -> str | None:
        log.warning(
            "variable_resolver_unresolved",
            var_name=var_name,
            hint="Mapear no FlowDrawer ou usar nome convencional (name, produto, email, phone)",
        )
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Resolver (orquestrador das strategies)
# ─────────────────────────────────────────────────────────────────────────────


_DEFAULT_STRATEGIES: tuple[VariableStrategy, ...] = (
    ExplicitBindingStrategy(),
    ConventionStrategy(),
    EmptyFallbackStrategy(),
)


class VariableResolver:
    """Resolve variáveis encontradas no body de um template Meta.

    Use `resolve_template_vars` (novo, completo). O método `resolve_all` antigo
    foi mantido por backward-compat mas resolve APENAS variáveis com binding
    configurado — não detecta vars do body. Prefira `resolve_template_vars`.
    """

    def __init__(self, strategies: tuple[VariableStrategy, ...] | None = None) -> None:
        self._strategies = strategies or _DEFAULT_STRATEGIES

    def resolve_template_vars(
        self,
        var_names: list[str],
        configured: dict[str, object],
        ctx: ResolutionContext,
    ) -> dict[str, str]:
        """Resolve TODAS as variáveis presentes no body do template.

        Args:
            var_names: nomes de variáveis extraídos via regex do body
                       (ex: `re.findall(r'\\{\\{(\\w+)\\}\\}', body)`)
            configured: bindings configurados no FlowDrawer
                        (ex: {"name": {"source": "customer_name"}})
            ctx: snapshot dos dados do contato/produto

        Returns:
            Dict {var_name: valor resolvido}. Todas as vars terão valor
            (mesmo que string vazia — garante match de parâmetros na Meta API).
        """
        out: dict[str, str] = {}
        for var_name in var_names:
            cfg_raw = configured.get(var_name)
            cfg_binding: StepVariableBinding | None = (
                StepVariableBinding.from_dict(cfg_raw) if isinstance(cfg_raw, dict) else None
            )

            for strategy in self._strategies:
                value = strategy.try_resolve(var_name, cfg_binding, ctx)
                if value is not None:
                    out[var_name] = value
                    break
            else:
                # Nenhuma strategy resolveu — segurança extra (não deveria acontecer
                # porque EmptyFallbackStrategy sempre retorna string vazia, não None).
                out[var_name] = ""
        return out

    # ─── Backward-compat ────────────────────────────────────────────────────

    def resolve(self, binding: StepVariableBinding, ctx: ResolutionContext) -> str:
        """Legacy — resolve um único binding. Use resolve_template_vars."""
        result = ExplicitBindingStrategy().try_resolve(
            var_name="<legacy>", configured=binding, ctx=ctx
        )
        if result is not None:
            return result
        raise ValueError(f"unknown source: {binding.source}")

    def resolve_all(self, raw: dict, ctx: ResolutionContext) -> dict[str, str]:
        """Legacy — resolve apenas vars com binding configurado.

        NÃO detecta vars do body — pode causar erro #132000 na Meta API se o
        template tiver vars não mapeadas. Use resolve_template_vars.
        """
        out: dict[str, str] = {}
        for key, raw_binding in raw.items():
            binding = StepVariableBinding.from_dict(raw_binding)
            out[key] = self.resolve(binding, ctx)
        return out
