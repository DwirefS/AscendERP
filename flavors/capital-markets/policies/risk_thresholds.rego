# Capital Markets Risk Thresholds Policy
# Governs portfolio risk metrics, Greeks exposure, stress testing requirements,
# and drawdown limits for portfolio management

package capital_markets.risk_thresholds

import future.keywords.if
import future.keywords.in

default decision = "ALLOW"
default reason = "Risk within acceptable thresholds"

# VaR limits (Value at Risk)
var_thresholds := {
    "monitoring_level": 0.015,  # 1.5% of NAV
    "action_level": 0.018,  # 1.8% of NAV (require hedging)
    "escalation_level": 0.020,  # 2.0% of NAV (escalate to committee)
    "circuit_breaker": 0.030  # 3.0% of NAV (trading halt)
}

# Options Greeks exposure limits
greeks_limits := {
    "delta": 0.30,  # Maximum portfolio delta exposure
    "gamma": 0.10,  # Maximum gamma exposure
    "vega": 0.20,  # Maximum vega exposure per vol point
    "theta": 0.02,  # Maximum theta decay per day
    "rho": 0.15  # Maximum interest rate sensitivity
}

# Drawdown limits
drawdown_limits := {
    "max_drawdown_from_hwm": 0.10,  # 10% from high water mark
    "max_monthly_drawdown": 0.05,  # 5% per month
    "max_weekly_drawdown": 0.03  # 3% per week
}

# Stress test thresholds
stress_test_config := {
    "scenarios_required": ["vix_up_20", "rates_up_100bps", "spreads_widen_50bps", "equity_down_10pct"],
    "frequency": "weekly",
    "max_loss_scenario": 0.15  # Max 15% loss in any scenario
}

# Liquidity risk thresholds
liquidity_thresholds := {
    "illiquid_position_pct": 0.10,  # Illiquid positions <= 10% of portfolio
    "large_position_exit_days": 5,  # Can exit large position in 5 days
    "minimum_cash_buffer": 0.05  # 5% cash minimum
}

# Correlation shock assumptions
correlation_scenarios := {
    "normal": 0.3,  # Normal market correlation
    "high_stress": 0.8,  # Correlations converge to 1 in stress
    "black_swan": 0.95  # Everything correlates in extreme stress
}

# Main risk decision logic
decision = "ALLOW" if {
    portfolio_var_within_threshold
    greeks_exposure_acceptable
    drawdown_within_limits
    diversification_adequate
    not exceeds_circuit_breaker
}

decision = "MONITOR" if {
    portfolio_var_in_action_range
}

decision = "REQUIRE_HEDGING" if {
    portfolio_var_exceeds_action_level
    not is_hedged
}

decision = "REQUIRE_RISK_COMMITTEE" if {
    portfolio_var_exceeds_escalation_level
}

decision = "TRADING_HALT" if {
    exceeds_circuit_breaker
}

decision = "REQUIRE_DELEVERAGING" if {
    exceeds_leverage_limit
}

# VaR monitoring and thresholds
calculate_portfolio_var if {
    var_daily := input.portfolio_var
    var_10day := var_daily * sqrt(10)
    var_daily <= var_thresholds.monitoring_level
}

portfolio_var_within_threshold if {
    var_value := input.portfolio_var
    var_value <= var_thresholds.monitoring_level
}

portfolio_var_in_action_range if {
    var_value := input.portfolio_var
    var_value > var_thresholds.monitoring_level
    var_value <= var_thresholds.action_level
}

portfolio_var_exceeds_action_level if {
    var_value := input.portfolio_var
    var_value > var_thresholds.action_level
    var_value <= var_thresholds.escalation_level
}

portfolio_var_exceeds_escalation_level if {
    var_value := input.portfolio_var
    var_value > var_thresholds.escalation_level
    var_value <= var_thresholds.circuit_breaker
}

exceeds_circuit_breaker if {
    var_value := input.portfolio_var
    var_value > var_thresholds.circuit_breaker
}

# Greeks exposure validation
portfolio_delta_acceptable if {
    delta_exposure := input.portfolio_delta
    abs(delta_exposure) <= greeks_limits.delta
}

portfolio_gamma_acceptable if {
    gamma_exposure := input.portfolio_gamma
    abs(gamma_exposure) <= greeks_limits.gamma
}

portfolio_vega_acceptable if {
    vega_exposure := input.portfolio_vega
    abs(vega_exposure) <= greeks_limits.vega
}

portfolio_theta_acceptable if {
    theta_exposure := input.portfolio_theta
    theta_exposure <= greeks_limits.theta
}

portfolio_rho_acceptable if {
    rho_exposure := input.portfolio_rho
    abs(rho_exposure) <= greeks_limits.rho
}

greeks_exposure_acceptable if {
    portfolio_delta_acceptable
    portfolio_gamma_acceptable
    portfolio_vega_acceptable
    portfolio_theta_acceptable
    portfolio_rho_acceptable
}

# Greeks exposure classification
delta_exposure_level = "HIGH" if {
    abs(input.portfolio_delta) > greeks_limits.delta
}

delta_exposure_level = "MODERATE" if {
    abs(input.portfolio_delta) > greeks_limits.delta * 0.5
    abs(input.portfolio_delta) <= greeks_limits.delta
}

delta_exposure_level = "LOW" if {
    abs(input.portfolio_delta) <= greeks_limits.delta * 0.5
}

gamma_exposure_level = "HIGH" if {
    abs(input.portfolio_gamma) > greeks_limits.gamma * 0.7
}

gamma_exposure_level = "MODERATE" if {
    abs(input.portfolio_gamma) > greeks_limits.gamma * 0.3
    abs(input.portfolio_gamma) <= greeks_limits.gamma * 0.7
}

gamma_exposure_level = "LOW" if {
    abs(input.portfolio_gamma) <= greeks_limits.gamma * 0.3
}

vega_exposure_level = "HIGH" if {
    abs(input.portfolio_vega) > greeks_limits.vega * 0.7
}

vega_exposure_level = "MODERATE" if {
    abs(input.portfolio_vega) > greeks_limits.vega * 0.3
}

vega_exposure_level = "LOW" if {
    abs(input.portfolio_vega) <= greeks_limits.vega * 0.3
}

# Drawdown monitoring
drawdown_within_limits if {
    current_dd := input.current_drawdown_from_hwm
    current_dd <= drawdown_limits.max_drawdown_from_hwm

    monthly_dd := input.monthly_drawdown
    monthly_dd <= drawdown_limits.max_monthly_drawdown

    weekly_dd := input.weekly_drawdown
    weekly_dd <= drawdown_limits.max_weekly_drawdown
}

exceeds_drawdown_limit if {
    not drawdown_within_limits
}

# Diversification assessment
diversification_adequate if {
    effective_assets := input.effective_number_of_assets
    effective_assets >= 5

    largest_position := input.largest_position_pct
    largest_position <= 0.25

    hhi := input.herfindahl_index
    hhi <= 0.15
}

diversification_score = "HIGH" if {
    effective_assets := input.effective_number_of_assets
    effective_assets >= 10
}

diversification_score = "MODERATE" if {
    effective_assets := input.effective_number_of_assets
    effective_assets >= 5
    effective_assets < 10
}

diversification_score = "LOW" if {
    effective_assets := input.effective_number_of_assets
    effective_assets < 5
}

# Stress testing requirements
stress_test_required if {
    input.days_since_last_stress_test > 7
}

requires_stress_test_results if {
    input.portfolio_var > var_thresholds.action_level
}

stress_test_max_loss_acceptable if {
    some scenario in stress_test_config.scenarios_required
    max_loss := input.stress_test_scenarios[scenario]
    max_loss <= stress_test_config.max_loss_scenario
}

# Leverage monitoring
calculate_leverage if {
    gross_notional := input.total_long_notional + abs(input.total_short_notional)
    net_notional := abs(input.total_long_notional - input.total_short_notional)

    gross_leverage := gross_notional / input.nav
    net_leverage := net_notional / input.nav

    gross_leverage <= 2.5
    net_leverage <= 1.5
}

exceeds_leverage_limit if {
    not calculate_leverage
}

# Liquidity risk assessment
has_adequate_liquidity if {
    illiquid_pct := input.illiquid_position_pct
    illiquid_pct <= liquidity_thresholds.illiquid_position_pct

    cash_buffer := input.cash_position_pct
    cash_buffer >= liquidity_thresholds.minimum_cash_buffer

    exit_days := input.avg_position_exit_days
    exit_days <= liquidity_thresholds.large_position_exit_days
}

liquidity_risk_level = "HIGH" if {
    input.illiquid_position_pct > liquidity_thresholds.illiquid_position_pct * 1.5
}

liquidity_risk_level = "MEDIUM" if {
    input.illiquid_position_pct > liquidity_thresholds.illiquid_position_pct
}

liquidity_risk_level = "LOW" if {
    input.illiquid_position_pct <= liquidity_thresholds.illiquid_position_pct
}

# Hedging status
is_hedged if {
    hedge_ratio := input.hedge_ratio
    hedge_ratio > 0.50  # At least 50% hedged
}

requires_hedging_recommendation if {
    portfolio_var_exceeds_action_level
    hedge_ratio := input.hedge_ratio
    hedge_ratio < 0.50
}

# Monitoring frequency determination
monitoring_frequency = "REALTIME" if {
    exceeds_circuit_breaker
}

monitoring_frequency = "HOURLY" if {
    portfolio_var_exceeds_escalation_level
}

monitoring_frequency = "DAILY" if {
    portfolio_var_exceeds_action_level
}

monitoring_frequency = "DAILY" if {
    delta_exposure_level == "HIGH"
}

monitoring_frequency = "WEEKLY" if {
    portfolio_var_within_threshold
    not exceeds_drawdown_limit
}

# Risk rating assignment
risk_rating = "RED" if {
    exceeds_circuit_breaker
}

risk_rating = "RED" if {
    exceeds_drawdown_limit
}

risk_rating = "AMBER" if {
    portfolio_var_exceeds_escalation_level
}

risk_rating = "AMBER" if {
    delta_exposure_level == "HIGH"
}

risk_rating = "AMBER" if {
    liquidity_risk_level == "HIGH"
}

risk_rating = "GREEN" if {
    portfolio_var_within_threshold
    drawdown_within_limits
    not exceeds_leverage_limit
    liquidity_risk_level != "HIGH"
}

# Decision rationale
reason = "Portfolio risk metrics within acceptable thresholds" if {
    decision == "ALLOW"
}

reason = sprintf("Portfolio VaR at action level: %.2f%% (threshold: %.2f%%)",
    [input.portfolio_var * 100, var_thresholds.action_level * 100]) if {
    decision == "MONITOR"
}

reason = sprintf("Portfolio VaR exceeds action level: %.2f%% - hedging required",
    [input.portfolio_var * 100]) if {
    decision == "REQUIRE_HEDGING"
}

reason = sprintf("Portfolio VaR exceeds escalation level: %.2f%% - escalate to committee",
    [input.portfolio_var * 100]) if {
    decision == "REQUIRE_RISK_COMMITTEE"
}

reason = sprintf("Portfolio VaR exceeds circuit breaker: %.2f%% - trading halt imposed",
    [input.portfolio_var * 100]) if {
    decision == "TRADING_HALT"
}

reason = sprintf("Leverage exceeds limits - deleveraging required")  if {
    decision == "REQUIRE_DELEVERAGING"
}

reason = sprintf("Drawdown from high water mark: %.2f%%",
    [input.current_drawdown_from_hwm * 100]) if {
    exceeds_drawdown_limit
}

reason = sprintf("Delta exposure: %.2f (limit: %.2f)",
    [input.portfolio_delta, greeks_limits.delta]) if {
    delta_exposure_level == "HIGH"
}

# Required conditions and actions
conditions = ["daily_monitoring"] if {
    portfolio_var_in_action_range
}

conditions = ["implement_hedging", "risk_committee_review"] if {
    decision == "REQUIRE_HEDGING"
}

conditions = ["risk_committee_escalation", "real_time_monitoring"] if {
    decision == "REQUIRE_RISK_COMMITTEE"
}

conditions = ["immediate_trading_halt", "executive_escalation"] if {
    decision == "TRADING_HALT"
}

conditions = ["stress_testing"] if {
    stress_test_required
}

# Required audit fields
required_audit_fields = [
    "portfolio_id",
    "measurement_timestamp",
    "portfolio_var",
    "portfolio_var_threshold",
    "portfolio_delta",
    "portfolio_gamma",
    "portfolio_vega",
    "portfolio_theta",
    "portfolio_rho",
    "current_drawdown",
    "hedge_ratio",
    "diversification_score",
    "risk_rating",
    "monitoring_frequency"
] if {
    decision in {"ALLOW", "MONITOR"}
}

required_audit_fields = [
    "portfolio_id",
    "measurement_timestamp",
    "portfolio_var",
    "var_threshold_violated",
    "hedging_status",
    "hedge_recommendation",
    "required_action",
    "approver_id",
    "approval_timestamp"
] if {
    decision in {"REQUIRE_HEDGING", "REQUIRE_RISK_COMMITTEE"}
}

required_audit_fields = [
    "portfolio_id",
    "measurement_timestamp",
    "circuit_breaker_level",
    "current_var",
    "halt_timestamp",
    "halt_reason",
    "trading_halt_issued_by",
    "escalation_to_executive"
] if {
    decision == "TRADING_HALT"
}
