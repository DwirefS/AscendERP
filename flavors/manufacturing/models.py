"""
Shared domain models for the Manufacturing flavor.

Single source of truth: agents, workflows, councils, simulation, autoresearch,
and Mission Control all import from here. Do not redefine these elsewhere.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# Plant entities
# ---------------------------------------------------------------------------

class MachineState(Enum):
    IDLE = "idle"
    RUNNING = "running"
    SETUP = "setup"
    DOWN = "down"
    MAINTENANCE = "maintenance"


@dataclass
class Machine:
    machine_id: str
    name: str
    work_center: str
    # Capability: which operation types this machine can perform
    operations: List[str] = field(default_factory=list)
    units_per_hour: float = 10.0
    setup_minutes: float = 20.0
    state: MachineState = MachineState.IDLE
    runtime_hours_since_pm: float = 0.0
    mtbf_hours: float = 400.0          # mean time between failures
    mttr_hours: float = 4.0            # mean time to repair
    vibration_trend: float = 0.0       # 0..1, rising = degrading
    scrap_rate_baseline: float = 0.01


@dataclass
class BOMLine:
    material_id: str
    quantity_per_unit: float


@dataclass
class Product:
    product_id: str
    name: str
    # Ordered routing: operation type per step
    routing: List[str] = field(default_factory=list)
    bom: List[BOMLine] = field(default_factory=list)
    unit_price: float = 100.0
    standard_cost: float = 60.0


@dataclass
class InventoryItem:
    material_id: str
    name: str
    on_hand: float
    on_order: float = 0.0
    reorder_point: float = 0.0
    safety_stock: float = 0.0
    unit_cost: float = 1.0
    lead_time_days: float = 7.0
    preferred_supplier_id: Optional[str] = None


@dataclass
class Supplier:
    supplier_id: str
    name: str
    materials: List[str] = field(default_factory=list)
    otd_rate: float = 0.95             # on-time delivery history
    defect_ppm: float = 500.0
    lead_time_days: float = 7.0
    price_index: float = 1.0           # 1.0 = market average
    region: str = "domestic"


# ---------------------------------------------------------------------------
# Orders & scheduling
# ---------------------------------------------------------------------------

class WorkOrderStatus(Enum):
    PLANNED = "planned"
    RELEASED = "released"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class Priority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class WorkOrder:
    work_order_id: str
    product_id: str
    quantity: float
    due_date: datetime
    status: WorkOrderStatus = WorkOrderStatus.PLANNED
    priority: Priority = Priority.NORMAL
    customer_id: Optional[str] = None
    released_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_quantity: float = 0.0
    scrapped_quantity: float = 0.0

    @staticmethod
    def new(product_id: str, quantity: float, due_date: datetime, **kw) -> "WorkOrder":
        return WorkOrder(
            work_order_id=_new_id("WO"),
            product_id=product_id,
            quantity=quantity,
            due_date=due_date,
            **kw,
        )


@dataclass
class ScheduleEntry:
    work_order_id: str
    machine_id: str
    operation: str
    start: datetime
    end: datetime
    quantity: float


@dataclass
class ProductionSchedule:
    schedule_id: str = field(default_factory=lambda: _new_id("SCHED"))
    entries: List[ScheduleEntry] = field(default_factory=list)
    policy_name: str = "default"
    created_at: datetime = field(default_factory=datetime.utcnow)

    def for_machine(self, machine_id: str) -> List[ScheduleEntry]:
        return sorted(
            (e for e in self.entries if e.machine_id == machine_id),
            key=lambda e: e.start,
        )


@dataclass
class SchedulingPolicy:
    """
    Parameterized dispatch policy — the AutoOptimize search space.
    dispatch_rule: EDD (earliest due date), SPT (shortest processing time),
    CR (critical ratio), WSPT (weighted SPT), FIFO.
    """
    dispatch_rule: str = "EDD"
    batch_size_factor: float = 1.0          # 0.25..2.0, scales lot splitting
    maintenance_buffer_hours: float = 8.0   # PM window reserved per machine/week
    expedite_threshold: float = 0.8         # critical-ratio cutoff for expedite
    queue_weight_due: float = 1.0           # blend weights for composite rule
    queue_weight_setup: float = 0.3

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dispatch_rule": self.dispatch_rule,
            "batch_size_factor": self.batch_size_factor,
            "maintenance_buffer_hours": self.maintenance_buffer_hours,
            "expedite_threshold": self.expedite_threshold,
            "queue_weight_due": self.queue_weight_due,
            "queue_weight_setup": self.queue_weight_setup,
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "SchedulingPolicy":
        return SchedulingPolicy(**d)


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------

class DispositionType(Enum):
    USE_AS_IS = "use_as_is"
    REWORK = "rework"
    SCRAP = "scrap"
    RETURN_TO_SUPPLIER = "return_to_supplier"


@dataclass
class QualityInspection:
    inspection_id: str
    work_order_id: str
    characteristic: str                 # e.g. "diameter_mm"
    measurements: List[float] = field(default_factory=list)
    nominal: float = 0.0
    usl: float = 0.0                    # upper spec limit
    lsl: float = 0.0                    # lower spec limit
    inspected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class NonConformanceReport:
    ncr_id: str
    work_order_id: str
    description: str
    severity: str = "minor"             # minor | major | critical
    quantity_affected: float = 0.0
    disposition: Optional[DispositionType] = None
    root_cause: Optional[str] = None
    corrective_action: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def new(work_order_id: str, description: str, **kw) -> "NonConformanceReport":
        return NonConformanceReport(
            ncr_id=_new_id("NCR"), work_order_id=work_order_id,
            description=description, **kw,
        )


# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

class MaintenanceType(Enum):
    PREVENTIVE = "preventive"
    CORRECTIVE = "corrective"
    PREDICTIVE = "predictive"


@dataclass
class MaintenanceWorkOrder:
    maintenance_id: str
    machine_id: str
    maintenance_type: MaintenanceType
    reason: str
    estimated_hours: float = 4.0
    scheduled_start: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    risk_score: float = 0.0             # 0..1 failure risk that triggered this

    @staticmethod
    def new(machine_id: str, maintenance_type: MaintenanceType, reason: str, **kw):
        return MaintenanceWorkOrder(
            maintenance_id=_new_id("PM"), machine_id=machine_id,
            maintenance_type=maintenance_type, reason=reason, **kw,
        )


# ---------------------------------------------------------------------------
# Procurement
# ---------------------------------------------------------------------------

class POStatus(Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    RECEIVED = "received"
    CANCELLED = "cancelled"


@dataclass
class PurchaseOrder:
    po_id: str
    supplier_id: str
    material_id: str
    quantity: float
    unit_cost: float
    status: POStatus = POStatus.DRAFT
    needed_by: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_cost(self) -> float:
        return self.quantity * self.unit_cost

    @staticmethod
    def new(supplier_id: str, material_id: str, quantity: float, unit_cost: float, **kw):
        return PurchaseOrder(
            po_id=_new_id("PO"), supplier_id=supplier_id, material_id=material_id,
            quantity=quantity, unit_cost=unit_cost, **kw,
        )


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

@dataclass
class KPISnapshot:
    """Standard KPI set produced by simulation runs and live tracking."""
    throughput_units: float = 0.0
    otd_rate: float = 0.0               # on-time delivery 0..1
    oee: float = 0.0                    # overall equipment effectiveness 0..1
    wip_units: float = 0.0
    scrap_rate: float = 0.0
    total_cost: float = 0.0
    makespan_hours: float = 0.0
    captured_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "throughput_units": round(self.throughput_units, 3),
            "otd_rate": round(self.otd_rate, 4),
            "oee": round(self.oee, 4),
            "wip_units": round(self.wip_units, 3),
            "scrap_rate": round(self.scrap_rate, 4),
            "total_cost": round(self.total_cost, 2),
            "makespan_hours": round(self.makespan_hours, 3),
            "captured_at": self.captured_at.isoformat(),
        }


@dataclass
class SimEvent:
    timestamp_hours: float              # sim time offset from start
    event_type: str                     # job_start|job_complete|breakdown|repair|scrap|...
    machine_id: Optional[str] = None
    work_order_id: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SimulationResult:
    kpis: KPISnapshot
    events: List[SimEvent] = field(default_factory=list)
    replications: int = 1
    seed: int = 0
    horizon_hours: float = 0.0


# ---------------------------------------------------------------------------
# Swarm scenario engine (MiroFish-inspired)
# ---------------------------------------------------------------------------

@dataclass
class SimulationScenario:
    name: str
    narrative: str                      # human description of the what-if
    shock: Dict[str, Any] = field(default_factory=dict)
    # shock examples:
    #   {"type": "supplier_outage", "supplier_id": "SUP-1", "days": 14}
    #   {"type": "demand_spike", "product_id": "P-1", "factor": 1.6}
    #   {"type": "machine_failure", "machine_id": "M-3", "days": 5}
    horizon_days: int = 30
    seed: int = 42


@dataclass
class ScenarioEvent:
    day: int
    actor_id: str
    event_type: str
    description: str
    impact: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioReport:
    scenario: SimulationScenario
    timeline: List[ScenarioEvent] = field(default_factory=list)
    kpi_impact: Dict[str, float] = field(default_factory=dict)   # deltas vs baseline
    risks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.5
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def summary(self) -> Dict[str, Any]:
        return {
            "scenario": self.scenario.name,
            "events": len(self.timeline),
            "kpi_impact": self.kpi_impact,
            "risks": self.risks,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
        }


# ---------------------------------------------------------------------------
# AutoOptimize (Karpathy autoresearch-inspired)
# ---------------------------------------------------------------------------

@dataclass
class OptimizationStep:
    step: int
    mutated_field: str
    old_value: Any
    new_value: Any
    objective_before: float
    objective_after: float
    accepted: bool
    kpis_after: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step": self.step,
            "mutated_field": self.mutated_field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "objective_before": round(self.objective_before, 6),
            "objective_after": round(self.objective_after, 6),
            "accepted": self.accepted,
            "kpis_after": self.kpis_after,
            "timestamp": self.timestamp.isoformat(),
        }
