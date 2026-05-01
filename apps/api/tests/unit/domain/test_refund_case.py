from shared.domain.entities.refund_case import RefundCase, RefundCaseStatus


def test_refund_case_defaults():
    case = RefundCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        student_email="aluno@g2.com",
    )
    assert case.status == RefundCaseStatus.COLLECTING
    assert case.offers_made == []
    assert case.offer_accepted is False
    assert case.within_deadline is None
    assert case.is_duplicate_purchase is False
    assert case.refund_processed_this_turn is False
    assert case.id is not None


def test_refund_case_status_values():
    assert RefundCaseStatus.COLLECTING == "collecting"
    assert RefundCaseStatus.REFUNDED == "refunded"
    assert RefundCaseStatus.DENIED == "denied"
    assert RefundCaseStatus.IN_RETENTION == "in_retention"
    assert RefundCaseStatus.ESCALATED == "escalated"
