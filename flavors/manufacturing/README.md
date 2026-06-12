# Manufacturing Flavor — AI-Agent-Native ERP for Discrete Manufacturing

A fully open-source, end-to-end agentic ERP vertical: six PRREEL agents, three
decision councils, four workflows, a deterministic plant simulator, a
MiroFish-style swarm scenario engine, Karpathy-autoresearch-style AutoOptimize
loops, markdown Agent Skills, a governed agent harness (budgets, policy gates,
hash-chained audit receipts, human-in-the-loop approvals), and a Mission Control
API — all runnable locally with zero cloud dependencies.

Design doc: [`docs/plans/MANUFACTURING_FLAVOR_DESIGN.md`](../../docs/plans/MANUFACTURING_FLAVOR_DESIGN.md)
· Decisions: D-016…D-020 in [`docs/decisions/DECISION_LOG.md`](../../docs/decisions/DECISION_LOG.md)

## Quick start

```bash
make install                      # core deps only
make serve                        # gateway on :8000 (manufacturing mounts at /manufacturing)

# Get a token
TOKEN=$(curl -s -X POST localhost:8000/v1/auth/token -H 'Content-Type: application/json' \
  -d '{"tenant_id":"plant-1","scopes":["agents:read","agents:write","workflows:run","scenarios:run","optimize:run","approvals:write","receipts:read"]}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# Fleet + baseline KPIs (seeded plant, simulated)
curl -s localhost:8000/manufacturing/fleet -H "Authorization: Bearer $TOKEN"
curl -s localhost:8000/manufacturing/kpis  -H "Authorization: Bearer $TOKEN"

# Run the order-to-production workflow
curl -s -X POST localhost:8000/manufacturing/workflows/order_to_production/run \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"input_data":{}}'

# What-if: 2-week supplier outage (swarm scenario)
curl -s -X POST localhost:8000/manufacturing/scenarios/run \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"sup1-outage","shock":{"type":"supplier_outage","supplier_id":"SUP-1","days":14}}'

# Let the factory improve its own scheduling policy (journaled, rollback-safe)
curl -s -X POST localhost:8000/manufacturing/autoresearch/run \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"steps":10}'
```

## Architecture

```
                       ┌──────────────  Mission Control (/manufacturing) ─────────────┐
                       │ fleet · kpis · workorders · schedule · workflows · scenarios │
                       │ autoresearch · approvals (HITL) · receipts (audit) · status  │
                       └──────────────────────────────┬────────────────────────────---┘
                                                      │ gateway auth scopes + rate limits
        ┌─────────────────────────────────────────────┼──────────────────────────────────┐
        │                       AgentHarness (src/core/harness)                          │
        │   budgets · policy gates (ALLOW/DENY/REQUIRE_APPROVAL) · skill injection       │
        │   hash-chained receipts · approval queue · Prometheus/OTel                     │
        └───┬─────────┬─────────┬──────────┬──────────┬─────────────┬────────────────────┘
            │         │         │          │          │             │
   ProductionPlanner Quality Maintenance Procurement Inventory  EHSCompliance     (PRREEL agents)
            │         │         │          │          │             │
        ┌───┴─────────┴─────────┴──────────┴──────────┴─────────────┴───┐
        │ Councils: S&OP · Quality · Maintenance (weighted deliberation)│
        │   ← ScenarioReports from the swarm engine as evidence         │
        └───────────────┬───────────────────────────┬───────────────────┘
                        │                           │
              PlantSimulator (seeded DES)   SwarmWorld (persona agents w/ memory)
                        ↑                           ↑
              AutoOptimizeLoop (propose→simulate→keep-if-better→journal)
```

## The four headline capabilities

### 1. Agent Skills (`skills/*.skill.md`, registry in `src/core/skills`)
Versioned markdown skill packs (YAML frontmatter + procedure body): scheduling
optimization, SPC analysis, RCA/8D, MRP planning, OEE improvement. The harness
matches skills to the task and injects them into the agent's reasoning context.
Add expertise by adding a markdown file — no code change.

### 2. AutoOptimize loops (`autoresearch/`, Karpathy-autoresearch pattern)
The agent doesn't edit code — it mutates a bounded `SchedulingPolicy`
(dispatch rule, batching, maintenance buffers), evaluates each mutation on the
seeded plant simulator (3 replications, 168h horizon), keeps it only if the
weighted OTD/OEE/cost objective improves, and journals every step (accepted or
rolled back) as an auditable `OptimizationStep`. Safe, explainable
self-improvement.

### 3. Swarm scenarios (`simulation/swarm.py`, MiroFish pattern)
A digital world of persona agents — suppliers, machines, operators, customers —
with memory and relations. Apply a shock (supplier outage, demand spike,
machine failure, price spike) and watch emergent behavior unfold day by day.
The resulting `ScenarioReport` (timeline, KPI impact, risks, recommendations)
feeds the S&OP council as deliberation evidence. Predict before you act.

### 4. Deep-agent missions (`deep_agents.py`)
Long-horizon goals ("cut late deliveries 30%") decompose into plan boards and
execute through harnessed sub-agents — natively with zero extra dependencies,
or via LangChain deepagents when installed (`pip install "ants[deep]"`).

## Governance ("controlled autonomy")

| Guardrail | Where | Behavior |
|---|---|---|
| PO > $50k | `policies/` | parked for human approval in Mission Control |
| Schedule change > 20% capacity | `policies/` | requires approval |
| EHS critical severity | `policies/` | always requires a human |
| Every agent action | harness | hash-chained receipt (verifiable, tamper-evident) |
| Budgets | harness | wall-clock + action caps per run |
| Auth | gateway | per-scope JWT/API-key, per-credential rate limits |

## Layout

```
models.py          domain contract (single source of truth)
agents/            6 PRREEL agents (work with or without an LLM)
councils/          S&OP, Quality, Maintenance
workflows/         order_to_production, predictive_maintenance, quality_rca,
                   supply_disruption_response
simulation/        plant.py (deterministic DES + PolicyScheduler), swarm.py
autoresearch/      optimize_loop.py (+ JSONL journal)
skills/            *.skill.md packs
mission_control/   FastAPI router (mounted by the gateway)
policies/          approval-threshold policies for the harness
data/seed.py       deterministic demo factory (8 machines, 4 products, 4 suppliers)
```

Tests live in `tests/flavors/manufacturing/` and run with the root suite.
