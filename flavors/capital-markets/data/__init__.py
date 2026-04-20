"""
Market data simulation and seed data for Capital Markets platform.

Provides realistic market data generation and demo datasets for backtesting
and demonstrations.
"""

from .market_data_simulator import MarketDataSimulator

from .seed_data import (
    SAMPLE_PORTFOLIOS,
    SAMPLE_CLIENTS,
    SAMPLE_TICKERS,
    RISK_PARAMETERS,
    DEMO_SCENARIOS,
    EXPECTED_RETURNS,
    VOLATILITIES,
    SAMPLE_CORRELATION_MATRIX,
    BACKTEST_CONFIG,
    PERFORMANCE_BENCHMARKS,
)

__all__ = [
    "MarketDataSimulator",
    "SAMPLE_PORTFOLIOS",
    "SAMPLE_CLIENTS",
    "SAMPLE_TICKERS",
    "RISK_PARAMETERS",
    "DEMO_SCENARIOS",
    "EXPECTED_RETURNS",
    "VOLATILITIES",
    "SAMPLE_CORRELATION_MATRIX",
    "BACKTEST_CONFIG",
    "PERFORMANCE_BENCHMARKS",
]
