"""
Trade Lifecycle Workflow for Capital Markets.

Orchestrates the complete trade lifecycle from order reception through post-trade
verification and learning. Implements the PERCEIVE→RETRIEVE→REASON→EXECUTE→VERIFY→LEARN
loop with conditional routing based on order size and compliance status.

Workflow Flow:
    Order Reception → Pre-Trade Compliance Check → Risk Assessment
    → [if order > $5M] Trading Council Deliberation → Order Execution
    → Post-Trade Verification → Learn

Uses LangGraph for orchestration with TypedDict state management.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class TradeLifecycleState(TypedDict):
    """State management for trade lifecycle workflow."""

    # Order details
    order_id: str
    client_id: str
    ticker: str
    side: str  # "buy" or "sell"
    quantity: float
    limit_price: Optional[float]
    order_type: str  # "market", "limit", "stop", "stop_limit"
    order_value: float  # quantity * current_price
    urgency: str  # "immediate", "normal", "patient"

    # PERCEIVE phase
    perception_complete: bool
    order_validated: bool
    validation_errors: List[str]

    # RETRIEVE phase
    retrieval_complete: bool
    market_data: Dict[str, Any]
    historical_patterns: Dict[str, Any]
    compliance_rules: Dict[str, Any]

    # PRE-TRADE COMPLIANCE
    compliance_check_complete: bool
    compliance_passed: bool
    compliance_issues: List[str]
    compliance_status: str  # "approved", "rejected", "escalated"

    # RISK ASSESSMENT
    risk_assessment_complete: bool
    var_95: float
    var_99: float
    counterparty_risk_score: float
    position_limit_breach: bool
    concentration_risk: float
    risk_passed: bool
    risk_issues: List[str]

    # TRADING COUNCIL (if needed)
    council_required: bool
    council_convened: bool
    council_decision: Optional[str]
    council_deliberation: Dict[str, Any]
    council_members_votes: Dict[str, str]

    # EXECUTION
    execution_complete: bool
    execution_status: str  # "pending", "filled", "partially_filled", "rejected"
    execution_venue: str
    execution_price: float
    execution_quantity: float
    execution_time: Optional[str]
    execution_latency_ms: float
    slippage: float

    # POST-TRADE VERIFICATION
    verification_complete: bool
    verification_passed: bool
    verification_issues: List[str]
    settlement_status: str
    audit_trail: List[Dict[str, Any]]

    # LEARNING
    learning_complete: bool
    lessons_learned: List[str]
    pattern_updates: Dict[str, Any]

    # Workflow metadata
    workflow_status: str  # "pending", "executing", "completed", "failed"
    errors: List[str]
    created_at: str
    updated_at: str


async def perceive_order(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    PERCEIVE: Parse and validate incoming order request.

    Validates order structure, ticker symbol, side, quantity, and price parameters.
    Sets foundation for subsequent workflow steps.
    """
    logger.info(f"[PERCEIVE] Processing order {state['order_id']} for {state['ticker']}")

    state["updated_at"] = datetime.utcnow().isoformat()
    errors = []

    try:
        # Validate ticker
        if not state["ticker"] or len(state["ticker"]) > 10:
            errors.append(f"Invalid ticker: {state['ticker']}")

        # Validate side
        if state["side"].lower() not in ["buy", "sell"]:
            errors.append(f"Invalid side: {state['side']}")

        # Validate quantity
        if state["quantity"] <= 0:
            errors.append(f"Invalid quantity: {state['quantity']}")

        # Validate order type
        valid_types = ["market", "limit", "stop", "stop_limit"]
        if state["order_type"].lower() not in valid_types:
            errors.append(f"Invalid order type: {state['order_type']}")

        # Validate limit price for limit orders
        if state["order_type"].lower() == "limit" and state["limit_price"] is None:
            errors.append("Limit price required for limit orders")

        if state["limit_price"] is not None and state["limit_price"] <= 0:
            errors.append(f"Invalid limit price: {state['limit_price']}")

        state["order_validated"] = len(errors) == 0
        state["validation_errors"] = errors
        state["perception_complete"] = True

        logger.info(
            f"[PERCEIVE] Order {state['order_id']} validation: "
            f"{'PASSED' if state['order_validated'] else 'FAILED'}"
        )

    except Exception as e:
        logger.error(f"[PERCEIVE] Error validating order: {str(e)}")
        state["validation_errors"].append(str(e))
        state["order_validated"] = False
        state["perception_complete"] = True

    return state


async def retrieve_market_context(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    RETRIEVE: Fetch market data, compliance rules, and historical patterns.

    Gathers all contextual information needed for risk assessment and execution.
    This would typically call market data APIs, compliance databases, etc.
    """
    logger.info(f"[RETRIEVE] Fetching context for {state['ticker']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Simulate market data retrieval
        # In production, this would call real market data APIs
        state["market_data"] = {
            "ticker": state["ticker"],
            "current_price": 150.25,  # Mock price
            "bid": 150.23,
            "ask": 150.27,
            "volume": 1_000_000,
            "market_cap": 2_000_000_000,
            "sector": "Technology",
            "liquidity_score": 0.95,
        }

        # Calculate order value
        state["order_value"] = state["quantity"] * state["market_data"]["current_price"]

        # Simulate historical patterns retrieval
        state["historical_patterns"] = {
            "avg_execution_time_ms": 150,
            "avg_slippage_bps": 1.5,
            "success_rate": 0.99,
            "typical_volume_fill_time": 300,
        }

        # Simulate compliance rules retrieval
        state["compliance_rules"] = {
            "max_single_order_size": 50_000_000,
            "max_daily_volume_pct": 0.25,
            "requires_review_above": 5_000_000,
            "requires_council_above": 5_000_000,
        }

        state["retrieval_complete"] = True

        logger.info(
            f"[RETRIEVE] Context retrieved. Order value: ${state['order_value']:,.2f}"
        )

    except Exception as e:
        logger.error(f"[RETRIEVE] Error fetching context: {str(e)}")
        state["errors"].append(str(e))
        state["retrieval_complete"] = True

    return state


async def pre_trade_compliance_check(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    PRE-TRADE COMPLIANCE: Check regulatory and policy compliance.

    Verifies client KYC status, sanctions screening, order compliance rules,
    trading limits, and other pre-execution compliance requirements.
    """
    logger.info(f"[COMPLIANCE] Pre-trade compliance check for {state['order_id']}")

    state["updated_at"] = datetime.utcnow().isoformat()
    issues = []

    try:
        # Check client KYC status
        kyc_approved = True  # Mock - would check compliance database
        if not kyc_approved:
            issues.append("Client KYC status not approved")

        # Check sanctions screening
        sanctions_cleared = True  # Mock
        if not sanctions_cleared:
            issues.append("Client failed sanctions screening")

        # Check trading limits
        daily_volume_pct = (state["order_value"] / 100_000_000) * 100  # Mock calculation
        max_daily = state["compliance_rules"].get("max_daily_volume_pct", 0.25) * 100

        if daily_volume_pct > max_daily:
            issues.append(
                f"Order would exceed daily volume limit: {daily_volume_pct:.1f}% "
                f"of max {max_daily:.1f}%"
            )

        # Check order size limits
        max_order = state["compliance_rules"].get("max_single_order_size", 50_000_000)
        if state["order_value"] > max_order:
            issues.append(
                f"Order size ${state['order_value']:,.0f} exceeds "
                f"maximum ${max_order:,.0f}"
            )

        state["compliance_passed"] = len(issues) == 0
        state["compliance_issues"] = issues

        if state["compliance_passed"]:
            state["compliance_status"] = "approved"
        else:
            state["compliance_status"] = "escalated"

        state["compliance_check_complete"] = True

        logger.info(
            f"[COMPLIANCE] Compliance check: "
            f"{'PASSED' if state['compliance_passed'] else 'ISSUES FOUND'}"
        )

    except Exception as e:
        logger.error(f"[COMPLIANCE] Error during compliance check: {str(e)}")
        state["errors"].append(str(e))
        state["compliance_check_complete"] = True

    return state


async def assess_risk(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    REASON/RISK ASSESSMENT: Calculate portfolio risk metrics.

    Computes VaR, Greeks, concentration risk, and counterparty risk.
    Checks risk limits and potential portfolio impact.
    """
    logger.info(f"[RISK] Assessing risk for order {state['order_id']}")

    state["updated_at"] = datetime.utcnow().isoformat()
    issues = []

    try:
        # Mock VaR calculation
        portfolio_value = 100_000_000
        state["var_95"] = portfolio_value * 0.015  # 1.5% at 95% confidence
        state["var_99"] = portfolio_value * 0.025  # 2.5% at 99% confidence

        # Mock counterparty risk assessment
        state["counterparty_risk_score"] = 0.15  # 15% risk score (0-1 scale)

        # Check concentration risk
        if state["order_value"] > portfolio_value * 0.20:
            issues.append(
                f"Order creates excessive concentration: "
                f"{(state['order_value']/portfolio_value)*100:.1f}% of portfolio"
            )
            state["concentration_risk"] = state["order_value"] / portfolio_value
        else:
            state["concentration_risk"] = state["order_value"] / portfolio_value

        # Check position limits
        max_position = portfolio_value * 0.15
        if state["order_value"] > max_position:
            issues.append(
                f"Proposed position ${state['order_value']:,.0f} "
                f"exceeds limit ${max_position:,.0f}"
            )
            state["position_limit_breach"] = True

        state["risk_passed"] = len(issues) == 0
        state["risk_issues"] = issues
        state["risk_assessment_complete"] = True

        logger.info(
            f"[RISK] Risk assessment complete. "
            f"VaR 95%: ${state['var_95']:,.0f}, "
            f"Risk Passed: {state['risk_passed']}"
        )

    except Exception as e:
        logger.error(f"[RISK] Error assessing risk: {str(e)}")
        state["errors"].append(str(e))
        state["risk_assessment_complete"] = True

    return state


async def check_council_requirement(state: TradeLifecycleState) -> str:
    """
    Conditional routing: Determine if Trading Council deliberation is needed.

    Trading Council is convened for orders exceeding $5M or with significant
    risk or compliance concerns.
    """
    if state["order_value"] > 5_000_000:
        state["council_required"] = True
        logger.info(f"[ROUTE] Order ${state['order_value']:,.0f} > $5M - Council required")
        return "council_deliberation"

    if not state["compliance_passed"] or not state["risk_passed"]:
        state["council_required"] = True
        logger.info(
            f"[ROUTE] Compliance/Risk issues found - Council deliberation required"
        )
        return "council_deliberation"

    logger.info(f"[ROUTE] Order approved - proceeding to execution")
    return "execute_order"


async def convene_trading_council(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    REASON: Convene Trading Council for high-value or high-risk orders.

    Trading Council includes Head Trader, Equity Analyst, Execution Specialist,
    and Risk Officer. Uses weighted voting to reach consensus on order approval.
    """
    logger.info(f"[COUNCIL] Convening Trading Council for order {state['order_id']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Mock council member votes
        # In production, would integrate with actual council agents
        council_members = {
            "head_trader": {"vote": "approve", "confidence": 0.92},
            "equity_analyst": {"vote": "approve", "confidence": 0.88},
            "execution_specialist": {"vote": "approve", "confidence": 0.90},
            "risk_officer": {"vote": "caution" if not state["risk_passed"] else "approve",
                           "confidence": 0.85},
        }

        # Calculate weighted consensus
        approve_weight = 0.0
        total_weight = 0.0

        for member, vote_info in council_members.items():
            weight = vote_info["confidence"]
            total_weight += weight

            if vote_info["vote"] == "approve":
                approve_weight += weight

        consensus_score = approve_weight / total_weight if total_weight > 0 else 0

        state["council_members_votes"] = {
            k: v["vote"] for k, v in council_members.items()
        }
        state["council_deliberation"] = {
            "consensus_score": consensus_score,
            "threshold": 0.70,
            "members_votes": council_members,
            "deliberation_time_ms": 250,
        }

        if consensus_score >= 0.70:
            state["council_decision"] = "approve"
        else:
            state["council_decision"] = "reject"

        state["council_convened"] = True

        logger.info(
            f"[COUNCIL] Council decision: {state['council_decision']} "
            f"(consensus: {consensus_score:.2%})"
        )

    except Exception as e:
        logger.error(f"[COUNCIL] Error during council deliberation: {str(e)}")
        state["errors"].append(str(e))
        state["council_decision"] = "reject"
        state["council_convened"] = True

    return state


async def execute_order(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    EXECUTE: Submit order to market.

    Routes order to appropriate venue, executes using optimal strategy
    (market, VWAP, TWAP, or algo execution), and monitors fill.
    """
    logger.info(f"[EXECUTE] Executing order {state['order_id']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Check if order was approved by council or passed compliance
        if state["council_required"] and state["council_decision"] != "approve":
            state["execution_status"] = "rejected"
            state["execution_complete"] = True
            logger.warning(f"[EXECUTE] Order rejected by council")
            return state

        if not state["compliance_passed"]:
            state["execution_status"] = "rejected"
            state["execution_complete"] = True
            logger.warning(f"[EXECUTE] Order rejected due to compliance issues")
            return state

        # Simulate order execution
        import time
        start_time = time.time()

        # Mock execution
        state["execution_venue"] = "NYSE"
        state["execution_price"] = state["market_data"]["current_price"] * 1.0005  # Slight slippage
        state["execution_quantity"] = state["quantity"] * 0.99  # 99% fill
        state["execution_time"] = datetime.utcnow().isoformat()
        state["execution_latency_ms"] = (time.time() - start_time) * 1000
        state["slippage"] = abs(
            state["execution_price"] - state["market_data"]["current_price"]
        ) / state["market_data"]["current_price"] * 10000  # in basis points

        if state["execution_quantity"] == state["quantity"]:
            state["execution_status"] = "filled"
        else:
            state["execution_status"] = "partially_filled"

        state["execution_complete"] = True

        logger.info(
            f"[EXECUTE] Order executed: {state['execution_quantity']} @ "
            f"${state['execution_price']:.2f}, slippage: {state['slippage']:.1f} bps"
        )

    except Exception as e:
        logger.error(f"[EXECUTE] Error executing order: {str(e)}")
        state["errors"].append(str(e))
        state["execution_status"] = "rejected"
        state["execution_complete"] = True

    return state


async def verify_post_trade(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    VERIFY: Post-trade verification and settlement confirmation.

    Verifies execution details, confirms settlement, checks for
    trade breaks, and compares expected vs. actual execution.
    """
    logger.info(f"[VERIFY] Verifying trade {state['order_id']}")

    state["updated_at"] = datetime.utcnow().isoformat()
    issues = []

    try:
        # Verify execution status
        if state["execution_status"] == "rejected":
            state["verification_passed"] = False
            issues.append("Order was rejected during execution")

        # Verify slippage is acceptable
        max_slippage = 5.0  # max 5 basis points
        if state["slippage"] > max_slippage:
            issues.append(
                f"Slippage {state['slippage']:.1f} bps exceeds limit {max_slippage} bps"
            )

        # Verify fill quantity
        min_fill_pct = 0.95  # minimum 95% fill
        fill_pct = state["execution_quantity"] / state["quantity"]
        if fill_pct < min_fill_pct:
            issues.append(
                f"Fill quantity {fill_pct:.1%} below minimum {min_fill_pct:.1%}"
            )

        # Verify execution time
        if state["execution_latency_ms"] > 1000:  # Over 1 second
            issues.append(
                f"Execution latency {state['execution_latency_ms']:.0f}ms exceeded"
            )

        state["verification_passed"] = len(issues) == 0
        state["verification_issues"] = issues
        state["settlement_status"] = "settled" if state["verification_passed"] else "pending_review"
        state["verification_complete"] = True

        # Build audit trail
        state["audit_trail"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "phase": "verification",
            "status": "passed" if state["verification_passed"] else "issues_found",
            "details": issues,
        })

        logger.info(
            f"[VERIFY] Verification complete: "
            f"{'PASSED' if state['verification_passed'] else 'ISSUES FOUND'}"
        )

    except Exception as e:
        logger.error(f"[VERIFY] Error verifying trade: {str(e)}")
        state["errors"].append(str(e))
        state["verification_complete"] = True

    return state


async def learn_from_execution(state: TradeLifecycleState) -> TradeLifecycleState:
    """
    LEARN: Extract lessons from trade execution for future improvements.

    Updates execution patterns, identifies improvements in slippage,
    timing, venue selection, and risk assessment accuracy.
    """
    logger.info(f"[LEARN] Learning from execution of {state['order_id']}")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        lessons = []
        pattern_updates = {}

        # Analyze execution efficiency
        if state["execution_status"] in ["filled", "partially_filled"]:
            actual_slippage = state["slippage"]
            expected_slippage = state["historical_patterns"].get("avg_slippage_bps", 1.5)

            if actual_slippage < expected_slippage:
                lessons.append(
                    f"Better than expected slippage: "
                    f"{actual_slippage:.1f} vs {expected_slippage:.1f} bps"
                )
                pattern_updates["improved_slippage"] = actual_slippage
            elif actual_slippage > expected_slippage * 1.5:
                lessons.append(
                    f"Higher than expected slippage: {actual_slippage:.1f} bps - "
                    f"consider alternative venues"
                )

            # Analyze execution time
            actual_time = state["execution_latency_ms"]
            expected_time = state["historical_patterns"].get("avg_execution_time_ms", 150)

            if actual_time > expected_time * 1.5:
                lessons.append(
                    f"Slower execution: {actual_time:.0f}ms vs "
                    f"expected {expected_time:.0f}ms"
                )
                pattern_updates["slower_execution"] = actual_time

        # Analyze compliance and risk assessment accuracy
        if state["compliance_passed"] and not state["risk_issues"]:
            lessons.append("Compliance and risk assessments were accurate")
            pattern_updates["compliance_accuracy"] = 1.0

        state["lessons_learned"] = lessons
        state["pattern_updates"] = pattern_updates
        state["learning_complete"] = True

        # Final audit trail entry
        state["audit_trail"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "phase": "learning",
            "lessons": lessons,
            "updates": pattern_updates,
        })

        logger.info(
            f"[LEARN] Extracted {len(lessons)} lessons from execution. "
            f"Updating {len(pattern_updates)} patterns"
        )

    except Exception as e:
        logger.error(f"[LEARN] Error during learning phase: {str(e)}")
        state["errors"].append(str(e))
        state["learning_complete"] = True

    return state


def create_trade_lifecycle_workflow():
    """
    Create and compile the Trade Lifecycle workflow.

    Returns:
        Compiled StateGraph workflow ready for execution.

    Workflow Phases:
        1. PERCEIVE: Validate order structure and parameters
        2. RETRIEVE: Fetch market data, patterns, compliance rules
        3. COMPLIANCE: Pre-trade compliance check (KYC, sanctions, limits)
        4. RISK: Risk assessment (VaR, concentration, counterparty)
        5. COUNCIL: [Conditional] Trading Council deliberation for large orders
        6. EXECUTE: Submit order to market
        7. VERIFY: Post-trade verification and settlement
        8. LEARN: Extract lessons for future improvements
    """
    workflow = StateGraph(TradeLifecycleState)

    # Add nodes
    workflow.add_node("perceive", perceive_order)
    workflow.add_node("retrieve", retrieve_market_context)
    workflow.add_node("compliance", pre_trade_compliance_check)
    workflow.add_node("risk", assess_risk)
    workflow.add_node("council_deliberation", convene_trading_council)
    workflow.add_node("execute_order", execute_order)
    workflow.add_node("verify", verify_post_trade)
    workflow.add_node("learn", learn_from_execution)

    # Add edges - linear flow
    workflow.add_edge("perceive", "retrieve")
    workflow.add_edge("retrieve", "compliance")
    workflow.add_edge("compliance", "risk")

    # Conditional edge: check if council is needed
    workflow.add_conditional_edges(
        "risk",
        check_council_requirement,
        {
            "council_deliberation": "council_deliberation",
            "execute_order": "execute_order",
        }
    )

    # After council, execute order
    workflow.add_edge("council_deliberation", "execute_order")

    # Post-execution verification and learning
    workflow.add_edge("execute_order", "verify")
    workflow.add_edge("verify", "learn")
    workflow.add_edge("learn", END)

    # Set entry point
    workflow.set_entry_point("perceive")

    return workflow.compile()


if __name__ == "__main__":
    """Demo execution of trade lifecycle workflow."""
    import asyncio
    from datetime import datetime

    async def demo():
        # Create workflow
        trade_workflow = create_trade_lifecycle_workflow()

        # Create sample large order requiring council deliberation
        initial_state: TradeLifecycleState = {
            "order_id": "ORD-001-LARGE",
            "client_id": "CLIENT-001",
            "ticker": "AAPL",
            "side": "buy",
            "quantity": 50000,  # 50k shares
            "limit_price": None,
            "order_type": "market",
            "order_value": 0.0,  # Will be calculated
            "urgency": "normal",
            "perception_complete": False,
            "order_validated": False,
            "validation_errors": [],
            "retrieval_complete": False,
            "market_data": {},
            "historical_patterns": {},
            "compliance_rules": {},
            "compliance_check_complete": False,
            "compliance_passed": False,
            "compliance_issues": [],
            "compliance_status": "pending",
            "risk_assessment_complete": False,
            "var_95": 0.0,
            "var_99": 0.0,
            "counterparty_risk_score": 0.0,
            "position_limit_breach": False,
            "concentration_risk": 0.0,
            "risk_passed": False,
            "risk_issues": [],
            "council_required": False,
            "council_convened": False,
            "council_decision": None,
            "council_deliberation": {},
            "council_members_votes": {},
            "execution_complete": False,
            "execution_status": "pending",
            "execution_venue": "",
            "execution_price": 0.0,
            "execution_quantity": 0.0,
            "execution_time": None,
            "execution_latency_ms": 0.0,
            "slippage": 0.0,
            "verification_complete": False,
            "verification_passed": False,
            "verification_issues": [],
            "settlement_status": "pending",
            "audit_trail": [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "phase": "initialization",
                    "status": "started",
                    "order_id": "ORD-001-LARGE",
                }
            ],
            "learning_complete": False,
            "lessons_learned": [],
            "pattern_updates": {},
            "workflow_status": "pending",
            "errors": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        print("\n" + "="*80)
        print("TRADE LIFECYCLE WORKFLOW DEMO")
        print("="*80)
        print(f"Order ID: {initial_state['order_id']}")
        print(f"Ticker: {initial_state['ticker']}")
        print(f"Side: {initial_state['side']}")
        print(f"Quantity: {initial_state['quantity']:,}")
        print("="*80 + "\n")

        # Execute workflow
        final_state = await trade_workflow.ainvoke(initial_state)

        print("\n" + "="*80)
        print("WORKFLOW RESULTS")
        print("="*80)
        print(f"Order Status: {final_state['execution_status']}")
        print(f"Compliance: {'PASSED' if final_state['compliance_passed'] else 'FAILED'}")
        print(f"Risk Assessment: {'PASSED' if final_state['risk_passed'] else 'FAILED'}")
        print(f"Council Required: {final_state['council_required']}")
        if final_state['council_required']:
            print(f"Council Decision: {final_state['council_decision']}")
        print(f"Execution Price: ${final_state['execution_price']:.2f}")
        print(f"Execution Quantity: {final_state['execution_quantity']:,.0f}")
        print(f"Slippage: {final_state['slippage']:.2f} bps")
        print(f"Verification: {'PASSED' if final_state['verification_passed'] else 'FAILED'}")
        print(f"Lessons Learned: {len(final_state['lessons_learned'])}")
        print("="*80 + "\n")

        if final_state['errors']:
            print("ERRORS:")
            for error in final_state['errors']:
                print(f"  - {error}")

        if final_state['audit_trail']:
            print("\nAUDIT TRAIL:")
            for entry in final_state['audit_trail']:
                print(f"  [{entry['timestamp']}] {entry['phase']}: {entry.get('status', 'info')}")

    asyncio.run(demo())
