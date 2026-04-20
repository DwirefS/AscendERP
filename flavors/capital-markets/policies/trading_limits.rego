# Capital Markets Trading Limits Policy
# Enforces trade amount limits, execution thresholds, velocity controls,
# and counterparty exposure restrictions

package capital_markets.trading_limits

import future.keywords.if
import future.keywords.in

default decision = "DENY"
default reason = "No matching policy rule"

# Trading limit configuration
trading_limits := {
    "daily_limit": 100_000_000,  # $100M per day
    "single_trade_limit": 10_000_000,  # $10M per trade
    "large_order_threshold": 5_000_000  # $5M triggers council review
}

# Market hours (in seconds since midnight, UTC)
market_hours := {
    "weekday_start": 32400,  # 9:00 AM UTC
    "weekday_end": 57600,    # 4:00 PM UTC
    "weekend": "closed"
}

# Counterparty exposure limits
counterparty_limits := {
    "max_exposure": 500_000_000,  # $500M per counterparty
    "concentration_threshold": 0.20  # 20% of portfolio
}

# Velocity limits (rate of trading)
velocity_limits := {
    "trades_per_hour": 500,
    "trades_per_minute": 50,
    "max_amount_per_hour": 50_000_000,  # $50M per hour per agent
    "max_amount_per_minute": 2_000_000  # $2M per minute per agent
}

# Restricted securities and counterparties
restricted_list := {
    "securities": ["CRYPTO_TOKEN", "PENNY_STOCKS"],
    "counterparties": ["SANCTIONED_ENTITY_1", "SANCTIONED_ENTITY_2"]
}

# Main trading decision logic
decision = "ALLOW" if {
    amount_within_single_trade_limit
    not is_restricted_security
    not is_restricted_counterparty
    within_daily_limit
    within_market_hours
    within_velocity_limit
    counterparty_exposure_acceptable
    not exceeds_concentration_limit
}

decision = "REQUIRE_COUNCIL_APPROVAL" if {
    amount > trading_limits.single_trade_limit
    amount <= trading_limits.daily_limit
    not is_restricted_security
    not is_restricted_counterparty
    within_market_hours
    counterparty_exposure_acceptable
}

decision = "REQUIRE_COUNCIL_APPROVAL" if {
    amount > trading_limits.large_order_threshold
    is_large_order
}

decision = "DENY" if {
    is_restricted_security
}

decision = "DENY" if {
    is_restricted_counterparty
}

decision = "DENY" if {
    exceeds_daily_limit
}

decision = "DENY" if {
    outside_market_hours
}

decision = "DENY" if {
    exceeds_velocity_limit
}

decision = "DENY" if {
    exceeds_counterparty_limit
}

decision = "QUARANTINE_AGENT" if {
    exceeds_velocity_limit
    is_suspicious_pattern
}

# Amount validation rules
amount_within_single_trade_limit if {
    input.amount <= trading_limits.single_trade_limit
}

amount_within_daily_limit if {
    input.amount <= trading_limits.daily_limit
}

within_daily_limit if {
    period_amount := input.daily_trading_volume
    period_amount + input.amount <= trading_limits.daily_limit
}

exceeds_daily_limit if {
    not within_daily_limit
}

# Restricted security checks
is_restricted_security if {
    security := input.security
    security in restricted_list.securities
}

is_restricted_security if {
    # Check for pattern matches
    security := input.security
    startswith(security, "CRYPTO")
}

# Counterparty checks
is_restricted_counterparty if {
    counterparty := input.counterparty
    counterparty in restricted_list.counterparties
}

counterparty_exposure_acceptable if {
    current_exposure := input.current_counterparty_exposure
    new_exposure := current_exposure + input.amount
    new_exposure <= counterparty_limits.max_exposure
}

exceeds_counterparty_limit if {
    not counterparty_exposure_acceptable
}

exceeds_concentration_limit if {
    portfolio_size := input.portfolio_size
    counterparty_weight := (input.current_counterparty_exposure + input.amount) / portfolio_size
    counterparty_weight > counterparty_limits.concentration_threshold
}

# Market hours validation
is_market_hours(hour, day_of_week) if {
    day_of_week != "Saturday"
    day_of_week != "Sunday"
    hour >= 9
    hour <= 16
}

within_market_hours if {
    hour := input.transaction_hour
    day := input.day_of_week
    is_market_hours(hour, day)
}

within_market_hours if {
    # Allow pre-market and after-hours for institutional traders
    input.agent_type == "institutional_trader"
}

outside_market_hours if {
    not within_market_hours
}

# Velocity limit checks
within_velocity_limit if {
    hourly_count := input.hourly_trade_count
    hourly_count < velocity_limits.trades_per_hour
    hourly_amount := input.hourly_trading_volume
    hourly_amount < velocity_limits.max_amount_per_hour
}

within_velocity_limit if {
    minute_count := input.minute_trade_count
    minute_count < velocity_limits.trades_per_minute
    minute_amount := input.minute_trading_volume
    minute_amount < velocity_limits.max_amount_per_minute
}

exceeds_velocity_limit if {
    not within_velocity_limit
}

# Large order detection
is_large_order if {
    input.amount >= trading_limits.large_order_threshold
}

# Suspicious pattern detection
is_suspicious_pattern if {
    # Rapid-fire orders
    input.hourly_trade_count > velocity_limits.trades_per_hour
}

is_suspicious_pattern if {
    # Unusual order size relative to average
    avg_size := input.average_trade_size
    input.amount > avg_size * 5
}

is_suspicious_pattern if {
    # Concentrated in single counterparty
    input.daily_counterparty_concentration > 0.5
}

# Approval level determination
approval_level = "trading_council" if {
    amount > trading_limits.single_trade_limit
    amount <= 20_000_000
}

approval_level = "executive_committee" if {
    amount > 20_000_000
}

approval_level = "risk_committee" if {
    exceeds_velocity_limit
    not is_restricted_security
}

# Detailed reason generation
reason = "Trade amount within single trade limit" if {
    amount_within_single_trade_limit
    decision == "ALLOW"
}

reason = sprintf("Trade exceeds single trade limit of $%d, requires council approval",
    [trading_limits.single_trade_limit]) if {
    amount > trading_limits.single_trade_limit
    decision == "REQUIRE_COUNCIL_APPROVAL"
}

reason = "Security is on restricted list" if {
    is_restricted_security
}

reason = "Counterparty is restricted" if {
    is_restricted_counterparty
}

reason = sprintf("Daily trading limit exceeded: $%d remaining",
    [trading_limits.daily_limit - input.daily_trading_volume]) if {
    exceeds_daily_limit
}

reason = "Trade outside market hours" if {
    outside_market_hours
}

reason = sprintf("Velocity limit exceeded: %d trades/hour, max is %d",
    [input.hourly_trade_count, velocity_limits.trades_per_hour]) if {
    exceeds_velocity_limit
}

reason = sprintf("Counterparty exposure exceeds limit: $%d > $%d",
    [input.current_counterparty_exposure + input.amount, counterparty_limits.max_exposure]) if {
    exceeds_counterparty_limit
}

reason = "Concentration risk: single counterparty exposure too high" if {
    exceeds_concentration_limit
}

# Conditions for approval
conditions = ["single_approval"] if {
    decision == "REQUIRE_COUNCIL_APPROVAL"
    amount <= trading_limits.large_order_threshold
}

conditions = ["trading_council_approval"] if {
    decision == "REQUIRE_COUNCIL_APPROVAL"
    amount > trading_limits.large_order_threshold
}

# Audit requirements
required_audit_fields = [
    "trade_id",
    "timestamp",
    "agent_id",
    "security",
    "amount",
    "price",
    "counterparty",
    "execution_venue",
    "trader_id"
] if {
    decision in {"ALLOW", "REQUIRE_COUNCIL_APPROVAL"}
}

required_audit_fields = [
    "trade_id",
    "timestamp",
    "agent_id",
    "rejection_reason",
    "security",
    "amount",
    "counterparty"
] if {
    decision == "DENY"
}
