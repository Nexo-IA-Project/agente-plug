# tests/unit/domain/test_loja_express_case.py
from __future__ import annotations

from datetime import datetime

from nexoia.domain.entities.loja_express_case import (
    LojaExpressCase,
    LojaExpressCaseStatus,
)


def test_status_values_are_lowercase_strings():
    assert LojaExpressCaseStatus.AGUARDANDO_FORMULARIO == "aguardando_formulario"
    assert LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO == "lembrete_d1_enviado"
    assert LojaExpressCaseStatus.CHECK_D3_ENVIADO == "check_d3_enviado"
    assert LojaExpressCaseStatus.ALERTA_D5_ENVIADO == "alerta_d5_enviado"
    assert LojaExpressCaseStatus.PRAZO_CRITICO_D7 == "prazo_critico_d7"
    assert LojaExpressCaseStatus.ENTREGUE == "entregue"
    assert LojaExpressCaseStatus.ESCALADO == "escalado"


def test_loja_express_case_defaults():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express Pack",
        student_email="aluno@test.com",
    )
    assert case.account_id == 1
    assert case.contact_id == "5511999990000"
    assert case.conversation_id == "conv-1"
    assert case.purchase_id == "purchase-abc"
    assert case.product_name == "Loja Express Pack"
    assert case.student_email == "aluno@test.com"
    assert case.form_submitted is False
    assert case.loja_entregue is False
    assert case.status == LojaExpressCaseStatus.AGUARDANDO_FORMULARIO
    assert case.scheduled_job_d1_id is None
    assert case.scheduled_job_d3_id is None
    assert case.scheduled_job_d5_id is None
    assert case.scheduled_job_d7_id is None
    assert isinstance(case.id, str)
    assert len(case.id) == 36  # UUID format
    assert isinstance(case.created_at, datetime)
    assert isinstance(case.updated_at, datetime)


def test_loja_express_case_id_is_unique_per_instance():
    case1 = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-1",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    case2 = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-2",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    assert case1.id != case2.id


def test_loja_express_case_explicit_id_is_preserved():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express",
        student_email="a@b.com",
        id="my-fixed-id",
    )
    assert case.id == "my-fixed-id"


def test_loja_express_case_status_can_be_changed():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    case.status = LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO
    assert case.status == LojaExpressCaseStatus.LEMBRETE_D1_ENVIADO


def test_loja_express_case_job_ids_can_be_set():
    case = LojaExpressCase(
        account_id=1,
        contact_id="5511999990000",
        conversation_id="conv-1",
        purchase_id="purchase-abc",
        product_name="Loja Express",
        student_email="a@b.com",
    )
    case.scheduled_job_d1_id = "job-d1-id"
    case.scheduled_job_d3_id = "job-d3-id"
    case.scheduled_job_d5_id = "job-d5-id"
    case.scheduled_job_d7_id = "job-d7-id"
    assert case.scheduled_job_d1_id == "job-d1-id"
    assert case.scheduled_job_d3_id == "job-d3-id"
    assert case.scheduled_job_d5_id == "job-d5-id"
    assert case.scheduled_job_d7_id == "job-d7-id"
