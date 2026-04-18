from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry(auto_describe=True)

WEBHOOK_RECEIVED = Counter(
    "webhook_received_total",
    "Webhooks received",
    ["source", "status"],
    registry=REGISTRY,
)

QUEUE_DEPTH = Gauge(
    "queue_depth",
    "Current depth of the Redis work queue",
    ["name"],
    registry=REGISTRY,
)

WORKER_JOB_DURATION = Histogram(
    "worker_job_duration_seconds",
    "Time spent processing worker jobs",
    ["job_type", "outcome"],
    registry=REGISTRY,
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)

CAPABILITY_OUTCOME = Counter(
    "capability_outcome_total",
    "Capability executions by outcome",
    ["capability", "outcome"],
    registry=REGISTRY,
)

HANDOFF_TOTAL = Counter(
    "handoff_total",
    "Number of handoffs to humans",
    ["reason"],
    registry=REGISTRY,
)

LLM_TOKENS_USED = Counter(
    "llm_tokens_used_total",
    "LLM tokens consumed",
    ["model", "purpose"],
    registry=REGISTRY,
)

IDLE_CHECK_FIRED = Counter(
    "idle_check_fired_total",
    "Idle checks fired",
    ["stage"],
    registry=REGISTRY,
)


def render_latest() -> bytes:
    return generate_latest(REGISTRY)


CONTENT_TYPE = CONTENT_TYPE_LATEST
