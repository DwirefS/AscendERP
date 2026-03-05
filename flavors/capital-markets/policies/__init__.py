"""
Capital Markets OPA Policies

OPA/Rego policies for capital markets guardrails and control enforcement.

Policies:
- trading_limits.rego: Trade amount and execution controls
- position_limits.rego: Position sizing and concentration limits
- compliance.rego: KYC/AML, sanctions, best execution
- risk_thresholds.rego: VaR, Greeks, drawdown, stress testing
"""

__all__ = [
    "trading_limits",
    "position_limits",
    "compliance",
    "risk_thresholds"
]
