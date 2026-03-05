"""
Derivatives Expert - Capital Markets MoE

Specialized expert for options, futures, and structured products analysis
including Greeks, volatility, and hedging strategies.

Domains: options, futures, hedging, greeks, volatility, structured_products
"""

from typing import Any, Dict
import math
import logging

from src.core.moe.moe_agent import Expert, ExpertType, ExpertOutput

logger = logging.getLogger(__name__)


class DerivativesExpert(Expert):
    """
    Expert specialized in derivatives analysis and risk management

    Analyzes derivative instruments using:
    - Option pricing models (Black-Scholes, binomial)
    - Greeks calculation (delta, gamma, vega, theta, rho)
    - Volatility surface analysis and vol clustering
    - Hedging recommendations and strategy optimization
    - Structured product decomposition and valuation
    - Futures and forward analysis
    """

    def __init__(self):
        """Initialize Derivatives Expert"""
        super().__init__(
            expert_id="cm_derivatives_expert",
            expert_type=ExpertType.FINANCE,
            domain=["options", "futures", "hedging", "greeks", "volatility", "structured_products"]
        )

    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """
        Analyze derivatives-related tasks

        Args:
            task: Dict containing:
                - product_type: 'option', 'future', 'swap', 'structured'
                - underlying: Underlying asset
                - spot_price: Current spot price
                - strike: Strike price (for options)
                - maturity: Time to maturity in years
                - volatility: Implied volatility (for options)
                - risk_free_rate: Risk-free rate
                - description: Analysis task description

        Returns:
            ExpertOutput with derivatives analysis and confidence
        """
        logger.info(f"Derivatives Expert analyzing: {task.get('description', 'derivatives task')}")

        confidence = await self.estimate_confidence(task)

        product_type = task.get("product_type", "option").lower()
        underlying = task.get("underlying", "Unknown")
        spot = task.get("spot_price", 100)
        maturity = task.get("maturity", 1)

        if product_type == "option":
            analysis = self._analyze_option(task)
        elif product_type == "future":
            analysis = self._analyze_future(task)
        elif product_type == "structured":
            analysis = self._analyze_structured(task)
        else:
            analysis = self._analyze_generic_derivative(task)

        result = {
            "product_type": product_type,
            "valuation": analysis["valuation"],
            "greeks": analysis.get("greeks", {}),
            "volatility_analysis": analysis.get("vol_analysis", {}),
            "hedging_recommendations": analysis["hedging"],
            "risk_metrics": analysis["risk_metrics"],
            "key_insights": analysis["insights"]
        }

        return ExpertOutput(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            result=result,
            confidence=confidence,
            reasoning=f"Derivatives analysis for {underlying}: {analysis.get('rationale', 'detailed analysis')}"
        )

    async def estimate_confidence(self, task: Dict[str, Any]) -> float:
        """Estimate confidence for derivatives task"""
        task_domain = task.get("domain", "").lower()
        task_description = task.get("description", "").lower()
        product_type = task.get("product_type", "").lower()

        derivatives_keywords = ["option", "future", "hedging", "volatility", "greek", "derivatives"]
        description_match = sum(1 for kw in derivatives_keywords if kw in task_description)

        if product_type in self.domain or any(kw in task_domain for kw in self.domain):
            return 0.88
        elif description_match >= 2:
            return 0.80
        elif any(kw in task_domain for kw in self.domain):
            return 0.70
        else:
            return 0.35

    def _analyze_option(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze option contract"""
        spot = task.get("spot_price", 100)
        strike = task.get("strike", 100)
        maturity = task.get("maturity", 1)
        volatility = task.get("volatility", 0.20)
        rate = task.get("risk_free_rate", 0.05)
        option_type = task.get("option_type", "call").lower()

        # Simplified Black-Scholes
        d1 = (math.log(spot / strike) + (rate + 0.5 * volatility ** 2) * maturity) / (volatility * math.sqrt(maturity))
        d2 = d1 - volatility * math.sqrt(maturity)

        if option_type == "call":
            price = spot * self._normal_cdf(d1) - strike * math.exp(-rate * maturity) * self._normal_cdf(d2)
            delta = self._normal_cdf(d1)
            intrinsic = max(spot - strike, 0)
        else:
            price = strike * math.exp(-rate * maturity) * self._normal_cdf(-d2) - spot * self._normal_cdf(-d1)
            delta = self._normal_cdf(d1) - 1
            intrinsic = max(strike - spot, 0)

        gamma = self._normal_pdf(d1) / (spot * volatility * math.sqrt(maturity))
        vega = spot * self._normal_pdf(d1) * math.sqrt(maturity) / 100
        theta = (-spot * self._normal_pdf(d1) * volatility / (2 * math.sqrt(maturity)) -
                 rate * strike * math.exp(-rate * maturity) * self._normal_cdf(d2)) / 365
        rho = strike * maturity * math.exp(-rate * maturity) * self._normal_cdf(d2) / 100

        moneyness = spot / strike
        if moneyness > 1.05:
            moneyness_status = "ITM"
        elif moneyness < 0.95:
            moneyness_status = "OTM"
        else:
            moneyness_status = "ATM"

        # Valuation recommendation
        time_value = price - intrinsic
        if time_value > 0 and maturity > 0.25:
            pricing_view = "Fair value"
        elif time_value > 0 and maturity < 0.05:
            pricing_view = "Theta decay premium"
        else:
            pricing_view = "Deep ITM/OTM"

        return {
            "valuation": {
                "option_price": round(price, 3),
                "intrinsic_value": round(intrinsic, 3),
                "time_value": round(time_value, 3),
                "moneyness": f"{moneyness_status} ({moneyness:.3f})"
            },
            "greeks": {
                "delta": round(delta, 4),
                "gamma": round(gamma, 4),
                "vega": round(vega, 4),
                "theta": round(theta, 4),
                "rho": round(rho, 4)
            },
            "vol_analysis": {
                "implied_volatility": volatility,
                "vol_regime": "High" if volatility > 0.25 else ("Low" if volatility < 0.15 else "Normal"),
                "vol_term_structure": "Upward sloping" if volatility > 0.20 else "Flat/Inverted"
            },
            "hedging": {
                "delta_hedge_ratio": round(abs(delta), 3),
                "hedge_rebalance_frequency": "Daily" if abs(gamma) > 0.05 else "Weekly",
                "recommended_strategy": self._get_option_strategy(moneyness_status, volatility)
            },
            "risk_metrics": {
                "max_profit": "Unlimited" if option_type == "call" else strike,
                "max_loss": price,
                "breakeven": strike + price if option_type == "call" else strike - price,
                "gamma_exposure": "High" if abs(gamma) > 0.05 else "Low",
                "vega_exposure": "High" if abs(vega) > 0.10 else "Low"
            },
            "insights": [
                f"Option {pricing_view}",
                f"Delta hedge ratio: {round(abs(delta), 3)}",
                f"Time decay: ${round(abs(theta), 2)} per day",
                f"Volatility sensitivity: ${round(vega, 2)} per vol point"
            ],
            "rationale": f"{option_type.upper()} option analysis: {moneyness_status}, price ${price:.2f}"
        }

    def _analyze_future(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze futures contract"""
        spot = task.get("spot_price", 100)
        maturity = task.get("maturity", 1)
        rate = task.get("risk_free_rate", 0.05)
        dividend_yield = task.get("dividend_yield", 0.02)

        # Futures price using cost-of-carry
        futures_price = spot * math.exp((rate - dividend_yield) * maturity)
        basis = spot - futures_price

        return {
            "valuation": {
                "spot_price": round(spot, 2),
                "futures_price": round(futures_price, 2),
                "basis": round(basis, 2),
                "carry_cost": round(rate - dividend_yield, 4)
            },
            "greeks": {
                "delta": 1.0,
                "gamma": 0.0,
                "vega": 0.0,
                "theta": round((rate - dividend_yield) * futures_price, 2)
            },
            "vol_analysis": {
                "contract_volatility": task.get("volatility", 0.18),
                "roll_cost": f"{round(basis, 2)}"
            },
            "hedging": {
                "hedge_ratio": 1.0,
                "contract_multiplier": task.get("multiplier", 1),
                "recommended_strategy": "Roll forward" if maturity < 0.25 else "Hold"
            },
            "risk_metrics": {
                "daily_mark_to_market": "Settled daily",
                "margin_requirement": f"${round(spot * 0.1, 0)}",
                "leverage": "High"
            },
            "insights": [
                f"Futures premium: {round(basis/spot*100, 2)}%",
                f"Cost of carry: {round((rate - dividend_yield)*100, 2)}% annualized",
                f"Fair value: ${round(futures_price, 2)}"
            ],
            "rationale": f"Futures contract: Fair value ${futures_price:.2f}, Basis ${basis:.2f}"
        }

    def _analyze_structured(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze structured product"""
        spot = task.get("spot_price", 100)
        barrier = task.get("barrier_level", 80)
        coupon = task.get("coupon", 0.05)
        maturity = task.get("maturity", 1)

        barrier_level = (barrier / spot) * 100

        return {
            "valuation": {
                "estimated_price": "Depends on components",
                "barrier_level_pct": round(barrier_level, 1),
                "coupon": coupon,
                "payoff_structure": task.get("payoff_type", "Autocallable")
            },
            "greeks": {
                "embedded_options": "Knockout call + bonds",
                "vega_exposure": "Significant"
            },
            "vol_analysis": {
                "note": "Structured products contain embedded volatility",
                "vol_benefit": "Vol sellers benefit; Vol buyers pay premium"
            },
            "hedging": {
                "replication_strategy": "Long bond + Short OTM calls",
                "risk_management": "Monitor barrier breach probability"
            },
            "risk_metrics": {
                "barrier_breach_probability": self._estimate_barrier_prob(spot, barrier, maturity),
                "liquidity_risk": "High - Difficult to exit",
                "counterparty_risk": "Issuer dependent"
            },
            "insights": [
                f"Barrier at {barrier_level:.1f}% of spot",
                "Liquidity premium embedded in pricing",
                "Suitable for yield-seeking investors"
            ],
            "rationale": f"Structured product: {task.get('payoff_type', 'Autocallable')}, Barrier {barrier_level:.1f}%"
        }

    def _analyze_generic_derivative(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze generic derivative"""
        return {
            "valuation": {"status": "Requires specific product details"},
            "hedging": {"recommendation": "Consult product documentation"},
            "risk_metrics": {"status": "Unable to compute without specifications"},
            "insights": ["Provide product type for detailed analysis"],
            "rationale": "Generic derivative analysis - specify product type"
        }

    @staticmethod
    def _normal_cdf(x):
        """Approximate normal CDF using error function"""
        return (1 + math.erf(x / math.sqrt(2))) / 2

    @staticmethod
    def _normal_pdf(x):
        """Normal probability density function"""
        return math.exp(-x ** 2 / 2) / math.sqrt(2 * math.pi)

    @staticmethod
    def _estimate_barrier_prob(spot, barrier, maturity):
        """Estimate probability of barrier breach (simplified)"""
        if spot <= barrier:
            return 1.0
        distance = spot - barrier
        return min(1.0, (distance / spot) ** 2 / maturity)

    @staticmethod
    def _get_option_strategy(moneyness_status, volatility):
        """Recommend option strategy based on conditions"""
        if moneyness_status == "OTM":
            return "Sell for premium" if volatility > 0.25 else "Hold/Let expire"
        elif moneyness_status == "ITM":
            return "Consider taking profits" if volatility > 0.20 else "Hold"
        else:
            return "Monitor delta" if volatility > 0.20 else "Hold ATM"
