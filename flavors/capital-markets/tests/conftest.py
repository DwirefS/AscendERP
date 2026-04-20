"""
Capital Markets Test Configuration and Fixtures.
Provides common test setup and sample data for capital markets tests.
"""
import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any
from unittest.mock import MagicMock, AsyncMock
import numpy as np

from flavors.capital_markets.models.market_data import (
    Trade, Position, Portfolio, MarketTick, OrderSide, OrderType,
    OrderStatus, AssetClass, RiskMetrics
)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_memory_system():
    """Mock memory system for testing agents and councils."""
    memory = AsyncMock()
    memory.store_episodic = AsyncMock(return_value="mem-001")
    memory.store_semantic = AsyncMock(return_value="mem-002")
    memory.store_procedural = AsyncMock(return_value="mem-003")
    memory.retrieve_episodic = AsyncMock(return_value=[])
    memory.retrieve_semantic = AsyncMock(return_value=[])
    memory.retrieve_procedural = AsyncMock(return_value=[])
    return memory


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for agent testing."""
    llm = AsyncMock()
    llm.generate = AsyncMock(return_value={
        "content": "Mock LLM response",
        "tokens_used": 150,
        "confidence": 0.92
    })
    llm.embed = AsyncMock(return_value=[0.1] * 1024)
    llm.complete = AsyncMock(return_value="Mock completion")
    return llm


@pytest.fixture
def mock_policy_engine():
    """Mock policy engine for compliance testing."""
    policy = AsyncMock()
    policy.evaluate = AsyncMock(return_value={
        "decision": "ALLOW",
        "allowed": True,
        "reason": None,
        "conditions": [],
        "audit_required": False
    })
    policy.check_tool_access = AsyncMock(return_value={
        "decision": "ALLOW",
        "allowed": True
    })
    policy.check_data_access = AsyncMock(return_value={
        "decision": "ALLOW",
        "allowed": True
    })
    policy.check_trading_limits = AsyncMock(return_value={
        "allowed": True,
        "remaining_limit": 1000000.0
    })
    return policy


@pytest.fixture
def sample_portfolio() -> Portfolio:
    """Sample portfolio with multiple positions."""
    portfolio = Portfolio(
        portfolio_id="port-001",
        name="Test Portfolio",
        cash=500000.0,
        risk_profile="balanced",
        currency="USD"
    )

    # Add sample positions
    aapl = Position(
        ticker="AAPL",
        quantity=1000,
        avg_cost=150.0,
        current_price=155.0,
        sector="Technology",
        asset_class=AssetClass.EQUITY
    )

    msft = Position(
        ticker="MSFT",
        quantity=500,
        avg_cost=300.0,
        current_price=310.0,
        sector="Technology",
        asset_class=AssetClass.EQUITY
    )

    bond = Position(
        ticker="BND",
        quantity=100,
        avg_cost=80.0,
        current_price=82.0,
        sector="Fixed Income",
        asset_class=AssetClass.FIXED_INCOME
    )

    portfolio.add_position(aapl)
    portfolio.add_position(msft)
    portfolio.add_position(bond)

    return portfolio


@pytest.fixture
def sample_trade() -> Trade:
    """Sample executed trade."""
    return Trade(
        trade_id="trd-001",
        ticker="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        price=150.0,
        timestamp=datetime.utcnow(),
        order_type=OrderType.MARKET,
        venue="NYSE",
        status=OrderStatus.FILLED,
        execution_latency_ms=45.5,
        slippage=0.02,
        realized_pnl=150.0
    )


@pytest.fixture
def sample_market_data() -> Dict[str, MarketTick]:
    """Sample market data for multiple securities."""
    now = datetime.utcnow()
    return {
        "AAPL": MarketTick(
            ticker="AAPL",
            bid=154.95,
            ask=155.05,
            last=155.00,
            volume=50000000,
            timestamp=now,
            open=153.0,
            high=156.0,
            low=152.5,
            close=155.00
        ),
        "MSFT": MarketTick(
            ticker="MSFT",
            bid=309.95,
            ask=310.05,
            last=310.00,
            volume=30000000,
            timestamp=now,
            open=308.0,
            high=312.0,
            low=307.5,
            close=310.00
        ),
        "BND": MarketTick(
            ticker="BND",
            bid=81.95,
            ask=82.05,
            last=82.00,
            volume=5000000,
            timestamp=now,
            open=81.5,
            high=82.5,
            low=81.0,
            close=82.00
        )
    }


@pytest.fixture
def sample_returns() -> np.ndarray:
    """Sample historical returns for risk calculations."""
    np.random.seed(42)
    # Generate realistic daily returns (mean ~0.05%, std ~1.5%)
    returns = np.random.normal(0.0005, 0.015, 252)
    return returns


@pytest.fixture
def sample_cov_matrix() -> np.ndarray:
    """Sample 3x3 covariance matrix for 3 assets."""
    cov = np.array([
        [0.0004, 0.00015, 0.00008],
        [0.00015, 0.0005, 0.00010],
        [0.00008, 0.00010, 0.0002]
    ])
    return cov


@pytest.fixture
def sample_expected_returns() -> np.ndarray:
    """Sample expected returns for 3 assets."""
    return np.array([0.08, 0.10, 0.04])  # 8%, 10%, 4% annual returns


@pytest.fixture
def sample_risk_metrics() -> RiskMetrics:
    """Sample risk metrics."""
    return RiskMetrics(
        var_95=0.025,  # 2.5% VaR at 95%
        var_99=0.038,  # 3.8% VaR at 99%
        cvar_95=0.035,  # 3.5% CVaR at 95%
        sharpe_ratio=1.25,
        sortino_ratio=1.80,
        max_drawdown=0.15,
        beta=1.05,
        alpha=0.02,
        herfindahl_index=0.45,
        tracking_error=0.08
    )


# Test markers configuration
def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "models: mark test as model test")
    config.addinivalue_line("markers", "agents: mark test as agent test")
    config.addinivalue_line("markers", "councils: mark test as council test")
    config.addinivalue_line("markers", "workflows: mark test as workflow test")
