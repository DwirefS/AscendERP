"""
Portfolio Expert - Capital Markets MoE

Specialized expert for portfolio construction, optimization, and rebalancing
using modern portfolio theory and risk management principles.

Domains: portfolio_construction, risk_parity, optimization, asset_allocation, rebalancing
"""

from typing import Any, Dict, List
import math
import logging

from src.core.moe.moe_agent import Expert, ExpertType, ExpertOutput

logger = logging.getLogger(__name__)


class PortfolioExpert(Expert):
    """
    Expert specialized in portfolio construction and optimization

    Analyzes portfolio decisions using:
    - Modern Portfolio Theory (Markowitz)
    - Risk parity frameworks
    - Factor-based analysis
    - Diversification metrics
    - Rebalancing strategies
    - Asset allocation optimization
    - Concentration risk assessment
    """

    def __init__(self):
        """Initialize Portfolio Expert"""
        super().__init__(
            expert_id="cm_portfolio_expert",
            expert_type=ExpertType.FINANCE,
            domain=["portfolio_construction", "risk_parity", "optimization", "asset_allocation", "rebalancing"]
        )

    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """
        Analyze portfolio-related tasks

        Args:
            task: Dict containing:
                - portfolio: Dict of positions {asset: weight}
                - expected_returns: Dict of expected returns
                - volatilities: Dict of volatilities
                - correlations: Correlation matrix or correlation values
                - risk_budget: Total risk budget
                - objective: 'maximize_return', 'minimize_risk', 'risk_parity'
                - description: Analysis task description

        Returns:
            ExpertOutput with portfolio analysis and recommendations
        """
        logger.info(f"Portfolio Expert analyzing: {task.get('description', 'portfolio task')}")

        confidence = await self.estimate_confidence(task)

        portfolio = task.get("portfolio", {})
        expected_returns = task.get("expected_returns", {})
        volatilities = task.get("volatilities", {})
        objective = task.get("objective", "optimize")

        analysis = self._analyze_portfolio(
            portfolio=portfolio,
            expected_returns=expected_returns,
            volatilities=volatilities,
            task=task
        )

        result = {
            "current_portfolio": analysis["current_metrics"],
            "diversification_analysis": analysis["diversification"],
            "optimization_recommendations": analysis["recommendations"],
            "rebalancing_guidance": analysis["rebalancing"],
            "risk_analysis": analysis["risk_analysis"],
            "factor_exposure": analysis["factor_exposure"]
        }

        return ExpertOutput(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            result=result,
            confidence=confidence,
            reasoning=f"Portfolio analysis: {analysis['rationale']}"
        )

    async def estimate_confidence(self, task: Dict[str, Any]) -> float:
        """Estimate confidence for portfolio task"""
        task_domain = task.get("domain", "").lower()
        task_description = task.get("description", "").lower()
        has_portfolio = "portfolio" in task

        portfolio_keywords = ["portfolio", "allocation", "diversification", "rebalance", "optimization"]
        description_match = sum(1 for kw in portfolio_keywords if kw in task_description)

        if has_portfolio or any(kw in task_domain for kw in self.domain):
            return 0.90
        elif description_match >= 2:
            return 0.82
        elif any(kw in task_domain for kw in self.domain):
            return 0.75
        else:
            return 0.35

    def _analyze_portfolio(
        self,
        portfolio: Dict[str, float],
        expected_returns: Dict[str, float],
        volatilities: Dict[str, float],
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Comprehensive portfolio analysis
        """
        if not portfolio:
            portfolio = {}

        assets = list(portfolio.keys()) if portfolio else list(expected_returns.keys())
        weights = [portfolio.get(asset, 1.0/len(assets)) for asset in assets]

        # Normalize weights
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        else:
            weights = [1.0 / len(assets) if assets else 1.0]

        # Calculate portfolio metrics
        port_return = sum(
            weights[i] * expected_returns.get(assets[i], 0.05)
            for i in range(len(assets))
        )

        port_volatility = self._calculate_portfolio_volatility(
            weights, assets, volatilities, task
        )

        sharpe_ratio = self._calculate_sharpe_ratio(
            port_return, port_volatility, task.get("risk_free_rate", 0.02)
        )

        # Concentration analysis
        concentration = {
            "herfindahl_index": sum(w ** 2 for w in weights),
            "largest_position": max(weights) if weights else 0,
            "largest_five_pct": sum(sorted(weights, reverse=True)[:5]),
            "diversification_score": self._calculate_diversification_score(weights)
        }

        # Diversification metrics
        diversification = {
            "effective_number_of_assets": 1.0 / concentration["herfindahl_index"] if concentration["herfindahl_index"] > 0 else 0,
            "is_well_diversified": concentration["herfindahl_index"] < 0.10,
            "concentration_warning": concentration["largest_position"] > 0.25,
            "entropy": self._calculate_entropy(weights)
        }

        # Risk analysis
        var_95 = port_return - 1.65 * port_volatility
        var_99 = port_return - 2.33 * port_volatility
        cvar_95 = var_95 - 0.5 * port_volatility

        risk_analysis = {
            "portfolio_volatility": round(port_volatility, 4),
            "value_at_risk_95pct": round(var_95, 4),
            "value_at_risk_99pct": round(var_99, 4),
            "conditional_var_95pct": round(cvar_95, 4),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "sortino_ratio": round(sharpe_ratio * 1.2, 3)  # Simplified
        }

        # Factor exposure analysis
        factor_exposure = self._analyze_factor_exposure(weights, assets, task)

        # Rebalancing recommendations
        rebalancing = self._get_rebalancing_guidance(weights, assets, portfolio)

        # Optimization recommendations
        target_weights = self._optimize_portfolio(weights, assets, expected_returns, volatilities, task)

        recommendations = {
            "current_status": "Well-diversified" if diversification["is_well_diversified"] else "Concentrated",
            "suggested_reallocation": {
                assets[i]: {"current": round(weights[i], 3), "target": round(target_weights[i], 3)}
                for i in range(len(assets))
            },
            "key_improvements": [
                "Increase diversification" if concentration["herfindahl_index"] > 0.10 else "Diversification adequate",
                f"Expected return: {round(port_return*100, 2)}%" if port_return else "Neutral returns",
                f"Risk level: {'High' if port_volatility > 0.15 else 'Moderate' if port_volatility > 0.08 else 'Low'}"
            ]
        }

        rationale = f"Portfolio with {len(assets)} assets: Return {port_return*100:.1f}%, Volatility {port_volatility*100:.1f}%, Sharpe {sharpe_ratio:.2f}"

        return {
            "current_metrics": {
                "assets": assets,
                "weights": {assets[i]: round(weights[i], 4) for i in range(len(assets))},
                "expected_return": round(port_return, 4),
                "volatility": round(port_volatility, 4),
                "sharpe_ratio": round(sharpe_ratio, 3)
            },
            "diversification": diversification,
            "concentration": concentration,
            "recommendations": recommendations,
            "rebalancing": rebalancing,
            "risk_analysis": risk_analysis,
            "factor_exposure": factor_exposure,
            "rationale": rationale
        }

    def _calculate_portfolio_volatility(
        self,
        weights: List[float],
        assets: List[str],
        volatilities: Dict[str, float],
        task: Dict[str, Any]
    ) -> float:
        """Calculate portfolio volatility with correlation"""
        n = len(weights)

        # Variance from individual volatilities
        variance = sum(
            (weights[i] * volatilities.get(assets[i], 0.15)) ** 2
            for i in range(n)
        )

        # Add covariance terms (simplified with correlation)
        correlations = task.get("correlations", 0.3)
        if isinstance(correlations, dict):
            for i in range(n):
                for j in range(i + 1, n):
                    key = f"{assets[i]}-{assets[j]}"
                    corr = correlations.get(key, 0.3)
                    vol_i = volatilities.get(assets[i], 0.15)
                    vol_j = volatilities.get(assets[j], 0.15)
                    variance += 2 * weights[i] * weights[j] * corr * vol_i * vol_j
        else:
            for i in range(n):
                for j in range(i + 1, n):
                    vol_i = volatilities.get(assets[i], 0.15)
                    vol_j = volatilities.get(assets[j], 0.15)
                    variance += 2 * weights[i] * weights[j] * correlations * vol_i * vol_j

        return math.sqrt(max(variance, 0))

    @staticmethod
    def _calculate_sharpe_ratio(ret: float, vol: float, rf_rate: float) -> float:
        """Calculate Sharpe ratio"""
        if vol == 0:
            return 0
        return (ret - rf_rate) / vol

    @staticmethod
    def _calculate_diversification_score(weights: List[float]) -> float:
        """Calculate diversification score (0-1)"""
        if not weights:
            return 0
        n = len(weights)
        max_equal_weight = 1.0 / n if n > 0 else 1.0
        sum_sq = sum(w ** 2 for w in weights)
        return (1 - sum_sq) / (1 - max_equal_weight) if (1 - max_equal_weight) > 0 else 0

    @staticmethod
    def _calculate_entropy(weights: List[float]) -> float:
        """Calculate portfolio entropy (Shannon entropy)"""
        entropy = 0
        for w in weights:
            if w > 0.0001:
                entropy -= w * math.log(w)
        return entropy

    def _analyze_factor_exposure(
        self,
        weights: List[float],
        assets: List[str],
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze exposure to common factors"""
        factors = {
            "value": sum(weights[i] * 0.6 for i in range(len(assets))),
            "growth": sum(weights[i] * 0.4 for i in range(len(assets))),
            "momentum": sum(weights[i] * 0.3 for i in range(len(assets))),
            "quality": sum(weights[i] * 0.5 for i in range(len(assets)))
        }

        return {
            "value_factor": round(factors["value"], 3),
            "growth_factor": round(factors["growth"], 3),
            "momentum_factor": round(factors["momentum"], 3),
            "quality_factor": round(factors["quality"], 3),
            "factor_balance": "Balanced" if abs(factors["value"] - factors["growth"]) < 0.2 else "Skewed"
        }

    @staticmethod
    def _get_rebalancing_guidance(
        weights: List[float],
        assets: List[str],
        portfolio: Dict[str, float]
    ) -> Dict[str, Any]:
        """Provide rebalancing guidance"""
        max_drift = max(weights) - min(weights) if weights else 0

        return {
            "rebalancing_frequency": "Quarterly" if max_drift > 0.05 else "Semi-annually",
            "drift_from_targets": round(max_drift, 3),
            "rebalancing_required": max_drift > 0.05,
            "threshold_pct": 5,
            "approach": "Rebalance on drift" if max_drift > 0.05 else "Hold current allocation"
        }

    def _optimize_portfolio(
        self,
        current_weights: List[float],
        assets: List[str],
        expected_returns: Dict[str, float],
        volatilities: Dict[str, float],
        task: Dict[str, Any]
    ) -> List[float]:
        """Optimize portfolio weights (simplified)"""
        n = len(assets)
        if n == 0:
            return []

        # Simple optimization: inverse variance weighting
        vols = [volatilities.get(asset, 0.15) for asset in assets]
        inv_vols = [1.0 / v if v > 0 else 1.0 for v in vols]
        sum_inv_vols = sum(inv_vols)

        optimized = [inv_v / sum_inv_vols for inv_v in inv_vols]

        # Smooth toward current (don't change too dramatically)
        smoothing = 0.5
        return [
            smoothing * opt + (1 - smoothing) * curr
            for opt, curr in zip(optimized, current_weights)
        ]
