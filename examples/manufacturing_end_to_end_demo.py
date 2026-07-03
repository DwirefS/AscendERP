"""
End-to-end demo of the Manufacturing flavor — no server, no cloud, no LLM.

Runs the whole story in one process:
  1. Seed a demo factory (8 machines / 4 products / 4 suppliers / 12 orders)
  2. Production planning: MRP + policy-scheduled plan (ProductionPlannerAgent)
  3. Simulate the plan on the plant digital twin → baseline KPIs
  4. Quality: SPC analysis flags an out-of-control characteristic → NCR
  5. Maintenance: risk scoring proposes predictive maintenance
  6. Procurement through the GOVERNED HARNESS: a big PO trips the $50k policy
     and parks for human approval; the receipt chain records everything
  7. Swarm what-if: 14-day supplier outage → emergent timeline + council evidence
  8. AutoOptimize: mutate the scheduling policy, keep only measured improvements
  9. Verify the audit receipt chain

Run:  ENCRYPTION_MASTER_KEY=dev-only-key python examples/manufacturing_end_to_end_demo.py
"""
import asyncio
import uuid

from src.core.agent.base import AgentContext
from src.core.harness import AgentHarness, Budget, ReceiptChain, ApprovalQueue
from src.core.skills import SkillRegistry

from flavors.manufacturing.data.seed import build_seed
from flavors.manufacturing.models import (
    QualityInspection,
    SchedulingPolicy,
    SimulationScenario,
)
from flavors.manufacturing.simulation.plant import PlantSimulator, PolicyScheduler
from flavors.manufacturing.simulation.swarm import SwarmWorld
from flavors.manufacturing.autoresearch.optimize_loop import AutoOptimizeLoop
from flavors.manufacturing.policies import build_manufacturing_policies
from flavors.manufacturing.agents import (
    MaintenanceAgent,
    ProcurementAgent,
    ProductionPlannerAgent,
    QualityAgent,
)

W = 74


def banner(step: str, title: str):
    print(f"\n{'=' * W}\n  {step}  {title}\n{'=' * W}")


def ctx() -> AgentContext:
    return AgentContext(trace_id=str(uuid.uuid4()), tenant_id="demo-plant")


async def main():
    print("ANTS Manufacturing — end-to-end demo (local, deterministic, no LLM)")

    # 1 ── Seed the factory ---------------------------------------------------
    banner("1/9", "Seed the demo factory")
    seed = build_seed(42)
    print(f"  machines={len(seed.machines)}  products={len(seed.products)}"
          f"  materials={len(seed.inventory)}  suppliers={len(seed.suppliers)}"
          f"  open work orders={len(seed.work_orders)}")

    # 2 ── Production planning ------------------------------------------------
    banner("2/9", "Production planning (MRP + policy scheduling)")
    planner = ProductionPlannerAgent()
    result = await planner.run({
        "type": "plan",
        "work_orders": seed.work_orders,
        "products": seed.products,
        "inventory": seed.inventory,
        "machines": seed.machines,
    }, ctx())
    out = result.output or {}
    print(f"  success={result.success}  shortages={len(out.get('shortages', []))}"
          f"  scheduled_entries={out.get('scheduled_entries', 'n/a')}")

    # 3 ── Simulate the plan --------------------------------------------------
    banner("3/9", "Simulate the plan on the plant digital twin")
    schedule = PolicyScheduler(SchedulingPolicy()).build_schedule(
        seed.work_orders, seed.machines, seed.products)
    sim = PlantSimulator(seed=42)
    sim.load(machines=seed.machines, products=seed.products,
             inventory=seed.inventory, work_orders=seed.work_orders)
    baseline = sim.run(schedule, horizon_hours=168.0, replications=3)
    k = baseline.kpis
    print(f"  OTD {k.otd_rate:.1%} · OEE {k.oee:.1%} · throughput {k.throughput_units:.0f}u"
          f" · scrap {k.scrap_rate:.1%} · cost ${k.total_cost:,.0f}")

    # 4 ── Quality / SPC ------------------------------------------------------
    banner("4/9", "Quality: SPC catches a drifting characteristic")
    drifting = [10.01, 10.02, 10.05, 10.08, 10.11, 10.15, 10.18, 10.22, 10.26, 10.31]
    inspection = QualityInspection(
        inspection_id="INSP-1", work_order_id=seed.work_orders[0].work_order_id,
        characteristic="diameter_mm", measurements=drifting,
        nominal=10.0, usl=10.2, lsl=9.8)
    qres = await QualityAgent().run({"type": "spc_review",
                                     "inspection": inspection}, ctx())
    qout = qres.output or {}
    ncr = qout.get("ncr")
    stats = qout.get("stats", {})
    print(f"  in_control={qout.get('in_control')} · rules fired={len(qout.get('rules_fired', []))}"
          f" · Cpk={stats.get('cpk')}")
    if ncr is not None:
        print(f"  NCR {ncr.ncr_id} opened · severity={ncr.severity}"
              f" · disposition={qout.get('recommended_disposition')}")

    # 5 ── Predictive maintenance ---------------------------------------------
    banner("5/9", "Maintenance: risk scoring proposes predictive PM")
    # Age one machine past its PM interval so the risk trigger demonstrably fires
    seed.machines[1].runtime_hours_since_pm = seed.machines[1].mtbf_hours * 1.1
    seed.machines[1].vibration_trend = 0.7
    mres = await MaintenanceAgent().run({"type": "risk_assessment",
                                         "machines": seed.machines}, ctx())
    mout = mres.output or {}
    pms = mout.get("maintenance_orders") or mout.get("pm_orders") or []
    print(f"  machines assessed={len(seed.machines)} · PM orders proposed={len(pms)}")

    # 6 ── Governed procurement (harness + policy + receipts) ------------------
    banner("6/9", "Procurement through the governed harness ($50k policy)")
    chain, queue = ReceiptChain(), ApprovalQueue()
    skills = SkillRegistry()
    skills.load_dir("flavors/manufacturing/skills")
    harness = AgentHarness(
        ProcurementAgent(),
        policies=build_manufacturing_policies(),
        skill_registry=skills,
        receipt_chain=chain,
        approval_queue=queue,
        budget=Budget(max_seconds=30, max_actions=20),
    )
    outcome = await harness.run(
        {"type": "invoke", "total_cost": 85_000,
         "material_id": "MAT-STEEL", "quantity": 5000},
        ctx())
    pending = queue.pending()
    print(f"  $85k PO → approval_required={outcome.approval_required}"
          f" · pending approvals={len(pending)}")
    if pending:
        queue.approve(pending[0].id if hasattr(pending[0], 'id') else pending[0]["id"])
        print("  human approved via Mission Control → PO can proceed")

    # 7 ── Swarm what-if -------------------------------------------------------
    banner("7/9", "Swarm scenario: 14-day outage at the primary supplier")
    world = SwarmWorld.from_seed(seed)
    report = world.run_scenario(SimulationScenario(
        name="supplier-outage", narrative="primary supplier down two weeks",
        shock={"type": "supplier_outage", "supplier_id": seed.suppliers[0].supplier_id,
               "days": 14}))
    print(f"  emergent events={len(report.timeline)} · confidence {report.confidence:.0%}")
    print(f"  KPI impact: {report.kpi_impact}")
    for r in report.recommendations[:3]:
        print(f"   → {r}")

    # 8 ── AutoOptimize --------------------------------------------------------
    banner("8/9", "AutoOptimize: the factory tunes its own scheduling policy")
    loop = AutoOptimizeLoop(
        simulator_factory=lambda: _loaded_sim(seed),
        scheduler_factory=PolicyScheduler,
        work_orders=seed.work_orders, machines=seed.machines,
        products=seed.products, seed=7)
    summary = loop.run(8)
    accepted = sum(1 for s in loop.history if s.accepted)
    print(f"  steps=8 accepted={accepted} · best objective {summary['best_objective']:.4f}"
          f" · best rule {summary['best_policy']['dispatch_rule']}")
    print("  every step journaled — accepted or rolled back, nothing silent")

    # 9 ── Audit ---------------------------------------------------------------
    banner("9/9", "Audit: verify the hash-chained receipt trail")
    print(f"  receipts={len(chain.receipts)} · chain verified={chain.verify()}")

    print(f"\n{'=' * W}\n  Demo complete. Start the server (`make serve`) and open"
          f"\n  http://localhost:8000/manufacturing/ui for Mission Control.\n{'=' * W}")


def _loaded_sim(seed):
    sim = PlantSimulator(seed=7)
    sim.load(machines=seed.machines, products=seed.products,
             inventory=seed.inventory, work_orders=seed.work_orders)
    return sim


if __name__ == "__main__":
    asyncio.run(main())
