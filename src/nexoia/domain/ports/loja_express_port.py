# src/nexoia/domain/ports/loja_express_port.py
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LojaExpressPort(Protocol):
    async def is_form_submitted(self, case_id: str) -> bool:
        """Return True if the student submitted the enrollment form."""
        ...

    async def get_store_status(self, case_id: str) -> str:
        """Return delivery status: 'delivered' | 'pending' | 'processing'."""
        ...
