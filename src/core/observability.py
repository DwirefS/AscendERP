"""
OpenTelemetry Observability for ANTS

Implements distributed tracing, metrics, and logging following Microsoft Agent Framework patterns.
Reference: https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/observability

Provides comprehensive monitoring of:
- Agent execution flows and reasoning chains
- LLM invocations and token usage
- Tool executions
- Council deliberations
- Swarm coordination
- Policy evaluations
"""

import os
import logging
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
    ConsoleMetricExporter
)
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry import propagate
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Instrumentation
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

logger = logging.getLogger(__name__)


def create_resource() -> Resource:
    """
    Create OpenTelemetry resource with service identification.

    Following Microsoft Agent Framework pattern.
    """
    return Resource.create({
        SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", "ants-platform"),
        SERVICE_VERSION: os.getenv("SERVICE_VERSION", "1.0.0"),
        "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        "cloud.provider": "azure",
        "cloud.platform": "azure_aks"
    })


def configure_otel_providers(
    exporters: Optional[List[SpanExporter]] = None,
    enable_console: bool = None,
    enable_sensitive_data: bool = None
) -> None:
    """
    Configure OpenTelemetry providers for ANTS platform.

    Follows Microsoft Agent Framework observability patterns:
    - Pattern 1: Environment variable configuration (default)
    - Pattern 2: Custom exporters (via exporters parameter)
    - Supports Azure Monitor, Aspire Dashboard, and OTLP backends

    Args:
        exporters: Optional list of custom span exporters
        enable_console: Output to console (defaults to ENABLE_CONSOLE_EXPORTERS env var)
        enable_sensitive_data: Include prompts/responses (defaults to ENABLE_SENSITIVE_DATA env var)

    Environment Variables:
        ENABLE_INSTRUMENTATION: Enable telemetry collection (default: false)
        ENABLE_CONSOLE_EXPORTERS: Output to console (default: false)
        ENABLE_SENSITIVE_DATA: Include prompts/responses in traces (default: false)
        OTEL_EXPORTER_OTLP_ENDPOINT: OTLP backend endpoint (default: http://localhost:4317)
        OTEL_SERVICE_NAME: Service name for tracing (default: ants-platform)
        APPLICATIONINSIGHTS_CONNECTION_STRING: Azure Monitor connection string

    Reference: Microsoft Agent Framework observability sample
    """
    # Check if instrumentation is enabled
    instrumentation_enabled = os.getenv("ENABLE_INSTRUMENTATION", "false").lower() == "true"

    if not instrumentation_enabled:
        logger.info("OpenTelemetry instrumentation disabled. Set ENABLE_INSTRUMENTATION=true to enable.")
        return

    # Determine console output
    if enable_console is None:
        enable_console = os.getenv("ENABLE_CONSOLE_EXPORTERS", "false").lower() == "true"

    # Determine sensitive data collection
    if enable_sensitive_data is None:
        enable_sensitive_data = os.getenv("ENABLE_SENSITIVE_DATA", "false").lower() == "true"

    # Create resource
    resource = create_resource()

    # Configure Trace Provider
    trace_provider = TracerProvider(resource=resource)

    # Add exporters
    if exporters:
        # Pattern 2: Custom exporters provided
        for exporter in exporters:
            trace_provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        # Pattern 1: Environment variable configuration
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        if otlp_endpoint:
            # OTLP exporter (for Aspire Dashboard, Jaeger, etc.)
            otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
            logger.info(f"OTLP trace exporter configured: {otlp_endpoint}")

    # Console exporter for development
    if enable_console:
        console_exporter = ConsoleSpanExporter()
        trace_provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("Console trace exporter enabled")

    # Set global tracer provider
    trace.set_tracer_provider(trace_provider)

    # Configure propagation
    propagate.set_global_textmap(TraceContextTextMapPropagator())

    # Configure Metrics Provider
    otlp_metric_endpoint = os.getenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", otlp_endpoint)

    metric_readers = []
    if otlp_metric_endpoint:
        metric_exporter = OTLPMetricExporter(endpoint=otlp_metric_endpoint)
        metric_readers.append(PeriodicExportingMetricReader(metric_exporter))

    if enable_console:
        console_metric_exporter = ConsoleMetricExporter()
        metric_readers.append(PeriodicExportingMetricReader(console_metric_exporter))

    if metric_readers:
        meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
        metrics.set_meter_provider(meter_provider)
        logger.info("OpenTelemetry metrics configured")

    logger.info(
        "OpenTelemetry configured",
        service_name=resource.attributes.get(SERVICE_NAME),
        console_enabled=enable_console,
        sensitive_data_enabled=enable_sensitive_data
    )


def configure_azure_monitor(
    connection_string: Optional[str] = None,
    enable_live_metrics: bool = True
) -> None:
    """
    Configure Azure Monitor (Application Insights) for ANTS observability.

    Integrates with Azure AI Foundry and Azure Monitor for production observability.

    Args:
        connection_string: Application Insights connection string (defaults to env var)
        enable_live_metrics: Enable live metrics streaming

    Environment Variables:
        APPLICATIONINSIGHTS_CONNECTION_STRING: Azure Monitor connection string

    Reference: Microsoft Agent Framework Azure Monitor integration
    """
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor as azure_configure

        # Get connection string
        conn_str = connection_string or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

        if not conn_str:
            logger.warning(
                "Azure Monitor not configured: APPLICATIONINSIGHTS_CONNECTION_STRING not set"
            )
            return

        # Configure Azure Monitor with custom resource
        azure_configure(
            connection_string=conn_str,
            resource=create_resource(),
            enable_live_metrics=enable_live_metrics
        )

        # Enable instrumentation
        enable_instrumentation()

        logger.info("Azure Monitor configured", live_metrics=enable_live_metrics)

    except ImportError:
        logger.error(
            "Azure Monitor configuration failed: azure-monitor-opentelemetry not installed. "
            "Install with: pip install azure-monitor-opentelemetry"
        )


def enable_instrumentation():
    """
    Enable automatic instrumentation for common libraries.

    Instruments:
    - System metrics (CPU, memory, disk, network)
    - Logging (structured log correlation with traces)
    - HTTP requests (httpx, requests)
    - Database clients (psycopg, asyncpg)
    """
    try:
        # System metrics
        SystemMetricsInstrumentor().instrument()
        logger.info("System metrics instrumentation enabled")
    except Exception as e:
        logger.warning(f"System metrics instrumentation failed: {e}")

    try:
        # Logging instrumentation
        LoggingInstrumentor().instrument(set_logging_format=True)
        logger.info("Logging instrumentation enabled")
    except Exception as e:
        logger.warning(f"Logging instrumentation failed: {e}")

    # HTTP instrumentation
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
        logger.info("HTTPX instrumentation enabled")
    except:
        pass

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentor
        RequestsInstrumentor().instrument()
        logger.info("Requests instrumentation enabled")
    except:
        pass

    # Database instrumentation
    try:
        from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
        PsycopgInstrumentor().instrument()
        logger.info("Psycopg instrumentation enabled")
    except:
        pass

    try:
        from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor
        AsyncPGInstrumentor().instrument()
        logger.info("AsyncPG instrumentation enabled")
    except:
        pass


# Global tracer and meter for ANTS
tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)


# ANTS-specific metrics
agent_execution_counter = meter.create_counter(
    "ants.agent.executions",
    description="Number of agent executions",
    unit="1"
)

agent_latency_histogram = meter.create_histogram(
    "ants.agent.latency",
    description="Agent execution latency",
    unit="ms"
)

token_usage_counter = meter.create_counter(
    "ants.llm.tokens",
    description="LLM token usage",
    unit="tokens"
)

council_decision_counter = meter.create_counter(
    "ants.council.decisions",
    description="Council decisions made",
    unit="1"
)

swarm_event_counter = meter.create_counter(
    "ants.swarm.events",
    description="Swarm coordination events",
    unit="1"
)

policy_evaluation_counter = meter.create_counter(
    "ants.policy.evaluations",
    description="Policy evaluations",
    unit="1"
)


@contextmanager
def trace_agent_execution(
    agent_id: str,
    agent_type: str,
    operation: str,
    context: Optional[Dict[str, Any]] = None
):
    """
    Context manager for tracing agent execution with OpenTelemetry.

    Usage:
        with trace_agent_execution("agent-123", "FinanceAgent", "reconcile_invoices"):
            result = await agent.run(input_data)

    Args:
        agent_id: Unique agent identifier
        agent_type: Agent class/type name
        operation: Operation being performed
        context: Optional additional context
    """
    import time

    with tracer.start_as_current_span(
        f"{agent_type}.{operation}",
        attributes={
            "agent.id": agent_id,
            "agent.type": agent_type,
            "agent.operation": operation,
            **(context or {})
        }
    ) as span:
        start_time = time.time()

        try:
            yield span

            # Record metrics on success
            latency_ms = (time.time() - start_time) * 1000
            agent_execution_counter.add(1, {"agent_type": agent_type, "status": "success"})
            agent_latency_histogram.record(latency_ms, {"agent_type": agent_type})

            span.set_attribute("success", True)
            span.set_attribute("latency_ms", latency_ms)

        except Exception as e:
            # Record metrics on failure
            agent_execution_counter.add(1, {"agent_type": agent_type, "status": "error"})

            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            span.record_exception(e)

            raise


def trace_llm_call(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int
):
    """
    Record LLM invocation metrics.

    Args:
        model: Model name (e.g., "llama-3.1-nemotron-nano-8b")
        prompt_tokens: Input token count
        completion_tokens: Output token count
        total_tokens: Total token count
    """
    token_usage_counter.add(
        total_tokens,
        {
            "model": model,
            "token_type": "total"
        }
    )

    token_usage_counter.add(
        prompt_tokens,
        {
            "model": model,
            "token_type": "prompt"
        }
    )

    token_usage_counter.add(
        completion_tokens,
        {
            "model": model,
            "token_type": "completion"
        }
    )


def trace_council_decision(
    council_id: str,
    decision_type: str,
    consensus_score: float,
    agent_count: int
):
    """
    Record council decision metrics.

    Args:
        council_id: Council identifier
        decision_type: Type of decision
        consensus_score: Consensus score (0-1)
        agent_count: Number of agents in council
    """
    council_decision_counter.add(
        1,
        {
            "council_id": council_id,
            "decision_type": decision_type,
            "agent_count": str(agent_count)
        }
    )


def trace_policy_evaluation(
    policy_name: str,
    decision: str,
    risk_level: str
):
    """
    Record policy evaluation metrics.

    Args:
        policy_name: Policy being evaluated
        decision: allow, deny, or require_approval
        risk_level: low, medium, high, critical
    """
    policy_evaluation_counter.add(
        1,
        {
            "policy": policy_name,
            "decision": decision,
            "risk_level": risk_level
        }
    )
