# tests/unit/domain/test_loja_express_job_types.py
from nexoia.domain.entities.scheduled_job import JobType


def test_loja_express_d1_value():
    assert JobType.LOJA_EXPRESS_D1 == "loja_express_d1"


def test_loja_express_d3_value():
    assert JobType.LOJA_EXPRESS_D3 == "loja_express_d3"


def test_loja_express_d5_value():
    assert JobType.LOJA_EXPRESS_D5 == "loja_express_d5"


def test_loja_express_d7_value():
    assert JobType.LOJA_EXPRESS_D7 == "loja_express_d7"


def test_all_job_types_are_lowercase():
    for jt in JobType:
        assert jt == jt.lower(), f"JobType.{jt.name} value is not lowercase: {jt.value!r}"
