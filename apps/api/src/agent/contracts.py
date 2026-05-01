"""Lightweight result types used across agent skills and use-cases."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Ok:
    """Successful result carrying an optional payload."""

    value: Any = None


@dataclass(frozen=True)
class Err:
    """Failed result carrying a human-readable reason."""

    reason: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Precondition:
    """A guard check result — either passed or blocked with a message."""

    passed: bool
    block_message: str = ""

    @classmethod
    def ok(cls) -> "Precondition":
        return cls(passed=True)

    @classmethod
    def block(cls, message: str) -> "Precondition":
        return cls(passed=False, block_message=message)
