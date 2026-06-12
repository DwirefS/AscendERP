"""
Supply Disruption Response Workflow for the Manufacturing flavor.

Stages (per design §4):
    swarm_scenario (lazy import of the swarm engine; deterministic heuristic
    report when absent) -> sop_council (with the scenario report as evidence)
    -> revised_plan -> expedited_pos (ProcurementAgent)

Follows the capital-markets workflow style: an async run() that drives named
stages and returns a stage-results dict.
"""
import uuid
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import AgentContext
from flavors.manufacturing.agents.procurement_agent import ProcurementAgent
from flavors.manufacturing.councils.sop_council import SOPCouncil
from flavors.manufacturing.models import (
    Priority,
    Supplier,
    WorkOrder,
    WorkOrderStatus,
)

logger = structlog.get_logger()


class SupplyDisruptionResponseWorkflow:
    """Shock -> swarm scenario -> S&OP council -> revised plan + expedited POs."""

    def __init__(
        self,
        sop_council: Optional[SOPCouncil] = None,
        procurement_agent: Optional[ProcurementAgent] = None,
    ):
        self.sop_council = sop_council or SOPCouncil()
        self.procurement_agent = procurement_agent or ProcurementAgent()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected input:
        {
            "shock": {"type": "supplier_outage"|"demand_spike"|"machine_failure", ...},
            "inventory": [InventoryItem], "suppliers": [Supplier],
            "work_orders": [WorkOrder], "products": [Product],
            "plan"?: dict  # current plan summary for the council
        }
        """
        trace_id = f"sdr-{uuid.uuid4().hex[:8]}"
        context = AgentContext(trace_id=trace_id, tenant_id="manufacturing")
        stages: Dict[str, Any] = {}
        errors: List[str] = []

        shock: Dict[str, Any] = dict(input_data.get("shock", {}))
        suppliers: List[Supplier] = list(input_data.get("suppliers", []))
        work_orders: List[WorkOrder] = list(input_data.get("work_orders", []))
        products = {p.product_id: p for p in input_data.get("products", [])}
        affected_materials = self._affected_materials(shock, suppliers, products)

        # Stage 1: swarm scenario simulation (lazy import, graceful skip)
        report, source = self._run_scenario(shock, input_data)
        stages["swarm_scenario"] = {
            "skipped": source != "swarm",
            "source": source,
            "report": report,
        }
        logger.info(
            "sdr_scenario", trace_id=trace_id, source=source,
            risks=len(report.get("risks", [])),
        )

        # Stage 2: S&OP council with the scenario report as evidence
        plan = input_data.get("plan") or {
            "open_work_orders": len(work_orders),
            "shortages": [
                {"material_id": m} for m in sorted(affected_materials)
            ],
            "shock": shock,
        }
        decision = await self.sop_council.decide(plan, report)
        stages["sop_council"] = {"decision": decision}

        # Stage 3: revised plan — expedite affected work orders
        expedited_wos = []
        affected_products = {
            pid for pid, p in products.items()
            if {line.material_id for line in p.bom} & affected_materials
        }
        if shock.get("type") == "demand_spike" and shock.get("product_id"):
            affected_products.add(shock["product_id"])
        for wo in work_orders:
            if wo.status in (WorkOrderStatus.PLANNED, WorkOrderStatus.RELEASED) \
                    and wo.product_id in affected_products:
                if wo.priority.value < Priority.HIGH.value:
                    wo.priority = Priority.HIGH
                expedited_wos.append(wo.work_order_id)
        stages["revised_plan"] = {
            "affected_materials": sorted(affected_materials),
            "affected_products": sorted(affected_products),
            "expedited_work_orders": expedited_wos,
            "adjustments": decision.get("adjustments", []),
        }

        # Stage 4: expedited POs via the procurement agent
        demand_boost = {
            item.material_id: item.reorder_point + item.safety_stock + 1.0
            for item in input_data.get("inventory", [])
            if item.material_id in affected_materials
        }
        exclude = []
        if shock.get("type") == "supplier_outage" and shock.get("supplier_id"):
            exclude.append(shock["supplier_id"])

        proc_result = await self.procurement_agent.run({
            "inventory": input_data.get("inventory", []),
            "suppliers": suppliers,
            "demand": demand_boost,
            "exclude_suppliers": exclude,
        }, context)

        if proc_result.success:
            pos = proc_result.output.get("purchase_orders", [])
            stages["expedited_pos"] = {
                "success": True,
                "purchase_orders": [po.po_id for po in pos],
                "pending_approval": [
                    po.po_id for po in pos
                    if po.status.value == "pending_approval"
                ],
                "excluded_suppliers": exclude,
            }
        else:
            pos = []
            errors.append(proc_result.error or "procurement agent failed")
            stages["expedited_pos"] = {"success": False}

        return {
            "status": "completed" if not errors else "completed_with_errors",
            "trace_id": trace_id,
            "stages": stages,
            "errors": errors,
            "scenario_report": report,
            "council_decision": decision,
            "expedited_purchase_orders": pos,
        }

    # ------------------------------------------------------------------

    def _run_scenario(
        self,
        shock: Dict[str, Any],
        input_data: Dict[str, Any],
    ):
        """Run the swarm engine when available, else a heuristic report."""
        try:
            from flavors.manufacturing.simulation.swarm import SwarmWorld
            from flavors.manufacturing.data.seed import FactorySeed
            from flavors.manufacturing.models import SimulationScenario
        except ImportError as e:
            logger.info("sdr_swarm_unavailable", reason=str(e))
            return self._heuristic_report(shock), "heuristic_fallback"

        try:
            from datetime import datetime as _dt
            seed_data = FactorySeed(
                seed=int(input_data.get("seed", 42)),
                anchor=input_data.get("now") or _dt.utcnow(),
                machines=list(input_data.get("machines", [])),
                products=list(input_data.get("products", [])),
                inventory=list(input_data.get("inventory", [])),
                suppliers=list(input_data.get("suppliers", [])),
                work_orders=list(input_data.get("work_orders", [])),
                customer_ids=list(input_data.get("customer_ids", ["CUST-1"])),
            )
            world = SwarmWorld.from_seed(seed_data)
            report = world.run_scenario(SimulationScenario(
                name=f"shock_{shock.get('type', 'unknown')}",
                narrative=str(shock),
                shock=shock,
                horizon_days=int(input_data.get("horizon_days", 30)),
            ))
            return report.summary(), "swarm"
        except Exception as e:
            logger.warning("sdr_swarm_failed", error=str(e))
            return self._heuristic_report(shock), "heuristic_fallback"

    @staticmethod
    def _heuristic_report(shock: Dict[str, Any]) -> Dict[str, Any]:
        """Deterministic fallback scenario report derived from the shock."""
        shock_type = shock.get("type", "unknown")
        risks: List[str] = []
        recommendations: List[str] = []
        kpi_impact: Dict[str, float] = {}

        if shock_type == "supplier_outage":
            supplier = shock.get("supplier_id", "unknown supplier")
            days = shock.get("days", 14)
            risks = [
                f"Supplier {supplier} outage for ~{days} days starves "
                "dependent materials",
                "On-time delivery degrades once buffer stock is consumed",
            ]
            recommendations = [
                "Expedite purchase orders with alternate suppliers",
                "Prioritize work orders consuming the constrained materials",
            ]
            kpi_impact = {"otd_rate": -0.12, "total_cost": 0.05}
        elif shock_type == "demand_spike":
            product = shock.get("product_id", "unknown product")
            factor = shock.get("factor", 1.5)
            risks = [
                f"Demand spike x{factor} on {product} exceeds planned capacity",
                "Component inventory for the spiked product depletes early",
            ]
            recommendations = [
                "Raise reorder quantities for the product's BOM materials",
                "Add overtime or shift capacity at the bottleneck work center",
            ]
            kpi_impact = {"otd_rate": -0.08, "throughput_units": 0.2}
        elif shock_type == "machine_failure":
            machine = shock.get("machine_id", "unknown machine")
            risks = [
                f"Machine {machine} unavailable reduces work-center capacity",
                "Schedule slip on routings through the failed machine",
            ]
            recommendations = [
                "Reroute operations to alternate machines",
                "Schedule corrective maintenance in the next downtime window",
            ]
            kpi_impact = {"oee": -0.1, "makespan_hours": 0.15}
        else:
            risks = [f"Unmodeled shock '{shock_type}': impact uncertain"]
            recommendations = ["Convene S&OP council and monitor KPIs daily"]

        return {
            "scenario": f"heuristic_{shock_type}",
            "risks": risks,
            "recommendations": recommendations,
            "kpi_impact": kpi_impact,
            "confidence": 0.4,
        }

    @staticmethod
    def _affected_materials(
        shock: Dict[str, Any],
        suppliers: List[Supplier],
        products: Dict[str, Any],
    ) -> set:
        """Materials put at risk by the shock."""
        affected: set = set()
        shock_type = shock.get("type")

        if shock_type == "supplier_outage":
            supplier_id = shock.get("supplier_id")
            for supplier in suppliers:
                if supplier.supplier_id == supplier_id:
                    affected.update(supplier.materials)
        elif shock_type == "demand_spike":
            product = products.get(shock.get("product_id"))
            if product is not None:
                affected.update(line.material_id for line in product.bom)
        if shock.get("material_ids"):
            affected.update(shock["material_ids"])
        return affected
