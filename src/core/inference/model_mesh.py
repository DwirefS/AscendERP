"""
Model Mesh v1 — capability-tiered, sensitivity-gated model routing.

Formalizes the "model spectrum" vision (docs/plans/FABLES_REVIEW_AND_ENHANCEMENTS.md
Part II-B): not every decision deserves a frontier model. The mesh registers
models across four tiers and routes each task to the *lowest tier that is
sufficient* for it, under hard governance rules.

Tiers (ordered — lower value = cheaper/faster/more deterministic):
    RULES        deterministic code: SPC rules, reorder-point formulas, schedulers
    SPECIALIZED  small task models: TabPFN-style tabular, TimesFM-style forecast,
                 function-calling small models for tool schemas
    LOCAL        self-hosted mid-size models (Ollama / OpenAI-compatible endpoint)
    FRONTIER     cloud judgment models for council reasoning and disposition

Routing algorithm (implemented in ModelMesh.route, documented here as the
contract; see ADR D-025):
    1. Capability match — a spec must advertise every capability the request
       needs; misses are recorded in the rejected list.
    2. Data-sensitivity gate (HARD RULE) — the request's sensitivity level must
       be in the spec's ``data_sensitivity_ok``. PII never routes to a spec
       without "pii" clearance, even if it is the only capable model: the
       decision comes back with ``chosen=None`` rather than leaking data.
    3. Latency filter — if ``latency_budget_ms`` is given, specs whose
       ``max_latency_ms`` exceeds it are rejected.
    4. Budget filter — if ``budget_usd`` is given, specs whose
       ``cost_per_1k_tokens`` exceeds it are rejected (unit assumption: the
       budget is per ~1k-token call; RULES tier is always free).
    5. Tier preference — survivors are ordered by the lowest-sufficient-tier
       principle: rules < specialized < local < frontier, EXCEPT when
       ``stakes == "critical"``: then tiers below LOCAL are rejected outright
       (judgment calls with real consequences do not go to lookup tables) and
       the ordering flips to prefer FRONTIER.
    6. Deterministic tie-break — within a tier, order by (cost, name) so the
       same mesh + request always yields the same decision.
    7. Availability — unavailable specs still flow through steps 1-6 and are
       only skipped at selection time with reason "unavailable", so the
       rejected list shows what WOULD have been chosen with the full mesh.

``route`` never raises on no-match: it returns a decision with ``chosen=None``
and the full rejected list, which is itself receipt-worthy evidence.

Governance: every RoutingDecision carries ``to_receipt_fragment()``; the
AgentHarness copies ``context.metadata["routing_decision"]`` into the
receipt's cost dict so the hash-chained audit trail records which model
decided what (src/core/harness/harness.py).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger()

STAKES_LEVELS = ("routine", "significant", "critical")
SENSITIVITY_LEVELS = ("public", "internal", "pii")


class ModelTier(IntEnum):
    """Capability tiers, ordered cheapest/most-deterministic first."""

    RULES = 0  # deterministic code — no model at all
    SPECIALIZED = 1  # small task models (tabular / time-series / tool-schema)
    LOCAL = 2  # self-hosted mid-size (Ollama / OpenAI-compatible)
    FRONTIER = 3  # cloud judgment models


@dataclass
class ModelSpec:
    """One routable model (or deterministic routine) in the mesh."""

    name: str
    tier: ModelTier
    capabilities: List[str]
    cost_per_1k_tokens: float  # 0.0 for RULES — code is free
    max_latency_ms: float
    data_sensitivity_ok: List[str]  # subset of SENSITIVITY_LEVELS
    endpoint: Optional[str] = None
    available: bool = True
    note: Optional[str] = None  # e.g. install instructions for placeholders


@dataclass
class RoutingRequest:
    """What a task needs from the mesh."""

    task_type: str
    capabilities_needed: List[str]
    stakes: str = "routine"  # routine | significant | critical
    data_sensitivity: str = "internal"  # public | internal | pii
    budget_usd: Optional[float] = None  # per-call budget (~1k tokens)
    latency_budget_ms: Optional[float] = None


@dataclass
class RoutingDecision:
    """Outcome of one routing pass — including everything that was rejected."""

    chosen: Optional[ModelSpec]
    tier: Optional[ModelTier]
    reason: str
    rejected: List[Tuple[str, str]] = field(default_factory=list)
    task_type: str = ""

    def to_receipt_fragment(self) -> Dict[str, object]:
        """Compact, JSON-safe dict for the harness receipt cost record."""
        return {
            "task_type": self.task_type,
            "model": self.chosen.name if self.chosen else None,
            "tier": self.tier.name.lower() if self.tier is not None else None,
            "reason": self.reason,
        }


class ModelMesh:
    """Registry + router over capability-tiered model specs.

    See the module docstring for the full routing algorithm; the short form:
    filter (capability → sensitivity → latency → budget), then choose the
    lowest sufficient tier — except critical stakes, which require >= LOCAL
    and prefer FRONTIER — with a deterministic (cost, name) tie-break.
    """

    def __init__(self) -> None:
        self._specs: Dict[str, ModelSpec] = {}

    def register(self, spec: ModelSpec) -> None:
        """Register (or replace) a model spec by name."""
        self._specs[spec.name] = spec
        logger.debug(
            "mesh_model_registered",
            name=spec.name,
            tier=spec.tier.name,
            available=spec.available,
        )

    def specs(self) -> List[ModelSpec]:
        """All registered specs (registration order)."""
        return list(self._specs.values())

    def route(self, request: RoutingRequest) -> RoutingDecision:
        """Route a request. Never raises on no-match — returns chosen=None."""
        rejected: List[Tuple[str, str]] = []
        candidates: List[ModelSpec] = []

        needed = set(request.capabilities_needed)
        critical = request.stakes == "critical"

        for spec in self._specs.values():
            # 1. capability match
            missing = needed - set(spec.capabilities)
            if missing:
                rejected.append(
                    (spec.name, f"missing capabilities: {', '.join(sorted(missing))}")
                )
                continue
            # 2. data-sensitivity gate (hard rule — especially PII)
            if request.data_sensitivity not in spec.data_sensitivity_ok:
                rejected.append(
                    (
                        spec.name,
                        f"not cleared for data_sensitivity={request.data_sensitivity}",
                    )
                )
                continue
            # 3. latency filter
            if (
                request.latency_budget_ms is not None
                and spec.max_latency_ms > request.latency_budget_ms
            ):
                rejected.append(
                    (
                        spec.name,
                        f"max_latency_ms {spec.max_latency_ms:g} exceeds "
                        f"budget {request.latency_budget_ms:g}",
                    )
                )
                continue
            # 4. budget filter (per ~1k-token call)
            if (
                request.budget_usd is not None
                and spec.cost_per_1k_tokens > request.budget_usd
            ):
                rejected.append(
                    (
                        spec.name,
                        f"cost_per_1k_tokens {spec.cost_per_1k_tokens:g} exceeds "
                        f"budget_usd {request.budget_usd:g}",
                    )
                )
                continue
            # 5. critical stakes: tiers below LOCAL are not eligible
            if critical and spec.tier < ModelTier.LOCAL:
                rejected.append(
                    (
                        spec.name,
                        f"stakes=critical requires tier >= LOCAL "
                        f"(spec is {spec.tier.name})",
                    )
                )
                continue
            candidates.append(spec)

        # 5b/6. tier preference + deterministic tie-break.
        # Routine/significant: lowest sufficient tier. Critical: highest tier
        # first (prefers FRONTIER). Ties broken by (cost, name).
        tier_key = (lambda s: -int(s.tier)) if critical else (lambda s: int(s.tier))
        candidates.sort(key=lambda s: (tier_key(s), s.cost_per_1k_tokens, s.name))

        # 7. availability — skipped only at selection time so the rejected
        # list shows what the full mesh would have chosen.
        chosen: Optional[ModelSpec] = None
        for spec in candidates:
            if not spec.available:
                reason = "unavailable"
                if spec.note:
                    reason += f" ({spec.note})"
                rejected.append((spec.name, reason))
                continue
            chosen = spec
            break

        if chosen is None:
            decision = RoutingDecision(
                chosen=None,
                tier=None,
                reason=f"no model satisfies request (rejected {len(rejected)})",
                rejected=rejected,
                task_type=request.task_type,
            )
            logger.warning(
                "mesh_route_no_match",
                task_type=request.task_type,
                rejected=len(rejected),
            )
            return decision

        preference = (
            "highest tier preferred (stakes=critical)"
            if critical
            else "lowest sufficient tier"
        )
        decision = RoutingDecision(
            chosen=chosen,
            tier=chosen.tier,
            reason=(
                f"{chosen.tier.name} tier satisfies "
                f"[{', '.join(sorted(needed)) or 'no capabilities'}] "
                f"at sensitivity={request.data_sensitivity}; {preference}"
            ),
            rejected=rejected,
            task_type=request.task_type,
        )
        logger.info(
            "mesh_routed",
            task_type=request.task_type,
            model=chosen.name,
            tier=chosen.tier.name,
        )
        return decision


def DEFAULT_MESH() -> ModelMesh:
    """Honest starter mesh: what runs today, plus placeholders for the
    specialized/local/frontier rungs gated on installation or env config.

    Env:
        ANTS_OLLAMA_URL       — enables the LOCAL tier (OpenAI-compatible URL)
        ANTS_FRONTIER_API_KEY — enables the FRONTIER tier (cloud judgment)
    """
    mesh = ModelMesh()
    # RULES — deterministic code already in the agents; free, fast, PII-safe.
    mesh.register(
        ModelSpec(
            name="spc_rules",
            tier=ModelTier.RULES,
            capabilities=["classify_control_chart"],
            cost_per_1k_tokens=0.0,
            max_latency_ms=10,
            data_sensitivity_ok=["public", "internal", "pii"],
        )
    )
    mesh.register(
        ModelSpec(
            name="reorder_rules",
            tier=ModelTier.RULES,
            capabilities=["reorder_point"],
            cost_per_1k_tokens=0.0,
            max_latency_ms=10,
            data_sensitivity_ok=["public", "internal", "pii"],
        )
    )
    # SPECIALIZED — placeholders until the small models are installed.
    mesh.register(
        ModelSpec(
            name="tabular_small",
            tier=ModelTier.SPECIALIZED,
            capabilities=["classify_tabular"],
            cost_per_1k_tokens=0.0,
            max_latency_ms=2_000,
            data_sensitivity_ok=["public", "internal", "pii"],
            available=False,
            note="install a TabPFN-style tabular foundation model",
        )
    )
    mesh.register(
        ModelSpec(
            name="timeseries_small",
            tier=ModelTier.SPECIALIZED,
            capabilities=["forecast"],
            cost_per_1k_tokens=0.0,
            max_latency_ms=2_000,
            data_sensitivity_ok=["public", "internal", "pii"],
            available=False,
            note="install a TimesFM-style time-series foundation model",
        )
    )
    # LOCAL — self-hosted mid-size; PII stays on-prem, so it is cleared.
    ollama_url = os.environ.get("ANTS_OLLAMA_URL")
    mesh.register(
        ModelSpec(
            name="ollama_local",
            tier=ModelTier.LOCAL,
            capabilities=["reasoning"],
            cost_per_1k_tokens=0.0,
            max_latency_ms=30_000,
            data_sensitivity_ok=["public", "internal", "pii"],
            endpoint=ollama_url,
            available=bool(ollama_url),
            note=None if ollama_url else "set ANTS_OLLAMA_URL to enable",
        )
    )
    # FRONTIER — cloud judgment; NOT PII-cleared by default (hard rule keeps
    # PII from leaving the local tier until a DPA/clearance flips this).
    frontier_key = os.environ.get("ANTS_FRONTIER_API_KEY")
    mesh.register(
        ModelSpec(
            name="frontier_cloud",
            tier=ModelTier.FRONTIER,
            capabilities=["reasoning", "judgment"],
            cost_per_1k_tokens=0.015,
            max_latency_ms=60_000,
            data_sensitivity_ok=["public", "internal"],
            available=bool(frontier_key),
            note=None if frontier_key else "set ANTS_FRONTIER_API_KEY to enable",
        )
    )
    return mesh
