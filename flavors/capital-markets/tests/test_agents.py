"""
Tests for Capital Markets Agents.
Tests agent initialization, perception, tool building, and domain-specific logic.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from flavors.capital_markets.agents import (
    TradingAgent,
    RiskManagementAgent,
    PortfolioManagerAgent,
    ClientServiceAgent,
    ComplianceAgent,
    DerivativesAgent,
)
from flavors.capital_markets.models.market_data import OrderSide, OrderType


class TestTradingAgent:
    """Test Trading Agent functionality."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_trading_agent_initialization(self):
        """Test TradingAgent can be initialized with default config."""
        agent = TradingAgent()

        assert agent.name == "Trading Agent"
        assert "fetch_market_data" in agent.config.tools
        assert "route_order" in agent.config.tools
        assert agent.config.max_iterations == 15

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_trading_agent_perceive_valid_order(self):
        """Test perceive method with valid order."""
        agent = TradingAgent()

        order_data = {
            "ticker": "aapl",
            "side": "BUY",
            "quantity": 100,
            "order_type": "market",
            "urgency": "immediate",
            "client_id": "client-001",
        }

        # Mock context
        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(order_data, context)

        assert perception["ticker"] == "AAPL"
        assert perception["side"] == "buy"
        assert perception["quantity"] == 100.0
        assert perception["order_type"] == "market"

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_trading_agent_perceive_invalid_ticker(self):
        """Test perceive with missing ticker raises error."""
        agent = TradingAgent()

        order_data = {
            "side": "buy",
            "quantity": 100,
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        with pytest.raises(ValueError):
            await agent.perceive(order_data, context)

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_trading_agent_perceive_invalid_side(self):
        """Test perceive with invalid side raises error."""
        agent = TradingAgent()

        order_data = {
            "ticker": "AAPL",
            "side": "invalid",
            "quantity": 100,
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        with pytest.raises(ValueError):
            await agent.perceive(order_data, context)

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_trading_agent_perceive_invalid_quantity(self):
        """Test perceive with invalid quantity raises error."""
        agent = TradingAgent()

        order_data = {
            "ticker": "AAPL",
            "side": "buy",
            "quantity": -100,
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        with pytest.raises(ValueError):
            await agent.perceive(order_data, context)


class TestRiskManagementAgent:
    """Test Risk Management Agent functionality."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_risk_agent_initialization(self):
        """Test RiskManagementAgent can be initialized."""
        agent = RiskManagementAgent()

        assert agent.name == "Risk Management Agent"
        assert "calculate_var" in agent.config.tools
        assert "check_position_limits" in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_risk_agent_perceive_portfolio_data(self):
        """Test perceive method with portfolio data."""
        agent = RiskManagementAgent()

        portfolio_data = {
            "portfolio_id": "port-001",
            "total_value": 1000000.0,
            "positions": 5,
            "cash_level": 0.15,
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(portfolio_data, context)

        assert perception["portfolio_id"] == "port-001"
        assert perception["total_value"] == 1000000.0


class TestPortfolioManagerAgent:
    """Test Portfolio Manager Agent functionality."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_portfolio_manager_initialization(self):
        """Test PortfolioManagerAgent can be initialized."""
        agent = PortfolioManagerAgent()

        assert agent.name == "Portfolio Manager Agent"
        assert "rebalance_portfolio" in agent.config.tools
        assert "optimize_allocation" in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_portfolio_manager_perceive(self):
        """Test portfolio manager perceive method."""
        agent = PortfolioManagerAgent()

        rebalance_request = {
            "portfolio_id": "port-001",
            "target_allocation": {"stocks": 0.60, "bonds": 0.40},
            "rebalance_threshold": 0.05,
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(rebalance_request, context)

        assert perception["portfolio_id"] == "port-001"
        assert perception["target_allocation"] is not None


class TestClientServiceAgent:
    """Test Client Service Agent functionality."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_client_service_initialization(self):
        """Test ClientServiceAgent can be initialized."""
        agent = ClientServiceAgent()

        assert agent.name == "Client Service Agent"
        assert "fetch_client_profile" in agent.config.tools
        assert "update_client_data" in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_client_service_perceive(self):
        """Test client service perceive method."""
        agent = ClientServiceAgent()

        client_request = {
            "client_id": "client-001",
            "request_type": "profile_update",
            "data": {
                "risk_profile": "aggressive",
                "investment_horizon": "long_term",
            },
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(client_request, context)

        assert perception["client_id"] == "client-001"
        assert perception["request_type"] == "profile_update"


class TestComplianceAgent:
    """Test Compliance Agent functionality."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_compliance_agent_initialization(self):
        """Test ComplianceAgent can be initialized."""
        agent = ComplianceAgent()

        assert agent.name == "Compliance Agent"
        assert "check_kyc" in agent.config.tools
        assert "check_aml" in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_compliance_agent_perceive_kyc_check(self):
        """Test compliance agent perceive for KYC."""
        agent = ComplianceAgent()

        kyc_request = {
            "check_type": "kyc",
            "client_id": "client-001",
            "documents": ["id", "proof_of_address"],
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(kyc_request, context)

        assert perception["check_type"] == "kyc"
        assert perception["client_id"] == "client-001"

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_compliance_agent_perceive_aml_check(self):
        """Test compliance agent perceive for AML."""
        agent = ComplianceAgent()

        aml_request = {
            "check_type": "aml",
            "client_id": "client-001",
            "transaction_amount": 500000.0,
            "source": "wire_transfer",
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(aml_request, context)

        assert perception["check_type"] == "aml"
        assert perception["transaction_amount"] == 500000.0


class TestDerivativesAgent:
    """Test Derivatives Agent functionality."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_derivatives_agent_initialization(self):
        """Test DerivativesAgent can be initialized."""
        agent = DerivativesAgent()

        assert agent.name == "Derivatives Agent"
        assert "price_option" in agent.config.tools
        assert "calculate_greeks" in agent.config.tools
        assert "hedge_position" in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_derivatives_agent_perceive_pricing_request(self):
        """Test derivatives agent perceive for option pricing."""
        agent = DerivativesAgent()

        pricing_request = {
            "request_type": "price_option",
            "underlying": "AAPL",
            "strike": 150.0,
            "maturity": "2025-01-17",
            "volatility": 0.25,
            "option_type": "call",
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(pricing_request, context)

        assert perception["underlying"] == "AAPL"
        assert perception["strike"] == 150.0
        assert perception["option_type"] == "call"

    @pytest.mark.unit
    @pytest.mark.agents
    @pytest.mark.asyncio
    async def test_derivatives_agent_perceive_greeks_request(self):
        """Test derivatives agent perceive for Greeks calculation."""
        agent = DerivativesAgent()

        greeks_request = {
            "request_type": "calculate_greeks",
            "underlying": "MSFT",
            "strike": 350.0,
            "maturity": "2025-03-21",
            "volatility": 0.30,
        }

        context = MagicMock()
        context.trace_id = "trace-001"

        perception = await agent.perceive(greeks_request, context)

        assert perception["underlying"] == "MSFT"
        assert perception["request_type"] == "calculate_greeks"


class TestAgentToolBuilding:
    """Test that agents properly build their tools."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_trading_agent_tools(self):
        """Test TradingAgent has correct tools configured."""
        agent = TradingAgent()

        expected_tools = [
            "fetch_market_data",
            "check_trading_limits",
            "calculate_slippage",
            "route_order",
            "verify_execution",
        ]

        for tool in expected_tools:
            assert tool in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    def test_risk_agent_tools(self):
        """Test RiskManagementAgent has correct tools."""
        agent = RiskManagementAgent()

        expected_tools = [
            "calculate_var",
            "check_position_limits",
            "calculate_greeks",
            "stress_test",
        ]

        for tool in expected_tools:
            assert tool in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    def test_portfolio_manager_tools(self):
        """Test PortfolioManagerAgent has correct tools."""
        agent = PortfolioManagerAgent()

        expected_tools = [
            "rebalance_portfolio",
            "optimize_allocation",
            "calculate_performance",
        ]

        for tool in expected_tools:
            assert tool in agent.config.tools

    @pytest.mark.unit
    @pytest.mark.agents
    def test_compliance_agent_tools(self):
        """Test ComplianceAgent has correct tools."""
        agent = ComplianceAgent()

        expected_tools = ["check_kyc", "check_aml", "check_sanctions"]

        for tool in expected_tools:
            assert tool in agent.config.tools


class TestAgentConfiguration:
    """Test agent configuration and setup."""

    @pytest.mark.unit
    @pytest.mark.agents
    def test_all_agents_have_names(self):
        """Test all agents have meaningful names."""
        agents = [
            TradingAgent(),
            RiskManagementAgent(),
            PortfolioManagerAgent(),
            ClientServiceAgent(),
            ComplianceAgent(),
            DerivativesAgent(),
        ]

        for agent in agents:
            assert agent.name is not None
            assert len(agent.name) > 0
            assert "Agent" in agent.name

    @pytest.mark.unit
    @pytest.mark.agents
    def test_all_agents_have_descriptions(self):
        """Test all agents have descriptions."""
        agents = [
            TradingAgent(),
            RiskManagementAgent(),
            PortfolioManagerAgent(),
            ClientServiceAgent(),
            ComplianceAgent(),
            DerivativesAgent(),
        ]

        for agent in agents:
            assert agent.description is not None
            assert len(agent.description) > 0

    @pytest.mark.unit
    @pytest.mark.agents
    def test_all_agents_have_tools(self):
        """Test all agents have at least one tool."""
        agents = [
            TradingAgent(),
            RiskManagementAgent(),
            PortfolioManagerAgent(),
            ClientServiceAgent(),
            ComplianceAgent(),
            DerivativesAgent(),
        ]

        for agent in agents:
            assert len(agent.config.tools) > 0

    @pytest.mark.unit
    @pytest.mark.agents
    def test_agent_timeout_values(self):
        """Test agents have reasonable timeout values."""
        agents = [
            TradingAgent(),
            RiskManagementAgent(),
            PortfolioManagerAgent(),
            ClientServiceAgent(),
            ComplianceAgent(),
            DerivativesAgent(),
        ]

        for agent in agents:
            assert agent.config.timeout_seconds > 0
            assert agent.config.timeout_seconds <= 300  # Max 5 minutes

    @pytest.mark.unit
    @pytest.mark.agents
    def test_agent_max_iterations(self):
        """Test agents have reasonable max iteration values."""
        agents = [
            TradingAgent(),
            RiskManagementAgent(),
            PortfolioManagerAgent(),
            ClientServiceAgent(),
            ComplianceAgent(),
            DerivativesAgent(),
        ]

        for agent in agents:
            assert agent.config.max_iterations > 0
            assert agent.config.max_iterations <= 30
