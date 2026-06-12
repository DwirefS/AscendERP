"""
Procurement Agent for the Manufacturing flavor.

Reorder-point purchasing across InventoryItems, weighted supplier scoring and
PurchaseOrder generation with a policy approval threshold.

Reorder policy (documented):
    inventory position = on_hand + on_order - committed demand
    breach when position <= reorder_point
    order-up-to target  = 2 * reorder_point + safety_stock
    order quantity      = ceil(target - position), minimum 1

Supplier score (documented weights, all components normalized to [0, 1]):
    otd_score    = otd_rate
    defect_score = max(0, 1 - defect_ppm / 10000)
    price_score  = clamp(2 - price_index, 0, 1)   # 1.0 at market avg, 0 at 2x
    lead_score   = max(0, 1 - lead_time_days / 30)
    score = 0.35*otd + 0.25*defect + 0.20*price + 0.20*lead

Policy threshold: purchase orders with total_cost > 50,000 get status
PENDING_APPROVAL; smaller orders are auto-APPROVED.
"""
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext
from flavors.manufacturing.models import (
    InventoryItem,
    POStatus,
    PurchaseOrder,
    Supplier,
)

logger = structlog.get_logger()

PO_APPROVAL_THRESHOLD = 50_000.0

_W_OTD = 0.35
_W_DEFECT = 0.25
_W_PRICE = 0.20
_W_LEAD = 0.20


class ProcurementAgent(BaseAgent):
    """Reorder-point checks, supplier scoring and PO generation."""

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Procurement Agent",
                description=(
                    "Reorder-point purchasing with weighted supplier scoring "
                    "and approval-threshold policy"
                ),
                tools=[
                    "check_reorder_points",
                    "score_suppliers",
                    "generate_purchase_order",
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
        """Parse inventory, suppliers and demand commitments."""
        logger.info(
            "perceiving_procurement_request",
            trace_id=context.trace_id,
            items=len(input_data.get("inventory", [])),
            suppliers=len(input_data.get("suppliers", [])),
        )

        return {
            "inventory": list(input_data.get("inventory", [])),
            "suppliers": list(input_data.get("suppliers", [])),
            "demand": dict(input_data.get("demand", {})),
            "exclude_suppliers": set(input_data.get("exclude_suppliers", [])),
            "approval_threshold": float(
                input_data.get("approval_threshold", PO_APPROVAL_THRESHOLD)
            ),
            "now": input_data.get("now") or datetime.utcnow(),
        }

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Retrieve supplier performance history when memory is available."""
        retrieved: Dict[str, Any] = {}

        if self.memory:
            semantic = await self.memory.retrieve_semantic(
                query="supplier performance and sourcing rules",
                tenant_id=context.tenant_id,
                limit=5,
            )
            retrieved["sourcing_rules"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Decide on the replenishment action. Deterministic without an LLM."""
        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=(
                        "You are a procurement expert. Review reorder needs for "
                        f"{len(perception['inventory'])} items across "
                        f"{len(perception['suppliers'])} suppliers."
                    ),
                    max_tokens=self.config.max_tokens,
                    temperature=0.2,
                )
                return {
                    "action": {
                        "type": "replenish_inventory",
                        "inputs": perception,
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get(
                        "reasoning", "LLM-assisted sourcing review"
                    ),
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed", error=str(e), fallback="deterministic"
                )

        return {
            "action": {
                "type": "replenish_inventory",
                "inputs": perception,
            },
            "confidence": 0.8,
            "reasoning": (
                "Deterministic reorder-point check with weighted supplier "
                "scoring (otd 0.35, defects 0.25, price 0.20, lead time 0.20)"
            ),
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext,
    ) -> Any:
        """Check reorder points, pick suppliers and generate POs."""
        inputs = action.get("inputs", {})
        inventory: List[InventoryItem] = inputs.get("inventory", [])
        suppliers: List[Supplier] = inputs.get("suppliers", [])
        demand: Dict[str, float] = inputs.get("demand", {})
        excluded: set = inputs.get("exclude_suppliers", set())
        threshold: float = inputs.get("approval_threshold", PO_APPROVAL_THRESHOLD)
        now: datetime = inputs.get("now", datetime.utcnow())

        supplier_scores = {
            s.supplier_id: round(self.score_supplier(s), 4) for s in suppliers
        }

        breaches: List[Dict[str, Any]] = []
        purchase_orders: List[PurchaseOrder] = []
        unsourced: List[str] = []

        for item in inventory:
            position = item.on_hand + item.on_order - demand.get(
                item.material_id, 0.0
            )
            if position > item.reorder_point:
                continue

            target = 2.0 * item.reorder_point + item.safety_stock
            quantity = max(1.0, math.ceil(target - position))
            breaches.append({
                "material_id": item.material_id,
                "position": round(position, 3),
                "reorder_point": item.reorder_point,
                "order_quantity": quantity,
            })

            supplier = self._select_supplier(
                item, suppliers, supplier_scores, excluded
            )
            if supplier is None:
                unsourced.append(item.material_id)
                logger.warning(
                    "no_supplier_for_material",
                    trace_id=context.trace_id,
                    material_id=item.material_id,
                )
                continue

            unit_cost = item.unit_cost * supplier.price_index
            po = PurchaseOrder.new(
                supplier_id=supplier.supplier_id,
                material_id=item.material_id,
                quantity=quantity,
                unit_cost=unit_cost,
                needed_by=now + timedelta(days=supplier.lead_time_days),
            )
            # Policy threshold: large POs need human approval.
            po.status = (
                POStatus.PENDING_APPROVAL
                if po.total_cost > threshold
                else POStatus.APPROVED
            )
            purchase_orders.append(po)
            logger.info(
                "purchase_order_generated",
                trace_id=context.trace_id,
                po_id=po.po_id,
                material_id=item.material_id,
                supplier_id=supplier.supplier_id,
                total_cost=round(po.total_cost, 2),
                status=po.status.value,
            )

        return {
            "generated": True,
            "reorder_breaches": breaches,
            "purchase_orders": purchase_orders,
            "supplier_scores": supplier_scores,
            "unsourced_materials": unsourced,
            "summary": {
                "breaches": len(breaches),
                "pos_created": len(purchase_orders),
                "pending_approval": sum(
                    1 for po in purchase_orders
                    if po.status == POStatus.PENDING_APPROVAL
                ),
                "approval_threshold": threshold,
            },
        }

    async def verify(
        self,
        result: Any,
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Verify every sourced breach produced a PO."""
        breaches = result.get("reorder_breaches", [])
        pos = result.get("purchase_orders", [])
        unsourced = result.get("unsourced_materials", [])
        covered = len(pos) + len(unsourced) >= len(breaches)

        return {
            "complete": result.get("generated", False),
            "quality_score": 1.0 if covered and not unsourced else 0.7,
            "metrics": {
                "breaches": len(breaches),
                "pos_created": len(pos),
                "unsourced": len(unsourced),
            },
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext,
    ):
        """Persist sourcing outcomes when memory is available."""
        if not self.memory or not actions_taken:
            return

        last_result = actions_taken[-1].get("result", {})
        await self.memory.store_episodic(
            content={
                "summary": last_result.get("summary"),
                "supplier_scores": last_result.get("supplier_scores"),
                "trace_id": context.trace_id,
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id,
        )

    # ------------------------------------------------------------------
    # Deterministic sourcing internals
    # ------------------------------------------------------------------

    @staticmethod
    def score_supplier(supplier: Supplier) -> float:
        """
        Weighted supplier score in [0, 1]:
        0.35*otd_rate + 0.25*(1 - defect_ppm/10000)
        + 0.20*clamp(2 - price_index, 0, 1) + 0.20*(1 - lead_time_days/30).
        """
        otd_score = min(max(supplier.otd_rate, 0.0), 1.0)
        defect_score = max(0.0, 1.0 - supplier.defect_ppm / 10_000.0)
        price_score = min(max(2.0 - supplier.price_index, 0.0), 1.0)
        lead_score = max(0.0, 1.0 - supplier.lead_time_days / 30.0)
        return (
            _W_OTD * otd_score
            + _W_DEFECT * defect_score
            + _W_PRICE * price_score
            + _W_LEAD * lead_score
        )

    @staticmethod
    def _select_supplier(
        item: InventoryItem,
        suppliers: List[Supplier],
        scores: Dict[str, float],
        excluded: set,
    ) -> Optional[Supplier]:
        """Pick the best-scoring eligible supplier for a material."""
        candidates = [
            s for s in suppliers
            if item.material_id in s.materials and s.supplier_id not in excluded
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda s: (
                scores.get(s.supplier_id, 0.0),
                s.supplier_id == item.preferred_supplier_id,
            ),
        )
