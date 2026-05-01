import pytest

from shared.domain.ports.cademi_port import CademiStudent
from tests.fakes.fake_cademi_client import FakeCademiClient


@pytest.mark.asyncio
async def test_fake_cademi_returns_student_by_email_only():
    alice = CademiStudent(id="s1", name="Alice", email="alice@x.com", phone="+5511999990001")
    client = FakeCademiClient(students_by_email={"alice@x.com": alice})
    assert await client.get_student_by_email("alice@x.com") == alice


@pytest.mark.asyncio
async def test_fake_cademi_returns_none_when_email_not_mapped():
    client = FakeCademiClient(students_by_email={})
    assert await client.get_student_by_email("nope@x.com") is None


@pytest.mark.asyncio
async def test_fake_cademi_returns_student_by_cpf():
    bob = CademiStudent(id="s2", name="Bob", email="bob@x.com", phone="+5511999990002")
    client = FakeCademiClient(students_by_cpf={"12345678900": bob})
    assert await client.get_student_by_cpf("12345678900") == bob


@pytest.mark.asyncio
async def test_fake_cademi_returns_none_when_cpf_not_mapped():
    client = FakeCademiClient(students_by_cpf={})
    assert await client.get_student_by_cpf("00000000000") is None


@pytest.mark.asyncio
async def test_fake_cademi_name_phone_raises_not_implemented_by_default():
    client = FakeCademiClient()
    with pytest.raises(NotImplementedError, match="CQ-A02"):
        await client.get_student_by_name_phone("Alice", "+5511999990001")


@pytest.mark.asyncio
async def test_fake_cademi_name_phone_configurable_returns_none():
    client = FakeCademiClient(name_phone_supported=True, students_by_name_phone={})
    assert await client.get_student_by_name_phone("Alice", "+5511999990001") is None


@pytest.mark.asyncio
async def test_fake_cademi_name_phone_configurable_returns_student():
    student = CademiStudent(id="s3", name="Carla", email="carla@x.com", phone="+5511999990003")
    client = FakeCademiClient(
        name_phone_supported=True,
        students_by_name_phone={("Carla", "+5511999990003"): student},
    )
    assert await client.get_student_by_name_phone("Carla", "+5511999990003") == student


@pytest.mark.asyncio
async def test_fake_cademi_tracks_call_counts_per_method():
    client = FakeCademiClient()
    await client.get_student_by_email("x@x.com")
    await client.get_student_by_email("y@x.com")
    await client.get_student_by_cpf("111")
    assert client.email_calls == 2
    assert client.cpf_calls == 1
