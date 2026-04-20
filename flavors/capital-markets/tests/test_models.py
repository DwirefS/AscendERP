"""
Tests for Capital Markets mathematical models.
Covers VaR, Black-Scholes pricing, Greeks, portfolio optimization, and risk metrics.
"""
import pytest
import numpy as np
from scipy import stats

from flavors.capital_markets.models.risk_models import (
    VaRCalculator, sharpe_ratio, sortino_ratio, max_drawdown,
    herfindahl_concentration, beta_calculation, tracking_error,
    StressTester, RiskAnalyzer
)
from flavors.capital_markets.models.pricing import (
    BlackScholesModel, BinomialModel, OptionPricingUtils
)
from flavors.capital_markets.models.portfolio_optimization import (
    ModernPortfolioTheory, OptimizedPortfolio, risk_parity_weights,
    equal_weight, calculate_portfolio_metrics
)
from flavors.capital_markets.models.market_data import Portfolio, Position, AssetClass


class TestVaRCalculator:
    """Test Value at Risk calculations."""

    @pytest.mark.unit
    @pytest.mark.models
    def test_historical_var_calculation(self, sample_returns):
        """Test historical simulation VaR calculation."""
        var_95 = VaRCalculator.historical_simulation(sample_returns, confidence=0.95)

        # VaR should be positive and reasonable for daily returns
        assert var_95 >= 0
        assert var_95 < 0.10  # Less than 10% daily loss

    @pytest.mark.unit
    @pytest.mark.models
    def test_parametric_var_calculation(self, sample_returns):
        """Test parametric (normal) VaR calculation."""
        var_95 = VaRCalculator.parametric_var(sample_returns, confidence=0.95)
        var_99 = VaRCalculator.parametric_var(sample_returns, confidence=0.99)

        # VaR at 99% should be higher than at 95%
        assert var_99 > var_95
        assert var_95 > 0
        assert var_99 > 0

    @pytest.mark.unit
    @pytest.mark.models
    def test_conditional_var_calculation(self, sample_returns):
        """Test Conditional VaR (Expected Shortfall)."""
        cvar = VaRCalculator.conditional_var(sample_returns, confidence=0.95)

        # CVaR should be greater than or equal to VaR
        var = VaRCalculator.historical_simulation(sample_returns, confidence=0.95)
        assert cvar >= var
        assert cvar > 0

    @pytest.mark.unit
    @pytest.mark.models
    def test_var_insufficient_data(self):
        """Test VaR with insufficient data raises error."""
        small_returns = np.array([0.01])
        with pytest.raises(ValueError):
            VaRCalculator.historical_simulation(small_returns)

    @pytest.mark.unit
    @pytest.mark.models
    def test_var_scaling_with_horizon(self, sample_returns):
        """Test VaR scaling with different time horizons."""
        var_1day = VaRCalculator.historical_simulation(
            sample_returns, confidence=0.95, horizon_days=1
        )
        var_10day = VaRCalculator.historical_simulation(
            sample_returns, confidence=0.95, horizon_days=10
        )

        # 10-day VaR should be higher than 1-day (scales by sqrt(horizon))
        expected_ratio = np.sqrt(10)
        assert var_10day / var_1day == pytest.approx(expected_ratio, rel=0.01)


class TestBlackScholesModel:
    """Test Black-Scholes option pricing model."""

    @pytest.mark.unit
    @pytest.mark.models
    def test_call_pricing_known_value(self):
        """Test call option pricing against known value.

        S=100, K=100, T=1, r=0.05, sigma=0.2 should give ~10.45
        """
        price = BlackScholesModel.call_price(
            S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.2
        )

        # Known value from Black-Scholes tables
        assert price == pytest.approx(10.45, rel=0.01)

    @pytest.mark.unit
    @pytest.mark.models
    def test_put_pricing_known_value(self):
        """Test put option pricing against known value."""
        price = BlackScholesModel.put_price(
            S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.2
        )

        # Put price for ATM option with these params
        assert price == pytest.approx(5.57, rel=0.01)

    @pytest.mark.unit
    @pytest.mark.models
    def test_put_call_parity(self):
        """Test put-call parity relationship."""
        S, K, T, r = 100.0, 100.0, 1.0, 0.05
        sigma = 0.2

        call_price = BlackScholesModel.call_price(S, K, T, r, sigma)
        put_price = BlackScholesModel.put_price(S, K, T, r, sigma)

        # C - P = S - K*e^(-rT)
        parity_deviation = OptionPricingUtils.put_call_parity_check(
            call_price, put_price, S, K, r, T
        )

        assert parity_deviation < 0.01  # Should be very close to 0

    @pytest.mark.unit
    @pytest.mark.models
    def test_delta_call_bounds(self):
        """Test call option delta bounds [0, 1]."""
        deltas = []
        for S in [50, 100, 150]:
            delta = BlackScholesModel.delta(S, 100, 1.0, 0.05, 0.2, "call")
            deltas.append(delta)
            assert 0 <= delta <= 1

        # Delta should increase with stock price
        assert deltas[0] < deltas[1] < deltas[2]

    @pytest.mark.unit
    @pytest.mark.models
    def test_delta_put_bounds(self):
        """Test put option delta bounds [-1, 0]."""
        deltas = []
        for S in [50, 100, 150]:
            delta = BlackScholesModel.delta(S, 100, 1.0, 0.05, 0.2, "put")
            deltas.append(delta)
            assert -1 <= delta <= 0

        # Delta should increase with stock price (become less negative)
        assert deltas[0] < deltas[1] < deltas[2]

    @pytest.mark.unit
    @pytest.mark.models
    def test_all_greeks_calculation(self):
        """Test calculation of all Greeks."""
        greeks = BlackScholesModel.all_greeks(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2
        )

        assert greeks.delta > 0
        assert greeks.gamma > 0
        assert greeks.vega > 0
        assert greeks.theta < 0  # Time decay is negative
        assert greeks.rho > 0  # For call

    @pytest.mark.unit
    @pytest.mark.models
    def test_implied_volatility_recovery(self):
        """Test that IV recovers original volatility."""
        S, K, T, r = 100.0, 100.0, 1.0, 0.05
        original_sigma = 0.25

        market_price = BlackScholesModel.call_price(S, K, T, r, original_sigma)
        recovered_sigma = BlackScholesModel.implied_volatility(
            market_price, S, K, T, r, "call"
        )

        assert recovered_sigma == pytest.approx(original_sigma, rel=0.01)


class TestBinomialModel:
    """Test binomial tree option pricing."""

    @pytest.mark.unit
    @pytest.mark.models
    def test_american_call_greater_than_european(self):
        """American options should be >= European (early exercise value)."""
        american = BinomialModel.price_american_option(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call"
        )
        european = BinomialModel.price_european_option(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="call"
        )

        # For calls on non-dividend stocks, should be equal, but within tolerance
        assert american >= european - 0.01

    @pytest.mark.unit
    @pytest.mark.models
    def test_american_put_greater_than_european(self):
        """American puts should be >= European (early exercise for puts)."""
        american = BinomialModel.price_american_option(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="put"
        )
        european = BinomialModel.price_european_option(
            S=100, K=100, T=1.0, r=0.05, sigma=0.2, option_type="put"
        )

        # American puts have early exercise premium
        assert american >= european

    @pytest.mark.unit
    @pytest.mark.models
    def test_binomial_convergence_to_bs(self):
        """Binomial should converge to Black-Scholes with more steps."""
        S, K, T, r, sigma = 100.0, 100.0, 1.0, 0.05, 0.2

        bs_price = BlackScholesModel.call_price(S, K, T, r, sigma)

        binomial_50 = BinomialModel.price_european_option(
            S, K, T, r, sigma, steps=50, option_type="call"
        )
        binomial_200 = BinomialModel.price_european_option(
            S, K, T, r, sigma, steps=200, option_type="call"
        )

        # Higher step count should be closer to BS
        error_50 = abs(binomial_50 - bs_price)
        error_200 = abs(binomial_200 - bs_price)

        assert error_200 < error_50


class TestRiskMetrics:
    """Test risk calculation functions."""

    @pytest.mark.unit
    @pytest.mark.models
    def test_sharpe_ratio_calculation(self, sample_returns):
        """Test Sharpe ratio calculation."""
        sharpe = sharpe_ratio(sample_returns, risk_free_rate=0.05)

        # Sharpe ratio should be positive for positive excess returns
        assert sharpe > 0
        assert sharpe < 5  # Reasonable upper bound

    @pytest.mark.unit
    @pytest.mark.models
    def test_sharpe_ratio_zero_volatility(self):
        """Test Sharpe ratio with zero volatility."""
        returns = np.array([0.01, 0.01, 0.01])
        sharpe = sharpe_ratio(returns)

        # Zero volatility should give 0 sharpe
        assert sharpe == 0

    @pytest.mark.unit
    @pytest.mark.models
    def test_sortino_ratio_greater_than_sharpe(self, sample_returns):
        """Sortino ratio should generally be higher than Sharpe for normal distributions."""
        sharpe = sharpe_ratio(sample_returns)
        sortino = sortino_ratio(sample_returns)

        # Sortino focuses on downside, should be higher
        assert sortino >= sharpe

    @pytest.mark.unit
    @pytest.mark.models
    def test_max_drawdown_calculation(self):
        """Test maximum drawdown calculation."""
        # Simple returns: up 10%, down 20%, up 15%
        returns = np.array([0.10, -0.20, 0.15])

        drawdown, peak_idx, trough_idx = max_drawdown(returns)

        # With cumulative: [1.1, 0.88, 1.012]
        # Peak at 0 (1.1), trough at 1 (0.88)
        # Drawdown = (0.88 - 1.1) / 1.1 = -0.109
        assert drawdown == pytest.approx(0.109, rel=0.01)
        assert peak_idx < trough_idx

    @pytest.mark.unit
    @pytest.mark.models
    def test_herfindahl_concentration(self):
        """Test Herfindahl concentration index."""
        # Equal weights: HHI = 1/n
        equal = np.array([0.25, 0.25, 0.25, 0.25])
        hhi_equal = herfindahl_concentration(equal)
        assert hhi_equal == pytest.approx(0.25, rel=0.01)

        # Concentrated: one asset 100%
        concentrated = np.array([1.0, 0.0, 0.0, 0.0])
        hhi_concentrated = herfindahl_concentration(concentrated)
        assert hhi_concentrated == pytest.approx(1.0, rel=0.01)

    @pytest.mark.unit
    @pytest.mark.models
    def test_beta_calculation(self, sample_returns):
        """Test beta calculation."""
        market_returns = np.random.normal(0.0005, 0.015, len(sample_returns))
        beta = beta_calculation(sample_returns, market_returns)

        # Beta should be a reasonable value
        assert -2 < beta < 3

    @pytest.mark.unit
    @pytest.mark.models
    def test_tracking_error(self, sample_returns):
        """Test tracking error calculation."""
        benchmark = sample_returns + np.random.normal(0, 0.005, len(sample_returns))

        te = tracking_error(sample_returns, benchmark)

        # Tracking error should be positive
        assert te >= 0
        assert te < 0.5  # Reasonable upper bound


class TestPortfolioOptimization:
    """Test Modern Portfolio Theory optimization."""

    @pytest.mark.unit
    @pytest.mark.models
    def test_efficient_frontier_generation(
        self, sample_expected_returns, sample_cov_matrix
    ):
        """Test efficient frontier generation."""
        frontier = ModernPortfolioTheory.efficient_frontier(
            sample_expected_returns, sample_cov_matrix, num_portfolios=100
        )

        # Should have 100 portfolios
        assert len(frontier) == 100

        # Each portfolio should have valid properties
        for portfolio in frontier:
            assert "return" in portfolio
            assert "risk" in portfolio
            assert "weights" in portfolio
            assert "sharpe" in portfolio
            assert portfolio["risk"] >= 0
            assert len(portfolio["weights"]) == len(sample_expected_returns)
            assert abs(sum(portfolio["weights"]) - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.models
    def test_min_variance_portfolio(
        self, sample_expected_returns, sample_cov_matrix
    ):
        """Test minimum variance portfolio optimization."""
        opt_port = ModernPortfolioTheory.min_variance_portfolio(
            sample_expected_returns, sample_cov_matrix
        )

        assert isinstance(opt_port, OptimizedPortfolio)
        assert opt_port.volatility > 0
        assert abs(sum(opt_port.weights) - 1.0) < 0.01
        assert all(w >= 0 for w in opt_port.weights)

    @pytest.mark.unit
    @pytest.mark.models
    def test_max_sharpe_portfolio(
        self, sample_expected_returns, sample_cov_matrix
    ):
        """Test maximum Sharpe ratio portfolio."""
        opt_port = ModernPortfolioTheory.max_sharpe_portfolio(
            sample_expected_returns, sample_cov_matrix, risk_free_rate=0.05
        )

        assert isinstance(opt_port, OptimizedPortfolio)
        assert opt_port.sharpe_ratio > 0
        assert abs(sum(opt_port.weights) - 1.0) < 0.01

    @pytest.mark.unit
    @pytest.mark.models
    def test_target_return_portfolio(
        self, sample_expected_returns, sample_cov_matrix
    ):
        """Test target return portfolio optimization."""
        target_return = 0.07  # 7% target

        opt_port = ModernPortfolioTheory.target_return_portfolio(
            sample_expected_returns, sample_cov_matrix, target_return=target_return
        )

        assert isinstance(opt_port, OptimizedPortfolio)
        assert opt_port.expected_return == pytest.approx(target_return, rel=0.01)

    @pytest.mark.unit
    @pytest.mark.models
    def test_risk_parity_weights(self, sample_cov_matrix):
        """Test risk parity weight calculation."""
        weights = risk_parity_weights(sample_cov_matrix)

        # Weights should sum to 1
        assert abs(sum(weights) - 1.0) < 0.01

        # All weights should be positive (long only)
        assert all(w > 0 for w in weights)

        # Risk parity: inverse volatility weighted
        vols = np.sqrt(np.diag(sample_cov_matrix))
        inv_vols = 1.0 / vols
        inv_vols /= sum(inv_vols)

        np.testing.assert_array_almost_equal(weights, inv_vols)

    @pytest.mark.unit
    @pytest.mark.models
    def test_equal_weight_portfolio(self):
        """Test equal weight portfolio construction."""
        n_assets = 5
        weights = equal_weight(n_assets)

        assert len(weights) == n_assets
        assert abs(sum(weights) - 1.0) < 0.01
        assert all(w == pytest.approx(1.0 / n_assets) for w in weights)

    @pytest.mark.unit
    @pytest.mark.models
    def test_portfolio_metrics_calculation(
        self, sample_expected_returns, sample_cov_matrix
    ):
        """Test portfolio metrics calculation."""
        weights = np.array([0.4, 0.35, 0.25])

        metrics = calculate_portfolio_metrics(
            weights, sample_expected_returns, sample_cov_matrix
        )

        assert "return" in metrics
        assert "volatility" in metrics
        assert "variance" in metrics
        assert "sharpe_ratio" in metrics

        assert metrics["return"] > 0
        assert metrics["volatility"] > 0
        assert metrics["sharpe_ratio"] > 0


class TestStressScenarios:
    """Test portfolio stress testing."""

    @pytest.mark.unit
    @pytest.mark.models
    def test_stress_scenario_application(self, sample_portfolio):
        """Test applying stress scenario to portfolio."""
        result = StressTester.apply_scenario(sample_portfolio, "2008_gfc")

        assert result.scenario_name == "2008_gfc"
        assert result.portfolio_impact < 0  # GFC should have negative impact
        assert result.max_loss < 0
        assert len(result.returns) == len(sample_portfolio.positions)

    @pytest.mark.unit
    @pytest.mark.models
    def test_custom_scenario(self, sample_portfolio):
        """Test applying custom stress scenario."""
        shocks = {
            "AAPL": -0.10,  # 10% loss
            "MSFT": -0.05,  # 5% loss
            "BND": 0.02,    # 2% gain
        }

        result = StressTester.apply_custom_scenario(sample_portfolio, shocks)

        assert result.scenario_name == "custom"
        assert result.portfolio_impact < 0

    @pytest.mark.unit
    @pytest.mark.models
    def test_monte_carlo_simulation(self, sample_portfolio, sample_returns):
        """Test Monte Carlo simulation."""
        mc_results = StressTester.monte_carlo_simulation(
            sample_portfolio, sample_returns, num_simulations=1000, time_horizon_days=1
        )

        assert "mean" in mc_results
        assert "median" in mc_results
        assert "std" in mc_results
        assert "var_95" in mc_results
        assert "var_99" in mc_results

        # VaR should be reasonable
        assert 0 < mc_results["var_95"] < sample_portfolio.total_market_value
        assert mc_results["var_99"] < mc_results["var_95"]


class TestRiskAnalyzer:
    """Test comprehensive risk analysis."""

    @pytest.mark.unit
    @pytest.mark.models
    def test_portfolio_risk_calculation(self, sample_portfolio, sample_returns):
        """Test comprehensive portfolio risk metrics."""
        market_returns = np.random.normal(0.0005, 0.015, len(sample_returns))

        metrics = RiskAnalyzer.calculate_portfolio_risk(
            sample_portfolio, sample_returns, market_returns
        )

        assert metrics.var_95 > 0
        assert metrics.var_99 > metrics.var_95
        assert metrics.sharpe_ratio != 0
        assert metrics.max_drawdown >= 0
        assert metrics.beta > 0
        assert 0 <= metrics.herfindahl_index <= 1
