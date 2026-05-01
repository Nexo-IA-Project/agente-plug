import pytest

from nexoia.infrastructure.cademi.client import CademiClient


@pytest.mark.asyncio
async def test_cademi_client_get_student_raises_not_implemented():
    client = CademiClient(base_url="http://fake", api_key="key")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.get_student_by_email("test@test.com")


@pytest.mark.asyncio
async def test_cademi_client_get_access_link_raises_not_implemented():
    client = CademiClient(base_url="http://fake", api_key="key")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.get_access_link("student-1", "product-1")


@pytest.mark.asyncio
async def test_cademi_client_get_by_cpf_raises_not_implemented():
    client = CademiClient(base_url="http://fake", api_key="key")
    with pytest.raises(NotImplementedError, match="OPEN_QUESTIONS"):
        await client.get_student_by_cpf("123.456.789-00")
