"""
Example: Advanced Observability and Monitoring for ANTS

Demonstrates comprehensive observability for multi-agent systems:
- Distributed tracing (OpenTelemetry)
- Metrics collection (Prometheus)
- Performance monitoring
- Cost tracking
- Anomaly detection

Observability is critical for production AI systems. This example shows:
- End-to-end tracing across agent workflows
- Real-time performance metrics
- LLM cost analytics
- Swarm coordination monitoring
- Error tracking and debugging

Integration with monitoring stack:
- OpenTelemetry → Jaeger/Zipkin (tracing)
- Prometheus → Grafana (metrics)
- Alert Manager → PagerDuty/Slack (alerts)
"""
import asyncio
import random
from src.core.observability import (
    create_tracing_client,
    create_metrics_client
)


async def example_1_distributed_tracing():
    """Example 1: Distributed tracing across agent workflow."""
    print("=" * 60)
    print("Example 1: Distributed Tracing")
    print("=" * 60 + "\n")

    tracing = create_tracing_client(
        service_name="ants-agents",
        enable_simulation=True
    )

    print("Tracing agent workflow with OpenTelemetry...\n")

    # Simulate agent execution with multiple spans
    print("Agent: Finance Reconciliation Agent")
    print("Task: Reconcile outstanding invoices\n")

    # Root span: Agent execution
    with tracing.start_agent_trace(
        agent_id="finance_reconciliation_01",
        agent_type="finance.reconciliation"
    ) as agent_span:
        agent_span.set_attribute("task", "reconcile_invoices")
        agent_span.set_attribute("user_id", "analyst_123")

        # Span 1: Perceive
        print("Step 1: Perceive (validate input)")
        with tracing.start_span("agent.perceive") as perceive_span:
            perceive_span.set_attribute("input_valid", True)
            await asyncio.sleep(0.05)  # Simulate work

        # Span 2: Retrieve
        print("Step 2: Retrieve (semantic search for similar cases)")
        with tracing.start_retrieval_trace(
            query="outstanding invoice reconciliation procedures",
            search_type="semantic"
        ) as retrieval_span:
            retrieval_span.set_attribute("results_count", 15)
            retrieval_span.set_attribute("top_score", 0.92)
            await asyncio.sleep(0.01)  # Simulate vector search

        # Span 3: Reason (LLM call)
        print("Step 3: Reason (LLM generates reconciliation plan)")
        with tracing.start_llm_trace(
            model="gpt-4-turbo",
            provider="azure_openai"
        ) as llm_span:
            llm_span.set_attribute("input_tokens", 1500)
            llm_span.set_attribute("output_tokens", 500)
            llm_span.set_attribute("temperature", 0.7)
            await asyncio.sleep(0.8)  # Simulate LLM latency

        # Span 4: Execute (tool calls)
        print("Step 4: Execute (call ERP tools)")
        with tracing.start_tool_trace(
            tool_name="erp.get_outstanding_invoices",
            tool_args={"days_overdue": 30}
        ) as tool_span:
            tool_span.set_attribute("invoices_found", 42)
            tool_span.set_attribute("total_amount_usd", 125000.00)
            await asyncio.sleep(0.3)  # Simulate ERP call

        # Span 5: Verify
        print("Step 5: Verify (validate results)")
        with tracing.start_span("agent.verify") as verify_span:
            verify_span.set_attribute("verification_passed", True)
            await asyncio.sleep(0.02)

        # Span 6: Learn
        print("Step 6: Learn (update procedural memory)")
        with tracing.start_span("agent.learn") as learn_span:
            learn_span.set_attribute("memory_updated", True)
            learn_span.add_event("memory_update", {
                "type": "procedural",
                "pattern": "invoice_reconciliation_success"
            })
            await asyncio.sleep(0.01)

    print("\n✓ Trace completed\n")

    # Show metrics
    metrics = tracing.get_metrics()
    print("Tracing Metrics:")
    print(f"  Total Spans: {metrics['total_spans']}")
    print(f"  Total Duration: {metrics['total_duration_ms']:.2f}ms")
    print(f"  Avg Duration: {metrics['avg_duration_ms']:.2f}ms")
    print(f"  Error Rate: {metrics['error_rate']:.1%}")
    print()

    print("Spans by Operation:")
    for operation, count in metrics['spans_by_operation'].items():
        print(f"  {operation}: {count}")
    print()


async def example_2_metrics_collection():
    """Example 2: Prometheus metrics collection."""
    print("=" * 60)
    print("Example 2: Metrics Collection")
    print("=" * 60 + "\n")

    metrics = create_metrics_client(
        service_name="ants-agents",
        enable_simulation=True
    )

    print("Collecting metrics for Prometheus/Grafana...\n")

    # Scenario 1: Agent execution metrics
    print("1. Recording agent executions:")
    for i in range(5):
        agent_type = random.choice(["finance", "hr", "security"])
        with metrics.measure_agent_execution(f"agent_{i}", agent_type):
            # Simulate work
            await asyncio.sleep(random.uniform(0.1, 0.5))

    print(f"   ✓ Recorded 5 agent executions")
    print()

    # Scenario 2: LLM usage metrics
    print("2. Recording LLM usage:")
    llm_calls = [
        ("gpt-4-turbo", 1500, 500, 0.045),
        ("claude-sonnet", 2000, 600, 0.018),
        ("gpt-4-turbo", 800, 300, 0.024),
        ("claude-haiku", 500, 200, 0.0006),
    ]

    for model, input_tokens, output_tokens, cost in llm_calls:
        metrics.record_llm_tokens(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost
        )

    total_tokens = sum(inp + out for _, inp, out, _ in llm_calls)
    total_cost = sum(cost for _, _, _, cost in llm_calls)

    print(f"   ✓ Recorded {len(llm_calls)} LLM calls")
    print(f"   Total Tokens: {total_tokens:,}")
    print(f"   Total Cost: ${total_cost:.4f}")
    print()

    # Scenario 3: Swarm metrics
    print("3. Recording swarm activity:")
    for i in range(10):
        pheromone_type = random.choice(["success", "danger", "task_available"])
        metrics.record_pheromone_deposit(
            pheromone_type=pheromone_type,
            strength=random.uniform(0.5, 1.0),
            agent_id=f"agent_{i % 5}"
        )

    print(f"   ✓ Recorded 10 pheromone deposits")
    print()

    # Scenario 4: System metrics
    print("4. Recording system health:")
    metrics.set_active_agents("finance", 15)
    metrics.set_active_agents("hr", 8)
    metrics.set_active_agents("security", 5)
    metrics.set_task_queue_size("high_priority", 23)
    metrics.set_task_queue_size("normal", 157)

    print(f"   ✓ Active agents: finance=15, hr=8, security=5")
    print(f"   ✓ Task queues: high_priority=23, normal=157")
    print()

    # Get metrics snapshot
    snapshot = metrics.get_snapshot()
    print("Metrics Snapshot:")
    print(f"  Timestamp: {snapshot.timestamp}")
    print(f"  Agent Executions: {snapshot.agent_executions}")
    print(f"  Total Tokens: {snapshot.total_tokens:,}")
    print(f"  Total Cost: ${snapshot.total_cost_usd:.4f}")
    print(f"  Avg Latency: {snapshot.avg_latency_ms:.2f}ms")
    print(f"  Errors: {snapshot.error_count}")
    print()


async def example_3_end_to_end_monitoring():
    """Example 3: End-to-end monitoring with tracing + metrics."""
    print("=" * 60)
    print("Example 3: End-to-End Monitoring")
    print("=" * 60 + "\n")

    tracing = create_tracing_client(enable_simulation=True)
    metrics = create_metrics_client(enable_simulation=True)

    print("Simulating production agent workflow with full observability...\n")

    print("Scenario: User asks finance agent to analyze Q4 revenue\n")

    # Track with both tracing and metrics
    with tracing.start_agent_trace(
        agent_id="finance_analyst_01",
        agent_type="finance.analysis"
    ) as trace_span:
        with metrics.measure_agent_execution("finance_analyst_01", "finance"):
            trace_span.set_attribute("query", "Analyze Q4 2024 revenue trends")

            # Step 1: Vector search
            print("1. Vector search for relevant financial data...")
            with tracing.start_retrieval_trace("Q4 2024 revenue data") as ret_span:
                with metrics.measure_vector_search("semantic"):
                    await asyncio.sleep(0.01)
                    ret_span.set_attribute("results_count", 25)

            # Step 2: LLM reasoning
            print("2. LLM analyzes financial trends...")
            with tracing.start_llm_trace("gpt-4-turbo") as llm_span:
                with metrics.measure_llm_latency("gpt-4-turbo"):
                    await asyncio.sleep(1.2)
                    llm_span.set_attribute("input_tokens", 3000)
                    llm_span.set_attribute("output_tokens", 800)

                    # Record metrics
                    metrics.record_llm_tokens(
                        model="gpt-4-turbo",
                        input_tokens=3000,
                        output_tokens=800,
                        cost_usd=0.095
                    )

            # Step 3: Generate visualizations
            print("3. Generate charts via tool call...")
            with tracing.start_tool_trace("visualization.create_chart") as tool_span:
                await asyncio.sleep(0.5)
                tool_span.set_attribute("chart_type", "line_chart")
                tool_span.set_attribute("data_points", 12)

            # Step 4: Deposit success pheromone
            print("4. Deposit success pheromone...")
            with tracing.start_pheromone_trace("success", 0.95):
                metrics.record_pheromone_deposit(
                    pheromone_type="success",
                    strength=0.95,
                    agent_id="finance_analyst_01"
                )

    print("\n✓ Workflow completed\n")

    # Show combined observability data
    trace_metrics = tracing.get_metrics()
    metric_snapshot = metrics.get_snapshot()

    print("Observability Summary:")
    print("\nTracing:")
    print(f"  Total Spans: {trace_metrics['total_spans']}")
    print(f"  Total Duration: {trace_metrics['total_duration_ms']:.2f}ms")

    print("\nMetrics:")
    print(f"  Agent Executions: {metric_snapshot.agent_executions}")
    print(f"  LLM Tokens: {metric_snapshot.total_tokens:,}")
    print(f"  LLM Cost: ${metric_snapshot.total_cost_usd:.4f}")
    print()


async def example_4_cost_analytics():
    """Example 4: LLM cost analytics and optimization."""
    print("=" * 60)
    print("Example 4: Cost Analytics")
    print("=" * 60 + "\n")

    metrics = create_metrics_client(enable_simulation=True)

    print("Tracking LLM costs across different models and agents...\n")

    # Simulate 100 agent executions with different models
    print("Simulating 100 agent executions...\n")

    model_usage = {
        "gpt-4-turbo": {"calls": 0, "tokens": 0, "cost": 0.0, "rate": 0.01},
        "claude-opus": {"calls": 0, "tokens": 0, "cost": 0.0, "rate": 0.015},
        "claude-sonnet": {"calls": 0, "tokens": 0, "cost": 0.0, "rate": 0.003},
        "claude-haiku": {"calls": 0, "tokens": 0, "cost": 0.0, "rate": 0.00025},
    }

    for i in range(100):
        # Intelligent routing based on task complexity
        if i % 10 == 0:  # 10% complex tasks
            model = "gpt-4-turbo"
            tokens = random.randint(2000, 5000)
        elif i % 3 == 0:  # 30% medium tasks
            model = "claude-sonnet"
            tokens = random.randint(1000, 3000)
        else:  # 60% simple tasks
            model = "claude-haiku"
            tokens = random.randint(500, 1500)

        cost = (tokens / 1000) * model_usage[model]["rate"]

        metrics.record_llm_tokens(
            model=model,
            input_tokens=int(tokens * 0.7),
            output_tokens=int(tokens * 0.3),
            cost_usd=cost
        )

        model_usage[model]["calls"] += 1
        model_usage[model]["tokens"] += tokens
        model_usage[model]["cost"] += cost

    # Print cost breakdown
    print("Cost Breakdown by Model:\n")
    total_cost = 0.0
    total_tokens = 0

    for model, stats in sorted(model_usage.items(), key=lambda x: x[1]["cost"], reverse=True):
        if stats["calls"] > 0:
            avg_cost_per_call = stats["cost"] / stats["calls"]
            print(f"{model}:")
            print(f"  Calls: {stats['calls']}")
            print(f"  Tokens: {stats['tokens']:,}")
            print(f"  Total Cost: ${stats['cost']:.4f}")
            print(f"  Avg Cost/Call: ${avg_cost_per_call:.4f}")
            print()

            total_cost += stats["cost"]
            total_tokens += stats["tokens"]

    print(f"Total Cost: ${total_cost:.4f}")
    print(f"Total Tokens: {total_tokens:,}")
    print(f"Avg Cost/Token: ${total_cost/total_tokens:.6f}")
    print()

    # Compare with naive approach (all GPT-4)
    naive_cost = (total_tokens / 1000) * 0.01
    savings = naive_cost - total_cost
    savings_pct = (savings / naive_cost) * 100

    print("Cost Optimization:")
    print(f"  Intelligent Routing: ${total_cost:.4f}")
    print(f"  All GPT-4 Turbo: ${naive_cost:.4f}")
    print(f"  Savings: ${savings:.4f} ({savings_pct:.1f}%)")
    print()


async def example_5_performance_monitoring():
    """Example 5: Agent performance monitoring and anomaly detection."""
    print("=" * 60)
    print("Example 5: Performance Monitoring")
    print("=" * 60 + "\n")

    tracing = create_tracing_client(enable_simulation=True)
    metrics = create_metrics_client(enable_simulation=True)

    print("Monitoring agent performance and detecting anomalies...\n")

    # Simulate normal performance
    print("Phase 1: Normal operation (baseline)")
    latencies_normal = []

    for i in range(20):
        with tracing.start_agent_trace(f"agent_{i%5}", "finance"):
            with metrics.measure_agent_execution(f"agent_{i%5}", "finance"):
                latency = random.gauss(200, 50) / 1000  # ~200ms ± 50ms
                latencies_normal.append(latency * 1000)
                await asyncio.sleep(latency)

    avg_normal = sum(latencies_normal) / len(latencies_normal)
    print(f"  Avg Latency: {avg_normal:.2f}ms")
    print(f"  Min/Max: {min(latencies_normal):.2f}ms / {max(latencies_normal):.2f}ms")
    print()

    # Simulate performance degradation
    print("Phase 2: Performance degradation detected")
    latencies_degraded = []

    for i in range(10):
        with tracing.start_agent_trace(f"agent_{i%5}", "finance"):
            with metrics.measure_agent_execution(f"agent_{i%5}", "finance"):
                latency = random.gauss(800, 200) / 1000  # ~800ms (degraded!)
                latencies_degraded.append(latency * 1000)
                await asyncio.sleep(latency)

    avg_degraded = sum(latencies_degraded) / len(latencies_degraded)
    print(f"  Avg Latency: {avg_degraded:.2f}ms")
    print(f"  Min/Max: {min(latencies_degraded):.2f}ms / {max(latencies_degraded):.2f}ms")
    print()

    # Anomaly detection
    threshold = avg_normal * 2.0  # 2x normal is anomaly
    if avg_degraded > threshold:
        print(f"🚨 ALERT: Performance Anomaly Detected!")
        print(f"  Baseline: {avg_normal:.2f}ms")
        print(f"  Current: {avg_degraded:.2f}ms")
        print(f"  Degradation: {((avg_degraded/avg_normal - 1) * 100):.1f}%")
        print(f"  Threshold: {threshold:.2f}ms")
        print()

        print("Recommended Actions:")
        print("  1. Check LLM provider status (API latency spike?)")
        print("  2. Review vector DB performance (slow searches?)")
        print("  3. Check agent load (too many concurrent agents?)")
        print("  4. Scale up resources (add more workers)")
    print()


async def example_6_error_tracking():
    """Example 6: Error tracking and debugging."""
    print("=" * 60)
    print("Example 6: Error Tracking")
    print("=" * 60 + "\n")

    tracing = create_tracing_client(enable_simulation=True)
    metrics = create_metrics_client(enable_simulation=True)

    print("Demonstrating error tracking for debugging...\n")

    # Scenario 1: Successful execution
    print("1. Successful execution:")
    try:
        with tracing.start_agent_trace("agent_01", "finance") as span:
            with metrics.measure_agent_execution("agent_01", "finance"):
                span.set_attribute("task", "reconcile_invoices")
                await asyncio.sleep(0.1)
                print("   ✓ Completed successfully")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    print()

    # Scenario 2: Tool call failure
    print("2. Tool call failure:")
    try:
        with tracing.start_agent_trace("agent_02", "hr") as span:
            with metrics.measure_agent_execution("agent_02", "hr"):
                span.set_attribute("task", "onboard_employee")

                with tracing.start_tool_trace("hr.create_account") as tool_span:
                    tool_span.set_attribute("employee_id", "E12345")
                    # Simulate tool failure
                    raise Exception("HR API timeout after 30s")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        metrics.record_error(
            error_type="timeout",
            component="hr_api"
        )
        print("   ✓ Error logged in metrics")
    print()

    # Scenario 3: LLM failure
    print("3. LLM call failure:")
    try:
        with tracing.start_agent_trace("agent_03", "security") as span:
            with metrics.measure_agent_execution("agent_03", "security"):
                span.set_attribute("task", "analyze_threat")

                with tracing.start_llm_trace("gpt-4-turbo") as llm_span:
                    # Simulate rate limit error
                    llm_span.add_event("rate_limit_hit", {
                        "retry_after": 60,
                        "request_id": "req_abc123"
                    })
                    raise Exception("Rate limit exceeded: 429")

    except Exception as e:
        print(f"   ✗ Error: {e}")
        metrics.record_error(
            error_type="rate_limit",
            component="llm_provider"
        )
        print("   ✓ Error logged with retry info")
    print()

    # Show error summary
    trace_metrics = tracing.get_metrics()
    print("Error Summary:")
    print(f"  Total Executions: {trace_metrics['total_spans'] // 3}")  # Approximate
    print(f"  Errors: {trace_metrics['errors']}")
    print(f"  Error Rate: {trace_metrics['error_rate']:.1%}")
    print()


async def example_7_grafana_dashboards():
    """Example 7: Grafana dashboard queries."""
    print("=" * 60)
    print("Example 7: Grafana Dashboard Queries")
    print("=" * 60 + "\n")

    print("Example PromQL queries for Grafana dashboards:\n")

    dashboards = {
        "Agent Performance Dashboard": [
            ("Agent Execution Rate", "rate(ants_agent_executions_total[5m])"),
            ("Agent Latency (P95)", "histogram_quantile(0.95, rate(ants_agent_execution_duration_seconds_bucket[5m]))"),
            ("Agent Success Rate", "sum(rate(ants_agent_executions_total{status=\"success\"}[5m])) / sum(rate(ants_agent_executions_total[5m]))"),
            ("Active Agents by Type", "ants_active_agents"),
        ],
        "Cost Analytics Dashboard": [
            ("LLM Cost per Hour", "rate(ants_llm_cost_usd_total[1h]) * 3600"),
            ("Token Usage by Model", "sum by (model) (rate(ants_llm_tokens_total[5m]))"),
            ("Cost by Provider", "sum by (provider) (rate(ants_llm_cost_usd_total[1h])) * 3600"),
            ("Cost per Agent Type", "sum by (agent_type) (rate(ants_llm_cost_usd_total[5m]))"),
        ],
        "Swarm Coordination Dashboard": [
            ("Pheromone Deposit Rate", "rate(ants_pheromone_deposits_total[5m])"),
            ("Task Queue Depth", "ants_task_queue_size"),
            ("Agent Utilization", "avg(rate(ants_agent_executions_total[5m])) by (agent_type)"),
            ("Cross-Agent Communication", "rate(ants_pheromone_deposits_total[5m])"),
        ],
        "System Health Dashboard": [
            ("Error Rate", "rate(ants_errors_total[5m])"),
            ("Memory Usage", "ants_memory_usage_bytes"),
            ("CPU Usage", "ants_cpu_usage_percent"),
            ("Vector Search Latency", "histogram_quantile(0.95, rate(ants_vector_search_latency_seconds_bucket[5m]))"),
        ]
    }

    for dashboard_name, queries in dashboards.items():
        print(f"{dashboard_name}:")
        for panel_name, query in queries:
            print(f"  {panel_name}:")
            print(f"    {query}")
        print()

    print("To create dashboards:")
    print("1. Start Prometheus: prometheus --config.file=prometheus.yml")
    print("2. Start Grafana: grafana-server")
    print("3. Add Prometheus datasource in Grafana")
    print("4. Import dashboard JSON with above queries")
    print("5. Set refresh interval (e.g., 5s for real-time)")
    print()


async def main():
    """Run all observability examples."""
    print("\n")
    print("█" * 60)
    print("ANTS Advanced Observability Examples")
    print("OpenTelemetry + Prometheus + Grafana")
    print("█" * 60)
    print("\n")

    await example_1_distributed_tracing()
    await example_2_metrics_collection()
    await example_3_end_to_end_monitoring()
    await example_4_cost_analytics()
    await example_5_performance_monitoring()
    await example_6_error_tracking()
    await example_7_grafana_dashboards()

    print("=" * 60)
    print("All Examples Complete")
    print("=" * 60)
    print("\nKey Takeaways:")
    print("✓ Distributed tracing provides end-to-end visibility")
    print("✓ Metrics enable real-time performance monitoring")
    print("✓ Cost analytics optimize LLM spend")
    print("✓ Anomaly detection catches performance degradation")
    print("✓ Error tracking enables rapid debugging")
    print("✓ Grafana dashboards visualize system health")
    print()
    print("Observability Stack:")
    print("  • OpenTelemetry: Distributed tracing (traces)")
    print("  • Prometheus: Time-series metrics (metrics)")
    print("  • Grafana: Visualization dashboards (UI)")
    print("  • Jaeger/Zipkin: Trace visualization (optional)")
    print("  • Alert Manager: Alerting (Slack, PagerDuty)")
    print()
    print("Production deployment:")
    print("  1. Install: pip install opentelemetry-api prometheus-client")
    print("  2. Configure: OTLP endpoint, Prometheus scraping")
    print("  3. Deploy: Collectors, exporters, dashboards")
    print("  4. Monitor: Set up alerts for errors, latency, cost")
    print()


if __name__ == "__main__":
    asyncio.run(main())
