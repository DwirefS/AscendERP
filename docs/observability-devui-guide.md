# ANTS Observability & DevUI Guide

Comprehensive guide for visual debugging and production observability in ANTS.

Based on Microsoft Agent Framework official patterns:
- [Agent Framework](https://github.com/microsoft/agent-framework)
- [DevUI Sample](https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/devui)
- [Observability Sample](https://github.com/microsoft/agent-framework/tree/main/python/samples/getting_started/observability)
- [Agent Framework Samples](https://github.com/microsoft/Agent-Framework-Samples)

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [DevUI - Visual Debugging](#devui---visual-debugging)
4. [OpenTelemetry - Production Observability](#opentelemetry---production-observability)
5. [Azure Monitor Integration](#azure-monitor-integration)
6. [Aspire Dashboard (Local Development)](#aspire-dashboard-local-development)
7. [AG-UI Protocol](#ag-ui-protocol)
8. [Best Practices](#best-practices)

## Overview

ANTS provides two complementary observability tools following Microsoft Agent Framework patterns:

### DevUI (Development)
Visual debugging interface showing real-time agent reasoning chains, memory state, policy evaluations, and council deliberations.

**Use Cases:**
- Development and testing
- Debugging agent behavior
- Understanding reasoning chains
- Inspecting memory and policy decisions

### OpenTelemetry (Production)
Distributed tracing, metrics, and logging for production monitoring.

**Use Cases:**
- Production observability
- Performance monitoring
- Cost tracking (token usage)
- Multi-agent coordination analysis
- Azure Monitor integration

## Installation

```bash
# Install observability dependencies
pip install -r requirements-observability.txt

# Or install specific components
pip install opentelemetry-api opentelemetry-sdk
pip install azure-monitor-opentelemetry
pip install fastapi uvicorn websockets
```

## DevUI - Visual Debugging

### Quick Start

**1. Enable DevUI**
```bash
export ANTS_DEVUI_ENABLED=true
```

**2. Start DevUI Server**
```python
from src.core.observability_config import start_devui_server

# Start server (blocking)
start_devui_server()

# Or start in background
start_devui_server(background=True)
```

**3. Run Agents**

Agents automatically stream reasoning steps to DevUI when `ANTS_DEVUI_ENABLED=true`.

```python
from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

agent = MyAgent(config=AgentConfig(name="test-agent"))
await agent.initialize(memory, policy_engine, llm)

# Reasoning steps automatically captured in DevUI
result = await agent.run(input_data, context)
```

**4. Open DevUI Interface**

Navigate to: `http://localhost:8090`

### DevUI Interface

The DevUI interface has three panels:

#### Left Panel: Agent List
- Shows all active agents
- Click to select agent
- Auto-refreshes every 5 seconds

#### Center Panel: Reasoning Chain
- Real-time stream of reasoning steps
- Color-coded by phase:
  - **Phase 1 (Perceive)**: Blue
  - **Phase 2 (Retrieve)**: Purple
  - **Phase 3 (Reason)**: Pink
  - **Phase 4 (Execute)**: Orange
  - **Phase 5 (Verify)**: Green
  - **Phase 6 (Learn)**: Light Blue
- Shows input/output, latency, token usage

#### Right Panel: Inspector
- Click any step to inspect details
- Memory snapshot view
- Policy evaluation results

### Configuration

```bash
# Enable DevUI
export ANTS_DEVUI_ENABLED=true

# Optional: Custom host/port
export DEVUI_HOST=0.0.0.0
export DEVUI_PORT=8090
```

### Programmatic Usage

```python
from src.devtools.devui_server import debugger

# Manually capture reasoning step
await debugger.capture_reasoning_step(
    agent_id="agent-123",
    step_type="reason",
    phase_number=3,
    input_data={"query": "Analyze invoice"},
    output_data={"action": "reconcile", "confidence": 0.95},
    metadata={
        "memory_snapshot": {...},
        "policy_result": {...},
        "latency_ms": 45.2
    }
)

# Capture council deliberation
await debugger.capture_council_deliberation(
    council_id="finance-council",
    decision_type="approve_transaction",
    phase="resolve",
    agent_contributions=[...],
    consensus_score=0.87,
    final_decision={...}
)
```

## OpenTelemetry - Production Observability

### Quick Start

**1. Enable Instrumentation**
```bash
export ENABLE_INSTRUMENTATION=true
```

**2. Configure OpenTelemetry**

```python
from src.core.observability_config import setup_observability

# Development: Console output
setup_observability(environment="development", enable_console_output=True)

# Production: Azure Monitor
setup_observability(environment="production", enable_azure_monitor=True)
```

**3. Agents Automatically Instrumented**

All agents inheriting from `BaseAgent` automatically emit:
- Distributed traces
- Performance metrics
- Token usage metrics
- Error tracking

### Environment Variables

```bash
# Enable telemetry collection
export ENABLE_INSTRUMENTATION=true

# Console output (development)
export ENABLE_CONSOLE_EXPORTERS=true

# Include prompts/responses in traces
export ENABLE_SENSITIVE_DATA=false  # Default: false for security

# OTLP endpoint (for Aspire Dashboard, Jaeger, etc.)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Service identification
export OTEL_SERVICE_NAME=ants-platform
export SERVICE_VERSION=1.0.0
export ENVIRONMENT=development
```

### Captured Metrics

**Agent Execution Metrics:**
```python
# Counter: Agent executions
ants.agent.executions{agent_type, status}

# Histogram: Execution latency
ants.agent.latency{agent_type}

# Counter: LLM token usage
ants.llm.tokens{model, token_type}

# Counter: Council decisions
ants.council.decisions{council_id, decision_type, agent_count}

# Counter: Swarm events
ants.swarm.events{event_type}

# Counter: Policy evaluations
ants.policy.evaluations{policy, decision, risk_level}
```

### Distributed Tracing

**Automatic Tracing:**

Every agent execution creates a trace with:
- Agent ID, type, operation
- Tenant and trace IDs
- 6-phase span hierarchy (perceive → retrieve → reason → execute → verify → learn)
- Latency per phase
- Token usage
- Policy evaluation results

**Example Trace:**
```
AgentExecution [200ms]
├─ Perceive [10ms]
├─ Retrieve [30ms]
│  └─ VectorSearch [25ms]
├─ Reason [40ms]
│  └─ LLMCall [38ms] {tokens: 850}
├─ Execute [100ms]
│  ├─ PolicyCheck [5ms] {decision: allow}
│  └─ ToolExecution [90ms]
├─ Verify [15ms]
└─ Learn [5ms]
```

### Custom Instrumentation

```python
from src.core.observability import (
    tracer,
    trace_llm_call,
    trace_council_decision,
    trace_policy_evaluation
)

# Custom span
with tracer.start_as_current_span("custom_operation") as span:
    span.set_attribute("tenant.id", tenant_id)
    result = await do_work()
    span.set_attribute("result_count", len(result))

# Record LLM call
trace_llm_call(
    model="llama-3.1-nemotron-nano-8b",
    prompt_tokens=500,
    completion_tokens=200,
    total_tokens=700
)

# Record council decision
trace_council_decision(
    council_id="finance-council",
    decision_type="approve_payment",
    consensus_score=0.92,
    agent_count=5
)

# Record policy evaluation
trace_policy_evaluation(
    policy_name="pii_protection",
    decision="allow",
    risk_level="low"
)
```

## Azure Monitor Integration

### Setup

**1. Create Application Insights Resource**

Azure Portal → Create Resource → Application Insights

**2. Get Connection String**

Copy from Application Insights → Properties → Connection String

**3. Configure ANTS**

```bash
export APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=..."
export ENABLE_AZURE_MONITOR=true
export ENABLE_INSTRUMENTATION=true
```

**4. Initialize**

```python
from src.core.observability_config import setup_observability

setup_observability(
    environment="production",
    enable_azure_monitor=True
)
```

### Azure Monitor Features

- **Live Metrics**: Real-time agent performance
- **Application Map**: Multi-agent dependencies
- **Transaction Search**: Individual execution traces
- **Failures**: Error tracking and alerts
- **Performance**: Latency analysis
- **Metrics Explorer**: Custom metrics visualization

### Queries (Kusto/KQL)

**Agent execution latency:**
```kusto
customMetrics
| where name == "ants.agent.latency"
| summarize avg(value), percentile(value, 95) by tostring(customDimensions.agent_type)
| render timechart
```

**Token usage by model:**
```kusto
customMetrics
| where name == "ants.llm.tokens"
| summarize sum(value) by tostring(customDimensions.model), tostring(customDimensions.token_type)
| render piechart
```

**Policy denials:**
```kusto
customMetrics
| where name == "ants.policy.evaluations"
| where tostring(customDimensions.decision) == "deny"
| summarize count() by tostring(customDimensions.policy), tostring(customDimensions.risk_level)
```

## Aspire Dashboard (Local Development)

### What is Aspire Dashboard?

Microsoft's free, open-source telemetry viewer for local development.

- Web UI for viewing traces, metrics, logs
- OTLP endpoint for receiving telemetry
- No cloud dependencies
- Perfect for development

### Start Aspire Dashboard

**Using Docker:**
```bash
docker run --rm -it -d \
  -p 18888:18888 \
  -p 4317:18889 \
  --name aspire-dashboard \
  mcr.microsoft.com/dotnet/aspire-dashboard:latest
```

**Using Docker Compose:**
```yaml
services:
  aspire-dashboard:
    image: mcr.microsoft.com/dotnet/aspire-dashboard:latest
    ports:
      - "18888:18888"  # Web UI
      - "4317:18889"   # OTLP endpoint
    environment:
      - ASPNETCORE_URLS=http://+:18888
```

### Configure ANTS

```bash
export ENABLE_INSTRUMENTATION=true
export ENABLE_ASPIRE_DASHBOARD=true
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

### Access Dashboard

Navigate to: `http://localhost:18888`

Features:
- **Traces**: Distributed tracing view
- **Metrics**: Real-time metrics charts
- **Logs**: Structured log viewer
- **Resources**: Service discovery

## AG-UI Protocol

Server-Sent Events (SSE) streaming for agent-user communication.

### Features

- Real-time streaming of agent thoughts and actions
- Human-in-the-loop approval mechanism
- Standardized message format
- Progress tracking

### Usage

```python
from src.devtools.ag_ui_protocol import AGUIProtocol, StreamingResponse, ApprovalRequest

protocol = AGUIProtocol()

# Create SSE stream
async with StreamingResponse(protocol, session_id) as stream:
    # Stream thinking
    await stream.thinking("Analyzing invoice data...")

    # Stream tool use
    await stream.tool_use("vector_search", {"query": "invoice 12345"})

    # Stream tool result
    result = await execute_search()
    await stream.tool_result("vector_search", result, success=True)

    # Request human approval for high-risk action
    approval = await stream.request_approval(
        ApprovalRequest(
            request_id="approve-payment",
            action="transfer_funds",
            description="Transfer $50,000 to vendor",
            risk_level="high",
            context={"amount": 50000, "vendor": "ACME Corp"},
            timeout_seconds=60
        )
    )

    if approval == "approved":
        await stream.response("Payment approved and processed")
    else:
        await stream.response("Payment cancelled by user")
```

## Best Practices

### Development

✅ **DO:**
- Enable both DevUI and Aspire Dashboard for comprehensive debugging
- Use console exporters for immediate feedback
- Enable sensitive data logging only in dev (never production)
- Review reasoning chains in DevUI to understand agent behavior

❌ **DON'T:**
- Commit `.env` files with connection strings
- Enable sensitive data logging in production
- Run DevUI in production (development tool only)

### Production

✅ **DO:**
- Use Azure Monitor for production observability
- Set up alerts on error rates and latency spikes
- Monitor token usage for cost optimization
- Use distributed tracing to debug multi-agent issues
- Implement sampling for high-traffic scenarios

❌ **DON'T:**
- Enable console exporters (performance impact)
- Collect sensitive data in traces
- Ignore instrumentation overhead
- Over-instrument (balance visibility vs. performance)

### Security

✅ **DO:**
- Use Azure Managed Identity for Application Insights
- Mask PII in custom spans
- Restrict DevUI to localhost in dev
- Rotate Application Insights keys regularly

❌ **DON'T:**
- Log prompts containing PII
- Expose DevUI publicly
- Hardcode connection strings
- Enable `ENABLE_SENSITIVE_DATA` in production

## Troubleshooting

### DevUI Not Showing Agents

**Check:**
```bash
# 1. Is DevUI enabled?
echo $ANTS_DEVUI_ENABLED  # Should be "true"

# 2. Is server running?
curl http://localhost:8090/api/agents

# 3. Check agent instrumentation
# Agents must inherit from BaseAgent and have debugger imported
```

### No Telemetry in Azure Monitor

**Check:**
```bash
# 1. Is instrumentation enabled?
echo $ENABLE_INSTRUMENTATION  # Should be "true"

# 2. Is connection string set?
echo $APPLICATIONINSIGHTS_CONNECTION_STRING

# 3. Check Azure Monitor status
from src.core.observability_config import print_observability_status
print_observability_status()
```

### Aspire Dashboard Connection Failed

**Check:**
```bash
# 1. Is Aspire Dashboard running?
docker ps | grep aspire-dashboard

# 2. Is endpoint correct?
echo $OTEL_EXPORTER_OTLP_ENDPOINT  # Should be http://localhost:4317

# 3. Test connection
curl http://localhost:4317/v1/traces
```

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_INSTRUMENTATION` | `false` | Enable all telemetry |
| `ANTS_DEVUI_ENABLED` | `false` | Enable DevUI server |
| `DEVUI_HOST` | `localhost` | DevUI server host |
| `DEVUI_PORT` | `8090` | DevUI server port |
| `ENABLE_CONSOLE_EXPORTERS` | `false` | Output to console |
| `ENABLE_SENSITIVE_DATA` | `false` | Include prompts/responses |
| `ENABLE_AZURE_MONITOR` | `false` | Enable Azure Monitor |
| `ENABLE_ASPIRE_DASHBOARD` | `false` | Use Aspire Dashboard |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://localhost:4317` | OTLP endpoint |
| `OTEL_SERVICE_NAME` | `ants-platform` | Service name |
| `SERVICE_VERSION` | `1.0.0` | Service version |
| `ENVIRONMENT` | `development` | Deployment environment |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | None | Azure Monitor connection |

## References

- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Agent Framework Samples](https://github.com/microsoft/Agent-Framework-Samples)
- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Azure Monitor OpenTelemetry](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-python)
- [Aspire Dashboard](https://learn.microsoft.com/en-us/dotnet/aspire/fundamentals/dashboard)
