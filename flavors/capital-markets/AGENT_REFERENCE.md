# Capital Markets Agents - Quick Reference

## File Structure

```
flavors/capital-markets/agents/
├── __init__.py                      (27 lines)  - Package imports
├── trading_agent.py                 (480 lines) - Order execution
├── risk_management_agent.py         (534 lines) - Risk monitoring
├── portfolio_manager_agent.py       (504 lines) - Portfolio optimization
├── client_service_agent.py          (476 lines) - Client management
├── compliance_agent.py              (419 lines) - Regulatory compliance
└── derivatives_agent.py             (623 lines) - Options pricing
```

## Agent Quick Reference

### 1. TradingAgent
```python
from flavors.capital-markets.agents import TradingAgent

agent = TradingAgent()
await agent.initialize(memory, policy_engine, llm)

result = await agent.run(
    input_data={
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 1000,
        "limit_price": 150.00,
        "order_type": "limit",
        "urgency": "normal",
        "client_id": "CLIENT_123"
    },
    context=agent_context
)

# Result contains:
# - status: "executed" | "rejected" | "error"
# - execution_result: {fills: [...]}
# - report: {...execution summary...}
```

**Input Parameters:**
- `ticker` (str): Symbol (e.g., "AAPL")
- `side` (str): "buy" or "sell"
- `quantity` (float): Number of shares
- `limit_price` (float, optional): Max/min price
- `order_type` (str): "market", "limit", "vwap", "twap"
- `urgency` (str): "immediate", "normal", "patient"
- `client_id` (str): Client identifier

**Output Fields:**
- `status`: Execution status
- `execution_result`: Fills and execution details
- `report`: Summary with slippage analysis

---

### 2. RiskManagementAgent
```python
from flavors.capital-markets.agents import RiskManagementAgent

agent = RiskManagementAgent()
await agent.initialize(memory, policy_engine, llm)

result = await agent.run(
    input_data={
        "portfolio_id": "PORTFOLIO_001",
        "assessment_type": "on_demand",
        "positions": [
            {"ticker": "AAPL", "quantity": 100, "value": 15000, "type": "stock"},
            {"ticker": "SPY", "quantity": 50, "value": 22500, "type": "stock"},
            # ... more positions
        ]
    },
    context=agent_context
)

# Result contains risk metrics:
# - var_95, var_99: Value at Risk
# - portfolio_delta, gamma, vega: Greeks
# - concentration_hhi: Concentration index
# - breaches: [{type, limit, current, severity}]
```

**Assessment Types:**
- `continuous`: Regular monitoring
- `on_demand`: One-time assessment
- `stress_test`: Scenario analysis

**Output Metrics:**
- VaR at 95% and 99% confidence
- Greeks: Delta, Gamma, Vega, Theta, Rho
- HHI concentration index
- Sector exposure
- Stress test results
- Breach list with severity

---

### 3. PortfolioManagerAgent
```python
from flavors.capital-markets.agents import PortfolioManagerAgent

agent = PortfolioManagerAgent()
await agent.initialize(memory, policy_engine, llm)

result = await agent.run(
    input_data={
        "portfolio_id": "PORTFOLIO_001",
        "action": "rebalance",
        "drift_threshold": 0.05,  # 5% default
        "rebalance_params": {
            "max_trade_size": 1000000
        }
    },
    context=agent_context
)

# Actions:
# - "monitor": Check drift status
# - "rebalance": Execute if drift > threshold
# - "optimize": Run MPT optimization
# - "report": Generate performance report
```

**Output:**
- `drift`: Current allocation drift
- `rebalancing_trades`: Specific trades needed (if rebalancing)
- `needs_approval`: True if > $1M rebalancing
- `execution_result`: Trades executed
- `optimization_result`: Recommended allocation (if optimize)
- `report`: Performance metrics (if report)

---

### 4. ClientServiceAgent
```python
from flavors.capital-markets.agents import ClientServiceAgent

agent = ClientServiceAgent()
await agent.initialize(memory, policy_engine, llm)

result = await agent.run(
    input_data={
        "client_id": "CLIENT_123",
        "query_type": "portfolio_summary",  # | "transaction_history" | "general_inquiry"
        "message": "What's my current allocation?",
        "parameters": {
            "days": 90,
            "limit": 20
        }
    },
    context=agent_context
)

# Result contains:
# - response: Formatted answer to client
# - portfolio_summary or transaction_history
# - callback_scheduled (if needed)
# - ticket_created (if needed)
```

**Query Types:**
- `portfolio_summary`: Current holdings and performance
- `transaction_history`: Recent trades
- `general_inquiry`: Free-form question
- `callback`: Schedule relationship manager call

---

### 5. ComplianceAgent
```python
from flavors.capital-markets.agents import ComplianceAgent

agent = ComplianceAgent()
await agent.initialize(memory, policy_engine, llm)

result = await agent.run(
    input_data={
        "request_type": "kyc",  # | "aml" | "pre_trade" | "reporting"
        "entity_id": "CLIENT_123",
        "entity_type": "individual",
        "entity_data": {
            "name": "John Smith",
            "dob": "1980-01-15",
            "address": "123 Main St"
        },
        "transaction": {  # For pre_trade
            "ticker": "AAPL",
            "quantity": 10000,
            "price": 150.00
        }
    },
    context=agent_context
)

# Result contains:
# - status: "approved" | "flagged" | "rejected" | "pending"
# - checks_performed: List of checks run
# - issues: [{type, severity, details}]
# - requires_escalation: Boolean
```

**Request Types:**
- `kyc`: Identity and PEP verification
- `aml`: Anti-money laundering screening
- `pre_trade`: Position limits and restrictions
- `reporting`: Regulatory reporting

**Compliance Status:**
- `approved`: All checks passed
- `flagged`: Issues found, review required
- `rejected`: Blocked by compliance
- `pending`: Additional info needed

---

### 6. DerivativesAgent
```python
from flavors.capital-markets.agents import DerivativesAgent

agent = DerivativesAgent()
await agent.initialize(memory, policy_engine, llm)

result = await agent.run(
    input_data={
        "request_type": "price",  # | "hedge" | "analyze" | "backtest"
        "instrument_data": {
            "type": "call",  # | "put"
            "underlying": "AAPL",
            "strike": 150.00,
            "expiry": "2026-06-15",
            "spot": 152.00,
            "volatility": 0.25,  # 25%
            "rate": 0.05,  # 5%
            "dividend_yield": 0.02  # 2%
        },
        "parameters": {
            "strategy": "long_call"  # For backtest
        }
    },
    context=agent_context
)

# Result contains:
# - pricing: {fair_value, bid, ask, greeks}
# - hedging_recommendation: Hedge ratios
# - volatility_analysis: Vol surface
# - backtest_results: Performance metrics
```

**Greeks Provided:**
- Delta: Directional exposure
- Gamma: Delta acceleration
- Vega: Volatility exposure
- Theta: Time decay
- Rho: Interest rate exposure

**Pricing Models:**
- Black-Scholes: European options
- Binomial: American options (50 steps)

---

## Common Response Structure

All agents return AgentResult:
```python
{
    "success": bool,
    "output": Any,           # Main result
    "trace_id": str,        # Request tracking
    "actions_taken": [      # Execution history
        {
            "action": {...},
            "result": {...},
            "policy_decision": {...}
        }
    ],
    "tokens_used": int,     # LLM tokens
    "latency_ms": float,    # Execution time
    "confidence": float,    # 0.0-1.0 confidence
    "error": str | None     # Error message if failed
}
```

---

## Error Handling

All agents include graceful error handling:

```python
try:
    result = await agent.run(input_data, context)
except Exception as e:
    # Agent returns AgentResult with success=False
    logger.error("agent_failed", error=str(e))
    # Always returns AgentResult, never raises
```

---

## Memory Integration

Agents automatically store learnings:

```python
# Procedural Memory (patterns and strategies)
await memory.store_procedural(
    pattern={"strategy": "vwap", "success_rate": 0.92},
    success_rate=0.92,
    agent_id=agent.config.agent_id,
    tenant_id=context.tenant_id
)

# Episodic Memory (historical decisions)
await memory.store_episodic(
    content={"input": input_data, "result": result},
    agent_id=agent.config.agent_id,
    tenant_id=context.tenant_id
)

# Retrieval
procedural = await memory.retrieve_procedural(
    context={"ticker": "AAPL"},
    agent_id=agent.config.agent_id,
    limit=5
)
```

---

## Configuration Options

```python
from src.core.agent.base import AgentConfig

config = AgentConfig(
    agent_id="custom_id",           # Auto-generated if not provided
    name="Trading Agent",            # Display name
    description="Executes trades",   # Description
    version="1.0.0",                 # Version string
    tenant_id="tenant_123",          # Tenant identifier
    tools=[...],                     # Available tools
    max_iterations=15,               # Max reasoning iterations
    timeout_seconds=60,              # Timeout in seconds
    memory_enabled=True,             # Enable memory storage
    episodic_memory_limit=1000,      # Max episodic memories
    policy_enabled=True,             # Enable policy checks
    require_approval_threshold=0.8,  # Policy threshold
    model_name="gpt-4-turbo",        # LLM model
    temperature=0.3,                 # LLM temperature
    max_tokens=2048                  # Max tokens per call
)
```

---

## Logging Examples

All agents log structured data:

```python
logger.info(
    "perceiving_order_request",
    trace_id=context.trace_id,
    ticker="AAPL",
    side="buy",
    quantity=1000
)

logger.warning(
    "llm_reasoning_failed",
    error=str(e),
    fallback="rule_based"
)

logger.error(
    "order_execution_failed",
    trace_id=context.trace_id,
    error=str(e)
)
```

---

## Performance Expectations

| Agent | Typical Latency | Max Time | Confidence |
|-------|----------------|----------|-----------|
| Trading | 500ms | 60s | 0.75-0.95 |
| Risk | 2000ms | 120s | 0.80-0.95 |
| Portfolio | 1500ms | 120s | 0.75-0.95 |
| Client | 200ms | 60s | 0.70-0.95 |
| Compliance | 800ms | 90s | 0.75-0.95 |
| Derivatives | 1200ms | 120s | 0.80-0.95 |

---

## Dependencies

**Required:**
```python
from src.core.agent.base import BaseAgent, AgentConfig, AgentContext
import structlog
```

**Optional (Integration):**
- Market data API (Trading)
- Order routing API (Trading)
- Policy engine (All agents)
- Memory substrate (All agents)
- LLM client (All agents)
- CRM system (Client Service)
- Compliance services (Compliance)

---

## Testing Notes

All agents are syntax-validated:
```bash
python3 -m py_compile trading_agent.py  # ✓ OK
python3 -m py_compile risk_management_agent.py  # ✓ OK
# ... etc
```

To test integration:
1. Initialize with mock memory, policy, and LLM
2. Call agent.run() with sample input
3. Verify AgentResult structure
4. Check logs for any warnings/errors

---

## Tips & Best Practices

1. **Always provide context**: AgentContext with trace_id
2. **Handle graceful degradation**: All agents have fallback logic
3. **Monitor confidence scores**: Lower confidence = less certain decision
4. **Check logs regularly**: Structured logs help debugging
5. **Use appropriate timeouts**: Longer for complex operations
6. **Provide complete input**: Missing fields may cause validation errors
7. **Initialize dependencies**: Memory, policy_engine, llm are required
8. **Track trace_ids**: Essential for multi-agent coordination

---

