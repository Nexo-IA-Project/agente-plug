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

welcome_capability_total = Counter(
    "welcome_capability_total",
    "Total de execuções da Capability Welcome",
    ["status"],
    registry=REGISTRY,
)
welcome_cademi_latency_seconds = Histogram(
    "welcome_cademi_latency_seconds",
    "Latência das chamadas à Cademi API",
    buckets=[0.1, 0.5, 1.0, 3.0, 9.0, 30.0],
    registry=REGISTRY,
)
welcome_d1_scheduled_total = Counter(
    "welcome_d1_scheduled_total",
    "Total de follow-ups D+1 agendados pela Welcome Capability",
    registry=REGISTRY,
)
welcome_d1_cancelled_total = Counter(
    "welcome_d1_cancelled_total",
    "Total de follow-ups D+1 cancelados (acesso confirmado)",
    registry=REGISTRY,
)


# Capability Access (spec ③)
access_capability_total = Counter(
    "access_capability_total",
    "Total de execuções da Capability Access",
    ["status"],
    registry=REGISTRY,
)
access_cademi_cascade_attempts = Histogram(
    "access_cademi_cascade_attempts",
    "Distribuição de tentativas até encontrar aluno na cascade Cademi",
    buckets=[1, 2, 3],
    registry=REGISTRY,
)
access_cpf_fallback_total = Counter(
    "access_cpf_fallback_total",
    "Vezes que a IA pediu CPF ao aluno (student_cpf=None no AccessCase)",
    registry=REGISTRY,
)

AGENT_RUN_DURATION = Histogram(
    "agent_run_duration_seconds",
    "Total time spent in the OpenAI function calling loop per user turn",
    ["outcome"],
    registry=REGISTRY,
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

AGENT_TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "Tool calls dispatched by the agent",
    ["tool_name"],
    registry=REGISTRY,
)

AGENT_ITERATIONS = Counter(
    "agent_iterations_total",
    "Number of LLM iterations in the agent loop",
    ["outcome"],
    registry=REGISTRY,
)


def render_latest() -> bytes:
    return generate_latest(REGISTRY)


CONTENT_TYPE = CONTENT_TYPE_LATEST
