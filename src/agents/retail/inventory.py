"""
Inventory Management Agent for ANTS.
Manages stock levels, reordering, and demand forecasting.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext
from src.core.agent.registry import register_agent

logger = structlog.get_logger()


@register_agent(
    agent_type="retail.inventory",
    name="Inventory Management Agent",
    description="Manages inventory levels, reordering, and demand forecasting",
    category="retail",
    capabilities=["inventory_tracking", "demand_forecasting", "auto_reorder"]
)
class InventoryAgent(BaseAgent):
    """
    Agent for inventory management in retail.
    Monitors stock levels, predicts demand, and triggers reorders.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Inventory Management Agent",
                description="Manages inventory and demand forecasting",
                tools=[
                    "query_inventory",
                    "update_stock_levels",
                    "create_purchase_order",
                    "forecast_demand",
                    "check_supplier_availability"
                ],
                max_iterations=10,
                timeout_seconds=300,
                model_name="llama-3.1-nemotron-nano-8b"
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Parse inventory management request."""
        logger.info(
            "perceiving_inventory_request",
            trace_id=context.trace_id,
            request_type=input_data.get("type")
        )

        perception = {
            "request_type": input_data.get("type", "check_levels"),
            "products": input_data.get("products", []),
            "warehouse_id": input_data.get("warehouse_id"),
            "threshold": input_data.get("reorder_threshold", 0.2),
            "forecast_days": input_data.get("forecast_days", 30),
            "urgency": input_data.get("urgency", "normal"),
            "parameters": input_data.get("parameters", {})
        }

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Retrieve relevant inventory context."""
        retrieved = {}

        if self.memory:
            # Get historical demand patterns
            semantic = await self.memory.retrieve_semantic(
                query=f"demand patterns for {perception['products']}",
                tenant_id=context.tenant_id,
                limit=20
            )
            retrieved["demand_patterns"] = [s.content for s in semantic]

            # Get successful reorder patterns
            procedural = await self.memory.retrieve_procedural(
                context={"products": perception["products"]},
                agent_id=self.config.agent_id,
                limit=5
            )
            retrieved["reorder_patterns"] = [p.content for p in procedural]

        # Get current inventory data
        retrieved["current_inventory"] = await self._get_current_inventory(
            perception["products"],
            perception["warehouse_id"]
        )

        # Get recent sales velocity
        retrieved["sales_velocity"] = await self._get_sales_velocity(
            perception["products"],
            days=perception["forecast_days"]
        )

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Determine inventory management actions."""
        request_type = perception["request_type"]

        if request_type == "check_levels":
            return await self._reason_check_levels(perception, retrieved_context)
        elif request_type == "forecast_demand":
            return await self._reason_forecast(perception, retrieved_context)
        elif request_type == "auto_reorder":
            return await self._reason_reorder(perception, retrieved_context)
        else:
            return {
                "action": None,
                "confidence": 0.0,
                "reasoning": f"Unknown request type: {request_type}"
            }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """Execute inventory management actions."""
        action_type = action.get("type")
        results = {
            "action_type": action_type,
            "actions_taken": [],
            "status": "in_progress"
        }

        if action_type == "check_levels":
            results["inventory_status"] = action.get("inventory_status", [])
            results["low_stock_items"] = action.get("low_stock_items", [])

        elif action_type == "forecast_demand":
            results["forecasts"] = action.get("forecasts", [])

        elif action_type == "create_purchase_orders":
            for po in action.get("purchase_orders", []):
                result = await self._create_purchase_order(po, context)
                results["actions_taken"].append({
                    "action": "create_po",
                    "result": result
                })

        results["status"] = "completed"
        return results

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """Verify inventory management results."""
        status = result.get("status")

        return {
            "complete": status == "completed",
            "success": True,
            "metrics": {
                "actions_count": len(result.get("actions_taken", [])),
                "low_stock_count": len(result.get("low_stock_items", []))
            }
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """Learn from inventory management operations."""
        if not self.memory:
            return

        # Store successful reorder patterns
        if actions_taken:
            last_result = actions_taken[-1].get("result", {})

            if last_result.get("status") == "completed":
                await self.memory.store_procedural(
                    pattern={
                        "request_type": input_data.get("type"),
                        "products": input_data.get("products"),
                        "actions": [a.get("action") for a in actions_taken]
                    },
                    success_rate=0.9,
                    agent_id=self.config.agent_id,
                    tenant_id=context.tenant_id
                )

        # Store episodic trace
        await self.memory.store_episodic(
            content={
                "input": input_data,
                "actions": actions_taken,
                "trace_id": context.trace_id
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _reason_check_levels(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reason about inventory levels."""
        current_inventory = retrieved_context.get("current_inventory", {})
        threshold = perception["threshold"]

        low_stock_items = []
        inventory_status = []

        for product_id, data in current_inventory.items():
            current_qty = data.get("quantity", 0)
            max_qty = data.get("max_quantity", 100)
            stock_ratio = current_qty / max_qty if max_qty > 0 else 0

            status_entry = {
                "product_id": product_id,
                "current_quantity": current_qty,
                "max_quantity": max_qty,
                "stock_ratio": stock_ratio,
                "status": "ok" if stock_ratio > threshold else "low"
            }

            inventory_status.append(status_entry)

            if stock_ratio <= threshold:
                low_stock_items.append(status_entry)

        return {
            "action": {
                "type": "check_levels",
                "inventory_status": inventory_status,
                "low_stock_items": low_stock_items
            },
            "confidence": 0.95,
            "reasoning": f"Identified {len(low_stock_items)} items below {threshold*100}% threshold"
        }

    async def _reason_forecast(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reason about demand forecasting."""
        sales_velocity = retrieved_context.get("sales_velocity", {})
        forecast_days = perception["forecast_days"]

        forecasts = []
        for product_id, velocity in sales_velocity.items():
            avg_daily_sales = velocity.get("avg_daily_sales", 0)
            predicted_demand = avg_daily_sales * forecast_days

            forecasts.append({
                "product_id": product_id,
                "forecast_days": forecast_days,
                "predicted_demand": predicted_demand,
                "confidence": 0.8
            })

        return {
            "action": {
                "type": "forecast_demand",
                "forecasts": forecasts
            },
            "confidence": 0.8,
            "reasoning": f"Forecasted demand for {len(forecasts)} products"
        }

    async def _reason_reorder(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Reason about automatic reordering."""
        current_inventory = retrieved_context.get("current_inventory", {})
        sales_velocity = retrieved_context.get("sales_velocity", {})
        threshold = perception["threshold"]

        purchase_orders = []

        for product_id, inv_data in current_inventory.items():
            current_qty = inv_data.get("quantity", 0)
            max_qty = inv_data.get("max_quantity", 100)
            stock_ratio = current_qty / max_qty if max_qty > 0 else 0

            if stock_ratio <= threshold:
                # Calculate reorder quantity
                velocity = sales_velocity.get(product_id, {})
                avg_daily_sales = velocity.get("avg_daily_sales", 1)
                lead_time_days = inv_data.get("lead_time_days", 7)
                safety_stock = avg_daily_sales * lead_time_days * 2

                reorder_qty = max_qty - current_qty + safety_stock

                purchase_orders.append({
                    "product_id": product_id,
                    "quantity": int(reorder_qty),
                    "supplier_id": inv_data.get("preferred_supplier"),
                    "priority": "high" if stock_ratio < 0.1 else "normal"
                })

        return {
            "action": {
                "type": "create_purchase_orders",
                "purchase_orders": purchase_orders
            },
            "confidence": 0.85,
            "reasoning": f"Generated {len(purchase_orders)} purchase orders for low stock items"
        }

    async def _get_current_inventory(
        self,
        products: List[str],
        warehouse_id: Optional[str]
    ) -> Dict[str, Any]:
        """Get current inventory data."""
        # Placeholder implementation
        return {
            pid: {
                "quantity": 50,
                "max_quantity": 100,
                "lead_time_days": 7,
                "preferred_supplier": "SUP-001"
            }
            for pid in products
        }

    async def _get_sales_velocity(
        self,
        products: List[str],
        days: int
    ) -> Dict[str, Any]:
        """Get sales velocity data."""
        # Placeholder implementation
        return {
            pid: {
                "avg_daily_sales": 10.0,
                "trend": "stable"
            }
            for pid in products
        }

    async def _create_purchase_order(
        self,
        po_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Create purchase order."""
        return {
            "success": True,
            "po_id": f"PO-{context.trace_id[:8]}",
            "product_id": po_data["product_id"],
            "quantity": po_data["quantity"]
        }
