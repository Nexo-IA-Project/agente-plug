import uuid
from types import SimpleNamespace

from shared.application.use_cases.onboarding.diff_flow_steps import compute_diff
from shared.domain.entities.onboarding import EnrollmentStepStatus


def _flow_step(id_, position=1, delay=24, template="t", text=None, vars=None):
    return SimpleNamespace(
        id=id_,
        position=position,
        delay_from_purchase_minutes=delay,
        meta_template_name=template,
        message_text=text,
        template_variables=vars or {},
    )


def _enr_step(
    flow_step_id,
    position=1,
    delay=24,
    status=EnrollmentStepStatus.PENDING,
    template="t",
    text=None,
    vars=None,
):
    return SimpleNamespace(
        id=uuid.uuid4(),
        flow_step_id=flow_step_id,
        position=position,
        delay_from_purchase_minutes=delay,
        status=status,
        meta_template_name=template,
        message_text=text,
        template_variables=vars or {},
        scheduled_job_id=uuid.uuid4(),
    )


def test_diff_detects_new_step():
    fs_id = uuid.uuid4()
    diff = compute_diff([_flow_step(fs_id)], [])
    assert len(diff.to_add) == 1
    assert diff.to_add[0].id == fs_id


def test_diff_detects_delay_change_reschedule():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, delay=48)]
    enr_steps = [_enr_step(fs_id, delay=24)]
    diff = compute_diff(flow_steps, enr_steps)
    assert len(diff.to_reschedule) == 1
    assert diff.to_update_content == []


def test_diff_detects_content_only_change():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, delay=24, template="t2")]
    enr_steps = [_enr_step(fs_id, delay=24, template="t1")]
    diff = compute_diff(flow_steps, enr_steps)
    assert len(diff.to_update_content) == 1
    assert diff.to_reschedule == []


def test_diff_skips_sent_steps():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id, delay=48, template="t2")]
    enr_steps = [_enr_step(fs_id, delay=24, status=EnrollmentStepStatus.SENT)]
    diff = compute_diff(flow_steps, enr_steps)
    assert diff.to_reschedule == []
    assert diff.to_update_content == []


def test_diff_detects_removed_step():
    enr_steps = [_enr_step(uuid.uuid4())]
    diff = compute_diff([], enr_steps)
    assert len(diff.to_cancel) == 1


def test_diff_is_idempotent_on_unchanged():
    fs_id = uuid.uuid4()
    flow_steps = [_flow_step(fs_id)]
    enr_steps = [_enr_step(fs_id)]
    diff = compute_diff(flow_steps, enr_steps)
    assert diff.to_add == []
    assert diff.to_reschedule == []
    assert diff.to_update_content == []
    assert diff.to_cancel == []
