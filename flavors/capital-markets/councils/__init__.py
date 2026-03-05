"""
Capital Markets Councils

Specialized decision-making councils for capital markets operations.

Councils:
- Trading Council: Real-time execution and order routing
- Risk Committee: Enterprise risk governance
- Capital Allocation Council: Strategic asset allocation
"""

from .trading_council import create_trading_council
from .risk_committee import create_risk_committee
from .capital_allocation_council import create_capital_allocation_council

__all__ = [
    "create_trading_council",
    "create_risk_committee",
    "create_capital_allocation_council"
]
