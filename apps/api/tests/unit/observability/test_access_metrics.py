from shared.adapters.observability.metrics import (
    access_capability_total,
    access_cpf_fallback_total,
)


def test_access_capability_counter_labels_exist():
    access_capability_total.labels(status="success").inc()
    access_capability_total.labels(status="escalated").inc()
    access_capability_total.labels(status="no_access_case").inc()
    access_capability_total.labels(status="out_of_scope").inc()


def test_access_cpf_fallback_counter_increments():
    before = access_cpf_fallback_total._value.get()
    access_cpf_fallback_total.inc()
    after = access_cpf_fallback_total._value.get()
    assert after == before + 1
