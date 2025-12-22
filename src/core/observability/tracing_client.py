"""
OpenTelemetry Distributed Tracing for ANTS

Provides comprehensive observability for multi-agent systems:
- Distributed tracing across agent workflows
- Span context propagation (agent-to-agent)
- Performance metrics and latency tracking
- Error tracking and debugging
- Integration with Grafana, Jaeger, Zipkin

Architecture:
┌──────────────────────────────────────────────────────┐
│  User Request                                        │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│  API Gateway (Trace ID created)                      │
│  Span: api.request                                   │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│  Finance Agent (Trace ID propagated)                 │
│  Span: agent.execute                                 │
│    ├─ Span: agent.perceive                          │
│    ├─ Span: agent.retrieve (semantic search)        │
│    ├─ Span: agent.reason (LLM call)                 │
│    ├─ Span: agent.execute (tool calls)              │
│    └─ Span: agent.verify                            │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│  ERP Integration (same trace)                        │
│  Span: mcp.erp_call                                  │
└──────────────────────────────────────────────────────┘

All spans share the same trace_id, enabling end-to-end visibility.

Example:
    from src.core.observability import TracingClient

    tracing = TracingClient(service_name="ants-agents")

    # Start a trace for agent execution
    with tracing.start_span("agent.execute", agent_id="finance_01") as span:
        span.set_attribute("agent.type", "finance.reconciliation")

        # Child span for LLM call
        with tracing.start_span("agent.reason") as llm_span:
            llm_span.set_attribute("model", "gpt-4-turbo")
            result = await llm_call()
            llm_span.set_attribute("tokens.input", 1500)
            llm_span.set_attribute("tokens.output", 500)
"""
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import Status, StatusCode
    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logging.warning("OpenTelemetry not installed - using simulation mode")


logger = logging.getLogger(__name__)


@dataclass
class SpanMetrics:
    """Metrics collected during a span."""
    span_id: str
    trace_id: str
    operation_name: str
    duration_ms: float
    status: str
    attributes: Dict[str, Any]
    start_time: str
    end_time: str


class TracingClient:
    """
    OpenTelemetry distributed tracing client for ANTS.

    Provides comprehensive observability for multi-agent workflows:
    - Trace agent execution (Perceive → Retrieve → Reason → Execute → Verify → Learn)
    - Track cross-agent communication (pheromone messaging, task delegation)
    - Monitor external calls (LLM, vector DB, MCP tools)
    - Collect performance metrics (latency, throughput)
    - Enable debugging (error tracking, context propagation)
    """

    def __init__(
        self,
        service_name: str = "ants-agents",
        otlp_endpoint: Optional[str] = None,
        enable_simulation: bool = False
    ):
        """
        Initialize Tracing Client.

        Args:
            service_name: Service name for traces
            otlp_endpoint: OTLP collector endpoint (e.g., "http://localhost:4317")
            enable_simulation: Use simulation mode if OpenTelemetry unavailable
        """
        self.service_name = service_name
        self.otlp_endpoint = otlp_endpoint or "http://localhost:4317"
        self.simulation_mode = enable_simulation or not OTEL_AVAILABLE

        # Statistics
        self.stats = {
            'total_spans': 0,
            'spans_by_operation': {},
            'total_duration_ms': 0.0,
            'errors': 0,
        }

        # Span storage (for simulation)
        self.spans: List[SpanMetrics] = []

        # Initialize OpenTelemetry
        if not self.simulation_mode:
            try:
                # Create resource
                resource = Resource.create({
                    "service.name": service_name,
                    "service.version": "1.0.0",
                    "deployment.environment": "production"
                })

                # Create tracer provider
                provider = TracerProvider(resource=resource)

                # Add OTLP exporter
                otlp_exporter = OTLPSpanExporter(
                    endpoint=self.otlp_endpoint,
                    insecure=True  # Use TLS in production
                )
                processor = BatchSpanProcessor(otlp_exporter)
                provider.add_span_processor(processor)

                # Set global tracer provider
                trace.set_tracer_provider(provider)

                # Get tracer
                self.tracer = trace.get_tracer(__name__)

                logger.info(f"OpenTelemetry tracing initialized: {self.otlp_endpoint}")
            except Exception as e:
                logger.error(f"Failed to initialize OpenTelemetry: {e}")
                self.tracer = None
                self.simulation_mode = True
        else:
            self.tracer = None
            logger.info("Tracing client initialized in SIMULATION mode")

    @contextmanager
    def start_span(
        self,
        operation_name: str,
        attributes: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Start a new span for tracing an operation.

        Args:
            operation_name: Name of the operation (e.g., "agent.execute", "llm.call")
            attributes: Attributes to attach to span
            **kwargs: Additional attributes as keyword arguments

        Yields:
            Span object for adding attributes and events

        Example:
            with tracing.start_span("agent.retrieve", agent_id="finance_01") as span:
                span.set_attribute("query", "outstanding invoices")
                results = await search()
                span.set_attribute("results.count", len(results))
        """
        start_time = time.time()
        span_attrs = {**(attributes or {}), **kwargs}

        self.stats['total_spans'] += 1
        self.stats['spans_by_operation'][operation_name] = \
            self.stats['spans_by_operation'].get(operation_name, 0) + 1

        # Use OpenTelemetry if available
        if not self.simulation_mode and self.tracer:
            with self.tracer.start_as_current_span(operation_name) as span:
                # Set initial attributes
                for key, value in span_attrs.items():
                    span.set_attribute(key, value)

                try:
                    # Create span wrapper
                    span_wrapper = SpanWrapper(span, operation_name, self.stats)
                    yield span_wrapper

                    # Mark as success
                    span.set_status(Status(StatusCode.OK))

                except Exception as e:
                    # Mark as error
                    span.set_status(
                        Status(StatusCode.ERROR, description=str(e))
                    )
                    span.record_exception(e)
                    self.stats['errors'] += 1
                    raise

                finally:
                    duration_ms = (time.time() - start_time) * 1000
                    self.stats['total_duration_ms'] += duration_ms
                    span.set_attribute("duration_ms", duration_ms)

        # Simulation mode
        else:
            try:
                # Create simulated span
                sim_span = SimulatedSpan(
                    operation_name,
                    span_attrs,
                    self.spans,
                    self.stats
                )
                yield sim_span

                # Record metrics
                duration_ms = (time.time() - start_time) * 1000
                self.stats['total_duration_ms'] += duration_ms

                sim_span._finalize(duration_ms, "ok")

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                sim_span._finalize(duration_ms, "error", str(e))
                self.stats['errors'] += 1
                raise

    def start_agent_trace(
        self,
        agent_id: str,
        agent_type: str,
        operation: str = "agent.execute"
    ):
        """
        Start a trace for agent execution.

        Convenience method that sets standard agent attributes.

        Args:
            agent_id: Unique agent identifier
            agent_type: Agent type (e.g., "finance.reconciliation")
            operation: Operation name (default: "agent.execute")

        Returns:
            Context manager for span
        """
        return self.start_span(
            operation,
            agent_id=agent_id,
            agent_type=agent_type,
            component="agent"
        )

    def start_llm_trace(
        self,
        model: str,
        provider: str = "azure_openai"
    ):
        """
        Start a trace for LLM call.

        Args:
            model: Model name (e.g., "gpt-4-turbo")
            provider: Provider name (e.g., "azure_openai", "anthropic")

        Returns:
            Context manager for span
        """
        return self.start_span(
            "llm.call",
            model=model,
            provider=provider,
            component="llm"
        )

    def start_retrieval_trace(self, query: str, search_type: str = "semantic"):
        """
        Start a trace for vector/semantic search.

        Args:
            query: Search query
            search_type: Type of search (semantic, keyword, hybrid)

        Returns:
            Context manager for span
        """
        return self.start_span(
            "retrieval.search",
            query=query[:100],  # Truncate for readability
            search_type=search_type,
            component="retrieval"
        )

    def start_tool_trace(self, tool_name: str, tool_args: Optional[Dict] = None):
        """
        Start a trace for MCP tool execution.

        Args:
            tool_name: Tool name (e.g., "erp.get_invoice")
            tool_args: Tool arguments (truncated for privacy)

        Returns:
            Context manager for span
        """
        return self.start_span(
            "tool.execute",
            tool_name=tool_name,
            component="mcp_tool"
        )

    def start_pheromone_trace(self, pheromone_type: str, strength: float):
        """
        Start a trace for pheromone messaging.

        Args:
            pheromone_type: Pheromone type (e.g., "success", "danger")
            strength: Pheromone strength

        Returns:
            Context manager for span
        """
        return self.start_span(
            "pheromone.deposit",
            pheromone_type=pheromone_type,
            strength=strength,
            component="swarm"
        )

    def get_metrics(self) -> Dict[str, Any]:
        """Get tracing metrics."""
        avg_duration = (
            self.stats['total_duration_ms'] / self.stats['total_spans']
            if self.stats['total_spans'] > 0 else 0.0
        )

        return {
            **self.stats,
            'avg_duration_ms': avg_duration,
            'error_rate': (
                self.stats['errors'] / self.stats['total_spans']
                if self.stats['total_spans'] > 0 else 0.0
            ),
            'simulation_mode': self.simulation_mode
        }

    def get_recent_spans(self, limit: int = 10) -> List[SpanMetrics]:
        """Get recent spans (simulation mode only)."""
        return self.spans[-limit:]


class SpanWrapper:
    """Wrapper for OpenTelemetry span."""

    def __init__(self, span, operation_name: str, stats: Dict):
        self.span = span
        self.operation_name = operation_name
        self.stats = stats

    def set_attribute(self, key: str, value: Any):
        """Set span attribute."""
        self.span.set_attribute(key, value)

    def add_event(self, name: str, attributes: Optional[Dict] = None):
        """Add event to span."""
        self.span.add_event(name, attributes or {})

    def record_exception(self, exception: Exception):
        """Record exception in span."""
        self.span.record_exception(exception)


class SimulatedSpan:
    """Simulated span for testing/development."""

    def __init__(
        self,
        operation_name: str,
        attributes: Dict[str, Any],
        spans_list: List,
        stats: Dict
    ):
        self.operation_name = operation_name
        self.attributes = attributes.copy()
        self.spans_list = spans_list
        self.stats = stats
        self.start_time = datetime.utcnow().isoformat()
        self.events = []

    def set_attribute(self, key: str, value: Any):
        """Set attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: Optional[Dict] = None):
        """Add event."""
        self.events.append({
            'name': name,
            'timestamp': datetime.utcnow().isoformat(),
            'attributes': attributes or {}
        })

    def record_exception(self, exception: Exception):
        """Record exception."""
        self.attributes['error'] = str(exception)
        self.attributes['error.type'] = type(exception).__name__

    def _finalize(self, duration_ms: float, status: str, error: Optional[str] = None):
        """Finalize span and record metrics."""
        span_metrics = SpanMetrics(
            span_id=f"span_{len(self.spans_list)}",
            trace_id=f"trace_{len(self.spans_list) // 10}",
            operation_name=self.operation_name,
            duration_ms=duration_ms,
            status=status,
            attributes=self.attributes,
            start_time=self.start_time,
            end_time=datetime.utcnow().isoformat()
        )

        if error:
            span_metrics.attributes['error'] = error

        self.spans_list.append(span_metrics)

        logger.debug(
            f"Span completed: {self.operation_name}",
            extra={
                'duration_ms': duration_ms,
                'status': status,
                'attributes': self.attributes
            }
        )


def create_tracing_client(**kwargs) -> TracingClient:
    """
    Factory function to create Tracing Client.

    Args:
        **kwargs: Arguments for TracingClient

    Returns:
        Configured TracingClient
    """
    return TracingClient(**kwargs)
