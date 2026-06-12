"""
Order-to-Production Workflow for the Manufacturing flavor.

Stages (per design §4):
    order_intake -> mrp_planning (ProductionPlannerAgent) -> release_work_orders
    -> simulate (optional, lazy import of the plant simulator; skipped
       gracefully when absent) -> kpi_summary

Follows the capital-markets workflow style: an async run() that drives named
stages and returns a stage-results dict.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import AgentContext
from flavors.manufacturing.agents.production_planner_agent import (
    ProductionPlannerAgent,
)
from flavors.manufacturing.models import (
    Priority,
    WorkOrder,
    WorkOrderStatus,
)

logger = structlog.get_logger()


class OrderToProductionWorkflow:
    """Order intake through schedule release, simulation and KPI summary."""

    def __init__(self, planner: Optional[ProductionPlannerAgent] = None):
        self.planner = planner or ProductionPlannerAgent()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected input:
        {
            "orders": [{"product_id", "quantity", "due_date", "priority"?}],
            "work_orders": [WorkOrder]  (optional pre-existing),
            "products": [Product], "inventory": [InventoryItem],
            "machines": [Machine], "policy"?: SchedulingPolicy|dict,
            "horizon_hours"?: float, "simulate"?: bool
        }
        """
        trace_id = f"o2p-{uuid.uuid4().hex[:8]}"
        context = AgentContext(trace_id=trace_id, tenant_id="manufacturing")
        now = input_data.get("now") or datetime.utcnow()
        stages: Dict[str, Any] = {}
        errors: List[str] = []

        # Stage 1: order intake -> work orders
        work_orders: List[WorkOrder] = list(input_data.get("work_orders", []))
        created = 0
        for order in input_data.get("orders", []):
            priority = order.get("priority", Priority.NORMAL)
            if isinstance(priority, int):
                priority = Priority(priority)
            work_orders.append(WorkOrder.new(
                product_id=order["product_id"],
                quantity=float(order["quantity"]),
                due_date=order["due_date"],
                priority=priority,
                customer_id=order.get("customer_id"),
            ))
            created += 1
        stages["order_intake"] = {
            "orders_received": created,
            "open_work_orders": len(work_orders),
        }
        logger.info("o2p_order_intake", trace_id=trace_id, created=created)

        # Stage 2: MRP planning + scheduling via the planner agent
        plan_result = await self.planner.run({
            "work_orders": work_orders,
            "products": input_data.get("products", []),
            "inventory": input_data.get("inventory", []),
            "machines": input_data.get("machines", []),
            "policy": input_data.get("policy"),
            "horizon_hours": input_data.get("horizon_hours", 80.0),
            "now": now,
        }, context)

        if not plan_result.success:
            errors.append(plan_result.error or "planner failed")
            stages["mrp_planning"] = {"success": False}
            return {
                "status": "failed",
                "trace_id": trace_id,
                "stages": stages,
                "errors": errors,
            }

        plan = plan_result.output
        schedule = plan["schedule"]
        stages["mrp_planning"] = {
            "success": True,
            "material_requirements": plan["material_requirements"],
            "shortages": plan["shortages"],
            "capacity": plan["capacity"],
            "scheduler": plan["summary"]["scheduler"],
            "scheduled_entries": len(schedule.entries),
            "confidence": plan_result.confidence,
        }

        # Stage 3: release work orders (hold orders blocked by shortages)
        blocked_materials = {s["material_id"] for s in plan["shortages"]}
        products_by_id = {
            p.product_id: p for p in input_data.get("products", [])
        }
        released, held = [], []
        for wo in work_orders:
            if wo.status != WorkOrderStatus.PLANNED:
                continue
            product = products_by_id.get(wo.product_id)
            bom_materials = {
                line.material_id for line in (product.bom if product else [])
            }
            if bom_materials & blocked_materials:
                wo.status = WorkOrderStatus.ON_HOLD
                held.append(wo.work_order_id)
            else:
                wo.status = WorkOrderStatus.RELEASED
                wo.released_at = now
                released.append(wo.work_order_id)
        stages["release_work_orders"] = {"released": released, "held": held}
        logger.info(
            "o2p_release", trace_id=trace_id,
            released=len(released), held=len(held),
        )

        # Stage 4: optional simulation (lazy import; skip gracefully)
        sim_kpis = None
        if input_data.get("simulate", True):
            stages["simulate"] = self._try_simulate(
                input_data, work_orders, schedule
            )
            sim_kpis = stages["simulate"].get("kpis")
        else:
            stages["simulate"] = {"skipped": True, "reason": "disabled by input"}

        # Stage 5: KPI summary
        stages["kpi_summary"] = self._kpi_summary(
            work_orders, schedule, sim_kpis
        )

        return {
            "status": "completed",
            "trace_id": trace_id,
            "stages": stages,
            "errors": errors,
            "schedule": schedule,
            "work_orders": work_orders,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _try_simulate(
        input_data: Dict[str, Any],
        work_orders: List[WorkOrder],
        schedule,
    ) -> Dict[str, Any]:
        """Run the plant simulator when available; otherwise skip gracefully."""
        try:
            from flavors.manufacturing.simulation.plant import PlantSimulator
        except ImportError as e:
            logger.info("o2p_simulator_unavailable", reason=str(e))
            return {"skipped": True, "reason": "plant simulator not available"}

        try:
            sim = PlantSimulator(seed=int(input_data.get("seed", 42)))
            sim.load(
                input_data.get("machines", []),
                work_orders,
                input_data.get("inventory", []),
            )
            result = sim.run(
                schedule,
                horizon_hours=float(input_data.get("horizon_hours", 80.0)),
            )
            return {
                "skipped": False,
                "kpis": result.kpis.to_dict(),
                "events": len(result.events),
            }
        except Exception as e:
            logger.warning("o2p_simulation_failed", error=str(e))
            return {"skipped": True, "reason": f"simulation failed: {e}"}

    @staticmethod
    def _kpi_summary(
        work_orders: List[WorkOrder],
        schedule,
        sim_kpis: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """KPI summary from simulation when present, else from the schedule."""
        if sim_kpis:
            return {"source": "simulation", "kpis": sim_kpis}

        wo_by_id = {wo.work_order_id: wo for wo in work_orders}
        last_op_end: Dict[str, datetime] = {}
        for entry in schedule.entries:
            current = last_op_end.get(entry.work_order_id)
            if current is None or entry.end > current:
                last_op_end[entry.work_order_id] = entry.end

        on_time = sum(
            1 for wo_id, end in last_op_end.items()
            if wo_id in wo_by_id and end <= wo_by_id[wo_id].due_date
        )
        scheduled = len(last_op_end)
        makespan_hours = 0.0
        if schedule.entries:
            start = min(e.start for e in schedule.entries)
            end = max(e.end for e in schedule.entries)
            makespan_hours = (end - start).total_seconds() / 3600.0

        return {
            "source": "schedule_estimate",
            "kpis": {
                "planned_units": round(sum(wo.quantity for wo in work_orders), 2),
                "scheduled_work_orders": scheduled,
                "otd_rate": round(on_time / scheduled, 4) if scheduled else 0.0,
                "makespan_hours": round(makespan_hours, 2),
            },
        }
