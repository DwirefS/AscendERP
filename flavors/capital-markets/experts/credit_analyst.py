"""
Credit Analyst Expert - Capital Markets MoE

Specialized expert for fixed income research and credit risk analysis.

Domains: bonds, credit, fixed_income, credit_spreads, default_risk, ratings
"""

from typing import Any, Dict
import logging

from src.core.moe.moe_agent import Expert, ExpertType, ExpertOutput

logger = logging.getLogger(__name__)


class CreditAnalystExpert(Expert):
    """
    Expert specialized in credit analysis and fixed income assessment

    Analyzes credit instruments using:
    - Credit spreads and relative value
    - Default probability and recovery
    - Covenant analysis and restrictions
    - Credit rating assessment
    - Duration and yield curve positioning
    - Counterparty risk evaluation
    """

    def __init__(self):
        """Initialize Credit Analyst Expert"""
        super().__init__(
            expert_id="cm_credit_analyst",
            expert_type=ExpertType.FINANCE,
            domain=["bonds", "credit", "fixed_income", "credit_spreads", "default_risk", "ratings"]
        )

    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """
        Analyze credit-related tasks

        Args:
            task: Dict containing:
                - issuer: Bond issuer name
                - credit_rating: Current rating (AAA, AA, A, BBB, etc.)
                - spread: Credit spread in basis points
                - coupon: Coupon rate
                - duration: Bond duration
                - maturity: Years to maturity
                - description: Analysis task description

        Returns:
            ExpertOutput with credit analysis and confidence
        """
        logger.info(f"Credit Analyst analyzing: {task.get('description', 'credit task')}")

        confidence = await self.estimate_confidence(task)

        issuer = task.get("issuer", "Unknown")
        rating = task.get("credit_rating", "BBB")
        spread = task.get("spread", 200)  # bps
        coupon = task.get("coupon", 0)
        duration = task.get("duration", 5)
        maturity = task.get("maturity", 10)

        analysis = self._build_credit_analysis(
            issuer=issuer,
            rating=rating,
            spread=spread,
            coupon=coupon,
            duration=duration,
            maturity=maturity,
            task=task
        )

        result = {
            "recommendation": analysis["recommendation"],
            "credit_assessment": analysis["credit_assessment"],
            "spread_analysis": analysis["spread_analysis"],
            "default_risk": analysis["default_risk"],
            "covenant_strength": analysis["covenant_strength"],
            "yield_analysis": analysis["yield_analysis"],
            "key_risks": analysis["risks"]
        }

        return ExpertOutput(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            result=result,
            confidence=confidence,
            reasoning=f"Credit analysis for {issuer}: {analysis['rationale']}"
        )

    async def estimate_confidence(self, task: Dict[str, Any]) -> float:
        """
        Estimate confidence for credit task

        High confidence: Fixed income and credit tasks
        Medium confidence: Cross-asset with credit component
        Low confidence: Equity-focused tasks
        """
        task_domain = task.get("domain", "").lower()
        task_description = task.get("description", "").lower()
        issuer = task.get("issuer")

        credit_keywords = ["bond", "credit", "fixed_income", "spread", "default", "covenant"]
        description_match = sum(1 for kw in credit_keywords if kw in task_description)

        if issuer or any(kw in task_domain for kw in ["bonds", "fixed_income", "credit"]):
            return 0.90
        elif description_match >= 2:
            return 0.82
        elif task_domain in self.domain:
            return 0.88
        elif any(kw in task_domain for kw in self.domain):
            return 0.70
        else:
            return 0.30

    def _build_credit_analysis(
        self,
        issuer: str,
        rating: str,
        spread: float,
        coupon: float,
        duration: float,
        maturity: float,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build detailed credit analysis across multiple dimensions
        """
        # Credit rating assessment
        rating_hierarchy = {
            "AAA": 1.0, "AA": 0.95, "A": 0.85, "BBB": 0.65,
            "BB": 0.40, "B": 0.25, "CCC": 0.10
        }
        rating_score = rating_hierarchy.get(rating, 0.50)
        rating_outlook = "Stable" if rating_score > 0.70 else "Deteriorating"

        # Spread analysis (relative value)
        # Historical context: Investment grade spreads 75-200 bps, HY 300-600 bps
        if rating in ["AAA", "AA"]:
            spread_fair = 100 + (maturity * 5)
            spread_type = "Investment Grade"
        elif rating in ["A", "BBB"]:
            spread_fair = 150 + (maturity * 10)
            spread_type = "Investment Grade"
        else:
            spread_fair = 300 + (maturity * 20)
            spread_type = "High Yield"

        if spread < spread_fair * 0.8:
            spread_assessment = "Tight - Potentially Attractive"
        elif spread > spread_fair * 1.2:
            spread_assessment = "Wide - Potentially Risky"
        else:
            spread_assessment = "Fair Value"

        spread_analysis = {
            "current_spread_bps": int(spread),
            "fair_value_estimate_bps": int(spread_fair),
            "assessment": spread_assessment,
            "credit_type": spread_type
        }

        # Default probability (simplified estimate)
        rating_to_default_prob = {
            "AAA": 0.01, "AA": 0.02, "A": 0.05, "BBB": 0.15,
            "BB": 0.40, "B": 0.75, "CCC": 2.0
        }
        annual_default_prob = rating_to_default_prob.get(rating, 0.50)
        cumulative_default_prob = min(1.0, annual_default_prob * maturity)

        default_risk = {
            "rating": rating,
            "rating_score": rating_score,
            "annual_default_probability_pct": annual_default_prob,
            "cumulative_default_prob_pct": cumulative_default_prob,
            "recovery_assumption_pct": 40,  # Recovery after default
            "risk_adjusted_yield": coupon + (spread / 10000)
        }

        # Covenant strength (simplified)
        covenant_strength = {
            "maintenance_covenants": "Moderate" if rating_score > 0.60 else "Weak",
            "financial_flexibility": "Strong" if rating_score > 0.75 else "Limited",
            "change_of_control": "Present" if rating_score > 0.70 else "Absent"
        }

        # Yield and return analysis
        yield_to_maturity = coupon + (spread / 10000)
        price_sensitivity = duration  # Years of duration

        yield_analysis = {
            "coupon": coupon,
            "spread_bps": int(spread),
            "ytm": yield_to_maturity,
            "duration_years": duration,
            "convexity": "Negative" if rating_score < 0.50 else "Positive"
        }

        # Key risks
        risks = []
        if rating_score < 0.50:
            risks.append(f"Credit deterioration risk - {rating} rating")
        if cumulative_default_prob > 0.10:
            risks.append(f"Default risk - {cumulative_default_prob*100:.1f}% cumulative probability")
        if duration > 7:
            risks.append("Interest rate risk - Long duration exposure")
        if spread < 100:
            risks.append("Spread widening risk - Tight valuations")

        # Recommendation logic
        credit_score = rating_score
        spread_opportunity = 1.0 if "Attractive" in spread_assessment else (0.5 if "Fair" in spread_assessment else 0.2)
        risk_adjusted_score = credit_score * 0.7 + spread_opportunity * 0.3

        if risk_adjusted_score > 0.75:
            recommendation = "BUY"
        elif risk_adjusted_score > 0.60:
            recommendation = "ACCUMULATE"
        elif risk_adjusted_score > 0.40:
            recommendation = "HOLD"
        else:
            recommendation = "REDUCE"

        rationale = f"{recommendation}: {rating} rated, {spread_assessment}, YTM {yield_to_maturity*100:.2f}%"

        return {
            "recommendation": recommendation,
            "credit_assessment": {
                "rating": rating,
                "rating_outlook": rating_outlook,
                "credit_score": credit_score
            },
            "spread_analysis": spread_analysis,
            "default_risk": default_risk,
            "covenant_strength": covenant_strength,
            "yield_analysis": yield_analysis,
            "risks": risks,
            "rationale": rationale
        }
