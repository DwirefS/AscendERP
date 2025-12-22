# Reference Implementations
**Ascend ERP / ANTS: runnable vertical demos + golden paths**

This document defines a **Reference-Implementations/** structure for the repo. The goal is *adoptability*: developers and enterprise teams must be able to deploy a minimal stack, run a demo, and understand how to extend it.

---

## 0) Repository Layout (recommended)
```
reference-implementations/
  common/
    datasets/                 # small, legally shareable sample data
    scripts/                  # load, seed, generate
    eval/                     # CLEAR + RAG eval harness
    mcp/                      # sample MCP servers (safe, stubbed)
    policies/                 # policy-as-code examples
    dashboards/               # Grafana/PowerBI starter dashboards
  finance/
  retail/
  manufacturing/
  healthcare/
```

---

## 1) Golden Paths (the 3 most valuable ways to start)
### GP1: “Enterprise RAG Assistant”
- Ingest PDFs/docs into ANF
- OCR + chunk + embed (GPU accelerated)
- Index into (pgvector or Weaviate/Milvus) and/or Azure AI Search
- Chat UI answers with citations and guardrails

**Why:** lowest friction, highest immediate business value.

### GP2: “Multi-Agent Workflow Automation”
- Define a LangGraph workflow for a real process
- Agents coordinate tool use (DB, search, ticketing stubs)
- Produce receipts + audit logs

**Why:** shows ANTS as execution layer, not just chat.

### GP3: “SelfOps Autopilot”
- Health checks + drift detection + auto rollback
- Demonstrates policy gates, receipts, and operational maturity

**Why:** the differentiator enterprises will remember.

---

## 2) Reference Implementation 1: Finance (Reconciliation + Audit Receipts)
### Demo narrative
**“Close the books faster, with perfect traceability.”**

#### Inputs
- invoices (PDF), purchase orders (CSV), GL entries (Postgres tables)
- event stream of new transactions

#### Pipeline
1. Ingest docs to ANF
2. OCR + extraction → structured fields
3. Match PO ↔ invoice ↔ receipt ↔ GL entries
4. Flag anomalies and produce a reconciliation report
5. Human approval gate for adjustments
6. Post journal entry via tool stub (or real ERP integration later)
7. Write receipts (who/what/why) to immutable audit log

#### What you ship
- `finance/demo.md` (story + screenshots)
- `finance/load_data.py`
- `finance/agents/finance_recon_agent.py`
- `finance/policies/sox_gate.rego` (example)
- `finance/eval/accuracy_suite.py` (CLEAR metrics)

---

## 3) Reference Implementation 2: Retail (Demand Signals + Inventory Agent)
### Demo narrative
**“From demand signals to replenishment—autonomously.”**

#### Inputs
- POS events stream
- inventory table + supplier lead times
- product catalog (docs + structured)

#### Pipeline
1. Event Hubs stream → Spark/Databricks (or lightweight streaming) → curated tables
2. Agent queries “what will stock out in 48 hours?”
3. Agent proposes reorder plan with confidence + cost impact
4. Human approval gate triggers purchase order creation
5. Dashboards show forecast accuracy + service levels

#### What you ship
- `retail/demand_forecast_agent.py`
- `retail/streaming_simulator.py`
- `retail/policies/reorder_limits.rego`
- `retail/dashboards/`

---

## 4) Reference Implementation 3: Manufacturing (Digital Twin + Vision QA)
### Demo narrative
**“Digital twin triggers + vision QA = fewer outages and defects.”**

#### Inputs
- IoT telemetry (machine temp, vibration)
- Digital Twin model graph + state
- optional video stream metadata for inspection

#### Pipeline
1. IoT Hub → Digital Twins (state sync)
2. Twin event triggers workflow (maintenance agent)
3. RAG retrieves manuals + incident history
4. Agent recommends action and generates work order
5. If video enabled: VSS-style summarization pipeline on sample clips
6. Results stored in memory substrate; receipts logged

#### What you ship
- `manufacturing/twin_event_router.py`
- `manufacturing/maintenance_agent.py`
- `manufacturing/runbook_generator.py`
- `manufacturing/video_demo/` (optional, stubbed if needed)

---

## 5) Reference Implementation 4: Healthcare (PHI-safe RAG + Strict Policy Gates)
### Demo narrative
**“Clinical + operational intelligence without violating compliance.”**

#### Inputs
- de-identified sample notes (synthetic)
- policy docs (HIPAA, internal SOPs)
- operational scheduling events

#### Pipeline
1. Strict data classification tags at ingestion
2. Role-based retrieval filters
3. RAG assistant answers with citations and redaction rules
4. Any action (e.g., appointment changes) requires policy gates
5. Full audit trail for compliance reporting

#### What you ship
- `healthcare/redaction_middleware.py`
- `healthcare/policies/hipaa_access.rego`
- `healthcare/audit/receipt_schema.json`
- `healthcare/eval/`

---

## 6) Common Tooling Included in Every Demo
### 6.1 MCP Tool Servers (safe & stubbed)
- `mcp/github_stub` (read-only demo of repo interactions)
- `mcp/itops_stub` (simulated infra calls)
- `mcp/ticketing_stub` (ServiceNow/Jira style)
- `mcp/erp_stub` (post journal entry / create PO)

### 6.2 Evaluation Harness (CLEAR + RAG)
- cost: token usage + GPU seconds + storage IO
- latency: end-to-end and per tool-call
- efficacy: accuracy, task success rate
- assurance: policy compliance, redaction success, safety tests
- reliability: uptime, retries, error budgets

### 6.3 “One-click deploy”
- terraform module: ANF + AKS + Postgres
- helm charts: agent services, vector DB, NIM endpoints
- sample `make demo-finance` commands

---

## 7) Licensing and Data Safety
- Only include **permissively licensed** libraries in core runtime.
- Any “fair-code” / non-OSI terms must be optional and isolated.
- Demo datasets must be:
  - synthetic, de-identified, or freely redistributable
  - documented with provenance in `datasets/README.md`

---

## 8) What Makes These Demos Viral (without hype)
- They are **end-to-end**
- They show **governance gates**
- They show **audit receipts**
- They show **SelfOps auto rollback**
- They map to **real departments** and **real ROI**
