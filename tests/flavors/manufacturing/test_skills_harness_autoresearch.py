"""
Tests for the Agent Skills system, the core AgentHarness, and the
manufacturing AutoOptimize loop.

Uses stub agents / simulators implementing the design contracts
(docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.2-3.3, §3.5-3.6) so these
tests do not depend on the real PlantSimulator/PolicyScheduler.
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.core.agent.base import AgentConfig, AgentContext, AgentResult, BaseAgent
from src.core.harness import (
    AgentHarness,
    AllowedActionTypesPolicy,
    ApprovalQueue,
    ApprovalStatus,
    Budget,
    PolicyDecision,
    Receipt,
    ReceiptChain,
    ThresholdPolicy,
)
from src.core.skills import Skill, SkillRegistry
from flavors.manufacturing.autoresearch import AutoOptimizeLoop
from flavors.manufacturing.models import (
    KPISnapshot,
    Machine,
    OptimizationStep,
    Product,
    ProductionSchedule,
    SchedulingPolicy,
    SimulationResult,
    WorkOrder,
)

SKILLS_DIR = Path(__file__).resolve().parents[3] / "flavors" / "manufacturing" / "skills"

SAMPLE_SKILL_MD = """---
name: test-skill
version: 2.1.0
domain: manufacturing
description: A test skill.
triggers:
  - widget calibration
  - frobnicate
tools:
  - widget_tool
---
# Test Skill

Step 1: frobnicate the widget.
Step 2: verify calibration.
"""


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

class StubAgent(BaseAgent):
    """Minimal BaseAgent subclass; run() short-circuits the PRREEL loop."""

    def __init__(self, actions=None, delay: float = 0.0, succeed: bool = True):
        super().__init__(AgentConfig(name="stub-agent", tenant_id="tenant-test"))
        self._actions = list(actions or [])
        self._delay = delay
        self._succeed = succeed
        self.run_count = 0
        self.last_context = None

    async def run(self, input_data, context):
        self.run_count += 1
        self.last_context = context
        if self._delay:
            await asyncio.sleep(self._delay)
        return AgentResult(
            success=self._succeed,
            output={"echo": input_data},
            trace_id=context.trace_id,
            actions_taken=list(self._actions),
            tokens_used=7,
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


class StubScheduler:
    """Implements the PolicyScheduler contract; tags the schedule with its policy."""

    def __init__(self, policy: SchedulingPolicy):
        self.policy = policy

    def build_schedule(self, work_orders, machines, products=None) -> ProductionSchedule:
        schedule = ProductionSchedule(policy_name=self.policy.dispatch_rule)
        schedule._policy = self.policy  # contract stub: carry policy to the simulator
        return schedule


class StubSimulator:
    """Deterministic pure-function-of-policy simulator (PlantSimulator contract)."""

    RULE_OTD = {"EDD": 0.85, "CR": 0.88, "SPT": 0.78, "WSPT": 0.82, "FIFO": 0.70}

    def run(self, schedule, horizon_hours: float, replications: int = 1) -> SimulationResult:
        p: SchedulingPolicy = schedule._policy
        otd = self.RULE_OTD[p.dispatch_rule] - 0.05 * abs(p.batch_size_factor - 1.0)
        oee = (
            0.60
            + 0.10 * min(p.maintenance_buffer_hours, 24.0) / 24.0
            + 0.05 * (1.0 - min(abs(p.expedite_threshold - 0.8), 1.0))
        )
        cost = 1000.0 * (
            1.0
            + 0.10 * abs(p.queue_weight_due - 1.5)
            + 0.05 * p.queue_weight_setup
        )
        kpis = KPISnapshot(
            otd_rate=max(0.0, min(otd, 1.0)),
            oee=max(0.0, min(oee, 1.0)),
            total_cost=cost,
            throughput_units=20.0,
            makespan_hours=horizon_hours / 2,
        )
        return SimulationResult(
            kpis=kpis, replications=replications, horizon_hours=horizon_hours
        )


def make_loop(seed: int = 42, journal_path=None) -> AutoOptimizeLoop:
    products = [Product(product_id="P-1", name="Widget", standard_cost=60.0)]
    work_orders = [
        WorkOrder.new("P-1", 10, datetime(2026, 6, 20) + timedelta(days=i))
        for i in range(2)
    ]
    machines = [Machine(machine_id="M-1", name="Mill", work_center="WC-1")]
    return AutoOptimizeLoop(
        simulator_factory=StubSimulator,
        scheduler_factory=StubScheduler,
        work_orders=work_orders,
        machines=machines,
        products=products,
        seed=seed,
        journal_path=journal_path,
    )


def make_context(**metadata) -> AgentContext:
    return AgentContext(trace_id="trace-1", tenant_id="tenant-test", metadata=metadata)


# ---------------------------------------------------------------------------
# Skills: parsing
# ---------------------------------------------------------------------------

def test_skill_parses_frontmatter_and_body():
    skill = Skill.from_markdown(SAMPLE_SKILL_MD, path="/x/test-skill.skill.md")
    assert skill.name == "test-skill"
    assert skill.version == "2.1.0"
    assert skill.domain == "manufacturing"
    assert skill.triggers == ["widget calibration", "frobnicate"]
    assert skill.tools == ["widget_tool"]
    assert "---" not in skill.body
    assert skill.body.startswith("# Test Skill")
    assert "verify calibration" in skill.body


def test_skill_tolerates_missing_optional_fields():
    text = "---\nname: bare\n---\nJust a body."
    skill = Skill.from_markdown(text)
    assert skill.name == "bare"
    assert skill.version == "0.0.0"
    assert skill.triggers == [] and skill.tools == []
    assert skill.body == "Just a body."
    # No frontmatter at all: name falls back to file stem.
    bare = Skill.from_markdown("only body", path="/tmp/fallback.skill.md")
    assert bare.name == "fallback"
    assert bare.body == "only body"


# ---------------------------------------------------------------------------
# Skills: registry
# ---------------------------------------------------------------------------

def test_registry_loads_manufacturing_skill_packs():
    registry = SkillRegistry()
    count = registry.load_dir(SKILLS_DIR)
    assert count == 5
    names = {s.name for s in registry.list()}
    assert names == {
        "scheduling-optimization",
        "spc-analysis",
        "rca-8d",
        "mrp-planning",
        "oee-improvement",
    }
    for skill in registry.list():
        assert skill.version == "1.0.0"
        assert skill.domain == "manufacturing"
        assert skill.triggers and skill.tools and len(skill.body) > 200
    assert registry.get("spc-analysis") is not None
    assert registry.get("nope") is None


def test_registry_match_scores_relevant_skill_first():
    registry = SkillRegistry()
    registry.load_dir(SKILLS_DIR)
    top = registry.match("interpret this control chart with western electric rules and cpk")
    assert top and top[0].name == "spc-analysis"
    top2 = registry.match("which dispatch rule should we use at the bottleneck scheduling")
    assert top2 and top2[0].name == "scheduling-optimization"
    assert registry.match("completely unrelated zebra astronomy text") == []


def test_registry_match_is_deterministic_with_name_tiebreak():
    registry = SkillRegistry()
    registry.add(Skill(name="b-skill", triggers=["shared trigger"]))
    registry.add(Skill(name="a-skill", triggers=["shared trigger"]))
    first = [s.name for s in registry.match("shared trigger please", limit=5)]
    second = [s.name for s in registry.match("shared trigger please", limit=5)]
    assert first == second == ["a-skill", "b-skill"]  # tie broken by name


def test_registry_render_contains_headers_and_bodies():
    registry = SkillRegistry()
    registry.load_dir(SKILLS_DIR)
    skills = [registry.get("spc-analysis"), registry.get("rca-8d")]
    rendered = SkillRegistry.render(skills)
    assert "## Relevant Skills" in rendered
    assert "### Skill: spc-analysis (v1.0.0)" in rendered
    assert "### Skill: rca-8d (v1.0.0)" in rendered
    assert "Western Electric rules" in rendered
    assert "fishbone" in rendered.lower()
    assert SkillRegistry.render([]) == ""


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

def test_threshold_policy_dotted_path():
    policy = ThresholdPolicy("input.po.total_cost", max_value=50_000)
    over = {"type": "invoke", "input": {"po": {"total_cost": 60_000}}}
    under = {"type": "invoke", "input": {"po": {"total_cost": 10_000}}}
    missing = {"type": "invoke", "input": {}}
    assert policy.evaluate(over)[0] is PolicyDecision.REQUIRE_APPROVAL
    assert policy.evaluate(under)[0] is PolicyDecision.ALLOW
    assert policy.evaluate(missing)[0] is PolicyDecision.ALLOW
    deny = ThresholdPolicy("amount", 100, decision_above=PolicyDecision.DENY)
    decision, reason = deny.evaluate({"amount": 101})
    assert decision is PolicyDecision.DENY and "exceeds" in reason


def test_allowed_action_types_policy():
    policy = AllowedActionTypesPolicy({"invoke", "po.create"})
    assert policy.evaluate({"type": "invoke"})[0] is PolicyDecision.ALLOW
    assert policy.evaluate({"type": "machine.delete"})[0] is PolicyDecision.DENY
    assert policy.evaluate({})[0] is PolicyDecision.DENY  # closed allowlist


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------

def _sample_receipt(i: int) -> Receipt:
    return Receipt(
        agent_id=f"agent-{i}",
        agent_type="StubAgent",
        trace_id=f"trace-{i}",
        tenant_id="tenant-test",
        inputs_hash="ab" * 32,
        actions=[{"type": "noop"}],
        skills_used=["spc-analysis"],
        cost={"tokens_used": i},
    )


def test_receipt_chain_verifies():
    chain = ReceiptChain()
    for i in range(3):
        chain.append(_sample_receipt(i))
    assert len(chain) == 3
    assert chain.verify() is True
    receipts = chain.receipts
    assert receipts[0].prev_hash == "0" * 64
    assert receipts[1].prev_hash == receipts[0].hash
    assert all(len(r.hash) == 64 for r in receipts)


def test_receipt_chain_detects_tampering():
    chain = ReceiptChain()
    for i in range(3):
        chain.append(_sample_receipt(i))
    chain.receipts  # copies — mutate the live object instead
    chain._receipts[1].cost["tokens_used"] = 999_999
    assert chain.verify() is False


def test_receipt_chain_to_jsonl(tmp_path):
    chain = ReceiptChain()
    for i in range(2):
        chain.append(_sample_receipt(i))
    out = tmp_path / "receipts.jsonl"
    assert chain.to_jsonl(out) == 2
    lines = out.read_text().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        record = json.loads(line)
        assert {"receipt_id", "hash", "prev_hash", "inputs_hash"} <= set(record)


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

def test_approval_queue_approve_and_reject():
    queue = ApprovalQueue()
    req_a = queue.request("run-1", {"type": "invoke"}, "over threshold")
    req_b = queue.request("run-2", {"type": "invoke"}, "over threshold")
    assert {r.id for r in queue.pending()} == {req_a.id, req_b.id}
    assert queue.approve(req_a.id).status is ApprovalStatus.APPROVED
    assert queue.reject(req_b.id).status is ApprovalStatus.REJECTED
    assert queue.pending() == []
    assert queue.approve(req_a.id) is None  # already resolved
    assert queue.approve("nonexistent") is None


async def test_approval_wait_timeout_and_grant():
    queue = ApprovalQueue(poll_interval_s=0.01)
    req = queue.request("run-1", {"type": "invoke"}, "needs human")
    # Times out while unresolved.
    assert await queue.wait(req.id, timeout_s=0.05) is ApprovalStatus.PENDING

    async def approve_soon():
        await asyncio.sleep(0.03)
        queue.approve(req.id)

    status, _ = await asyncio.gather(queue.wait(req.id, timeout_s=2.0), approve_soon())
    assert status is ApprovalStatus.APPROVED


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

async def test_harness_deny_blocks_agent_run():
    agent = StubAgent()
    harness = AgentHarness(agent, policies=[AllowedActionTypesPolicy({"never"})])
    outcome = await harness.run({"task": "do something"}, make_context())
    assert outcome.denied is True and outcome.success is False
    assert agent.run_count == 0
    assert outcome.receipt is not None
    assert any(d["decision"] == "deny" for d in outcome.policy_decisions)
    assert harness.receipt_chain.verify() is True


async def test_harness_approval_granted_in_background():
    agent = StubAgent()
    queue = ApprovalQueue(poll_interval_s=0.01)
    harness = AgentHarness(
        agent,
        policies=[ThresholdPolicy("input.amount", 1_000)],
        approval_queue=queue,
        budget=Budget(max_seconds=5.0),
    )

    async def approve_soon():
        await asyncio.sleep(0.05)
        pending = queue.pending()
        assert len(pending) == 1
        queue.approve(pending[0].id)

    outcome, _ = await asyncio.gather(
        harness.run({"amount": 5_000}, make_context()), approve_soon()
    )
    assert outcome.success is True
    assert outcome.approval_id is not None
    assert agent.run_count == 1
    assert any(d["decision"] == "require_approval" for d in outcome.policy_decisions)
    assert harness.receipt_chain.verify() is True


async def test_harness_approval_rejected_blocks_run():
    agent = StubAgent()
    queue = ApprovalQueue(poll_interval_s=0.01)
    harness = AgentHarness(
        agent,
        policies=[ThresholdPolicy("input.amount", 1_000)],
        approval_queue=queue,
        budget=Budget(max_seconds=5.0),
    )

    async def reject_soon():
        await asyncio.sleep(0.05)
        queue.reject(queue.pending()[0].id)

    outcome, _ = await asyncio.gather(
        harness.run({"amount": 5_000}, make_context()), reject_soon()
    )
    assert outcome.approval_required is True and outcome.success is False
    assert agent.run_count == 0
    assert outcome.receipt is not None


async def test_harness_budget_timeout():
    agent = StubAgent(delay=0.5)
    harness = AgentHarness(agent, budget=Budget(max_seconds=0.05))
    outcome = await harness.run({"task": "slow"}, make_context())
    assert outcome.success is False
    assert "timeout" in outcome.error
    assert outcome.receipt is not None
    assert harness.receipt_chain.verify() is True


async def test_harness_success_injects_skills_and_seals_receipt():
    registry = SkillRegistry()
    registry.load_dir(SKILLS_DIR)
    actions = [{"type": "ncr.create", "severity": "major"}]
    agent = StubAgent(actions=actions)
    harness = AgentHarness(
        agent,
        policies=[AllowedActionTypesPolicy({"invoke", "ncr.create"})],
        skill_registry=registry,
    )
    original_context = make_context(environment="test")
    outcome = await harness.run(
        {"task": "analyze the control chart for western electric spc signals"},
        original_context,
    )
    assert outcome.success is True and outcome.denied is False
    assert "spc-analysis" in outcome.skills_used
    # Skills injected into the context the agent saw...
    assert "spc-analysis" in agent.last_context.metadata["skills_prompt"]
    # ...without mutating the caller's context.
    assert "skills_prompt" not in original_context.metadata
    assert original_context.metadata == {"environment": "test"}
    # Receipt covers actions, policies, skills, cost — and the chain verifies.
    receipt = outcome.receipt
    assert receipt.skills_used == outcome.skills_used
    assert receipt.actions[0]["type"] == "ncr.create"
    assert receipt.inputs_hash and len(receipt.inputs_hash) == 64
    assert receipt.cost["tokens_used"] == 7
    phases = {d["phase"] for d in receipt.policy_decisions}
    assert phases == {"pre", "post"}
    assert harness.receipt_chain.verify() is True


# ---------------------------------------------------------------------------
# AutoOptimize loop
# ---------------------------------------------------------------------------

def test_autoresearch_best_objective_monotone_and_acceptance_recorded():
    loop = make_loop(seed=42)
    best_trajectory = []
    for _ in range(15):
        record = loop.step()
        best_trajectory.append(loop.best_objective)
        # Journal invariants per step.
        assert record.accepted == (record.objective_after > record.objective_before)
        if record.accepted:
            assert loop.best_objective == pytest.approx(record.objective_after)
    assert all(b >= a for a, b in zip(best_trajectory, best_trajectory[1:]))
    summary = loop.run(0)
    assert summary["steps"] == 15
    accepted = [s for s in loop.history if s.accepted]
    rejected = [s for s in loop.history if not s.accepted]
    assert accepted and rejected  # both outcomes exercised
    assert summary["acceptance_rate"] == pytest.approx(len(accepted) / 15)
    assert summary["best_objective"] == pytest.approx(best_trajectory[-1])
    assert summary["best_policy"]["dispatch_rule"] in {"EDD", "SPT", "CR", "WSPT", "FIFO"}


def test_autoresearch_journal_lines_parse_as_optimization_steps(tmp_path):
    journal = tmp_path / "journal.jsonl"
    loop = make_loop(seed=7, journal_path=journal)
    loop.run(6)
    lines = journal.read_text().strip().splitlines()
    assert len(lines) == 6
    expected_keys = set(OptimizationStep(
        step=0, mutated_field="x", old_value=0, new_value=1,
        objective_before=0.0, objective_after=0.0, accepted=False,
    ).to_dict())
    for i, line in enumerate(lines, start=1):
        record = json.loads(line)
        assert set(record) == expected_keys
        assert record["step"] == i
        assert isinstance(record["accepted"], bool)
        assert record["mutated_field"] in {
            "dispatch_rule", "batch_size_factor", "maintenance_buffer_hours",
            "expedite_threshold", "queue_weight_due", "queue_weight_setup",
        }


def test_autoresearch_deterministic_across_runs_with_same_seed():
    loop_a, loop_b = make_loop(seed=42), make_loop(seed=42)
    summary_a, summary_b = loop_a.run(12), loop_b.run(12)

    def strip_ts(step: OptimizationStep) -> dict:
        d = step.to_dict()
        d.pop("timestamp")
        d["kpis_after"].pop("captured_at", None)
        return d

    assert [strip_ts(s) for s in loop_a.history] == [strip_ts(s) for s in loop_b.history]
    assert summary_a["best_policy"] == summary_b["best_policy"]
    assert summary_a["best_objective"] == pytest.approx(summary_b["best_objective"])
    # A different seed explores a different trajectory.
    loop_c = make_loop(seed=1)
    loop_c.run(12)
    fields_c = [s.mutated_field for s in loop_c.history]
    fields_a = [s.mutated_field for s in loop_a.history]
    assert fields_a != fields_c
