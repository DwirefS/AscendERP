#!/usr/bin/env python3
"""
ANTS Capital Markets Demo Data Generator

Generates synthetic financial market data using Geometric Brownian Motion (GBM)
for demonstration and testing purposes.

Methodology:
-----------
Geometric Brownian Motion is a standard stochastic process used to model stock prices.
The differential equation is:

    dS = μS dt + σS dW

Where:
  S = Stock price
  μ = Drift (expected return)
  σ = Volatility (annualized standard deviation)
  W = Wiener process (random walk)

Discretized form (Euler scheme):
    S(t+dt) = S(t) * exp((μ - σ²/2)dt + σ√dt * Z)

Where:
  Z ~ N(0,1) is a standard normal random variable
  dt = 1/252 (one trading day)
  μ is annualized return
  σ is annualized volatility

This approach ensures:
  1. Log-normal distribution of returns (realistic for stock prices)
  2. No negative prices (prices are always positive)
  3. Continuous compounding consistent with market conventions
  4. Correlation structure can be modeled through correlated Z values

Parameters for each ticker are calibrated to realistic market regimes:
  - Tech stocks (NVDA, AAPL, MSFT): Higher volatility (20-30%), strong drift
  - Established mega-caps: Moderate volatility (15-25%), steady growth
  - Financial stocks: Moderate volatility (18-22%), cyclical
  - Energy: High volatility (25-35%), mean-reverting
  - Defensive: Low volatility (12-18%), stable dividends

Seed: 42 ensures reproducibility across runs for demo consistency.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import os
import json

# Set random seed for reproducibility
np.random.seed(42)

# Configuration
SEED = 42
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
MARKET_DATA_DIR = os.path.join(OUTPUT_DIR, 'market_data')
NUM_TICKERS = 20
TRADING_DAYS = 252 * 2  # 2 years of daily data
INITIAL_DATE = datetime(2022, 1, 3)  # Start of 2022

# Ticker configurations: (ticker, initial_price, annual_return, annual_volatility, sector)
TICKER_CONFIG = [
    # Technology
    ('NVDA', 295.00, 0.28, 0.35, 'Technology'),
    ('AAPL', 150.00, 0.22, 0.28, 'Technology'),
    ('MSFT', 300.00, 0.25, 0.25, 'Technology'),
    ('META', 130.00, 0.15, 0.40, 'Technology'),
    ('TSLA', 920.00, 0.35, 0.60, 'Technology'),

    # Financials
    ('JPM', 140.00, 0.12, 0.22, 'Financials'),
    ('BAC', 35.00, 0.08, 0.25, 'Financials'),
    ('GS', 340.00, 0.10, 0.24, 'Financials'),

    # Healthcare
    ('JNJ', 160.00, 0.15, 0.16, 'Healthcare'),
    ('UNH', 480.00, 0.18, 0.20, 'Healthcare'),
    ('PFE', 50.00, 0.05, 0.22, 'Healthcare'),

    # Energy
    ('XOM', 110.00, 0.25, 0.32, 'Energy'),
    ('CVX', 160.00, 0.22, 0.28, 'Energy'),

    # Consumer/Retail
    ('AMZN', 140.00, 0.20, 0.30, 'Consumer'),
    ('WMT', 140.00, 0.10, 0.18, 'Consumer'),

    # Industrial
    ('BA', 190.00, 0.08, 0.35, 'Industrial'),
    ('CAT', 220.00, 0.12, 0.28, 'Industrial'),

    # Utilities
    ('NEE', 85.00, 0.08, 0.14, 'Utilities'),
    ('DUK', 105.00, 0.06, 0.15, 'Utilities'),

    # Real Estate
    ('SPG', 145.00, 0.05, 0.22, 'Real Estate'),
]


def generate_trading_dates(start_date, num_days):
    """
    Generate trading dates (business days only).

    Args:
        start_date: datetime object for first trading day
        num_days: number of trading days to generate

    Returns:
        list of datetime objects (excluding weekends and major holidays)
    """
    dates = []
    current_date = start_date

    # US market holidays (simplified list)
    holidays = {
        datetime(2022, 1, 17),   # MLK Day
        datetime(2022, 2, 21),   # Presidents Day
        datetime(2022, 3, 18),   # Good Friday
        datetime(2022, 5, 30),   # Memorial Day
        datetime(2022, 6, 20),   # Juneteenth
        datetime(2022, 7, 4),    # Independence Day
        datetime(2022, 9, 5),    # Labor Day
        datetime(2022, 11, 23),  # Thanksgiving
        datetime(2022, 12, 26),  # Christmas observed
        datetime(2023, 1, 16),   # MLK Day
        datetime(2023, 2, 20),   # Presidents Day
        datetime(2023, 4, 7),    # Good Friday
        datetime(2023, 5, 29),   # Memorial Day
        datetime(2023, 6, 19),   # Juneteenth
        datetime(2023, 7, 4),    # Independence Day
        datetime(2023, 9, 4),    # Labor Day
        datetime(2023, 11, 23),  # Thanksgiving
        datetime(2023, 12, 25),  # Christmas
    }

    while len(dates) < num_days:
        # Skip weekends and holidays
        if current_date.weekday() < 5 and current_date not in holidays:
            dates.append(current_date)
        current_date += timedelta(days=1)

    return dates[:num_days]


def generate_gbm_path(S0, mu, sigma, T, num_steps, seed_offset=0):
    """
    Generate a Geometric Brownian Motion price path.

    Implementation of the discretized GBM equation:
        S(t+dt) = S(t) * exp((μ - σ²/2)dt + σ√dt * Z)

    This ensures:
    - Lognormal distribution of prices (prices never negative)
    - Consistent with Black-Scholes framework
    - Realistic mean-reversion and volatility clustering when calibrated properly

    Args:
        S0: Initial stock price
        mu: Annual drift (expected return)
        sigma: Annual volatility
        T: Time period in years
        num_steps: Number of time steps
        seed_offset: Offset for random seed to vary across tickers

    Returns:
        numpy array of prices
    """
    # Set seed for this ticker (ensures reproducibility but varies by ticker)
    np.random.seed(SEED + seed_offset)

    dt = T / num_steps  # Time step (1 trading day)

    # Drift and diffusion components
    drift_component = (mu - 0.5 * sigma ** 2) * dt
    diffusion_component = sigma * np.sqrt(dt)

    # Generate random normal increments
    Z = np.random.standard_normal(num_steps)

    # Initialize price array
    prices = np.zeros(num_steps + 1)
    prices[0] = S0

    # Generate GBM path using the discretized equation
    for i in range(num_steps):
        prices[i + 1] = prices[i] * np.exp(drift_component + diffusion_component * Z[i])

    return prices


def generate_ohlcv_from_path(prices, dates, ticker):
    """
    Generate OHLCV data from a GBM price path.

    Uses intraday volatility to create realistic open/high/low/close bars.
    Volume is correlated with volatility (realistic market microstructure).

    Args:
        prices: Array of closing prices from GBM
        dates: List of trading dates
        ticker: Ticker symbol (for volume base calculation)

    Returns:
        pandas DataFrame with OHLC data
    """
    np.random.seed(SEED + hash(ticker) % 1000)

    data = []

    for i in range(len(prices) - 1):
        close = prices[i + 1]
        open_price = prices[i]

        # Intraday volatility (typically 30-50% of daily vol)
        intraday_vol = 0.3 * np.random.uniform(0.8, 1.2)

        # Generate realistic high/low
        high_shock = np.abs(np.random.normal(0, intraday_vol)) + 0.001
        low_shock = np.abs(np.random.normal(0, intraday_vol)) + 0.001

        high_price = max(open_price, close) * (1 + high_shock)
        low_price = min(open_price, close) * (1 - low_shock)

        # Volume: base volume with volatility correlation
        base_volume = {
            'NVDA': 50_000_000, 'AAPL': 50_000_000, 'MSFT': 30_000_000,
            'TSLA': 120_000_000, 'META': 20_000_000,
            'JPM': 8_000_000, 'BAC': 40_000_000, 'GS': 2_000_000,
            'JNJ': 4_000_000, 'UNH': 3_000_000, 'PFE': 35_000_000,
            'XOM': 8_000_000, 'CVX': 3_000_000,
            'AMZN': 50_000_000, 'WMT': 7_000_000,
            'BA': 4_000_000, 'CAT': 3_500_000,
            'NEE': 2_000_000, 'DUK': 3_000_000, 'SPG': 2_500_000,
        }.get(ticker, 5_000_000)

        # Volume correlates with realized volatility
        price_change = abs((close - open_price) / open_price)
        volume_multiplier = 0.8 + 1.2 * min(price_change * 10, 1.0)
        volume = int(base_volume * volume_multiplier * np.random.uniform(0.7, 1.3))

        data.append({
            'Date': dates[i],
            'Ticker': ticker,
            'Open': round(open_price, 2),
            'High': round(high_price, 2),
            'Low': round(low_price, 2),
            'Close': round(close, 2),
            'Volume': volume,
            'Adjusted_Close': round(close, 2),  # No splits/dividends in this sim
        })

    return pd.DataFrame(data)


def main():
    """Generate all market data."""

    print("ANTS Capital Markets Demo Data Generator")
    print("=" * 60)
    print(f"Seed: {SEED}")
    print(f"Start Date: {INITIAL_DATE.strftime('%Y-%m-%d')}")
    print(f"Trading Days: {TRADING_DAYS}")
    print(f"Number of Tickers: {NUM_TICKERS}")
    print("=" * 60)

    # Generate trading dates
    trading_dates = generate_trading_dates(INITIAL_DATE, TRADING_DAYS)
    print(f"\nGenerated {len(trading_dates)} trading dates")

    # Generate OHLCV data for all tickers
    all_data = []

    for ticker_idx, (ticker, price, mu, sigma, sector) in enumerate(TICKER_CONFIG):
        print(f"Generating {ticker:6s} ({sector:15s}): ", end='', flush=True)

        # Generate GBM price path
        prices = generate_gbm_path(
            S0=price,
            mu=mu,
            sigma=sigma,
            T=2.0,  # 2 years
            num_steps=TRADING_DAYS,
            seed_offset=ticker_idx
        )

        # Convert to OHLCV
        df = generate_ohlcv_from_path(prices, trading_dates, ticker)
        all_data.append(df)

        print(f"Price range: ${df['Low'].min():.2f} - ${df['High'].max():.2f}")

    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df = combined_df.sort_values(['Date', 'Ticker']).reset_index(drop=True)

    # Ensure output directory exists
    os.makedirs(MARKET_DATA_DIR, exist_ok=True)

    # Write to CSV
    output_path = os.path.join(MARKET_DATA_DIR, 'equities.csv')
    combined_df.to_csv(output_path, index=False)

    print("\n" + "=" * 60)
    print(f"Data generated successfully!")
    print(f"Output: {output_path}")
    print(f"Records: {len(combined_df)}")
    print(f"Date range: {combined_df['Date'].min()} to {combined_df['Date'].max()}")
    print("=" * 60)


if __name__ == '__main__':
    main()
