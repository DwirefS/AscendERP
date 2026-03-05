"""
Trading Agent for Capital Markets.
Executes equity and derivatives orders with smart order routing.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
import time

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


class TradingAgent(BaseAgent):
    """
    Agent for executing equity and derivatives trades with smart order routing.
    Handles order validation, venue selection, execution strategy, and fill verification.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Trading Agent",
                description="Executes equity and derivatives orders with smart order routing",
                tools=[
                    "fetch_market_data",
                    "check_trading_limits",
                    "calculate_slippage",
                    "route_order",
                    "verify_execution"
                ],
                max_iterations=15,
                timeout_seconds=60,
                model_name="gpt-4-turbo"
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Parse and validate order request.

        Expected input:
        {
            "ticker": str,
            "side": "buy" | "sell",
            "quantity": float,
            "limit_price": float (optional),
            "order_type": "market" | "limit" | "vwap" | "twap",
            "urgency": "immediate" | "normal" | "patient",
            "client_id": str
        }
        """
        logger.info(
            "perceiving_order_request",
            trace_id=context.trace_id,
            ticker=input_data.get("ticker"),
            side=input_data.get("side"),
            quantity=input_data.get("quantity")
        )

        perception = {
            "ticker": input_data.get("ticker", "").upper(),
            "side": input_data.get("side", "").lower(),
            "quantity": float(input_data.get("quantity", 0)),
            "limit_price": input_data.get("limit_price"),
            "order_type": input_data.get("order_type", "market").lower(),
            "urgency": input_data.get("urgency", "normal").lower(),
            "client_id": input_data.get("client_id"),
            "request_time": datetime.utcnow().isoformat()
        }

        # Validate order
        if not perception["ticker"]:
            raise ValueError("Ticker symbol is required")
        if perception["side"] not in ["buy", "sell"]:
            raise ValueError(f"Invalid side: {perception['side']}")
        if perception["quantity"] <= 0:
            raise ValueError(f"Invalid quantity: {perception['quantity']}")

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve market data, execution patterns, and compliance rules.
        """
        retrieved = {}

        if self.memory:
            # Get execution patterns for this ticker/venue combination
            procedural = await self.memory.retrieve_procedural(
                context={"ticker": perception["ticker"]},
                agent_id=self.config.agent_id,
                limit=10
            )
            retrieved["execution_patterns"] = [p.content for p in procedural]

            # Get market intelligence and venue information
            semantic = await self.memory.retrieve_semantic(
                query=f"execution strategy for {perception['ticker']} {perception['side']} orders",
                tenant_id=context.tenant_id,
                limit=10
            )
            retrieved["market_intelligence"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Use LLM to determine execution venue, split strategy, and timing.
        """
        prompt = f"""
        You are an expert algorithmic trading system. Based on the following order request
        and market context, determine the optimal execution approach.

        Order Details:
        - Ticker: {perception['ticker']}
        - Side: {perception['side']}
        - Quantity: {perception['quantity']:,.0f} shares
        - Order Type: {perception['order_type']}
        - Limit Price: {perception['limit_price']}
        - Urgency: {perception['urgency']}

        Past Execution Patterns:
        {retrieved_context.get('execution_patterns', [])}

        Market Intelligence:
        {retrieved_context.get('market_intelligence', [])}

        Provide a structured execution plan including:
        1. Execution venue (primary exchange, ATS, dark pool)
        2. Order split strategy (VWAP, TWAP, POV, single fill)
        3. Timing and pace
        4. Expected slippage estimate
        5. Risk considerations
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
                        "type": "execute_order",
                        "venue": response.get("venue", "nyse"),
                        "split_strategy": response.get("split_strategy", "vwap"),
                        "timing": response.get("timing", "normal"),
                        "expected_slippage": response.get("expected_slippage", 0.01),
                        "order_details": perception
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed",
                    error=str(e),
                    fallback="rule_based"
                )

        # Fallback: Rule-based routing
        return {
            "action": {
                "type": "execute_order",
                "venue": self._select_venue_rule_based(perception),
                "split_strategy": self._select_strategy_rule_based(perception),
                "timing": "normal",
                "expected_slippage": 0.015,
                "order_details": perception
            },
            "confidence": 0.75,
            "reasoning": "Rule-based routing applied"
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute the trading order.
        """
        order_details = action.get("order_details", {})
        venue = action.get("venue", "nyse")
        strategy = action.get("split_strategy", "vwap")

        logger.info(
            "executing_order",
            trace_id=context.trace_id,
            ticker=order_details.get("ticker"),
            venue=venue,
            strategy=strategy
        )

        try:
            # Fetch current market data
            market_data = await self._fetch_market_data(order_details.get("ticker"))

            # Calculate expected slippage
            slippage = await self._calculate_slippage(
                order_details.get("quantity"),
                market_data.get("orderbook", {})
            )

            # Check pre-trade compliance
            compliance_result = await self._check_pre_trade_compliance(
                order_details,
                context
            )

            if not compliance_result.get("allowed", False):
                return {
                    "status": "rejected",
                    "reason": compliance_result.get("reason", "Compliance check failed"),
                    "timestamp": datetime.utcnow().isoformat()
                }

            # Route and execute order
            execution_result = await self._route_order(
                venue,
                strategy,
                order_details,
                market_data
            )

            # Generate execution report
            report = await self._generate_execution_report(
                execution_result.get("fills", []),
                order_details,
                slippage
            )

            return {
                "status": "executed",
                "execution_result": execution_result,
                "report": report,
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(
                "order_execution_failed",
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
        Verify execution results and compare against expectations.
        """
        status = result.get("status", "unknown")

        if status == "executed":
            report = result.get("report", {})
            fills = report.get("fills", [])

            # Calculate metrics
            total_filled = sum(f.get("quantity", 0) for f in fills)
            avg_fill_price = (
                sum(f.get("quantity", 0) * f.get("price", 0) for f in fills) / total_filled
                if total_filled > 0 else 0
            )

            return {
                "complete": len(fills) > 0,
                "quality_score": 0.95 if len(fills) > 0 else 0.5,
                "metrics": {
                    "total_filled": total_filled,
                    "average_fill_price": avg_fill_price,
                    "fill_count": len(fills),
                    "execution_time_ms": report.get("execution_time_ms", 0)
                }
            }

        return {
            "complete": status == "executed",
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
        Store successful execution patterns and outcomes.
        """
        if not self.memory or not actions_taken:
            return

        last_action = actions_taken[-1]
        result = last_action.get("result", {})

        if result.get("status") == "executed":
            report = result.get("report", {})
            fills = report.get("fills", [])

            if fills:
                # Calculate execution quality
                total_filled = sum(f.get("quantity", 0) for f in fills)
                success_rate = 1.0

                # Store procedural memory if successful
                if success_rate > 0.85:
                    await self.memory.store_procedural(
                        pattern={
                            "ticker": input_data.get("ticker"),
                            "side": input_data.get("side"),
                            "quantity": input_data.get("quantity"),
                            "venue": last_action.get("action", {}).get("venue"),
                            "strategy": last_action.get("action", {}).get("split_strategy"),
                            "fills": fills
                        },
                        success_rate=success_rate,
                        agent_id=self.config.agent_id,
                        tenant_id=context.tenant_id
                    )

        # Store episodic memory
        await self.memory.store_episodic(
            content={
                "input": input_data,
                "actions": actions_taken,
                "trace_id": context.trace_id
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _fetch_market_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch current market data for ticker."""
        # Placeholder: In production, integrate with market data provider
        logger.info("fetching_market_data", ticker=ticker)
        return {
            "ticker": ticker,
            "last_price": 100.0,
            "bid": 99.95,
            "ask": 100.05,
            "volume": 1000000,
            "orderbook": {
                "bid_levels": [(99.95, 10000), (99.90, 20000)],
                "ask_levels": [(100.05, 10000), (100.10, 20000)]
            }
        }

    async def _calculate_slippage(
        self,
        order_size: float,
        orderbook: Dict[str, Any]
    ) -> float:
        """Calculate expected slippage based on order book."""
        # Simplified impact model
        if order_size < 1000:
            return 0.005
        elif order_size < 10000:
            return 0.01
        else:
            return 0.02

    async def _check_pre_trade_compliance(
        self,
        order: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Check pre-trade compliance via policy engine."""
        if self.policy_engine:
            decision = await self.policy_engine.evaluate({
                "agent_id": self.config.agent_id,
                "action": "place_order",
                "order": order,
                "context": context.metadata
            })
            return decision

        # Default: allow
        return {"allowed": True}

    async def _route_order(
        self,
        venue: str,
        strategy: str,
        order: Dict[str, Any],
        market_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Route and execute order via specified venue."""
        # Placeholder: Integrate with order execution simulator/API
        logger.info(
            "routing_order",
            venue=venue,
            strategy=strategy,
            ticker=order.get("ticker")
        )

        fills = [
            {
                "venue": venue,
                "quantity": order.get("quantity", 0),
                "price": market_data.get("last_price", 100.0),
                "timestamp": datetime.utcnow().isoformat()
            }
        ]

        return {
            "fills": fills,
            "execution_time_ms": 500
        }

    async def _generate_execution_report(
        self,
        fills: List[Dict[str, Any]],
        order: Dict[str, Any],
        slippage: float
    ) -> Dict[str, Any]:
        """Generate comprehensive execution report."""
        total_filled = sum(f.get("quantity", 0) for f in fills)
        total_value = sum(f.get("quantity", 0) * f.get("price", 0) for f in fills)
        avg_price = total_value / total_filled if total_filled > 0 else 0

        return {
            "order_id": f"ORD-{int(time.time())}",
            "ticker": order.get("ticker"),
            "side": order.get("side"),
            "requested_quantity": order.get("quantity"),
            "filled_quantity": total_filled,
            "average_price": avg_price,
            "total_value": total_value,
            "estimated_slippage": slippage,
            "fills": fills,
            "execution_time_ms": 500
        }

    def _select_venue_rule_based(self, perception: Dict[str, Any]) -> str:
        """Rule-based venue selection."""
        quantity = perception.get("quantity", 0)

        if quantity > 100000:
            return "dark_pool"
        elif quantity > 10000:
            return "ats"
        else:
            return "nyse"

    def _select_strategy_rule_based(self, perception: Dict[str, Any]) -> str:
        """Rule-based strategy selection."""
        urgency = perception.get("urgency", "normal")

        if urgency == "immediate":
            return "vwap"
        elif urgency == "patient":
            return "twap"
        else:
            return "vwap"
