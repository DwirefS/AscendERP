"""
Action policies evaluated by the agent harness.

A policy inspects an action dict (plus execution context) and returns a
:class:`PolicyDecision` with a human-readable reason. Policies are evaluated
before the agent runs (pre-check on the invocation) and after it runs
(post-check / audit on each action taken).

Design contract: docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.6.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Optional, Protocol, Set, Tuple, runtime_checkable

import structlog

logger = structlog.get_logger()


class PolicyDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@runtime_checkable
class ActionPolicy(Protocol):
    """Protocol every harness policy must satisfy."""

    name: str

    def evaluate(self, action: Dict[str, Any], context: Any = None) -> Tuple[PolicyDecision, str]:
        """Return (decision, reason) for ``action``."""
        ...


def resolve_field_path(data: Any, field_path: str) -> Any:
    """
    Resolve a dotted path (e.g. ``"input.po.total_cost"``) into nested dicts.

    Returns ``None`` if any segment is missing or the value is not a mapping
    along the way (attribute access is attempted as a fallback).
    """
    current = data
    for segment in field_path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return None
            current = current[segment]
        else:
            current = getattr(current, segment, None)
        if current is None:
            return None
    return current


class ThresholdPolicy:
    """
    Numeric threshold on a dotted field path into the action dict.

    If the resolved value exceeds ``max_value``, returns ``decision_above``
    (default REQUIRE_APPROVAL). Missing or non-numeric values are allowed —
    a threshold policy only constrains the field it can see.
    """

    def __init__(
        self,
        field_path: str,
        max_value: float,
        decision_above: PolicyDecision = PolicyDecision.REQUIRE_APPROVAL,
        name: Optional[str] = None,
    ) -> None:
        self.field_path = field_path
        self.max_value = float(max_value)
        self.decision_above = decision_above
        self.name = name or f"threshold:{field_path}<={max_value}"

    def evaluate(self, action: Dict[str, Any], context: Any = None) -> Tuple[PolicyDecision, str]:
        value = resolve_field_path(action, self.field_path)
        if value is None:
            return PolicyDecision.ALLOW, f"{self.field_path} not present"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return PolicyDecision.ALLOW, f"{self.field_path} not numeric"
        if numeric > self.max_value:
            return (
                self.decision_above,
                f"{self.field_path}={numeric} exceeds max {self.max_value}",
            )
        return PolicyDecision.ALLOW, f"{self.field_path}={numeric} within max {self.max_value}"


class AllowedActionTypesPolicy:
    """
    Allowlist on the action ``type`` field. Unknown/absent types are DENIED —
    an allowlist is closed by construction.
    """

    def __init__(self, allowed: Iterable[str], name: Optional[str] = None) -> None:
        self.allowed: Set[str] = set(allowed)
        self.name = name or f"allowed_action_types:{','.join(sorted(self.allowed))}"

    def evaluate(self, action: Dict[str, Any], context: Any = None) -> Tuple[PolicyDecision, str]:
        action_type = action.get("type")
        if action_type in self.allowed:
            return PolicyDecision.ALLOW, f"action type '{action_type}' allowed"
        return PolicyDecision.DENY, f"action type '{action_type}' not in allowlist"
