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
