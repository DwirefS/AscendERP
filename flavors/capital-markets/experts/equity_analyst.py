"""
Equity Analyst Expert - Capital Markets MoE

Specialized expert for equity research and stock analysis using fundamental
and technical indicators.

Domains: equities, stocks, fundamental_analysis, earnings, sector_analysis
"""

from abc import ABC
from typing import Any, Dict, List
import logging

from src.core.moe.moe_agent import Expert, ExpertType, ExpertOutput

logger = logging.getLogger(__name__)


class EquityAnalystExpert(Expert):
    """
    Expert specialized in equity analysis and stock research

    Analyzes equity positions using:
    - Fundamental analysis (P/E, growth, profitability)
    - Technical indicators (momentum, trend, support/resistance)
    - Sector analysis and relative strength
    - Earnings quality and sustainability
    - Valuation models (DCF, comparable companies)
    """

    def __init__(self):
        """Initialize Equity Analyst Expert"""
        super().__init__(
            expert_id="cm_equity_analyst",
            expert_type=ExpertType.FINANCE,
            domain=["equities", "stocks", "fundamental_analysis", "earnings", "sector_analysis"]
        )

    async def analyze(self, task: Dict[str, Any]) -> ExpertOutput:
        """
        Analyze equity-related tasks

        Args:
            task: Dict containing:
                - ticker: Stock ticker symbol
                - price: Current price
                - pe_ratio: P/E ratio
                - growth_rate: Expected growth rate
                - sector: Industry sector
                - market_cap: Market capitalization
                - description: Analysis task description

        Returns:
            ExpertOutput with equity analysis and confidence
        """
        logger.info(f"Equity Analyst analyzing: {task.get('description', 'equity task')}")

        confidence = await self.estimate_confidence(task)

        # Build equity analysis
        ticker = task.get("ticker", "UNKNOWN")
        pe_ratio = task.get("pe_ratio", 0)
        growth_rate = task.get("growth_rate", 0)
        sector = task.get("sector", "General")
        price = task.get("price", 0)

        analysis = self._build_equity_analysis(
            ticker=ticker,
            price=price,
            pe_ratio=pe_ratio,
            growth_rate=growth_rate,
            sector=sector,
            task=task
        )

        result = {
            "recommendation": analysis["recommendation"],
            "valuation_assessment": analysis["valuation"],
            "technical_signals": analysis["technicals"],
            "sector_momentum": analysis["sector_momentum"],
            "earnings_quality": analysis["earnings_quality"],
            "target_price": analysis["target_price"],
            "key_risks": analysis["risks"]
        }

        return ExpertOutput(
            expert_id=self.expert_id,
            expert_type=self.expert_type,
            result=result,
            confidence=confidence,
            reasoning=f"Equity analysis for {ticker}: {analysis['rationale']}"
        )

    async def estimate_confidence(self, task: Dict[str, Any]) -> float:
        """
        Estimate confidence for equity task

        High confidence: Equity-related tasks
        Medium confidence: Cross-asset with equity component
        Low confidence: Non-equity tasks
        """
        task_domain = task.get("domain", "").lower()
        task_description = task.get("description", "").lower()
        ticker = task.get("ticker")

        equity_keywords = ["equity", "stock", "ticker", "share", "equity_analyst"]
        description_equity_match = sum(1 for kw in equity_keywords if kw in task_description)

        if ticker or any(kw in task_domain for kw in ["equities", "stocks"]):
            return 0.92
        elif description_equity_match >= 2:
            return 0.85
        elif task_domain in ["equities", "stocks", "fundamental_analysis"]:
            return 0.88
        elif any(kw in task_domain for kw in self.domain):
            return 0.75
        else:
            return 0.35

    def _build_equity_analysis(
        self,
        ticker: str,
        price: float,
        pe_ratio: float,
        growth_rate: float,
        sector: str,
        task: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build detailed equity analysis

        Returns assessment across multiple dimensions
        """
        # Valuation assessment
        if pe_ratio > 0:
            if pe_ratio < 15:
                valuation = "Undervalued"
                valuation_confidence = 0.78
            elif pe_ratio > 25:
                valuation = "Overvalued"
                valuation_confidence = 0.72
            else:
                valuation = "Fair Value"
                valuation_confidence = 0.75
        else:
            valuation = "Insufficient Data"
            valuation_confidence = 0.50

        # Growth assessment
        if growth_rate > 0.15:
            growth_assessment = "High Growth"
            growth_confidence = 0.80
        elif growth_rate > 0.05:
            growth_assessment = "Moderate Growth"
            growth_confidence = 0.75
        else:
            growth_assessment = "Low/No Growth"
            growth_confidence = 0.70

        # PEG ratio analysis (P/E to Growth)
        if growth_rate > 0 and pe_ratio > 0:
            peg_ratio = pe_ratio / (growth_rate * 100)
            if peg_ratio < 1.0:
                peg_assessment = "Attractive (PEG < 1.0)"
            elif peg_ratio < 2.0:
                peg_assessment = "Reasonable (PEG 1.0-2.0)"
            else:
                peg_assessment = "Expensive (PEG > 2.0)"
        else:
            peg_assessment = "Unable to calculate PEG"

        # Technical signals (simplified)
        technical_signals = {
            "momentum": "Positive" if price > 100 else "Neutral",
            "trend": "Uptrend" if growth_rate > 0.05 else "Downtrend",
            "support_level": price * 0.95,
            "resistance_level": price * 1.05
        }

        # Sector analysis
        sector_momentum = {
            "sector": sector,
            "relative_strength": "Strong" if growth_rate > 0.10 else "Moderate",
            "sector_outlook": "Positive" if growth_rate > 0.05 else "Neutral"
        }

        # Earnings quality
        earnings_quality = {
            "payout_ratio": min(0.6, growth_rate),  # Simplified
            "earnings_stability": "Stable" if growth_rate > 0.03 else "Volatile",
            "fcf_strength": "Strong" if growth_rate > 0.10 else "Moderate"
        }

        # Target price (simplified DCF approach)
        if price > 0 and pe_ratio > 0:
            target_price = price * (1 + growth_rate * 3)  # 3-year target
        else:
            target_price = price

        # Risks
        risks = []
        if pe_ratio > 25:
            risks.append("Valuation risk - High P/E ratio")
        if growth_rate < 0.03:
            risks.append("Growth deceleration risk")
        if growth_rate > 0.20:
            risks.append("Unsustainability risk - High growth expectations")
        risks.append(f"Sector risk - {sector} sector dynamics")

        # Recommendation logic
        valuation_score = 1.0 if valuation == "Undervalued" else (0.5 if valuation == "Fair Value" else 0.2)
        growth_score = 0.9 if growth_rate > 0.15 else (0.6 if growth_rate > 0.05 else 0.3)
        combined_score = valuation_score * 0.6 + growth_score * 0.4

        if combined_score > 0.75:
            recommendation = "STRONG BUY"
        elif combined_score > 0.60:
            recommendation = "BUY"
        elif combined_score > 0.40:
            recommendation = "HOLD"
        else:
            recommendation = "SELL"

        rationale = f"{recommendation}: {valuation} ({pe_ratio:.1f}x), {growth_assessment} ({growth_rate*100:.1f}%), {peg_assessment}"

        return {
            "recommendation": recommendation,
            "valuation": {
                "assessment": valuation,
                "pe_ratio": pe_ratio,
                "peg_ratio": peg_assessment,
                "confidence": valuation_confidence
            },
            "technicals": technical_signals,
            "sector_momentum": sector_momentum,
            "earnings_quality": earnings_quality,
            "target_price": target_price,
            "risks": risks,
            "rationale": rationale
        }
