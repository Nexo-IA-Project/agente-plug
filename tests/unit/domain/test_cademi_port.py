import pytest

from nexoia.domain.errors import CademiError
from nexoia.domain.ports.cademi_port import CademiStudent


def test_cademi_student_is_frozen():
    student = CademiStudent(id="s1", name="João Silva", email="joao@email.com", phone="+5511999999999")
    with pytest.raises(Exception):
        student.name = "Outro nome"  # type: ignore[misc]


def test_cademi_student_without_phone():
    student = CademiStudent(id="s1", name="Maria", email="maria@email.com", phone=None)
    assert student.phone is None


def test_cademi_error_is_domain_error():
    from nexoia.domain.errors import DomainError
    err = CademiError("Connection timeout")
    assert isinstance(err, DomainError)
    assert str(err) == "Connection timeout"


def test_fake_cademi_satisfies_port():
    from tests.fakes.fake_cademi_client import FakeCademiClient
    client = FakeCademiClient()
    assert isinstance(client, FakeCademiClient)
    assert hasattr(client, "get_student_by_email")
    assert hasattr(client, "get_student_by_cpf")
    assert hasattr(client, "get_access_link")
