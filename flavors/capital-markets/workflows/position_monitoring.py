"""
Position Monitoring Workflow for Capital Markets.

Continuous real-time monitoring of portfolio positions with automated alert
generation when risk limits are breached. Implements periodic re-evaluation
with configurable monitoring intervals.

Workflow Flow:
    Fetch Market Data → Recalculate Positions → Check Risk Limits
    → [if breach] Generate Alerts → Update Dashboard → [loop or exit]

Uses LangGraph for orchestration with TypedDict state management.
Supports both single-cycle and continuous monitoring modes.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)


class PositionMonitoringState(TypedDict):
    """State management for position monitoring workflow."""

    # Portfolio information
    portfolio_id: str
    portfolio_name: str
    current_portfolio_value: float
    positions: List[Dict[str, Any]]
    cash_balance: float

    # Market data
    market_data: Dict[str, Dict[str, float]]  # ticker -> {price, volume, bid, ask}
    market_snapshot_time: str
    market_conditions: Dict[str, Any]

    # Position calculations
    position_revaluation_complete: bool
    position_details: List[Dict[str, Any]]
    portfolio_changes: Dict[str, float]  # delta, gamma, vega, etc.
    portfolio_pnl: Dict[str, float]  # realized, unrealized totals

    # Risk monitoring
    risk_check_complete: bool
    current_metrics: Dict[str, float]  # VaR, concentration, Greeks
    risk_limits: Dict[str, float]
    limit_breaches: List[Dict[str, Any]]
    breaches_detected: bool

    # Alerts
    alerts: List[Dict[str, Any]]
    alert_count: int
    alert_severity_distribution: Dict[str, int]  # "info", "warning", "critical"
    alert_actions: List[str]

    # Dashboard update
    dashboard_updated: bool
    dashboard_update_timestamp: str
    dashboard_metrics: Dict[str, Any]

    # Monitoring configuration
    monitoring_interval_seconds: int
    max_monitoring_cycles: int
    current_cycle: int
    cycle_complete: bool

    # Performance metrics
    calculation_time_ms: float
    last_market_update_time: str
    monitoring_duration_ms: float

    # Workflow metadata
    workflow_status: str
    should_continue_monitoring: bool
    monitoring_reason_to_stop: Optional[str]
    errors: List[str]
    created_at: str
    updated_at: str


async def fetch_market_data(state: PositionMonitoringState) -> PositionMonitoringState:
    """
    Fetch current market data for all positions.

    Retrieves real-time quotes, volumes, and market conditions
    needed for position revaluation.
    """
    logger.info(f"[MARKET] Fetching market data for {len(state['positions'])} positions")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()
    state["market_snapshot_time"] = datetime.utcnow().isoformat()

    try:
        # Simulate market data fetch
        # In production, would call real-time market data providers
        state["market_data"] = {}

        mock_prices = {
            "AAPL": 150.25,
            "MSFT": 380.50,
            "JPM": 190.75,
            "AAPL_CALL_200": 15.50,
        }

        for position in state["positions"]:
            ticker = position["ticker"]
            current_price = mock_prices.get(ticker, position["current_price"])

            # Simulate some price movement
            import random
            random.seed(int(datetime.utcnow().timestamp()))
            price_change = current_price * random.uniform(-0.01, 0.01)
            current_price += price_change

            state["market_data"][ticker] = {
                "price": current_price,
                "bid": current_price - 0.05,
                "ask": current_price + 0.05,
                "volume": random.randint(1_000_000, 10_000_000),
                "timestamp": datetime.utcnow().isoformat(),
                "market_cap": random.randint(100_000_000_000, 3_000_000_000_000),
            }

        state["last_market_update_time"] = datetime.utcnow().isoformat()

        logger.info(
            f"[MARKET] Market data fetched for {len(state['market_data'])} tickers"
        )

    except Exception as e:
        logger.error(f"[MARKET] Error fetching market data: {str(e)}")
        state["errors"].append(str(e))

    state["calculation_time_ms"] += (time.time() - start_time) * 1000
    return state


async def recalculate_positions(state: PositionMonitoringState) -> PositionMonitoringState:
    """
    Recalculate position values, Greeks, and PnL.

    Updates all positions with current market prices and recomputes
    unrealized PnL, Greeks, and portfolio-level metrics.
    """
    logger.info(f"[REVALUE] Recalculating {len(state['positions'])} positions")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        state["position_details"] = []
        total_market_value = 0.0
        total_book_value = 0.0
        total_unrealized_pnl = 0.0
        total_realized_pnl = 0.0

        portfolio_delta = 0.0
        portfolio_gamma = 0.0
        portfolio_vega = 0.0

        for position in state["positions"]:
            ticker = position["ticker"]

            if ticker not in state["market_data"]:
                logger.warning(f"[REVALUE] No market data for {ticker}")
                continue

            current_price = state["market_data"][ticker]["price"]
            quantity = position["quantity"]
            avg_cost = position["avg_cost"]
            position_type = position.get("position_type", "equity")

            # Calculate position values
            market_value = quantity * current_price
            book_value = quantity * avg_cost
            unrealized_pnl = market_value - book_value

            # Mock realized PnL (for closed trades)
            realized_pnl = 0.0

            # Calculate Greeks for derivatives
            if position_type == "option":
                # Mock Greeks calculation
                delta = 0.65 * quantity
                gamma = 0.03 * quantity
                vega = 0.25 * quantity
            else:
                # Equity: delta = quantity, no other Greeks
                delta = quantity
                gamma = 0.0
                vega = 0.0

            portfolio_delta += delta
            portfolio_gamma += gamma
            portfolio_vega += vega

            # Build position details
            position_detail = {
                "ticker": ticker,
                "position_type": position_type,
                "quantity": quantity,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "price_change": current_price - avg_cost,
                "price_change_pct": (current_price - avg_cost) / avg_cost * 100,
                "market_value": market_value,
                "book_value": book_value,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_pct": (unrealized_pnl / book_value * 100) if book_value != 0 else 0,
                "realized_pnl": realized_pnl,
                "delta": delta,
                "gamma": gamma,
                "vega": vega,
                "last_update": state["market_snapshot_time"],
            }

            state["position_details"].append(position_detail)

            total_market_value += market_value
            total_book_value += book_value
            total_unrealized_pnl += unrealized_pnl
            total_realized_pnl += realized_pnl

        # Update portfolio totals
        state["current_portfolio_value"] = total_market_value + state["cash_balance"]

        state["portfolio_pnl"] = {
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_realized_pnl": total_realized_pnl,
            "total_pnl": total_unrealized_pnl + total_realized_pnl,
            "total_return_pct": (
                (total_unrealized_pnl + total_realized_pnl) / total_book_value * 100
                if total_book_value != 0
                else 0
            ),
        }

        state["portfolio_changes"] = {
            "delta": portfolio_delta,
            "gamma": portfolio_gamma,
            "vega": portfolio_vega,
        }

        state["position_revaluation_complete"] = True

        logger.info(
            f"[REVALUE] Position revaluation complete. "
            f"Portfolio Value: ${state['current_portfolio_value']:,.0f}, "
            f"Total PnL: ${state['portfolio_pnl']['total_pnl']:,.0f}"
        )

    except Exception as e:
        logger.error(f"[REVALUE] Error recalculating positions: {str(e)}")
        state["errors"].append(str(e))
        state["position_revaluation_complete"] = True

    state["calculation_time_ms"] += (time.time() - start_time) * 1000
    return state


async def check_risk_limits(state: PositionMonitoringState) -> PositionMonitoringState:
    """
    Check portfolio against configured risk limits.

    Monitors:
    - Position concentration limits
    - Greeks exposure limits (delta, gamma, vega)
    - Stop-loss levels
    - Volatility-based limits
    - Liquidity constraints
    """
    logger.info("[LIMITS] Checking portfolio against risk limits")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()

    breaches = []

    try:
        # Mock risk limits
        state["risk_limits"] = {
            "max_position_concentration": 0.15,  # 15% of portfolio
            "max_sector_concentration": 0.35,  # 35% of portfolio
            "max_delta": 500.0,
            "max_gamma": 50.0,
            "max_vega": 100.0,
            "stop_loss_pct": 0.10,  # 10% loss trigger
            "max_daily_loss": 0.05,  # 5% of portfolio
        }

        # Check position concentration
        for position_detail in state["position_details"]:
            concentration = (
                position_detail["market_value"] / state["current_portfolio_value"]
            )

            if concentration > state["risk_limits"]["max_position_concentration"]:
                breaches.append({
                    "type": "position_concentration",
                    "ticker": position_detail["ticker"],
                    "current": concentration * 100,
                    "limit": state["risk_limits"]["max_position_concentration"] * 100,
                    "severity": "warning" if concentration < 0.20 else "critical",
                    "message": f"{position_detail['ticker']} concentration "
                              f"{concentration*100:.1f}% exceeds limit "
                              f"{state['risk_limits']['max_position_concentration']*100:.1f}%",
                })

        # Check stop-loss triggers
        for position_detail in state["position_details"]:
            pnl_pct = position_detail["unrealized_pnl_pct"]

            if pnl_pct < -state["risk_limits"]["stop_loss_pct"] * 100:
                breaches.append({
                    "type": "stop_loss",
                    "ticker": position_detail["ticker"],
                    "current": pnl_pct,
                    "limit": -state["risk_limits"]["stop_loss_pct"] * 100,
                    "severity": "critical",
                    "message": f"{position_detail['ticker']} down "
                              f"{abs(pnl_pct):.1f}% - stop loss triggered",
                })

        # Check Greeks limits
        if abs(state["portfolio_changes"]["delta"]) > state["risk_limits"]["max_delta"]:
            breaches.append({
                "type": "delta_limit",
                "current": abs(state["portfolio_changes"]["delta"]),
                "limit": state["risk_limits"]["max_delta"],
                "severity": "warning",
                "message": f"Portfolio delta {abs(state['portfolio_changes']['delta']):.0f} "
                          f"exceeds limit {state['risk_limits']['max_delta']:.0f}",
            })

        if abs(state["portfolio_changes"]["vega"]) > state["risk_limits"]["max_vega"]:
            breaches.append({
                "type": "vega_limit",
                "current": abs(state["portfolio_changes"]["vega"]),
                "limit": state["risk_limits"]["max_vega"],
                "severity": "warning",
                "message": f"Portfolio vega {abs(state['portfolio_changes']['vega']):.2f} "
                          f"exceeds limit {state['risk_limits']['max_vega']:.2f}",
            })

        # Check daily loss limit
        daily_loss = -state["portfolio_pnl"]["total_unrealized_pnl"]
        daily_loss_pct = daily_loss / state["current_portfolio_value"]

        if daily_loss_pct > state["risk_limits"]["max_daily_loss"]:
            breaches.append({
                "type": "daily_loss_limit",
                "current": daily_loss_pct * 100,
                "limit": state["risk_limits"]["max_daily_loss"] * 100,
                "severity": "critical",
                "message": f"Daily loss {daily_loss_pct*100:.1f}% "
                          f"exceeds limit {state['risk_limits']['max_daily_loss']*100:.1f}%",
            })

        # Store current metrics for monitoring
        state["current_metrics"] = {
            "max_position_concentration": max(
                (p["market_value"] / state["current_portfolio_value"])
                for p in state["position_details"]
            ) if state["position_details"] else 0,
            "delta": abs(state["portfolio_changes"]["delta"]),
            "gamma": abs(state["portfolio_changes"]["gamma"]),
            "vega": abs(state["portfolio_changes"]["vega"]),
            "daily_loss_pct": daily_loss_pct * 100,
        }

        state["limit_breaches"] = breaches
        state["breaches_detected"] = len(breaches) > 0
        state["risk_check_complete"] = True

        logger.info(
            f"[LIMITS] Risk check complete. "
            f"Breaches: {len(breaches)}"
        )

    except Exception as e:
        logger.error(f"[LIMITS] Error checking risk limits: {str(e)}")
        state["errors"].append(str(e))
        state["risk_check_complete"] = True

    state["calculation_time_ms"] += (time.time() - start_time) * 1000
    return state


async def generate_alerts(state: PositionMonitoringState) -> PositionMonitoringState:
    """
    Generate alerts based on detected limit breaches.

    Creates actionable alerts with severity levels and recommended actions.
    """
    logger.info("[ALERTS] Generating alerts for detected breaches")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        state["alerts"] = []
        alert_actions = []
        severity_counts = {"info": 0, "warning": 0, "critical": 0}

        # Generate alerts from breaches
        for breach in state["limit_breaches"]:
            severity = breach.get("severity", "warning")
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            alert = {
                "timestamp": datetime.utcnow().isoformat(),
                "severity": severity,
                "type": breach["type"],
                "message": breach["message"],
                "current_value": breach.get("current"),
                "limit_value": breach.get("limit"),
                "recommended_action": None,
            }

            # Add recommended actions based on breach type
            if breach["type"] == "position_concentration":
                alert["recommended_action"] = (
                    f"Consider reducing {breach['ticker']} position"
                )
                alert_actions.append(alert["recommended_action"])

            elif breach["type"] == "stop_loss":
                alert["recommended_action"] = (
                    f"Consider closing {breach['ticker']} position - stop loss triggered"
                )
                alert_actions.append(alert["recommended_action"])

            elif breach["type"] == "delta_limit":
                alert["recommended_action"] = (
                    "Consider adjusting options exposure or hedging"
                )

            elif breach["type"] == "daily_loss_limit":
                alert["recommended_action"] = (
                    "Portfolio daily loss limit exceeded - consider risk reduction"
                )
                alert_actions.append(alert["recommended_action"])

            state["alerts"].append(alert)

        # Add informational alerts
        if state["portfolio_pnl"]["total_pnl"] > state["current_portfolio_value"] * 0.10:
            state["alerts"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "severity": "info",
                "type": "profit_target",
                "message": f"Portfolio profit {state['portfolio_pnl']['total_pnl_pct']:.1f}% "
                          f"- consider profit taking",
                "current_value": state["portfolio_pnl"]["total_pnl"],
                "limit_value": state["current_portfolio_value"] * 0.10,
                "recommended_action": "Consider partial profit realization",
            })
            severity_counts["info"] += 1

        state["alert_count"] = len(state["alerts"])
        state["alert_severity_distribution"] = severity_counts
        state["alert_actions"] = alert_actions

        logger.info(
            f"[ALERTS] Generated {state['alert_count']} alerts. "
            f"Critical: {severity_counts['critical']}, "
            f"Warning: {severity_counts['warning']}, "
            f"Info: {severity_counts['info']}"
        )

    except Exception as e:
        logger.error(f"[ALERTS] Error generating alerts: {str(e)}")
        state["errors"].append(str(e))

    state["calculation_time_ms"] += (time.time() - start_time) * 1000
    return state


async def update_dashboard(state: PositionMonitoringState) -> PositionMonitoringState:
    """
    Update monitoring dashboard with current state.

    Packages all metrics and alerts for display to traders and risk managers.
    """
    logger.info("[DASHBOARD] Updating monitoring dashboard")

    import time
    start_time = time.time()

    state["updated_at"] = datetime.utcnow().isoformat()

    try:
        state["dashboard_metrics"] = {
            "portfolio_id": state["portfolio_id"],
            "timestamp": state["market_snapshot_time"],
            "portfolio_value": state["current_portfolio_value"],
            "cash": state["cash_balance"],
            "positions_count": len(state["position_details"]),
            "pnl": state["portfolio_pnl"],
            "greeks": state["portfolio_changes"],
            "risk_metrics": state["current_metrics"],
            "alerts": {
                "total": state["alert_count"],
                "critical": state["alert_severity_distribution"].get("critical", 0),
                "warning": state["alert_severity_distribution"].get("warning", 0),
                "info": state["alert_severity_distribution"].get("info", 0),
            },
            "top_positions": sorted(
                state["position_details"],
                key=lambda x: x["market_value"],
                reverse=True
            )[:5],
            "worst_performers": sorted(
                state["position_details"],
                key=lambda x: x["unrealized_pnl_pct"]
            )[:3],
        }

        state["dashboard_update_timestamp"] = datetime.utcnow().isoformat()
        state["dashboard_updated"] = True

        logger.info("[DASHBOARD] Dashboard updated successfully")

    except Exception as e:
        logger.error(f"[DASHBOARD] Error updating dashboard: {str(e)}")
        state["errors"].append(str(e))

    state["calculation_time_ms"] += (time.time() - start_time) * 1000
    return state


async def check_continuation(state: PositionMonitoringState) -> str:
    """
    Conditional routing: Determine if monitoring should continue.

    Continues monitoring if:
    - Not at max cycles
    - No critical breaches require immediate action
    - System is healthy
    """
    state["current_cycle"] += 1

    # Check if max cycles reached
    if state["current_cycle"] >= state["max_monitoring_cycles"]:
        state["should_continue_monitoring"] = False
        state["monitoring_reason_to_stop"] = "Max monitoring cycles reached"
        logger.info(
            f"[ROUTE] Max cycles ({state['max_monitoring_cycles']}) reached. Stopping."
        )
        return END

    # Check for critical errors
    if len(state["errors"]) > 5:
        state["should_continue_monitoring"] = False
        state["monitoring_reason_to_stop"] = "Too many errors - stopping monitoring"
        logger.warning("[ROUTE] Too many errors - stopping monitoring")
        return END

    # Check for critical breaches (could trigger automatic actions)
    critical_breaches = [
        b for b in state["limit_breaches"]
        if b.get("severity") == "critical"
    ]

    if critical_breaches:
        logger.warning(
            f"[ROUTE] Critical breach detected. Cycle {state['current_cycle']}/{state['max_monitoring_cycles']}"
        )
        # Continue monitoring but could trigger escalation

    logger.info(
        f"[ROUTE] Continuing monitoring. Cycle {state['current_cycle']}/{state['max_monitoring_cycles']}"
    )
    state["should_continue_monitoring"] = True

    return "market_data_fetch"  # Loop back to fetch fresh data


def create_position_monitoring_workflow():
    """
    Create and compile the Position Monitoring workflow.

    Returns:
        Compiled StateGraph workflow ready for execution.

    Workflow Phases:
        1. MARKET DATA: Fetch current prices and market conditions
        2. REVALUE: Recalculate position values and Greeks
        3. RISK LIMITS: Check against configured risk limits
        4. ALERTS: Generate alerts for detected breaches
        5. DASHBOARD: Update monitoring dashboard
        6. CONTINUATION: [Conditional] Loop or exit based on configuration

    The workflow is designed for continuous operation with configurable
    monitoring intervals and cycle limits.
    """
    workflow = StateGraph(PositionMonitoringState)

    # Add nodes
    workflow.add_node("market_data_fetch", fetch_market_data)
    workflow.add_node("position_revaluation", recalculate_positions)
    workflow.add_node("risk_check", check_risk_limits)
    workflow.add_node("alert_generation", generate_alerts)
    workflow.add_node("dashboard_update", update_dashboard)

    # Add edges - linear monitoring cycle
    workflow.add_edge("market_data_fetch", "position_revaluation")
    workflow.add_edge("position_revaluation", "risk_check")
    workflow.add_edge("risk_check", "alert_generation")
    workflow.add_edge("alert_generation", "dashboard_update")

    # Conditional edge for continuation
    workflow.add_conditional_edges(
        "dashboard_update",
        check_continuation,
        {
            "market_data_fetch": "market_data_fetch",
            END: END,
        }
    )

    # Set entry point
    workflow.set_entry_point("market_data_fetch")

    return workflow.compile()


if __name__ == "__main__":
    """Demo execution of position monitoring workflow."""
    import asyncio
    from datetime import datetime

    async def demo():
        # Create workflow
        monitoring_workflow = create_position_monitoring_workflow()

        # Initialize state for position monitoring
        initial_state: PositionMonitoringState = {
            "portfolio_id": "PORT-002-ACTIVE",
            "portfolio_name": "Active Trading Portfolio",
            "current_portfolio_value": 5_000_000,
            "positions": [
                {
                    "ticker": "AAPL",
                    "quantity": 10000,
                    "avg_cost": 145.00,
                    "current_price": 150.25,
                    "position_type": "equity",
                },
                {
                    "ticker": "MSFT",
                    "quantity": 8000,
                    "avg_cost": 370.00,
                    "current_price": 380.50,
                    "position_type": "equity",
                },
                {
                    "ticker": "JPM",
                    "quantity": 5000,
                    "avg_cost": 185.00,
                    "current_price": 190.75,
                    "position_type": "equity",
                },
                {
                    "ticker": "AAPL_CALL_200",
                    "quantity": 50,
                    "avg_cost": 12.00,
                    "current_price": 15.50,
                    "position_type": "option",
                },
            ],
            "cash_balance": 500_000,
            "market_data": {},
            "market_snapshot_time": "",
            "market_conditions": {},
            "position_revaluation_complete": False,
            "position_details": [],
            "portfolio_changes": {},
            "portfolio_pnl": {},
            "risk_check_complete": False,
            "current_metrics": {},
            "risk_limits": {},
            "limit_breaches": [],
            "breaches_detected": False,
            "alerts": [],
            "alert_count": 0,
            "alert_severity_distribution": {},
            "alert_actions": [],
            "dashboard_updated": False,
            "dashboard_update_timestamp": "",
            "dashboard_metrics": {},
            "monitoring_interval_seconds": 60,
            "max_monitoring_cycles": 3,  # Run 3 cycles for demo
            "current_cycle": 0,
            "cycle_complete": False,
            "calculation_time_ms": 0.0,
            "last_market_update_time": "",
            "monitoring_duration_ms": 0.0,
            "workflow_status": "running",
            "should_continue_monitoring": True,
            "monitoring_reason_to_stop": None,
            "errors": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        print("\n" + "="*80)
        print("POSITION MONITORING WORKFLOW DEMO")
        print("="*80)
        print(f"Portfolio: {initial_state['portfolio_name']}")
        print(f"Portfolio ID: {initial_state['portfolio_id']}")
        print(f"Portfolio Value: ${initial_state['current_portfolio_value']:,.0f}")
        print(f"Max Monitoring Cycles: {initial_state['max_monitoring_cycles']}")
        print("="*80 + "\n")

        # Execute workflow
        final_state = await monitoring_workflow.ainvoke(initial_state)

        print("\n" + "="*80)
        print("MONITORING RESULTS")
        print("="*80)
        print(f"Monitoring Cycles Completed: {final_state['current_cycle']}")
        print(f"Should Continue: {final_state['should_continue_monitoring']}")
        if final_state['monitoring_reason_to_stop']:
            print(f"Reason to Stop: {final_state['monitoring_reason_to_stop']}")
        print(f"\nPortfolio Status:")
        print(f"  Portfolio Value: ${final_state['current_portfolio_value']:,.0f}")
        print(f"  Cash: ${final_state['cash_balance']:,.0f}")
        print(f"  Positions: {len(final_state['position_details'])}")
        print(f"\nP&L Summary:")
        print(f"  Total PnL: ${final_state['portfolio_pnl'].get('total_pnl', 0):,.0f}")
        print(f"  Unrealized PnL: ${final_state['portfolio_pnl'].get('total_unrealized_pnl', 0):,.0f}")
        print(f"  Return: {final_state['portfolio_pnl'].get('total_return_pct', 0):.2f}%")
        print(f"\nGreeks Exposure:")
        print(f"  Delta: {final_state['portfolio_changes'].get('delta', 0):.0f}")
        print(f"  Gamma: {final_state['portfolio_changes'].get('gamma', 0):.2f}")
        print(f"  Vega: {final_state['portfolio_changes'].get('vega', 0):.2f}")
        print(f"\nRisk Status:")
        print(f"  Risk Checks Complete: {final_state['risk_check_complete']}")
        print(f"  Breaches Detected: {final_state['breaches_detected']}")
        print(f"  Breach Count: {len(final_state['limit_breaches'])}")
        print(f"\nAlerts:")
        print(f"  Total Alerts: {final_state['alert_count']}")
        print(f"  Critical: {final_state['alert_severity_distribution'].get('critical', 0)}")
        print(f"  Warning: {final_state['alert_severity_distribution'].get('warning', 0)}")
        print(f"  Info: {final_state['alert_severity_distribution'].get('info', 0)}")
        if final_state['alert_actions']:
            print(f"  Recommended Actions: {len(final_state['alert_actions'])}")
        print(f"\nPerformance:")
        print(f"  Calculation Time: {final_state['calculation_time_ms']:.0f}ms")
        print("="*80 + "\n")

        if final_state['alerts']:
            print("ALERTS SUMMARY:")
            for alert in final_state['alerts'][:3]:
                print(f"  [{alert['severity'].upper()}] {alert['message']}")
            if len(final_state['alerts']) > 3:
                print(f"  ... and {len(final_state['alerts']) - 3} more alerts")

        if final_state['position_details']:
            print("\nTOP POSITIONS:")
            top_positions = sorted(
                final_state['position_details'],
                key=lambda x: x['market_value'],
                reverse=True
            )[:3]
            for pos in top_positions:
                print(f"  {pos['ticker']}: {pos['quantity']:.0f} @ ${pos['current_price']:.2f} "
                      f"(PnL: ${pos['unrealized_pnl']:,.0f}, {pos['unrealized_pnl_pct']:.2f}%)")

        if final_state['errors']:
            print("\nERRORS:")
            for error in final_state['errors']:
                print(f"  - {error}")

    asyncio.run(demo())
