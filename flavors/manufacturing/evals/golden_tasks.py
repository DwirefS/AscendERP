"""
Golden tasks for the Manufacturing flavor (WS-3 Evidence Engine).

Three task sets with analytically known correct answers, derived from the
agents' own documented rules — the agents' documented behavior is the spec:

* ``SPC_TASKS`` — crafted measurement series for the QualityAgent's Western
  Electric rules 1-4 and Cpk severity grading (critical < 0.7 <= major
  < 1.0 <= minor).
* ``REORDER_TASKS`` — inventory positions vs reorder points for the
  ProcurementAgent (position = on_hand + on_order - demand; breach when
  position <= reorder_point; supplier score 0.35*otd + 0.25*defects
  + 0.20*price + 0.20*lead; POs > 50k -> PENDING_APPROVAL).
* ``MAINTENANCE_TASKS`` — machine wear/vibration combos for the
  MaintenanceAgent (risk = clamp(0.6*runtime/mtbf + 0.4*vibration, 0, 1),
  PM order iff risk >= 0.6).

Each set ships a matching subject callable (``spc_subject`` etc.) that runs
the real agent through its full PRREEL loop, so the eval measures the agents
as deployed, not reimplementations.
"""
from __future__ import annotations

from typing import Any, Dict, List

import structlog

from src.core.agent.base import AgentContext
from src.core.evals.runner import GoldenTask
from flavors.manufacturing.agents import (
    MaintenanceAgent,
    ProcurementAgent,
    QualityAgent,
)
from flavors.manufacturing.models import (
    InventoryItem,
    Machine,
    QualityInspection,
    Supplier,
)

logger = structlog.get_logger()

_NOMINAL = 10.0

# Lazily-created agent singletons (agents are stateless between runs).
_agents: Dict[str, Any] = {}


def _agent(cls: type) -> Any:
    instance = _agents.get(cls.__name__)
    if instance is None:
        instance = cls()
        _agents[cls.__name__] = instance
    return instance


def _ctx(task_hint: str) -> AgentContext:
    return AgentContext(trace_id=f"eval-{task_hint}", tenant_id="eval")


def _alternating(n: int, delta: float, start: int = 1) -> List[float]:
    """n points alternating nominal +/- delta (no same-side runs possible)."""
    side, series = start, []
    for _ in range(n):
        series.append(_NOMINAL + side * delta)
        side = -side
    return series


# ---------------------------------------------------------------------------
# Subjects: run the real agents, return their execute() output dict
# ---------------------------------------------------------------------------


async def spc_subject(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the real QualityAgent on an inspection payload."""
    result = await _agent(QualityAgent).run(input_data, _ctx("spc"))
    if not result.success:
        raise RuntimeError(result.error or "QualityAgent run failed")
    return result.output


async def reorder_subject(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the real ProcurementAgent on an inventory/supplier payload."""
    result = await _agent(ProcurementAgent).run(input_data, _ctx("reorder"))
    if not result.success:
        raise RuntimeError(result.error or "ProcurementAgent run failed")
    return result.output


async def maintenance_subject(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Run the real MaintenanceAgent on a machine telemetry payload."""
    result = await _agent(MaintenanceAgent).run(input_data, _ctx("maintenance"))
    if not result.success:
        raise RuntimeError(result.error or "MaintenanceAgent run failed")
    return result.output


# ---------------------------------------------------------------------------
# Scorers
# ---------------------------------------------------------------------------


def score_spc(actual: Any, expected: Dict[str, Any]) -> float:
    """
    0.5 for the in-control verdict, 0.3 for the exact Western Electric rule
    set (0.15 if all expected rules fired plus extras), 0.2 for the correct
    NCR severity + disposition (both None for in-control series).
    """
    score = 0.0
    if actual.get("in_control") == expected["in_control"]:
        score += 0.5

    expected_rules = set(expected.get("rules", []))
    fired = set(actual.get("rules_fired", []))
    if expected_rules == fired:
        score += 0.3
    elif expected_rules and expected_rules.issubset(fired):
        score += 0.15

    ncr = actual.get("ncr")
    actual_severity = ncr.severity if ncr is not None else None
    disposition = actual.get("recommended_disposition")
    actual_disposition = disposition.value if disposition is not None else None
    if (
        actual_severity == expected.get("severity")
        and actual_disposition == expected.get("disposition")
    ):
        score += 0.2
    return score


def score_reorder(actual: Any, expected: Dict[str, Any]) -> float:
    """
    No-PO cases: full credit iff no PO was generated (half-weighted with the
    unsourced listing when a sourcing failure is expected). PO cases: 0.4 for
    generating a PO, 0.3 supplier, 0.2 approval status, 0.1 quantity.
    """
    purchase_orders = actual.get("purchase_orders", [])
    if not expected["po_created"]:
        no_po = 1.0 if not purchase_orders else 0.0
        if expected.get("unsourced_material"):
            listed = expected["unsourced_material"] in actual.get(
                "unsourced_materials", []
            )
            return 0.5 * no_po + (0.5 if listed else 0.0)
        return no_po

    if not purchase_orders:
        return 0.0
    po = purchase_orders[0]
    score = 0.4
    if po.supplier_id == expected.get("supplier_id"):
        score += 0.3
    if po.status.value == expected.get("status"):
        score += 0.2
    if expected.get("quantity") is None or po.quantity == expected["quantity"]:
        score += 0.1
    return score


def score_maintenance(actual: Any, expected: Dict[str, Any]) -> float:
    """
    0.5 for the exact set of machines that got PM orders, 0.3 for the
    descending risk ordering, 0.2 for risk values within 1e-3 of the
    analytically expected scores.
    """
    ordered_machines = {o.machine_id for o in actual.get("maintenance_orders", [])}
    score = 0.5 if ordered_machines == set(expected["pm_machines"]) else 0.0

    risk_scores = actual.get("risk_scores", {})
    ranking = sorted(risk_scores, key=lambda m: (-risk_scores[m], m))
    if ranking == expected["risk_order"]:
        score += 0.3

    expected_risks: Dict[str, float] = expected.get("risks", {})
    if expected_risks and all(
        abs(risk_scores.get(machine_id, -1.0) - risk) <= 1e-3
        for machine_id, risk in expected_risks.items()
    ):
        score += 0.2
    return score


# ---------------------------------------------------------------------------
# SPC golden tasks (ground truth per the QualityAgent's documented rules)
# ---------------------------------------------------------------------------


def _inspection(task_id: str, measurements: List[float], usl: float, lsl: float) -> QualityInspection:
    return QualityInspection(
        inspection_id=f"INSP-{task_id}",
        work_order_id=f"WO-{task_id}",
        characteristic="diameter_mm",
        measurements=measurements,
        nominal=_NOMINAL,
        usl=usl,
        lsl=lsl,
    )


# A sustained mean shift: 10 in-control points, then 10 points ~ +0.3 above
# nominal. Fires rules 2, 3 and 4 (shift is large vs in-control spread).
_SHIFT_SERIES = _alternating(10, 0.1) + [
    10.3 + (0.05 if i % 2 == 0 else -0.05) for i in range(10)
]


def _build_spc_tasks() -> List[GoldenTask]:
    def task(task_id, description, measurements, usl, lsl, expected, supplier=False, tags=()):
        return GoldenTask(
            task_id=task_id,
            description=description,
            input_data={
                "inspection": _inspection(task_id, measurements, usl, lsl),
                "supplier_material": supplier,
            },
            expected=expected,
            scorer=score_spc,
            tags=["spc", *tags],
            domain="manufacturing.quality",
        )

    in_control = {"in_control": True, "rules": [], "severity": None, "disposition": None}
    minor_signal = {"severity": "minor", "disposition": "use_as_is"}

    # Irregular in-control series: alternating sides, |dev| <= 0.12, so no
    # same-side runs and every |z| < 2 -> no rule can fire.
    gaussian_like = [
        _NOMINAL + sign * delta
        for sign, delta in zip(
            [1, -1] * 10,
            [0.05, 0.08, 0.02, 0.11, 0.07, 0.04, 0.10, 0.03, 0.06, 0.12,
             0.09, 0.01, 0.05, 0.10, 0.02, 0.08, 0.11, 0.04, 0.07, 0.03],
        )
    ]

    return [
        task(
            "spc_in_control_gaussian",
            "Alternating-side gaussian-like series stays in control",
            gaussian_like, 10.6, 9.4,
            dict(in_control), tags=["in_control"],
        ),
        task(
            "spc_rule1_spike",
            "Single +1.0 spike beyond 3 sigma fires rule 1 only",
            _alternating(19, 0.1) + [11.0], 11.5, 8.5,
            {"in_control": False, "rules": ["rule1_one_beyond_3_sigma"], **minor_signal},
            tags=["rule1"],
        ),
        task(
            "spc_rule4_sustained_shift",
            "Mild sustained shift: 8 consecutive points above center (rule 4 only)",
            _alternating(12, 0.2)
            + [10.12 + (0.06 if i % 2 == 0 else -0.06) for i in range(8)],
            11.2, 8.8,
            {"in_control": False, "rules": ["rule4_eight_consecutive_same_side"], **minor_signal},
            tags=["rule4"],
        ),
        task(
            "spc_rule2_two_of_three",
            "2 of 3 consecutive points beyond 2 sigma, same side (rule 2)",
            _alternating(8, 0.1) + [10.55, 9.9, 10.55] + _alternating(8, 0.1, start=-1),
            11.5, 8.5,
            {"in_control": False, "rules": ["rule2_two_of_three_beyond_2_sigma"], **minor_signal},
            tags=["rule2"],
        ),
        task(
            "spc_rule3_four_of_five",
            "4 of 5 consecutive points beyond 1 sigma, same side (rule 3)",
            _alternating(8, 0.1)
            + [10.22, 10.25, 9.95, 10.22, 10.25]
            + _alternating(7, 0.1, start=-1),
            11.5, 8.5,
            {"in_control": False, "rules": ["rule3_four_of_five_beyond_1_sigma"], **minor_signal},
            tags=["rule3"],
        ),
        task(
            "spc_drift",
            "Linear drift 9.9 -> 10.5 trips run rules 2, 3 and 4",
            [9.9 + 0.6 * i / 19.0 for i in range(20)], 11.5, 8.5,
            {
                "in_control": False,
                "rules": [
                    "rule2_two_of_three_beyond_2_sigma",
                    "rule3_four_of_five_beyond_1_sigma",
                    "rule4_eight_consecutive_same_side",
                ],
                **minor_signal,
            },
            tags=["drift"],
        ),
        task(
            "spc_cpk_capable",
            "Tight alternating series, Cpk ~1.95: capable and in control",
            _alternating(20, 0.1), 10.6, 9.4,
            dict(in_control), tags=["cpk"],
        ),
        task(
            "spc_cpk_marginal",
            "Shifted series with Cpk ~0.77 (< 1.0): major severity, rework",
            list(_SHIFT_SERIES), 10.55, 9.0,
            {
                "in_control": False,
                "rules": [
                    "rule2_two_of_three_beyond_2_sigma",
                    "rule3_four_of_five_beyond_1_sigma",
                    "rule4_eight_consecutive_same_side",
                ],
                "severity": "major",
                "disposition": "rework",
            },
            tags=["cpk"],
        ),
        task(
            "spc_cpk_incapable",
            "Shifted series with Cpk ~0.38 (< 0.7): critical severity, scrap",
            list(_SHIFT_SERIES), 10.35, 9.0,
            {
                "in_control": False,
                "rules": [
                    "rule2_two_of_three_beyond_2_sigma",
                    "rule3_four_of_five_beyond_1_sigma",
                    "rule4_eight_consecutive_same_side",
                ],
                "severity": "critical",
                "disposition": "scrap",
            },
            tags=["cpk"],
        ),
        task(
            "spc_supplier_material_return",
            "Critical NCR on supplier material -> return to supplier",
            list(_SHIFT_SERIES), 10.35, 9.0,
            {
                "in_control": False,
                "rules": [
                    "rule2_two_of_three_beyond_2_sigma",
                    "rule3_four_of_five_beyond_1_sigma",
                    "rule4_eight_consecutive_same_side",
                ],
                "severity": "critical",
                "disposition": "return_to_supplier",
            },
            supplier=True, tags=["supplier"],
        ),
        task(
            "spc_sigma_zero_constant",
            "Constant series: zero sigma, capped capability, in control",
            [10.0] * 15, 10.5, 9.5,
            dict(in_control), tags=["edge"],
        ),
    ]


# ---------------------------------------------------------------------------
# Reorder golden tasks (ground truth per the ProcurementAgent's documented
# reorder policy, supplier weights 0.35/0.25/0.20/0.20 and 50k PO threshold)
# ---------------------------------------------------------------------------

def _sup_good() -> Supplier:
    # Dominates every scoring component: score = 0.35*0.99 + 0.25*0.99
    # + 0.20*1.0 + 0.20*(1 - 5/30) = 0.9607
    return Supplier(
        supplier_id="SUP-GOOD", name="Dominant Supplies",
        materials=["RM-X"], otd_rate=0.99, defect_ppm=100.0,
        lead_time_days=5.0, price_index=0.9,
    )


def _sup_poor() -> Supplier:
    # Dominated on every component: score = 0.35*0.80 + 0.25*0.5
    # + 0.20*0.7 + 0.20*(1 - 25/30) = 0.5783
    return Supplier(
        supplier_id="SUP-POOR", name="Laggard Logistics",
        materials=["RM-X"], otd_rate=0.80, defect_ppm=5000.0,
        lead_time_days=25.0, price_index=1.3,
    )


def _sup_solo(material_id: str = "RM-X", unit_price_index: float = 1.0) -> Supplier:
    return Supplier(
        supplier_id="SUP-SOLO", name="Only Option Inc",
        materials=[material_id], otd_rate=0.95, defect_ppm=400.0,
        lead_time_days=7.0, price_index=unit_price_index,
    )


def _item(material_id: str, on_hand: float, reorder_point: float,
          safety_stock: float = 0.0, unit_cost: float = 1.0,
          on_order: float = 0.0) -> InventoryItem:
    return InventoryItem(
        material_id=material_id, name=material_id, on_hand=on_hand,
        on_order=on_order, reorder_point=reorder_point,
        safety_stock=safety_stock, unit_cost=unit_cost,
    )


def _build_reorder_tasks() -> List[GoldenTask]:
    def task(task_id, description, input_data, expected, tags=()):
        return GoldenTask(
            task_id=task_id,
            description=description,
            input_data=input_data,
            expected=expected,
            scorer=score_reorder,
            tags=["reorder", *tags],
            domain="manufacturing.procurement",
        )

    return [
        task(
            "reorder_above_point_no_po",
            "Position (500) above reorder point (100): no PO",
            {"inventory": [_item("RM-X", 500.0, 100.0)], "suppliers": [_sup_solo()]},
            {"po_created": False},
        ),
        task(
            "reorder_breach_single_supplier",
            "Breach (20 <= 40) with one supplier: PO for 70 units, auto-approved",
            {
                "inventory": [_item("RM-X", 20.0, 40.0, safety_stock=10.0, unit_cost=2.0)],
                "suppliers": [_sup_solo()],
            },
            # target = 2*40 + 10 = 90; qty = ceil(90 - 20) = 70; 70*2 = 140 < 50k
            {"po_created": True, "supplier_id": "SUP-SOLO", "status": "approved", "quantity": 70.0},
        ),
        task(
            "reorder_dominant_supplier_wins",
            "Two suppliers, one dominates all four score components",
            {
                "inventory": [_item("RM-X", 10.0, 50.0, unit_cost=3.0)],
                "suppliers": [_sup_poor(), _sup_good()],
            },
            # scores: SUP-GOOD 0.9607 > SUP-POOR 0.5783; qty = ceil(100-10) = 90
            {"po_created": True, "supplier_id": "SUP-GOOD", "status": "approved", "quantity": 90.0},
        ),
        task(
            "reorder_big_po_pending_approval",
            "PO total 63,000 (> 50k threshold) requires approval",
            {
                "inventory": [_item("RM-BIG", 100.0, 1000.0, safety_stock=200.0, unit_cost=30.0)],
                "suppliers": [_sup_solo("RM-BIG")],
            },
            # target = 2200; qty = 2100; 2100 * 30 * 1.0 = 63,000 > 50,000
            {"po_created": True, "supplier_id": "SUP-SOLO",
             "status": "pending_approval", "quantity": 2100.0},
            tags=["threshold"],
        ),
        task(
            "reorder_just_below_threshold_auto",
            "PO total 49,800 (< 50k) is auto-approved",
            {
                "inventory": [_item("RM-EDGE", 0.0, 100.0, unit_cost=249.0)],
                "suppliers": [_sup_solo("RM-EDGE")],
            },
            # qty = ceil(200 - 0) = 200; 200 * 249 = 49,800 < 50,000
            {"po_created": True, "supplier_id": "SUP-SOLO",
             "status": "approved", "quantity": 200.0},
            tags=["threshold"],
        ),
        task(
            "reorder_demand_driven_breach",
            "On-hand above ROP but committed demand pushes position below",
            {
                "inventory": [_item("RM-X", 120.0, 100.0, safety_stock=20.0)],
                "suppliers": [_sup_solo()],
                "demand": {"RM-X": 50.0},
            },
            # position = 120 - 50 = 70 <= 100; target = 220; qty = 150
            {"po_created": True, "supplier_id": "SUP-SOLO",
             "status": "approved", "quantity": 150.0},
        ),
        task(
            "reorder_unsourced_material",
            "Breach but no supplier carries the material: flagged unsourced",
            {
                "inventory": [_item("RM-ORPHAN", 0.0, 30.0)],
                "suppliers": [_sup_solo("RM-X")],
            },
            {"po_created": False, "unsourced_material": "RM-ORPHAN"},
            tags=["unsourced"],
        ),
        task(
            "reorder_excluded_supplier_fallback",
            "Best supplier excluded: falls back to the runner-up",
            {
                "inventory": [_item("RM-X", 10.0, 50.0)],
                "suppliers": [_sup_good(), _sup_poor()],
                "exclude_suppliers": ["SUP-GOOD"],
            },
            {"po_created": True, "supplier_id": "SUP-POOR",
             "status": "approved", "quantity": 90.0},
        ),
    ]


# ---------------------------------------------------------------------------
# Maintenance golden tasks (ground truth per the documented risk formula
# risk = clamp(0.6*runtime/mtbf + 0.4*vibration, 0, 1), threshold 0.6)
# ---------------------------------------------------------------------------

def _machine(machine_id: str, runtime: float, mtbf: float, vibration: float) -> Machine:
    return Machine(
        machine_id=machine_id, name=machine_id, work_center="WC-EVAL",
        operations=["machine"], runtime_hours_since_pm=runtime,
        mtbf_hours=mtbf, vibration_trend=vibration,
    )


def _build_maintenance_tasks() -> List[GoldenTask]:
    def task(task_id, description, input_data, expected, tags=()):
        return GoldenTask(
            task_id=task_id,
            description=description,
            input_data=input_data,
            expected=expected,
            scorer=score_maintenance,
            tags=["maintenance", *tags],
            domain="manufacturing.maintenance",
        )

    return [
        task(
            "pm_low_risk_no_order",
            "risk = 0.6*(100/400) + 0.4*0.1 = 0.19 < 0.6: no PM",
            {"machines": [_machine("M-LOW", 100.0, 400.0, 0.1)]},
            {"pm_machines": [], "risk_order": ["M-LOW"], "risks": {"M-LOW": 0.19}},
        ),
        task(
            "pm_high_runtime_triggers",
            "risk = 0.6*(500/400) = 0.75 >= 0.6: PM created",
            {"machines": [_machine("M-WORN", 500.0, 400.0, 0.0)]},
            {"pm_machines": ["M-WORN"], "risk_order": ["M-WORN"], "risks": {"M-WORN": 0.75}},
        ),
        task(
            "pm_vibration_alone_insufficient",
            "risk = 0.6*(100/400) + 0.4*1.0 = 0.55 < 0.6: vibration alone cannot trigger",
            {"machines": [_machine("M-SHAKY", 100.0, 400.0, 1.0)]},
            {"pm_machines": [], "risk_order": ["M-SHAKY"], "risks": {"M-SHAKY": 0.55}},
        ),
        task(
            "pm_exact_threshold_triggers",
            "risk = 0.6*(400/400) = 0.6 == threshold: PM created (>= comparison)",
            {"machines": [_machine("M-EDGE", 400.0, 400.0, 0.0)]},
            {"pm_machines": ["M-EDGE"], "risk_order": ["M-EDGE"], "risks": {"M-EDGE": 0.6}},
            tags=["threshold"],
        ),
        task(
            "pm_combined_wear_and_vibration",
            "risk = 0.6*(300/400) + 0.4*0.5 = 0.65 >= 0.6: PM created",
            {"machines": [_machine("M-COMBO", 300.0, 400.0, 0.5)]},
            {"pm_machines": ["M-COMBO"], "risk_order": ["M-COMBO"], "risks": {"M-COMBO": 0.65}},
        ),
        task(
            "pm_risk_ordering_across_fleet",
            "Fleet risks 0.75 > 0.55 > 0.19; only the 0.75 machine gets a PM",
            {"machines": [
                _machine("M-A", 100.0, 400.0, 0.1),   # 0.19
                _machine("M-B", 500.0, 400.0, 0.0),   # 0.75
                _machine("M-C", 100.0, 400.0, 1.0),   # 0.55
            ]},
            {
                "pm_machines": ["M-B"],
                "risk_order": ["M-B", "M-C", "M-A"],
                "risks": {"M-A": 0.19, "M-B": 0.75, "M-C": 0.55},
            },
            tags=["ordering"],
        ),
        task(
            "pm_risk_clamped_at_one",
            "risk = 0.6*(2000/400) + 0.4*1.0 = 3.4 -> clamped to 1.0: PM created",
            {"machines": [_machine("M-DYING", 2000.0, 400.0, 1.0)]},
            {"pm_machines": ["M-DYING"], "risk_order": ["M-DYING"], "risks": {"M-DYING": 1.0}},
            tags=["clamp"],
        ),
        task(
            "pm_telemetry_override",
            "Telemetry overrides stale machine fields: risk 0.75+0.4 -> 1.0: PM",
            {
                "machines": [_machine("M-TELE", 100.0, 400.0, 0.0)],
                "telemetry": {"M-TELE": {"runtime_hours_since_pm": 500.0,
                                         "vibration_trend": 1.0}},
            },
            {"pm_machines": ["M-TELE"], "risk_order": ["M-TELE"], "risks": {"M-TELE": 1.0}},
            tags=["telemetry"],
        ),
    ]


SPC_TASKS: List[GoldenTask] = _build_spc_tasks()
REORDER_TASKS: List[GoldenTask] = _build_reorder_tasks()
MAINTENANCE_TASKS: List[GoldenTask] = _build_maintenance_tasks()
