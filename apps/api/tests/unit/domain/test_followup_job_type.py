from shared.domain.entities.scheduled_job import JobType


def test_followup_step_job_type_value():
    assert JobType.FOLLOWUP_STEP == "followup_step"


def test_followup_step_is_lowercase():
    assert JobType.FOLLOWUP_STEP.lower() == JobType.FOLLOWUP_STEP
