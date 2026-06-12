"""
Observability module for ANTS.

Comprehensive monitoring and observability for multi-agent systems:
- Distributed tracing (OpenTelemetry)
- Metrics collection (Prometheus)
- Performance monitoring
- Cost tracking
- System health monitoring

This enables production-grade observability for ANTS agents with:
- End-to-end request tracing across agents
- Real-time performance metrics
- Cost analytics per agent/model
- Grafana dashboards for visualization
- Alerting on anomalies and errors
"""
from src.core.observability.otel import (
    create_resource,
    configure_otel_providers,
    configure_azure_monitor,
    enable_instrumentation,
    tracer,
    meter,
    agent_execution_counter,
    agent_latency_histogram,
    token_usage_counter,
    council_decision_counter,
    swarm_event_counter,
    policy_evaluation_counter,
    trace_agent_execution,
    trace_llm_call,
    trace_council_decision,
    trace_policy_evaluation,
)
from src.core.observability.tracing_client import (
    TracingClient,
    SpanMetrics,
    create_tracing_client
)
from src.core.observability.metrics_client import (
    MetricsClient,
    MetricSnapshot,
    create_metrics_client
)

__all__ = [
    "create_resource",
    "configure_otel_providers",
    "configure_azure_monitor",
    "enable_instrumentation",
    "tracer",
    "meter",
    "agent_execution_counter",
    "agent_latency_histogram",
    "token_usage_counter",
    "council_decision_counter",
    "swarm_event_counter",
    "policy_evaluation_counter",
    "trace_agent_execution",
    "trace_llm_call",
    "trace_council_decision",
    "trace_policy_evaluation",
    "TracingClient",
    "SpanMetrics",
    "create_tracing_client",
    "MetricsClient",
    "MetricSnapshot",
    "create_metrics_client",
]
