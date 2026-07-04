# ANTS Decision Log

Append-only record of significant decisions: what was decided, why, what the
alternatives were, and what changed. Newest entries at the bottom. Format is a
lightweight ADR (Architecture Decision Record).

Companion documents:
- [`docs/plans/MASTER_ENHANCEMENT_PLAN.md`](../plans/MASTER_ENHANCEMENT_PLAN.md) — the overall plan
- `docs/plans/SESSION_2026-06-12_WORKLOG.md` — blow-by-blow work record for this session

---

## D-001 — Plan-first, local-first strategy for "get it working"

**Date:** 2026-06-12 · **Status:** Accepted

**Context.** Fresh-eyes review (3 parallel audits: code map, docs/vision summary,
empirical buildability audit) found ~70–75% of the system genuinely implemented but
**zero working end-to-end path**: the package could not even be pip-installed safely,
pytest crashed inside itself, and the API gateway could not start.

**Decision.** Prioritize a no-Azure local boot path (clone → install → run → smoke
test) before any feature work. Azure remains the production profile; local is the
demo/dev/CI profile.

**Why.** Every stakeholder journey (contributor, evaluator, customer demo) dies at
step 1 today. The most distinctive features (councils, swarm) cannot be shown to
anyone without a cloud subscription. Competitors (Rillet, Campfire) win on "it
works"; the way to make this repo's ambition credible is a 15-minute quickstart.

**Alternatives considered.** (a) Fix only the Azure deployment path — rejected:
requires subscription, slow iteration, doesn't help CI. (b) Keep building features —
rejected: compounds the connective-tissue debt that is the actual problem.

---

## D-002 — Rename `platform/` → `ants_platform/` and `mcp/` → `ants_mcp/`

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** Top-level `platform/` shadowed the Python **stdlib** `platform` module
whenever the repo root was on `sys.path` (which `pytest.ini` requires). Verified
effects: `python -m pytest` crashed inside pytest (`uuid.py` →
`AttributeError: module 'platform' has no attribute 'system'`); even
`from fastapi import FastAPI` failed (pydantic imports `platform` internally); the
built wheel would poison any environment that installed it; the `antsctl` console
script was unimportable. Likewise `mcp/` shadowed the PyPI **`mcp` SDK**, making
`from mcp.server import Server` in our own MCP servers unresolvable — the
docker-compose MCP services crashed at startup.

**Decision.** `git mv platform ants_platform`, `git mv mcp ants_mcp`; update
`pyproject.toml` (hatch packages, `antsctl` entry point), all imports, and
docker-compose commands.

**Why.** Nothing in the repo was reliably runnable until this landed. Shadowing the
stdlib is not fixable by configuration; the only correct fix is the rename.

**Alternatives considered.** (a) Run everything from outside the repo root —
unworkable for contributors and CI. (b) src-layout repackaging (`src/ants/...`) —
better long-term but far more invasive; deferred to WS-1 (one-spine refactor) as an
option, not required now.

---

## D-003 — Dependency surgery: minimal core + optional extras

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** The default dependency set bundled torch, transformers, tritonclient,
nemo-guardrails, LangChain, AutoGen, CrewAI, Milvus, Weaviate and the full Azure SDK
— a fragile, multi-GB install for a system whose core (FastAPI gateway + PRREEL
agents + Postgres memory) needs none of them. Six dependencies that the code
*actually imports* were missing entirely: `openai`, `aiofiles`, `jsonschema`,
`pyjwt`, `cryptography`, `mcp`.

**Decision.** `[project.dependencies]` is now the minimal local-profile core
(~2 min install). Heavy/cloud stacks moved to extras: `[azure]`, `[frameworks]`,
`[ml]`, `[nvidia]`, `[vector]`, `[policy]`, `[mcp]`, `[spark]`, `[databricks]`,
`[rapids]`. Missing real dependencies added to core. Root `requirements.txt` created
(CI referenced it but it didn't exist) as a thin `-e .` pointer.

**Why.** Install reliability is the gate to everything else; optional capability
should cost nothing until used. This also forces honest accounting of what each
module really needs.

**Consequence.** Modules importing extras must degrade gracefully (see D-005) and
tests for extra-dependent features skip with an instructive reason when the extra is
absent.

---

## D-004 — Resolve the `observability.py` vs `observability/` package collision

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** `src/core/observability.py` (tracer, metrics instruments,
`trace_agent_execution`, `trace_llm_call`, OTel provider setup) was silently
**shadowed** by the `src/core/observability/` package, so 10+ consumer modules
(`llm_client`, all selfops agents, all Azure integrations, streaming API) failed at
import: the names existed in the shadowed file but not in the package. This single
collision broke 4 of 11 test modules.

**Decision.** Moved the module into the package as
`src/core/observability/otel.py`; the package `__init__.py` re-exports both the OTel
helpers and the existing `TracingClient`/`MetricsClient`. Top-level imports of
*optional* instrumentation (`system_metrics`, `logging`) moved inside
`enable_instrumentation()` with try/except, matching the lazy pattern the file
already used for httpx/requests instrumentation.

**Alternatives.** Deleting one of the two implementations — premature; both are
consumed. Full observability consolidation is WS-1.3.

---

## D-005 — Optional-dependency failures become skips/log-warnings, not crashes

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented (partially, ongoing)**

**Decision.** (a) Test modules requiring optional extras use
`pytest.importorskip(..., reason="pip install 'ants[<extra>]'")` — applied to
pyspark-based pipeline/e2e tests and Azure AI Foundry connector tests. (b) Library
modules importing optional packages at module scope must either lazy-import or guard
with try/except and a warning.

**Why.** A contributor with the core install must get a green test run with
informative skips, not a wall of ImportErrors.

---

## D-006 — Gateway hardening defaults: env-based JWT secret, `jti` claims, per-credential rate limiting

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** `services/api_gateway/auth.py` shipped a hardcoded JWT secret
(`"your-secret-key-change-in-production"`). The rate limiter had no simple
per-client interface. Missing-credential requests returned 403 (HTTPBearer default)
instead of 401.

**Decision.**
1. JWT secret comes from `ANTS_JWT_SECRET`; if unset, generate a random
   **per-process** secret and log a warning — tokens then never validate across
   restarts/replicas, which is safe-by-default for dev and impossible to ship to
   prod accidentally.
2. Every issued JWT carries a unique `jti` (token id) — enables revocation lists,
   audit correlation, and per-session rate limiting.
3. Rate limiting at the gateway is keyed per credential (tenant + hash of the
   presented token/key) — one runaway session cannot starve a tenant's other
   sessions. Aggregate per-tenant limits belong to the Redis-backed limiter in the
   production profile (WS-2.4).
4. `HTTPBearer(auto_error=False)` so unauthenticated requests get a proper 401, and
   scope checks return 403 — authn and authz failures are now distinguishable.
5. `AuthService` became configurable (`jwt_secret`, `jwt_algorithm`,
   `token_expiry_hours`) with a documented `AuthService.current` process-wide
   resolution point, plus `create_api_key()` (returns raw key once; stores SHA256).
6. Wildcard scopes: `admin:*` grants everything; `agents:*` grants `agents:read`
   etc.

---

## D-007 — Agent-framework strategy: own PRREEL core; consolidate external frameworks behind extras (target: Microsoft Agent Framework for orchestration)

**Date:** 2026-06-12 · **Status:** Proposed (direction accepted; migration is WS-7.3)

**Context.** The repo simultaneously depended on LangChain, LangGraph, AutoGen,
CrewAI, and Semantic Kernel while implementing its own PRREEL cognitive loop —
five overlapping orchestration stacks. Microsoft Agent Framework 1.0 went GA
(April 2026) and unifies SK + AutoGen; Foundry Agent Service is now wire-compatible
with the OpenAI Responses API.

**Decision.** The PRREEL loop + councils + swarm remain ANTS's own core (they are
the differentiation). External frameworks are demoted to the optional
`[frameworks]` extra; the strategic integration target for hosted orchestration is
Microsoft Agent Framework / Foundry Agent Service in the Azure profile. MCP is the
tool protocol; A2A is the planned agent-interop protocol (WS-7.1).

---

## D-008 — The API gateway integration tests are the contract; implementation was brought up to them

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** `tests/integration/test_api_gateway.py` (27 tests) described a richer
gateway than `main.py` implemented: `/api/v1/agents` (GET requires `agents:read`,
POST requires `agents:write`), `/api/v1/tasks` (`tasks:submit`), `/metrics` (admin),
configurable AuthService, API keys, tenant isolation, 429 under burst, 422
validation. The implementation had placeholder routing and could not start.

**Decision.** Treat those tests as the API spec. The gateway now: builds a real
`AgentRegistry` at startup (finance.reconciliation, retail.inventory), serves the
`/api/v1` resource API with scope enforcement and per-credential rate limits, and
`/v1/agents/invoke` executes the **real PRREEL loop** via the registry (agents fall
back to deterministic logic when no LLM/memory is configured — so invocation works
in the local profile out of the box). Eager state init (not lifespan-only) so test
clients without startup events work. Result: 27/27 passing.

**Rejected alternative.** Rewriting the tests to match the placeholder — would have
ratified the missing connective tissue instead of building it.

---

## D-009 — `tests/integration/test_agent_framework.py` rewritten against real interfaces

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** Unlike the gateway tests (D-008), this module tested an API that
*never existed and contradicts the working design*: direct instantiation of the
abstract `BaseAgent`, nonexistent `AgentState.INITIALIZED/ACTIVE/IDLE/SLEEPING`
values, `AgentMetadata(agent_id=...)`, `MemorySubstrate(db_client=...)`. The real
core (registry, DatabaseClient/DatabaseConfig, PRREEL agents, SwarmOrchestrator) is
implemented and used by everything else.

**Decision.** Where tests describe a *missing implementation*, build the
implementation (D-008). Where tests describe a *contradictory parallel design*,
rewrite the tests against the real one. Small real API gaps surfaced by the tests
were filled in source: `DatabaseConfig` dataclass + `DatabaseClient` accepting
config-or-string + `disconnect()` alias; `AgentStatus = AgentHealthStatus` alias;
`LLMClient = BaseLLMClient` alias; `reason()` made defensive with the same defaults
`perceive()` applies (fixed a real KeyError bug).

---

## D-010 — Local test infrastructure: real PostgreSQL 16 + pgvector, not mocks

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Decision.** Memory-substrate integration tests run against a real
Postgres+pgvector (`ants_test`/`test_user`), provisioned in dev by
`docker-compose.dev.yml` (image `pgvector/pgvector:pg16`) and in CI by a service
container; tests skip (not fail) when the DB is unreachable.

**Why.** The memory substrate's SQL/IVFFlat/vector-search code is the heart of the
platform; mocking the DB would test nothing real. pgvector in a container is cheap.

---

## D-011 — CI must be honest: test what exists, build what exists, no fictional deploy stages

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** `.github/workflows/ci-cd.yml` failed at step 1 (installed a
`requirements.txt` that didn't exist), used Python 3.10 against
`requires-python >=3.11`, built Dockerfiles in a nonexistent `docker/` tree,
deployed nonexistent Helm charts with nonexistent values files, and ran smoke
suites in directories that don't exist.

**Decision.** Replace with two real jobs: (1) lint (advisory) + full pytest against
a pgvector service container on Python 3.11; (2) docker build of the fixed root
Dockerfile (no push). Deploy/helm stages return only when the charts they reference
exist and are validated (WS-9).

---

## D-012 — Documentation policy: claims must be measured or labeled

**Date:** 2026-06-12 · **Status:** Accepted (execution is WS-3/WS-4)

**Decision.** README/business metrics (95% invoice-time reduction, 99% fraud
detection, 90.1% council accuracy, 20–130x velocity) move to clearly-labeled
*hypotheses* in the whitepaper until the WS-3 evaluation harness produces measured
numbers, which then become the published claims — whatever they turn out to be.

**Why.** In a market with funded, shipping competitors, unverifiable claims cost
more credibility than honest "here's what we measured" numbers buy.

---

## D-013 — structlog is the logging standard for agent code

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** The selfops agents used stdlib `logging` with structlog-style
keyword arguments (`logger.warning("msg", threats=...)`), which raises
`TypeError` at runtime — meaning several "implemented" code paths could never
have executed successfully.

**Decision.** All agent/platform code logs via `structlog` (the rest of the
codebase already did). Fixed in dataops/secops/agentops agents.

---

## D-014 — `reason()` returns a dict-shaped `action`; agents must honor the BaseAgent PRREEL contract

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** `BaseAgent.run` passes `reasoning["action"]` into `execute()`,
which reads it with `.get()`. DataOps/SecOps/AgentOps returned bare strings,
crashing every full execution (`'str' object has no attribute 'get'`).
ReconciliationAgent already used the dict convention.

**Decision.** The PRREEL contract is: `reason()` → `{"action": {<dict>},
"confidence": float, ...}`. All agents now conform; the rewritten framework
integration tests enforce it end-to-end.

---

## D-015 — ENCRYPTION_MASTER_KEY accepts base64-32-bytes or any passphrase

**Date:** 2026-06-12 · **Status:** Accepted · **Implemented**

**Context.** `EncryptionHelper` crashed unless the env var was exactly
base64-encoded 32 bytes — hostile to local dev and undocumented.

**Decision.** If the value decodes to exactly 32 bytes of base64 it is used
directly; otherwise a 32-byte key is derived via SHA-256 of the raw string.
Production guidance remains: provision a proper random key from Key Vault.

---

## D-016 — Manufacturing is the next flavor, built as an importable package with root-collected tests

**Date:** 2026-06-12 · **Status:** Accepted

**Context.** User directive: end-to-end AI-agent-native ERP for manufacturing.
The capital-markets flavor is the proven template, but its hyphenated directory
(`flavors/capital-markets/`) makes it un-importable — its own tests import
`flavors.capital_markets`, which cannot resolve, so they are silently never run.

**Decision.** `flavors/manufacturing/` (underscore-safe, importable), shared
domain contract in `flavors/manufacturing/models.py`, tests under
`tests/flavors/manufacturing/` so the root suite collects them. Migrating
capital-markets to the same convention is follow-up work.

---

## D-017 — AutoOptimize loops: Karpathy-autoresearch pattern applied to scheduling policy

**Date:** 2026-06-12 · **Status:** Accepted

**Context.** [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
(Mar 2026, 66k+ stars) demonstrated a minimal, powerful pattern: agent proposes a
change → runs a short, measurable experiment → keeps it if the objective improves,
rolls back otherwise → journals everything.

**Decision.** Apply the loop to a **parameterized SchedulingPolicy** (dispatch
rule + tunables), evaluated on a deterministic seeded plant simulator with a
weighted OTD/OEE/cost objective. Every step (accepted or rolled back) is a
journaled `OptimizationStep`. The policy — not code — is the mutation target:
safe, bounded, explainable, and auditable, unlike letting an agent edit source in
production.

---

## D-018 — Swarm scenario engine: MiroFish pattern as decision evidence, not oracle

**Date:** 2026-06-12 · **Status:** Accepted

**Context.** [MiroFish](https://github.com/666ghj/MiroFish) builds a "digital
world" of persona agents with memory/relations from seed documents and watches
emergent behavior to produce prediction reports.

**Decision.** `SwarmWorld` models the plant's *ecosystem* (suppliers, machines,
operators, customers as persona agents) and runs shock scenarios
(supplier outage, demand spike, machine failure, price spike). The resulting
`ScenarioReport` (timeline, KPI impact, risks, recommendations, confidence) is
**deliberation evidence for councils** — the S&OP council consumes it before
deciding; it never auto-executes. Deterministic per scenario seed so reports are
reproducible and testable.

---

## D-019 — Generic Agent Skills + AgentHarness live in src/core, not the flavor

**Date:** 2026-06-12 · **Status:** Accepted

**Decision.** `src/core/skills/` (SKILL.md packs: YAML frontmatter + procedure
body; registry with trigger matching and prompt rendering) and
`src/core/harness/` (budgets, pre/post policy gates with
ALLOW/DENY/REQUIRE_APPROVAL, hash-chained receipts, HITL approval queue, replayable
outcomes, Prometheus counters) are **platform capabilities** — manufacturing is
the first consumer, every flavor benefits. This begins WS-2 (governance) with real
running code instead of empty `ants_platform/receipts/` scaffolding.

**Why skills as markdown:** versionable, reviewable, hot-loadable expertise that
works with any model — the emerging cross-vendor convention for packaged agent
procedures.

---

## D-020 — deepagents integration is an optional adapter behind the `[deep]` extra

**Date:** 2026-06-12 · **Status:** Accepted

**Context.** [LangChain deepagents](https://github.com/langchain-ai/deepagents)
(the "batteries-included agent harness": planning todos, sub-agents, virtual FS,
middleware) is valuable but pulls the LangChain stack into the dependency tree.

**Decision.** ANTS's own harness provides the local-profile primitives; a thin
adapter exposes manufacturing missions as deepagents-driven plans when
`pip install "ants[deep]"` is present, and degrades gracefully (clear message,
native harness path) when not. Keeps the default install lean (D-003) and the
platform fully open-source-runnable either way.

---

## D-021 — The carve begins: ideas sorted into verdict tiers, no deletions

**Date:** 2026-07-03 · **Status:** Accepted

**Context.** The author's "bulk-up phase" doctrine (README, whitepaper_addition
§23.6) deliberately maximized idea mass and deferred pruning. A full-corpus
read (all whitepapers, README, swarm design, Edition 3 — ~13K doc lines)
produced a complete idea inventory and an honest audit.

**Decision.** `docs/plans/PHILOSOPHY_TO_REALITY.md` is the canonical sorting of
every idea into six tiers: KEEP & AMPLIFY / MARKET-PROVEN / REAL-NEEDS-EVIDENCE
/ BEAUTIFUL-NOT-YET-REAL / RESHAPE / QUARANTINE. Consistent with the
no-deletions doctrine, nothing is removed — speculative essays move to a
labeled home (`docs/essays/`, future WS-4), projected metrics move to
hypothesis status pending the WS-3 eval harness, and internal tensions get one
canonical resolution each ("bounded emergence"; coexistence→elimination as
sequence; meta-agents for the long tail + catalogs for the head; open core
anywhere + vendor stack as production profile; positive-framing doctrine scoped
to vision docs only).

**Why.** The bulk-up phase succeeded at its own goal (no idea was lost) and
had reached its failure mode (the repo could not run, and unverifiable claims
were costing credibility). The carve preserves the philosophy while making it
measurable and shippable.

---

## D-022 — Council deliberation upgraded to evidence-weighted reasoning after WS-3 measurement

**Date:** 2026-07-04 · **Status:** Accepted

**Context.** The WS-3 evidence engine measured the QualityCouncil at **0.6667**
vs the solo QualityAgent's **0.9167** on the 12-case NCR disposition rubric —
the council *lost* its own headline A/B test. Root cause: `decide()` read a
fixed severity→disposition lookup table (`minor → USE_AS_IS`, `major →
REWORK`) that ignored the actual evidence on the NCR. It shipped defective
minor-NCR units as USE_AS_IS (d02, d03, d11) and reworked an uneconomical
major lot where rework cost exceeded unit value (d06 — a case the solo agent
also missed, since neither subject considered rework economics).

**Decision.** `QualityCouncil.decide()` now deliberates by weighing real
evidence per member instead of reading the table:
- **Quality engineer:** any defective units carrying a spec violation
  (`quantity_affected > 0`) can never ship as USE_AS_IS; a minor NCR with
  zero defective units is a control signal from a capable process.
- **Manufacturing engineer (economics):** when `rework_cost_per_unit` and
  `unit_value` are both known, REWORK only while economical
  (`rework_cost_per_unit < unit_value`), otherwise SCRAP.
- **Compliance officer (unchanged):** critical → SCRAP (RETURN_TO_SUPPLIER
  when supplier material) with `requires_human_approval=True`;
  supplier-related major/critical goes back to the supplier.
Resolution order: binding compliance positions → quality's
conforming-product evidence → economics → default containment (REWORK).
The member positions and reasons travel in the decision
(`member_assessments`) and the rationale. `decide()` stays
backward-compatible: the new `rework_cost_per_unit`/`unit_value` kwargs
default to None, and with economics unknown the behavior for existing
callers is unchanged — all pre-existing council tests pass unmodified.
For a fair fight, `QualityAgent._recommend_disposition` reads the same two
optional economics fields (defaulting to None ⇒ original behavior), and the
eval passes each case's full inputs to **both** subjects. Rubric and
expected answers untouched.

**Measured (seed 42, deterministic).** Solo vs council on the same 12 cases:
council **0.6667 → 1.0000** (d02/d03/d06/d11 fixed), solo **0.9167 →
1.0000** (d06 fixed via the shared economics fields). The council no longer
loses — it ties the upgraded solo agent at 1.0 on this rubric; the remaining
separation must come from cases where deliberation beats a single policy
(conflicting evidence, incomplete inputs), which is the next eval to write.
Full suite green after the change.

---

## D-023 — Durable receipts: Postgres sink behind the hash chain, availability over durability

**Date:** 2026-07-04 · **Status:** Accepted

**Context.** Backlog item 6 (FABLES_REVIEW Part IV): the hash-chained
receipt chain — the governance spine of the harness — lived only in process
memory, so a restart erased the audit trail the whole "prove your agent did
what you claim" pitch rests on. `audit.receipts` already existed in the
episodic schema (`DatabaseClient.initialize_schemas` /
`insert_receipt`), but predates the chained format: it computes its own hash
and stores neither `prev_hash` nor the chain fields, so it cannot round-trip
a verifiable chain.

**Decision.** `src/core/harness/receipts.py` gains `PostgresReceiptSink`:
`ensure_schema()` extends `audit.receipts` with
`ALTER TABLE ... ADD COLUMN IF NOT EXISTS` for the chain fields (`receipt_id`,
`prev_hash`, `agent_type`, `inputs_hash`, `actions`/`policy_decisions`/
`skills_used`/`cost` JSONB, `receipt_created_at`), so legacy
`insert_receipt` rows and chained receipts coexist in one audit table (legacy
rows have `receipt_id IS NULL` and are excluded from chain loads).
`ReceiptChain(sink=...)` schedules `sink.store(receipt)` on every append as a
background task, serialized in append order and wrapped in try/except +
structlog warning. This is a deliberate **availability-over-durability**
choice: a database outage degrades the audit trail to in-memory but never
blocks or fails an agent run. `ReceiptChain.load_from_sink(db, tenant_id)`
restores a tenant's chain and raises `ValueError` when `verify()` fails —
tampering with stored receipts is detected at load. Mission Control's
`ensure_governance` wires the sink best-effort (`ANTS_DATABASE_URL` or
default local Postgres, 3s timeout, one attempt, backfill of pre-sink
receipts) and degrades silently — Mission Control keeps working without a DB.

**Why.** Durable, tamper-evident receipts convert the EU-AI-Act-era
governance pitch from demo to artifact — and the fire-and-forget contract
keeps the harness honest about which failure mode it prefers: losing a
receipt's durability beats halting production agents. 6 live-DB tests
(`tests/unit/memory/test_receipt_sink.py`, entropy-style skip when Postgres
is down) cover round-trip + verify, tamper detection, tenant isolation,
legacy coexistence, and append-through-dead-sink.

---

## D-024 — README truth pass: three-tier status, hypotheses labeled, credibility section

**Date:** 2026-07-04 · **Status:** Accepted

**Context.** Backlog item 10; PHILOSOPHY_TO_REALITY §3.5–3.6 and D-012.
The README led with "Implementation Status: 75% Complete (Production-Ready
Core)" while its own disclaimer said "not production-ready software," and
presented modeled projections (99.999% savings, 87%/67% cost reductions,
"90%+ accuracy", "proven 20-30% improvement") in observed-result voice —
the audit called this the single largest credibility liability.

**Decision.** The status block became an honest three-tier section —
**Working & verified** (270 tests, green CI, live demos) / **Implemented,
evidence pending** / **Vision (whitepaper)** — plus a "Predicted 2025 →
Confirmed 2026" section (MCP/A2A won; agents-as-app-layer per Gartner;
governance-first per the EU AI Act; memory-as-moat). Every projection-in-
results-voice was reframed as a hypothesis the evidence engine will test,
pointing at `eval_reports/manufacturing_scorecard.md` for the numbers we can
stand behind; "Real-World Examples" became "Illustrative Examples"; the
"Cost Impact Summary" became "Cost Impact Hypotheses" with a D-012 label.
No vision content was deleted — it was retiered. `docs/essays/README.md`
establishes the labeled-speculation tier's home (D-021); moving whitepaper
sections into it stays the author's call.

**Why.** A measured 1.0 on an 11-task SPC rubric is worth more to a
skeptical CTO than an unmeasured 2,000% ROI. The README is the engineering
claims path, and D-012 applies to it with full force; the vision keeps its
place — one tier down, correctly labeled.

---

## D-025 — Model Mesh v1 — capability-tiered, sensitivity-gated model routing

**Date:** 2026-07-04 · **Status:** Accepted

**Context.** The author's model-spectrum vision (FABLES_REVIEW Part II-B):
not every decision deserves a frontier model. The 2026 specialized-model
landscape made the middle rungs real — Nemotron-3-Nano-class self-hostable
MoE models for the lightweight-agent tier, TabPFN-style tabular foundation
models, TimesFM-style time-series forecasters, function-calling small models
for tool schemas — while deterministic code (SPC rules, reorder-point
formulas) remains the correct "model" for a large share of ERP decisions.
The existing `model_router.py` scores LLMs against LLMs; it has no notion of
the rules tier, of data sensitivity, or of stakes, and its decisions leave no
trace in the governance receipts.

**Decision.** `src/core/inference/model_mesh.py` adds a four-tier mesh
(RULES < SPECIALIZED < LOCAL < FRONTIER) with a documented routing
algorithm: filter by capability match → data-sensitivity gate → latency →
budget, then choose by the **lowest-sufficient-tier principle** with a
deterministic (cost, name) tie-break. Two governance rules are hard:
1. **PII never routes to a spec lacking "pii" clearance** — even when it is
   the only capable model, `route()` returns `chosen=None` (with the full
   rejected list) rather than leaking data; the default `frontier_cloud`
   spec is deliberately NOT PII-cleared, while local/rules tiers are.
2. **Critical stakes escalate**: `stakes=="critical"` rejects tiers below
   LOCAL and inverts the preference to favor FRONTIER — judgment calls with
   real consequences do not go to lookup tables.
`route()` never raises on no-match, and unavailable specs (uninstalled small
models, unset `ANTS_OLLAMA_URL`/`ANTS_FRONTIER_API_KEY`) still flow through
the filters and are skipped only at selection time with reason
"unavailable", so every decision shows what the full mesh would have chosen.
Decisions carry `to_receipt_fragment()`, and the AgentHarness copies
`context.metadata["routing_decision"]` into the receipt's cost dict — the
hash-chained audit trail now records which model decided what.
`DEFAULT_MESH()` registers an honest starter set: two live RULES specs
(spc_rules, reorder_rules), two placeholder SPECIALIZED specs
(tabular_small, timeseries_small — available=False until installed), and
env-gated LOCAL/FRONTIER specs. 14 unit tests
(`tests/unit/inference/test_model_mesh.py`); full suite green.
