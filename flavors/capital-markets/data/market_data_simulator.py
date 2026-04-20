"""
Market data simulator for safe demos and backtesting.

Generates realistic market data using Geometric Brownian Motion,
order books, and trade history without requiring live market connections.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np
import uuid

try:
    from ..models.market_data import (
        MarketTick,
        OrderBook,
        Trade,
        OrderType,
        OrderSide,
        OrderStatus,
        Portfolio,
    )
except ImportError:
    from models.market_data import (
        MarketTick,
        OrderBook,
        Trade,
        OrderType,
        OrderSide,
        OrderStatus,
        Portfolio,
    )


class MarketDataSimulator:
    """
    Simulates realistic market data for safe demos and backtesting.

    Uses Geometric Brownian Motion (GBM) for price evolution with realistic
    volatilities and volumes.
    """

    # Realistic starting prices and daily volatilities
    DEFAULT_TICKERS = {
        "AAPL": {"price": 175.50, "vol": 0.018, "sector": "Technology"},
        "MSFT": {"price": 420.30, "vol": 0.016, "sector": "Technology"},
        "GOOGL": {"price": 139.80, "vol": 0.020, "sector": "Technology"},
        "TSLA": {"price": 195.75, "vol": 0.035, "sector": "Technology"},
        "JPM": {"price": 195.40, "vol": 0.015, "sector": "Finance"},
        "BAC": {"price": 32.10, "vol": 0.018, "sector": "Finance"},
        "GE": {"price": 98.50, "vol": 0.022, "sector": "Industrials"},
        "XOM": {"price": 112.35, "vol": 0.020, "sector": "Energy"},
        "JNJ": {"price": 160.80, "vol": 0.014, "sector": "Healthcare"},
        "PG": {"price": 165.20, "vol": 0.012, "sector": "Consumer"},
        "SPY": {"price": 445.80, "vol": 0.016, "sector": "Index"},
        "BND": {"price": 73.45, "vol": 0.008, "sector": "Fixed Income"},
        "GLD": {"price": 185.30, "vol": 0.013, "sector": "Commodity"},
    }

    def __init__(
        self,
        seed: int = 42,
        tickers: Optional[List[str]] = None,
        config: Optional[Dict] = None
    ):
        """
        Initialize market data simulator.

        Args:
            seed: Random seed for reproducibility
            tickers: List of ticker symbols to simulate (default: all DEFAULT_TICKERS)
            config: Optional configuration dict with custom prices/volatilities
        """
        np.random.seed(seed)

        self.current_time = datetime.now()
        self.seed = seed

        # Initialize ticker data
        if tickers:
            self.tickers = {t: self.DEFAULT_TICKERS[t] for t in tickers if t in self.DEFAULT_TICKERS}
        else:
            self.tickers = self.DEFAULT_TICKERS.copy()

        # Apply custom config if provided
        if config:
            for ticker, params in config.items():
                if ticker in self.tickers:
                    self.tickers[ticker].update(params)

        # Store current prices
        self.current_prices = {t: data["price"] for t, data in self.tickers.items()}

        # Store OHLC values
        self.ohlc_data = {t: {"open": data["price"], "high": data["price"], "low": data["price"]} for t, data in self.tickers.items()}

        # Volume tracking
        self.volume_data = {t: 0.0 for t in self.tickers.keys()}

        # Trade counter
        self.trade_counter = 0

    def generate_tick(self, ticker: str) -> MarketTick:
        """
        Generate a single market tick using Geometric Brownian Motion.

        Args:
            ticker: Ticker symbol

        Returns:
            MarketTick with updated prices
        """
        if ticker not in self.tickers:
            raise ValueError(f"Unknown ticker: {ticker}")

        config = self.tickers[ticker]
        current_price = self.current_prices[ticker]
        vol = config["vol"]

        # GBM: dS = μ*S*dt + σ*S*dW
        # Using daily dt and annual vol
        dt = 1.0 / 252.0  # One trading day
        mu = 0.05  # Drift (annual return)

        dW = np.random.normal(0, np.sqrt(dt))
        price_change = mu * current_price * dt + vol * current_price * dW

        new_price = current_price + price_change
        new_price = max(new_price, current_price * 0.9)  # Prevent huge drops

        # Update OHLC
        ohlc = self.ohlc_data[ticker]
        ohlc["open"] = current_price
        ohlc["high"] = max(ohlc.get("high", new_price), new_price)
        ohlc["low"] = min(ohlc.get("low", new_price), new_price)

        # Generate volume (lognormal distribution)
        base_volume = 1e6  # 1M shares base
        volume = base_volume * np.exp(np.random.normal(0, 0.5))

        # Generate bid/ask spread (wider for volatile stocks)
        spread_bps = max(1, vol * 10000)  # basis points
        spread = new_price * spread_bps / 10000

        bid_price = new_price - spread / 2
        ask_price = new_price + spread / 2

        self.current_prices[ticker] = new_price
        self.volume_data[ticker] = volume

        return MarketTick(
            ticker=ticker,
            bid=bid_price,
            ask=ask_price,
            last=new_price,
            volume=volume,
            timestamp=self.current_time,
            open=ohlc["open"],
            high=ohlc["high"],
            low=ohlc["low"],
            close=new_price,
        )

    def generate_orderbook(
        self,
        ticker: str,
        depth: int = 10
    ) -> OrderBook:
        """
        Generate order book snapshot at current market prices.

        Args:
            ticker: Ticker symbol
            depth: Number of levels on each side

        Returns:
            OrderBook with realistic bid/ask levels
        """
        if ticker not in self.tickers:
            raise ValueError(f"Unknown ticker: {ticker}")

        current_price = self.current_prices[ticker]
        config = self.tickers[ticker]
        vol = config["vol"]

        # Spread based on volatility
        spread_bps = max(1, vol * 10000)
        spread = current_price * spread_bps / 10000
        tick_size = spread / depth

        # Generate bids (descending)
        bids = []
        for i in range(depth):
            price = current_price - (i + 1) * tick_size
            # Volume decreases at wider prices
            size = 10000 * np.exp(-i * 0.3)
            bids.append((max(price, 0.01), size))

        # Generate asks (ascending)
        asks = []
        for i in range(depth):
            price = current_price + (i + 1) * tick_size
            size = 10000 * np.exp(-i * 0.3)
            asks.append((price, size))

        return OrderBook(
            ticker=ticker,
            bids=bids,
            asks=asks,
            timestamp=self.current_time,
        )

    def generate_daily_ohlcv(
        self,
        ticker: str,
        num_days: int = 252
    ) -> List[MarketTick]:
        """
        Generate historical daily OHLCV data.

        Args:
            ticker: Ticker symbol
            num_days: Number of trading days to generate

        Returns:
            List of MarketTick objects with daily OHLCV
        """
        if ticker not in self.tickers:
            raise ValueError(f"Unknown ticker: {ticker}")

        config = self.tickers[ticker]
        price = config["price"]
        vol = config["vol"]

        ticks = []
        start_time = self.current_time - timedelta(days=num_days)

        for day in range(num_days):
            timestamp = start_time + timedelta(days=day)

            # Generate daily return
            daily_return = np.random.normal(0.05 / 252, vol / np.sqrt(252))

            # OHLC values
            open_price = price
            close_price = price * (1 + daily_return)
            high_price = max(open_price, close_price) * (1 + abs(np.random.normal(0, vol / np.sqrt(252))))
            low_price = min(open_price, close_price) * (1 - abs(np.random.normal(0, vol / np.sqrt(252))))

            # Volume
            volume = 1e6 * np.exp(np.random.normal(0, 0.3))

            # Bid/ask
            spread = close_price * vol * 0.5 / 100
            bid = close_price - spread / 2
            ask = close_price + spread / 2

            tick = MarketTick(
                ticker=ticker,
                bid=bid,
                ask=ask,
                last=close_price,
                volume=volume,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
            )
            ticks.append(tick)

            price = close_price

        return ticks

    def generate_trade_history(
        self,
        portfolio: Portfolio,
        num_trades: int = 100,
        start_time: Optional[datetime] = None
    ) -> List[Trade]:
        """
        Generate realistic trade history for a portfolio.

        Args:
            portfolio: Portfolio to generate trades for
            num_trades: Number of trades to generate
            start_time: Start time for trades (default: current_time - 30 days)

        Returns:
            List of Trade objects
        """
        if start_time is None:
            start_time = self.current_time - timedelta(days=30)

        trades = []
        current_time_sim = start_time

        for _ in range(num_trades):
            # Random ticker from portfolio
            if portfolio.positions:
                position = np.random.choice(portfolio.positions)
                ticker = position.ticker
            else:
                ticker = np.random.choice(list(self.tickers.keys()))

            # Random side
            side = np.random.choice([OrderSide.BUY, OrderSide.SELL])

            # Random quantity
            quantity = np.random.randint(100, 5000)

            # Current price + small random slippage
            price = self.current_prices.get(ticker, self.tickers[ticker]["price"])
            slippage = price * np.random.normal(0, 0.001)  # 0-1 bps slippage
            execution_price = price + slippage

            # Realistic latency (0.5 - 50ms)
            latency_ms = np.random.lognormal(1.5, 1.2)  # log-normal distribution

            # Realized PnL (for demonstration)
            pnl = quantity * slippage * (1 if side == OrderSide.BUY else -1)

            trade = Trade(
                trade_id=f"TRADE_{self.trade_counter:06d}",
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=execution_price,
                timestamp=current_time_sim,
                order_type=np.random.choice([OrderType.MARKET, OrderType.LIMIT]),
                venue=np.random.choice(["NYSE", "NASDAQ", "ARCA"]),
                status=OrderStatus.FILLED,
                execution_latency_ms=latency_ms,
                slippage=slippage,
                realized_pnl=pnl,
            )
            trades.append(trade)

            self.trade_counter += 1

            # Advance time randomly (5 seconds to 5 minutes between trades)
            time_advance = np.random.uniform(5, 300)
            current_time_sim += timedelta(seconds=time_advance)

        return trades

    def advance_time(self, minutes: float = 1.0) -> None:
        """
        Advance simulation time forward.

        Args:
            minutes: Number of minutes to advance
        """
        self.current_time += timedelta(minutes=minutes)

    def get_current_prices(self) -> Dict[str, float]:
        """Get current prices for all tickers."""
        return self.current_prices.copy()

    def get_price(self, ticker: str) -> float:
        """Get current price for a ticker."""
        if ticker not in self.current_prices:
            raise ValueError(f"Unknown ticker: {ticker}")
        return self.current_prices[ticker]

    def generate_returns(
        self,
        ticker: str,
        num_periods: int = 252
    ) -> np.ndarray:
        """
        Generate daily returns for a ticker.

        Args:
            ticker: Ticker symbol
            num_periods: Number of daily periods

        Returns:
            Array of log returns
        """
        if ticker not in self.tickers:
            raise ValueError(f"Unknown ticker: {ticker}")

        config = self.tickers[ticker]
        vol = config["vol"]

        # Generate returns from normal distribution
        returns = np.random.normal(0.05 / 252, vol / np.sqrt(252), num_periods)

        return returns

    def generate_correlated_returns(
        self,
        tickers: List[str],
        num_periods: int = 252,
        correlation_matrix: Optional[np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """
        Generate correlated returns for multiple tickers.

        Args:
            tickers: List of ticker symbols
            num_periods: Number of periods
            correlation_matrix: Custom correlation matrix (default: computed from tickers)

        Returns:
            Dictionary mapping ticker -> returns array
        """
        n = len(tickers)

        # Use provided correlation matrix or create default
        if correlation_matrix is None:
            # Default: higher correlation within sectors, lower across
            correlation_matrix = np.eye(n)
            for i in range(n):
                for j in range(i + 1, n):
                    # Check if same sector
                    sector_i = self.tickers[tickers[i]].get("sector", "")
                    sector_j = self.tickers[tickers[j]].get("sector", "")

                    if sector_i == sector_j:
                        corr = 0.7 + 0.2 * np.random.random()
                    else:
                        corr = 0.2 + 0.3 * np.random.random()

                    correlation_matrix[i, j] = corr
                    correlation_matrix[j, i] = corr

        # Generate correlated normal random variables
        uncorrelated = np.random.normal(0, 1, (n, num_periods))

        # Apply Cholesky decomposition for correlation
        L = np.linalg.cholesky(correlation_matrix)
        correlated = L @ uncorrelated

        # Scale by volatilities
        returns_dict = {}
        for i, ticker in enumerate(tickers):
            vol = self.tickers[ticker]["vol"]
            returns_dict[ticker] = correlated[i] * vol / np.sqrt(252)

        return returns_dict

    def reset(self, seed: Optional[int] = None) -> None:
        """
        Reset simulator to initial state.

        Args:
            seed: New random seed (optional)
        """
        if seed is not None:
            self.seed = seed
            np.random.seed(seed)

        self.current_time = datetime.now()
        self.current_prices = {t: data["price"] for t, data in self.tickers.items()}
        self.ohlc_data = {t: {"open": data["price"], "high": data["price"], "low": data["price"]} for t, data in self.tickers.items()}
        self.volume_data = {t: 0.0 for t in self.tickers.keys()}
        self.trade_counter = 0
