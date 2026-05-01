from nexoia.infrastructure.db.models import RefundCaseModel


def test_refund_case_model_tablename():
    assert RefundCaseModel.__tablename__ == "refund_cases"


def test_refund_case_model_has_required_columns():
    cols = {c.name for c in RefundCaseModel.__table__.columns}
    required = {
        "id", "account_id", "contact_id", "conversation_id",
        "student_email", "status", "offers_made", "offer_accepted",
        "is_duplicate_purchase", "refund_processed_this_turn",
        "created_at", "updated_at",
    }
    assert required.issubset(cols)
