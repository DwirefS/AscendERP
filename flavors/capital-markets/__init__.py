"""
Capital Markets Flavor for ANTS/Ascend EOS

Provides specialized councils, experts, and policies for capital markets operations including:
- Trading execution and order management
- Risk governance and oversight
- Capital allocation and portfolio optimization
- Regulatory compliance and enforcement

Modules:
- councils: Specialized decision-making councils
- experts: MoE financial experts for analysis
- policies: OPA policies for guardrails and control
"""

from flavors.capital_markets.councils.trading_council import create_trading_council
from flavors.capital_markets.councils.risk_committee import create_risk_committee
from flavors.capital_markets.councils.capital_allocation_council import create_capital_allocation_council

__all__ = [
    "create_trading_council",
    "create_risk_committee",
    "create_capital_allocation_council"
]
