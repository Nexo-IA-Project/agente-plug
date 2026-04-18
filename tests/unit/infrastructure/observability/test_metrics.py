from nexoia.infrastructure.observability.metrics import (
    WEBHOOK_RECEIVED,
    render_latest,
)


def test_webhook_counter_appears_in_metrics_output() -> None:
    WEBHOOK_RECEIVED.labels(source="hubla", status="202").inc()
    output = render_latest().decode()
    assert "webhook_received_total" in output
    assert 'source="hubla"' in output
