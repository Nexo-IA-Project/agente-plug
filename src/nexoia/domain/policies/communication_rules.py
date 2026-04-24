# src/nexoia/domain/policies/communication_rules.py (stub — full impl in Task 2)
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    correction_hint: str = ""

class CommunicationRules:
    def validate(self, content: str) -> ValidationResult:
        return ValidationResult(ok=True)
