# src/nexoia/infrastructure/loja_express/stub_client.py
from __future__ import annotations

from shared.domain.ports.loja_express_port import StoreStatus


class LojaExpressStubClient:
    """Stub implementation — raises NotImplementedError until real adapter is built."""

    async def is_form_submitted(self, case_id: str) -> bool:
        raise NotImplementedError(
            "LojaExpressStubClient.is_form_submitted: real adapter not implemented yet"
        )

    async def get_store_status(self, case_id: str) -> StoreStatus:
        raise NotImplementedError(
            "LojaExpressStubClient.get_store_status: real adapter not implemented yet"
        )
