from __future__ import annotations

from enum import StrEnum


class EscalationReason(StrEnum):
    """Catalog of the 8 escalation triggers defined in PRD 7.6."""

    HUMAN_REQUESTED_3X = "human_requested_3x"
    CHARGEBACK = "chargeback"
    BUG_PERSISTENT = "bug_persistent"
    MEDIA_MATERIAL_REQUEST = "media_material_request"
    PURCHASE_NOT_FOUND_3X = "purchase_not_found_3x"
    LEGAL_MENTION = "legal_mention"
    POST_DENY_3RD_INSISTENCE = "post_deny_3rd_insistence"
    LOJA_EXPRESS_BLOCKED = "loja_express_blocked"
