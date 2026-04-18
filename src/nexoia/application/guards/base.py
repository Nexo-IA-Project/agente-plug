from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Guard(Protocol):
    """Marker interface for guard components."""
