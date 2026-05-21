from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

VariableSource = Literal[
    "customer_name", "product_name", "contact_phone", "contact_email", "static"
]


@dataclass(frozen=True, slots=True)
class StepVariableBinding:
    source: VariableSource
    value: str | None = None  # obrigatório se source == "static"

    @classmethod
    def from_dict(cls, raw: dict) -> StepVariableBinding:
        source = raw.get("source")
        if source not in (
            "customer_name",
            "product_name",
            "contact_phone",
            "contact_email",
            "static",
        ):
            raise ValueError(f"invalid source: {source!r}")
        value = raw.get("value")
        if source == "static" and not value:
            raise ValueError("static binding requires non-empty value")
        if source != "static" and value is not None:
            raise ValueError("non-static binding must not include value")
        return cls(source=source, value=value)

    def to_dict(self) -> dict:
        d: dict = {"source": self.source}
        if self.value is not None:
            d["value"] = self.value
        return d
