from __future__ import annotations

from dataclasses import dataclass

from shared.domain.value_objects.step_variable_binding import StepVariableBinding


@dataclass(frozen=True, slots=True)
class ResolutionContext:
    customer_name: str
    product_name: str
    contact_phone: str
    contact_email: str | None


class VariableResolver:
    def resolve(self, binding: StepVariableBinding, ctx: ResolutionContext) -> str:
        if binding.source == "static":
            return binding.value or ""
        if binding.source == "customer_name":
            return ctx.customer_name
        if binding.source == "product_name":
            return ctx.product_name
        if binding.source == "contact_phone":
            return ctx.contact_phone
        if binding.source == "contact_email":
            return ctx.contact_email or ""
        raise ValueError(f"unknown source: {binding.source}")

    def resolve_all(self, raw: dict, ctx: ResolutionContext) -> dict[str, str]:
        out: dict[str, str] = {}
        for key, raw_binding in raw.items():
            binding = StepVariableBinding.from_dict(raw_binding)
            out[key] = self.resolve(binding, ctx)
        return out
