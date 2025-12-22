"""
Prometheus Metrics Collection for ANTS

Provides comprehensive metrics for monitoring multi-agent systems:
- Agent performance metrics (latency, throughput, success rate)
- Resource utilization (CPU, memory, GPU)
- LLM usage metrics (tokens, cost, latency)
- Swarm coordination metrics (pheromones, tasks)
- System health metrics (errors, queues, capacity)

Metrics are exposed in Prometheus format for scraping by Prometheus server
and visualization in Grafana dashboards.

Architecture:
┌──────────────────────────────────────────────────────┐
│  ANTS Agents                                         │
│  - Record metrics via MetricsClient                  │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│  Prometheus Exporter (port 9090)                     │
│  - Exposes /metrics endpoint                         │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│  Prometheus Server                                   │
│  - Scrapes metrics every 15s                         │
│  - Stores time-series data                           │
└────────────────┬─────────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────────┐
│  Grafana Dashboards                                  │
│  - Agent Performance Dashboard                       │
│  - Swarm Coordination Dashboard                      │
│  - Cost Analytics Dashboard                          │
└──────────────────────────────────────────────────────┘

Example:
    from src.core.observability import MetricsClient

    metrics = MetricsClient(service_name="ants-agents")

    # Record agent execution
    with metrics.measure_agent_execution("finance_01", "reconciliation"):
        result = await agent.execute(task)

    # Record LLM usage
    metrics.record_llm_tokens(
        model="gpt-4-turbo",
        input_tokens=1500,
        output_tokens=500,
        cost_usd=0.045
    )

    # Record swarm activity
    metrics.record_pheromone_deposit(
        pheromone_type="success",
        strength=0.9,
        agent_id="finance_01"
    )
"""
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Summary,
        CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("Prometheus client not installed - using simulation mode")


logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time."""
    timestamp: str
    agent_executions: int
    total_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    error_count: int


class MetricsClient:
    """
    Prometheus metrics client for ANTS.

    Provides comprehensive metrics collection for:
    - Agent performance (latency, throughput, success rate)
    - Resource utilization (CPU, memory, GPU)
    - LLM usage (tokens, cost, latency)
    - Swarm coordination (pheromones, tasks, agents)
    - System health (errors, queues, capacity)
    """

    def __init__(
        self,
        service_name: str = "ants-agents",
        enable_simulation: bool = False,
        registry: Optional[Any] = None
    ):
        """
        Initialize Metrics Client.

        Args:
            service_name: Service name for metrics
            enable_simulation: Use simulation mode if Prometheus unavailable
            registry: Custom Prometheus registry (optional)
        """
        self.service_name = service_name
        self.simulation_mode = enable_simulation or not PROMETHEUS_AVAILABLE
        self.registry = registry

        # Simulation storage
        self.simulated_metrics = {
            'agent_executions_total': 0,
            'agent_execution_duration_seconds': [],
            'llm_tokens_total': 0,
            'llm_cost_usd_total': 0.0,
            'pheromone_deposits_total': 0,
            'errors_total': 0,
        }

        # Initialize Prometheus metrics
        if not self.simulation_mode:
            try:
                if not self.registry:
                    self.registry = CollectorRegistry()

                # Agent execution metrics
                self.agent_executions = Counter(
                    'ants_agent_executions_total',
                    'Total number of agent executions',
                    ['agent_id', 'agent_type', 'status'],
                    registry=self.registry
                )

                self.agent_execution_duration = Histogram(
                    'ants_agent_execution_duration_seconds',
                    'Agent execution duration in seconds',
                    ['agent_id', 'agent_type'],
                    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
                    registry=self.registry
                )

                # LLM metrics
                self.llm_tokens = Counter(
                    'ants_llm_tokens_total',
                    'Total LLM tokens consumed',
                    ['model', 'provider', 'token_type'],
                    registry=self.registry
                )

                self.llm_cost = Counter(
                    'ants_llm_cost_usd_total',
                    'Total LLM cost in USD',
                    ['model', 'provider'],
                    registry=self.registry
                )

                self.llm_latency = Histogram(
                    'ants_llm_latency_seconds',
                    'LLM call latency in seconds',
                    ['model', 'provider'],
                    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
                    registry=self.registry
                )

                # Swarm metrics
                self.pheromone_deposits = Counter(
                    'ants_pheromone_deposits_total',
                    'Total pheromone deposits',
                    ['pheromone_type', 'agent_id'],
                    registry=self.registry
                )

                self.active_agents = Gauge(
                    'ants_active_agents',
                    'Number of active agents',
                    ['agent_type'],
                    registry=self.registry
                )

                self.task_queue_size = Gauge(
                    'ants_task_queue_size',
                    'Number of tasks in queue',
                    ['queue_name'],
                    registry=self.registry
                )

                # Retrieval metrics
                self.vector_searches = Counter(
                    'ants_vector_searches_total',
                    'Total vector searches',
                    ['search_type'],
                    registry=self.registry
                )

                self.vector_search_latency = Histogram(
                    'ants_vector_search_latency_seconds',
                    'Vector search latency in seconds',
                    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5],
                    registry=self.registry
                )

                # Error metrics
                self.errors = Counter(
                    'ants_errors_total',
                    'Total errors',
                    ['error_type', 'component'],
                    registry=self.registry
                )

                # Resource metrics
                self.memory_usage_bytes = Gauge(
                    'ants_memory_usage_bytes',
                    'Memory usage in bytes',
                    ['component'],
                    registry=self.registry
                )

                self.cpu_usage_percent = Gauge(
                    'ants_cpu_usage_percent',
                    'CPU usage percentage',
                    ['component'],
                    registry=self.registry
                )

                logger.info("Prometheus metrics initialized")

            except Exception as e:
                logger.error(f"Failed to initialize Prometheus metrics: {e}")
                self.simulation_mode = True
        else:
            logger.info("Metrics client initialized in SIMULATION mode")

    @contextmanager
    def measure_agent_execution(
        self,
        agent_id: str,
        agent_type: str
    ):
        """
        Measure agent execution duration.

        Args:
            agent_id: Unique agent identifier
            agent_type: Agent type (e.g., "finance.reconciliation")

        Example:
            with metrics.measure_agent_execution("agent_01", "finance"):
                result = await agent.execute(task)
        """
        start_time = time.time()

        try:
            yield

            # Success
            duration = time.time() - start_time

            if not self.simulation_mode:
                self.agent_executions.labels(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    status="success"
                ).inc()

                self.agent_execution_duration.labels(
                    agent_id=agent_id,
                    agent_type=agent_type
                ).observe(duration)
            else:
                self.simulated_metrics['agent_executions_total'] += 1
                self.simulated_metrics['agent_execution_duration_seconds'].append(duration)

        except Exception as e:
            # Failure
            duration = time.time() - start_time

            if not self.simulation_mode:
                self.agent_executions.labels(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    status="error"
                ).inc()

                self.agent_execution_duration.labels(
                    agent_id=agent_id,
                    agent_type=agent_type
                ).observe(duration)
            else:
                self.simulated_metrics['agent_executions_total'] += 1
                self.simulated_metrics['errors_total'] += 1

            raise

    def record_llm_tokens(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        provider: str = "azure_openai"
    ):
        """
        Record LLM token usage and cost.

        Args:
            model: Model name (e.g., "gpt-4-turbo")
            input_tokens: Input tokens consumed
            output_tokens: Output tokens generated
            cost_usd: Total cost in USD
            provider: Provider name (e.g., "azure_openai", "anthropic")
        """
        if not self.simulation_mode:
            self.llm_tokens.labels(
                model=model,
                provider=provider,
                token_type="input"
            ).inc(input_tokens)

            self.llm_tokens.labels(
                model=model,
                provider=provider,
                token_type="output"
            ).inc(output_tokens)

            self.llm_cost.labels(
                model=model,
                provider=provider
            ).inc(cost_usd)
        else:
            self.simulated_metrics['llm_tokens_total'] += input_tokens + output_tokens
            self.simulated_metrics['llm_cost_usd_total'] += cost_usd

        logger.debug(
            f"LLM usage recorded",
            extra={
                'model': model,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'cost_usd': cost_usd
            }
        )

    @contextmanager
    def measure_llm_latency(self, model: str, provider: str = "azure_openai"):
        """
        Measure LLM call latency.

        Args:
            model: Model name
            provider: Provider name

        Example:
            with metrics.measure_llm_latency("gpt-4-turbo"):
                response = await llm_call()
        """
        start_time = time.time()

        try:
            yield
        finally:
            duration = time.time() - start_time

            if not self.simulation_mode:
                self.llm_latency.labels(
                    model=model,
                    provider=provider
                ).observe(duration)

    def record_pheromone_deposit(
        self,
        pheromone_type: str,
        strength: float,
        agent_id: str
    ):
        """
        Record pheromone deposit.

        Args:
            pheromone_type: Type of pheromone (e.g., "success", "danger")
            strength: Pheromone strength (0.0-1.0)
            agent_id: Agent depositing pheromone
        """
        if not self.simulation_mode:
            self.pheromone_deposits.labels(
                pheromone_type=pheromone_type,
                agent_id=agent_id
            ).inc()
        else:
            self.simulated_metrics['pheromone_deposits_total'] += 1

    def set_active_agents(self, agent_type: str, count: int):
        """
        Set number of active agents.

        Args:
            agent_type: Agent type
            count: Number of active agents
        """
        if not self.simulation_mode:
            self.active_agents.labels(agent_type=agent_type).set(count)

    def set_task_queue_size(self, queue_name: str, size: int):
        """
        Set task queue size.

        Args:
            queue_name: Queue name
            size: Number of tasks in queue
        """
        if not self.simulation_mode:
            self.task_queue_size.labels(queue_name=queue_name).set(size)

    @contextmanager
    def measure_vector_search(self, search_type: str = "semantic"):
        """
        Measure vector search latency.

        Args:
            search_type: Type of search (semantic, keyword, hybrid)

        Example:
            with metrics.measure_vector_search("semantic"):
                results = await vector_search(query)
        """
        start_time = time.time()

        try:
            yield
        finally:
            duration = time.time() - start_time

            if not self.simulation_mode:
                self.vector_searches.labels(search_type=search_type).inc()
                self.vector_search_latency.observe(duration)

    def record_error(self, error_type: str, component: str):
        """
        Record error occurrence.

        Args:
            error_type: Error type (e.g., "timeout", "validation_error")
            component: Component where error occurred
        """
        if not self.simulation_mode:
            self.errors.labels(
                error_type=error_type,
                component=component
            ).inc()
        else:
            self.simulated_metrics['errors_total'] += 1

    def set_memory_usage(self, component: str, bytes_used: int):
        """
        Set memory usage for component.

        Args:
            component: Component name
            bytes_used: Memory usage in bytes
        """
        if not self.simulation_mode:
            self.memory_usage_bytes.labels(component=component).set(bytes_used)

    def set_cpu_usage(self, component: str, percent: float):
        """
        Set CPU usage for component.

        Args:
            component: Component name
            percent: CPU usage percentage (0-100)
        """
        if not self.simulation_mode:
            self.cpu_usage_percent.labels(component=component).set(percent)

    def get_metrics_text(self) -> str:
        """
        Get metrics in Prometheus text format.

        Returns:
            Metrics text for /metrics endpoint
        """
        if not self.simulation_mode:
            return generate_latest(self.registry).decode('utf-8')
        else:
            # Return simulated metrics
            lines = [
                f"# HELP ants_agent_executions_total Total agent executions",
                f"# TYPE ants_agent_executions_total counter",
                f"ants_agent_executions_total {self.simulated_metrics['agent_executions_total']}",
                f"",
                f"# HELP ants_llm_tokens_total Total LLM tokens",
                f"# TYPE ants_llm_tokens_total counter",
                f"ants_llm_tokens_total {self.simulated_metrics['llm_tokens_total']}",
                f"",
                f"# HELP ants_llm_cost_usd_total Total LLM cost in USD",
                f"# TYPE ants_llm_cost_usd_total counter",
                f"ants_llm_cost_usd_total {self.simulated_metrics['llm_cost_usd_total']}",
                f"",
                f"# HELP ants_pheromone_deposits_total Total pheromone deposits",
                f"# TYPE ants_pheromone_deposits_total counter",
                f"ants_pheromone_deposits_total {self.simulated_metrics['pheromone_deposits_total']}",
                f"",
                f"# HELP ants_errors_total Total errors",
                f"# TYPE ants_errors_total counter",
                f"ants_errors_total {self.simulated_metrics['errors_total']}",
            ]
            return "\n".join(lines)

    def get_snapshot(self) -> MetricSnapshot:
        """Get current metrics snapshot."""
        if not self.simulation_mode:
            # In real mode, would query Prometheus
            return MetricSnapshot(
                timestamp=datetime.utcnow().isoformat(),
                agent_executions=0,
                total_tokens=0,
                total_cost_usd=0.0,
                avg_latency_ms=0.0,
                error_count=0
            )
        else:
            durations = self.simulated_metrics['agent_execution_duration_seconds']
            avg_latency = sum(durations) / len(durations) * 1000 if durations else 0.0

            return MetricSnapshot(
                timestamp=datetime.utcnow().isoformat(),
                agent_executions=self.simulated_metrics['agent_executions_total'],
                total_tokens=self.simulated_metrics['llm_tokens_total'],
                total_cost_usd=self.simulated_metrics['llm_cost_usd_total'],
                avg_latency_ms=avg_latency,
                error_count=self.simulated_metrics['errors_total']
            )


def create_metrics_client(**kwargs) -> MetricsClient:
    """
    Factory function to create Metrics Client.

    Args:
        **kwargs: Arguments for MetricsClient

    Returns:
        Configured MetricsClient
    """
    return MetricsClient(**kwargs)
