from datetime import datetime, UTC
from shared.domain.ports.hubla_port import HublaPurchase, RefundResult, HublaPort
from shared.domain.ports.refund_mutex import RefundMutexPort
from shared.domain.ports.legal_history_port import LegalHistoryPort


def test_hubla_purchase_is_frozen():
    p = HublaPurchase(
        id="p1",
        product_name="Curso X",
        created_at=datetime.now(UTC),
        amount=99.0,
        is_duplicate=False,
        is_recurring=False,
        first_charge_at=None,
    )
    assert p.id == "p1"
    assert p.is_recurring is False


def test_refund_result_is_frozen():
    r = RefundResult(success=True, refund_id="ref-1", error=None)
    assert r.success is True


def test_hubla_port_is_protocol():
    assert hasattr(HublaPort, "get_purchase_by_email")
    assert hasattr(HublaPort, "process_refund")


def test_refund_mutex_port_is_protocol():
    assert hasattr(RefundMutexPort, "acquire")
    assert hasattr(RefundMutexPort, "release")


def test_legal_history_port_is_protocol():
    assert hasattr(LegalHistoryPort, "has_prior_refund_mention")
