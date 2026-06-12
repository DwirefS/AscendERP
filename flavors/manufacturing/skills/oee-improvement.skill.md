---
name: oee-improvement
version: 1.0.0
domain: manufacturing
description: Decompose OEE into availability, performance, and quality losses and pick the highest-leverage improvement plays.
triggers:
  - oee
  - equipment effectiveness
  - downtime
  - availability
  - minor stops
  - changeover
  - utilization
  - six big losses
tools:
  - machine_telemetry
  - maintenance_history
  - plant_simulator
---
# OEE Improvement Procedure

## 1. Compute and decompose
```
OEE = Availability × Performance × Quality
Availability = run_time / planned_production_time
Performance  = (ideal_cycle_time × total_count) / run_time
Quality      = good_count / total_count
```
World-class discrete manufacturing ≈ 85% (90% A × 95% P × 99% Q). Typical
unimproved plants sit near 60%. Always report the three factors, never just
the headline number — 60% from bad availability needs a different fix than
60% from slow cycles.

## 2. Loss taxonomy (the six big losses)
**Availability losses**
1. *Breakdowns* — unplanned stops > 5–10 min (failures, tooling breakage).
2. *Setup & adjustment* — changeovers, trials, planned maintenance overruns.

**Performance losses**
3. *Minor stops* — < 5 min jams, misfeeds, sensor blocks; rarely logged,
   often the biggest hidden loss. Trust counters, not memory.
4. *Reduced speed* — running below ideal cycle (worn tooling, cautious
   settings after past quality scares, suboptimal parameters).

**Quality losses**
5. *Startup/yield scrap* — defects during warm-up and after changeover.
6. *Production rejects* — defects in steady-state running.

## 3. Improvement plays, by dominant loss
- **Breakdowns dominate:** move from reactive to planned — risk-score
  machines (runtime since PM, vibration trend, MTBF), schedule PM inside the
  maintenance buffer windows on the bottleneck's low-load shift; attack the
  top recurring failure mode with RCA, not the average.
- **Changeover dominates:** SMED — film a changeover, split internal vs
  external steps, move steps external (prep while running), then streamline.
  50% reduction without capex is the normal first result. Then consider
  re-sequencing to group similar setups (raise `queue_weight_setup`).
- **Minor stops dominate:** instrument first (auto-count stops), Pareto by
  station, fix the top jam point; check material presentation and sensors.
- **Reduced speed:** verify the *ideal* cycle time is honest (not padded);
  restore parameters to standard, address tooling wear schedule.
- **Startup scrap:** standardize first-article checks and warm-up recipes;
  smaller batches make startup loss a larger share — weigh against flow gains.
- **Steady-state rejects:** hand off to SPC analysis (control the process)
  and RCA/8D for recurring defects.

## 4. Guardrails
1. Improve OEE on the **bottleneck** first; OEE gains on non-bottlenecks
   mostly create WIP.
2. Never "improve" availability by skipping PM or quality checks — it shows
   up later with interest (the simulator will show it within one horizon).
3. Validate each play with before/after KPI snapshots (OEE, OTD, scrap,
   cost) over at least a week-long simulated or measured horizon.
