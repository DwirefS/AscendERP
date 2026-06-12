"""
Comprehensive agent harness: budgets, policy gates, skill injection,
HITL approvals, and hash-chained receipts around any BaseAgent-compatible
agent (anything exposing ``async run(input_data, context) -> AgentResult``).

Pipeline (design §3.6):
  1. skill match + injection (context.metadata["skills_prompt"], copy-on-write)
  2. policy pre-check on the invocation action — DENY / REQUIRE_APPROVAL gates
  3. agent run under a wall-clock budget (asyncio.wait_for)
  4. policy post-check on each action taken (audit — actions already happened)
  5. hash-chained receipt appended to the chain

Design contract: docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.6.
"""
from __future__ import annotations

import asyncio
import copy
import dataclasses
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import structlog

from src.core.harness.approvals import ApprovalQueue, ApprovalStatus
from src.core.harness.policy import ActionPolicy, PolicyDecision
from src.core.harness.receipts import Receipt, ReceiptChain, hash_inputs

logger = structlog.get_logger()

# --- optional metrics (guarded; never required at runtime) -----------------

_PROM_RUNS = None
_PROM_DENIALS = None
_PROM_APPROVALS_PENDING = None
try:  # pragma: no cover - environment dependent
    from prometheus_client import Counter as _PromCounter, Gauge as _PromGauge

    def _prom(factory, *args):
        try:
            return factory(*args)
        except ValueError:  # duplicate registration (e.g. test re-imports)
            return None

    _PROM_RUNS = _prom(_PromCounter, "harness_runs_total", "Agent harness runs", ["status"])
    _PROM_DENIALS = _prom(_PromCounter, "harness_policy_denials_total", "Harness policy denials")
    _PROM_APPROVALS_PENDING = _prom(
        _PromGauge, "harness_approvals_pending", "Harness approvals currently pending"
    )
except Exception:  # pragma: no cover
    pass

_OTEL_RUN_COUNTER = None
try:  # pragma: no cover - environment dependent
    from src.core.observability import agent_execution_counter as _OTEL_RUN_COUNTER
except Exception:  # pragma: no cover
    _OTEL_RUN_COUNTER = None


def _record_run(status: str, agent_type: str) -> None:
    if _PROM_RUNS is not None:
        _PROM_RUNS.labels(status=status).inc()
    if _OTEL_RUN_COUNTER is not None:
        try:
            _OTEL_RUN_COUNTER.add(1, {"agent_type": agent_type, "status": f"harness_{status}"})
        except Exception:  # pragma: no cover
            pass


# --- dataclasses ------------------------------------------------------------


@dataclass
class Budget:
    """Resource limits for one harness run."""

    max_seconds: float = 60.0
    max_actions: Optional[int] = None
    max_llm_calls: Optional[int] = None


@dataclass
class HarnessOutcome:
    """Result of one harnessed agent run."""

    success: bool
    result: Optional[Any] = None  # AgentResult or None
    receipt: Optional[Receipt] = None
    policy_decisions: List[Dict[str, Any]] = field(default_factory=list)
    skills_used: List[str] = field(default_factory=list)
    denied: bool = False
    approval_required: bool = False
    approval_id: Optional[str] = None
    duration_s: float = 0.0
    error: Optional[str] = None


# --- harness ----------------------------------------------------------------


class AgentHarness:
    """Wraps a single agent with policies, skills, budget, approvals, receipts."""

    def __init__(
        self,
        agent: Any,
        policies: Optional[Sequence[ActionPolicy]] = None,
        skill_registry: Optional[Any] = None,
        receipt_chain: Optional[ReceiptChain] = None,
        approval_queue: Optional[ApprovalQueue] = None,
        budget: Optional[Budget] = None,
    ) -> None:
        self.agent = agent
        self.policies: List[ActionPolicy] = list(policies or [])
        self.skill_registry = skill_registry
        self.receipt_chain = receipt_chain if receipt_chain is not None else ReceiptChain()
        self.approval_queue = approval_queue
        self.budget = budget or Budget()

    # -- helpers --------------------------------------------------------------

    @property
    def _agent_id(self) -> str:
        config = getattr(self.agent, "config", None)
        return getattr(config, "agent_id", "") or ""

    @property
    def _agent_type(self) -> str:
        return type(self.agent).__name__

    def _evaluate_policies(
        self, action: Dict[str, Any], context: Any, phase: str
    ) -> List[Dict[str, Any]]:
        decisions: List[Dict[str, Any]] = []
        for policy in self.policies:
            decision, reason = policy.evaluate(action, context)
            decisions.append(
                {
                    "policy": getattr(policy, "name", type(policy).__name__),
                    "decision": decision.value,
                    "reason": reason,
                    "phase": phase,
                    "action_type": action.get("type"),
                }
            )
        return decisions

    @staticmethod
    def _inject_skills(context: Any, skills_prompt: str) -> Any:
        """Return a context copy with skills_prompt in metadata (caller's dict untouched)."""
        metadata = dict(getattr(context, "metadata", None) or {})
        metadata["skills_prompt"] = skills_prompt
        if dataclasses.is_dataclass(context) and not isinstance(context, type):
            return dataclasses.replace(context, metadata=metadata)
        clone = copy.copy(context)
        clone.metadata = metadata
        return clone

    @staticmethod
    def _summarize_actions(actions_taken: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        summary = []
        for item in actions_taken:
            action_type = item.get("type")
            if action_type is None and isinstance(item.get("action"), dict):
                action_type = item["action"].get("type")
            summary.append({"type": action_type or "unknown", "keys": sorted(item.keys())})
        return summary

    def _seal_receipt(
        self,
        *,
        input_data: Any,
        context: Any,
        actions_taken: Sequence[Dict[str, Any]],
        policy_decisions: List[Dict[str, Any]],
        skills_used: List[str],
        cost: Dict[str, Any],
    ) -> Receipt:
        receipt = Receipt(
            agent_id=self._agent_id,
            agent_type=self._agent_type,
            trace_id=getattr(context, "trace_id", "") or "",
            tenant_id=getattr(context, "tenant_id", "") or "",
            inputs_hash=hash_inputs(input_data),
            actions=self._summarize_actions(actions_taken),
            policy_decisions=list(policy_decisions),
            skills_used=list(skills_used),
            cost=dict(cost),
        )
        return self.receipt_chain.append(receipt)

    # -- main pipeline ----------------------------------------------------------

    async def run(self, input_data: Any, context: Any) -> HarnessOutcome:
        start = time.monotonic()
        run_id = f"RUN-{uuid.uuid4().hex[:12]}"
        policy_decisions: List[Dict[str, Any]] = []
        skills_used: List[str] = []
        run_context = context

        log = logger.bind(
            run_id=run_id, agent_id=self._agent_id, agent_type=self._agent_type
        )

        # (a) skill matching + injection
        if self.skill_registry is not None:
            matched = self.skill_registry.match(str(input_data))
            if matched:
                skills_used = [s.name for s in matched]
                run_context = self._inject_skills(context, self.skill_registry.render(matched))
                log.info("harness_skills_injected", skills=skills_used)

        def _finish(
            outcome_status: str,
            *,
            success: bool,
            result: Any = None,
            denied: bool = False,
            approval_required: bool = False,
            approval_id: Optional[str] = None,
            error: Optional[str] = None,
            actions_taken: Sequence[Dict[str, Any]] = (),
            cost: Optional[Dict[str, Any]] = None,
        ) -> HarnessOutcome:
            duration = time.monotonic() - start
            full_cost = {"duration_s": round(duration, 4), **(cost or {})}
            receipt = self._seal_receipt(
                input_data=input_data,
                context=context,
                actions_taken=actions_taken,
                policy_decisions=policy_decisions,
                skills_used=skills_used,
                cost=full_cost,
            )
            _record_run(outcome_status, self._agent_type)
            log.info(
                "harness_run_finished",
                status=outcome_status,
                duration_s=round(duration, 4),
                receipt_id=receipt.receipt_id,
            )
            return HarnessOutcome(
                success=success,
                result=result,
                receipt=receipt,
                policy_decisions=list(policy_decisions),
                skills_used=list(skills_used),
                denied=denied,
                approval_required=approval_required,
                approval_id=approval_id,
                duration_s=duration,
                error=error,
            )

        # (b) policy pre-check on the invocation itself
        invoke_action = {"type": "invoke", "input": input_data}
        pre_decisions = self._evaluate_policies(invoke_action, context, phase="pre")
        policy_decisions.extend(pre_decisions)

        denials = [d for d in pre_decisions if d["decision"] == PolicyDecision.DENY.value]
        if denials:
            if _PROM_DENIALS is not None:
                _PROM_DENIALS.inc()
            log.warning("harness_run_denied", reasons=[d["reason"] for d in denials])
            return _finish(
                "denied", success=False, denied=True, error=denials[0]["reason"]
            )

        approvals_needed = [
            d for d in pre_decisions if d["decision"] == PolicyDecision.REQUIRE_APPROVAL.value
        ]
        approval_id: Optional[str] = None
        if approvals_needed:
            reason = "; ".join(d["reason"] for d in approvals_needed)
            if self.approval_queue is None:
                log.warning("harness_approval_required_no_queue", reason=reason)
                return _finish(
                    "approval_required",
                    success=False,
                    approval_required=True,
                    error=f"approval required but no approval queue configured: {reason}",
                )
            request = self.approval_queue.request(run_id, invoke_action, reason)
            approval_id = request.id
            if _PROM_APPROVALS_PENDING is not None:
                _PROM_APPROVALS_PENDING.inc()
            try:
                status = await self.approval_queue.wait(
                    request.id, timeout_s=self.budget.max_seconds
                )
            finally:
                if _PROM_APPROVALS_PENDING is not None:
                    _PROM_APPROVALS_PENDING.dec()
            if status is not ApprovalStatus.APPROVED:
                log.warning(
                    "harness_approval_not_granted",
                    approval_id=approval_id,
                    status=status.value,
                )
                return _finish(
                    "approval_required",
                    success=False,
                    approval_required=True,
                    approval_id=approval_id,
                    error=f"approval not granted (status={status.value}): {reason}",
                )
            log.info("harness_approval_granted", approval_id=approval_id)

        # (c) run the agent under the (remaining) wall-clock budget
        remaining = max(self.budget.max_seconds - (time.monotonic() - start), 0.001)
        try:
            result = await asyncio.wait_for(
                self.agent.run(input_data, run_context), timeout=remaining
            )
        except asyncio.TimeoutError:
            log.error("harness_budget_timeout", max_seconds=self.budget.max_seconds)
            return _finish(
                "timeout",
                success=False,
                approval_id=approval_id,
                error=f"budget timeout after {self.budget.max_seconds}s",
            )
        except Exception as exc:  # agent crashed — still receipt it
            log.error("harness_agent_error", error=str(exc))
            return _finish("error", success=False, approval_id=approval_id, error=str(exc))

        # (d) policy post-check on each action taken (audit only)
        actions_taken: List[Dict[str, Any]] = list(getattr(result, "actions_taken", None) or [])
        post_denials = 0
        for action in actions_taken:
            if not isinstance(action, dict):
                continue
            decisions = self._evaluate_policies(action, context, phase="post")
            policy_decisions.extend(decisions)
            post_denials += sum(
                1 for d in decisions if d["decision"] == PolicyDecision.DENY.value
            )
        if post_denials:
            # Actions already happened — flag in the receipt, don't unwind.
            if _PROM_DENIALS is not None:
                _PROM_DENIALS.inc(post_denials)
            log.warning("harness_post_check_violations", count=post_denials)

        cost: Dict[str, Any] = {
            "actions": len(actions_taken),
            "tokens_used": getattr(result, "tokens_used", 0),
            "latency_ms": getattr(result, "latency_ms", 0.0),
        }
        if self.budget.max_actions is not None and len(actions_taken) > self.budget.max_actions:
            cost["actions_over_budget"] = len(actions_taken) - self.budget.max_actions
            log.warning(
                "harness_action_budget_exceeded",
                actions=len(actions_taken),
                max_actions=self.budget.max_actions,
            )

        success = bool(getattr(result, "success", False))
        # (e) receipt + outcome
        return _finish(
            "success" if success else "agent_failed",
            success=success,
            result=result,
            approval_id=approval_id,
            error=getattr(result, "error", None),
            actions_taken=actions_taken,
            cost=cost,
        )
