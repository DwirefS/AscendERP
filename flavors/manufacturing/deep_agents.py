"""
Deep-agent missions for manufacturing (optional LangChain deepagents adapter).

A "mission" is a long-horizon goal ("cut late deliveries 30% this quarter")
that decomposes into planned sub-tasks executed by manufacturing agents.

Two execution paths:

1. **Native (always available):** `MissionPlanner` decomposes the mission with
   deterministic domain rules into a plan board (todo/in_progress/done) and
   executes each task through the corresponding PRREEL agent via the core
   AgentHarness — same primitives deepagents popularized (plan, sub-agents,
   progress tracking), no extra dependencies.

2. **deepagents (when `pip install "ants[deep]"`):** the same mission is handed
   to a LangChain deep agent with the manufacturing agents exposed as tools and
   the flavor's skill packs as instructions. Requires a configured LLM.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()

try:  # optional extra
    import deepagents  # noqa: F401
    DEEPAGENTS_AVAILABLE = True
except ImportError:
    DEEPAGENTS_AVAILABLE = False


@dataclass
class MissionTask:
    task_id: str
    description: str
    agent_type: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    status: str = "todo"            # todo | in_progress | done | failed | skipped
    result_summary: Optional[str] = None


@dataclass
class Mission:
    goal: str
    tasks: List[MissionTask] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def board(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {"todo": [], "in_progress": [], "done": [], "failed": [], "skipped": []}
        for t in self.tasks:
            out.setdefault(t.status, []).append(f"{t.task_id}: {t.description}")
        return out


# Deterministic goal → task decomposition rules. Each rule maps trigger
# keywords to the agent sequence that addresses that class of goal.
_DECOMPOSITION_RULES = [
    (
        {"late", "otd", "on-time", "delivery", "delays"},
        [
            ("manufacturing.production_planner",
             "Rebuild the production schedule prioritizing at-risk orders",
             {"type": "plan", "focus": "due_date_risk"}),
            ("manufacturing.inventory",
             "Project material shortages against the new schedule",
             {"type": "shortage_projection"}),
            ("manufacturing.procurement",
             "Expedite purchase orders for projected shortages",
             {"type": "expedite_review"}),
        ],
    ),
    (
        {"quality", "scrap", "defect", "ncr", "cpk"},
        [
            ("manufacturing.quality",
             "Run SPC analysis across recent inspections",
             {"type": "spc_review"}),
            ("manufacturing.quality",
             "Open NCRs and recommend dispositions for out-of-control characteristics",
             {"type": "ncr_review"}),
            ("manufacturing.maintenance",
             "Check whether degrading machines explain the quality drift",
             {"type": "risk_assessment"}),
        ],
    ),
    (
        {"downtime", "breakdown", "oee", "maintenance", "availability"},
        [
            ("manufacturing.maintenance",
             "Score failure risk for every machine and schedule predictive maintenance",
             {"type": "risk_assessment"}),
            ("manufacturing.production_planner",
             "Replan around the proposed maintenance windows",
             {"type": "plan", "focus": "maintenance_windows"}),
        ],
    ),
    (
        {"cost", "spend", "margin", "inventory value", "working capital"},
        [
            ("manufacturing.inventory",
             "ABC-classify inventory and recompute safety stocks",
             {"type": "abc_analysis"}),
            ("manufacturing.procurement",
             "Re-score suppliers and flag renegotiation candidates",
             {"type": "supplier_review"}),
        ],
    ),
]

_FALLBACK_TASKS = [
    ("manufacturing.production_planner",
     "Assess current plan vs goal", {"type": "plan"}),
    ("manufacturing.inventory",
     "Assess material readiness", {"type": "shortage_projection"}),
]


class MissionPlanner:
    """Decompose and execute long-horizon manufacturing missions."""

    def __init__(self, harness_factory=None):
        # harness_factory(agent) -> AgentHarness; defaults to the core harness
        # with the flavor's policy set.
        self._harness_factory = harness_factory

    def plan(self, goal: str) -> Mission:
        text = goal.lower()
        tasks: List[MissionTask] = []
        matched = False
        for triggers, rule_tasks in _DECOMPOSITION_RULES:
            if any(t in text for t in triggers):
                matched = True
                for i, (agent_type, desc, input_data) in enumerate(rule_tasks):
                    tasks.append(MissionTask(
                        task_id=f"T{len(tasks)+1}",
                        description=desc,
                        agent_type=agent_type,
                        input_data={**input_data, "goal": goal},
                    ))
        if not matched:
            for agent_type, desc, input_data in _FALLBACK_TASKS:
                tasks.append(MissionTask(
                    task_id=f"T{len(tasks)+1}",
                    description=desc,
                    agent_type=agent_type,
                    input_data={**input_data, "goal": goal},
                ))
        mission = Mission(goal=goal, tasks=tasks)
        logger.info("mission_planned", goal=goal, tasks=len(tasks))
        return mission

    async def execute(self, mission: Mission, context=None) -> Dict[str, Any]:
        """Execute the mission plan task-by-task through harnessed agents."""
        from src.core.agent.base import AgentContext
        import uuid

        context = context or AgentContext(
            trace_id=str(uuid.uuid4()), tenant_id="mission-control"
        )
        for task in mission.tasks:
            task.status = "in_progress"
            try:
                agent = self._build_agent(task.agent_type)
                harness = self._build_harness(agent)
                outcome = await harness.run(task.input_data, context)
                if getattr(outcome, "approval_required", False):
                    task.status = "skipped"
                    task.result_summary = "parked for human approval"
                elif getattr(outcome, "denied", False):
                    task.status = "skipped"
                    task.result_summary = "denied by policy"
                elif outcome.success:
                    task.status = "done"
                    task.result_summary = "completed"
                else:
                    task.status = "failed"
                    task.result_summary = str(getattr(outcome, "error", "unknown"))
            except Exception as e:
                task.status = "failed"
                task.result_summary = str(e)
                logger.warning("mission_task_failed", task=task.task_id, error=str(e))
        done = sum(1 for t in mission.tasks if t.status == "done")
        return {
            "goal": mission.goal,
            "board": mission.board(),
            "completed": done,
            "total": len(mission.tasks),
            "engine": "native",
        }

    def _build_agent(self, agent_type: str):
        import importlib

        suffix = agent_type.split(".", 1)[1]
        module = importlib.import_module(
            f"flavors.manufacturing.agents.{suffix}_agent"
        )
        cls_name = "".join(p.capitalize() for p in suffix.split("_")) + "Agent"
        # Handle EHS acronym casing
        if suffix == "ehs_compliance":
            cls_name = "EHSComplianceAgent"
        return getattr(module, cls_name)()

    def _build_harness(self, agent):
        if self._harness_factory:
            return self._harness_factory(agent)
        from src.core.harness import AgentHarness, Budget
        from flavors.manufacturing.policies import build_manufacturing_policies

        return AgentHarness(
            agent,
            policies=build_manufacturing_policies(),
            budget=Budget(max_seconds=120, max_actions=50),
        )


def build_deep_agent(model: Any = None, **kwargs):
    """
    Build a LangChain deep agent over the manufacturing fleet.
    Requires the `[deep]` extra and a configured chat model.
    """
    if not DEEPAGENTS_AVAILABLE:
        raise ImportError(
            "deepagents is not installed. Install with: pip install 'ants[deep]'. "
            "The native MissionPlanner provides the dependency-free path."
        )
    from deepagents import create_deep_agent  # type: ignore

    from src.core.skills import SkillRegistry
    from pathlib import Path

    registry = SkillRegistry()
    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.exists():
        registry.load_dir(str(skills_dir))
    instructions = (
        "You are Mission Control for a discrete-manufacturing plant. "
        "Decompose the mission, delegate to sub-agents, and respect approval "
        "policies.\n\n" + registry.render(registry.list())
    )
    return create_deep_agent(
        model=model,
        tools=kwargs.pop("tools", []),
        system_prompt=instructions,
        **kwargs,
    )
