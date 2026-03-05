"""
Derivatives Agent for Capital Markets.
Handles pricing, Greeks calculation, hedging analysis, and strategy backtesting.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass
import structlog
import math

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


@dataclass
class OptionGreeks:
    """Container for option Greeks."""
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float


@dataclass
class OptionPrice:
    """Container for option pricing."""
    fair_value: float
    bid: float
    ask: float
    implied_volatility: float
    greeks: OptionGreeks


class DerivativesAgent(BaseAgent):
    """
    Agent for derivatives pricing, Greeks calculation, hedging analysis,
    and strategy backtesting.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Derivatives Agent",
                description="Prices derivatives and calculates hedging requirements",
                tools=[
                    "price_option",
                    "calculate_greeks",
                    "analyze_vol_surface",
                    "recommend_hedge",
                    "backtest_strategy"
                ],
                max_iterations=15,
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
        Parse derivatives request.

        Expected input:
        {
            "request_type": "price" | "hedge" | "analyze" | "backtest",
            "instrument_data": {
                "type": "call" | "put",
                "underlying": str,
                "strike": float,
                "expiry": str (YYYY-MM-DD),
                "spot": float,
                "volatility": float,
                "rate": float,
                "dividend_yield": float (optional)
            },
            "parameters": dict (optional)
        }
        """
        logger.info(
            "perceiving_derivatives_request",
            trace_id=context.trace_id,
            request_type=input_data.get("request_type"),
            underlying=input_data.get("instrument_data", {}).get("underlying")
        )

        perception = {
            "request_type": input_data.get("request_type", "price").lower(),
            "instrument_data": input_data.get("instrument_data", {}),
            "parameters": input_data.get("parameters", {}),
            "request_time": datetime.utcnow().isoformat()
        }

        valid_types = ["price", "hedge", "analyze", "backtest"]
        if perception["request_type"] not in valid_types:
            raise ValueError(f"Invalid request type: {perception['request_type']}")

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve historical volatility data and hedging patterns.
        """
        retrieved = {}

        if self.memory:
            # Get historical volatility data
            procedural = await self.memory.retrieve_procedural(
                context={
                    "underlying": perception["instrument_data"].get("underlying")
                },
                agent_id=self.config.agent_id,
                limit=20
            )
            retrieved["volatility_history"] = [p.content for p in procedural]

            # Get hedging patterns and pricing models
            semantic = await self.memory.retrieve_semantic(
                query=f"options pricing hedging {perception['instrument_data'].get('underlying')}",
                tenant_id=context.tenant_id,
                limit=10
            )
            retrieved["pricing_models"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Determine appropriate derivatives model and calculations.
        """
        instrument = perception["instrument_data"]
        request_type = perception["request_type"]

        prompt = f"""
        You are an expert derivatives trader and quant. Based on the option parameters,
        determine the optimal pricing model and analysis approach.

        Option Details:
        - Type: {instrument.get('type')}
        - Underlying: {instrument.get('underlying')}
        - Strike: ${instrument.get('strike')}
        - Expiry: {instrument.get('expiry')}
        - Spot: ${instrument.get('spot')}
        - Volatility: {instrument.get('volatility'):.1%}

        Request Type: {request_type}

        Volatility History:
        {retrieved_context.get('volatility_history', [])}

        Pricing Models:
        {retrieved_context.get('pricing_models', [])}

        Provide a structured analysis including:
        1. Selected model (Black-Scholes vs Binomial vs other)
        2. Fair value estimate
        3. Greeks calculation
        4. Model assumptions and limitations
        5. Any red flags or considerations
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
                        "type": "analyze_derivatives",
                        "request_type": request_type,
                        "model": response.get("model", "black_scholes"),
                        "instrument_data": instrument,
                        "parameters": perception["parameters"]
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed",
                    error=str(e),
                    fallback="black_scholes"
                )

        # Fallback: Use Black-Scholes for European options
        model = "black_scholes"
        if self._is_american_option(instrument):
            model = "binomial"

        return {
            "action": {
                "type": "analyze_derivatives",
                "request_type": request_type,
                "model": model,
                "instrument_data": instrument,
                "parameters": perception["parameters"]
            },
            "confidence": 0.80,
            "reasoning": f"Using {model} model for option pricing"
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute derivatives analysis and calculations.
        """
        request_type = action.get("request_type")
        instrument = action.get("instrument_data", {})
        model = action.get("model", "black_scholes")

        logger.info(
            "executing_derivatives_analysis",
            trace_id=context.trace_id,
            request_type=request_type,
            underlying=instrument.get("underlying"),
            model=model
        )

        try:
            result = {
                "request_type": request_type,
                "instrument": instrument,
                "model_used": model,
                "timestamp": datetime.utcnow().isoformat()
            }

            if request_type == "price":
                price = await self._price_option(instrument, model)
                result["pricing"] = price

            elif request_type == "hedge":
                hedge = await self._analyze_hedge(instrument, model)
                result["hedging_recommendation"] = hedge

            elif request_type == "analyze":
                analysis = await self._analyze_vol_surface(instrument)
                result["volatility_analysis"] = analysis

            elif request_type == "backtest":
                backtest = await self._backtest_strategy(
                    instrument,
                    action.get("parameters", {})
                )
                result["backtest_results"] = backtest

            return result

        except Exception as e:
            logger.error(
                "derivatives_analysis_failed",
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
        Verify pricing calculations and Greeks consistency.
        """
        if "pricing" in result:
            pricing = result.get("pricing", {})

            # Check for reasonable values
            fair_value = pricing.get("fair_value", 0)
            bid = pricing.get("bid", 0)
            ask = pricing.get("ask", 0)
            greeks = pricing.get("greeks", {})

            # Verify bid-ask spread
            valid_spread = 0 < bid < fair_value < ask

            # Verify Greeks bounds
            valid_delta = -1 <= greeks.get("delta", 0) <= 1
            valid_gamma = greeks.get("gamma", 0) >= 0
            valid_vega = greeks.get("vega", 0) >= 0
            valid_theta = abs(greeks.get("theta", 0)) > 0
            valid_rho = abs(greeks.get("rho", 0)) > 0

            all_valid = all([
                valid_spread,
                valid_delta,
                valid_gamma,
                valid_vega,
                valid_theta,
                valid_rho
            ])

            return {
                "complete": all_valid,
                "quality_score": 0.95 if all_valid else 0.6,
                "metrics": {
                    "bid_ask_spread": ask - bid if bid and ask else 0,
                    "delta": greeks.get("delta", 0),
                    "gamma": greeks.get("gamma", 0),
                    "validation_passed": all_valid
                }
            }

        return {
            "complete": True,
            "quality_score": 0.85,
            "metrics": {}
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Store pricing accuracy and model calibration data.
        """
        if not self.memory or not actions_taken:
            return

        last_action = actions_taken[-1]
        result = last_action.get("result", {})

        # Store episodic memory for model calibration
        await self.memory.store_episodic(
            content={
                "instrument": input_data.get("instrument_data"),
                "request_type": input_data.get("request_type"),
                "model_used": result.get("model_used"),
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": context.trace_id
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _price_option(
        self,
        instrument: Dict[str, Any],
        model: str
    ) -> Dict[str, Any]:
        """Price an option using specified model."""
        logger.info("pricing_option", model=model, underlying=instrument.get("underlying"))

        spot = instrument.get("spot", 100)
        strike = instrument.get("strike", 100)
        rate = instrument.get("rate", 0.05)
        volatility = instrument.get("volatility", 0.20)
        dividend_yield = instrument.get("dividend_yield", 0)

        if model == "black_scholes":
            fair_value = self._black_scholes_call(
                spot, strike, rate, volatility, 0.25, dividend_yield
            ) if instrument.get("type") == "call" else self._black_scholes_put(
                spot, strike, rate, volatility, 0.25, dividend_yield
            )
        else:  # binomial
            fair_value = self._binomial_price(
                spot, strike, rate, volatility, 0.25, instrument.get("type") == "call"
            )

        # Calculate Greeks
        greeks = await self._calculate_greeks(instrument, model)

        # Estimate bid-ask
        bid_ask_width = fair_value * 0.02  # 2% spread

        return {
            "fair_value": fair_value,
            "bid": fair_value - bid_ask_width / 2,
            "ask": fair_value + bid_ask_width / 2,
            "implied_volatility": volatility,
            "greeks": greeks
        }

    async def _analyze_hedge(
        self,
        instrument: Dict[str, Any],
        model: str
    ) -> Dict[str, Any]:
        """Analyze hedging requirements."""
        logger.info("analyzing_hedge", underlying=instrument.get("underlying"))

        # Get Greeks
        greeks = await self._calculate_greeks(instrument, model)

        delta = greeks.get("delta", 0)
        gamma = greeks.get("gamma", 0)
        vega = greeks.get("vega", 0)

        # Determine hedge ratios
        delta_hedge_size = -delta * 100  # Hedge delta with 100 shares per contract

        return {
            "primary_hedge": {
                "type": "delta_hedge",
                "instrument": instrument.get("underlying"),
                "quantity": abs(delta_hedge_size),
                "side": "sell" if delta > 0 else "buy"
            },
            "secondary_hedges": [
                {
                    "type": "gamma_hedge" if gamma != 0 else "vega_hedge",
                    "recommendation": "Consider options for gamma/vega exposure"
                }
            ],
            "greeks": greeks
        }

    async def _analyze_vol_surface(
        self,
        instrument: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze volatility surface and smile."""
        logger.info("analyzing_volatility_surface", underlying=instrument.get("underlying"))

        # Placeholder: Simplified vol surface analysis
        return {
            "underlying": instrument.get("underlying"),
            "current_vol": instrument.get("volatility", 0.20),
            "vol_skew": "slight_downward",
            "term_structure": "contango",
            "implied_vol_levels": {
                "90_delta": 0.18,
                "100_delta": 0.20,
                "110_delta": 0.22
            },
            "observations": "Vol skew suggests protective put demand"
        }

    async def _backtest_strategy(
        self,
        instrument: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Backtest a derivatives strategy."""
        logger.info(
            "backtesting_strategy",
            underlying=instrument.get("underlying"),
            parameters=parameters
        )

        # Placeholder: Simplified backtest
        return {
            "strategy": parameters.get("strategy", "long_call"),
            "backtest_period": "1Y",
            "total_return": 0.15,
            "max_drawdown": -0.08,
            "sharpe_ratio": 1.2,
            "win_rate": 0.65,
            "profit_factor": 1.85
        }

    async def _calculate_greeks(
        self,
        instrument: Dict[str, Any],
        model: str
    ) -> Dict[str, float]:
        """Calculate option Greeks."""
        spot = instrument.get("spot", 100)
        strike = instrument.get("strike", 100)
        rate = instrument.get("rate", 0.05)
        volatility = instrument.get("volatility", 0.20)
        time_to_expiry = 0.25  # Placeholder: 3 months

        # Simplified Black-Scholes Greeks
        d1 = (
            math.log(spot / strike) +
            (rate + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * math.sqrt(time_to_expiry))

        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        # Normal distribution approximations
        nd1 = self._norm_cdf(d1)
        nd1_prime = self._norm_pdf(d1)
        nd2_cdf = self._norm_cdf(d2)

        is_call = instrument.get("type") == "call"

        delta = nd1 if is_call else nd1 - 1
        gamma = nd1_prime / (spot * volatility * math.sqrt(time_to_expiry))
        vega = spot * nd1_prime * math.sqrt(time_to_expiry) / 100
        theta = (
            -spot * nd1_prime * volatility / (2 * math.sqrt(time_to_expiry)) -
            rate * strike * math.exp(-rate * time_to_expiry) * (nd2_cdf if is_call else nd2_cdf - 1)
        ) / 365
        rho = (
            strike * time_to_expiry * math.exp(-rate * time_to_expiry) * (nd2_cdf if is_call else nd2_cdf - 1)
        ) / 100

        return {
            "delta": delta,
            "gamma": gamma,
            "vega": vega,
            "theta": theta,
            "rho": rho
        }

    def _black_scholes_call(
        self,
        spot: float,
        strike: float,
        rate: float,
        volatility: float,
        time_to_expiry: float,
        dividend_yield: float = 0
    ) -> float:
        """Black-Scholes call option pricing."""
        d1 = (
            math.log(spot / strike) +
            (rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * math.sqrt(time_to_expiry))

        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        call = (
            spot * math.exp(-dividend_yield * time_to_expiry) * self._norm_cdf(d1) -
            strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(d2)
        )

        return call

    def _black_scholes_put(
        self,
        spot: float,
        strike: float,
        rate: float,
        volatility: float,
        time_to_expiry: float,
        dividend_yield: float = 0
    ) -> float:
        """Black-Scholes put option pricing."""
        d1 = (
            math.log(spot / strike) +
            (rate - dividend_yield + 0.5 * volatility ** 2) * time_to_expiry
        ) / (volatility * math.sqrt(time_to_expiry))

        d2 = d1 - volatility * math.sqrt(time_to_expiry)

        put = (
            strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(-d2) -
            spot * math.exp(-dividend_yield * time_to_expiry) * self._norm_cdf(-d1)
        )

        return put

    def _binomial_price(
        self,
        spot: float,
        strike: float,
        rate: float,
        volatility: float,
        time_to_expiry: float,
        is_call: bool,
        steps: int = 50
    ) -> float:
        """Binomial option pricing."""
        dt = time_to_expiry / steps
        u = math.exp(volatility * math.sqrt(dt))
        d = 1 / u
        p = (math.exp(rate * dt) - d) / (u - d)

        # Build price tree
        prices = [[0 for _ in range(i + 1)] for i in range(steps + 1)]

        for i in range(steps + 1):
            for j in range(i + 1):
                prices[i][j] = spot * (u ** (i - j)) * (d ** j)

        # Calculate option values
        option_values = [0] * (steps + 1)

        for j in range(steps + 1):
            option_values[j] = max(
                prices[steps][j] - strike, 0
            ) if is_call else max(strike - prices[steps][j], 0)

        # Backward induction
        for i in range(steps - 1, -1, -1):
            for j in range(i + 1):
                option_values[j] = (
                    p * option_values[j] +
                    (1 - p) * option_values[j + 1]
                ) * math.exp(-rate * dt)

        return option_values[0]

    def _norm_cdf(self, x: float) -> float:
        """Approximation of normal CDF."""
        return (1 + math.erf(x / math.sqrt(2))) / 2

    def _norm_pdf(self, x: float) -> float:
        """Normal PDF."""
        return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)

    def _is_american_option(self, instrument: Dict[str, Any]) -> bool:
        """Determine if option is American style."""
        return instrument.get("style", "european").lower() == "american"
