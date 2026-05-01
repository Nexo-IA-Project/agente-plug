from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus


def test_access_case_default_student_cpf_is_none():
    case = AccessCase(account_id=1, contact_id="c", conversation_id="cv",
                      purchase_id="p", product_name="P")
    assert case.student_cpf is None


def test_access_case_default_search_attempts_is_zero():
    case = AccessCase(account_id=1, contact_id="c", conversation_id="cv",
                      purchase_id="p", product_name="P")
    assert case.search_attempts == 0


def test_access_case_with_student_cpf():
    case = AccessCase(account_id=1, contact_id="c", conversation_id="cv",
                      purchase_id="p", product_name="Curso",
                      student_cpf="123.456.789-00")
    assert case.student_cpf == "123.456.789-00"


def test_access_case_search_attempts_mutable():
    case = AccessCase(account_id=1, contact_id="c", conversation_id="cv",
                      purchase_id="p", product_name="Curso")
    case.search_attempts = 2
    assert case.search_attempts == 2


def test_access_case_reactive_status_enum_values():
    assert AccessCaseStatus.REACTIVE_LINK_SENT == "reactive_link_sent"
    assert AccessCaseStatus.REACTIVE_ESCALATED == "reactive_escalated"


def test_access_case_existing_status_preserved():
    assert AccessCaseStatus.PENDING == "pending"
    assert AccessCaseStatus.LINK_SENT == "link_sent_proativo"
    assert AccessCaseStatus.ACCESSED == "accessed"
    assert AccessCaseStatus.REMINDED_D1 == "reminded_d1"
    assert AccessCaseStatus.ESCALATED == "escalated"
