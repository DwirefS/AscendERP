---
name: scheduling-optimization
version: 1.0.0
domain: manufacturing
description: Select and tune dispatch rules, reason about bottlenecks, and evaluate schedule changes on the plant simulator before release.
triggers:
  - scheduling
  - dispatch rule
  - bottleneck
  - sequence jobs
  - makespan
  - late orders
  - capacity overload
  - production schedule
tools:
  - policy_scheduler
  - plant_simulator
  - autoresearch_loop
---
# Scheduling Optimization Procedure

## 1. Diagnose before you tune
1. Pull the current schedule and KPI snapshot (OTD rate, OEE, WIP, makespan).
2. Identify the bottleneck: the work center with the highest utilization
   (queue time / total time). The bottleneck governs throughput — an hour lost
   there is an hour lost for the whole plant; an hour saved elsewhere is a mirage.
3. Classify the dominant pain:
   - Many late orders, due dates clustered → due-date problem.
   - Long queues, high WIP, low throughput → flow/sequencing problem.
   - Excessive setup time share (>15% of bottleneck time) → batching problem.

## 2. Dispatch rule selection heuristics
| Symptom | Rule | Why |
|---|---|---|
| Late deliveries, varied due dates | **EDD** (earliest due date) | Minimizes maximum lateness |
| High WIP, queue congestion | **SPT** (shortest processing time) | Minimizes mean flow time; clears queues fastest |
| Mixed urgency + long/short jobs | **CR** (critical ratio = time remaining / work remaining) | Balances urgency against work content; expedite when CR < 1 |
| Orders differ in value/priority | **WSPT** (weighted SPT) | Maximizes weighted throughput per machine-hour |
| Stable demand, fairness matters | **FIFO** | Predictable, low nervousness, easiest for operators |

Caution: SPT starves long jobs — pair it with an expedite threshold
(critical ratio cutoff ~0.8) so aging jobs jump the queue.

## 3. Parameter tuning guidance
- `batch_size_factor` (0.25–2.0): smaller batches cut queue time and improve
  flow but raise setup share. Reduce only while bottleneck setup share < 20%.
- `maintenance_buffer_hours`: reserve PM windows on the bottleneck during the
  lowest-load shift; skipping PM trades scheduled minutes for unscheduled hours.
- `queue_weight_due` vs `queue_weight_setup`: raise the setup weight when
  changeovers dominate; raise the due weight when OTD is the failing KPI.
- `expedite_threshold`: raise it when chronic firefighting reorders the whole
  queue (everything expedited = nothing expedited).

## 4. Validate, then release
1. Never release a policy change on intuition: simulate ≥3 replications over a
   ≥1 week horizon and compare KPI deltas against the incumbent policy.
2. Accept only if the weighted objective (OTD, OEE, cost) improves; otherwise
   roll back and journal the rejected step with metrics before/after.
3. Watch for KPI trades: a makespan win that raises scrap or starves a
   downstream cell is not a win. Check WIP and scrap deltas explicitly.
4. Flag capacity overload (load > 95% of available bottleneck hours) to the
   planner — no dispatch rule fixes a plant that is simply over-committed.
