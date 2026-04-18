from nexoia.infrastructure.observability.metrics import (
    access_capability_total,
    access_cademi_cascade_attempts,
    access_cpf_fallback_total,
)


def test_access_capability_counter_labels_exist():
    access_capability_total.labels(status="success").inc()
    access_capability_total.labels(status="escalated").inc()
    access_capability_total.labels(status="no_access_case").inc()
    access_capability_total.labels(status="out_of_scope").inc()
    access_capability_total.labels(status="error").inc()


def test_access_cascade_attempts_histogram_observes():
    access_cademi_cascade_attempts.observe(1)
    access_cademi_cascade_attempts.observe(2)
    access_cademi_cascade_attempts.observe(3)


def test_access_cpf_fallback_counter_increments():
    before = access_cpf_fallback_total._value.get()
    access_cpf_fallback_total.inc()
    after = access_cpf_fallback_total._value.get()
    assert after == before + 1
