"""
Capital Markets Agents for ANTS/Ascend EOS.

This module provides specialized agents for capital markets operations including:
- Trading execution with smart order routing
- Risk management and VaR calculations
- Portfolio optimization and rebalancing
- Client relationship management
- Regulatory compliance (KYC, AML, sanctions)
- Derivatives pricing and hedging
"""

from .trading_agent import TradingAgent
from .risk_management_agent import RiskManagementAgent
from .portfolio_manager_agent import PortfolioManagerAgent
from .client_service_agent import ClientServiceAgent
from .compliance_agent import ComplianceAgent
from .derivatives_agent import DerivativesAgent

__all__ = [
    "TradingAgent",
    "RiskManagementAgent",
    "PortfolioManagerAgent",
    "ClientServiceAgent",
    "ComplianceAgent",
    "DerivativesAgent",
]
