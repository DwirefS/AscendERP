"""
Headline experiments for the Manufacturing Evidence Engine (WS-3).

1. ``run_solo_vs_council_disposition`` — the council A/B test the whitepaper
   promised: the QualityAgent's solo disposition policy vs the
   QualityCouncil's deliberated decision, both scored against a documented,
   agent-independent ground-truth rubric. Both subjects are deterministic
   (no LLM), so the measured numbers are reproducible. Whatever the numbers
   say is the result — the rubric is fixed here, in the open, and is not
   tuned to favor either subject.

2. ``run_dispatch_policy_eval`` — all five dispatch rules (EDD/SPT/CR/WSPT/
   FIFO) scheduled by the real PolicyScheduler and executed by the real
   PlantSimulator (168h horizon, 3 replications) on the deterministic factory
   seed, scored by the same weighted objective the AutoOptimizeLoop uses
   (0.5*otd_rate + 0.3*oee - 0.2*total_cost/cost_baseline).

Ground-truth rubric for NCR disposition (documented; severity x quantity x
rework economics):

    R1. supplier_related and severity in {major, critical}
            -> RETURN_TO_SUPPLIER   (defective purchased material goes back)
    R2. severity == critical -> SCRAP
            (safety/function cannot be assured by rework)
    R3. severity == major    -> REWORK if rework_cost_per_unit < unit_value
                                else SCRAP (rework uneconomical)
    R4. severity == minor    -> REWORK if quantity_affected > 0
                                else USE_AS_IS (control signal only)
"""
from __future__ import annotations

from typing import Any, Dict, List

import structlog

from src.core.evals.runner import EvalReport, EvalRunner, GoldenTask
from src.core.evals.scorecard import Scorecard
from flavors.manufacturing.agents.quality_agent import QualityAgent
from flavors.manufacturing.autoresearch.optimize_loop import (
    DEFAULT_OBJECTIVE_WEIGHTS,
)
from flavors.manufacturing.councils.quality_council import QualityCouncil
from flavors.manufacturing.data.seed import build_seed
from flavors.manufacturing.models import (
    NonConformanceReport,
    SchedulingPolicy,
)
from flavors.manufacturing.simulation.plant import (
    DISPATCH_RULES,
    PlantSimulator,
    PolicyScheduler,
)

logger = structlog.get_logger()

DISPATCH_HORIZON_HOURS = 168.0
DISPATCH_REPLICATIONS = 3


# ---------------------------------------------------------------------------
# Experiment 1: solo QualityAgent vs QualityCouncil on NCR disposition
# ---------------------------------------------------------------------------

def rubric_disposition(
    severity: str,
    supplier_related: bool,
    quantity_affected: float,
    rework_cost_per_unit: float,
    unit_value: float,
) -> str:
    """Documented ground-truth rubric (see module docstring)."""
    if supplier_related and severity in ("major", "critical"):
        return "return_to_supplier"
    if severity == "critical":
        return "scrap"
    if severity == "major":
        return "rework" if rework_cost_per_unit < unit_value else "scrap"
    return "rework" if quantity_affected > 0 else "use_as_is"


# (case_id, severity, supplier_related, quantity_affected,
#  rework_cost_per_unit, unit_value)
_DISPOSITION_CASES: List[tuple] = [
    ("d01_minor_control_signal_only", "minor", False, 0.0, 5.0, 100.0),
    ("d02_minor_few_defects", "minor", False, 5.0, 5.0, 100.0),
    ("d03_minor_many_defects", "minor", False, 12.0, 8.0, 100.0),
    ("d04_major_economical_rework", "major", False, 20.0, 10.0, 100.0),
    ("d05_major_cheap_rework", "major", False, 8.0, 15.0, 90.0),
    ("d06_major_uneconomical_rework", "major", False, 40.0, 120.0, 100.0),
    ("d07_critical_small_lot", "critical", False, 3.0, 20.0, 100.0),
    ("d08_critical_large_lot", "critical", False, 60.0, 30.0, 250.0),
    ("d09_supplier_major", "major", True, 10.0, 12.0, 100.0),
    ("d10_supplier_critical", "critical", True, 30.0, 25.0, 150.0),
    ("d11_supplier_minor_defects", "minor", True, 4.0, 6.0, 100.0),
    ("d12_major_cheap_vs_valuable", "major", False, 15.0, 50.0, 200.0),
]


def _score_disposition(actual: Any, expected: Dict[str, Any]) -> float:
    disposition = actual.get("disposition")
    value = disposition.value if disposition is not None else None
    return 1.0 if value == expected["disposition"] else 0.0


def build_disposition_tasks() -> List[GoldenTask]:
    """The 12 NCR disposition cases with rubric-derived ground truth."""
    tasks: List[GoldenTask] = []
    for case_id, severity, supplier, qty, rework_cost, unit_value in _DISPOSITION_CASES:
        tasks.append(
            GoldenTask(
                task_id=case_id,
                description=(
                    f"{severity} NCR, qty {qty}, rework {rework_cost}/u vs "
                    f"value {unit_value}/u, supplier={supplier}"
                ),
                input_data={
                    "severity": severity,
                    "supplier_related": supplier,
                    "quantity_affected": qty,
                    "rework_cost_per_unit": rework_cost,
                    "unit_value": unit_value,
                },
                expected={
                    "disposition": rubric_disposition(
                        severity, supplier, qty, rework_cost, unit_value
                    )
                },
                scorer=_score_disposition,
                tags=["disposition", severity],
                domain="manufacturing.quality",
            )
        )
    return tasks


async def run_solo_vs_council_disposition(seed: int = 42) -> Dict[str, Any]:
    """
    Score the QualityAgent's solo disposition policy against the
    QualityCouncil's deliberated decision on the same 12 rubric cases.

    Both subjects are deterministic, so ``seed`` only labels the run; the
    cases themselves are fixed. Returns ``{"solo": EvalReport, "council":
    EvalReport, "comparison": dict}`` — reported as measured, win or lose.
    """
    tasks = build_disposition_tasks()
    runner = EvalRunner()

    async def solo_subject(input_data: Dict[str, Any]) -> Dict[str, Any]:
        # The QualityAgent's own documented disposition policy: severity plus
        # material origin plus whether any units are actually out of spec.
        disposition = QualityAgent._recommend_disposition(
            severity=input_data["severity"],
            supplier_material=input_data["supplier_related"],
            out_of_spec=input_data["quantity_affected"] > 0,
        )
        return {"disposition": disposition}

    council = QualityCouncil()

    async def council_subject(input_data: Dict[str, Any]) -> Dict[str, Any]:
        ncr = NonConformanceReport.new(
            work_order_id="WO-EVAL",
            description="Disposition eval case",
            severity=input_data["severity"],
            quantity_affected=input_data["quantity_affected"],
        )
        decision = await council.decide(
            ncr, supplier_related=input_data["supplier_related"]
        )
        return {"disposition": decision["disposition"]}

    solo_report = await runner.run(tasks, solo_subject, name="quality_agent_solo")
    council_report = await runner.run(tasks, council_subject, name="quality_council")
    comparison = Scorecard.compare([solo_report, council_report])

    logger.info(
        "solo_vs_council_complete",
        seed=seed,
        solo_mean=round(solo_report.mean_score, 4),
        council_mean=round(council_report.mean_score, 4),
        best=comparison["best"],
    )
    return {"solo": solo_report, "council": council_report, "comparison": comparison}


# ---------------------------------------------------------------------------
# Experiment 2: dispatch-rule policy eval on the seeded plant
# ---------------------------------------------------------------------------


def _objective(kpis: Any, cost_baseline: float) -> float:
    """The AutoOptimizeLoop objective: 0.5*otd + 0.3*oee - 0.2*cost_norm."""
    score = 0.0
    for kpi, weight in DEFAULT_OBJECTIVE_WEIGHTS.items():
        value = float(getattr(kpis, kpi, 0.0))
        if kpi == "total_cost":
            value = value / cost_baseline
        score += weight * value
    return score


def _score_dispatch(actual: Any, expected: Dict[str, Any]) -> float:
    """
    Monotone affine map of the objective into [0, 1]:
    ``score = clamp((objective + 1) / 2, 0, 1)``. Ranking by score is
    therefore identical to ranking by the raw objective (kept in ``detail``).
    """
    return min(max((float(actual["objective"]) + 1.0) / 2.0, 0.0), 1.0)


async def run_dispatch_policy_eval(seed: int = 42) -> Dict[str, Any]:
    """
    Schedule + simulate every dispatch rule on the deterministic factory seed
    (168h horizon, 3 replications) and rank rules by the AutoOptimizeLoop
    objective. Same seed => identical report.

    Returns ``{"report": EvalReport, "ranking": [{rule, objective, kpis}]}``.
    """
    seed_data = build_seed(seed)
    cost_baseline = max(
        sum(
            wo.quantity * seed_data.products_by_id[wo.product_id].standard_cost
            for wo in seed_data.work_orders
        ),
        1.0,
    )

    async def dispatch_subject(input_data: Dict[str, Any]) -> Dict[str, Any]:
        rule = input_data["dispatch_rule"]
        scheduler = PolicyScheduler(SchedulingPolicy(dispatch_rule=rule))
        schedule = scheduler.build_schedule(
            seed_data.work_orders, seed_data.machines, seed_data.products
        )
        simulator = PlantSimulator(seed=seed).load(
            machines=seed_data.machines,
            products=seed_data.products,
            inventory=seed_data.inventory,
            work_orders=seed_data.work_orders,
        )
        result = simulator.run(
            schedule,
            horizon_hours=DISPATCH_HORIZON_HOURS,
            replications=DISPATCH_REPLICATIONS,
        )
        objective = _objective(result.kpis, cost_baseline)
        return {
            "objective": objective,
            "detail": {
                "rule": rule,
                "objective": round(objective, 6),
                "kpis": result.kpis.to_dict(),
            },
        }

    tasks = [
        GoldenTask(
            task_id=f"dispatch_{rule.lower()}",
            description=(
                f"{rule} dispatch rule scheduled and simulated over "
                f"{DISPATCH_HORIZON_HOURS:.0f}h x {DISPATCH_REPLICATIONS} reps"
            ),
            input_data={"dispatch_rule": rule},
            expected={},
            scorer=_score_dispatch,
            tags=["dispatch", rule],
            domain="manufacturing.scheduling",
        )
        for rule in DISPATCH_RULES
    ]

    report = await EvalRunner().run(tasks, dispatch_subject, name="dispatch_policy_eval")

    ranking = [
        {
            "rule": r.detail.get("rule"),
            "objective": r.detail.get("objective"),
            "kpis": r.detail.get("kpis", {}),
        }
        for r in sorted(
            report.results, key=lambda x: (-x.score, x.task_id)
        )
    ]
    logger.info(
        "dispatch_policy_eval_complete",
        seed=seed,
        best_rule=ranking[0]["rule"] if ranking else None,
        ranking=[r["rule"] for r in ranking],
    )
    return {"report": report, "ranking": ranking}


def rank_reports(experiment: Dict[str, Any]) -> List[str]:
    """Convenience: dispatch rule names in ranked (best-first) order."""
    return [entry["rule"] for entry in experiment["ranking"]]
