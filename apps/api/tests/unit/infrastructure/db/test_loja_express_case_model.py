# tests/unit/infrastructure/db/test_loja_express_case_model.py
from shared.adapters.db.models import LojaExpressCaseModel


def test_loja_express_case_model_tablename():
    assert LojaExpressCaseModel.__tablename__ == "loja_express_cases"


def test_loja_express_case_model_has_required_columns():
    cols = {c.name for c in LojaExpressCaseModel.__table__.columns}
    required = {
        "id", "account_id", "contact_id", "conversation_id",
        "purchase_id", "product_name", "student_email",
        "form_submitted", "loja_entregue", "status",
        "scheduled_job_d1_id", "scheduled_job_d3_id",
        "scheduled_job_d5_id", "scheduled_job_d7_id",
        "created_at", "updated_at",
    }
    assert required.issubset(cols)


def test_purchase_id_has_unique_constraint():
    unique_cols = set()
    for c in LojaExpressCaseModel.__table__.columns:
        if c.name == "purchase_id" and c.unique:
            unique_cols.add(c.name)
    assert "purchase_id" in unique_cols


def test_account_id_is_indexed():
    indexed_cols = {
        c.name
        for c in LojaExpressCaseModel.__table__.columns
        if c.index
    }
    assert "account_id" in indexed_cols
