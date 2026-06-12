"""
Human-in-the-loop approval queue for the agent harness.

When a policy returns REQUIRE_APPROVAL, the harness parks the run here.
Mission Control (or any operator surface) lists pending requests and resolves
them via ``approve()`` / ``reject()``; the harness awaits the outcome with
``wait()``.

Design contract: docs/plans/MANUFACTURING_FLAVOR_DESIGN.md §3.6.
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalRequest:
    id: str = field(default_factory=lambda: f"APRV-{uuid.uuid4().hex[:12]}")
    run_id: str = ""
    action: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "action": self.action,
            "reason": self.reason,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }


class ApprovalQueue:
    """In-memory HITL approval queue (asyncio-friendly, no locks needed)."""

    def __init__(self, poll_interval_s: float = 0.02) -> None:
        self._requests: Dict[str, ApprovalRequest] = {}
        self.poll_interval_s = poll_interval_s

    def request(self, run_id: str, action: Dict[str, Any], reason: str) -> ApprovalRequest:
        req = ApprovalRequest(run_id=run_id, action=action, reason=reason)
        self._requests[req.id] = req
        logger.info("approval_requested", approval_id=req.id, run_id=run_id, reason=reason)
        return req

    def get(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(approval_id)

    def pending(self) -> List[ApprovalRequest]:
        return [r for r in self._requests.values() if r.status is ApprovalStatus.PENDING]

    def _resolve(self, approval_id: str, status: ApprovalStatus) -> Optional[ApprovalRequest]:
        req = self._requests.get(approval_id)
        if req is None or req.status is not ApprovalStatus.PENDING:
            return None
        req.status = status
        req.resolved_at = datetime.utcnow()
        logger.info("approval_resolved", approval_id=approval_id, status=status.value)
        return req

    def approve(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._resolve(approval_id, ApprovalStatus.APPROVED)

    def reject(self, approval_id: str) -> Optional[ApprovalRequest]:
        return self._resolve(approval_id, ApprovalStatus.REJECTED)

    async def wait(self, approval_id: str, timeout_s: float) -> ApprovalStatus:
        """
        Poll until the request is resolved or ``timeout_s`` elapses.

        Returns the final status — still PENDING when the wait timed out or
        the id is unknown.
        """
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout_s
        while True:
            req = self._requests.get(approval_id)
            if req is None:
                return ApprovalStatus.PENDING
            if req.status is not ApprovalStatus.PENDING:
                return req.status
            if loop.time() >= deadline:
                return ApprovalStatus.PENDING
            await asyncio.sleep(min(self.poll_interval_s, max(deadline - loop.time(), 0.0)))
