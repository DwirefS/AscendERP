# Capital Markets Position Limits Policy
# Enforces position sizing, concentration limits, leverage constraints,
# and liquidity requirements for portfolio positions

package capital_markets.position_limits

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default reason = "No matching position policy rule"

# Position sizing limits
position_limits := {
    "max_notional_per_position": 50_000_000,  # $50M per position
    "max_single_asset_pct": 0.30,  # 30% of portfolio
    "max_sector_pct": 0.25,  # 25% per sector
    "max_country_pct": 0.20  # 20% per country
}

# Leverage constraints
leverage_limits := {
    "max_gross_leverage": 2.0,  # 2x gross leverage
    "max_net_leverage": 1.5,  # 1.5x net leverage
    "max_notional_exposure": 500_000_000  # $500M
}

# Liquidity requirements
liquidity_requirements := {
    "max_position_pct_of_adv": 0.05,  # Position <= 5% of avg daily volume
    "min_bid_ask_spread_bps": 10,  # Min 10 bps liquidity
    "min_market_cap_usd": 100_000_000  # $100M minimum market cap
}

# Risk concentration thresholds
concentration_thresholds := {
    "high": 0.25,  # Position >= 25% of portfolio
    "medium": 0.15,  # Position >= 15% of portfolio
    "low": 0.05   # Position >= 5% of portfolio
}

# Asset class categories
asset_categories := {
    "equities": ["STOCK", "ETF", "FUND"],
    "fixed_income": ["BOND", "NOTE", "RATE_SWAP"],
    "derivatives": ["OPTION", "FUTURE", "CDS"],
    "alternatives": ["COMMODITY", "REAL_ESTATE", "PRIVATE_EQUITY"]
}

# Position approval decision logic
decision = "ALLOW" if {
    notional_within_limit
    not violates_single_asset_limit
    not violates_sector_limit
    not violates_country_limit
    leverage_acceptable
    position_sufficiently_liquid
    not exceeds_concentration_warning
}

decision = "CONDITIONAL_APPROVAL" if {
    notional_within_limit
    leverage_acceptable
    position_sufficiently_liquid
    at_concentration_warning_level
    not violates_single_asset_limit
}

decision = "REQUIRE_APPROVAL" if {
    notional_within_limit
    leverage_acceptable
    violates_single_asset_limit
    margin_available_for_leverage
}

decision = "REQUIRE_APPROVAL" if {
    notional_within_limit
    violates_sector_limit
}

decision = "DENY" if {
    exceeds_notional_limit
}

decision = "DENY" if {
    exceeds_leverage_limit
}

decision = "DENY" if {
    insufficient_liquidity
}

decision = "DENY" if {
    exceeds_concentration_limit
}

# Notional position limit checks
notional_within_limit if {
    input.position_notional <= position_limits.max_notional_per_position
}

exceeds_notional_limit if {
    not notional_within_limit
}

# Single asset concentration checks
violates_single_asset_limit if {
    weight_in_portfolio := input.position_notional / input.total_portfolio_value
    weight_in_portfolio > position_limits.max_single_asset_pct
}

exceeds_concentration_limit if {
    weight_in_portfolio := input.position_notional / input.total_portfolio_value
    weight_in_portfolio > 0.35  # Hard limit at 35%
}

at_concentration_warning_level if {
    weight_in_portfolio := input.position_notional / input.total_portfolio_value
    weight_in_portfolio > position_limits.max_single_asset_pct
    weight_in_portfolio <= 0.35
}

concentration_level = "HIGH" if {
    weight := input.position_notional / input.total_portfolio_value
    weight > concentration_thresholds.high
}

concentration_level = "MEDIUM" if {
    weight := input.position_notional / input.total_portfolio_value
    weight > concentration_thresholds.medium
    weight <= concentration_thresholds.high
}

concentration_level = "LOW" if {
    weight := input.position_notional / input.total_portfolio_value
    weight <= concentration_thresholds.medium
}

# Sector concentration limits
violates_sector_limit if {
    sector_exposure := input.current_sector_exposure
    new_sector_weight := (sector_exposure + input.position_notional) / input.total_portfolio_value
    new_sector_weight > position_limits.max_sector_pct
}

# Country exposure limits
violates_country_limit if {
    country_exposure := input.current_country_exposure
    new_country_weight := (country_exposure + input.position_notional) / input.total_portfolio_value
    new_country_weight > position_limits.max_country_pct
}

# Leverage checks
calculate_gross_leverage if {
    gross_notional := input.total_long_notional + input.total_short_notional
    gross_leverage := gross_notional / input.total_portfolio_value
    gross_leverage <= leverage_limits.max_gross_leverage
}

calculate_net_leverage if {
    net_notional := input.total_long_notional - input.total_short_notional
    net_leverage := abs(net_notional) / input.total_portfolio_value
    net_leverage <= leverage_limits.max_net_leverage
}

calculate_total_notional if {
    total_exposure := input.total_long_notional + input.total_short_notional
    total_exposure <= leverage_limits.max_notional_exposure
}

leverage_acceptable if {
    calculate_gross_leverage
    calculate_net_leverage
    calculate_total_notional
}

exceeds_leverage_limit if {
    not leverage_acceptable
}

# Liquidity checks
position_sufficiently_liquid if {
    # Check position as % of average daily volume
    position_pct_adv := input.position_notional / input.average_daily_volume
    position_pct_adv <= liquidity_requirements.max_position_pct_of_adv

    # Check minimum spread requirement
    bid_ask_spread := input.bid_ask_spread_bps
    bid_ask_spread <= liquidity_requirements.min_bid_ask_spread_bps

    # Check minimum market cap
    market_cap := input.market_cap
    market_cap >= liquidity_requirements.min_market_cap_usd
}

insufficient_liquidity if {
    not position_sufficiently_liquid
}

liquidity_score = "HIGH" if {
    pct_adv := input.position_notional / input.average_daily_volume
    pct_adv < 0.01
    input.bid_ask_spread_bps < 5
}

liquidity_score = "MEDIUM" if {
    pct_adv := input.position_notional / input.average_daily_volume
    pct_adv < 0.05
    input.bid_ask_spread_bps < 15
}

liquidity_score = "LOW" if {
    pct_adv := input.position_notional / input.average_daily_volume
    pct_adv >= 0.05
}

# Exit strategy assessment
has_exit_strategy if {
    liquidity_score != "LOW"
    input.position_volatility < 0.40
}

# Monitoring requirements
monitoring_frequency = "REALTIME" if {
    concentration_level == "HIGH"
}

monitoring_frequency = "DAILY" if {
    concentration_level == "MEDIUM"
}

monitoring_frequency = "WEEKLY" if {
    concentration_level == "LOW"
}

# Margin and collateral requirements
margin_available_for_leverage if {
    available_margin := input.available_margin
    required_margin := input.position_notional * 0.15  # 15% margin requirement
    available_margin >= required_margin
}

# Risk rating assignment
risk_rating = "RED" if {
    exceeds_concentration_limit
}

risk_rating = "AMBER" if {
    at_concentration_warning_level
    not has_exit_strategy
}

risk_rating = "AMBER" if {
    liquidity_score == "LOW"
}

risk_rating = "GREEN" if {
    not exceeds_concentration_limit
    not at_concentration_warning_level
    liquidity_score != "LOW"
    has_exit_strategy
}

# Decision reasons
reason = "Position notional within limits, concentration acceptable" if {
    decision == "ALLOW"
}

reason = sprintf("Position concentration at warning level: %.1f%% of portfolio",
    [input.position_notional / input.total_portfolio_value * 100]) if {
    decision == "CONDITIONAL_APPROVAL"
}

reason = sprintf("Single asset limit violated: %.1f%% > %.1f%% limit",
    [input.position_notional / input.total_portfolio_value * 100,
     position_limits.max_single_asset_pct * 100]) if {
    violates_single_asset_limit
}

reason = sprintf("Sector concentration violated: %.1f%% > %.1f%% limit",
    [input.current_sector_exposure / input.total_portfolio_value * 100,
     position_limits.max_sector_pct * 100]) if {
    violates_sector_limit
}

reason = "Position notional exceeds maximum limit" if {
    exceeds_notional_limit
}

reason = sprintf("Leverage would exceed limits: proposed %.2fx > %.2fx",
    [leverage_limits.max_gross_leverage * 1.1, leverage_limits.max_gross_leverage]) if {
    exceeds_leverage_limit
}

reason = sprintf("Insufficient liquidity: position is %.2f%% of daily volume",
    [input.position_notional / input.average_daily_volume * 100]) if {
    insufficient_liquidity
}

reason = "Position concentration exceeds hard limit" if {
    exceeds_concentration_limit
}

# Approval conditions
conditions = ["concentration_monitoring"] if {
    decision == "CONDITIONAL_APPROVAL"
}

conditions = ["sector_reallocation"] if {
    violates_sector_limit
}

conditions = ["risk_committee_approval", "increased_monitoring"] if {
    decision == "REQUIRE_APPROVAL"
}

# Audit fields
required_audit_fields = [
    "position_id",
    "asset_identifier",
    "position_notional",
    "portfolio_weight",
    "concentration_level",
    "liquidity_score",
    "leverage_impact",
    "sector",
    "country",
    "decision_timestamp"
] if {
    decision in {"ALLOW", "CONDITIONAL_APPROVAL", "REQUIRE_APPROVAL"}
}

required_audit_fields = [
    "position_id",
    "asset_identifier",
    "position_notional",
    "rejection_reason",
    "limit_violated",
    "decision_timestamp"
] if {
    decision == "DENY"
}
