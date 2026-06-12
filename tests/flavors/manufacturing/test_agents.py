"""
Tests for the six manufacturing PRREEL agents.

All agents run the full perceive/retrieve/reason/execute/verify/learn loop
without an LLM or memory substrate; fixtures are built inline (no dependency
on data/seed.py).
"""
from datetime import datetime, timedelta

import pytest

from src.core.agent.base import AgentContext
from flavors.manufacturing.models import (
    BOMLine,
    DispositionType,
    InventoryItem,
    Machine,
    MaintenanceType,
    POStatus,
    Product,
    QualityInspection,
    Supplier,
    WorkOrder,
)
from flavors.manufacturing.agents import (
    EHSComplianceAgent,
    InventoryAgent,
    MaintenanceAgent,
    ProcurementAgent,
    ProductionPlannerAgent,
    QualityAgent,
)

NOW = datetime(2026, 6, 1, 8, 0, 0)


def make_context() -> AgentContext:
    return AgentContext(trace_id="trace-mfg-test", tenant_id="tenant-test")


def make_machine(machine_id="M-1", **kw) -> Machine:
    defaults = dict(
        name=f"Machine {machine_id}",
        work_center="WC-1",
        operations=["machining"],
        units_per_hour=10.0,
        setup_minutes=30.0,
    )
    defaults.update(kw)
    return Machine(machine_id=machine_id, **defaults)


def make_product(product_id="P-1") -> Product:
    return Product(
        product_id=product_id,
        name="Widget",
        routing=["machining"],
        bom=[BOMLine(material_id="RM-1", quantity_per_unit=2.0)],
    )


# ---------------------------------------------------------------------------
# ProductionPlannerAgent
# ---------------------------------------------------------------------------

async def test_production_planner_full_run_with_shortage():
    agent = ProductionPlannerAgent()
    wo = WorkOrder.new("P-1", 50.0, NOW + timedelta(days=3))
    result = await agent.run({
        "work_orders": [wo],
        "products": [make_product()],
        "inventory": [InventoryItem("RM-1", "Raw steel", on_hand=60.0)],
        "machines": [make_machine()],
        "horizon_hours": 80.0,
        "now": NOW,
    }, make_context())

    assert result.success
    output = result.output
    # MRP explosion: 50 units x 2.0 per unit = 100 required, 60 available
    assert output["material_requirements"]["RM-1"] == pytest.approx(100.0)
    assert len(output["shortages"]) == 1
    assert output["shortages"][0]["material_id"] == "RM-1"
    assert output["shortages"][0]["shortage"] == pytest.approx(40.0)
    assert len(output["schedule"].entries) >= 1
    assert "WC-1" in output["capacity"]
    assert output["capacity"]["WC-1"]["overloaded"] is False
    assert result.confidence > 0


async def test_production_planner_flags_capacity_overload():
    agent = ProductionPlannerAgent()
    wo = WorkOrder.new("P-1", 200.0, NOW + timedelta(days=1))
    result = await agent.run({
        "work_orders": [wo],
        "products": [make_product()],
        "inventory": [InventoryItem("RM-1", "Raw steel", on_hand=1000.0)],
        "machines": [make_machine(units_per_hour=10.0)],
        "horizon_hours": 4.0,  # 200 units need ~20h on one machine
        "now": NOW,
    }, make_context())

    assert result.success
    capacity = result.output["capacity"]["WC-1"]
    assert capacity["required_hours"] > capacity["available_hours"]
    assert capacity["overloaded"] is True


# ---------------------------------------------------------------------------
# QualityAgent — SPC
# ---------------------------------------------------------------------------

def _inspection(measurements, usl=13.5, lsl=6.5, nominal=10.0):
    return QualityInspection(
        inspection_id="INSP-1",
        work_order_id="WO-1",
        characteristic="diameter_mm",
        measurements=measurements,
        nominal=nominal,
        usl=usl,
        lsl=lsl,
    )


async def test_quality_in_control_series_stays_quiet():
    agent = QualityAgent()
    # Alternating small deviations: no WE rule should fire.
    deviations = [0.5, -0.5, 1.0, -1.0, 0.2, -0.2] * 3
    measurements = [10.0 + d for d in deviations]
    result = await agent.run(
        {"inspection": _inspection(measurements)}, make_context()
    )

    assert result.success
    output = result.output
    assert output["in_control"] is True
    assert output["rules_fired"] == []
    assert output["ncr"] is None
    assert output["recommended_disposition"] is None


async def test_quality_rule1_fires_and_creates_ncr():
    agent = QualityAgent()
    # Tight series with one extreme outlier -> Rule 1.
    measurements = [10.0 + (0.1 if i % 2 else -0.1) for i in range(24)] + [13.0]
    result = await agent.run(
        {"inspection": _inspection(measurements)}, make_context()
    )

    assert result.success
    output = result.output
    assert output["in_control"] is False
    assert "rule1_one_beyond_3_sigma" in output["rules_fired"]
    assert output["ncr"] is not None
    assert output["ncr"].work_order_id == "WO-1"
    assert output["recommended_disposition"] is not None


async def test_quality_rule4_eight_consecutive_same_side():
    agent = QualityAgent()
    # 10 points all above the nominal center line -> Rule 4.
    measurements = [10.2, 10.3, 10.25, 10.35, 10.2, 10.3, 10.25, 10.3, 10.2, 10.3]
    result = await agent.run(
        {"inspection": _inspection(measurements)}, make_context()
    )

    assert result.success
    output = result.output
    assert output["in_control"] is False
    assert "rule4_eight_consecutive_same_side" in output["rules_fired"]


def test_quality_cpk_math_spot_check():
    # xbar=10, sample sigma=2 -> Cp=(16-4)/(6*2)=1.0, Cpk=min(6,6)/(3*2)=1.0
    xbar, sigma, cp, cpk = QualityAgent.compute_capability(
        [8.0, 10.0, 12.0], nominal=10.0, usl=16.0, lsl=4.0
    )
    assert xbar == pytest.approx(10.0)
    assert sigma == pytest.approx(2.0)
    assert cp == pytest.approx(1.0)
    assert cpk == pytest.approx(1.0)

    # Off-center process: xbar=12 -> Cpk=min(16-12, 12-4)/(3*2)=4/6
    _, _, _, cpk_off = QualityAgent.compute_capability(
        [10.0, 12.0, 14.0], nominal=10.0, usl=16.0, lsl=4.0
    )
    assert cpk_off == pytest.approx(4.0 / 6.0)


async def test_quality_low_cpk_grades_critical_and_recommends_scrap():
    agent = QualityAgent()
    # Outlier + very tight specs -> Cpk far below 0.7 -> critical -> SCRAP.
    measurements = [10.0 + (0.1 if i % 2 else -0.1) for i in range(24)] + [13.0]
    result = await agent.run(
        {"inspection": _inspection(measurements, usl=10.4, lsl=9.6)},
        make_context(),
    )

    assert result.success
    output = result.output
    assert output["stats"]["cpk"] < 0.7
    assert output["ncr"].severity == "critical"
    assert output["recommended_disposition"] == DispositionType.SCRAP


# ---------------------------------------------------------------------------
# MaintenanceAgent
# ---------------------------------------------------------------------------

def test_maintenance_risk_monotonicity():
    base = dict(mtbf_hours=400.0, vibration_trend=0.2)
    low = make_machine("M-low", runtime_hours_since_pm=100.0, **base)
    mid = make_machine("M-mid", runtime_hours_since_pm=200.0, **base)
    high = make_machine("M-high", runtime_hours_since_pm=300.0, **base)
    assert (
        MaintenanceAgent.compute_risk(low)
        < MaintenanceAgent.compute_risk(mid)
        < MaintenanceAgent.compute_risk(high)
    )

    calm = make_machine("M-calm", runtime_hours_since_pm=200.0,
                        mtbf_hours=400.0, vibration_trend=0.1)
    shaky = make_machine("M-shaky", runtime_hours_since_pm=200.0,
                         mtbf_hours=400.0, vibration_trend=0.6)
    assert MaintenanceAgent.compute_risk(calm) < MaintenanceAgent.compute_risk(shaky)


async def test_maintenance_creates_predictive_order_above_threshold():
    agent = MaintenanceAgent()
    risky = make_machine(
        "M-risky", runtime_hours_since_pm=380.0,
        mtbf_hours=400.0, vibration_trend=0.5,
    )
    healthy = make_machine(
        "M-healthy", runtime_hours_since_pm=50.0,
        mtbf_hours=400.0, vibration_trend=0.0,
    )
    result = await agent.run({
        "machines": [risky, healthy],
        "risk_threshold": 0.6,
        "now": NOW,
    }, make_context())

    assert result.success
    output = result.output
    assert output["risk_scores"]["M-risky"] >= 0.6
    assert output["risk_scores"]["M-healthy"] < 0.6
    orders = output["maintenance_orders"]
    assert len(orders) == 1
    order = orders[0]
    assert order.machine_id == "M-risky"
    assert order.maintenance_type == MaintenanceType.PREDICTIVE
    assert order.scheduled_start is not None
    assert order.risk_score == pytest.approx(output["risk_scores"]["M-risky"])


# ---------------------------------------------------------------------------
# ProcurementAgent
# ---------------------------------------------------------------------------

async def test_procurement_reorder_and_approval_threshold():
    agent = ProcurementAgent()
    supplier = Supplier(
        supplier_id="SUP-1", name="Acme", materials=["RM-BIG", "RM-SMALL"],
        otd_rate=0.97, defect_ppm=200.0, lead_time_days=5.0, price_index=1.0,
    )
    big = InventoryItem("RM-BIG", "Costly alloy", on_hand=100.0,
                        reorder_point=400.0, unit_cost=100.0)
    small = InventoryItem("RM-SMALL", "Cheap bolt", on_hand=10.0,
                          reorder_point=50.0, unit_cost=1.0)
    result = await agent.run({
        "inventory": [big, small],
        "suppliers": [supplier],
        "now": NOW,
    }, make_context())

    assert result.success
    pos = {po.material_id: po for po in result.output["purchase_orders"]}
    assert set(pos) == {"RM-BIG", "RM-SMALL"}
    # 700 units x $100 = $70,000 > $50,000 policy threshold
    assert pos["RM-BIG"].total_cost > 50_000
    assert pos["RM-BIG"].status == POStatus.PENDING_APPROVAL
    assert pos["RM-SMALL"].total_cost <= 50_000
    assert pos["RM-SMALL"].status == POStatus.APPROVED


async def test_procurement_picks_best_scored_supplier():
    agent = ProcurementAgent()
    good = Supplier("SUP-GOOD", "Good Co", materials=["RM-1"],
                    otd_rate=0.98, defect_ppm=100.0,
                    lead_time_days=5.0, price_index=1.0)
    bad = Supplier("SUP-BAD", "Bad Co", materials=["RM-1"],
                   otd_rate=0.80, defect_ppm=5000.0,
                   lead_time_days=20.0, price_index=1.4)
    item = InventoryItem("RM-1", "Steel", on_hand=5.0,
                         reorder_point=20.0, unit_cost=2.0)
    result = await agent.run({
        "inventory": [item],
        "suppliers": [bad, good],
        "now": NOW,
    }, make_context())

    assert result.success
    scores = result.output["supplier_scores"]
    assert scores["SUP-GOOD"] > scores["SUP-BAD"]
    pos = result.output["purchase_orders"]
    assert len(pos) == 1
    assert pos[0].supplier_id == "SUP-GOOD"


# ---------------------------------------------------------------------------
# InventoryAgent
# ---------------------------------------------------------------------------

async def test_inventory_abc_classification():
    agent = InventoryAgent()
    items = [
        InventoryItem("RM-A", "High runner", on_hand=10.0, unit_cost=10.0),
        InventoryItem("RM-B", "Mid runner", on_hand=10.0, unit_cost=10.0),
        InventoryItem("RM-C", "Slow mover", on_hand=10.0, unit_cost=10.0),
    ]
    result = await agent.run({
        "inventory": items,
        "annual_demand": {"RM-A": 800.0, "RM-B": 150.0, "RM-C": 50.0},
    }, make_context())

    assert result.success
    abc = result.output["abc_classes"]
    assert abc == {"RM-A": "A", "RM-B": "B", "RM-C": "C"}


async def test_inventory_safety_stock_and_shortage_projection():
    agent = InventoryAgent()
    item = InventoryItem("RM-1", "Steel", on_hand=40.0, on_order=10.0,
                         unit_cost=5.0, lead_time_days=9.0)
    wo = WorkOrder.new("P-1", 50.0, NOW + timedelta(days=5))
    result = await agent.run({
        "inventory": [item],
        "demand_sigma": {"RM-1": 4.0},
        "service_level_z": 1.65,
        "work_orders": [wo],
        "products": [make_product()],
    }, make_context())

    assert result.success
    output = result.output
    # ss = z * sigma_d * sqrt(LT) = 1.65 * 4 * 3 = 19.8
    assert output["safety_stocks"]["RM-1"] == pytest.approx(19.8)
    # 50 units x 2.0/unit = 100 required vs 50 available
    shortages = output["projected_shortages"]
    assert len(shortages) == 1
    assert shortages[0]["material_id"] == "RM-1"
    assert shortages[0]["shortage"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# EHSComplianceAgent
# ---------------------------------------------------------------------------

async def test_ehs_triage_loto_and_calendar():
    agent = EHSComplianceAgent()
    result = await agent.run({
        "incidents": [
            {"incident_id": "INC-1", "severity": 5, "likelihood": 4},
            {"incident_id": "INC-2", "severity": 2, "likelihood": 2},
        ],
        "loto_checklist": {
            "notify_affected_employees": True,
            "shutdown_equipment": True,
            "isolate_energy_sources": True,
            "apply_locks_and_tags": True,
            "release_stored_energy": True,
            # "verify_zero_energy" intentionally missing
        },
        "calendar_items": [
            {"name": "OSHA audit", "type": "audit",
             "date": NOW + timedelta(days=10)},
            {"name": "Forklift training", "type": "training",
             "date": NOW - timedelta(days=2)},
        ],
        "today": NOW,
    }, make_context())

    assert result.success
    output = result.output

    triage = {t["incident_id"]: t for t in output["incident_triage"]}
    assert triage["INC-1"]["risk_score"] == 20
    assert triage["INC-1"]["priority"] == "critical"
    assert triage["INC-1"]["requires_human_approval"] is True
    assert triage["INC-2"]["priority"] == "medium"

    assert output["loto"]["passed"] is False
    assert "verify_zero_energy" in output["loto"]["missing_or_failed_steps"]

    calendar = output["compliance_calendar"]
    assert len(calendar["upcoming"]) == 1
    assert len(calendar["overdue"]) == 1
    assert calendar["overdue"][0]["name"] == "Forklift training"
