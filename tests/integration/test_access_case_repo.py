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
