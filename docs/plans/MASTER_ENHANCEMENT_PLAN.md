# Ascend EOS / ANTS — Master Enhancement & Implementation Plan

**Date:** 2026-06-12
**Branch:** `claude/project-review-enhancement-85ajq1`
**Status:** Living document — updated as work proceeds. Every decision is recorded in
[`docs/decisions/DECISION_LOG.md`](../decisions/DECISION_LOG.md).

---

## 0. Executive Summary

AscendERP (Ascend EOS, powered by ANTS) is a genuinely ambitious agentic-enterprise
platform: ~125K lines of Python across 238 files, three whitepapers, a working
capital-markets vertical, and real implementations of decision councils, swarm
coordination, a three-tier memory substrate, polymorphic stem-cell agents, and
self-extending meta-agents.

**The verdict from a fresh-eyes review:** this is *not* vaporware — roughly 70–75% of
the claimed system is real code — but it is also **not currently runnable end-to-end**.
The single biggest problem is not missing features; it is **missing connective tissue**:
the HTTP gateway, agent registry, memory substrate, policy engine, and UI each exist,
but the spine that joins them into one bootable system is incomplete, and the project
cannot be installed and started by a newcomer in under a day.

The plan below is organized around three goals, in priority order:

1. **Make it work** — a `docker compose up` → working API → working demo path that
   requires zero Azure resources (Workstreams 0–1).
2. **Make it trustworthy** — governance, audit receipts, evaluation harness, honest
   docs (Workstreams 2–4).
3. **Make it matter** — deepen the finance vertical to compete with AI-native ERP
   entrants, add "for-good" verticals, marketplace, and protocol interoperability
   (Workstreams 5–9).

---

## 1. Where the Project Stands (Fresh-Eyes Map)

### 1.1 Architecture map (as found)

| Layer | Location | LOC | Reality check |
|---|---|---|---|
| Core agent framework (PRREEL loop, stem cells, registry) | `src/core/agent/` | ~15.3K (core total) | **Real** (~85%) |
| Memory substrate (episodic/semantic/procedural, pgvector) | `src/core/memory/` | 534+ | **Real** — actual SQL schema, IVFFlat indexes |
| Councils & consensus (weighted vote, Delphi, Nash) | `src/core/council/` | ~2K | **Real** |
| Swarm / pheromone coordination (Event Hubs) | `src/core/swarm/` | ~2.2K | **Real**, but Azure-only |
| Mixture of Experts routing | `src/core/moe/` | ~650 | **Real** |
| Meta-agents (self-coding integrations) | `src/agents/meta/` | ~2.4K | **Real** |
| LLM clients (Azure OpenAI, NIM, GitHub Models, Ollama) | `src/core/llm_client.py`, `src/core/inference/` | ~1.1K | **Real** |
| SelfOps agents (InfraOps/DataOps/AgentOps/SecOps) | `src/agents/selfops/` | ~2.5K | **Real** |
| Capital-markets flavor (6 agents, 4 workflows, 3 councils, API, tests) | `flavors/capital-markets/` | ~12.6K | **Real (~95%)** — has mock mode |
| MCP servers (ERP, HR, Azure, Defender, microcontroller) | `mcp/servers/` | ~2.9K | **Real (~65%)**, duplicates parts of `src/integrations/` |
| API gateway (FastAPI, JWT auth, rate limiting) | `services/api_gateway/` | ~1.4K | **Skeleton (~40%)** — routing to agents incomplete |
| Platform security / policies / receipts / standards | `platform/security/` etc. | ~0 | **Empty scaffolding** |
| Org-department agents (HR, CRM, supply chain, mfg, healthcare) | `src/agents/orgs/` | ~0 | **Empty scaffolding** |
| Data platform connectors (Databricks, Fabric, Lakehouse) | `src/integrations/`, `data/` | partial | **Scaffolding** |
| Data medallion pipeline (bronze→silver→gold) | `data/` | ~1.5K | **Partial (~40%)** |
| Web portal (Next.js 14, MSAL, Socket.io) | `ui/web_portal/` | TS | **Real UI (~70%)**, not wired to backend |
| Examples (14+ runnable demos, 4 industry examples) | `examples/` | ~10.7K | **Real (~90%)** |
| Tests | `tests/`, `flavors/*/tests/` | ~6.3K | Exist; collection/run status addressed in Workstream 0 |
| Infra (Terraform: ANF, AKS-GPU, Event Hubs; Helm; antsctl CLI) | `infra/`, `platform/bootstrap/` | ~2.2K | CLI real (~70%); IaC unverified against a live subscription |

### 1.2 What is genuinely good (keep and amplify)

1. **The conceptual frame aged well.** The 2024–25 whitepaper bets — multi-agent
   collaboration, shared memory, controlled autonomy, governance-first — are exactly
   where the 2026 market landed (Gartner: >40% of enterprise apps embedding
   role-specific agents by end-2026; SAP Joule's "copilot → autonomous operations"
   arc; runtime agent governance as the EU AI Act enforcement battleground).
2. **Councils + consensus algorithms are a real differentiator.** Most agentic
   platforms have a single orchestrator; deliberation with weighted voting/Delphi/Nash
   plus the Condorcet justification is novel and demo-able.
3. **The memory substrate is the right architecture.** Episodic/semantic/procedural
   tiers over PostgreSQL+pgvector matches the 2026 consensus on agent memory
   (graph/vector hybrid, shared team memory, "enterprise mind" patterns).
4. **MCP was the right protocol bet.** MCP won the agent-to-tool layer (~10K
   enterprise servers in production by April 2026). The repo already ships 5 MCP
   servers.
5. **Capital-markets flavor proves the model.** A vertical with agents + workflows +
   councils + API + tests + mock mode is the template every other flavor should copy.
6. **Observability was built in early** (OpenTelemetry, Prometheus, DevUI streaming),
   which is now table stakes for agent platforms.

### 1.3 What is wrong (the honest list)

1. **No end-to-end boot path.** There is no documented, working sequence from clone →
   install → run → see an agent do something. Heavy/conflicting dependencies
   (torch + langchain + autogen + crewai + semantic-kernel in one tree) make
   `pip install` fragile.
2. **Three parallel spines, none complete.** `services/api_gateway`,
   `src/api/agent_streaming_api.py`, and `flavors/capital-markets/api_gateway.py` are
   three separate FastAPI entry points with different auth and different agent-invocation
   paths. The "official" gateway's routing into the agent registry is unfinished.
3. **Governance is claimed but not wired.** `platform/policies/`, `platform/receipts/`,
   `platform/security/` are empty; the OPA engine has a framework but no enforced
   policies in the request path. For a finance-domain agent platform in 2026 (EU AI
   Act enforcement, runtime governance) this is the credibility-critical gap.
4. **Azure hard-dependency for core behaviors.** Pheromones require Event Hubs, state
   requires Cosmos, tasks require Service Bus. There is no local/in-memory bus, so the
   most distinctive feature (swarm coordination) cannot be demonstrated without a
   cloud subscription.
5. **Duplication and drift.** `mcp/servers/erp` vs `src/integrations/`,
   `src/core/observability.py` vs `src/core/observability/`, two `llm_client.py`
   files, `README.md.backup`, `CLAUDE_OLD.md` — the "bulk-up phase" has left
   contradictory parallel implementations.
6. **README overclaims.** "75% complete (production-ready core)" and specific
   business metrics (95% invoice-time reduction, 99% fraud detection) are presented
   as results but are projections. In a market where Rillet/Campfire/DualEntry have
   $65–100M+ and real ledger automation in production, unverifiable claims hurt.
7. **No evaluation harness.** There is no way to measure whether a council decision
   or an agent action is *good* — no benchmark tasks, no regression evals, no replay.
   2026 buyers ask for eval dashboards before they ask for features.
8. **No A2A.** Agent-to-agent interoperability (A2A, 150+ orgs in production) is
   absent; the platform can't talk to non-ANTS agents.
9. **Strategic framework ambiguity.** The repo simultaneously imports LangChain,
   LangGraph, AutoGen, CrewAI, and Semantic Kernel while also implementing its own
   PRREEL loop. Microsoft Agent Framework 1.0 went GA (Apr 2026) and unifies
   SK/AutoGen — the dependency strategy needs a decision (see DECISION_LOG D-007).
10. **Tests don't gate anything.** CI exists for GitHub Pages, not for tests/lint/type
    checks.

### 1.4 Missing architecture links (the connective tissue)

```
[UI (Next.js)] ──X──> [API Gateway] ──X──> [Agent Registry] ──✓──> [PRREEL Agents]
                          │                       │
                          X (not enforced)        ✓
                          v                       v
                    [OPA Policy Engine]     [Memory Substrate (pgvector)]
                          │
                          X (empty)
                          v
                    [Audit Receipts]

[Swarm/Pheromones] ──X (Azure-only, no local bus)──> demonstrable locally
[MCP servers] ──X (no MCP client in agent execute())──> agent tool use
[Eval harness] ──X (does not exist)──> quality measurement
```

Concretely, the five missing links:

| # | Missing link | Fix |
|---|---|---|
| L1 | Gateway → Registry → Agent invocation | Finish `services/api_gateway` routing; one composition root |
| L2 | Policy engine → request path → receipts | Middleware: every agent action passes OPA check, emits signed receipt |
| L3 | Swarm → local message bus abstraction | `MessageBus` interface: in-memory + Redis Streams impl; Event Hubs as prod driver |
| L4 | Agent `execute()` → MCP client → MCP servers | Adopt MCP client in tool registry so agents consume the repo's own MCP servers |
| L5 | UI → gateway WebSocket/SSE | Wire `ChatInterface.tsx` to the gateway's streaming endpoint |

---

## 2. Market Alignment (June 2026)

Findings from current research, with implications:

| Trend | Evidence | Implication for ANTS |
|---|---|---|
| Agentic ERP mainstream | Gartner >40% of enterprise apps w/ role agents by end-2026; SAP Joule agentic GA | Window is open but closing; differentiate on councils+governance, not "agents exist" |
| MCP won agent↔tool | ~10K enterprise MCP servers; all major vendors adopted | Double down: ship MCP client + servers; market the 5 existing servers |
| A2A won agent↔agent | 150+ orgs in production | Add A2A Agent Cards for councils — "your agents can sit on our councils" |
| Microsoft Agent Framework 1.0 GA (Apr 2026) | Unifies SK + AutoGen; Foundry Agent Service on Responses API, BYO-VNet | Replace 5 overlapping frameworks with MAF + own PRREEL core |
| AI-native ERP competitors funded | Rillet ($70M B), Campfire ($65M B), DualEntry | Don't compete on GL features; compete on *platform + governance + verticals* |
| Governance is the buying criterion | EU AI Act enforcement 2026; runtime agent governance research; Singapore agentic-AI framework | Receipts + policy gating + eval evidence = sales asset, build in Workstream 2 |
| Agent memory consolidation | Graph+vector shared memory, "enterprise mind" architectures | Memory substrate is on-trend; add graph layer + entropy mgmt later (WS-8) |

---

## 3. The Plan — Nine Workstreams

> Effort assumes 1–2 engineers + AI-assisted development. Each workstream has
> acceptance criteria ("Definition of Working"). Order matters: WS-0/1 unblock
> everything else.

### WS-0: Get It Working (the boot path) — *1–2 weeks* 🔴 CRITICAL

The deliverable is: **fresh clone → `make dev` → green smoke test → curl a working
agent endpoint → run one example — in under 15 minutes, no Azure account.**

- **0.1 Dependency surgery.** Split `pyproject.toml` into a minimal core
  (`fastapi, pydantic, sqlalchemy, asyncpg, pgvector, httpx, structlog, click,
  opentelemetry`) and optional extras: `[azure]`, `[nvidia]`, `[ml]`, `[frameworks]`,
  `[data]`. Core must install in <2 min on a clean machine. Remove unused heavyweight
  deps from default install (torch, transformers, langchain, autogen, crewai become
  extras).
- **0.2 Fix all import/syntax breaks** found by the buildability audit (tracked in
  DECISION_LOG as they are fixed). Ensure `python -c "import src.core"` and
  `pytest --collect-only` succeed.
- **0.3 Local-first infrastructure profile.** `docker-compose.dev.yml`:
  `postgres+pgvector`, `redis`, optional `ollama`. Settings object
  (pydantic-settings) with `ANTS_PROFILE=local|azure` switching drivers.
- **0.4 MessageBus abstraction (link L3).** `src/core/bus/` with `InMemoryBus`,
  `RedisStreamsBus`, `EventHubsBus` implementing one interface; pheromone client
  refactored onto it.
- **0.5 Mock LLM provider.** Deterministic `MockLLMClient` for tests/demos +
  Ollama for real local inference; provider chosen by profile.
- **0.6 Smoke test + Makefile + CI.** `make dev`, `make test`, `make smoke`.
  GitHub Actions: lint (ruff), type check (mypy, advisory), unit tests, smoke test
  on every PR.

**Definition of Working:** new contributor on a clean machine reaches a responding
`/agents/finance.reconciliation/invoke` endpoint and a passing smoke suite in ≤15 min.

### WS-1: One Spine (unify the architecture) — *2 weeks* 🔴 CRITICAL

- **1.1 Single composition root.** `src/main.py` builds: settings → DB → bus →
  LLM client → tool registry → agent registry → policy engine → FastAPI app.
  `services/api_gateway` becomes the only gateway; `src/api/` streaming endpoints
  mount into it; capital-markets API becomes a mounted flavor router.
- **1.2 Finish gateway → registry routing (link L1)** with SSE/WebSocket streaming
  of PRREEL steps (the DevUI events already exist — surface them).
- **1.3 De-duplicate**: one `llm_client`, one observability module, delete
  `README.md.backup`/`CLAUDE_OLD.md`, fold `mcp/servers/erp` and
  `src/integrations` overlap (decision D-009).
- **1.4 Wire UI (link L5).** `ChatInterface.tsx` → gateway streaming endpoint;
  dashboard reads `/metrics` summary; ship `docker-compose` profile including UI.
- **1.5 MCP client in the tool registry (link L4).** Agents consume MCP servers
  (incl. the repo's own five) through `execute()`; this also future-proofs for
  third-party MCP servers.

**Definition of Working:** one `uvicorn src.main:app` serves UI-connected chat,
agent invocation, streaming reasoning, and capital-markets endpoints, with traces
visible in the OTel exporter.

### WS-2: Trustworthy by Construction (governance, receipts, security) — *2–3 weeks* 🟠 HIGH

This is the EU-AI-Act-era differentiator and directly supports "for good" use.

- **2.1 Policy enforcement in the request path (link L2).** OPA sidecar (or
  `opa` Python eval) middleware: every agent action evaluated against Rego policies;
  write the actual policies the whitepaper describes (data governance, financial
  approval tiers, SoD, agent lifecycle) into `platform/policies/`.
- **2.2 Audit receipts.** `platform/receipts/`: append-only, hash-chained receipt
  per agent action: who (agent identity), what (action+inputs hash), why (goal +
  policy decisions), model/version, cost, trace ID. Export to JSONL + Postgres.
  This is the "flight recorder" regulators and auditors ask for.
- **2.3 Human-in-the-loop gates.** Approval queue for actions exceeding policy
  thresholds (amount, blast radius); surfaced in UI; agent blocks until approved
  or times out. Controlled autonomy, per the whitepaper's own framing.
- **2.4 Security hardening.** Key Vault/env-based secret handling, dependency audit
  (`pip-audit`), authn on all gateway routes, rate limits enforced, container
  hardening (non-root, read-only FS), SBOM in CI.
- **2.5 Identity for agents.** Keep Entra Agent IDs for the Azure profile; local
  profile uses signed service tokens. Every receipt carries the agent identity.

**Definition of Working:** a finance action above threshold is blocked, appears in
the approval queue, and every executed action produces a verifiable receipt chain.

### WS-3: Prove It (evaluation harness) — *2 weeks* 🟠 HIGH

- **3.1 Scenario benchmark suite.** 20–30 golden tasks per flavor (e.g., invoice
  reconciliation cases with known answers, trade-compliance cases) run nightly;
  score correctness, cost, latency, policy violations.
- **3.2 Council A/B evidence.** Empirically test the Condorcet claim: single agent
  vs 5-member vs 9-member council on the benchmark; publish the real numbers
  (whatever they are) and replace the README's theoretical claims with measured ones.
- **3.3 Replay & regression.** Persist full PRREEL traces (already in episodic
  memory) and add `antsctl replay <trace-id>`; CI fails if golden-task scores drop.
- **3.4 Cost telemetry.** Token/cost accounting per agent/action surfaced in the
  dashboard (becomes the Cost Management Dashboard the old roadmap promised).

**Definition of Working:** `make eval` produces a scorecard; README metrics link to
generated eval reports instead of projections.

### WS-4: Honest, Navigable Docs — *1 week* 🟠 HIGH

- **4.1 Truth pass on README**: separate *Implemented / Partially implemented /
  Vision* explicitly; move projections into the whitepaper with "hypothesis" labels.
- **4.2 Quickstart** (the WS-0 path) as the first thing in the README.
- **4.3 Consolidate** the 8 overlapping status/gap/summary docs into
  `docs/STATUS.md` (generated where possible) + archive the rest under
  `docs/archive/`.
- **4.4 ADRs**: adopt the decision log (already started) as the ADR system.
- **4.5 OpenAPI**: the unified gateway auto-generates `/openapi.json`; publish to
  GitHub Pages; regenerate the Postman collection from it.

### WS-5: Finance Vertical Depth (the wedge) — *3–4 weeks* 🟡 MEDIUM

Rather than competing feature-for-feature with funded AI-native ERPs, make ANTS the
**open, governable alternative** with one deep, demonstrable workflow:

- **5.1 Procure-to-pay reconciliation, end-to-end**: ingest invoices (PDF/CSV via
  bronze layer) → match against PO + receipt (3-way match) → council deliberation on
  exceptions → policy-gated payment approval → receipts + eval scoring. Uses only
  local profile + sample data so anyone can run it.
- **5.2 Continuous close starter kit**: journal anomaly detection, accrual
  suggestions, close-checklist agent with HITL gates.
- **5.3 ERP connectors as MCP servers**: harden the existing ERP MCP server; add a
  read-only NetSuite/Dynamics-style mock + interface contract so real connectors are
  fill-in-the-blank.

### WS-6: For-Good Flavors (purpose) — *3–4 weeks* 🟡 MEDIUM

Apply the proven flavor template (capital-markets structure) to domains with high
social return and low competition:

- **6.1 Nonprofit/NGO operations flavor**: grant-compliance agent (tracks restricted
  funds usage), donor-report generation, program-outcome measurement councils.
  Nonprofits are exactly the under-resourced back offices agentic ERP helps most.
- **6.2 Public-sector grants management**: application triage, eligibility checking
  with full receipts (auditability is mandatory here — WS-2 becomes the selling point).
- **6.3 Healthcare access (expand existing example)**: patient-scheduling and
  prior-auth paperwork agents with HIPAA-aligned policies in Rego.
- **6.4 ESG/sustainability reporting**: CSRD-style data collection from the medallion
  pipeline, with evidence-linked receipts per reported figure.

Each flavor = agents + workflows + councils + policies + golden eval tasks + sample
data + one-command demo, following the capital-markets template.

### WS-7: Interoperability (A2A + marketplace) — *2–3 weeks* 🟡 MEDIUM

- **7.1 A2A support**: publish Agent Cards for ANTS agents; allow external A2A agents
  to join councils as guest members (policy-gated, receipt-logged). This is a unique
  demo: *cross-vendor deliberation*.
- **7.2 Marketplace MVP**: make `marketplace/deploy_template.py` real — template
  validation, `antsctl deploy template <name>`, and registry listing in the UI for the
  3 existing YAML templates + new flavor templates.
- **7.3 Microsoft Agent Framework alignment**: migrate AutoGen/SK usage to MAF 1.0;
  keep PRREEL as the cognitive loop and MAF for orchestration/Foundry hosting
  (decision D-007).

### WS-8: Platform Maturity — *4+ weeks* 🟢 LATER

- Multi-tenancy (schema-per-tenant + tenant-scoped policies/receipts)
- Memory entropy management (decay, summarization, forgetting — per whitepaper §memory)
- Graph layer over semantic memory (shared team memory pattern)
- Visual workflow designer; advanced RBAC; Arc/edge story validation
- Load testing toward the 1000-agent claim; chaos tests

### WS-9: Infra Validation — *1–2 weeks, parallel* 🟢 LATER

- Validate Terraform modules against a real subscription (plan-only in CI)
- Helm chart smoke deploy on kind/k3d in CI
- `antsctl deploy` end-to-end against the local k3d profile

---

## 4. Sequencing & Effort

```
Weeks 1–2   WS-0 Boot path  ──────────────► everything depends on this
Weeks 2–4   WS-1 One spine
Weeks 4–6   WS-2 Governance+receipts   WS-4 Docs truth pass (parallel, wk 4)
Weeks 6–8   WS-3 Eval harness
Weeks 8–12  WS-5 Finance depth         WS-7 A2A/marketplace (parallel)
Weeks 12–16 WS-6 For-good flavors      WS-9 Infra validation (parallel)
Weeks 16+   WS-8 Platform maturity
```

Milestones:
- **M1 (wk 2):** `make dev` works; CI green. *"It runs."*
- **M2 (wk 4):** unified gateway + UI chat + capital-markets demo. *"It's one system."*
- **M3 (wk 6):** policy gates + receipts on every action. *"It's governable."*
- **M4 (wk 8):** eval scorecard published; README claims measured. *"It's credible."*
- **M5 (wk 12):** P2P reconciliation demo + A2A guest-council demo. *"It's useful."*
- **M6 (wk 16):** first for-good flavor shipped. *"It's purposeful."*

---

## 5. Risks

| Risk | Mitigation |
|---|---|
| Dependency surgery breaks hidden imports | CI import-check matrix per extras group (WS-0.6) |
| Council eval results underwhelm vs claims | Publish honestly; tune deliberation; the *receipts/governance* story doesn't depend on it |
| Azure-profile drift while building local profile | Driver-interface tests run against both profiles (Azure mocked in CI) |
| Scope gravity (the repo's historical failure mode) | Milestone gates: no WS-5+ work before M3 |

---

## 6. Research Sources

- Kore.ai — [7 best agentic AI platforms in 2026](https://www.kore.ai/blog/7-best-agentic-ai-platforms)
- ERP Software Blog — [Agentic AI in ERP: Moving from Copilots to Autonomous Operations](https://erpsoftwareblog.com/2026/03/agentic-ai-in-erp-autonomous-operations/)
- McKinsey — [The end of ERP as we know it](https://www.mckinsey.com/capabilities/mckinsey-technology/our-insights/the-end-of-erp-as-we-know-it-five-ways-ai-is-disrupting-erp)
- Prolifics — [SAP Joule Agentic AI 2026](https://prolifics.com/usa/resource-center/blog/sap-joule-agentic-ai)
- Digital Applied — [AI Agent Protocol Ecosystem Map 2026 (MCP/A2A/ACP/UCP)](https://www.digitalapplied.com/blog/ai-agent-protocol-ecosystem-map-2026-mcp-a2a-acp-ucp)
- Zylos Research — [Agent Interoperability Protocols 2026](https://zylos.ai/research/2026-03-26-agent-interoperability-protocols-mcp-a2a-acp-convergence/)
- arXiv — [Survey of Agent Interoperability Protocols](https://arxiv.org/html/2505.02279v1)
- Microsoft — [Foundry Agent Service overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview), [Build 2026 agent announcements](https://devblogs.microsoft.com/foundry/agent-service-build2026/), [Agent Framework 1.0 GA](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/the-future-of-agentic-ai-inside-microsoft-agent-framework-1-0/4510698)
- LiveFlow — [Best AI-native ERP software 2026](https://liveflow.com/blog/the-best-ai-native-erp-software-a-guide-for-multi-entity-businesses); Numeric — [Rillet vs Campfire](https://www.numeric.io/blog/rillet-vs-campfire)
- Red Hat — [Architecting memory for AI agents](https://next.redhat.com/2026/06/01/from-context-to-dreams-architecting-memory-for-ai-agents/)
- OODA Loop — [Agentic AI governance under the EU AI Act in 2026](https://oodaloop.com/briefs/technology/agentic-ais-governance-challenges-under-the-eu-ai-act-in-2026/)
- TechPolicy.Press — [The EU AI Act is Not Ready for Agents](https://www.techpolicy.press/the-eu-ai-act-is-not-ready-for-agents/)
