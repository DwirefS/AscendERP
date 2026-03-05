# Capital Markets Agents Architecture

## Overview

The Capital Markets flavor provides six production-quality agents for the ANTS/Ascend EOS platform, implementing specialized workflows for equity trading, derivatives, risk management, portfolio optimization, client services, and regulatory compliance.

## Agent Summary

### 1. Trading Agent (trading_agent.py)
**Lines:** 480 | **Complexity:** High

Executes equity and derivatives orders with smart order routing and execution strategy optimization.

**Key Methods:**
- `perceive()`: Parses order request (ticker, side, quantity, limit_price, order_type, urgency, client_id)
- `retrieve()`: Gets execution patterns and market intelligence from memory
- `reason()`: Uses LLM to determine venue, split strategy (VWAP/TWAP), and timing
- `execute()`: Fetches market data, calculates slippage, checks compliance, routes order
- `verify()`: Compares fill price vs limit, validates slippage tolerance
- `learn()`: Stores successful execution patterns when success_rate > 0.85

**Tools:** fetch_market_data, check_trading_limits, calculate_slippage, route_order, verify_execution

**Config:**
- max_iterations: 15
- timeout_seconds: 60
- model_name: "gpt-4-turbo"

**Private Helpers:**
- `_fetch_market_data()`: Market data simulator
- `_calculate_slippage()`: Impact model for order size
- `_check_pre_trade_compliance()`: Policy engine integration
- `_route_order()`: Execution via simulator/API
- `_generate_execution_report()`: Detailed fill report
- `_select_venue_rule_based()`: Fallback venue selection
- `_select_strategy_rule_based()`: Fallback strategy selection

---

### 2. Risk Management Agent (risk_management_agent.py)
**Lines:** 534 | **Complexity:** Very High

Comprehensive portfolio risk monitoring with VaR, Greeks, stress testing, and breach detection.

**Key Methods:**
- `perceive()`: Parses risk assessment request (portfolio_id, assessment_type: continuous/on_demand/stress_test)
- `retrieve()`: Gets past assessments, VaR history, breach patterns
- `reason()`: Determines which risk calculations needed; evaluates severity
- `execute()`: Calculates VaR (95%/99%), Greeks, concentration (HHI), stress tests
- `verify()`: Confirms all calculations complete, validates results
- `learn()`: Stores risk assessments and trend data

**Tools:** calculate_var, calculate_greeks, check_position_limits, stress_test, alert_breach

**Config:**
- max_iterations: 20
- timeout_seconds: 120
- model_name: "gpt-4-turbo"

**Private Helpers:**
- `_calculate_portfolio_var()`: Historical simulation for VaR
- `_calculate_portfolio_greeks()`: Black-Scholes Greeks for options
- `_check_concentration()`: HHI and sector exposure analysis
- `_run_stress_tests()`: Multiple scenario analysis (10%, 20%, vol spike, rate shock)
- `_identify_breaches()`: Detect limit violations and flag severity
- `_should_convene_risk_committee()`: Escalation logic for critical breaches

**RiskMetrics Dataclass:**
- var_95, var_99, expected_shortfall
- portfolio_delta, gamma, vega
- concentration_hhi
- max_breach

---

### 3. Portfolio Manager Agent (portfolio_manager_agent.py)
**Lines:** 504 | **Complexity:** High

Monitors drift, optimizes allocations, and manages rebalancing operations.

**Key Methods:**
- `perceive()`: Parses portfolio request (portfolio_id, action: monitor/rebalance/optimize/report, drift_threshold)
- `retrieve()`: Gets target allocation, historical performance, rebalancing history
- `reason()`: Calculates drift; determines if rebalancing needed (5% default threshold)
- `execute()`: Generates trade list; requests approval if > $1M; executes via TradingAgent
- `verify()`: Confirms new allocation matches target within tolerance
- `learn()`: Stores rebalancing outcomes and optimization parameters

**Tools:** get_portfolio, calculate_drift, optimize_allocation, rebalance, track_performance

**Config:**
- max_iterations: 15
- timeout_seconds: 120
- model_name: "gpt-4-turbo"

**Private Helpers:**
- `_get_portfolio()`: Fetch portfolio data
- `_calculate_drift()`: Compare current vs target allocation
- `_generate_rebalancing_trades()`: Create specific trade list
- `_execute_rebalancing()`: Delegate to TradingAgent
- `_optimize_allocation()`: Modern Portfolio Theory optimization
- `_generate_performance_report()`: YTD return, volatility, drift metrics

---

### 4. Client Service Agent (client_service_agent.py)
**Lines:** 476 | **Complexity:** Medium-High

Handles client inquiries, portfolio summaries, transaction history, and relationship management.

**Key Methods:**
- `perceive()`: Parses client request (client_id, query_type: portfolio_summary/transaction_history/general_inquiry/callback)
- `retrieve()`: Gets full interaction history and service guidelines from episodic memory
- `reason()`: LLM generates contextual response with full client history; fallback routes to human
- `execute()`: Generates response, updates CRM, schedules callbacks, creates tickets as needed
- `verify()`: Response quality check
- `learn()`: Stores interactions in episodic memory

**Tools:** lookup_client, get_portfolio_summary, get_transaction_history, schedule_callback, create_ticket

**Config:**
- max_iterations: 10
- timeout_seconds: 60
- model_name: "gpt-4-turbo"

**Private Helpers:**
- `_lookup_client()`: CRM integration
- `_get_portfolio_summary()`: Account balances, allocation, holdings
- `_get_transaction_history()`: Recent trades (configurable period)
- `_schedule_callback()`: Calendar system integration
- `_create_ticket()`: Support ticket system
- `_update_crm()`: Interaction logging
- `_format_portfolio_response()`: Readable portfolio summary
- `_format_transaction_response()`: Transaction history formatting

---

### 5. Compliance Agent (compliance_agent.py)
**Lines:** 419 | **Complexity:** High

Regulatory compliance including KYC, AML screening, sanctions checks, and pre-trade validation.

**Key Methods:**
- `perceive()`: Parses compliance request (request_type: kyc/aml/pre_trade/reporting, entity_id, entity_data)
- `retrieve()`: Gets past decisions, regulatory updates, entity history
- `reason()`: Applies compliance rules; determines required checks
- `execute()`: Runs screenings (identity, AML, sanctions, position limits); generates compliance report
- `verify()`: Confirms all checks completed; no missing data
- `learn()`: Stores compliance decisions for audit trail

**Tools:** check_kyc, screen_aml, check_sanctions, validate_trade, generate_regulatory_report

**Config:**
- max_iterations: 10
- timeout_seconds: 90
- model_name: "gpt-4-turbo"

**Private Helpers:**
- `_perform_kyc_check()`: Identity verification, PEP screening, document review
- `_perform_aml_screening()`: Transaction pattern analysis, watchlist screening
- `_perform_pre_trade_validation()`: Position limits, restricted list checks
- `_generate_regulatory_report()`: Audit trail and compliance summary
- `_get_default_checks()`: Maps request type to required checks

**ComplianceStatus Enum:**
- APPROVED, FLAGGED, REJECTED, PENDING

---

### 6. Derivatives Agent (derivatives_agent.py)
**Lines:** 623 | **Complexity:** Very High

Derivatives pricing, Greeks calculation, volatility analysis, hedging, and strategy backtesting.

**Key Methods:**
- `perceive()`: Parses derivatives request (request_type: price/hedge/analyze/backtest, instrument_data)
- `retrieve()`: Gets historical vol data, hedging patterns, pricing models
- `reason()`: Selects appropriate model (Black-Scholes for European, Binomial for American)
- `execute()`: Prices instruments, calculates Greeks, generates hedging recommendations
- `verify()`: Sanity checks (bid-ask bounds, Greeks consistency, put-call parity)
- `learn()`: Stores pricing accuracy for model calibration

**Tools:** price_option, calculate_greeks, analyze_vol_surface, recommend_hedge, backtest_strategy

**Config:**
- max_iterations: 15
- timeout_seconds: 120
- model_name: "gpt-4-turbo"

**Private Helpers:**
- `_price_option()`: Calls Black-Scholes or Binomial depending on model
- `_analyze_hedge()`: Calculates delta/gamma/vega hedging requirements
- `_analyze_vol_surface()`: Skew and term structure analysis
- `_backtest_strategy()`: Historical performance evaluation
- `_calculate_greeks()`: Delta, gamma, vega, theta, rho
- `_black_scholes_call/put()`: Analytical pricing formulas
- `_binomial_price()`: Binomial tree method (50 steps)
- `_norm_cdf/pdf()`: Normal distribution functions
- `_is_american_option()`: Style detection

**OptionGreeks & OptionPrice Dataclasses:**
- Delta, gamma, vega, theta, rho
- Fair value, bid, ask, implied volatility

---

## Common Patterns

### All Agents Follow the PRREEL Loop:
1. **Perceive**: Parse and validate input
2. **Retrieve**: Get relevant context from memory
3. **Reason**: Use LLM (with rule-based fallback)
4. **Execute**: Perform core operations
5. **Verify**: Validate results
6. **Learn**: Store outcomes in memory

### Logging
- All agents use `structlog` for structured logging
- Consistent logging at key decision points
- trace_id included for request tracing

### Memory Integration
- Procedural memory: Patterns and strategies
- Episodic memory: Historical decisions
- Semantic memory: Rules and guidelines

### Policy Integration
- Pre-execution policy checks via policy_engine
- Graceful fallback if policy engine unavailable

### Error Handling
- Try/except with logging
- Graceful degradation to fallback logic
- Confidence scoring reflects uncertainty

### Telemetry
- OpenTelemetry span creation (when enabled)
- Latency tracking
- Success/failure metrics

---

## Tool Dependencies

| Agent | Primary Tools |
|-------|---------------|
| Trading | market_data, slippage, compliance, routing, verification |
| Risk | VaR, Greeks, position_limits, stress_test, alert |
| Portfolio | portfolio_data, drift, optimization, rebalancing, performance |
| Client | lookup, portfolio_summary, transactions, callback, ticket |
| Compliance | kyc, aml, sanctions, pre_trade, reporting |
| Derivatives | pricing, Greeks, vol_surface, hedging, backtest |

---

## Configuration Examples

```python
# Trading Agent
config = AgentConfig(
    name="Trading Agent",
    tools=["fetch_market_data", "check_trading_limits", "calculate_slippage", "route_order", "verify_execution"],
    max_iterations=15,
    timeout_seconds=60,
    model_name="gpt-4-turbo"
)

# Risk Management Agent
config = AgentConfig(
    name="Risk Management Agent",
    tools=["calculate_var", "calculate_greeks", "check_position_limits", "stress_test", "alert_breach"],
    max_iterations=20,
    timeout_seconds=120,
    model_name="gpt-4-turbo"
)
```

---

## Integration Points

1. **Market Data**: Mock simulator; integrate with Bloomberg/Reuters
2. **Order Routing**: Mock simulator; integrate with broker APIs
3. **Policy Engine**: Via policy_engine interface
4. **Memory Substrate**: Via memory interface
5. **LLM**: Via llm interface (initialized at startup)
6. **CRM System**: Placeholder integration in ClientServiceAgent
7. **Compliance Systems**: KYC/AML/Sanctions vendor integration points

---

## Performance Characteristics

| Agent | Avg Latency | Max Iterations | Confidence |
|-------|-------------|----------------|-----------|
| Trading | ~500ms | 15 | 0.75-0.95 |
| Risk | ~2000ms | 20 | 0.80-0.95 |
| Portfolio | ~1500ms | 15 | 0.75-0.95 |
| Client | ~200ms | 10 | 0.70-0.95 |
| Compliance | ~800ms | 10 | 0.75-0.95 |
| Derivatives | ~1200ms | 15 | 0.80-0.95 |

---

## Future Enhancements

1. Real market data integration
2. Advanced ML models for execution prediction
3. Reinforcement learning for portfolio optimization
4. Deep market microstructure simulation
5. Enhanced volatility forecasting
6. Machine learning compliance scoring
7. Real-time monitoring dashboards
8. Advanced hedging strategies (dynamic, multi-leg)

