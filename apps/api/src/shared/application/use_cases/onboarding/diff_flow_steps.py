from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from shared.domain.entities.followup import EnrollmentStepStatus


@dataclass(frozen=True)
class Diff:
    to_add: list[Any] = field(default_factory=list)
    to_reschedule: list[tuple[Any, Any]] = field(default_factory=list)
    to_update_content: list[tuple[Any, Any]] = field(default_factory=list)
    to_cancel: list[Any] = field(default_factory=list)


def compute_diff(flow_steps, enrollment_steps) -> Diff:
    """Diff entre flow.steps (atual) e enrollment.steps (existente).

    Identidade: enrollment_step.flow_step_id == flow_step.id.
    - Step novo no flow → to_add
    - Step PENDING com delay alterado → to_reschedule (também aplica conteúdo novo)
    - Step PENDING com só conteúdo alterado → to_update_content (job intocado)
    - Step PENDING que sumiu do flow → to_cancel
    - Step SENT/FAILED/CANCELLED → imutável
    """
    enr_by_flow_step = {
        es.flow_step_id: es for es in enrollment_steps if es.flow_step_id is not None
    }
    to_add, to_reschedule, to_update_content, to_cancel = [], [], [], []

    for fs in flow_steps:
        enr = enr_by_flow_step.get(fs.id)
        if enr is None:
            to_add.append(fs)
            continue
        if enr.status != EnrollmentStepStatus.PENDING:
            continue

        delay_changed = enr.delay_from_purchase_minutes != fs.delay_from_purchase_minutes
        content_changed = (
            enr.meta_template_name != fs.meta_template_name
            or enr.message_text != fs.message_text
            or enr.template_variables != fs.template_variables
        )
        if delay_changed:
            to_reschedule.append((enr, fs))
        elif content_changed:
            to_update_content.append((enr, fs))

    flow_step_ids = {fs.id for fs in flow_steps}
    for es in enrollment_steps:
        if (
            es.flow_step_id is not None
            and es.flow_step_id not in flow_step_ids
            and es.status == EnrollmentStepStatus.PENDING
        ):
            to_cancel.append(es)

    return Diff(
        to_add=to_add,
        to_reschedule=to_reschedule,
        to_update_content=to_update_content,
        to_cancel=to_cancel,
    )
