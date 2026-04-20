"""
Capital Markets Experts - Mixture of Experts (MoE)

Specialized financial experts for capital markets analysis.

Experts:
- EquityAnalystExpert: Stock research and fundamental analysis
- CreditAnalystExpert: Fixed income and credit analysis
- DerivativesExpert: Options, futures, and hedging strategies
- PortfolioExpert: Portfolio construction and optimization
- ComplianceExpert: Regulatory compliance and AML/KYC
"""

from .equity_analyst import EquityAnalystExpert
from .credit_analyst import CreditAnalystExpert
from .derivatives_expert import DerivativesExpert
from .portfolio_expert import PortfolioExpert
from .compliance_expert import ComplianceExpert

__all__ = [
    "EquityAnalystExpert",
    "CreditAnalystExpert",
    "DerivativesExpert",
    "PortfolioExpert",
    "ComplianceExpert"
]
