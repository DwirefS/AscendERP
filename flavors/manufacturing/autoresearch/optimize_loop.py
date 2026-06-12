"""
AutoOptimize loop (Karpathy autoresearch-inspired) over scheduling policies.

Propose -> simulate -> measure -> keep-if-better -> journal/rollback, per
design §3.3. The loop mutates one :class:`SchedulingPolicy` field per step,
builds a schedule via an injected scheduler factory, evaluates it on an
injected simulator factory, and accepts the mutation only when the weighted
objective improves. Every step (accepted or rolled back) is journaled as an
:class:`OptimizationStep`, in memory and optionally as JSONL.

The simulator/scheduler are injected to honor the §3.2-3.3 contract:

    scheduler_factory(policy) -> scheduler
        scheduler.build_schedule(work_orders, machines) -> ProductionSchedule
    simulator_factory() -> simulator   # pre-loaded with plant state
        simulator.run(schedule, horizon_hours, replications) -> SimulationResult

so the loop works identically with the real ``PlantSimulator`` /
``PolicyScheduler`` (flavors/manufacturing/simulation/plant.py) or any stub.

Objective (documented normalization):
    objective = w_otd * otd_rate            # already 0..1
              + w_oee * oee                 # already 0..1
              + w_cost * (total_cost / cost_baseline)
where ``cost_baseline = sum(wo.quantity * standard_cost(product))`` (>= 1.0)
puts cost on a comparable ~0..N scale; ``w_cost`` is *negative* so lower cost
raises the objective. Determinism: a seeded ``random.Random`` drives field
choice and jitter, so two loops with the same seed and a deterministic
simulator produce identical histories.
"""
from __future__ import annotations

import dataclasses
import json
import random
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import structlog

from flavors.manufacturing.models import (
    KPISnapshot,
    Machine,
    OptimizationStep,
    Product,
    SchedulingPolicy,
    SimulationResult,
    WorkOrder,
)

logger = structlog.get_logger()

DISPATCH_RULES: List[str] = ["EDD", "SPT", "CR", "WSPT", "FIFO"]

# Mutable fields and their documented bounds (floats jitter +/-20%, clamped).
FLOAT_BOUNDS: Dict[str, tuple[float, float]] = {
    "batch_size_factor": (0.25, 2.0),
    "maintenance_buffer_hours": (0.0, 24.0),
    "expedite_threshold": (0.1, 1.5),
    "queue_weight_due": (0.0, 5.0),
    "queue_weight_setup": (0.0, 5.0),
}
MUTABLE_FIELDS: List[str] = ["dispatch_rule"] + sorted(FLOAT_BOUNDS)

DEFAULT_OBJECTIVE_WEIGHTS: Dict[str, float] = {
    "otd_rate": 0.5,
    "oee": 0.3,
    "total_cost": -0.2,
}

DEFAULT_HORIZON_HOURS = 168.0
DEFAULT_REPLICATIONS = 3


class AutoOptimizeLoop:
    """Self-improving scheduling-policy search with journaled rollback."""

    def __init__(
        self,
        simulator_factory: Callable[[], Any],
        scheduler_factory: Callable[[SchedulingPolicy], Any],
        work_orders: Sequence[WorkOrder],
        machines: Sequence[Machine],
        products: Sequence[Product],
        objective_weights: Optional[Dict[str, float]] = None,
        seed: int = 42,
        journal_path: Optional[str | Path] = None,
        initial_policy: Optional[SchedulingPolicy] = None,
        horizon_hours: float = DEFAULT_HORIZON_HOURS,
        replications: int = DEFAULT_REPLICATIONS,
    ) -> None:
        self.simulator_factory = simulator_factory
        self.scheduler_factory = scheduler_factory
        self.work_orders = list(work_orders)
        self.machines = list(machines)
        self.products = list(products)
        self.objective_weights = dict(objective_weights or DEFAULT_OBJECTIVE_WEIGHTS)
        self.seed = seed
        self.journal_path = Path(journal_path) if journal_path else None
        self.horizon_hours = horizon_hours
        self.replications = replications

        self._rng = random.Random(seed)
        self.policy = initial_policy or SchedulingPolicy()
        self.best_objective: Optional[float] = None
        self.best_kpis: Optional[KPISnapshot] = None
        self.history: List[OptimizationStep] = []
        self._step_count = 0
        self._cost_baseline = self._compute_cost_baseline()

    # -- objective ------------------------------------------------------------

    def _compute_cost_baseline(self) -> float:
        """Σ(work order qty x product standard cost), floored at 1.0."""
        costs = {p.product_id: p.standard_cost for p in self.products}
        total = sum(wo.quantity * costs.get(wo.product_id, 1.0) for wo in self.work_orders)
        return max(total, 1.0)

    def objective(self, kpis: KPISnapshot) -> float:
        """Weighted, normalized objective (higher is better)."""
        score = 0.0
        for kpi, weight in self.objective_weights.items():
            value = float(getattr(kpis, kpi, 0.0))
            if kpi == "total_cost":
                value = value / self._cost_baseline
            score += weight * value
        return score

    # -- evaluation -------------------------------------------------------------

    def _evaluate(self, policy: SchedulingPolicy) -> tuple[float, SimulationResult]:
        scheduler = self.scheduler_factory(policy)
        schedule = scheduler.build_schedule(self.work_orders, self.machines, self.products)
        simulator = self.simulator_factory()
        result = simulator.run(
            schedule, horizon_hours=self.horizon_hours, replications=self.replications
        )
        return self.objective(result.kpis), result

    def _ensure_baseline(self) -> None:
        if self.best_objective is None:
            objective, result = self._evaluate(self.policy)
            self.best_objective = objective
            self.best_kpis = result.kpis
            logger.info(
                "autoresearch_baseline",
                objective=round(self.best_objective, 6),
                policy=self.policy.to_dict(),
            )

    # -- mutation ---------------------------------------------------------------

    def _mutate(self, policy: SchedulingPolicy) -> tuple[str, Any, Any, SchedulingPolicy]:
        """Pick one field (seeded rng) and mutate it within documented bounds."""
        fname = self._rng.choice(MUTABLE_FIELDS)
        old_value = getattr(policy, fname)
        if fname == "dispatch_rule":
            # Cycle deterministically through the 5 rules.
            idx = DISPATCH_RULES.index(old_value) if old_value in DISPATCH_RULES else -1
            new_value: Any = DISPATCH_RULES[(idx + 1) % len(DISPATCH_RULES)]
        else:
            lo, hi = FLOAT_BOUNDS[fname]
            jitter = 1.0 + self._rng.uniform(-0.2, 0.2)
            new_value = round(min(max(old_value * jitter, lo), hi), 6)
            if new_value == old_value:  # clamped to same value — nudge inside bounds
                new_value = round(min(max(old_value + (hi - lo) * 0.05, lo), hi), 6)
        candidate = dataclasses.replace(policy, **{fname: new_value})
        return fname, old_value, new_value, candidate

    # -- journal -----------------------------------------------------------------

    def _journal(self, step: OptimizationStep) -> None:
        self.history.append(step)
        if self.journal_path is not None:
            self.journal_path.parent.mkdir(parents=True, exist_ok=True)
            with self.journal_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(step.to_dict(), default=str) + "\n")

    # -- main loop -----------------------------------------------------------------

    def step(self) -> OptimizationStep:
        """One propose → simulate → keep-if-better → journal iteration."""
        self._ensure_baseline()
        assert self.best_objective is not None  # for type checkers

        self._step_count += 1
        fname, old_value, new_value, candidate = self._mutate(self.policy)
        objective_before = self.best_objective
        objective_after, result = self._evaluate(candidate)

        accepted = objective_after > objective_before
        if accepted:
            self.policy = candidate
            self.best_objective = objective_after
            self.best_kpis = result.kpis
        # else: rollback is implicit — self.policy is untouched.

        record = OptimizationStep(
            step=self._step_count,
            mutated_field=fname,
            old_value=old_value,
            new_value=new_value,
            objective_before=objective_before,
            objective_after=objective_after,
            accepted=accepted,
            kpis_after=result.kpis.to_dict(),
        )
        self._journal(record)
        logger.info(
            "autoresearch_step",
            step=self._step_count,
            field=fname,
            old=old_value,
            new=new_value,
            accepted=accepted,
            objective_before=round(objective_before, 6),
            objective_after=round(objective_after, 6),
        )
        return record

    def run(self, n_steps: int) -> Dict[str, Any]:
        """Run ``n_steps`` iterations and return a summary."""
        for _ in range(max(n_steps, 0)):
            self.step()
        accepted = sum(1 for s in self.history if s.accepted)
        summary = {
            "best_policy": self.policy.to_dict(),
            "best_objective": self.best_objective,
            "best_kpis": self.best_kpis.to_dict() if self.best_kpis else None,
            "acceptance_rate": (accepted / len(self.history)) if self.history else 0.0,
            "steps": len(self.history),
            "seed": self.seed,
        }
        logger.info("autoresearch_run_complete", **{
            k: v for k, v in summary.items() if k != "best_kpis"
        })
        return summary
