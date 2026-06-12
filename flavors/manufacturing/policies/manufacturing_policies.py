"""
Action policies for the manufacturing flavor.

These are evaluated by the core AgentHarness (src/core/harness) before and
after agent execution. Thresholds implement "controlled autonomy": agents act
freely below them; above them a human approves via Mission Control.
"""
from typing import Any, Dict, Tuple

import structlog

logger = structlog.get_logger()

PO_APPROVAL_THRESHOLD_USD = 50_000.0
SCHEDULE_CHANGE_APPROVAL_FRACTION = 0.20   # >20% of capacity rescheduled
EHS_CRITICAL_SEVERITIES = {"critical", "fatality_risk"}


def _get(action: Dict[str, Any], path: str, default=None):
    cur: Any = action
    for part in path.split("."):
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part)
        if cur is None:
            return default
    return cur


class PurchaseOrderApprovalPolicy:
    """POs above the threshold require human approval."""

    name = "po_approval_threshold"

    def evaluate(self, action: Dict[str, Any], context: Any = None) -> Tuple[str, str]:
        from src.core.harness.policy import PolicyDecision

        total = _get(action, "input.total_cost") or _get(action, "total_cost")
        if action.get("type") in ("create_purchase_order", "invoke") and total:
            try:
                if float(total) > PO_APPROVAL_THRESHOLD_USD:
                    return (
                        PolicyDecision.REQUIRE_APPROVAL,
                        f"PO total ${float(total):,.0f} exceeds "
                        f"${PO_APPROVAL_THRESHOLD_USD:,.0f} approval threshold",
                    )
            except (TypeError, ValueError):
                pass
        return PolicyDecision.ALLOW, "within procurement authority"


class ScheduleChangeApprovalPolicy:
    """Large schedule rewrites require human approval."""

    name = "schedule_change_threshold"

    def evaluate(self, action: Dict[str, Any], context: Any = None) -> Tuple[str, str]:
        from src.core.harness.policy import PolicyDecision

        fraction = _get(action, "input.capacity_change_fraction") or _get(
            action, "capacity_change_fraction"
        )
        if fraction is not None:
            try:
                if float(fraction) > SCHEDULE_CHANGE_APPROVAL_FRACTION:
                    return (
                        PolicyDecision.REQUIRE_APPROVAL,
                        f"schedule change affects {float(fraction):.0%} of capacity "
                        f"(> {SCHEDULE_CHANGE_APPROVAL_FRACTION:.0%})",
                    )
            except (TypeError, ValueError):
                pass
        return PolicyDecision.ALLOW, "schedule change within autonomous bounds"


class EHSCriticalPolicy:
    """Critical EHS actions always require a human in the loop."""

    name = "ehs_critical_hitl"

    def evaluate(self, action: Dict[str, Any], context: Any = None) -> Tuple[str, str]:
        from src.core.harness.policy import PolicyDecision

        severity = (_get(action, "input.severity") or _get(action, "severity") or "")
        if str(severity).lower() in EHS_CRITICAL_SEVERITIES:
            return (
                PolicyDecision.REQUIRE_APPROVAL,
                f"EHS severity '{severity}' mandates human review",
            )
        return PolicyDecision.ALLOW, "EHS severity within autonomous bounds"


def build_manufacturing_policies() -> list:
    """The default policy set wired into manufacturing agent harnesses."""
    return [
        PurchaseOrderApprovalPolicy(),
        ScheduleChangeApprovalPolicy(),
        EHSCriticalPolicy(),
    ]
