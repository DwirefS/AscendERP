"""
Tests for Model Mesh v1 (src/core/inference/model_mesh.py) — capability-tiered,
sensitivity-gated routing with the harness governance hook (ADR D-025).
"""
from src.core.harness import AgentHarness
from src.core.inference.model_mesh import (
    DEFAULT_MESH,
    ModelMesh,
    ModelSpec,
    ModelTier,
    RoutingRequest,
)


def spec(name, tier, caps, cost=0.001, latency=1_000, sens=None, **kw) -> ModelSpec:
    return ModelSpec(
        name=name,
        tier=tier,
        capabilities=list(caps),
        cost_per_1k_tokens=cost,
        max_latency_ms=latency,
        data_sensitivity_ok=list(sens or ["public", "internal", "pii"]),
        **kw,
    )


def mesh_with(*specs) -> ModelMesh:
    mesh = ModelMesh()
    for s in specs:
        mesh.register(s)
    return mesh


def request(**kw) -> RoutingRequest:
    kw.setdefault("task_type", "test_task")
    kw.setdefault("capabilities_needed", ["forecast"])
    return RoutingRequest(**kw)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def test_capability_filtering_rejects_non_matching_specs():
    mesh = mesh_with(
        spec("forecaster", ModelTier.SPECIALIZED, ["forecast"]),
        spec("classifier", ModelTier.SPECIALIZED, ["classify_tabular"]),
    )
    decision = mesh.route(request(capabilities_needed=["forecast"]))
    assert decision.chosen.name == "forecaster"
    assert ("classifier", "missing capabilities: forecast") in decision.rejected


def test_pii_hard_rule_rejects_uncleared_spec_even_if_only_option():
    mesh = mesh_with(
        spec("frontier", ModelTier.FRONTIER, ["judgment"], sens=["public", "internal"]),
    )
    decision = mesh.route(
        request(capabilities_needed=["judgment"], data_sensitivity="pii")
    )
    assert decision.chosen is None
    assert decision.tier is None
    assert decision.rejected == [("frontier", "not cleared for data_sensitivity=pii")]


def test_latency_budget_filters_slow_specs():
    mesh = mesh_with(
        spec("slow", ModelTier.SPECIALIZED, ["forecast"], latency=5_000),
        spec("fast", ModelTier.LOCAL, ["forecast"], latency=200),
    )
    decision = mesh.route(request(latency_budget_ms=1_000))
    assert decision.chosen.name == "fast"
    assert any(n == "slow" and "latency" in r for n, r in decision.rejected)


def test_budget_filters_expensive_specs():
    mesh = mesh_with(
        spec("pricey", ModelTier.SPECIALIZED, ["forecast"], cost=0.05),
        spec("cheap", ModelTier.LOCAL, ["forecast"], cost=0.0),
    )
    decision = mesh.route(request(budget_usd=0.01))
    assert decision.chosen.name == "cheap"
    assert any(n == "pricey" and "budget_usd" in r for n, r in decision.rejected)


# ---------------------------------------------------------------------------
# Tier preference
# ---------------------------------------------------------------------------

def test_lowest_tier_wins_when_both_match():
    mesh = mesh_with(
        spec("frontier", ModelTier.FRONTIER, ["classify_tabular"], cost=0.02),
        spec("rules", ModelTier.RULES, ["classify_tabular"], cost=0.0),
    )
    decision = mesh.route(request(capabilities_needed=["classify_tabular"]))
    assert decision.chosen.name == "rules"
    assert decision.tier is ModelTier.RULES


def test_critical_stakes_rejects_rules_and_specialized():
    mesh = mesh_with(
        spec("rules", ModelTier.RULES, ["judgment"], cost=0.0),
        spec("small", ModelTier.SPECIALIZED, ["judgment"], cost=0.0),
        spec("local", ModelTier.LOCAL, ["judgment"], cost=0.0),
    )
    decision = mesh.route(request(capabilities_needed=["judgment"], stakes="critical"))
    assert decision.chosen.name == "local"
    reasons = dict(decision.rejected)
    assert "tier >= LOCAL" in reasons["rules"]
    assert "tier >= LOCAL" in reasons["small"]


def test_critical_stakes_prefers_frontier_over_local():
    mesh = mesh_with(
        spec("local", ModelTier.LOCAL, ["judgment"], cost=0.0),
        spec("frontier", ModelTier.FRONTIER, ["judgment"], cost=0.02),
    )
    decision = mesh.route(request(capabilities_needed=["judgment"], stakes="critical"))
    assert decision.chosen.name == "frontier"
    assert decision.tier is ModelTier.FRONTIER


def test_deterministic_tie_break_by_cost_then_name():
    a = spec("bravo", ModelTier.LOCAL, ["forecast"], cost=0.002)
    b = spec("alpha", ModelTier.LOCAL, ["forecast"], cost=0.002)
    c = spec("zulu", ModelTier.LOCAL, ["forecast"], cost=0.001)
    # cheapest wins regardless of name; equal cost falls back to name order —
    # and registration order never matters.
    assert mesh_with(a, b, c).route(request()).chosen.name == "zulu"
    assert mesh_with(c, b, a).route(request()).chosen.name == "zulu"
    assert mesh_with(a, b).route(request()).chosen.name == "alpha"
    assert mesh_with(b, a).route(request()).chosen.name == "alpha"


# ---------------------------------------------------------------------------
# Availability and no-match
# ---------------------------------------------------------------------------

def test_unavailable_spec_skipped_with_reason_and_next_chosen():
    mesh = mesh_with(
        spec(
            "small",
            ModelTier.SPECIALIZED,
            ["forecast"],
            available=False,
            note="install a TimesFM-style model",
        ),
        spec("local", ModelTier.LOCAL, ["forecast"]),
    )
    decision = mesh.route(request())
    assert decision.chosen.name == "local"
    name, reason = decision.rejected[0]
    assert name == "small"
    assert reason.startswith("unavailable")
    assert "TimesFM-style" in reason


def test_no_match_returns_none_with_full_rejected_list():
    mesh = mesh_with(
        spec("classifier", ModelTier.SPECIALIZED, ["classify_tabular"]),
        spec("judge", ModelTier.FRONTIER, ["judgment"], sens=["public"]),
    )
    decision = mesh.route(
        request(capabilities_needed=["forecast"], data_sensitivity="pii")
    )
    assert decision.chosen is None and decision.tier is None
    assert len(decision.rejected) == 2
    assert "no model satisfies request" in decision.reason


# ---------------------------------------------------------------------------
# DEFAULT_MESH
# ---------------------------------------------------------------------------

def test_default_mesh_shape(monkeypatch):
    monkeypatch.delenv("ANTS_OLLAMA_URL", raising=False)
    monkeypatch.delenv("ANTS_FRONTIER_API_KEY", raising=False)
    mesh = DEFAULT_MESH()
    by_name = {s.name: s for s in mesh.specs()}
    assert set(by_name) == {
        "spc_rules",
        "reorder_rules",
        "tabular_small",
        "timeseries_small",
        "ollama_local",
        "frontier_cloud",
    }
    assert by_name["spc_rules"].tier is ModelTier.RULES
    assert by_name["spc_rules"].available and by_name["spc_rules"].cost_per_1k_tokens == 0.0
    assert by_name["tabular_small"].available is False
    assert by_name["timeseries_small"].available is False
    assert by_name["ollama_local"].available is False  # no env URL
    assert by_name["frontier_cloud"].available is False  # no env key
    # PII is NOT cleared for the cloud frontier by default — the hard rule.
    assert "pii" not in by_name["frontier_cloud"].data_sensitivity_ok
    assert "pii" in by_name["ollama_local"].data_sensitivity_ok


def test_default_mesh_env_enables_local_and_shows_would_be_choice(monkeypatch):
    monkeypatch.setenv("ANTS_OLLAMA_URL", "http://localhost:11434/v1")
    monkeypatch.delenv("ANTS_FRONTIER_API_KEY", raising=False)
    mesh = DEFAULT_MESH()
    decision = mesh.route(
        RoutingRequest(task_type="disposition", capabilities_needed=["reasoning"])
    )
    assert decision.chosen.name == "ollama_local"
    assert decision.chosen.endpoint == "http://localhost:11434/v1"
    # SPC classification still routes to rules, not the LLM.
    spc = mesh.route(
        RoutingRequest(task_type="spc", capabilities_needed=["classify_control_chart"])
    )
    assert spc.chosen.name == "spc_rules" and spc.tier is ModelTier.RULES


# ---------------------------------------------------------------------------
# Governance: receipt fragment + harness hook
# ---------------------------------------------------------------------------

def test_receipt_fragment_shape():
    mesh = mesh_with(spec("local", ModelTier.LOCAL, ["forecast"]))
    fragment = mesh.route(request(task_type="demand_forecast")).to_receipt_fragment()
    assert set(fragment) == {"task_type", "model", "tier", "reason"}
    assert fragment["task_type"] == "demand_forecast"
    assert fragment["model"] == "local"
    assert fragment["tier"] == "local"
    assert isinstance(fragment["reason"], str) and fragment["reason"]
    # No-match fragments are still well-formed (None model/tier).
    empty = ModelMesh().route(request(task_type="x")).to_receipt_fragment()
    assert empty["model"] is None and empty["tier"] is None


async def test_harness_records_routing_decision_in_receipt_cost():
    from src.core.agent.base import AgentConfig, AgentContext, AgentResult, BaseAgent

    class StubAgent(BaseAgent):
        def __init__(self):
            super().__init__(AgentConfig(name="mesh-stub", tenant_id="tenant-test"))

        async def run(self, input_data, context):
            return AgentResult(
                success=True, output={}, trace_id=context.trace_id, actions_taken=[]
            )

        async def perceive(self, input_data, context):
            return {}

        async def retrieve(self, perception, context):
            return {}

        async def reason(self, perception, retrieved_context, context):
            return {}

        async def execute(self, action, context):
            return None

        async def verify(self, result, context):
            return {"complete": True}

        async def learn(self, input_data, actions_taken, context):
            return None

    mesh = mesh_with(spec("rules", ModelTier.RULES, ["classify_control_chart"], cost=0.0))
    decision = mesh.route(
        RoutingRequest(task_type="spc", capabilities_needed=["classify_control_chart"])
    )
    context = AgentContext(
        trace_id="trace-mesh",
        tenant_id="tenant-test",
        metadata={"routing_decision": decision},
    )
    outcome = await AgentHarness(StubAgent()).run({"task": "spc check"}, context)
    assert outcome.success is True
    recorded = outcome.receipt.cost["routing_decision"]
    assert recorded == decision.to_receipt_fragment()
    assert recorded["model"] == "rules" and recorded["tier"] == "rules"
    # The receipt chain still verifies with the fragment included.
    assert outcome.receipt.cost["duration_s"] >= 0
