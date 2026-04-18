from nexoia.infrastructure.observability.metrics import (
    welcome_capability_total,
    welcome_cademi_latency_seconds,
    welcome_d1_scheduled_total,
    welcome_d1_cancelled_total,
)


def test_welcome_capability_counter_labels():
    welcome_capability_total.labels(status="success").inc()
    welcome_capability_total.labels(status="cademi_failed").inc()
    welcome_capability_total.labels(status="error").inc()


def test_welcome_d1_counters():
    welcome_d1_scheduled_total.inc()
    welcome_d1_cancelled_total.inc()
