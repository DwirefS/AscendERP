"""
Generic agent harness: budgets, policy gates, hash-chained receipts,
skill injection, and HITL approvals around any ANTS agent.

See docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.6.
"""
from src.core.harness.approvals import ApprovalQueue, ApprovalRequest, ApprovalStatus
from src.core.harness.harness import AgentHarness, Budget, HarnessOutcome
from src.core.harness.policy import (
    ActionPolicy,
    AllowedActionTypesPolicy,
    PolicyDecision,
    ThresholdPolicy,
    resolve_field_path,
)
from src.core.harness.receipts import (
    GENESIS_HASH,
    Receipt,
    ReceiptChain,
    canonical_json,
    hash_inputs,
)

__all__ = [
    "ActionPolicy",
    "AgentHarness",
    "AllowedActionTypesPolicy",
    "ApprovalQueue",
    "ApprovalRequest",
    "ApprovalStatus",
    "Budget",
    "GENESIS_HASH",
    "HarnessOutcome",
    "PolicyDecision",
    "Receipt",
    "ReceiptChain",
    "ThresholdPolicy",
    "canonical_json",
    "hash_inputs",
    "resolve_field_path",
]
