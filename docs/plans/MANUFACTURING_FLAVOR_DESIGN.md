# Manufacturing Flavor — Design (AI-Agent-Native ERP for Manufacturing)

**Date:** 2026-06-12 · **Status:** Approved, under construction
**Decisions:** D-016…D-020 in [`../decisions/DECISION_LOG.md`](../decisions/DECISION_LOG.md)

## 1. Goal

An end-to-end, fully open-source, agent-native ERP vertical for discrete
manufacturing, runnable entirely locally (no cloud dependency), built on the ANTS
core (PRREEL agents, councils, memory substrate, gateway) and adding four new
capabilities inspired by the current state of the art:

| Capability | Inspiration | What it means here |
|---|---|---|
| **Agent Skills** | Agent-skills pattern (SKILL.md) | Versioned markdown skill packs (frontmatter + procedure) loaded into agent context by a `SkillRegistry`; agents declare skills, the harness injects them |
| **AutoOptimize loops** | [Karpathy's autoresearch](https://github.com/karpathy/autoresearch) | Propose → simulate → measure → keep-if-better → journal/rollback loops over *parameterized scheduling policies*, evaluated on the plant simulator. The factory improves itself nightly, with every accepted change journaled |
| **Swarm scenario simulation** | [MiroFish](https://github.com/666ghj/MiroFish) | Build a "digital world" of the plant + supply network (machines, operators, suppliers, customers as lightweight persona agents with memory), run what-if scenarios, emit a prediction report that councils consult before deciding |
| **Deep-agent missions** | [LangChain deepagents](https://github.com/langchain-ai/deepagents) | Optional `[deep]` extra: long-horizon missions decomposed into plans + sub-agent tasks; ANTS harness provides the same primitives natively (plan board, sub-task spawn) when deepagents isn't installed |

Plus a **comprehensive agent harness** (budgets, policy gates, receipts, replay,
HITL approvals), **security** (scoped auth, policy checks on actions), **monitoring**
(Prometheus + OTel, already core), and **Mission Control** (operational API + fleet
view) mounted into the one gateway.

## 2. Package layout (the contract)

```
flavors/manufacturing/                  # importable package (underscore-safe)
  __init__.py
  models.py            # ALL shared dataclasses/enums — single source of truth
  agents/              # 6 PRREEL agents (BaseAgent subclasses)
    production_planner_agent.py  quality_agent.py  maintenance_agent.py
    procurement_agent.py         inventory_agent.py  ehs_compliance_agent.py
  councils/            # sop_council.py, quality_council.py, maintenance_council.py
  workflows/           # order_to_production.py, predictive_maintenance.py,
                       # quality_rca.py, supply_disruption_response.py
  simulation/          # plant.py (PlantSimulator), swarm.py (scenario engine)
  autoresearch/        # optimize_loop.py (+ journal)
  skills/              # *.skill.md packs (scheduling, SPC, RCA/8D, MRP, OEE)
  mission_control/     # router.py (FastAPI APIRouter)
  policies/            # action policies (python policy defs evaluated by harness)
  data/                # seed.py — deterministic factory seed data
src/core/skills/       # generic SkillRegistry + loader (core, reusable)
src/core/harness/      # generic AgentHarness (core, reusable)
tests/flavors/manufacturing/   # collected by root pytest
```

## 3. Core interface contracts

### 3.1 `models.py` (already written — see file)
Machines, work orders, BOM, inventory, quality, maintenance, schedules, scenarios,
simulation reports, KPI snapshots. Everything else imports from here; nobody
redefines these.

### 3.2 PlantSimulator (deterministic, seeded)
```python
sim = PlantSimulator(seed=42)                  # builds plant from data/seed.py
sim.load(machines, work_orders, inventory)     # or explicit state
result: SimulationResult = sim.run(
    schedule: ProductionSchedule, horizon_hours: float, replications: int = 1)
# result.kpis: KPISnapshot (throughput_units, otd_rate, oee, wip_units,
#   scrap_rate, total_cost, makespan_hours), result.events: list[SimEvent]
```
Same seed + same inputs ⇒ identical results (tests rely on this).

### 3.3 Scheduling policy (the AutoOptimize search space)
```python
@dataclass SchedulingPolicy: dispatch_rule: str  # "EDD"|"SPT"|"CR"|"WSPT"|"FIFO"
    batch_size_factor: float; maintenance_buffer_hours: float;
    expedite_threshold: float; queue_weight_due: float; queue_weight_setup: float
PolicyScheduler(policy).build_schedule(work_orders, machines) -> ProductionSchedule
```
`AutoOptimizeLoop.step()`: mutate one field → simulate N replications → accept if
objective improves (default: weighted OTD/OEE/cost) → append JSONL journal entry
(accepted or rolled back, with metrics before/after). `run(n_steps)` loops.

### 3.4 Swarm scenario engine
```python
world = SwarmWorld.from_seed(seed_entities)    # persona agents w/ memory+relations
report: ScenarioReport = world.run_scenario(SimulationScenario(
    name, shock: dict, horizon_days, narrative))
# report: timeline of emergent events, entity reactions, kpi_impact estimate,
#   recommendations — councils receive this as deliberation evidence
```

### 3.5 Skills
`SKILL.md` format: YAML frontmatter (`name, version, domain, triggers, tools`)
+ markdown body (procedure). `SkillRegistry.load_dir(path)`,
`registry.match(task_description) -> list[Skill]`,
`skill.render() -> str` (for prompt injection). Agents declare `skills=[...]` in
config; the harness injects matched skill bodies into the reasoning context.

### 3.6 AgentHarness (core)
```python
harness = AgentHarness(agent, policies=[...], skill_registry=..., budget=Budget(
    max_seconds, max_actions, max_tokens), receipt_sink=...)
outcome = await harness.run(input_data, context)
```
Pipeline: policy pre-check (deny/allow/require_approval) → skill injection →
`agent.run()` → policy post-check on actions → hash-chained receipt (agent id,
inputs hash, actions, policy decisions, cost, trace id) → episodic persistence
(when memory available). `require_approval` parks the run in an ApprovalQueue
(Mission Control exposes approve/reject).

### 3.7 Mission Control API (mounted under `/manufacturing`)
```
GET  /manufacturing/fleet            # registered agents + health/state
GET  /manufacturing/kpis             # latest KPISnapshot from simulator/runs
POST /manufacturing/workorders       # create work order
GET  /manufacturing/schedule         # current schedule
POST /manufacturing/workflows/{name}/run     # run a workflow (auth: workflows:run)
POST /manufacturing/scenarios/run    # swarm what-if (auth: scenarios:run)
POST /manufacturing/autoresearch/step|run    # optimization loop (auth: optimize:run)
GET  /manufacturing/autoresearch/journal
GET  /manufacturing/approvals        # pending HITL approvals
POST /manufacturing/approvals/{id}/approve|reject  (auth: approvals:write)
GET  /manufacturing/receipts         # audit receipts (auth: receipts:read)
```
Reuses gateway auth (scopes above); per-credential rate limiting applies.

## 4. The six agents (PRREEL, deterministic fallbacks, LLM-optional)

| Agent | Type id | Core duties (fallback logic is real, not placeholder) |
|---|---|---|
| ProductionPlannerAgent | `manufacturing.production_planner` | MRP-lite: explode BOM, net against inventory, build schedule via PolicyScheduler, flag capacity overload |
| QualityAgent | `manufacturing.quality` | SPC: control-chart rules (Western Electric) on inspection series; NCR creation; disposition recommendation |
| MaintenanceAgent | `manufacturing.maintenance` | Weibull-ish risk scoring from runtime hours/vibration trend; PM scheduling inside maintenance_buffer windows |
| ProcurementAgent | `manufacturing.procurement` | Reorder-point purchasing, supplier scoring (OTD, defect ppm), PO generation w/ approval threshold |
| InventoryAgent | `manufacturing.inventory` | ABC classification, safety-stock calc, shortage projection vs schedule |
| EHSComplianceAgent | `manufacturing.ehs_compliance` | Incident triage, lockout/tagout checklist verification, compliance calendar |

Councils (reuse capital-markets council pattern): **S&OP Council** (planner +
procurement + inventory deliberate demand/supply plan; consumes ScenarioReport),
**Quality Council** (disposition of major NCRs — HITL above severity threshold),
**Maintenance Council** (downtime-window allocation).

Workflows: `order_to_production` (order → MRP → schedule → release → simulate →
KPIs), `predictive_maintenance` (telemetry → risk → council → PM order),
`quality_rca` (NCR → 8D-skill-guided RCA → CAPA), `supply_disruption_response`
(shock → swarm scenario → S&OP council → revised plan + POs).

## 5. Security & monitoring

- Every Mission Control route requires a scope; approval thresholds in
  `policies/` (e.g., PO > $50k, schedule change > 20% capacity, any EHS critical →
  `require_approval`).
- Receipts are hash-chained JSONL + queryable endpoint (start of WS-2 for real).
- Metrics: existing Prometheus/OTel core instruments + harness counters
  (runs, policy denials, approvals pending, optimization acceptance rate).

## 6. Open-source stance

Core + manufacturing flavor run with zero proprietary services: deterministic
simulator, optional Ollama for real LLM reasoning, Postgres+pgvector for memory,
Apache-2.0 throughout. `deepagents` integration lives behind the `[deep]` extra
with graceful degradation.
