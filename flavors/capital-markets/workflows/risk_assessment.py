"""
Risk Assessment Workflow for Capital Markets.

Orchestrates comprehensive portfolio risk analysis with real-time VaR, Greeks,
and concentration monitoring. Implements conditional escalation to Risk Committee
for threshold breaches.

Workflow Flow:
    Portfolio Snapshot → Calculate VaR → Calculate Greeks → Check Concentration
    → [if any breach] Convene Risk Committee → Hedge/Reject → Generate Report

Uses LangGraph for orchestration with parallel risk calculations where possible.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class RiskAssessmentState(TypedDict):
    """State management for risk assessment workflow."""

    # Portfolio information
    portfolio_id: str
    portfolio_name: str
    portfolio_value: float
    positions: List[Dict[str, Any]]
    cash_balance: float

    # Market conditions
    market_date: str
    market_snapshot_time: str
    market_data: Dict[str, Any]

    # VaR Calculation
    var_calculation_complete: bool
    var_95: float  # 95% confidence level
    var_99: float  # 99% confidence level
    cvar_95: float  # Conditional VaR (expected shortfall)
    historical_var_data: List[float]

    # Greeks Calculation
    greeks_calculation_complete: bool
    greeks_by_position: Dict[str, Dict[str, float]]
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_vega: float
    portfolio_theta: float
    portfolio_rho: float

    # Concentration Risk
    concentration_check_complete: bool
    concentration_metrics: Dict[str, float]
    sector_concentration: Dict[str, float]
    single_position_concentrations: List[Dict[str, Any]]
    concentration_breaches: List[str]

    # Risk Limits
    var_95_limit: float
    var_99_limit: float
    concentration_limit: float
    sector_limit: float
    delta_limit: float
    vega_limit: float

    # Breach Detection
    breaches_detected: bool
    breach_list: List[Dict[str, Any]]
    breach_severity: str  # "none", "warning", "critical"

    # Risk Committee (if needed)
    committee_required: bool
    committee_convened: bool
    committee_decision: Optional[str]
    committee_recommendations: List[str]
    hedging_required: bool

    # Hedging Actions
    hedging_actions: List[Dict[str, Any]]
    hedge_execution_status: str
    hedging_cost: float

    # Recommendations
    action_items: List[Dict[str, Any]]
    priority_actions: List[str]
    monitoring_frequency: str  # "intraday", "daily", "weekly"

    # Report Generation
    report_generation_complete: bool
    report_summary: Dict[str, Any]
    risk_score: float  # 0-1 scale
    trend: str  # "improving", "stable", "deteriorating"

    # Workflow metadata
    workflow_status: str
    errors: List[str]
    calculation_duration_ms: float
    created_at: str
    updated_at: str


async def fetch_portfolio_snapshot(state: RiskAssessmentState) -> RiskAssessmentState:
    """
    Fetch current portfolio composition and market data snapshot.

    Retrieves all positions, current prices, and market conditions
    at a point in time for consistent risk calculations.
    """
    logger.info(f"[SNAPSHOT] Fetching portfolio snapshot for {state['portfolio_id']}")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()
    state["market_snapshot_time"] = datetime.utcnow().isoformat()

    try:
        # Mock portfolio positions
        # In production, would fetch from portfolio management system
        state["positions"] = [
            {
                "ticker": "AAPL",
                "quantity": 10000,
                "current_price": 150.25,
                "market_value": 1_502_500,
                "sector": "Technology",
                "position_type": "equity",
                "purchase_price": 145.00,
                "unrealized_pnl": 52_500,
            },
            {
                "ticker": "MSFT",
                "quantity": 8000,
                "current_price": 380.50,
                "market_value": 3_044_000,
                "sector": "Technology",
                "position_type": "equity",
                "purchase_price": 370.00,
                "unrealized_pnl": 84_000,
            },
            {
                "ticker": "JPM",
                "quantity": 5000,
                "current_price": 190.75,
                "market_value": 953_750,
                "sector": "Financials",
                "position_type": "equity",
                "purchase_price": 185.00,
                "unrealized_pnl": 28_750,
            },
            {
                "ticker": "AAPL_CALL_200",
                "quantity": 50,
                "current_price": 15.50,
                "market_value": 775,
                "sector": "Technology",
                "position_type": "option",
                "purchase_price": 12.00,
                "unrealized_pnl": 175,
            },
        ]

        # Calculate portfolio value
        state["portfolio_value"] = sum(pos["market_value"] for pos in state["positions"])
        state["cash_balance"] = 2_000_000

        # Mock market data
        state["market_data"] = {
            "vix_index": 18.5,
            "risk_free_rate": 0.045,
            "market_volatility": 0.165,
            "yield_curve": "normal",
            "credit_spreads": "tight",
            "market_sentiment": "positive",
        }

        logger.info(
            f"[SNAPSHOT] Portfolio snapshot complete: "
            f"${state['portfolio_value']:,.0f} in {len(state['positions'])} positions"
        )

    except Exception as e:
        logger.error(f"[SNAPSHOT] Error fetching portfolio: {str(e)}")
        state["errors"].append(str(e))

    state["calculation_duration_ms"] += (time.time() - start_time) * 1000
    return state


async def calculate_var(state: RiskAssessmentState) -> RiskAssessmentState:
    """
    Calculate Value at Risk (VaR) using historical simulation.

    Computes VaR at 95% and 99% confidence levels, plus Conditional VaR
    (expected shortfall) for tail risk assessment.
    """
    logger.info(f"[VAR] Calculating VaR for {state['portfolio_id']}")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Mock historical return data (252 trading days)
        import random
        random.seed(42)  # For reproducibility
        state["historical_var_data"] = [
            random.normalvariate(-0.0001, 0.015) for _ in range(252)
        ]

        # Sort returns for percentile calculation
        sorted_returns = sorted(state["historical_var_data"])

        # Calculate portfolio value at risk
        portfolio_daily_vol = (
            state["portfolio_value"] * state["market_data"]["market_volatility"] / 16  # ~16 trading days per month
        )

        # VaR at different confidence levels
        # Using percentile approach
        idx_95 = int(len(sorted_returns) * 0.05)  # 5th percentile (95% confidence)
        idx_99 = int(len(sorted_returns) * 0.01)  # 1st percentile (99% confidence)

        worst_case_95 = sorted_returns[idx_95]
        worst_case_99 = sorted_returns[idx_99]

        state["var_95"] = abs(worst_case_95) * state["portfolio_value"]
        state["var_99"] = abs(worst_case_99) * state["portfolio_value"]

        # Calculate CVaR (expected shortfall)
        # Average of all returns worse than VaR
        tail_returns_95 = sorted_returns[:idx_95]
        state["cvar_95"] = (
            abs(sum(tail_returns_95) / len(tail_returns_95))
            * state["portfolio_value"]
            if tail_returns_95
            else state["var_95"]
        )

        state["var_calculation_complete"] = True

        logger.info(
            f"[VAR] VaR Calculation complete. "
            f"VaR 95%: ${state['var_95']:,.0f}, "
            f"VaR 99%: ${state['var_99']:,.0f}, "
            f"CVaR 95%: ${state['cvar_95']:,.0f}"
        )

    except Exception as e:
        logger.error(f"[VAR] Error calculating VaR: {str(e)}")
        state["errors"].append(str(e))
        state["var_calculation_complete"] = True

    state["calculation_duration_ms"] += (time.time() - start_time) * 1000
    return state


async def calculate_greeks(state: RiskAssessmentState) -> RiskAssessmentState:
    """
    Calculate Options Greeks for derivatives positions.

    Computes delta, gamma, vega, theta, and rho for all options
    and derivatives in the portfolio.
    """
    logger.info(f"[GREEKS] Calculating Greeks for derivatives")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Mock Greeks calculation for derivatives
        state["greeks_by_position"] = {}
        portfolio_delta = 0.0
        portfolio_gamma = 0.0
        portfolio_vega = 0.0
        portfolio_theta = 0.0
        portfolio_rho = 0.0

        for position in state["positions"]:
            if position["position_type"] == "option":
                # Mock Greeks (in production, use Black-Scholes)
                ticker = position["ticker"]
                quantity = position["quantity"]

                greeks = {
                    "delta": 0.65 * quantity,  # 65% delta per contract
                    "gamma": 0.03 * quantity,  # 3% gamma per contract
                    "vega": 0.25 * quantity,  # 0.25 vega per contract
                    "theta": -0.05 * quantity,  # -0.05 theta per contract (time decay)
                    "rho": 0.12 * quantity,  # 0.12 rho per contract
                }

                state["greeks_by_position"][ticker] = greeks

                portfolio_delta += greeks["delta"]
                portfolio_gamma += greeks["gamma"]
                portfolio_vega += greeks["vega"]
                portfolio_theta += greeks["theta"]
                portfolio_rho += greeks["rho"]

            else:
                # Equity positions have delta ~1.0, no other Greeks
                state["greeks_by_position"][position["ticker"]] = {
                    "delta": position["quantity"],
                    "gamma": 0.0,
                    "vega": 0.0,
                    "theta": 0.0,
                    "rho": 0.0,
                }
                portfolio_delta += position["quantity"]

        state["portfolio_delta"] = portfolio_delta
        state["portfolio_gamma"] = portfolio_gamma
        state["portfolio_vega"] = portfolio_vega
        state["portfolio_theta"] = portfolio_theta
        state["portfolio_rho"] = portfolio_rho

        state["greeks_calculation_complete"] = True

        logger.info(
            f"[GREEKS] Greeks calculation complete. "
            f"Portfolio Delta: {state['portfolio_delta']:.0f}, "
            f"Gamma: {state['portfolio_gamma']:.2f}, "
            f"Vega: {state['portfolio_vega']:.2f}"
        )

    except Exception as e:
        logger.error(f"[GREEKS] Error calculating Greeks: {str(e)}")
        state["errors"].append(str(e))
        state["greeks_calculation_complete"] = True

    state["calculation_duration_ms"] += (time.time() - start_time) * 1000
    return state


async def check_concentration_risk(state: RiskAssessmentState) -> RiskAssessmentState:
    """
    Analyze concentration risk across positions, sectors, and correlations.

    Identifies excessive concentration in single positions or sectors
    that could amplify losses in stress scenarios.
    """
    logger.info(f"[CONCENTRATION] Analyzing concentration risk")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()
    breaches = []

    try:
        # Calculate single position concentrations
        state["single_position_concentrations"] = []

        for position in state["positions"]:
            pct_of_portfolio = position["market_value"] / state["portfolio_value"] * 100

            state["single_position_concentrations"].append({
                "ticker": position["ticker"],
                "market_value": position["market_value"],
                "pct_of_portfolio": pct_of_portfolio,
                "limit": 15.0,
                "breach": pct_of_portfolio > 15.0,
            })

            # Check concentration limits
            if pct_of_portfolio > state["concentration_limit"]:
                breaches.append({
                    "type": "position_concentration",
                    "ticker": position["ticker"],
                    "current": pct_of_portfolio,
                    "limit": state["concentration_limit"],
                    "severity": "warning" if pct_of_portfolio < 20 else "critical",
                })

        # Calculate sector concentrations
        state["sector_concentration"] = {}

        for position in state["positions"]:
            sector = position["sector"]
            if sector not in state["sector_concentration"]:
                state["sector_concentration"][sector] = 0.0

            state["sector_concentration"][sector] += (
                position["market_value"] / state["portfolio_value"] * 100
            )

        # Check sector concentration limits
        for sector, concentration in state["sector_concentration"].items():
            if concentration > state["sector_limit"]:
                breaches.append({
                    "type": "sector_concentration",
                    "sector": sector,
                    "current": concentration,
                    "limit": state["sector_limit"],
                    "severity": "warning" if concentration < 40 else "critical",
                })

        # Calculate Herfindahl index (concentration measure)
        herfindahl = sum(
            (pos["market_value"] / state["portfolio_value"]) ** 2
            for pos in state["positions"]
        )

        state["concentration_metrics"] = {
            "herfindahl_index": herfindahl,
            "max_single_position_pct": max(
                (p["market_value"] / state["portfolio_value"] * 100)
                for p in state["positions"]
            ),
            "largest_sector_pct": max(state["sector_concentration"].values()),
        }

        # Check Greeks limits (if derivatives present)
        if abs(state["portfolio_delta"]) > state["delta_limit"]:
            breaches.append({
                "type": "delta_limit",
                "current": abs(state["portfolio_delta"]),
                "limit": state["delta_limit"],
                "severity": "warning",
            })

        if abs(state["portfolio_vega"]) > state["vega_limit"]:
            breaches.append({
                "type": "vega_limit",
                "current": abs(state["portfolio_vega"]),
                "limit": state["vega_limit"],
                "severity": "warning",
            })

        state["concentration_breaches"] = [b for b in breaches
                                          if b["type"] in ["sector_concentration",
                                                         "position_concentration"]]
        state["breach_list"] = breaches
        state["breaches_detected"] = len(breaches) > 0

        if breaches:
            critical = [b for b in breaches if b.get("severity") == "critical"]
            state["breach_severity"] = "critical" if critical else "warning"
        else:
            state["breach_severity"] = "none"

        state["concentration_check_complete"] = True

        logger.info(
            f"[CONCENTRATION] Concentration check complete. "
            f"Breaches: {len(breaches)}, Severity: {state['breach_severity']}"
        )

    except Exception as e:
        logger.error(f"[CONCENTRATION] Error checking concentration: {str(e)}")
        state["errors"].append(str(e))
        state["concentration_check_complete"] = True

    state["calculation_duration_ms"] += (time.time() - start_time) * 1000
    return state


async def check_risk_committee_requirement(state: RiskAssessmentState) -> str:
    """
    Conditional routing: Determine if Risk Committee review is needed.

    Risk Committee is convened for:
    - VaR breaches at either confidence level
    - Concentration breaches
    - Greeks limit violations
    - Any critical severity breach
    """
    critical_breaches = [b for b in state["breach_list"]
                         if b.get("severity") == "critical"]

    if (state["var_95"] > state["var_95_limit"] or
        state["var_99"] > state["var_99_limit"] or
        state["breaches_detected"] or
        critical_breaches):

        state["committee_required"] = True
        logger.info("[ROUTE] Risk threshold breach - Risk Committee required")
        return "risk_committee"
    else:
        logger.info("[ROUTE] All risk metrics within limits - generating report")
        return "generate_report"


async def convene_risk_committee(state: RiskAssessmentState) -> RiskAssessmentState:
    """
    Convene Risk Committee to deliberate on breach mitigation.

    Risk Committee reviews breaches and recommends hedging or position reductions.
    """
    logger.info(f"[COMMITTEE] Convening Risk Committee")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Mock Risk Committee deliberation
        # In production, would invoke actual committee agents/councils

        recommendations = []
        hedge_required = False

        # Analyze each breach
        for breach in state["breach_list"]:
            if breach["type"] == "position_concentration":
                breach_pct = breach["current"] - breach["limit"]
                recommendations.append(
                    f"Reduce {breach['ticker']} by at least "
                    f"{breach_pct:.1f}% to meet concentration limits"
                )

            elif breach["type"] == "sector_concentration":
                breach_pct = breach["current"] - breach["limit"]
                recommendations.append(
                    f"Reduce {breach['sector']} sector by {breach_pct:.1f}% "
                    f"to meet sector limits"
                )

            elif breach["type"] == "delta_limit":
                recommendations.append(
                    "Adjust delta exposure through offsetting options"
                )
                hedge_required = True

        # VaR breach recommendations
        if state["var_99"] > state["var_99_limit"]:
            breach_pct = (
                (state["var_99"] / state["var_99_limit"]) - 1
            ) * 100
            recommendations.append(
                f"Reduce portfolio risk: VaR breach of {breach_pct:.1f}%. "
                f"Consider portfolio rebalancing or hedging."
            )
            hedge_required = True

        state["committee_recommendations"] = recommendations
        state["hedging_required"] = hedge_required
        state["committee_decision"] = "approve_with_conditions" if recommendations else "approve"
        state["committee_convened"] = True

        logger.info(
            f"[COMMITTEE] Committee decision: {state['committee_decision']}. "
            f"Recommendations: {len(recommendations)}"
        )

    except Exception as e:
        logger.error(f"[COMMITTEE] Error during committee deliberation: {str(e)}")
        state["errors"].append(str(e))
        state["committee_convened"] = True

    return state


async def execute_hedging_actions(state: RiskAssessmentState) -> RiskAssessmentState:
    """
    Execute hedging recommendations from Risk Committee.

    Can include selling overconcentrated positions, buying protective puts,
    or adjusting derivatives exposure.
    """
    logger.info(f"[HEDGE] Executing hedging actions")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        if not state["hedging_required"]:
            state["hedge_execution_status"] = "not_required"
            logger.info("[HEDGE] Hedging not required")
            return state

        state["hedging_actions"] = []
        total_hedge_cost = 0.0

        # Mock hedging actions
        for recommendation in state["committee_recommendations"]:
            if "Reduce" in recommendation and "concentration" in recommendation:
                # Mock selling action
                action = {
                    "type": "reduce_position",
                    "recommendation": recommendation,
                    "status": "executed",
                    "cost": 0.0,  # Selling generates proceeds
                }
                state["hedging_actions"].append(action)

            elif "delta" in recommendation.lower():
                # Mock option hedge
                action = {
                    "type": "delta_hedge",
                    "recommendation": recommendation,
                    "status": "executed",
                    "cost": 15000,  # Cost of options
                }
                total_hedge_cost += action["cost"]
                state["hedging_actions"].append(action)

            elif "protective" in recommendation.lower() or "rebalancing" in recommendation:
                # Mock portfolio rebalancing
                action = {
                    "type": "portfolio_rebalance",
                    "recommendation": recommendation,
                    "status": "executed",
                    "cost": 5000,  # Rebalancing transaction costs
                }
                total_hedge_cost += action["cost"]
                state["hedging_actions"].append(action)

        state["hedging_cost"] = total_hedge_cost
        state["hedge_execution_status"] = "completed"

        logger.info(
            f"[HEDGE] Hedging complete. "
            f"Actions: {len(state['hedging_actions'])}, "
            f"Cost: ${total_hedge_cost:,.0f}"
        )

    except Exception as e:
        logger.error(f"[HEDGE] Error executing hedges: {str(e)}")
        state["errors"].append(str(e))
        state["hedge_execution_status"] = "failed"

    return state


async def generate_risk_report(state: RiskAssessmentState) -> RiskAssessmentState:
    """
    Generate comprehensive risk assessment report.

    Creates executive summary with key metrics, breaches, recommendations,
    and trend analysis for stakeholder review.
    """
    logger.info(f"[REPORT] Generating risk assessment report")

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        # Calculate overall risk score (0-1, where 1 is highest risk)
        risk_score = 0.0

        # Factor 1: VaR utilization
        if state["var_99_limit"] > 0:
            var_util = min(state["var_99"] / state["var_99_limit"], 1.0)
            risk_score += var_util * 0.4

        # Factor 2: Concentration risk
        herfindahl = state["concentration_metrics"]["herfindahl_index"]
        risk_score += herfindahl * 0.3  # Higher herfindahl = higher concentration risk

        # Factor 3: Greeks exposure
        delta_util = min(
            abs(state["portfolio_delta"]) / state["delta_limit"], 1.0
        ) if state["delta_limit"] > 0 else 0
        vega_util = min(
            abs(state["portfolio_vega"]) / state["vega_limit"], 1.0
        ) if state["vega_limit"] > 0 else 0
        risk_score += (delta_util * 0.15 + vega_util * 0.15)

        state["risk_score"] = risk_score

        # Determine trend
        # In production, would compare to historical trends
        critical_count = len([b for b in state["breach_list"]
                            if b.get("severity") == "critical"])

        if critical_count > 2:
            state["trend"] = "deteriorating"
            state["monitoring_frequency"] = "intraday"
        elif state["breaches_detected"]:
            state["trend"] = "stable"
            state["monitoring_frequency"] = "daily"
        else:
            state["trend"] = "improving"
            state["monitoring_frequency"] = "weekly"

        # Build action items
        state["action_items"] = []
        state["priority_actions"] = []

        for action in state["hedging_actions"]:
            state["action_items"].append({
                "action": action["recommendation"],
                "type": action["type"],
                "status": "pending" if action["status"] != "executed" else "completed",
            })
            if action["status"] != "executed":
                state["priority_actions"].append(action["recommendation"])

        # Build report summary
        state["report_summary"] = {
            "portfolio_id": state["portfolio_id"],
            "portfolio_value": state["portfolio_value"],
            "report_date": state["market_snapshot_time"],
            "risk_score": state["risk_score"],
            "trend": state["trend"],
            "var_95": state["var_95"],
            "var_99": state["var_99"],
            "cvar_95": state["cvar_95"],
            "breaches_detected": state["breaches_detected"],
            "breach_count": len(state["breach_list"]),
            "critical_breaches": len([b for b in state["breach_list"]
                                     if b.get("severity") == "critical"]),
            "concentration_metrics": state["concentration_metrics"],
            "portfolio_greeks": {
                "delta": state["portfolio_delta"],
                "gamma": state["portfolio_gamma"],
                "vega": state["portfolio_vega"],
                "theta": state["portfolio_theta"],
                "rho": state["portfolio_rho"],
            },
            "hedging_actions": len(state["hedging_actions"]),
            "hedging_cost": state["hedging_cost"],
            "monitoring_frequency": state["monitoring_frequency"],
            "action_items": len(state["action_items"]),
        }

        state["report_generation_complete"] = True

        logger.info(
            f"[REPORT] Risk report generated. "
            f"Risk Score: {state['risk_score']:.2f}, "
            f"Trend: {state['trend']}, "
            f"Monitoring: {state['monitoring_frequency']}"
        )

    except Exception as e:
        logger.error(f"[REPORT] Error generating report: {str(e)}")
        state["errors"].append(str(e))
        state["report_generation_complete"] = True

    return state


def create_risk_assessment_workflow():
    """
    Create and compile the Risk Assessment workflow.

    Returns:
        Compiled StateGraph workflow ready for execution.

    Workflow Phases:
        1. PORTFOLIO SNAPSHOT: Fetch current positions and market conditions
        2. VaR CALCULATION: Compute Value at Risk at multiple confidence levels
        3. GREEKS CALCULATION: Calculate derivatives Greeks for derivatives exposure
        4. CONCENTRATION CHECK: Analyze position and sector concentration
        5. RISK COMMITTEE: [Conditional] Deliberate on threshold breaches
        6. HEDGING: Execute hedging recommendations
        7. REPORT GENERATION: Create comprehensive risk report

    The workflow calculates VaR and Greeks in parallel, then checks for
    concentration breaches. If any risk metric exceeds limits, the Risk
    Committee is convened to recommend mitigation actions.
    """
    workflow = StateGraph(RiskAssessmentState)

    # Add nodes
    workflow.add_node("portfolio_snapshot", fetch_portfolio_snapshot)
    workflow.add_node("var_calculation", calculate_var)
    workflow.add_node("greeks_calculation", calculate_greeks)
    workflow.add_node("concentration_check", check_concentration_risk)
    workflow.add_node("risk_committee", convene_risk_committee)
    workflow.add_node("execute_hedging", execute_hedging_actions)
    workflow.add_node("generate_report", generate_risk_report)

    # Add edges
    workflow.add_edge("portfolio_snapshot", "var_calculation")
    workflow.add_edge("portfolio_snapshot", "greeks_calculation")
    workflow.add_edge("portfolio_snapshot", "concentration_check")

    # Wait for VaR and Greeks to complete
    workflow.add_edge("var_calculation", "concentration_check")
    workflow.add_edge("greeks_calculation", "concentration_check")

    # Conditional edge based on breach detection
    workflow.add_conditional_edges(
        "concentration_check",
        check_risk_committee_requirement,
        {
            "risk_committee": "risk_committee",
            "generate_report": "generate_report",
        }
    )

    # Risk Committee leads to hedging and report
    workflow.add_edge("risk_committee", "execute_hedging")
    workflow.add_edge("execute_hedging", "generate_report")

    # Report generation is final step
    workflow.add_edge("generate_report", END)

    # Set entry point
    workflow.set_entry_point("portfolio_snapshot")

    return workflow.compile()


if __name__ == "__main__":
    """Demo execution of risk assessment workflow."""
    import asyncio
    from datetime import datetime

    async def demo():
        # Create workflow
        risk_workflow = create_risk_assessment_workflow()

        # Initialize state with default values
        initial_state: RiskAssessmentState = {
            "portfolio_id": "PORT-001",
            "portfolio_name": "Growth Portfolio",
            "portfolio_value": 0.0,
            "positions": [],
            "cash_balance": 0.0,
            "market_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "market_snapshot_time": "",
            "market_data": {},
            "var_calculation_complete": False,
            "var_95": 0.0,
            "var_99": 0.0,
            "cvar_95": 0.0,
            "historical_var_data": [],
            "greeks_calculation_complete": False,
            "greeks_by_position": {},
            "portfolio_delta": 0.0,
            "portfolio_gamma": 0.0,
            "portfolio_vega": 0.0,
            "portfolio_theta": 0.0,
            "portfolio_rho": 0.0,
            "concentration_check_complete": False,
            "concentration_metrics": {},
            "sector_concentration": {},
            "single_position_concentrations": [],
            "concentration_breaches": [],
            "var_95_limit": 1_500_000,
            "var_99_limit": 2_500_000,
            "concentration_limit": 15.0,
            "sector_limit": 35.0,
            "delta_limit": 500.0,
            "vega_limit": 100.0,
            "breaches_detected": False,
            "breach_list": [],
            "breach_severity": "none",
            "committee_required": False,
            "committee_convened": False,
            "committee_decision": None,
            "committee_recommendations": [],
            "hedging_required": False,
            "hedging_actions": [],
            "hedge_execution_status": "pending",
            "hedging_cost": 0.0,
            "action_items": [],
            "priority_actions": [],
            "monitoring_frequency": "daily",
            "report_generation_complete": False,
            "report_summary": {},
            "risk_score": 0.0,
            "trend": "stable",
            "workflow_status": "pending",
            "errors": [],
            "calculation_duration_ms": 0.0,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        print("\n" + "="*80)
        print("RISK ASSESSMENT WORKFLOW DEMO")
        print("="*80)
        print(f"Portfolio ID: {initial_state['portfolio_id']}")
        print(f"Portfolio Name: {initial_state['portfolio_name']}")
        print("="*80 + "\n")

        # Execute workflow
        final_state = await risk_workflow.ainvoke(initial_state)

        print("\n" + "="*80)
        print("RISK ASSESSMENT RESULTS")
        print("="*80)
        print(f"Portfolio Value: ${final_state['portfolio_value']:,.0f}")
        print(f"Risk Score: {final_state['risk_score']:.2f}/1.0")
        print(f"Trend: {final_state['trend']}")
        print(f"\nVaR Metrics:")
        print(f"  VaR 95%: ${final_state['var_95']:,.0f} "
              f"(Limit: ${final_state['var_95_limit']:,.0f})")
        print(f"  VaR 99%: ${final_state['var_99']:,.0f} "
              f"(Limit: ${final_state['var_99_limit']:,.0f})")
        print(f"  CVaR 95%: ${final_state['cvar_95']:,.0f}")
        print(f"\nGreeks Exposure:")
        print(f"  Delta: {final_state['portfolio_delta']:.0f}")
        print(f"  Gamma: {final_state['portfolio_gamma']:.2f}")
        print(f"  Vega: {final_state['portfolio_vega']:.2f}")
        print(f"  Theta: {final_state['portfolio_theta']:.2f}")
        print(f"\nConcentration:")
        print(f"  Herfindahl Index: {final_state['concentration_metrics'].get('herfindahl_index', 0):.3f}")
        print(f"  Max Single Position: {final_state['concentration_metrics'].get('max_single_position_pct', 0):.1f}%")
        print(f"\nBreaches Detected: {final_state['breaches_detected']}")
        if final_state['breach_list']:
            print(f"  Total Breaches: {len(final_state['breach_list'])}")
            print(f"  Severity: {final_state['breach_severity']}")
        print(f"\nCommittee Required: {final_state['committee_required']}")
        if final_state['committee_convened']:
            print(f"  Committee Decision: {final_state['committee_decision']}")
            print(f"  Recommendations: {len(final_state['committee_recommendations'])}")
        print(f"\nHedging Actions: {len(final_state['hedging_actions'])}")
        if final_state['hedging_actions']:
            print(f"  Hedging Cost: ${final_state['hedging_cost']:,.0f}")
        print(f"\nMonitoring Frequency: {final_state['monitoring_frequency']}")
        print(f"Calculation Duration: {final_state['calculation_duration_ms']:.0f}ms")
        print("="*80 + "\n")

        if final_state['errors']:
            print("ERRORS:")
            for error in final_state['errors']:
                print(f"  - {error}")

    asyncio.run(demo())
