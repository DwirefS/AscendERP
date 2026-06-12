"""
Tests for the manufacturing workflows and councils.

Workflows run end-to-end with small inline fixtures (no dependency on
data/seed.py) and without an LLM or memory substrate.
"""
from datetime import datetime, timedelta

import pytest

from flavors.manufacturing.models import (
    BOMLine,
    DispositionType,
    InventoryItem,
    Machine,
    MaintenanceType,
    MaintenanceWorkOrder,
    NonConformanceReport,
    Product,
    Supplier,
    WorkOrder,
    WorkOrderStatus,
)
from flavors.manufacturing.councils import (
    MaintenanceCouncil,
    QualityCouncil,
    SOPCouncil,
)
from flavors.manufacturing.workflows import (
    OrderToProductionWorkflow,
    PredictiveMaintenanceWorkflow,
    QualityRCAWorkflow,
    SupplyDisruptionResponseWorkflow,
)

NOW = datetime(2026, 6, 1, 8, 0, 0)


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


def make_product(product_id="P-1", material_id="RM-1") -> Product:
    return Product(
        product_id=product_id,
        name="Widget",
        routing=["machining"],
        bom=[BOMLine(material_id=material_id, quantity_per_unit=2.0)],
    )


# ---------------------------------------------------------------------------
# OrderToProductionWorkflow
# ---------------------------------------------------------------------------

async def test_order_to_production_end_to_end():
    workflow = OrderToProductionWorkflow()
    result = await workflow.run({
        "orders": [
            {"product_id": "P-1", "quantity": 20.0,
             "due_date": NOW + timedelta(days=5)},
        ],
        "products": [make_product()],
        "inventory": [InventoryItem("RM-1", "Steel", on_hand=100.0)],
        "machines": [make_machine()],
        "horizon_hours": 80.0,
        "now": NOW,
    })

    assert result["status"] == "completed"
    stages = result["stages"]
    for stage in ("order_intake", "mrp_planning", "release_work_orders",
                  "simulate", "kpi_summary"):
        assert stage in stages
    assert stages["order_intake"]["orders_received"] == 1
    assert stages["mrp_planning"]["success"] is True
    assert stages["mrp_planning"]["shortages"] == []
    # Sufficient inventory: the order is released, not held.
    assert len(stages["release_work_orders"]["released"]) == 1
    assert stages["release_work_orders"]["held"] == []
    released_wo = result["work_orders"][0]
    assert released_wo.status == WorkOrderStatus.RELEASED
    # Simulation either ran (simulator present) or skipped gracefully.
    if stages["simulate"].get("skipped"):
        assert "reason" in stages["simulate"]
    else:
        assert "kpis" in stages["simulate"]
    assert "kpis" in stages["kpi_summary"]


async def test_order_to_production_holds_orders_with_shortages():
    workflow = OrderToProductionWorkflow()
    result = await workflow.run({
        "orders": [
            {"product_id": "P-1", "quantity": 100.0,
             "due_date": NOW + timedelta(days=5)},
        ],
        "products": [make_product()],
        "inventory": [InventoryItem("RM-1", "Steel", on_hand=10.0)],
        "machines": [make_machine()],
        "simulate": False,
        "now": NOW,
    })

    assert result["status"] == "completed"
    stages = result["stages"]
    assert len(stages["mrp_planning"]["shortages"]) == 1
    assert stages["release_work_orders"]["released"] == []
    assert len(stages["release_work_orders"]["held"]) == 1
    assert result["work_orders"][0].status == WorkOrderStatus.ON_HOLD
    assert stages["simulate"]["skipped"] is True


# ---------------------------------------------------------------------------
# PredictiveMaintenanceWorkflow
# ---------------------------------------------------------------------------

async def test_predictive_maintenance_without_contention():
    workflow = PredictiveMaintenanceWorkflow()
    machines = [make_machine("M-1"), make_machine("M-2")]
    result = await workflow.run({
        "machines": machines,
        "telemetry": {
            "M-1": {"runtime_hours_since_pm": 380.0, "vibration_trend": 0.6},
            "M-2": {"runtime_hours_since_pm": 30.0, "vibration_trend": 0.05},
        },
        "available_buffer_hours": 16.0,
        "estimated_hours": 4.0,
    })

    assert result["status"] == "completed"
    stages = result["stages"]
    assert stages["risk_assessment"]["success"] is True
    assert stages["risk_assessment"]["risk_scores"]["M-1"] >= 0.6
    # 4h requested within the 16h buffer: no council needed.
    assert stages["council_allocation"]["convened"] is False
    assert len(result["pm_orders"]) == 1
    assert result["pm_orders"][0].machine_id == "M-1"
    assert result["pm_orders"][0].maintenance_type == MaintenanceType.PREDICTIVE


async def test_predictive_maintenance_contention_convenes_council():
    workflow = PredictiveMaintenanceWorkflow()
    machines = [make_machine("M-1"), make_machine("M-2")]
    result = await workflow.run({
        "machines": machines,
        "telemetry": {
            "M-1": {"runtime_hours_since_pm": 390.0, "vibration_trend": 0.9},
            "M-2": {"runtime_hours_since_pm": 350.0, "vibration_trend": 0.5},
        },
        "available_buffer_hours": 4.0,   # only one 4h job fits
        "estimated_hours": 4.0,
    })

    assert result["status"] == "completed"
    stages = result["stages"]
    assert stages["council_allocation"]["convened"] is True
    decision = stages["council_allocation"]["decision"]
    assert len(decision["granted"]) == 1
    assert len(decision["deferred"]) == 1
    # The highest-risk machine (M-1) wins the window.
    assert len(result["pm_orders"]) == 1
    assert result["pm_orders"][0].machine_id == "M-1"
    assert len(result["deferred_orders"]) == 1
    assert result["deferred_orders"][0].machine_id == "M-2"


# ---------------------------------------------------------------------------
# QualityRCAWorkflow
# ---------------------------------------------------------------------------

async def test_quality_rca_runs_8d_and_emits_capa():
    workflow = QualityRCAWorkflow()
    ncr = NonConformanceReport.new(
        work_order_id="WO-1",
        description="Diameter out of control on lathe line",
        severity="major",
        quantity_affected=12.0,
    )
    result = await workflow.run({
        "ncr": ncr,
        "event_data": {
            "machine_id": "M-3",
            "vibration_alarm": True,
            "tool_wear": "high spindle bearing wear detected",
        },
        "now": NOW,
    })

    assert result["status"] == "completed"
    stages = result["stages"]
    for step in ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8"):
        assert step in stages
    # Deterministic fishbone inference: machine signals dominate.
    assert stages["D4"]["root_cause_category"] == "machine"
    assert stages["D4"]["category_scores"]["machine"] >= 2
    capa = result["capa"]
    assert capa["ncr_id"] == ncr.ncr_id
    assert capa["root_cause_category"] == "machine"
    assert capa["status"] == "open"
    # Findings written back onto the NCR.
    assert ncr.root_cause is not None and "machine" in ncr.root_cause
    assert ncr.corrective_action is not None


# ---------------------------------------------------------------------------
# SupplyDisruptionResponseWorkflow
# ---------------------------------------------------------------------------

async def test_supply_disruption_response_end_to_end():
    workflow = SupplyDisruptionResponseWorkflow()
    suppliers = [
        Supplier("SUP-1", "Primary", materials=["RM-1"],
                 otd_rate=0.95, defect_ppm=300.0,
                 lead_time_days=7.0, price_index=1.0),
        Supplier("SUP-2", "Backup", materials=["RM-1"],
                 otd_rate=0.92, defect_ppm=600.0,
                 lead_time_days=10.0, price_index=1.1),
    ]
    inventory = [InventoryItem("RM-1", "Steel", on_hand=50.0,
                               reorder_point=40.0, unit_cost=3.0)]
    wo = WorkOrder.new("P-1", 30.0, NOW + timedelta(days=7))
    result = await workflow.run({
        "shock": {"type": "supplier_outage", "supplier_id": "SUP-1", "days": 14},
        "inventory": inventory,
        "suppliers": suppliers,
        "work_orders": [wo],
        "products": [make_product()],
        "machines": [make_machine()],
        "now": NOW,
    })

    assert result["status"] in ("completed", "completed_with_errors")
    stages = result["stages"]

    # Scenario stage produced a report (swarm engine or heuristic fallback).
    scenario = stages["swarm_scenario"]
    assert scenario["source"] in ("swarm", "heuristic_fallback")
    assert scenario["report"].get("risks")

    # Council factored scenario risks into its decision.
    decision = stages["sop_council"]["decision"]
    assert decision["scenario_considered"] is True
    assert decision["risks_considered"]
    assert "risk" in decision["rationale"].lower()

    # Affected work order was expedited.
    assert wo.work_order_id in stages["revised_plan"]["expedited_work_orders"]
    assert wo.priority.value >= 3  # HIGH or above

    # Expedited POs avoid the failed supplier.
    pos = result["expedited_purchase_orders"]
    assert len(pos) >= 1
    assert all(po.supplier_id != "SUP-1" for po in pos)
    assert pos[0].supplier_id == "SUP-2"


# ---------------------------------------------------------------------------
# Councils
# ---------------------------------------------------------------------------

async def test_quality_council_critical_requires_human_approval():
    council = QualityCouncil()
    ncr = NonConformanceReport.new(
        work_order_id="WO-9",
        description="Cracked housing, safety-relevant",
        severity="critical",
        quantity_affected=5.0,
    )
    decision = await council.decide(ncr)

    assert decision["requires_human_approval"] is True
    assert decision["disposition"] == DispositionType.SCRAP
    assert decision["severity"] == "critical"
    assert 0.0 <= decision["consensus_score"] <= 1.0
    assert len(decision["votes"]) >= 3


async def test_quality_council_major_recommends_rework_without_hitl():
    council = QualityCouncil()
    ncr = NonConformanceReport.new(
        work_order_id="WO-10",
        description="Surface finish out of spec",
        severity="major",
    )
    decision = await council.decide(ncr)

    assert decision["requires_human_approval"] is False
    assert decision["disposition"] == DispositionType.REWORK


async def test_sop_council_factors_scenario_risks_into_rationale():
    council = SOPCouncil()
    plan = {
        "open_work_orders": 4,
        "shortages": [{"material_id": "RM-1"}],
        "capacity": {"WC-1": {"overloaded": True}},
    }
    scenario_report = {
        "risks": ["Supplier SUP-1 outage starves RM-1 for 14 days"],
        "recommendations": ["Expedite purchase orders with alternate suppliers"],
        "kpi_impact": {"otd_rate": -0.12},
    }
    decision = await council.decide(plan, scenario_report)

    assert decision["scenario_considered"] is True
    assert decision["risks_considered"] == scenario_report["risks"]
    assert "Supplier SUP-1 outage" in decision["rationale"]
    assert any("RM-1" in adj for adj in decision["adjustments"])
    assert any("WC-1" in adj for adj in decision["adjustments"])
    assert len(decision["votes"]) == 3


async def test_maintenance_council_allocates_buffer_by_risk():
    council = MaintenanceCouncil()
    requests = [
        MaintenanceWorkOrder.new(
            "M-1", MaintenanceType.PREDICTIVE, "high risk",
            estimated_hours=4.0, risk_score=0.9,
        ),
        MaintenanceWorkOrder.new(
            "M-2", MaintenanceType.PREDICTIVE, "medium risk",
            estimated_hours=4.0, risk_score=0.7,
        ),
        MaintenanceWorkOrder.new(
            "M-3", MaintenanceType.PREDICTIVE, "lower risk",
            estimated_hours=4.0, risk_score=0.65,
        ),
    ]
    decision = await council.decide(requests, available_buffer_hours=8.0)

    assert decision["contention"] is True
    assert len(decision["granted"]) == 2
    assert len(decision["deferred"]) == 1
    # Granted in descending risk order; lowest risk is deferred.
    assert decision["granted"] == [
        requests[0].maintenance_id, requests[1].maintenance_id,
    ]
    assert decision["deferred"] == [requests[2].maintenance_id]
    assert decision["allocated_hours"] == pytest.approx(8.0)
