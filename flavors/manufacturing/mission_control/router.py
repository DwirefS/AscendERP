"""
Mission Control — operational API for the manufacturing flavor.

One pane of glass for the agent fleet: status, KPIs, work orders, schedules,
workflow launches, swarm what-if scenarios, AutoOptimize runs, HITL approvals,
and the audit receipt chain. Mounted into the ANTS API gateway under
`/manufacturing`; gateway auth scopes guard every mutating route.

All flavor components are imported lazily and degrade gracefully, so Mission
Control stays up even if an individual subsystem is unavailable.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from flavors.manufacturing.models import (
    Priority,
    SimulationScenario,
    WorkOrder,
)

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class WorkOrderRequest(BaseModel):
    product_id: str = Field(..., description="Product to manufacture")
    quantity: float = Field(..., gt=0)
    due_in_days: float = Field(7.0, gt=0)
    priority: str = Field("normal", description="low|normal|high|critical")


class ScenarioRequest(BaseModel):
    name: str = Field(..., description="Scenario name")
    narrative: str = Field("", description="What-if description")
    shock: Dict[str, Any] = Field(
        ...,
        description=(
            'e.g. {"type": "supplier_outage", "supplier_id": "SUP-1", "days": 14}'
        ),
    )
    horizon_days: int = Field(30, ge=1, le=365)
    seed: int = Field(42)


class WorkflowRunRequest(BaseModel):
    input_data: Dict[str, Any] = Field(default_factory=dict)


class OptimizeRequest(BaseModel):
    steps: int = Field(5, ge=1, le=100)
    seed: int = Field(42)


@dataclass
class MissionControlState:
    """Singleton state behind the Mission Control router."""
    work_orders: List[WorkOrder] = field(default_factory=list)
    last_schedule: Optional[Any] = None
    last_kpis: Optional[Dict[str, Any]] = None
    receipt_chain: Any = None
    approval_queue: Any = None
    optimize_history: List[Dict[str, Any]] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)

    def ensure_governance(self):
        """Lazily create the shared receipt chain + approval queue."""
        if self.receipt_chain is None or self.approval_queue is None:
            from src.core.harness import ApprovalQueue, ReceiptChain

            self.receipt_chain = self.receipt_chain or ReceiptChain()
            self.approval_queue = self.approval_queue or ApprovalQueue()
        return self.receipt_chain, self.approval_queue


AGENT_TYPES = [
    ("manufacturing.production_planner", "agents.production_planner_agent", "ProductionPlannerAgent"),
    ("manufacturing.quality", "agents.quality_agent", "QualityAgent"),
    ("manufacturing.maintenance", "agents.maintenance_agent", "MaintenanceAgent"),
    ("manufacturing.procurement", "agents.procurement_agent", "ProcurementAgent"),
    ("manufacturing.inventory", "agents.inventory_agent", "InventoryAgent"),
    ("manufacturing.ehs_compliance", "agents.ehs_compliance_agent", "EHSComplianceAgent"),
]

WORKFLOWS = {
    "order_to_production": ("workflows.order_to_production", "OrderToProductionWorkflow"),
    "predictive_maintenance": ("workflows.predictive_maintenance", "PredictiveMaintenanceWorkflow"),
    "quality_rca": ("workflows.quality_rca", "QualityRCAWorkflow"),
    "supply_disruption_response": ("workflows.supply_disruption_response", "SupplyDisruptionResponseWorkflow"),
}


def _import_flavor(module_suffix: str, attr: str):
    import importlib

    module = importlib.import_module(f"flavors.manufacturing.{module_suffix}")
    return getattr(module, attr)


def _load_seed(seed: int = 42) -> Dict[str, Any]:
    build_seed = _import_flavor("data.seed", "build_seed")
    data = build_seed(seed)
    return data if isinstance(data, dict) else data.__dict__


def build_mission_control_router(
    require_scope,
    state: Optional[MissionControlState] = None,
) -> APIRouter:
    """
    Build the Mission Control router.

    `require_scope` is the gateway's scope-dependency factory, injected so this
    module has no hard dependency on gateway internals.
    """
    state = state or MissionControlState()
    router = APIRouter(prefix="/manufacturing", tags=["manufacturing"])

    # -- Fleet & KPIs --------------------------------------------------------

    @router.get("/fleet")
    async def fleet(auth=Depends(require_scope("agents:read"))):
        """Registered manufacturing agents and their availability."""
        fleet_info = []
        for agent_type, module_suffix, cls_name in AGENT_TYPES:
            try:
                cls = _import_flavor(module_suffix, cls_name)
                agent = cls()
                fleet_info.append({
                    "agent_type": agent_type,
                    "name": agent.config.name,
                    "state": agent.state.value,
                    "tools": list(agent.config.tools or []),
                    "available": True,
                })
            except Exception as e:
                fleet_info.append({
                    "agent_type": agent_type,
                    "available": False,
                    "error": str(e),
                })
        return {
            "fleet": fleet_info,
            "available": sum(1 for a in fleet_info if a.get("available")),
            "total": len(fleet_info),
        }

    @router.get("/kpis")
    async def kpis(auth=Depends(require_scope("agents:read"))):
        """Latest KPI snapshot (from the most recent simulation/workflow run)."""
        if state.last_kpis is None:
            # Produce a baseline from the seeded plant on first ask
            try:
                seed_data = _load_seed()
                PolicyScheduler = _import_flavor("simulation.plant", "PolicyScheduler")
                PlantSimulator = _import_flavor("simulation.plant", "PlantSimulator")
                from flavors.manufacturing.models import SchedulingPolicy

                schedule = PolicyScheduler(SchedulingPolicy()).build_schedule(
                    seed_data["work_orders"], seed_data["machines"], seed_data["products"]
                )
                sim = PlantSimulator(seed=42)
                sim.load(
                    machines=seed_data["machines"],
                    products=seed_data["products"],
                    inventory=seed_data["inventory"],
                    work_orders=seed_data["work_orders"],
                )
                result = sim.run(schedule, horizon_hours=168.0, replications=3)
                state.last_kpis = result.kpis.to_dict()
                state.last_schedule = schedule
            except Exception as e:
                raise HTTPException(503, f"KPI baseline unavailable: {e}")
        return {"kpis": state.last_kpis, "as_of": datetime.utcnow().isoformat()}

    # -- Work orders & schedule ---------------------------------------------

    @router.post("/workorders", status_code=201)
    async def create_work_order(
        req: WorkOrderRequest, auth=Depends(require_scope("agents:write"))
    ):
        priority = {
            "low": Priority.LOW, "normal": Priority.NORMAL,
            "high": Priority.HIGH, "critical": Priority.CRITICAL,
        }.get(req.priority.lower(), Priority.NORMAL)
        wo = WorkOrder.new(
            product_id=req.product_id,
            quantity=req.quantity,
            due_date=datetime.utcnow() + timedelta(days=req.due_in_days),
            priority=priority,
        )
        state.work_orders.append(wo)
        logger.info("work_order_created", work_order_id=wo.work_order_id,
                    product_id=wo.product_id, tenant=auth.tenant_id)
        return {
            "work_order_id": wo.work_order_id,
            "product_id": wo.product_id,
            "quantity": wo.quantity,
            "due_date": wo.due_date.isoformat(),
            "priority": wo.priority.name.lower(),
            "status": wo.status.value,
        }

    @router.get("/workorders")
    async def list_work_orders(auth=Depends(require_scope("agents:read"))):
        return [
            {
                "work_order_id": wo.work_order_id,
                "product_id": wo.product_id,
                "quantity": wo.quantity,
                "due_date": wo.due_date.isoformat(),
                "priority": wo.priority.name.lower(),
                "status": wo.status.value,
            }
            for wo in state.work_orders
        ]

    @router.get("/schedule")
    async def schedule(auth=Depends(require_scope("agents:read"))):
        if state.last_schedule is None:
            raise HTTPException(404, "No schedule yet — run order_to_production or /kpis")
        s = state.last_schedule
        return {
            "schedule_id": s.schedule_id,
            "policy_name": s.policy_name,
            "entries": [
                {
                    "work_order_id": e.work_order_id,
                    "machine_id": e.machine_id,
                    "operation": e.operation,
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat(),
                    "quantity": e.quantity,
                }
                for e in s.entries
            ],
        }

    # -- Workflows ------------------------------------------------------------

    @router.post("/workflows/{name}/run")
    async def run_workflow(
        name: str, req: WorkflowRunRequest,
        auth=Depends(require_scope("workflows:run")),
    ):
        if name not in WORKFLOWS:
            raise HTTPException(404, f"Unknown workflow: {name}. Known: {sorted(WORKFLOWS)}")
        module_suffix, cls_name = WORKFLOWS[name]
        try:
            cls = _import_flavor(module_suffix, cls_name)
        except Exception as e:
            raise HTTPException(503, f"Workflow {name} unavailable: {e}")

        workflow = cls()
        input_data = dict(req.input_data)
        if name == "order_to_production" and state.work_orders:
            input_data.setdefault("work_orders", state.work_orders)

        runner = getattr(workflow, "run", None) or getattr(workflow, "execute")
        result = await runner(input_data)

        # Capture KPIs/schedule when the workflow surfaces them
        if isinstance(result, dict):
            if isinstance(result.get("kpis"), dict):
                state.last_kpis = result["kpis"]
            if result.get("schedule") is not None:
                state.last_schedule = result["schedule"]
        logger.info("workflow_completed", workflow=name, tenant=auth.tenant_id)
        return {"workflow": name, "result": _jsonable(result)}

    # -- Swarm scenarios -------------------------------------------------------

    @router.post("/scenarios/run")
    async def run_scenario(
        req: ScenarioRequest, auth=Depends(require_scope("scenarios:run"))
    ):
        try:
            SwarmWorld = _import_flavor("simulation.swarm", "SwarmWorld")
        except Exception as e:
            raise HTTPException(503, f"Swarm engine unavailable: {e}")

        seed_data = _load_seed(req.seed)
        world = SwarmWorld.from_seed(seed_data)
        report = world.run_scenario(SimulationScenario(
            name=req.name, narrative=req.narrative, shock=req.shock,
            horizon_days=req.horizon_days, seed=req.seed,
        ))
        logger.info("scenario_completed", scenario=req.name, tenant=auth.tenant_id)
        return {
            "summary": report.summary(),
            "timeline": [
                {
                    "day": ev.day, "actor_id": ev.actor_id,
                    "event_type": ev.event_type, "description": ev.description,
                }
                for ev in report.timeline
            ],
        }

    # -- AutoOptimize ----------------------------------------------------------

    @router.post("/autoresearch/run")
    async def run_autoresearch(
        req: OptimizeRequest, auth=Depends(require_scope("optimize:run"))
    ):
        try:
            AutoOptimizeLoop = _import_flavor("autoresearch.optimize_loop", "AutoOptimizeLoop")
            PolicyScheduler = _import_flavor("simulation.plant", "PolicyScheduler")
            PlantSimulator = _import_flavor("simulation.plant", "PlantSimulator")
        except Exception as e:
            raise HTTPException(503, f"AutoOptimize unavailable: {e}")

        seed_data = _load_seed(req.seed)
        loop = AutoOptimizeLoop(
            simulator_factory=lambda: _loaded_simulator(PlantSimulator, seed_data, req.seed),
            scheduler_factory=PolicyScheduler,
            work_orders=seed_data["work_orders"],
            machines=seed_data["machines"],
            products=seed_data["products"],
            seed=req.seed,
        )
        summary = loop.run(req.steps)
        steps = [s.to_dict() for s in getattr(loop, "history", [])]
        state.optimize_history.extend(steps)
        logger.info("autoresearch_completed", steps=req.steps,
                    accepted=sum(1 for s in steps if s["accepted"]),
                    tenant=auth.tenant_id)
        return {"summary": _jsonable(summary), "steps": steps}

    @router.get("/autoresearch/journal")
    async def autoresearch_journal(auth=Depends(require_scope("agents:read"))):
        return {"steps": state.optimize_history,
                "accepted": sum(1 for s in state.optimize_history if s.get("accepted"))}

    # -- Governance: approvals + receipts -------------------------------------

    @router.get("/approvals")
    async def approvals(auth=Depends(require_scope("agents:read"))):
        _, queue = state.ensure_governance()
        return {"pending": [_jsonable(a) for a in queue.pending()]}

    @router.post("/approvals/{approval_id}/approve")
    async def approve(approval_id: str, auth=Depends(require_scope("approvals:write"))):
        _, queue = state.ensure_governance()
        try:
            queue.approve(approval_id)
        except KeyError:
            raise HTTPException(404, "Unknown approval id")
        logger.info("approval_granted", approval_id=approval_id,
                    by=auth.user_id or auth.tenant_id)
        return {"approval_id": approval_id, "status": "approved"}

    @router.post("/approvals/{approval_id}/reject")
    async def reject(approval_id: str, auth=Depends(require_scope("approvals:write"))):
        _, queue = state.ensure_governance()
        try:
            queue.reject(approval_id)
        except KeyError:
            raise HTTPException(404, "Unknown approval id")
        logger.info("approval_rejected", approval_id=approval_id,
                    by=auth.user_id or auth.tenant_id)
        return {"approval_id": approval_id, "status": "rejected"}

    @router.get("/receipts")
    async def receipts(auth=Depends(require_scope("receipts:read"))):
        chain, _ = state.ensure_governance()
        return {
            "verified": chain.verify(),
            "count": len(chain.receipts) if hasattr(chain, "receipts") else 0,
            "receipts": [_jsonable(r) for r in getattr(chain, "receipts", [])][-100:],
        }

    @router.get("/status")
    async def status(auth=Depends(require_scope("agents:read"))):
        """Mission Control overview."""
        _, queue = state.ensure_governance()
        return {
            "uptime_seconds": (datetime.utcnow() - state.started_at).total_seconds(),
            "open_work_orders": len(state.work_orders),
            "has_schedule": state.last_schedule is not None,
            "last_kpis": state.last_kpis,
            "approvals_pending": len(queue.pending()),
            "optimize_steps_recorded": len(state.optimize_history),
            "workflows": sorted(WORKFLOWS),
        }

    return router


def _loaded_simulator(PlantSimulator, seed_data: Dict[str, Any], seed: int):
    sim = PlantSimulator(seed=seed)
    sim.load(
        machines=seed_data["machines"],
        products=seed_data["products"],
        inventory=seed_data["inventory"],
        work_orders=seed_data["work_orders"],
    )
    return sim


def _jsonable(obj: Any) -> Any:
    """Best-effort conversion of dataclasses/datetimes/enums for JSON responses."""
    import dataclasses
    from enum import Enum

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj
