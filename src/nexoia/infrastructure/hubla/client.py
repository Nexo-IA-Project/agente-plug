from __future__ import annotations

from nexoia.domain.ports.hubla_port import HublaPurchase, RefundResult


class HublaClient:
    # ⚠️  TODO CQ-R04: implement get_purchase_by_email — confirm Hubla endpoint
    # ⚠️  TODO CQ-R01: implement process_refund via Hubla API or Playwright

    async def get_purchase_by_email(self, email: str, account_id: int) -> HublaPurchase | None:
        raise NotImplementedError("HublaClient.get_purchase_by_email — ver CQ-R04")

    async def process_refund(self, purchase_id: str, reason: str) -> RefundResult:
        raise NotImplementedError("HublaClient.process_refund — ver CQ-R01")
