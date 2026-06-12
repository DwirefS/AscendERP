"""
Tests for the Manufacturing flavor seed data, scheduler, plant simulator,
and swarm scenario engine.
"""
from datetime import timedelta

import pytest

from flavors.manufacturing.data.seed import SEED_ANCHOR, build_seed
from flavors.manufacturing.models import (
    SchedulingPolicy,
    SimulationScenario,
    WorkOrderStatus,
)
from flavors.manufacturing.simulation import (
    PlantSimulator,
    PolicyScheduler,
    SwarmWorld,
)
from flavors.manufacturing.simulation.plant import DISPATCH_RULES, HOURS_PER_WEEK


@pytest.fixture(scope="module")
def seed_data():
    return build_seed(42)


@pytest.fixture(scope="module")
def default_schedule(seed_data):
    scheduler = PolicyScheduler(SchedulingPolicy())
    return scheduler.build_schedule(
        seed_data.work_orders, seed_data.machines, seed_data.products)


def _entry_hours(entry):
    """(start, end) of a schedule entry as hours from the seed anchor."""
    return ((entry.start - SEED_ANCHOR).total_seconds() / 3600.0,
            (entry.end - SEED_ANCHOR).total_seconds() / 3600.0)


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

class TestSeed:
    def test_seed_contents(self, seed_data):
        assert len(seed_data.machines) == 8
        assert {m.work_center for m in seed_data.machines} == {
            "cutting", "machining", "assembly"}
        assert len(seed_data.products) == 4
        for product in seed_data.products:
            assert 2 <= len(product.routing) <= 4
            assert product.bom
        assert len(seed_data.inventory) == 10
        for item in seed_data.inventory:
            assert item.reorder_point > 0
            assert item.lead_time_days > 0
        assert len(seed_data.suppliers) == 4
        assert len({s.otd_rate for s in seed_data.suppliers}) == 4
        assert len(seed_data.work_orders) == 12
        assert all(wo.status == WorkOrderStatus.RELEASED
                   for wo in seed_data.work_orders)
        due_offsets = [(wo.due_date - SEED_ANCHOR).total_seconds() / 3600.0
                       for wo in seed_data.work_orders]
        assert any(h <= 72 for h in due_offsets), "expected tight due dates"
        assert any(h >= 120 for h in due_offsets), "expected loose due dates"

    def test_seed_deterministic(self, seed_data):
        other = build_seed(42)
        assert [(w.work_order_id, w.product_id, w.quantity, w.due_date,
                 w.priority, w.customer_id) for w in seed_data.work_orders] == \
               [(w.work_order_id, w.product_id, w.quantity, w.due_date,
                 w.priority, w.customer_id) for w in other.work_orders]
        assert [(m.machine_id, m.units_per_hour, m.mtbf_hours,
                 m.vibration_trend) for m in seed_data.machines] == \
               [(m.machine_id, m.units_per_hour, m.mtbf_hours,
                 m.vibration_trend) for m in other.machines]
        assert [(i.material_id, i.on_hand, i.reorder_point)
                for i in seed_data.inventory] == \
               [(i.material_id, i.on_hand, i.reorder_point)
                for i in other.inventory]


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TestPolicyScheduler:
    def test_no_machine_overlaps(self, seed_data, default_schedule):
        for machine in seed_data.machines:
            entries = default_schedule.for_machine(machine.machine_id)
            for prev, nxt in zip(entries, entries[1:]):
                assert prev.end <= nxt.start + timedelta(seconds=1), (
                    f"overlap on {machine.machine_id}: "
                    f"{prev.end} > {nxt.start}")

    def test_all_open_work_orders_scheduled(self, seed_data, default_schedule):
        products = seed_data.products_by_id
        for wo in seed_data.work_orders:
            steps = products[wo.product_id].routing
            for step in steps:
                qty = sum(e.quantity for e in default_schedule.entries
                          if e.work_order_id == wo.work_order_id
                          and e.operation == step)
                assert qty == pytest.approx(wo.quantity), (
                    f"{wo.work_order_id} step {step} under-scheduled")

    def test_dispatch_rules_order_differently(self, seed_data):
        orderings = {}
        for rule in DISPATCH_RULES:
            schedule = PolicyScheduler(
                SchedulingPolicy(dispatch_rule=rule)).build_schedule(
                seed_data.work_orders, seed_data.machines, seed_data.products)
            first_seen = []
            for entry in schedule.entries:
                if entry.work_order_id not in first_seen:
                    first_seen.append(entry.work_order_id)
            orderings[rule] = tuple(first_seen)
        assert len(set(orderings.values())) >= 3, (
            f"dispatch rules should produce different queues: {orderings}")

    def test_unknown_dispatch_rule_rejected(self):
        with pytest.raises(ValueError):
            PolicyScheduler(SchedulingPolicy(dispatch_rule="LIFO"))

    def test_batch_size_factor_splits_lots(self, seed_data, default_schedule):
        split = PolicyScheduler(
            SchedulingPolicy(batch_size_factor=0.5)).build_schedule(
            seed_data.work_orders, seed_data.machines, seed_data.products)
        assert len(split.entries) == 2 * len(default_schedule.entries)

    def test_maintenance_buffer_respected(self, seed_data):
        buffer_h = 100.0
        schedule = PolicyScheduler(
            SchedulingPolicy(maintenance_buffer_hours=buffer_h)).build_schedule(
            seed_data.work_orders, seed_data.machines, seed_data.products)
        assert schedule.entries
        for entry in schedule.entries:
            start, end = _entry_hours(entry)
            for week in range(int(end // HOURS_PER_WEEK) + 1):
                window_start = week * HOURS_PER_WEEK + (HOURS_PER_WEEK - buffer_h)
                window_end = (week + 1) * HOURS_PER_WEEK
                overlaps = start < window_end - 1e-6 and end > window_start + 1e-6
                assert not overlaps, (
                    f"entry [{start:.1f}, {end:.1f}] overlaps maintenance "
                    f"window [{window_start:.1f}, {window_end:.1f}]")


# ---------------------------------------------------------------------------
# Plant simulator
# ---------------------------------------------------------------------------

class TestPlantSimulator:
    def test_same_seed_identical_kpis(self, seed_data, default_schedule):
        results = []
        for _ in range(2):
            sim = PlantSimulator(seed=42).load(
                machines=seed_data.machines, products=seed_data.products,
                inventory=seed_data.inventory,
                work_orders=seed_data.work_orders)
            results.append(sim.run(default_schedule, 168.0, replications=3))
        assert results[0].kpis.to_dict() == results[1].kpis.to_dict()
        assert len(results[0].events) == len(results[1].events)

    def test_different_seed_differs(self, seed_data, default_schedule):
        kpis = []
        for seed in (42, 1234):
            sim = PlantSimulator(seed=seed).load(
                machines=seed_data.machines, products=seed_data.products,
                inventory=seed_data.inventory,
                work_orders=seed_data.work_orders)
            kpis.append(sim.run(default_schedule, 168.0).kpis.to_dict())
        assert kpis[0] != kpis[1]

    def test_kpis_in_sane_ranges(self, default_schedule):
        sim = PlantSimulator(seed=42).load()  # defaults from data/seed.py
        result = sim.run(default_schedule, 168.0, replications=3)
        kpis = result.kpis
        assert 0.0 <= kpis.otd_rate <= 1.0
        assert 0.0 < kpis.oee <= 1.0
        assert 0.0 <= kpis.scrap_rate <= 0.3
        assert kpis.throughput_units > 0.0
        assert kpis.wip_units >= 0.0
        assert kpis.total_cost > 0.0
        assert 0.0 < kpis.makespan_hours <= 1.5 * 168.0
        assert result.replications == 3

    def test_breakdowns_on_low_mtbf_machine(self, seed_data):
        machines = build_seed(42).machines
        flaky = machines[0]
        flaky.mtbf_hours = 2.0
        flaky.vibration_trend = 0.9
        schedule = PolicyScheduler(SchedulingPolicy()).build_schedule(
            seed_data.work_orders, machines, seed_data.products)
        sim = PlantSimulator(seed=42).load(
            machines=machines, products=seed_data.products,
            inventory=seed_data.inventory, work_orders=seed_data.work_orders)
        result = sim.run(schedule, 168.0)
        breakdowns = [e for e in result.events if e.event_type == "breakdown"]
        assert breakdowns, "expected breakdown events with MTBF=2h"
        assert any(e.machine_id == flaky.machine_id for e in breakdowns)
        assert any(e.event_type == "repair" for e in result.events)


# ---------------------------------------------------------------------------
# Swarm scenario engine
# ---------------------------------------------------------------------------

class TestSwarmScenarios:
    def test_world_from_seed_entities(self, seed_data):
        world = SwarmWorld.from_seed(seed_data)
        kinds = {e.kind for e in world.entities.values()}
        assert kinds == {"supplier", "machine", "operator", "customer", "planner"}
        assert len([e for e in world.entities.values()
                    if e.kind == "supplier"]) == 4
        assert len([e for e in world.entities.values()
                    if e.kind == "machine"]) == 8
        planner = world.entities["PLN-1"]
        assert set(planner.relations) >= {"SUP-1", "M-CUT-01", "CUST-01"}

    def test_supplier_outage_scenario(self, seed_data):
        world = SwarmWorld.from_seed(seed_data)
        report = world.run_scenario(SimulationScenario(
            name="steel supplier dark",
            narrative="Primary metals supplier offline for two weeks",
            shock={"type": "supplier_outage", "supplier_id": "SUP-1", "days": 14},
            horizon_days=30, seed=7))
        event_types = {ev.event_type for ev in report.timeline}
        assert "late_delivery" in event_types
        assert "shortage_warning" in event_types
        assert "expedite_po" in event_types, "risk-averse planner should expedite"
        assert report.kpi_impact["otd_rate"] < 0.0
        assert report.kpi_impact["total_cost"] > 0.0
        assert report.recommendations
        assert report.risks
        assert 0.3 <= report.confidence <= 0.95
        # Reactions were written into entity memory and propagated.
        assert world.last_entities["PLN-1"].memory

    def test_demand_spike_scenario(self, seed_data):
        world = SwarmWorld.from_seed(seed_data)
        report = world.run_scenario(SimulationScenario(
            name="P-300 demand surge",
            narrative="Key account doubles call-offs for motorized units",
            shock={"type": "demand_spike", "product_id": "P-300", "factor": 1.8},
            horizon_days=21, seed=11))
        event_types = {ev.event_type for ev in report.timeline}
        assert "demand_spike" in event_types
        assert "capacity_pressure" in event_types, (
            "demand spike should raise throughput pressure")
        # More demand pushed through the plant: cost and makespan rise.
        assert report.kpi_impact["total_cost"] > 0.0
        assert report.kpi_impact["throughput_units"] != 0.0
        assert report.recommendations

    def test_machine_failure_scenario(self, seed_data):
        world = SwarmWorld.from_seed(seed_data)
        report = world.run_scenario(SimulationScenario(
            name="laser cutter down",
            narrative="Laser cutter optics failure removes cutting capacity",
            shock={"type": "machine_failure", "machine_id": "M-CUT-01", "days": 5},
            horizon_days=14, seed=3))
        event_types = {ev.event_type for ev in report.timeline}
        assert "machine_down" in event_types
        assert "reroute_jobs" in event_types
        assert "machine_repaired" in event_types
        # Losing the fastest cutter stretches the plan and degrades OEE/cost.
        assert report.kpi_impact["makespan_hours"] > 0.0
        assert report.kpi_impact["oee"] < 0.0
        assert report.kpi_impact["total_cost"] > 0.0
        assert report.recommendations

    def test_scenario_report_deterministic(self, seed_data):
        scenario_kwargs = dict(
            name="determinism probe",
            narrative="same scenario twice must match",
            shock={"type": "supplier_outage", "supplier_id": "SUP-2", "days": 10},
            horizon_days=21, seed=99)
        reports = []
        for _ in range(2):
            world = SwarmWorld.from_seed(build_seed(42))
            reports.append(world.run_scenario(
                SimulationScenario(**scenario_kwargs)))
        a, b = reports
        assert a.summary() == b.summary()
        assert [(e.day, e.actor_id, e.event_type, e.description)
                for e in a.timeline] == \
               [(e.day, e.actor_id, e.event_type, e.description)
                for e in b.timeline]
        assert a.confidence == b.confidence
        assert a.kpi_impact == b.kpi_impact

    def test_unsupported_shock_rejected(self, seed_data):
        world = SwarmWorld.from_seed(seed_data)
        with pytest.raises(ValueError):
            world.run_scenario(SimulationScenario(
                name="bad", narrative="unsupported",
                shock={"type": "alien_invasion"}, horizon_days=5, seed=1))
