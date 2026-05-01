from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class LojaExpressCaseStatus(StrEnum):
    AGUARDANDO_FORMULARIO = "aguardando_formulario"
    LEMBRETE_D1_ENVIADO   = "lembrete_d1_enviado"
    CHECK_D3_ENVIADO      = "check_d3_enviado"
    ALERTA_D5_ENVIADO     = "alerta_d5_enviado"
    PRAZO_CRITICO_D7      = "prazo_critico_d7"
    ENTREGUE              = "entregue"
    ESCALADO              = "escalado"


@dataclass
class LojaExpressCase:
    account_id: int
    contact_id: str
    conversation_id: str
    purchase_id: str
    product_name: str
    student_email: str
    id: str = field(default_factory=lambda: str(uuid4()))
    form_submitted: bool = False
    loja_entregue: bool = False
    status: LojaExpressCaseStatus = LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    scheduled_job_d1_id: str | None = None
    scheduled_job_d3_id: str | None = None
    scheduled_job_d5_id: str | None = None
    scheduled_job_d7_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
