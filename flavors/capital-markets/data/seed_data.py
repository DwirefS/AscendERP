"""
Demo seed data for Capital Markets platform.

Provides sample portfolios, clients, tickers, risk parameters, and scenarios
for demonstrations and testing.
"""

from typing import Dict, List
from datetime import datetime

# Sample portfolio configurations
SAMPLE_PORTFOLIOS = {
    "aggressive": {
        "portfolio_id": "port_aggressive_001",
        "name": "Aggressive Growth Portfolio",
        "risk_profile": "aggressive",
        "currency": "USD",
        "created_at": datetime(2024, 1, 1),
        "positions": [
            {
                "ticker": "TSLA",
                "quantity": 500,
                "avg_cost": 180.00,
                "sector": "Technology",
                "asset_class": "equity",
            },
            {
                "ticker": "AAPL",
                "quantity": 1000,
                "avg_cost": 165.00,
                "sector": "Technology",
                "asset_class": "equity",
            },
            {
                "ticker": "MSFT",
                "quantity": 600,
                "avg_cost": 400.00,
                "sector": "Technology",
                "asset_class": "equity",
            },
            {
                "ticker": "GE",
                "quantity": 2000,
                "avg_cost": 95.00,
                "sector": "Industrials",
                "asset_class": "equity",
            },
            {
                "ticker": "XOM",
                "quantity": 800,
                "avg_cost": 110.00,
                "sector": "Energy",
                "asset_class": "equity",
            },
        ],
        "cash": 50000.00,
    },
    "conservative": {
        "portfolio_id": "port_conservative_001",
        "name": "Conservative Income Portfolio",
        "risk_profile": "conservative",
        "currency": "USD",
        "created_at": datetime(2024, 1, 1),
        "positions": [
            {
                "ticker": "JNJ",
                "quantity": 300,
                "avg_cost": 155.00,
                "sector": "Healthcare",
                "asset_class": "equity",
            },
            {
                "ticker": "PG",
                "quantity": 400,
                "avg_cost": 160.00,
                "sector": "Consumer",
                "asset_class": "equity",
            },
            {
                "ticker": "BND",
                "quantity": 5000,
                "avg_cost": 70.00,
                "sector": "Fixed Income",
                "asset_class": "fixed_income",
            },
            {
                "ticker": "GLD",
                "quantity": 200,
                "avg_cost": 180.00,
                "sector": "Commodity",
                "asset_class": "commodity",
            },
        ],
        "cash": 100000.00,
    },
    "balanced": {
        "portfolio_id": "port_balanced_001",
        "name": "Balanced Multi-Asset Portfolio",
        "risk_profile": "balanced",
        "currency": "USD",
        "created_at": datetime(2024, 1, 1),
        "positions": [
            {
                "ticker": "SPY",
                "quantity": 800,
                "avg_cost": 430.00,
                "sector": "Index",
                "asset_class": "equity",
            },
            {
                "ticker": "MSFT",
                "quantity": 300,
                "avg_cost": 410.00,
                "sector": "Technology",
                "asset_class": "equity",
            },
            {
                "ticker": "JNJ",
                "quantity": 200,
                "avg_cost": 158.00,
                "sector": "Healthcare",
                "asset_class": "equity",
            },
            {
                "ticker": "BND",
                "quantity": 3000,
                "avg_cost": 72.00,
                "sector": "Fixed Income",
                "asset_class": "fixed_income",
            },
            {
                "ticker": "GLD",
                "quantity": 100,
                "avg_cost": 185.00,
                "sector": "Commodity",
                "asset_class": "commodity",
            },
        ],
        "cash": 75000.00,
    },
}

# Sample client configurations
SAMPLE_CLIENTS = [
    {
        "client_id": "CLI_001",
        "name": "Pension Fund Alpha",
        "type": "institutional",
        "kyc_status": "verified",
        "risk_level": "conservative",
        "aml_status": "clean",
        "jurisdiction": "US",
        "account_value": 5000000.00,
    },
    {
        "client_id": "CLI_002",
        "name": "Wealth Manager Partners",
        "type": "institutional",
        "kyc_status": "verified",
        "risk_level": "balanced",
        "aml_status": "clean",
        "jurisdiction": "US",
        "account_value": 2500000.00,
    },
    {
        "client_id": "CLI_003",
        "name": "High Net Worth Individual",
        "type": "individual",
        "kyc_status": "verified",
        "risk_level": "aggressive",
        "aml_status": "clean",
        "jurisdiction": "US",
        "account_value": 500000.00,
    },
    {
        "client_id": "CLI_004",
        "name": "Hedge Fund Partners LP",
        "type": "institutional",
        "kyc_status": "verified",
        "risk_level": "aggressive",
        "aml_status": "clean",
        "jurisdiction": "US",
        "account_value": 1000000.00,
    },
    {
        "client_id": "CLI_005",
        "name": "Endowment Fund",
        "type": "institutional",
        "kyc_status": "verified",
        "risk_level": "balanced",
        "aml_status": "clean",
        "jurisdiction": "US",
        "account_value": 3000000.00,
    },
]

# Ticker information with sectors
SAMPLE_TICKERS = {
    # Technology
    "AAPL": {"sector": "Technology", "industry": "Consumer Electronics", "market_cap": "very_large"},
    "MSFT": {"sector": "Technology", "industry": "Software", "market_cap": "very_large"},
    "GOOGL": {"sector": "Technology", "industry": "Internet Services", "market_cap": "very_large"},
    "TSLA": {"sector": "Technology", "industry": "Automotive", "market_cap": "large"},
    # Finance
    "JPM": {"sector": "Finance", "industry": "Banking", "market_cap": "very_large"},
    "BAC": {"sector": "Finance", "industry": "Banking", "market_cap": "large"},
    # Industrials
    "GE": {"sector": "Industrials", "industry": "Diversified", "market_cap": "large"},
    # Energy
    "XOM": {"sector": "Energy", "industry": "Oil & Gas", "market_cap": "very_large"},
    # Healthcare
    "JNJ": {"sector": "Healthcare", "industry": "Pharmaceuticals", "market_cap": "very_large"},
    # Consumer
    "PG": {"sector": "Consumer", "industry": "Consumer Products", "market_cap": "very_large"},
    # Index
    "SPY": {"sector": "Index", "industry": "S&P 500 ETF", "market_cap": "mega"},
    # Fixed Income
    "BND": {"sector": "Fixed Income", "industry": "Bond ETF", "market_cap": "mega"},
    # Commodity
    "GLD": {"sector": "Commodity", "industry": "Gold ETF", "market_cap": "mega"},
}

# Risk parameters and limits
RISK_PARAMETERS = {
    "var_limit_pct": 2.5,  # Portfolio VaR limit at 95% confidence
    "var_99_limit_pct": 5.0,  # VaR at 99% confidence
    "concentration_limit": 0.20,  # Max 20% in any single position
    "sector_concentration_limits": {
        "Technology": 0.35,
        "Finance": 0.25,
        "Healthcare": 0.20,
        "Industrials": 0.15,
        "Energy": 0.15,
        "Consumer": 0.15,
        "Commodity": 0.10,
        "Fixed Income": 0.50,
    },
    "single_issuer_limit": 0.10,
    "correlation_stress": 0.95,  # Assume all correlations move to 0.95 in stress
    "volatility_stress_multiplier": 2.0,  # Volatility doubles in stress
    "max_leverage": 1.5,  # 150% of equity can be borrowed
    "min_liquidity_days": 5,  # Positions must be liquidatable in 5 days
}

# Demo scenarios for presentations
DEMO_SCENARIOS = [
    {
        "scenario_id": "demo_01",
        "name": "Bull Market",
        "description": "Strong economic growth, equity rally",
        "equity_return": 0.12,
        "bond_return": 0.03,
        "volatility_change": 0.8,
        "duration": "6 months",
        "probability": 0.25,
    },
    {
        "scenario_id": "demo_02",
        "name": "Base Case",
        "description": "Moderate economic growth, stable markets",
        "equity_return": 0.08,
        "bond_return": 0.04,
        "volatility_change": 1.0,
        "duration": "12 months",
        "probability": 0.50,
    },
    {
        "scenario_id": "demo_03",
        "name": "Bear Market",
        "description": "Economic slowdown, equity selloff",
        "equity_return": -0.15,
        "bond_return": 0.05,
        "volatility_change": 1.5,
        "duration": "6 months",
        "probability": 0.20,
    },
    {
        "scenario_id": "demo_04",
        "name": "Stagflation",
        "description": "High inflation with economic stagnation",
        "equity_return": -0.10,
        "bond_return": -0.05,
        "volatility_change": 2.0,
        "duration": "12 months",
        "probability": 0.05,
    },
    {
        "scenario_id": "demo_05",
        "name": "Crisis",
        "description": "Severe market dislocation (COVID-19 style)",
        "equity_return": -0.35,
        "bond_return": -0.10,
        "volatility_change": 3.5,
        "duration": "3 months",
        "probability": 0.02,
    },
]

# Default expected returns and volatilities for optimization
EXPECTED_RETURNS = {
    "AAPL": 0.12,
    "MSFT": 0.11,
    "GOOGL": 0.13,
    "TSLA": 0.20,  # Higher expected return for volatile stock
    "JPM": 0.09,
    "BAC": 0.08,
    "GE": 0.07,
    "XOM": 0.06,
    "JNJ": 0.08,
    "PG": 0.07,
    "SPY": 0.09,
    "BND": 0.04,
    "GLD": 0.05,
}

VOLATILITIES = {
    "AAPL": 0.25,
    "MSFT": 0.22,
    "GOOGL": 0.24,
    "TSLA": 0.45,
    "JPM": 0.20,
    "BAC": 0.22,
    "GE": 0.28,
    "XOM": 0.26,
    "JNJ": 0.18,
    "PG": 0.15,
    "SPY": 0.18,
    "BND": 0.08,
    "GLD": 0.14,
}

# Sample correlation matrix (13x13 for our tickers)
# This is a simplified correlation structure
SAMPLE_CORRELATION_MATRIX = {
    "AAPL": {"AAPL": 1.00, "MSFT": 0.65, "GOOGL": 0.68, "TSLA": 0.45, "JPM": 0.35, "BAC": 0.32, "GE": 0.42, "XOM": 0.25, "JNJ": 0.28, "PG": 0.25, "SPY": 0.72, "BND": 0.15, "GLD": 0.10},
    "MSFT": {"AAPL": 0.65, "MSFT": 1.00, "GOOGL": 0.70, "TSLA": 0.50, "JPM": 0.38, "BAC": 0.35, "GE": 0.45, "XOM": 0.28, "JNJ": 0.32, "PG": 0.28, "SPY": 0.75, "BND": 0.18, "GLD": 0.12},
    "GOOGL": {"AAPL": 0.68, "MSFT": 0.70, "GOOGL": 1.00, "TSLA": 0.52, "JPM": 0.40, "BAC": 0.37, "GE": 0.48, "XOM": 0.30, "JNJ": 0.35, "PG": 0.32, "SPY": 0.78, "BND": 0.20, "GLD": 0.15},
    "TSLA": {"AAPL": 0.45, "MSFT": 0.50, "GOOGL": 0.52, "TSLA": 1.00, "JPM": 0.35, "BAC": 0.32, "GE": 0.40, "XOM": 0.20, "JNJ": 0.25, "PG": 0.20, "SPY": 0.58, "BND": 0.10, "GLD": 0.08},
    "JPM": {"AAPL": 0.35, "MSFT": 0.38, "GOOGL": 0.40, "TSLA": 0.35, "JPM": 1.00, "BAC": 0.72, "GE": 0.55, "XOM": 0.48, "JNJ": 0.42, "PG": 0.40, "SPY": 0.65, "BND": 0.35, "GLD": 0.25},
    "BAC": {"AAPL": 0.32, "MSFT": 0.35, "GOOGL": 0.37, "TSLA": 0.32, "JPM": 0.72, "BAC": 1.00, "GE": 0.52, "XOM": 0.45, "JNJ": 0.40, "PG": 0.38, "SPY": 0.62, "BND": 0.32, "GLD": 0.22},
    "GE": {"AAPL": 0.42, "MSFT": 0.45, "GOOGL": 0.48, "TSLA": 0.40, "JPM": 0.55, "BAC": 0.52, "GE": 1.00, "XOM": 0.62, "JNJ": 0.48, "PG": 0.50, "SPY": 0.68, "BND": 0.30, "GLD": 0.35},
    "XOM": {"AAPL": 0.25, "MSFT": 0.28, "GOOGL": 0.30, "TSLA": 0.20, "JPM": 0.48, "BAC": 0.45, "GE": 0.62, "XOM": 1.00, "JNJ": 0.42, "PG": 0.45, "SPY": 0.55, "BND": 0.28, "GLD": 0.45},
    "JNJ": {"AAPL": 0.28, "MSFT": 0.32, "GOOGL": 0.35, "TSLA": 0.25, "JPM": 0.42, "BAC": 0.40, "GE": 0.48, "XOM": 0.42, "JNJ": 1.00, "PG": 0.68, "SPY": 0.58, "BND": 0.35, "GLD": 0.20},
    "PG": {"AAPL": 0.25, "MSFT": 0.28, "GOOGL": 0.32, "TSLA": 0.20, "JPM": 0.40, "BAC": 0.38, "GE": 0.50, "XOM": 0.45, "JNJ": 0.68, "PG": 1.00, "SPY": 0.60, "BND": 0.38, "GLD": 0.22},
    "SPY": {"AAPL": 0.72, "MSFT": 0.75, "GOOGL": 0.78, "TSLA": 0.58, "JPM": 0.65, "BAC": 0.62, "GE": 0.68, "XOM": 0.55, "JNJ": 0.58, "PG": 0.60, "SPY": 1.00, "BND": 0.35, "GLD": 0.25},
    "BND": {"AAPL": 0.15, "MSFT": 0.18, "GOOGL": 0.20, "TSLA": 0.10, "JPM": 0.35, "BAC": 0.32, "GE": 0.30, "XOM": 0.28, "JNJ": 0.35, "PG": 0.38, "SPY": 0.35, "BND": 1.00, "GLD": 0.40},
    "GLD": {"AAPL": 0.10, "MSFT": 0.12, "GOOGL": 0.15, "TSLA": 0.08, "JPM": 0.25, "BAC": 0.22, "GE": 0.35, "XOM": 0.45, "JNJ": 0.20, "PG": 0.22, "SPY": 0.25, "BND": 0.40, "GLD": 1.00},
}

# Backtesting configuration
BACKTEST_CONFIG = {
    "start_date": "2023-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 1000000.00,
    "trading_costs": {
        "commission_pct": 0.001,  # 10 bps
        "slippage_bps": 2,  # 2 basis points
    },
    "rebalancing": {
        "frequency": "monthly",
        "threshold_pct": 0.05,  # Rebalance if drift > 5%
    },
}

# Performance benchmarks
PERFORMANCE_BENCHMARKS = {
    "aggressive": {
        "target_return": 0.12,
        "target_volatility": 0.18,
        "target_sharpe": 0.67,
    },
    "balanced": {
        "target_return": 0.08,
        "target_volatility": 0.10,
        "target_sharpe": 0.80,
    },
    "conservative": {
        "target_return": 0.05,
        "target_volatility": 0.06,
        "target_sharpe": 0.83,
    },
}
