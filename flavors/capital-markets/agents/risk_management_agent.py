"""
Risk Management Agent for Capital Markets.
Monitors portfolio risk metrics, calculates VaR, stress tests, and manages risk limits.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
import structlog
import math

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


@dataclass
class RiskMetrics:
    """Container for risk calculation results."""
    var_95: float
    var_99: float
    expected_shortfall: float
    portfolio_delta: float
    portfolio_gamma: float
    portfolio_vega: float
    concentration_hhi: float
    max_breach: Optional[Dict[str, Any]]


class RiskManagementAgent(BaseAgent):
    """
    Agent for comprehensive portfolio risk assessment and management.
    Calculates VaR, Greeks, concentration metrics, and stress tests.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Risk Management Agent",
                description="Monitors portfolio risk metrics and enforces risk limits",
                tools=[
                    "calculate_var",
                    "calculate_greeks",
                    "check_position_limits",
                    "stress_test",
                    "alert_breach"
                ],
                max_iterations=20,
                timeout_seconds=120,
                model_name="gpt-4-turbo"
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Parse risk assessment request.

        Expected input:
        {
            "portfolio_id": str,
            "assessment_type": "continuous" | "on_demand" | "stress_test",
            "positions": list (optional),
            "scenario": str (optional, for stress test)
        }
        """
        logger.info(
            "perceiving_risk_assessment_request",
            trace_id=context.trace_id,
            portfolio_id=input_data.get("portfolio_id"),
            assessment_type=input_data.get("assessment_type")
        )

        perception = {
            "portfolio_id": input_data.get("portfolio_id"),
            "assessment_type": input_data.get("assessment_type", "on_demand").lower(),
            "positions": input_data.get("positions", []),
            "scenario": input_data.get("scenario"),
            "confidence_levels": [0.95, 0.99],
            "request_time": datetime.utcnow().isoformat()
        }

        if perception["assessment_type"] not in ["continuous", "on_demand", "stress_test"]:
            raise ValueError(f"Invalid assessment type: {perception['assessment_type']}")

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve risk history, past assessments, and breach patterns.
        """
        retrieved = {}

        if self.memory:
            # Get past risk assessments for this portfolio
            procedural = await self.memory.retrieve_procedural(
                context={"portfolio_id": perception["portfolio_id"]},
                agent_id=self.config.agent_id,
                limit=20
            )
            retrieved["past_assessments"] = [p.content for p in procedural]

            # Get VaR history and risk trends
            semantic = await self.memory.retrieve_semantic(
                query=f"risk metrics trends portfolio {perception['portfolio_id']}",
                tenant_id=context.tenant_id,
                limit=10
            )
            retrieved["risk_trends"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Determine which risk calculations to run and severity assessment.
        """
        prompt = f"""
        You are an expert risk manager. Based on the portfolio and assessment request,
        determine the appropriate risk calculations and monitoring approach.

        Portfolio Assessment:
        - Portfolio ID: {perception['portfolio_id']}
        - Assessment Type: {perception['assessment_type']}
        - Number of Positions: {len(perception['positions'])}

        Past Risk Assessments:
        {retrieved_context.get('past_assessments', [])}

        Risk Trends:
        {retrieved_context.get('risk_trends', [])}

        Provide a structured risk assessment plan including:
        1. Which risk metrics to calculate (VaR, Greeks, concentration)
        2. Assessment priority and urgency
        3. Potential areas of concern
        4. Recommended actions if any limits are breached
        """

        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    max_tokens=self.config.max_tokens,
                    temperature=0.3
                )

                return {
                    "action": {
                        "type": "assess_risk",
                        "calculate_var": response.get("calculate_var", True),
                        "calculate_greeks": response.get("calculate_greeks", True),
                        "check_concentration": response.get("check_concentration", True),
                        "run_stress_tests": perception["assessment_type"] == "stress_test",
                        "portfolio_id": perception["portfolio_id"],
                        "positions": perception["positions"]
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed",
                    error=str(e),
                    fallback="comprehensive"
                )

        # Fallback: Run all calculations
        return {
            "action": {
                "type": "assess_risk",
                "calculate_var": True,
                "calculate_greeks": True,
                "check_concentration": True,
                "run_stress_tests": perception["assessment_type"] == "stress_test",
                "portfolio_id": perception["portfolio_id"],
                "positions": perception["positions"]
            },
            "confidence": 0.80,
            "reasoning": "Comprehensive risk assessment applied"
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute risk calculations and analysis.
        """
        portfolio_id = action.get("portfolio_id")
        positions = action.get("positions", [])

        logger.info(
            "executing_risk_assessment",
            trace_id=context.trace_id,
            portfolio_id=portfolio_id,
            position_count=len(positions)
        )

        try:
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "portfolio_id": portfolio_id
            }

            # Calculate VaR
            if action.get("calculate_var", True):
                var_result = await self._calculate_portfolio_var(positions)
                metrics.update(var_result)

            # Calculate Greeks
            if action.get("calculate_greeks", True):
                greeks = await self._calculate_portfolio_greeks(positions)
                metrics.update(greeks)

            # Check concentration
            if action.get("check_concentration", True):
                concentration = await self._check_concentration(positions)
                metrics.update(concentration)

            # Run stress tests
            if action.get("run_stress_tests", False):
                stress_results = await self._run_stress_tests(positions)
                metrics["stress_tests"] = stress_results

            # Check for breaches
            breaches = await self._identify_breaches(metrics)

            # Prepare council convocation data if severe
            should_convene = self._should_convene_risk_committee(breaches)

            return {
                "status": "complete",
                "metrics": metrics,
                "breaches": breaches,
                "should_convene_committee": should_convene,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(
                "risk_assessment_failed",
                trace_id=context.trace_id,
                error=str(e)
            )
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Verify risk calculations are complete and valid.
        """
        status = result.get("status", "unknown")

        if status == "complete":
            metrics = result.get("metrics", {})

            # Check for NaN values
            has_nans = False
            for key in ["var_95", "var_99", "portfolio_delta", "concentration_hhi"]:
                if key in metrics and (
                    metrics[key] is None or
                    (isinstance(metrics[key], float) and math.isnan(metrics[key]))
                ):
                    has_nans = True

            # Check bounds
            within_bounds = True
            if "var_95" in metrics and (metrics["var_95"] < 0 or metrics["var_95"] > 100):
                within_bounds = False

            return {
                "complete": status == "complete",
                "quality_score": 0.95 if (not has_nans and within_bounds) else 0.6,
                "metrics": {
                    "has_nans": has_nans,
                    "within_bounds": within_bounds,
                    "breach_count": len(result.get("breaches", []))
                }
            }

        return {
            "complete": False,
            "quality_score": 0.0,
            "metrics": {}
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Store risk assessments and trends in memory.
        """
        if not self.memory or not actions_taken:
            return

        last_action = actions_taken[-1]
        result = last_action.get("result", {})

        if result.get("status") == "complete":
            # Store procedural memory for risk assessment patterns
            await self.memory.store_procedural(
                pattern={
                    "portfolio_id": input_data.get("portfolio_id"),
                    "assessment_type": input_data.get("assessment_type"),
                    "metrics": result.get("metrics", {}),
                    "breaches": result.get("breaches", [])
                },
                success_rate=1.0,
                agent_id=self.config.agent_id,
                tenant_id=context.tenant_id
            )

        # Store episodic memory
        await self.memory.store_episodic(
            content={
                "input": input_data,
                "result": result,
                "trace_id": context.trace_id
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _calculate_portfolio_var(
        self,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate Value at Risk using historical simulation.
        """
        logger.info("calculating_portfolio_var", position_count=len(positions))

        # Placeholder: In production, use actual historical data
        total_portfolio_value = sum(p.get("value", 0) for p in positions)

        # Simplified VaR calculation (95% and 99%)
        daily_volatility = 0.015  # 1.5% daily vol
        position_count = len(positions)
        concentration_penalty = 1.0 + (0.1 * max(0, position_count - 20) / 20)

        var_95 = total_portfolio_value * 1.645 * daily_volatility * concentration_penalty
        var_99 = total_portfolio_value * 2.326 * daily_volatility * concentration_penalty
        expected_shortfall = var_99 * 1.25

        return {
            "var_95": var_95,
            "var_99": var_99,
            "expected_shortfall": expected_shortfall,
            "portfolio_value": total_portfolio_value
        }

    async def _calculate_portfolio_greeks(
        self,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate Greeks for derivatives positions.
        """
        logger.info("calculating_portfolio_greeks", position_count=len(positions))

        portfolio_delta = 0.0
        portfolio_gamma = 0.0
        portfolio_vega = 0.0

        for position in positions:
            if position.get("type") == "option":
                # Simplified Black-Scholes Greeks
                portfolio_delta += position.get("delta", 0) * position.get("quantity", 0)
                portfolio_gamma += position.get("gamma", 0) * position.get("quantity", 0)
                portfolio_vega += position.get("vega", 0) * position.get("quantity", 0)
            elif position.get("type") == "stock":
                portfolio_delta += position.get("quantity", 0)

        return {
            "portfolio_delta": portfolio_delta,
            "portfolio_gamma": portfolio_gamma,
            "portfolio_vega": portfolio_vega
        }

    async def _check_concentration(
        self,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Check position concentration and sector exposure.
        """
        logger.info("checking_concentration", position_count=len(positions))

        total_value = sum(p.get("value", 0) for p in positions)

        # Calculate Herfindahl-Hirschman Index (HHI)
        hhi = 0.0
        for position in positions:
            weight = position.get("value", 0) / total_value if total_value > 0 else 0
            hhi += weight ** 2

        # Sector exposure analysis
        sector_exposure = {}
        for position in positions:
            sector = position.get("sector", "unknown")
            value = position.get("value", 0)
            sector_exposure[sector] = sector_exposure.get(sector, 0) + value

        max_sector_exposure = max(sector_exposure.values()) / total_value if sector_exposure else 0

        return {
            "concentration_hhi": hhi,
            "sector_exposure": sector_exposure,
            "max_sector_exposure": max_sector_exposure,
            "concentration_ratio": hhi  # Simplified
        }

    async def _run_stress_tests(
        self,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run stress test scenarios.
        """
        logger.info("running_stress_tests", position_count=len(positions))

        scenarios = {
            "market_crash_10pct": -0.10,
            "market_crash_20pct": -0.20,
            "rate_shock_up_100bps": 0.01,
            "vol_spike_50pct": 0.50,
            "sector_crash_airline": -0.25
        }

        results = {}
        for scenario_name, scenario_shock in scenarios.items():
            # Placeholder: Calculate P&L impact
            portfolio_value = sum(p.get("value", 0) for p in positions)
            shock_impact = portfolio_value * scenario_shock

            results[scenario_name] = {
                "shock": scenario_shock,
                "estimated_loss": abs(shock_impact) if shock_impact < 0 else 0
            }

        return results

    async def _identify_breaches(
        self,
        metrics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Identify any risk limit breaches.
        """
        breaches = []

        # VaR limits
        var_95_limit = 1000000  # $1M
        var_99_limit = 1500000  # $1.5M

        if metrics.get("var_95", 0) > var_95_limit:
            breaches.append({
                "type": "var_95_breach",
                "limit": var_95_limit,
                "current": metrics.get("var_95", 0),
                "severity": "high"
            })

        if metrics.get("var_99", 0) > var_99_limit:
            breaches.append({
                "type": "var_99_breach",
                "limit": var_99_limit,
                "current": metrics.get("var_99", 0),
                "severity": "critical"
            })

        # Concentration limits
        hhi_limit = 0.25
        if metrics.get("concentration_hhi", 0) > hhi_limit:
            breaches.append({
                "type": "concentration_breach",
                "limit": hhi_limit,
                "current": metrics.get("concentration_hhi", 0),
                "severity": "medium"
            })

        # Sector exposure limits
        sector_limit = 0.40
        if metrics.get("max_sector_exposure", 0) > sector_limit:
            breaches.append({
                "type": "sector_exposure_breach",
                "limit": sector_limit,
                "current": metrics.get("max_sector_exposure", 0),
                "severity": "medium"
            })

        return breaches

    def _should_convene_risk_committee(self, breaches: List[Dict[str, Any]]) -> bool:
        """
        Determine if risk committee should be convened based on breach severity.
        """
        if not breaches:
            return False

        # Convene if any critical breaches
        for breach in breaches:
            if breach.get("severity") == "critical":
                return True

        # Convene if multiple high-severity breaches
        high_severity_count = sum(
            1 for b in breaches
            if b.get("severity") in ["high", "critical"]
        )

        return high_severity_count >= 2
