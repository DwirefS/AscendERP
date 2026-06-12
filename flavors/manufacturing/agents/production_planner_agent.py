"""
Production Planner Agent for the Manufacturing flavor.

MRP-lite planning: explodes product BOMs for open work orders, nets gross
requirements against inventory (on_hand + on_order), builds a production
schedule (via PolicyScheduler when the simulation module is available, with a
deterministic EDD fallback otherwise), and flags capacity overload per work
center (required hours vs available hours).

Implements the PRREEL loop (perceive/retrieve/reason/execute/verify/learn)
and works fully without an LLM or memory substrate.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext
from flavors.manufacturing.models import (
    Machine,
    Product,
    InventoryItem,
    WorkOrder,
    WorkOrderStatus,
    ProductionSchedule,
    ScheduleEntry,
    SchedulingPolicy,
)

logger = structlog.get_logger()

_OPEN_STATUSES = (WorkOrderStatus.PLANNED, WorkOrderStatus.RELEASED)


class ProductionPlannerAgent(BaseAgent):
    """
    Agent for MRP-lite production planning.

    Output of a full run:
    {
        "material_requirements": {material_id: gross_qty},
        "shortages": [{"material_id", "required", "available", "shortage"}],
        "schedule": ProductionSchedule,
        "capacity": {work_center: {"required_hours", "available_hours",
                                   "utilization", "overloaded"}},
        "summary": {...}
    }
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Production Planner Agent",
                description="MRP-lite planning, scheduling and capacity checks",
                tools=[
                    "explode_bom",
                    "net_inventory",
                    "build_schedule",
                    "check_capacity",
                ],
                max_iterations=5,
                timeout_seconds=300,
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Parse the planning request into typed plan inputs."""
        logger.info(
            "perceiving_planning_request",
            trace_id=context.trace_id,
            input_keys=list(input_data.keys()),
        )

        policy = input_data.get("policy") or SchedulingPolicy()
        if isinstance(policy, dict):
            policy = SchedulingPolicy.from_dict(policy)

        work_orders: List[WorkOrder] = [
            wo for wo in input_data.get("work_orders", [])
            if wo.status in _OPEN_STATUSES
        ]
        products: List[Product] = list(input_data.get("products", []))

        return {
            "work_orders": work_orders,
            "products": {p.product_id: p for p in products},
            "inventory": list(input_data.get("inventory", [])),
            "machines": list(input_data.get("machines", [])),
            "policy": policy,
            "horizon_hours": float(input_data.get("horizon_hours", 80.0)),
            "now": input_data.get("now") or datetime.utcnow(),
        }

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Retrieve past planning patterns when memory is available."""
        retrieved: Dict[str, Any] = {}

        if self.memory:
            procedural = await self.memory.retrieve_procedural(
                context={"task": "production_planning"},
                agent_id=self.config.agent_id,
                limit=5,
            )
            retrieved["past_plans"] = [p.content for p in procedural]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Decide on the planning action. Deterministic without an LLM."""
        policy: SchedulingPolicy = perception["policy"]
        open_count = len(perception["work_orders"])

        if self.llm:
            try:
                prompt = (
                    "You are a production planning expert. "
                    f"Plan {open_count} open work orders with dispatch rule "
                    f"{policy.dispatch_rule}. Past plans: "
                    f"{retrieved_context.get('past_plans', [])}"
                )
                response = await self.llm.generate(
                    prompt=prompt,
                    max_tokens=self.config.max_tokens,
                    temperature=0.2,
                )
                return {
                    "action": {
                        "type": "plan_production",
                        "policy": policy.to_dict(),
                        "plan_inputs": perception,
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get(
                        "reasoning", "LLM-assisted MRP planning"
                    ),
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed", error=str(e), fallback="deterministic"
                )

        # Deterministic fallback: real MRP-lite logic executed in execute().
        return {
            "action": {
                "type": "plan_production",
                "policy": policy.to_dict(),
                "plan_inputs": perception,
            },
            "confidence": 0.8,
            "reasoning": (
                f"Deterministic MRP-lite plan for {open_count} open work orders "
                f"using {policy.dispatch_rule} dispatch"
            ),
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext,
    ) -> Any:
        """Run MRP explosion, netting, scheduling and capacity checks."""
        inputs = action.get("plan_inputs", {})
        work_orders: List[WorkOrder] = inputs.get("work_orders", [])
        products: Dict[str, Product] = inputs.get("products", {})
        inventory: List[InventoryItem] = inputs.get("inventory", [])
        machines: List[Machine] = inputs.get("machines", [])
        policy = SchedulingPolicy.from_dict(action.get("policy", {})) \
            if action.get("policy") else SchedulingPolicy()
        horizon_hours: float = inputs.get("horizon_hours", 80.0)
        now: datetime = inputs.get("now", datetime.utcnow())

        logger.info(
            "executing_mrp_plan",
            trace_id=context.trace_id,
            work_orders=len(work_orders),
            machines=len(machines),
        )

        # 1. BOM explosion -> gross material requirements
        requirements = self._explode_bom(work_orders, products)

        # 2. Net against inventory (on_hand + on_order) -> shortages
        shortages = self._net_against_inventory(requirements, inventory)

        # 3. Build schedule (PolicyScheduler if present, else EDD fallback)
        schedule, scheduler_used = self._build_schedule(
            work_orders, machines, products, policy, now
        )

        # 4. Capacity overload check per work center
        capacity = self._check_capacity(schedule, machines, horizon_hours)

        return {
            "material_requirements": requirements,
            "shortages": shortages,
            "schedule": schedule,
            "capacity": capacity,
            "summary": {
                "generated": True,
                "open_work_orders": len(work_orders),
                "shortage_count": len(shortages),
                "scheduled_entries": len(schedule.entries),
                "overloaded_work_centers": [
                    wc for wc, c in capacity.items() if c["overloaded"]
                ],
                "scheduler": scheduler_used,
            },
        }

    async def verify(
        self,
        result: Any,
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Verify the plan was produced and grade its quality."""
        summary = result.get("summary", {})
        shortage_count = summary.get("shortage_count", 0)
        overloaded = summary.get("overloaded_work_centers", [])

        quality = 1.0
        if shortage_count > 0:
            quality -= 0.2
        if overloaded:
            quality -= 0.2

        return {
            "complete": summary.get("generated", False),
            "quality_score": max(quality, 0.0),
            "metrics": {
                "shortage_count": shortage_count,
                "scheduled_entries": summary.get("scheduled_entries", 0),
                "overloaded_work_centers": len(overloaded),
            },
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext,
    ):
        """Persist successful planning patterns when memory is available."""
        if not self.memory or not actions_taken:
            return

        last_result = actions_taken[-1].get("result", {})
        summary = last_result.get("summary", {})
        if summary.get("generated") and summary.get("shortage_count", 0) == 0:
            await self.memory.store_procedural(
                pattern={
                    "task": "production_planning",
                    "policy": actions_taken[-1].get("action", {}).get("policy"),
                    "open_work_orders": summary.get("open_work_orders"),
                },
                success_rate=0.95,
                agent_id=self.config.agent_id,
                tenant_id=context.tenant_id,
            )

        await self.memory.store_episodic(
            content={
                "input": {"work_orders": len(input_data.get("work_orders", []))},
                "summary": summary,
                "trace_id": context.trace_id,
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id,
        )

    # ------------------------------------------------------------------
    # Deterministic planning internals
    # ------------------------------------------------------------------

    @staticmethod
    def _explode_bom(
        work_orders: List[WorkOrder],
        products: Dict[str, Product],
    ) -> Dict[str, float]:
        """Explode product BOMs into gross material requirements."""
        requirements: Dict[str, float] = {}
        for wo in work_orders:
            product = products.get(wo.product_id)
            if product is None:
                logger.warning("unknown_product", product_id=wo.product_id)
                continue
            remaining = max(wo.quantity - wo.completed_quantity, 0.0)
            for line in product.bom:
                requirements[line.material_id] = (
                    requirements.get(line.material_id, 0.0)
                    + line.quantity_per_unit * remaining
                )
        return requirements

    @staticmethod
    def _net_against_inventory(
        requirements: Dict[str, float],
        inventory: List[InventoryItem],
    ) -> List[Dict[str, Any]]:
        """Net gross requirements against on_hand + on_order inventory."""
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

    def _build_schedule(
        self,
        work_orders: List[WorkOrder],
        machines: List[Machine],
        products: Dict[str, Product],
        policy: SchedulingPolicy,
        now: datetime,
    ):
        """
        Build a schedule with PolicyScheduler if the simulation module exists,
        otherwise fall back to a simple deterministic EDD list schedule.
        """
        try:
            from flavors.manufacturing.simulation.plant import PolicyScheduler
            schedule = PolicyScheduler(policy).build_schedule(
                work_orders, machines, list(products.values()), start_time=now
            )
            return schedule, "policy_scheduler"
        except (ImportError, AttributeError, TypeError, ValueError) as e:
            logger.info(
                "policy_scheduler_unavailable",
                reason=str(e),
                fallback="edd_list_schedule",
            )
            return self._edd_schedule(work_orders, machines, products, now), \
                "edd_fallback"

    @staticmethod
    def _edd_schedule(
        work_orders: List[WorkOrder],
        machines: List[Machine],
        products: Dict[str, Product],
        now: datetime,
    ) -> ProductionSchedule:
        """Earliest-due-date list scheduling fallback."""
        schedule = ProductionSchedule(policy_name="EDD-fallback")
        if not machines:
            return schedule

        machine_free: Dict[str, datetime] = {m.machine_id: now for m in machines}

        for wo in sorted(work_orders, key=lambda w: w.due_date):
            product = products.get(wo.product_id)
            operations = (
                product.routing if product and product.routing else ["general"]
            )
            op_ready = now
            for op in operations:
                capable = [
                    m for m in machines
                    if not m.operations or op in m.operations
                ] or machines
                machine = min(capable, key=lambda m: machine_free[m.machine_id])
                start = max(machine_free[machine.machine_id], op_ready)
                hours = (
                    machine.setup_minutes / 60.0
                    + wo.quantity / max(machine.units_per_hour, 0.1)
                )
                end = start + timedelta(hours=hours)
                schedule.entries.append(ScheduleEntry(
                    work_order_id=wo.work_order_id,
                    machine_id=machine.machine_id,
                    operation=op,
                    start=start,
                    end=end,
                    quantity=wo.quantity,
                ))
                machine_free[machine.machine_id] = end
                op_ready = end

        return schedule

    @staticmethod
    def _check_capacity(
        schedule: ProductionSchedule,
        machines: List[Machine],
        horizon_hours: float,
    ) -> Dict[str, Dict[str, Any]]:
        """Compare required hours vs available hours per work center."""
        by_machine = {m.machine_id: m for m in machines}
        centers: Dict[str, Dict[str, float]] = {}
        for m in machines:
            centers.setdefault(
                m.work_center, {"machines": 0, "required_hours": 0.0}
            )["machines"] += 1

        for entry in schedule.entries:
            machine = by_machine.get(entry.machine_id)
            if machine is None:
                continue
            duration = (entry.end - entry.start).total_seconds() / 3600.0
            centers[machine.work_center]["required_hours"] += duration

        capacity: Dict[str, Dict[str, Any]] = {}
        for wc, c in centers.items():
            available = horizon_hours * c["machines"]
            required = c["required_hours"]
            capacity[wc] = {
                "required_hours": round(required, 2),
                "available_hours": round(available, 2),
                "utilization": round(required / available, 3) if available else 0.0,
                "overloaded": required > available,
            }
        return capacity
