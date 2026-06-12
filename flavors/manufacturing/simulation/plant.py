"""
Plant scheduling and simulation for the Manufacturing flavor.

Two pieces, both deterministic given a seed:

* :class:`PolicyScheduler` — turns open work orders into a
  :class:`~flavors.manufacturing.models.ProductionSchedule` using a
  parameterized :class:`~flavors.manufacturing.models.SchedulingPolicy`
  (EDD / SPT / CR / WSPT / FIFO dispatch + composite queue weighting,
  lot splitting via ``batch_size_factor``, weekly maintenance buffers).
* :class:`PlantSimulator` — a light discrete-event-style executor of a
  schedule with seeded stochastic breakdowns (exponential repair around
  MTBF/MTTR), vibration-driven scrap drift, and setup variability, producing
  :class:`~flavors.manufacturing.models.SimEvent` streams and a
  :class:`~flavors.manufacturing.models.KPISnapshot`.

Same seed + same inputs => identical results (tests rely on this).
"""
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import structlog

from flavors.manufacturing.data.seed import SEED_ANCHOR, build_seed
from flavors.manufacturing.models import (
    InventoryItem,
    KPISnapshot,
    Machine,
    Product,
    ProductionSchedule,
    ScheduleEntry,
    SchedulingPolicy,
    SimEvent,
    SimulationResult,
    WorkOrder,
    WorkOrderStatus,
)

logger = structlog.get_logger()

HOURS_PER_WEEK = 168.0

_SCHEDULABLE_STATUSES = (
    WorkOrderStatus.PLANNED,
    WorkOrderStatus.RELEASED,
    WorkOrderStatus.IN_PROGRESS,
)

DISPATCH_RULES = ("EDD", "SPT", "CR", "WSPT", "FIFO")


def _hours(delta_from: datetime, to: datetime) -> float:
    """Hours between two datetimes as a float."""
    return (to - delta_from).total_seconds() / 3600.0


@dataclass
class _JobStats:
    """Per-work-order processing estimates used by the dispatch rules."""
    proc_hours: float
    due_hours: float
    critical_ratio: float


class PolicyScheduler:
    """
    Builds production schedules from a parameterized dispatch policy.

    Work orders are ordered by the policy's dispatch rule blended with a
    composite queue score (due-date urgency and setup/product affinity,
    weighted by ``queue_weight_due`` / ``queue_weight_setup``); orders whose
    critical ratio falls below ``expedite_threshold`` jump the queue. Each
    order is split into lots per ``batch_size_factor``, routed through its
    product routing across capable machines (earliest-completion machine
    choice), with strictly sequential machine capacity and a weekly
    ``maintenance_buffer_hours`` window blocked on every machine.
    """

    #: Relative influence of the composite queue score vs. the primary rule.
    COMPOSITE_BLEND = 0.15

    def __init__(self, policy: Optional[SchedulingPolicy] = None):
        self.policy = policy or SchedulingPolicy()
        if self.policy.dispatch_rule not in DISPATCH_RULES:
            raise ValueError(
                f"Unknown dispatch_rule {self.policy.dispatch_rule!r}; "
                f"expected one of {DISPATCH_RULES}"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_schedule(
        self,
        work_orders: List[WorkOrder],
        machines: List[Machine],
        products: List[Product],
        start_time: Optional[datetime] = None,
    ) -> ProductionSchedule:
        """
        Schedule all open work orders onto the machine park.

        Args:
            work_orders: Orders to schedule (only PLANNED/RELEASED/IN_PROGRESS
                statuses are considered).
            machines: Available machines (capability via ``operations``).
            products: Product master data (routings + BOMs).
            start_time: Schedule time origin; defaults to the seed anchor.

        Returns:
            A :class:`ProductionSchedule` with no overlapping entries per
            machine and routing precedence respected within each lot.
        """
        start_time = start_time or SEED_ANCHOR
        products_by_id = {p.product_id: p for p in products}
        open_wos = [wo for wo in work_orders if wo.status in _SCHEDULABLE_STATUSES]
        ordered = self._order_queue(open_wos, products_by_id, machines, start_time)

        machine_free: Dict[str, float] = {m.machine_id: 0.0 for m in machines}
        entries: List[ScheduleEntry] = []

        for wo in ordered:
            product = products_by_id.get(wo.product_id)
            if product is None:
                logger.warning("unknown_product_skipped",
                               work_order_id=wo.work_order_id,
                               product_id=wo.product_id)
                continue
            for lot_qty in self._split_lots(wo.quantity):
                lot_ready = 0.0
                for operation in product.routing:
                    machine, op_start, op_end = self._place_operation(
                        operation, lot_qty, lot_ready, machines, machine_free)
                    machine_free[machine.machine_id] = op_end
                    lot_ready = op_end
                    entries.append(ScheduleEntry(
                        work_order_id=wo.work_order_id,
                        machine_id=machine.machine_id,
                        operation=operation,
                        start=start_time + timedelta(hours=op_start),
                        end=start_time + timedelta(hours=op_end),
                        quantity=lot_qty,
                    ))

        schedule = ProductionSchedule(
            entries=entries,
            policy_name=self.policy.dispatch_rule,
        )
        logger.info(
            "schedule_built",
            dispatch_rule=self.policy.dispatch_rule,
            work_orders=len(ordered),
            entries=len(entries),
            makespan_hours=round(max(machine_free.values(), default=0.0), 2),
        )
        return schedule

    # ------------------------------------------------------------------
    # Queue ordering (dispatch rules + composite weighting)
    # ------------------------------------------------------------------

    def _job_stats(
        self,
        wo: WorkOrder,
        product: Product,
        machines: List[Machine],
        start_time: datetime,
    ) -> _JobStats:
        """Estimate total processing hours and the critical ratio of a job."""
        proc = 0.0
        for operation in product.routing:
            capable = [m for m in machines if operation in m.operations]
            if not capable:
                raise ValueError(f"No machine capable of operation {operation!r}")
            best_rate = max(m.units_per_hour for m in capable)
            min_setup = min(m.setup_minutes for m in capable)
            proc += wo.quantity / best_rate + min_setup / 60.0
        due_h = _hours(start_time, wo.due_date)
        cr = due_h / max(proc, 1e-9)
        return _JobStats(proc_hours=proc, due_hours=due_h, critical_ratio=cr)

    def _order_queue(
        self,
        work_orders: List[WorkOrder],
        products_by_id: Dict[str, Product],
        machines: List[Machine],
        start_time: datetime,
    ) -> List[WorkOrder]:
        """Order the queue per dispatch rule + composite weighting + expedite."""
        if not work_orders:
            return []
        stats: Dict[str, _JobStats] = {}
        for wo in work_orders:
            product = products_by_id.get(wo.product_id)
            if product is None:
                continue
            stats[wo.work_order_id] = self._job_stats(wo, product, machines, start_time)
        candidates = [wo for wo in work_orders if wo.work_order_id in stats]

        rule = self.policy.dispatch_rule
        base_key: Dict[str, float] = {}
        for idx, wo in enumerate(candidates):
            s = stats[wo.work_order_id]
            if rule == "FIFO":
                key = float(idx)
            elif rule == "EDD":
                key = s.due_hours
            elif rule == "SPT":
                key = s.proc_hours
            elif rule == "CR":
                key = s.critical_ratio
            else:  # WSPT: descending priority-weight / processing time
                key = s.proc_hours / float(wo.priority.value)
            base_key[wo.work_order_id] = key

        def _normalize(values: Dict[str, float]) -> Dict[str, float]:
            lo, hi = min(values.values()), max(values.values())
            span = max(hi - lo, 1e-9)
            return {k: (v - lo) / span for k, v in values.items()}

        base_norm = _normalize(base_key)
        due_norm = _normalize({w.work_order_id: stats[w.work_order_id].due_hours
                               for w in candidates})
        product_order = sorted({w.product_id for w in candidates})
        prod_norm = {
            w.work_order_id: product_order.index(w.product_id) / max(len(product_order) - 1, 1)
            for w in candidates
        }

        scores: Dict[str, float] = {}
        for wo in candidates:
            wid = wo.work_order_id
            composite = (self.policy.queue_weight_due * due_norm[wid]
                         + self.policy.queue_weight_setup * prod_norm[wid])
            score = base_norm[wid] + self.COMPOSITE_BLEND * composite
            cr = stats[wid].critical_ratio
            if cr < self.policy.expedite_threshold:
                # Expedited jobs jump the queue, ordered among themselves by CR.
                score = -1000.0 + cr
            scores[wid] = score

        return sorted(
            candidates,
            key=lambda w: (scores[w.work_order_id],
                           w.due_date,
                           w.work_order_id),
        )

    # ------------------------------------------------------------------
    # Lot splitting & capacity placement
    # ------------------------------------------------------------------

    def _split_lots(self, quantity: float) -> List[float]:
        """Split a quantity into lots according to ``batch_size_factor``."""
        factor = float(np.clip(self.policy.batch_size_factor, 0.25, 2.0))
        n_lots = 1 if factor >= 1.0 else int(math.ceil(round(1.0 / factor, 6)))
        return [quantity / n_lots] * n_lots

    def _place_operation(
        self,
        operation: str,
        lot_qty: float,
        ready: float,
        machines: List[Machine],
        machine_free: Dict[str, float],
    ) -> Tuple[Machine, float, float]:
        """Pick the capable machine yielding the earliest operation finish."""
        capable = sorted(
            (m for m in machines if operation in m.operations),
            key=lambda m: m.machine_id,
        )
        if not capable:
            raise ValueError(f"No machine capable of operation {operation!r}")
        best: Optional[Tuple[Machine, float, float]] = None
        for machine in capable:
            duration = machine.setup_minutes / 60.0 + lot_qty / machine.units_per_hour
            op_start = self._next_free(
                max(ready, machine_free[machine.machine_id]), duration)
            op_end = op_start + duration
            if best is None or op_end < best[2]:
                best = (machine, op_start, op_end)
        return best

    def _next_free(self, t: float, duration: float) -> float:
        """
        Push a start time past any weekly maintenance-buffer window.

        Each machine reserves the last ``maintenance_buffer_hours`` of every
        168h week as blocked time.
        """
        buffer_h = max(0.0, float(self.policy.maintenance_buffer_hours))
        gap = HOURS_PER_WEEK - buffer_h
        if buffer_h <= 0.0:
            return t
        if duration >= gap:
            logger.warning("job_exceeds_weekly_window",
                           duration_hours=duration, free_gap_hours=gap)
            return t
        while True:
            moved = False
            for week in {int(t // HOURS_PER_WEEK),
                         int((t + duration) // HOURS_PER_WEEK)}:
                window_start = week * HOURS_PER_WEEK + gap
                window_end = (week + 1) * HOURS_PER_WEEK
                if t < window_end and (t + duration) > window_start:
                    t = window_end
                    moved = True
                    break
            if not moved:
                return t


class PlantSimulator:
    """
    Light discrete-event-style execution of a production schedule.

    Replays schedule entries in time order while tracking machine availability
    and routing precedence, injecting seeded stochastic effects:

    * breakdowns — Poisson count per operation at rate ``duration / mtbf``
      (vibration-amplified), each adding an exponential ``mttr`` repair;
    * scrap — baseline rate plus vibration-driven drift plus noise;
    * setup/processing variability around the planned durations.

    Replications use sub-seeds derived deterministically from the base seed
    and their KPIs are averaged. Same seed + inputs => identical results.
    """

    MACHINE_HOUR_COST = 75.0
    LATE_PENALTY_PER_HOUR = 25.0
    UNFINISHED_PENALTY = 250.0

    _KPI_FIELDS = ("throughput_units", "otd_rate", "oee", "wip_units",
                   "scrap_rate", "total_cost", "makespan_hours")

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.machines: List[Machine] = []
        self.products: List[Product] = []
        self.inventory: List[InventoryItem] = []
        self.work_orders: List[WorkOrder] = []
        self._loaded = False

    def load(
        self,
        machines: Optional[List[Machine]] = None,
        products: Optional[List[Product]] = None,
        inventory: Optional[List[InventoryItem]] = None,
        work_orders: Optional[List[WorkOrder]] = None,
    ) -> "PlantSimulator":
        """Load plant state; anything omitted comes from ``data/seed.py``."""
        if None in (machines, products, inventory, work_orders):
            seed_data = build_seed(self.seed)
            machines = machines if machines is not None else seed_data.machines
            products = products if products is not None else seed_data.products
            inventory = inventory if inventory is not None else seed_data.inventory
            work_orders = (work_orders if work_orders is not None
                           else seed_data.work_orders)
        self.machines = machines
        self.products = products
        self.inventory = inventory
        self.work_orders = work_orders
        self._loaded = True
        return self

    def run(
        self,
        schedule: ProductionSchedule,
        horizon_hours: float,
        replications: int = 1,
    ) -> SimulationResult:
        """
        Execute a schedule over a horizon.

        Args:
            schedule: The schedule to execute.
            horizon_hours: Simulation horizon (hours from schedule start).
            replications: Number of seeded replications; KPIs are averaged,
                events come from the first replication.

        Returns:
            A :class:`SimulationResult` with averaged KPIs and SimEvents.
        """
        if not self._loaded:
            self.load()
        replications = max(1, int(replications))
        t0 = min((e.start for e in schedule.entries), default=SEED_ANCHOR)

        rep_kpis: List[Dict[str, float]] = []
        events: List[SimEvent] = []
        for rep in range(replications):
            kpis_r, events_r = self._run_once(schedule, horizon_hours, t0, rep)
            rep_kpis.append(kpis_r)
            if rep == 0:
                events = events_r

        averaged = {
            key: float(np.mean([k[key] for k in rep_kpis]))
            for key in self._KPI_FIELDS
        }
        kpis = KPISnapshot(captured_at=t0, **averaged)
        logger.info(
            "simulation_complete",
            seed=self.seed,
            horizon_hours=horizon_hours,
            replications=replications,
            throughput=round(kpis.throughput_units, 1),
            otd_rate=round(kpis.otd_rate, 3),
            oee=round(kpis.oee, 3),
        )
        return SimulationResult(
            kpis=kpis,
            events=events,
            replications=replications,
            seed=self.seed,
            horizon_hours=horizon_hours,
        )

    # ------------------------------------------------------------------
    # Single replication
    # ------------------------------------------------------------------

    def _run_once(
        self,
        schedule: ProductionSchedule,
        horizon_hours: float,
        t0: datetime,
        replication: int,
    ) -> Tuple[Dict[str, float], List[SimEvent]]:
        """Execute one seeded replication; returns (kpi dict, events)."""
        rng = np.random.default_rng([max(0, self.seed), 1000 + replication])
        machines_by_id = {m.machine_id: m for m in self.machines}
        products_by_id = {p.product_id: p for p in self.products}
        material_cost = {i.material_id: i.unit_cost for i in self.inventory}
        wos_by_id = {w.work_order_id: w for w in self.work_orders}

        planned = sorted(
            schedule.entries,
            key=lambda e: (e.start, e.machine_id, e.work_order_id, e.operation),
        )
        expected_entries: Dict[str, int] = {}
        for entry in planned:
            expected_entries[entry.work_order_id] = (
                expected_entries.get(entry.work_order_id, 0) + 1)

        machine_ready: Dict[str, float] = {m: 0.0 for m in machines_by_id}
        machine_busy: Dict[str, float] = {m: 0.0 for m in machines_by_id}
        downtime_total = 0.0
        planned_dur_sum = 0.0
        actual_dur_sum = 0.0
        # per wo: {step_index: latest actual end}
        wo_step_end: Dict[str, Dict[int, float]] = {}
        wo_first_start: Dict[str, float] = {}
        wo_finish: Dict[str, float] = {}
        wo_executed: Dict[str, int] = {}
        wo_scrap: Dict[str, float] = {}
        total_scrap = 0.0
        total_started_qty = 0.0
        events: List[SimEvent] = []

        for entry in planned:
            machine = machines_by_id.get(entry.machine_id)
            if machine is None:
                continue
            wid = entry.work_order_id
            product = products_by_id.get(wos_by_id[wid].product_id) if wid in wos_by_id else None
            step_idx = (product.routing.index(entry.operation)
                        if product and entry.operation in product.routing else 0)
            planned_start = _hours(t0, entry.start)
            planned_dur = max(_hours(entry.start, entry.end), 1e-6)

            prev_step_end = wo_step_end.get(wid, {}).get(step_idx - 1, 0.0)
            actual_start = max(planned_start,
                               machine_ready[entry.machine_id],
                               prev_step_end)
            if actual_start >= horizon_hours:
                continue  # never starts within the horizon

            setup_h = (machine.setup_minutes / 60.0) * float(rng.uniform(0.85, 1.25))
            proc_h = ((entry.quantity / machine.units_per_hour)
                      * float(rng.uniform(0.95, 1.15)))
            base_dur = setup_h + proc_h

            # Breakdowns: Poisson arrivals over the busy interval, exponential
            # repairs around MTTR; degrading machines (vibration) fail more.
            failure_rate = ((1.0 + machine.vibration_trend)
                            / max(machine.mtbf_hours, 1e-6))
            n_failures = int(rng.poisson(base_dur * failure_rate))
            downtime = 0.0
            for _ in range(n_failures):
                fail_at = actual_start + float(rng.uniform(0.0, 1.0)) * base_dur
                repair_h = float(np.clip(rng.exponential(machine.mttr_hours),
                                         0.25, 4.0 * machine.mttr_hours))
                downtime += repair_h
                events.append(SimEvent(
                    timestamp_hours=round(fail_at, 3), event_type="breakdown",
                    machine_id=machine.machine_id, work_order_id=wid,
                    detail={"repair_hours": round(repair_h, 2)}))
                events.append(SimEvent(
                    timestamp_hours=round(fail_at + repair_h, 3),
                    event_type="repair", machine_id=machine.machine_id,
                    work_order_id=wid))

            actual_end = actual_start + base_dur + downtime

            # Scrap: baseline + vibration drift + noise.
            scrap_frac = float(np.clip(
                machine.scrap_rate_baseline
                + 0.05 * machine.vibration_trend
                + rng.normal(0.0, 0.004),
                0.0, 0.30))
            scrap_units = entry.quantity * scrap_frac
            if scrap_units >= 0.5:
                events.append(SimEvent(
                    timestamp_hours=round(actual_end, 3), event_type="scrap",
                    machine_id=machine.machine_id, work_order_id=wid,
                    detail={"units": round(scrap_units, 2),
                            "fraction": round(scrap_frac, 4)}))

            events.append(SimEvent(
                timestamp_hours=round(actual_start, 3), event_type="job_start",
                machine_id=machine.machine_id, work_order_id=wid,
                detail={"operation": entry.operation,
                        "quantity": entry.quantity}))
            events.append(SimEvent(
                timestamp_hours=round(actual_end, 3), event_type="job_complete",
                machine_id=machine.machine_id, work_order_id=wid,
                detail={"operation": entry.operation}))

            machine_ready[entry.machine_id] = actual_end
            machine_busy[entry.machine_id] += base_dur
            downtime_total += downtime
            planned_dur_sum += planned_dur
            actual_dur_sum += base_dur
            wo_step_end.setdefault(wid, {})
            wo_step_end[wid][step_idx] = max(
                wo_step_end[wid].get(step_idx, 0.0), actual_end)
            wo_first_start[wid] = min(wo_first_start.get(wid, actual_start),
                                      actual_start)
            wo_finish[wid] = max(wo_finish.get(wid, 0.0), actual_end)
            wo_executed[wid] = wo_executed.get(wid, 0) + 1
            wo_scrap[wid] = wo_scrap.get(wid, 0.0) + scrap_units
            total_scrap += scrap_units
            total_started_qty += entry.quantity

        kpis = self._compute_kpis(
            horizon_hours=horizon_hours,
            wos_in_schedule=sorted(expected_entries),
            wos_by_id=wos_by_id,
            products_by_id=products_by_id,
            material_cost=material_cost,
            t0=t0,
            expected_entries=expected_entries,
            wo_executed=wo_executed,
            wo_finish=wo_finish,
            wo_first_start=wo_first_start,
            wo_scrap=wo_scrap,
            machine_busy=machine_busy,
            downtime_total=downtime_total,
            planned_dur_sum=planned_dur_sum,
            actual_dur_sum=actual_dur_sum,
            total_scrap=total_scrap,
            total_started_qty=total_started_qty,
        )
        events.sort(key=lambda e: (e.timestamp_hours, e.event_type,
                                   e.machine_id or "", e.work_order_id or ""))
        return kpis, events

    def _compute_kpis(self, **s) -> Dict[str, float]:
        """Fold one replication's tallies into the standard KPI dict."""
        horizon = s["horizon_hours"]
        wos_by_id: Dict[str, WorkOrder] = s["wos_by_id"]
        products_by_id: Dict[str, Product] = s["products_by_id"]

        throughput = 0.0
        on_time = 0
        late_penalty = 0.0
        material_cost_total = 0.0
        wip_area = 0.0
        considered = 0

        for wid in s["wos_in_schedule"]:
            wo = wos_by_id.get(wid)
            if wo is None:
                continue
            considered += 1
            finish = s["wo_finish"].get(wid)
            executed_all = s["wo_executed"].get(wid, 0) == s["expected_entries"][wid]
            completed = executed_all and finish is not None and finish <= horizon
            due_h = _hours(s["t0"], wo.due_date)
            good_units = max(0.0, wo.quantity - s["wo_scrap"].get(wid, 0.0))

            if completed:
                throughput += good_units
                if finish <= due_h:
                    on_time += 1
                else:
                    late_penalty += (finish - due_h) * self.LATE_PENALTY_PER_HOUR
            elif due_h < horizon:
                late_penalty += self.UNFINISHED_PENALTY

            if wid in s["wo_first_start"]:
                start = min(s["wo_first_start"][wid], horizon)
                end = min(finish if finish is not None else horizon, horizon)
                wip_area += wo.quantity * max(0.0, end - start)
                product = products_by_id.get(wo.product_id)
                if product:
                    material_cost_total += sum(
                        line.quantity_per_unit * wo.quantity
                        * s["material_cost"].get(line.material_id, 1.0)
                        for line in product.bom)

        busy_sum = sum(s["machine_busy"].values())
        downtime = s["downtime_total"]
        availability = busy_sum / max(busy_sum + downtime, 1e-9)
        performance = float(np.clip(
            s["planned_dur_sum"] / max(s["actual_dur_sum"], 1e-9), 0.0, 1.0))
        scrap_rate = s["total_scrap"] / max(s["total_started_qty"], 1e-9)
        quality = max(0.0, 1.0 - scrap_rate)
        machine_cost = self.MACHINE_HOUR_COST * (busy_sum + downtime)
        makespan = max(s["wo_finish"].values(), default=0.0)

        return {
            "throughput_units": throughput,
            "otd_rate": on_time / max(considered, 1),
            "oee": availability * performance * quality,
            "wip_units": wip_area / max(horizon, 1e-9),
            "scrap_rate": scrap_rate,
            "total_cost": material_cost_total + machine_cost + late_penalty,
            "makespan_hours": makespan,
        }
