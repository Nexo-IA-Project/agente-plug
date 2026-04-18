from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus


def test_access_case_default_status_is_pending():
    case = AccessCase(
        account_id=1,
        contact_id="contact-123",
        conversation_id="conv-456",
        purchase_id="purchase-789",
        product_name="Curso Python",
    )
    assert case.status == AccessCaseStatus.PENDING
    assert case.access_confirmed is False
    assert case.scheduled_d1_job_id is None
    assert case.access_link is None


def test_access_case_has_uuid_id():
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="P",
    )
    assert len(case.id) == 36  # UUID format "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"


def test_access_case_status_enum_string_values():
    assert AccessCaseStatus.PENDING == "pending"
    assert AccessCaseStatus.LINK_SENT == "link_sent_proativo"
    assert AccessCaseStatus.ACCESSED == "accessed"
    assert AccessCaseStatus.REMINDED_D1 == "reminded_d1"
    assert AccessCaseStatus.ESCALATED == "escalated"


def test_access_case_with_link():
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p",
        product_name="Curso",
        access_link="https://cademi.com.br/auto-login/abc123",
        status=AccessCaseStatus.LINK_SENT,
    )
    assert case.access_link == "https://cademi.com.br/auto-login/abc123"
    assert case.status == AccessCaseStatus.LINK_SENT
