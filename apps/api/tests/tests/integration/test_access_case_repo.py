import pytest

from nexoia.domain.entities.access_case import AccessCase, AccessCaseStatus
from nexoia.infrastructure.db.repositories.access_case_repo import AccessCaseRepository


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_and_get_by_purchase_id(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id="contact-1",
        conversation_id="conv-1",
        purchase_id="purchase-unique-001",
        product_name="Curso Python",
        access_link="https://cademi.com.br/auto-login/abc",
        status=AccessCaseStatus.LINK_SENT,
    )
    await repo.save(case)

    found = await repo.get_by_purchase_id("purchase-unique-001")
    assert found is not None
    assert found.status == AccessCaseStatus.LINK_SENT
    assert found.access_link == "https://cademi.com.br/auto-login/abc"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_purchase_id_not_found(db_session):
    repo = AccessCaseRepository(db_session)
    found = await repo.get_by_purchase_id("non-existent-purchase")
    assert found is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_status(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1,
        contact_id="c",
        conversation_id="cv",
        purchase_id="p-update-test",
        product_name="Produto",
    )
    await repo.save(case)

    case.status = AccessCaseStatus.ACCESSED
    case.access_confirmed = True
    await repo.update(case)

    found = await repo.get_by_purchase_id("p-update-test")
    assert found.status == AccessCaseStatus.ACCESSED
    assert found.access_confirmed is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_duplicate_purchase_id_raises(db_session):
    repo = AccessCaseRepository(db_session)
    case1 = AccessCase(
        account_id=1, contact_id="c", conversation_id="cv",
        purchase_id="duplicate-purchase", product_name="P",
    )
    case2 = AccessCase(
        account_id=2, contact_id="c2", conversation_id="cv2",
        purchase_id="duplicate-purchase", product_name="P",
    )
    await repo.save(case1)
    with pytest.raises(Exception):
        await repo.save(case2)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_save_persists_student_cpf_and_search_attempts(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(
        account_id=1, contact_id="+5511999999999", conversation_id="conv-1",
        purchase_id="p-cpf-001", product_name="Curso X",
        student_cpf="111.222.333-44", search_attempts=2,
    )
    await repo.save(case)
    found = await repo.get_by_purchase_id("p-cpf-001")
    assert found is not None
    assert found.student_cpf == "111.222.333-44"
    assert found.search_attempts == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_find_by_phone_returns_most_recent(db_session):
    import asyncio
    repo = AccessCaseRepository(db_session)
    older = AccessCase(account_id=1, contact_id="+5511999999999", conversation_id="cv-older",
                       purchase_id="p-older", product_name="Curso Antigo")
    newer = AccessCase(account_id=1, contact_id="+5511999999999", conversation_id="cv-newer",
                       purchase_id="p-newer", product_name="Curso Novo")
    await repo.save(older)
    await asyncio.sleep(0.01)
    await repo.save(newer)
    found = await repo.find_by_phone(account_id=1, phone="+5511999999999")
    assert found is not None
    assert found.purchase_id == "p-newer"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_find_by_phone_respects_account_id_isolation(db_session):
    repo = AccessCaseRepository(db_session)
    case_a = AccessCase(account_id=1, contact_id="+5511999999999", conversation_id="cv-a",
                        purchase_id="p-tenant-a", product_name="Curso A")
    case_b = AccessCase(account_id=2, contact_id="+5511999999999", conversation_id="cv-b",
                        purchase_id="p-tenant-b", product_name="Curso B")
    await repo.save(case_a)
    await repo.save(case_b)
    found_a = await repo.find_by_phone(account_id=1, phone="+5511999999999")
    found_b = await repo.find_by_phone(account_id=2, phone="+5511999999999")
    assert found_a.purchase_id == "p-tenant-a"
    assert found_b.purchase_id == "p-tenant-b"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_find_by_phone_returns_none_when_no_case(db_session):
    repo = AccessCaseRepository(db_session)
    found = await repo.find_by_phone(account_id=1, phone="+5511000000000")
    assert found is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_status_sets_status_and_attempts(db_session):
    repo = AccessCaseRepository(db_session)
    case = AccessCase(account_id=1, contact_id="+5511999999999", conversation_id="cv-upd",
                      purchase_id="p-update-status", product_name="Curso")
    await repo.save(case)
    await repo.update_status(case_id=case.id, status=AccessCaseStatus.REACTIVE_LINK_SENT,
                             search_attempts=1)
    found = await repo.get_by_purchase_id("p-update-status")
    assert found.status == AccessCaseStatus.REACTIVE_LINK_SENT
    assert found.search_attempts == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_status_raises_when_case_not_found(db_session):
    repo = AccessCaseRepository(db_session)
    with pytest.raises(ValueError, match="not found"):
        await repo.update_status(case_id="nonexistent-id",
                                 status=AccessCaseStatus.REACTIVE_LINK_SENT, search_attempts=0)
