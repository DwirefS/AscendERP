"""
Inventory Agent for the Manufacturing flavor.

Three deterministic capabilities:

1. ABC classification by annual usage value (annual demand x unit cost),
   classic Pareto cutoffs on the cumulative value share BEFORE each item:
   < 80% -> A, < 95% -> B, otherwise C. When annual demand is not provided
   for a material we assume 4 inventory turns/year (annual ~ 4 * on_hand).

2. Safety stock = z * sigma_d * sqrt(lead_time_days).
   Assumptions (documented): daily demand is i.i.d. normal with standard
   deviation sigma_d (units/day), lead time is deterministic and expressed in
   days, z is the standard-normal quantile of the target cycle service level
   (default z = 1.65 ~ 95%). When sigma_d is not provided we assume a
   coefficient of variation of 25% of mean daily demand
   (sigma_d = 0.25 * annual_demand / 365).

3. Shortage projection: explodes the BOMs of open work orders (the provided
   schedule/demand) and nets against on_hand + on_order.
"""
import math
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext
from flavors.manufacturing.models import (
    InventoryItem,
    Product,
    WorkOrder,
    WorkOrderStatus,
)

logger = structlog.get_logger()

_DEFAULT_Z = 1.65          # ~95% cycle service level
_DEFAULT_TURNS = 4.0       # assumed annual inventory turns when demand unknown
_DEFAULT_CV = 0.25         # assumed daily-demand coefficient of variation

_OPEN_STATUSES = (WorkOrderStatus.PLANNED, WorkOrderStatus.RELEASED)


class InventoryAgent(BaseAgent):
    """ABC classification, safety-stock calculation, shortage projection."""

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Inventory Agent",
                description=(
                    "ABC classification, safety-stock sizing and shortage "
                    "projection against the production plan"
                ),
                tools=[
                    "classify_abc",
                    "compute_safety_stock",
                    "project_shortages",
                ],
                max_iterations=5,
                timeout_seconds=120,
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Parse inventory state, demand statistics and the open plan."""
        logger.info(
            "perceiving_inventory_request",
            trace_id=context.trace_id,
            items=len(input_data.get("inventory", [])),
        )

        products: List[Product] = list(input_data.get("products", []))

        return {
            "inventory": list(input_data.get("inventory", [])),
            "annual_demand": dict(input_data.get("annual_demand", {})),
            "demand_sigma": dict(input_data.get("demand_sigma", {})),
            "service_level_z": float(
                input_data.get("service_level_z", _DEFAULT_Z)
            ),
            "work_orders": [
                wo for wo in input_data.get("work_orders", [])
                if wo.status in _OPEN_STATUSES
            ],
            "products": {p.product_id: p for p in products},
        }

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Retrieve inventory policies when memory is available."""
        retrieved: Dict[str, Any] = {}

        if self.memory:
            semantic = await self.memory.retrieve_semantic(
                query="inventory stocking policies",
                tenant_id=context.tenant_id,
                limit=5,
            )
            retrieved["stocking_policies"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Decide on the analysis action. Deterministic without an LLM."""
        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=(
                        "You are an inventory analyst. Review stocking levels "
                        f"for {len(perception['inventory'])} materials."
                    ),
                    max_tokens=self.config.max_tokens,
                    temperature=0.2,
                )
                return {
                    "action": {
                        "type": "analyze_inventory",
                        "inputs": perception,
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get(
                        "reasoning", "LLM-assisted inventory review"
                    ),
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed", error=str(e), fallback="deterministic"
                )

        return {
            "action": {
                "type": "analyze_inventory",
                "inputs": perception,
            },
            "confidence": 0.82,
            "reasoning": (
                "Deterministic ABC classification (80/95 Pareto cutoffs), "
                "safety stock z*sigma_d*sqrt(LT) and BOM-based shortage "
                "projection"
            ),
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext,
    ) -> Any:
        """Run ABC classification, safety-stock sizing and shortage projection."""
        inputs = action.get("inputs", {})
        inventory: List[InventoryItem] = inputs.get("inventory", [])
        annual_demand: Dict[str, float] = inputs.get("annual_demand", {})
        demand_sigma: Dict[str, float] = inputs.get("demand_sigma", {})
        z: float = inputs.get("service_level_z", _DEFAULT_Z)
        work_orders: List[WorkOrder] = inputs.get("work_orders", [])
        products: Dict[str, Product] = inputs.get("products", {})

        abc_classes, usage_values = self.classify_abc(inventory, annual_demand)
        safety_stocks = {
            item.material_id: round(
                self.compute_safety_stock(item, annual_demand, demand_sigma, z), 3
            )
            for item in inventory
        }
        shortages = self._project_shortages(work_orders, products, inventory)

        return {
            "analyzed": True,
            "abc_classes": abc_classes,
            "usage_values": usage_values,
            "safety_stocks": safety_stocks,
            "projected_shortages": shortages,
            "summary": {
                "items": len(inventory),
                "class_a": sum(1 for c in abc_classes.values() if c == "A"),
                "class_b": sum(1 for c in abc_classes.values() if c == "B"),
                "class_c": sum(1 for c in abc_classes.values() if c == "C"),
                "shortage_count": len(shortages),
            },
        }

    async def verify(
        self,
        result: Any,
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Verify all items were classified."""
        summary = result.get("summary", {})
        classified = (
            summary.get("class_a", 0)
            + summary.get("class_b", 0)
            + summary.get("class_c", 0)
        )
        all_classified = classified == summary.get("items", 0)

        return {
            "complete": result.get("analyzed", False),
            "quality_score": 1.0 if all_classified else 0.5,
            "metrics": {
                "items_classified": classified,
                "shortage_count": summary.get("shortage_count", 0),
            },
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext,
    ):
        """Persist analysis outcomes when memory is available."""
        if not self.memory or not actions_taken:
            return

        last_result = actions_taken[-1].get("result", {})
        await self.memory.store_episodic(
            content={
                "summary": last_result.get("summary"),
                "abc_classes": last_result.get("abc_classes"),
                "trace_id": context.trace_id,
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id,
        )

    # ------------------------------------------------------------------
    # Deterministic inventory mathematics
    # ------------------------------------------------------------------

    @staticmethod
    def classify_abc(
        inventory: List[InventoryItem],
        annual_demand: Dict[str, float],
    ):
        """
        ABC classification by annual usage value (annual demand * unit cost).
        Cutoffs on cumulative value share before each item: <80% A, <95% B,
        else C. Unknown demand falls back to 4 turns/year (~4 * on_hand).
        """
        usage_values: Dict[str, float] = {}
        for item in inventory:
            demand = annual_demand.get(
                item.material_id, _DEFAULT_TURNS * item.on_hand
            )
            usage_values[item.material_id] = round(demand * item.unit_cost, 2)

        total_value = sum(usage_values.values())
        abc: Dict[str, str] = {}
        cumulative = 0.0
        for material_id, value in sorted(
            usage_values.items(), key=lambda kv: kv[1], reverse=True
        ):
            share_before = cumulative / total_value if total_value > 0 else 0.0
            if share_before < 0.80:
                abc[material_id] = "A"
            elif share_before < 0.95:
                abc[material_id] = "B"
            else:
                abc[material_id] = "C"
            cumulative += value

        return abc, usage_values

    @staticmethod
    def compute_safety_stock(
        item: InventoryItem,
        annual_demand: Dict[str, float],
        demand_sigma: Dict[str, float],
        z: float,
    ) -> float:
        """
        Safety stock = z * sigma_d * sqrt(lead_time_days).
        sigma_d defaults to 25% of mean daily demand when not supplied.
        """
        sigma_d = demand_sigma.get(item.material_id)
        if sigma_d is None:
            daily_demand = annual_demand.get(item.material_id, 0.0) / 365.0
            sigma_d = _DEFAULT_CV * daily_demand
        lead_time = max(item.lead_time_days, 0.0)
        return z * sigma_d * math.sqrt(lead_time)

    @staticmethod
    def _project_shortages(
        work_orders: List[WorkOrder],
        products: Dict[str, Product],
        inventory: List[InventoryItem],
    ) -> List[Dict[str, Any]]:
        """Project material shortages from open work orders' BOM demand."""
        requirements: Dict[str, float] = {}
        for wo in work_orders:
            product = products.get(wo.product_id)
            if product is None:
                continue
            remaining = max(wo.quantity - wo.completed_quantity, 0.0)
            for line in product.bom:
                requirements[line.material_id] = (
                    requirements.get(line.material_id, 0.0)
                    + line.quantity_per_unit * remaining
                )

        available = {
            item.material_id: item.on_hand + item.on_order for item in inventory
        }
        shortages = []
        for material_id, required in sorted(requirements.items()):
            avail = available.get(material_id, 0.0)
            if required > avail:
                shortages.append({
                    "material_id": material_id,
                    "required": round(required, 3),
                    "available": round(avail, 3),
                    "shortage": round(required - avail, 3),
                })
        return shortages
