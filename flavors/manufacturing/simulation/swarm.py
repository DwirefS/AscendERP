"""
MiroFish-inspired swarm scenario engine for the Manufacturing flavor.

Builds a lightweight "digital world" of the plant and supply network —
suppliers, machines, operators, customers, and a planner as persona entities
with memory and relations — and replays what-if shocks day by day. Entities
react via deterministic persona-driven rules (a risk-averse planner expedites
POs, an opportunistic supplier raises prices, customers churn after enough
late days), reactions propagate along relations into entity memory, and the
engine emits :class:`~flavors.manufacturing.models.ScenarioEvent` timelines.

KPI impact is estimated by re-running :class:`PlantSimulator` on the shocked
vs. baseline plant where the shock is plant-shaped (machine failure, demand
spike), or analytically for supply-side shocks. Confidence is derived from
event variance across 3 sub-seeded runs. Deterministic given ``scenario.seed``.
"""
import copy
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog

from flavors.manufacturing.data.seed import DEMAND_BASIS_DAYS, FactorySeed, build_seed
from flavors.manufacturing.models import (
    KPISnapshot,
    ScenarioEvent,
    ScenarioReport,
    SchedulingPolicy,
    SimulationScenario,
)
from flavors.manufacturing.simulation.plant import PlantSimulator, PolicyScheduler

logger = structlog.get_logger()

SUPPORTED_SHOCKS = (
    "supplier_outage", "demand_spike", "machine_failure", "material_price_spike",
)

_SUB_RUNS = 3
_SIM_HORIZON_HOURS = 168.0


@dataclass
class SwarmEntity:
    """One persona agent in the digital plant world."""
    entity_id: str
    kind: str                                   # supplier|machine|operator|customer|planner
    persona: Dict[str, Any] = field(default_factory=dict)
    memory: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)

    def remember(self, day: int, event_type: str, actor_id: str,
                 detail: Optional[Dict[str, Any]] = None) -> None:
        """Append an observed event to this entity's memory."""
        self.memory.append({
            "day": day, "event": event_type, "from": actor_id,
            "detail": detail or {},
        })

    def recalls(self, event_type: str, since_day: int = 0) -> bool:
        """True if an event of this type is in memory at/after ``since_day``."""
        return any(m["event"] == event_type and m["day"] >= since_day
                   for m in self.memory)


class SwarmWorld:
    """
    The digital plant + supply network as a population of persona entities.

    ``run_scenario`` is pure with respect to the world template: each run
    works on deep copies so repeated runs of the same scenario are identical.
    The entity state of the primary run is exposed as ``last_entities``.
    """

    def __init__(self, entities: List[SwarmEntity], seed_data: FactorySeed):
        self.entities: Dict[str, SwarmEntity] = {e.entity_id: e for e in entities}
        self.seed_data = seed_data
        self.last_entities: Dict[str, SwarmEntity] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_seed(cls, seed_data: Optional[FactorySeed] = None) -> "SwarmWorld":
        """Build the world from a factory seed (default: ``build_seed()``)."""
        seed_data = seed_data or build_seed()
        entities: List[SwarmEntity] = []
        planner_id = "PLN-1"

        for sup in seed_data.suppliers:
            opportunism = min(1.0, round(
                (1.0 - sup.otd_rate) * 2.0
                + (0.15 if sup.region == "overseas" else 0.0), 3))
            entities.append(SwarmEntity(
                entity_id=sup.supplier_id, kind="supplier",
                persona={"reliability": sup.otd_rate,
                         "opportunism": opportunism,
                         "lead_time_days": sup.lead_time_days,
                         "price_index": sup.price_index},
                relations=[planner_id],
                state={"materials": list(sup.materials), "available": True},
            ))

        operator_ids = ["OP-1", "OP-2", "OP-3"]
        for i, machine in enumerate(seed_data.machines):
            fragility = min(1.0, round(
                80.0 / max(machine.mtbf_hours, 1.0)
                + 0.5 * machine.vibration_trend, 3))
            entities.append(SwarmEntity(
                entity_id=machine.machine_id, kind="machine",
                persona={"fragility": fragility,
                         "vibration": machine.vibration_trend},
                relations=[planner_id, operator_ids[i % len(operator_ids)]],
                state={"work_center": machine.work_center, "down": False},
            ))

        operator_personas = [
            ("OP-1", {"caution": 0.85, "skill": 0.9, "tenure_years": 18}),
            ("OP-2", {"caution": 0.30, "skill": 0.45, "tenure_years": 1}),
            ("OP-3", {"caution": 0.55, "skill": 0.7, "hustle": 0.8}),
        ]
        for op_id, persona in operator_personas:
            entities.append(SwarmEntity(
                entity_id=op_id, kind="operator", persona=dict(persona),
                relations=[planner_id], state={"fatigue": 0.0},
            ))

        for i, cust_id in enumerate(seed_data.customer_ids):
            entities.append(SwarmEntity(
                entity_id=cust_id, kind="customer",
                persona={"patience_days": 3 + (i % 4), "loyalty": 0.5 + 0.1 * (i % 5)},
                relations=[planner_id],
                state={"late_days": 0, "churned": False},
            ))

        entities.append(SwarmEntity(
            entity_id=planner_id, kind="planner",
            persona={"risk_aversion": 0.7, "flexibility": 0.6},
            relations=[e.entity_id for e in entities],
            state={"expedited_materials": [], "warned_materials": []},
        ))
        logger.debug("swarm_world_built", entities=len(entities))
        return cls(entities, seed_data)

    # ------------------------------------------------------------------
    # Scenario execution
    # ------------------------------------------------------------------

    def run_scenario(self, scenario: SimulationScenario) -> ScenarioReport:
        """
        Run a what-if scenario and produce a prediction report.

        The timeline comes from the primary sub-run; confidence is derived
        from event-count variance across ``_SUB_RUNS`` sub-seeded runs;
        kpi_impact compares shocked vs. baseline plant performance.
        """
        shock_type = scenario.shock.get("type")
        if shock_type not in SUPPORTED_SHOCKS:
            raise ValueError(
                f"Unsupported shock type {shock_type!r}; "
                f"expected one of {SUPPORTED_SHOCKS}")

        runs: List[Tuple[List[ScenarioEvent], Dict[str, SwarmEntity]]] = [
            self._simulate_timeline(scenario, sub) for sub in range(_SUB_RUNS)
        ]
        timeline, self.last_entities = runs[0]
        kpi_impact = self._kpi_impact(scenario)
        risks, recommendations = self._derive_findings(timeline, scenario)
        confidence = self._confidence([events for events, _ in runs])

        logger.info(
            "scenario_complete",
            scenario=scenario.name,
            shock=shock_type,
            events=len(timeline),
            confidence=confidence,
        )
        return ScenarioReport(
            scenario=scenario,
            timeline=timeline,
            kpi_impact=kpi_impact,
            risks=risks,
            recommendations=recommendations,
            confidence=confidence,
        )

    # ------------------------------------------------------------------
    # Day-by-day world loop
    # ------------------------------------------------------------------

    def _simulate_timeline(
        self, scenario: SimulationScenario, sub_run: int,
    ) -> Tuple[List[ScenarioEvent], Dict[str, SwarmEntity]]:
        """One sub-seeded day-by-day run over deep-copied entities."""
        rng = np.random.default_rng([max(0, scenario.seed), sub_run])
        ents = copy.deepcopy(self.entities)
        shock = scenario.shock
        ctx: Dict[str, Any] = {
            "type": shock.get("type"),
            "shock": shock,
            "days": int(shock.get("days", 7)),
            "factor": float(shock.get("factor", 1.5)),
            "horizon": scenario.horizon_days,
            "ents": ents,
            "late": False,
            "coverage": self._initial_coverage(shock),
            "backlog": 0.0,
        }
        events: List[ScenarioEvent] = []
        events.extend(self._bootstrap_events(ctx))

        for day in range(scenario.horizon_days):
            day_events: List[ScenarioEvent] = []
            for entity_id in sorted(ents):
                entity = ents[entity_id]
                handler = getattr(self, f"_react_{entity.kind}", None)
                if handler:
                    day_events.extend(handler(entity, day, ctx, rng))
            # Propagate along relations: every related entity remembers.
            for ev in day_events:
                actor = ents.get(ev.actor_id)
                if actor is None:
                    continue
                actor.remember(ev.day, ev.event_type, ev.actor_id, ev.impact)
                for rel_id in actor.relations:
                    if rel_id in ents:
                        ents[rel_id].remember(ev.day, ev.event_type,
                                              ev.actor_id, ev.impact)
            events.extend(day_events)
            self._end_of_day(day, ctx)
        return events, ents

    def _initial_coverage(self, shock: Dict[str, Any]) -> Dict[str, float]:
        """Days of stock coverage for materials affected by a supply shock."""
        if shock.get("type") != "supplier_outage":
            return {}
        supplier = next((s for s in self.seed_data.suppliers
                         if s.supplier_id == shock.get("supplier_id")), None)
        if supplier is None:
            return {}
        usage = self._daily_usage()
        coverage = {}
        for item in self.seed_data.inventory:
            if item.material_id in supplier.materials:
                daily = max(usage.get(item.material_id, 0.0), 1e-6)
                coverage[item.material_id] = item.on_hand / daily
        return coverage

    def _daily_usage(self) -> Dict[str, float]:
        """Approximate daily material usage from the open order book."""
        products = self.seed_data.products_by_id
        usage: Dict[str, float] = defaultdict(float)
        for wo in self.seed_data.work_orders:
            product = products.get(wo.product_id)
            if product is None:
                continue
            for line in product.bom:
                usage[line.material_id] += (
                    line.quantity_per_unit * wo.quantity / DEMAND_BASIS_DAYS)
        return dict(usage)

    def _bootstrap_events(self, ctx: Dict[str, Any]) -> List[ScenarioEvent]:
        """Day-0 shock announcement events."""
        shock = ctx["shock"]
        stype = ctx["type"]
        if stype == "supplier_outage":
            sid = shock.get("supplier_id", "SUP-1")
            if sid in ctx["ents"]:
                ctx["ents"][sid].state["available"] = False
            return [ScenarioEvent(
                day=0, actor_id=sid, event_type="outage_start",
                description=f"Supplier {sid} goes dark for {ctx['days']} days",
                impact={"days": ctx["days"]})]
        if stype == "demand_spike":
            pid = shock.get("product_id", "P-300")
            actor = self.seed_data.customer_ids[0]
            return [ScenarioEvent(
                day=0, actor_id=actor, event_type="demand_spike",
                description=(f"Customer demand for {pid} jumps "
                             f"x{ctx['factor']:.2f}"),
                impact={"product_id": pid, "factor": ctx["factor"]})]
        if stype == "machine_failure":
            mid = shock.get("machine_id", "M-MILL-02")
            if mid in ctx["ents"]:
                ctx["ents"][mid].state["down"] = True
            return [ScenarioEvent(
                day=0, actor_id=mid, event_type="machine_down",
                description=f"Machine {mid} suffers a hard failure",
                impact={"days": ctx["days"]})]
        # material_price_spike
        mat = shock.get("material_id", "RM-STEEL")
        item = next((i for i in self.seed_data.inventory
                     if i.material_id == mat), None)
        actor = (item.preferred_supplier_id if item and item.preferred_supplier_id
                 else "SUP-1")
        return [ScenarioEvent(
            day=0, actor_id=actor, event_type="price_increase",
            description=(f"Market price of {mat} spikes "
                         f"x{ctx['factor']:.2f}"),
            impact={"material_id": mat, "factor": ctx["factor"]})]

    def _end_of_day(self, day: int, ctx: Dict[str, Any]) -> None:
        """Advance world-level state: stock burn-down, replenishment, lateness."""
        if ctx["type"] == "supplier_outage":
            restored = day >= ctx["days"]
            for mat in ctx["coverage"]:
                if restored:
                    ctx["coverage"][mat] = min(
                        ctx["coverage"][mat] + 3.0, 30.0)
                else:
                    ctx["coverage"][mat] -= 1.0
            ctx["late"] = any(c <= 0.0 for c in ctx["coverage"].values())
        elif ctx["type"] == "machine_failure":
            ctx["late"] = 2 <= day < ctx["days"] + 3
        elif ctx["type"] == "demand_spike":
            ctx["backlog"] += max(0.0, ctx["factor"] - 1.0) * 10.0
            ctx["late"] = ctx["backlog"] > 60.0

    # ------------------------------------------------------------------
    # Persona reaction rules (deterministic, trait-driven)
    # ------------------------------------------------------------------

    def _react_supplier(self, entity: SwarmEntity, day: int,
                        ctx: Dict[str, Any], rng: np.random.Generator,
                        ) -> List[ScenarioEvent]:
        events: List[ScenarioEvent] = []
        stype = ctx["type"]
        affected = entity.entity_id == ctx["shock"].get("supplier_id")
        if stype == "supplier_outage" and affected:
            if day < ctx["days"]:
                cadence = max(2, int(entity.persona["lead_time_days"] // 3))
                if day % cadence == 0:
                    events.append(ScenarioEvent(
                        day=day, actor_id=entity.entity_id,
                        event_type="late_delivery",
                        description=(f"{entity.entity_id} misses scheduled "
                                     f"deliveries (outage day {day + 1})"),
                        impact={"materials": entity.state["materials"]}))
            elif day == ctx["days"]:
                entity.state["available"] = True
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="supply_restored",
                    description=f"{entity.entity_id} resumes deliveries"))
            return events

        # Reactions to requests received via relations/memory yesterday.
        asked = (entity.recalls("expedite_po", since_day=day - 1)
                 or entity.recalls("order_increase", since_day=day - 1))
        if asked and not entity.state.get("responded"):
            entity.state["responded"] = True
            if entity.persona["opportunism"] > 0.5:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="price_increase",
                    description=(f"{entity.entity_id} opportunistically raises "
                                 f"prices on rush volume"),
                    impact={"factor": round(
                        1.0 + 0.2 * entity.persona["opportunism"], 3)}))
            else:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="rush_order_accepted",
                    description=(f"{entity.entity_id} accepts expedited order "
                                 f"at standard terms")))
        if (ctx["type"] == "material_price_spike" and not affected
                and entity.persona["opportunism"] > 0.6
                and entity.recalls("price_increase", since_day=day - 1)
                and not entity.state.get("matched")):
            entity.state["matched"] = True
            events.append(ScenarioEvent(
                day=day, actor_id=entity.entity_id, event_type="price_match",
                description=f"{entity.entity_id} follows the market price up"))
        return events

    def _react_machine(self, entity: SwarmEntity, day: int,
                       ctx: Dict[str, Any], rng: np.random.Generator,
                       ) -> List[ScenarioEvent]:
        events: List[ScenarioEvent] = []
        stype = ctx["type"]
        if stype == "machine_failure" and entity.entity_id == ctx["shock"].get(
                "machine_id", "M-MILL-02"):
            if day == ctx["days"]:
                entity.state["down"] = False
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="machine_repaired",
                    description=f"{entity.entity_id} back in service"))
            elif 0 < day < ctx["days"]:
                if day == 1:
                    events.append(ScenarioEvent(
                        day=day, actor_id=entity.entity_id,
                        event_type="capacity_lost",
                        description=(f"{entity.entity_id} down; "
                                     f"{entity.state['work_center']} capacity "
                                     f"reduced")))
            return events
        if stype == "demand_spike" and not entity.state.get("down"):
            stress = entity.persona["fragility"] * 0.12 * ctx["factor"]
            if float(rng.random()) < stress:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="breakdown_risk",
                    description=(f"{entity.entity_id} shows stress symptoms "
                                 f"under elevated load"),
                    impact={"fragility": entity.persona["fragility"]}))
        return events

    def _react_operator(self, entity: SwarmEntity, day: int,
                        ctx: Dict[str, Any], rng: np.random.Generator,
                        ) -> List[ScenarioEvent]:
        events: List[ScenarioEvent] = []
        if ctx["type"] == "demand_spike":
            entity.state["fatigue"] += 0.04 * ctx["factor"]
            if (entity.state["fatigue"] > 0.5
                    and entity.persona["caution"] < 0.5
                    and not entity.state.get("warned")):
                entity.state["warned"] = True
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="fatigue_warning",
                    description=(f"Operator {entity.entity_id} flags fatigue "
                                 f"after sustained overtime")))
        if (ctx["type"] == "machine_failure" and day == 1
                and entity.recalls("machine_down")
                and entity.persona.get("skill", 0.0) > 0.6
                and not entity.state.get("workaround")):
            entity.state["workaround"] = True
            events.append(ScenarioEvent(
                day=day, actor_id=entity.entity_id,
                event_type="manual_workaround",
                description=(f"Operator {entity.entity_id} reroutes work "
                             f"manually around the down machine")))
        return events

    def _react_customer(self, entity: SwarmEntity, day: int,
                        ctx: Dict[str, Any], rng: np.random.Generator,
                        ) -> List[ScenarioEvent]:
        events: List[ScenarioEvent] = []
        if entity.state["churned"]:
            return events
        if ctx["late"]:
            entity.state["late_days"] += 1
        patience = entity.persona["patience_days"]
        if entity.state["late_days"] == patience:
            events.append(ScenarioEvent(
                day=day, actor_id=entity.entity_id, event_type="churn_warning",
                description=(f"{entity.entity_id} escalates after "
                             f"{patience} late days"),
                impact={"late_days": entity.state["late_days"]}))
        elif entity.state["late_days"] >= patience + 4:
            entity.state["churned"] = True
            events.append(ScenarioEvent(
                day=day, actor_id=entity.entity_id, event_type="order_cancelled",
                description=f"{entity.entity_id} cancels open orders and churns"))
        return events

    def _react_planner(self, entity: SwarmEntity, day: int,
                       ctx: Dict[str, Any], rng: np.random.Generator,
                       ) -> List[ScenarioEvent]:
        events: List[ScenarioEvent] = []
        stype = ctx["type"]
        risk_averse = entity.persona["risk_aversion"] > 0.5

        if stype == "supplier_outage":
            for mat, cov in sorted(ctx["coverage"].items()):
                if cov <= 5.0 and mat not in entity.state["warned_materials"]:
                    entity.state["warned_materials"].append(mat)
                    events.append(ScenarioEvent(
                        day=day, actor_id=entity.entity_id,
                        event_type="shortage_warning",
                        description=(f"Planner projects {mat} stock-out in "
                                     f"{max(cov, 0.0):.0f} days"),
                        impact={"material_id": mat, "coverage_days": round(cov, 1)}))
                    if risk_averse and mat not in entity.state["expedited_materials"]:
                        entity.state["expedited_materials"].append(mat)
                        events.append(ScenarioEvent(
                            day=day, actor_id=entity.entity_id,
                            event_type="expedite_po",
                            description=(f"Planner expedites a PO for {mat} "
                                         f"with an alternate supplier"),
                            impact={"material_id": mat}))
            if ctx["late"] and not entity.state.get("halt_flagged"):
                entity.state["halt_flagged"] = True
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="late_delivery",
                    description=("Planner reports production slipping; "
                                 "customer orders going late"),
                    impact={"cause": "material_shortage"}))
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="reschedule_production",
                    description="Planner re-sequences schedule around shortages"))
        elif stype == "demand_spike":
            utilization = 0.78 * ctx["factor"]
            if day == 1 and utilization > 0.95:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="capacity_pressure",
                    description=(f"Planner projects utilization at "
                                 f"{utilization:.0%}; throughput pressure"),
                    impact={"utilization": round(utilization, 3)}))
            if day == 2 and entity.persona["flexibility"] > 0.5:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="overtime_authorized",
                    description="Planner authorizes weekend overtime shifts"))
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="order_increase",
                    description="Planner raises blanket-order volumes with suppliers"))
            if day == 3 and ctx["factor"] > 1.5:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="subcontract_evaluation",
                    description="Planner evaluates subcontracting assembly steps"))
        elif stype == "machine_failure":
            if day == 1:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id, event_type="reroute_jobs",
                    description=("Planner reroutes jobs to remaining machines "
                                 "in the work center")))
            if day == 2 and ctx["days"] > 3 and risk_averse:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="maintenance_priority_request",
                    description="Planner escalates repair priority with maintenance"))
            if ctx["late"] and not entity.state.get("halt_flagged"):
                entity.state["halt_flagged"] = True
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="late_delivery",
                    description="Capacity loss pushes orders past due dates",
                    impact={"cause": "machine_failure"}))
        elif stype == "material_price_spike":
            if day == 1:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id, event_type="cost_alert",
                    description="Planner flags material cost variance to finance"))
            if day == 2:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="alternate_supplier_quote",
                    description="Planner requests quotes from alternate suppliers"))
            if day == 3 and ctx["factor"] > 1.4:
                events.append(ScenarioEvent(
                    day=day, actor_id=entity.entity_id,
                    event_type="price_pass_through_review",
                    description="Planner reviews customer price pass-through"))
        return events

    # ------------------------------------------------------------------
    # KPI impact, findings, confidence
    # ------------------------------------------------------------------

    def _baseline_kpis(self, seed: int) -> KPISnapshot:
        scheduler = PolicyScheduler(SchedulingPolicy())
        schedule = scheduler.build_schedule(
            self.seed_data.work_orders, self.seed_data.machines,
            self.seed_data.products)
        sim = PlantSimulator(seed=seed).load(
            machines=self.seed_data.machines,
            products=self.seed_data.products,
            inventory=self.seed_data.inventory,
            work_orders=self.seed_data.work_orders)
        return sim.run(schedule, _SIM_HORIZON_HOURS, replications=1).kpis

    def _kpi_impact(self, scenario: SimulationScenario) -> Dict[str, float]:
        """Shocked-vs-baseline KPI deltas (simulated where plant-shaped)."""
        stype = scenario.shock.get("type")
        base = self._baseline_kpis(scenario.seed)

        if stype == "machine_failure":
            shocked = self._simulate_machine_failure(scenario, base)
        elif stype == "demand_spike":
            shocked = self._simulate_demand_spike(scenario, base)
        elif stype == "supplier_outage":
            return self._analytic_supplier_outage(scenario, base)
        else:
            return self._analytic_price_spike(scenario, base)

        return {
            "throughput_units": round(shocked.throughput_units - base.throughput_units, 3),
            "otd_rate": round(shocked.otd_rate - base.otd_rate, 4),
            "oee": round(shocked.oee - base.oee, 4),
            "total_cost": round(shocked.total_cost - base.total_cost, 2),
            "makespan_hours": round(shocked.makespan_hours - base.makespan_hours, 3),
        }

    def _simulate_machine_failure(self, scenario: SimulationScenario,
                                  base: KPISnapshot) -> KPISnapshot:
        mid = scenario.shock.get("machine_id", "M-MILL-02")
        remaining = [m for m in self.seed_data.machines if m.machine_id != mid]
        needed_ops = {op for p in self.seed_data.products for op in p.routing}
        covered_ops = {op for m in remaining for op in m.operations}
        if needed_ops <= covered_ops:
            machines = remaining
        else:
            # Sole capable machine: keep it but badly degraded instead.
            machines = [
                replace(m, mtbf_hours=6.0, mttr_hours=max(m.mttr_hours, 8.0),
                        units_per_hour=m.units_per_hour * 0.4)
                if m.machine_id == mid else m
                for m in self.seed_data.machines
            ]
        schedule = PolicyScheduler(SchedulingPolicy()).build_schedule(
            self.seed_data.work_orders, machines, self.seed_data.products)
        sim = PlantSimulator(seed=scenario.seed).load(
            machines=machines, products=self.seed_data.products,
            inventory=self.seed_data.inventory,
            work_orders=self.seed_data.work_orders)
        return sim.run(schedule, _SIM_HORIZON_HOURS, replications=1).kpis

    def _simulate_demand_spike(self, scenario: SimulationScenario,
                               base: KPISnapshot) -> KPISnapshot:
        pid = scenario.shock.get("product_id", "P-300")
        factor = float(scenario.shock.get("factor", 1.5))
        spiked = [
            replace(wo, quantity=wo.quantity * factor)
            if wo.product_id == pid else wo
            for wo in self.seed_data.work_orders
        ]
        schedule = PolicyScheduler(SchedulingPolicy()).build_schedule(
            spiked, self.seed_data.machines, self.seed_data.products)
        sim = PlantSimulator(seed=scenario.seed).load(
            machines=self.seed_data.machines, products=self.seed_data.products,
            inventory=self.seed_data.inventory, work_orders=spiked)
        return sim.run(schedule, _SIM_HORIZON_HOURS, replications=1).kpis

    def _analytic_supplier_outage(self, scenario: SimulationScenario,
                                  base: KPISnapshot) -> Dict[str, float]:
        sid = scenario.shock.get("supplier_id", "SUP-1")
        days = int(scenario.shock.get("days", 7))
        supplier = next((s for s in self.seed_data.suppliers
                         if s.supplier_id == sid), None)
        materials = set(supplier.materials) if supplier else set()
        products = self.seed_data.products_by_id
        affected = [
            wo for wo in self.seed_data.work_orders
            if products.get(wo.product_id)
            and any(line.material_id in materials
                    for line in products[wo.product_id].bom)
        ]
        fraction = len(affected) / max(len(self.seed_data.work_orders), 1)
        severity = min(1.0, days / max(scenario.horizon_days, 1))
        return {
            "otd_rate": -round(fraction * severity * 0.6, 4),
            "throughput_units": -round(
                base.throughput_units * fraction * severity * 0.4, 3),
            "total_cost": round(base.total_cost * fraction * severity * 0.12, 2),
        }

    def _analytic_price_spike(self, scenario: SimulationScenario,
                              base: KPISnapshot) -> Dict[str, float]:
        mat = scenario.shock.get("material_id", "RM-STEEL")
        factor = float(scenario.shock.get("factor", 1.3))
        unit_cost = next((i.unit_cost for i in self.seed_data.inventory
                          if i.material_id == mat), 1.0)
        products = self.seed_data.products_by_id
        exposed_spend = sum(
            line.quantity_per_unit * wo.quantity * unit_cost
            for wo in self.seed_data.work_orders
            for line in (products[wo.product_id].bom
                         if wo.product_id in products else [])
            if line.material_id == mat)
        return {
            "total_cost": round(exposed_spend * (factor - 1.0), 2),
            "otd_rate": 0.0,
            "throughput_units": 0.0,
        }

    _FINDING_RULES = [
        ("late_delivery",
         "On-time delivery is at risk: late deliveries propagate to customer orders.",
         "Expedite critical purchase orders and re-sequence the schedule with EDD dispatch."),
        ("shortage_warning",
         "Material stock-outs are projected before replenishment arrives.",
         "Qualify an alternate supplier and raise safety stock for affected materials."),
        ("churn_warning",
         "Customer attrition risk: repeated late days are eroding patience.",
         "Proactively communicate revised delivery dates to affected customers."),
        ("order_cancelled",
         "Order cancellations observed: revenue loss from churned customers.",
         "Offer expedited make-up shipments or concessions to retain churning accounts."),
        ("price_increase",
         "Margin erosion: suppliers are raising prices under disruption.",
         "Lock in framework-agreement pricing and dual-source exposed materials."),
        ("capacity_pressure",
         "Capacity overload: projected utilization exceeds sustainable levels.",
         "Authorize overtime and evaluate subcontracting the bottleneck operations."),
        ("breakdown_risk",
         "Unplanned downtime risk rises on fragile machines under elevated load.",
         "Pull preventive maintenance forward into the weekly buffer windows."),
        ("machine_down",
         "Single-machine loss removes work-center capacity for several days.",
         "Cross-train operators and pre-stage spares for the affected work center."),
        ("cost_alert",
         "Material cost variance threatens product margins.",
         "Review customer price pass-through and renegotiate volume pricing."),
    ]

    def _derive_findings(self, timeline: List[ScenarioEvent],
                         scenario: SimulationScenario,
                         ) -> Tuple[List[str], List[str]]:
        """Rule-based risks and recommendations from observed event patterns."""
        seen = {ev.event_type for ev in timeline}
        risks: List[str] = []
        recommendations: List[str] = []
        for event_type, risk, rec in self._FINDING_RULES:
            if event_type in seen:
                risks.append(risk)
                recommendations.append(rec)
        if not recommendations:
            recommendations.append(
                "No acute disruption pattern detected; monitor KPIs daily and "
                "keep the contingency plan current.")
        return risks, recommendations

    @staticmethod
    def _confidence(runs: List[List[ScenarioEvent]]) -> float:
        """Confidence from event-count variance across sub-seeded runs."""
        counters = [Counter(ev.event_type for ev in run) for run in runs]
        keys = sorted(set().union(*counters)) if counters else []
        cvs: List[float] = []
        for key in keys:
            values = np.array([c.get(key, 0) for c in counters], dtype=float)
            mean = values.mean()
            if mean > 0:
                cvs.append(float(values.std() / mean))
        dispersion = float(np.mean(cvs)) if cvs else 0.5
        return round(float(np.clip(0.95 - dispersion, 0.3, 0.95)), 3)
