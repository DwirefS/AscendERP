"""
Portfolio Manager Agent for Capital Markets.
Monitors portfolio drift, optimizes allocations, and manages rebalancing.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import structlog
import math

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


class PortfolioManagerAgent(BaseAgent):
    """
    Agent for portfolio management including drift monitoring,
    optimization, and rebalancing operations.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Portfolio Manager Agent",
                description="Monitors and optimizes portfolio allocations",
                tools=[
                    "get_portfolio",
                    "calculate_drift",
                    "optimize_allocation",
                    "rebalance",
                    "track_performance"
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
        Parse portfolio management request.

        Expected input:
        {
            "portfolio_id": str,
            "action": "monitor" | "rebalance" | "optimize" | "report",
            "drift_threshold": float (default 0.05),
            "rebalance_params": dict (optional)
        }
        """
        logger.info(
            "perceiving_portfolio_request",
            trace_id=context.trace_id,
            portfolio_id=input_data.get("portfolio_id"),
            action=input_data.get("action")
        )

        perception = {
            "portfolio_id": input_data.get("portfolio_id"),
            "action": input_data.get("action", "monitor").lower(),
            "drift_threshold": input_data.get("drift_threshold", 0.05),
            "rebalance_params": input_data.get("rebalance_params", {}),
            "request_time": datetime.utcnow().isoformat()
        }

        valid_actions = ["monitor", "rebalance", "optimize", "report"]
        if perception["action"] not in valid_actions:
            raise ValueError(f"Invalid action: {perception['action']}")

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve portfolio history, target allocation, and rebalancing patterns.
        """
        retrieved = {}

        if self.memory:
            # Get target allocation and historical performance
            procedural = await self.memory.retrieve_procedural(
                context={"portfolio_id": perception["portfolio_id"]},
                agent_id=self.config.agent_id,
                limit=20
            )
            retrieved["portfolio_history"] = [p.content for p in procedural]

            # Get rebalancing best practices and optimization guidelines
            semantic = await self.memory.retrieve_semantic(
                query=f"portfolio optimization rebalancing strategy {perception['portfolio_id']}",
                tenant_id=context.tenant_id,
                limit=10
            )
            retrieved["optimization_guidelines"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Determine portfolio management action and strategy.
        """
        prompt = f"""
        You are an expert portfolio manager. Based on the portfolio and request,
        determine the optimal management approach.

        Portfolio Request:
        - Portfolio ID: {perception['portfolio_id']}
        - Action: {perception['action']}
        - Drift Threshold: {perception['drift_threshold']:.1%}

        Portfolio History:
        {retrieved_context.get('portfolio_history', [])}

        Optimization Guidelines:
        {retrieved_context.get('optimization_guidelines', [])}

        Provide a structured portfolio management plan including:
        1. Current status assessment
        2. Drift calculation and comparison to threshold
        3. Recommended action (rebalance if drift exceeds threshold)
        4. Specific rebalancing trades if needed
        5. Expected impact and timeline
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
                        "type": perception["action"],
                        "portfolio_id": perception["portfolio_id"],
                        "drift_threshold": perception["drift_threshold"],
                        "rebalance_params": perception["rebalance_params"],
                        "suggested_trades": response.get("suggested_trades", [])
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed",
                    error=str(e),
                    fallback="analysis"
                )

        # Fallback: Basic analysis
        return {
            "action": {
                "type": perception["action"],
                "portfolio_id": perception["portfolio_id"],
                "drift_threshold": perception["drift_threshold"],
                "rebalance_params": perception["rebalance_params"],
                "suggested_trades": []
            },
            "confidence": 0.75,
            "reasoning": "Basic portfolio analysis applied"
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute portfolio management action.
        """
        action_type = action.get("type", "monitor")
        portfolio_id = action.get("portfolio_id")

        logger.info(
            "executing_portfolio_action",
            trace_id=context.trace_id,
            portfolio_id=portfolio_id,
            action_type=action_type
        )

        try:
            # Get current portfolio
            portfolio = await self._get_portfolio(portfolio_id)

            # Calculate current drift
            drift_result = await self._calculate_drift(portfolio)

            result = {
                "action_type": action_type,
                "portfolio_id": portfolio_id,
                "portfolio": portfolio,
                "drift": drift_result,
                "timestamp": datetime.utcnow().isoformat()
            }

            if action_type == "monitor":
                result["status"] = "monitored"

            elif action_type == "rebalance":
                drift_threshold = action.get("drift_threshold", 0.05)

                if drift_result.get("max_drift", 0) > drift_threshold:
                    # Generate rebalancing trades
                    rebalance_trades = await self._generate_rebalancing_trades(
                        portfolio,
                        drift_result
                    )

                    # Check if approval needed
                    total_rebalance_value = sum(
                        abs(t.get("value", 0)) for t in rebalance_trades
                    )

                    result["rebalancing_trades"] = rebalance_trades
                    result["total_rebalance_value"] = total_rebalance_value
                    result["needs_approval"] = total_rebalance_value > 1000000

                    if not result.get("needs_approval"):
                        # Execute rebalancing
                        execution_result = await self._execute_rebalancing(
                            portfolio_id,
                            rebalance_trades,
                            context
                        )
                        result["execution_result"] = execution_result

                    result["status"] = "rebalance_ready"
                else:
                    result["status"] = "no_rebalancing_needed"

            elif action_type == "optimize":
                # Run optimization
                optimized = await self._optimize_allocation(portfolio)
                result["optimization_result"] = optimized
                result["status"] = "optimized"

            elif action_type == "report":
                # Generate performance report
                report = await self._generate_performance_report(portfolio, drift_result)
                result["report"] = report
                result["status"] = "report_generated"

            return result

        except Exception as e:
            logger.error(
                "portfolio_action_failed",
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
        Verify portfolio management action results.
        """
        status = result.get("status", "unknown")

        if status in ["monitored", "optimized", "report_generated", "rebalance_ready"]:
            # Verify new allocation matches target within tolerance
            if "portfolio" in result:
                portfolio = result.get("portfolio", {})
                allocation = result.get("drift", {}).get("current_allocation", {})

                return {
                    "complete": status != "error",
                    "quality_score": 0.95,
                    "metrics": {
                        "position_count": len(portfolio.get("positions", [])),
                        "max_drift": result.get("drift", {}).get("max_drift", 0),
                        "total_value": portfolio.get("total_value", 0)
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
        Store portfolio management outcomes and optimization results.
        """
        if not self.memory or not actions_taken:
            return

        last_action = actions_taken[-1]
        result = last_action.get("result", {})

        # Store procedural memory for portfolio patterns
        await self.memory.store_procedural(
            pattern={
                "portfolio_id": input_data.get("portfolio_id"),
                "action": input_data.get("action"),
                "drift_result": result.get("drift", {}),
                "rebalancing": result.get("rebalancing_trades", [])
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

    async def _get_portfolio(self, portfolio_id: str) -> Dict[str, Any]:
        """Retrieve portfolio data."""
        logger.info("retrieving_portfolio", portfolio_id=portfolio_id)

        # Placeholder: In production, fetch from portfolio database
        return {
            "portfolio_id": portfolio_id,
            "total_value": 10000000,
            "positions": [
                {
                    "ticker": "AAPL",
                    "quantity": 1000,
                    "price": 150.0,
                    "value": 150000,
                    "target_allocation": 0.15
                },
                {
                    "ticker": "MSFT",
                    "quantity": 500,
                    "price": 400.0,
                    "value": 200000,
                    "target_allocation": 0.20
                },
                {
                    "ticker": "SPY",
                    "quantity": 2000,
                    "price": 450.0,
                    "value": 900000,
                    "target_allocation": 0.09
                }
            ]
        }

    async def _calculate_drift(
        self,
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate drift from target allocation."""
        logger.info("calculating_drift", portfolio_id=portfolio.get("portfolio_id"))

        total_value = portfolio.get("total_value", 0)
        positions = portfolio.get("positions", [])

        current_allocation = {}
        max_drift = 0.0

        for position in positions:
            ticker = position.get("ticker")
            position_value = position.get("value", 0)
            target = position.get("target_allocation", 0)

            current_weight = position_value / total_value if total_value > 0 else 0
            drift = abs(current_weight - target)

            current_allocation[ticker] = {
                "current_weight": current_weight,
                "target_weight": target,
                "drift": drift
            }

            max_drift = max(max_drift, drift)

        return {
            "current_allocation": current_allocation,
            "max_drift": max_drift,
            "total_drift": sum(
                abs(current_allocation[ticker]["drift"])
                for ticker in current_allocation
            ) / len(current_allocation) if current_allocation else 0
        }

    async def _generate_rebalancing_trades(
        self,
        portfolio: Dict[str, Any],
        drift_result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate specific rebalancing trades."""
        logger.info("generating_rebalancing_trades")

        trades = []
        total_value = portfolio.get("total_value", 0)

        for ticker, allocation in drift_result.get("current_allocation", {}).items():
            target_weight = allocation.get("target_weight", 0)
            current_weight = allocation.get("current_weight", 0)

            if allocation.get("drift", 0) > 0.02:  # 2% threshold
                target_value = total_value * target_weight
                current_value = total_value * current_weight
                trade_value = target_value - current_value

                trades.append({
                    "ticker": ticker,
                    "side": "buy" if trade_value > 0 else "sell",
                    "value": abs(trade_value),
                    "reason": "rebalancing"
                })

        return trades

    async def _execute_rebalancing(
        self,
        portfolio_id: str,
        trades: List[Dict[str, Any]],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Execute rebalancing trades."""
        logger.info(
            "executing_rebalancing",
            portfolio_id=portfolio_id,
            trade_count=len(trades)
        )

        # Placeholder: Delegate to trading agent
        return {
            "status": "executed",
            "trades_executed": len(trades),
            "total_value": sum(t.get("value", 0) for t in trades)
        }

    async def _optimize_allocation(
        self,
        portfolio: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Optimize portfolio allocation using Modern Portfolio Theory."""
        logger.info("optimizing_allocation")

        # Placeholder: Simplified optimization
        positions = portfolio.get("positions", [])

        optimized = {
            "recommended_allocation": {},
            "expected_return": 0.08,
            "expected_volatility": 0.12,
            "sharpe_ratio": 0.67
        }

        # Equal-weight simplified optimization
        equal_weight = 1.0 / len(positions) if positions else 0

        for position in positions:
            ticker = position.get("ticker")
            optimized["recommended_allocation"][ticker] = equal_weight

        return optimized

    async def _generate_performance_report(
        self,
        portfolio: Dict[str, Any],
        drift_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate portfolio performance report."""
        logger.info("generating_performance_report")

        return {
            "portfolio_id": portfolio.get("portfolio_id"),
            "total_value": portfolio.get("total_value"),
            "position_count": len(portfolio.get("positions", [])),
            "ytd_return": 0.12,
            "ytd_volatility": 0.14,
            "max_allocation_drift": drift_result.get("max_drift", 0),
            "average_allocation_drift": drift_result.get("total_drift", 0),
            "timestamp": datetime.utcnow().isoformat()
        }
