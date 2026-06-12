"""
Maintenance Council - Manufacturing Flavor

Allocates plant downtime windows when maintenance requests exceed the
available maintenance buffer. Members: maintenance lead (domain expert),
production scheduler (pessimistic about downtime) and reliability engineer
(data driven), using the core weighted-voting council machinery.

Allocation policy (deterministic): requests are granted in descending
risk_score order until the downtime buffer is exhausted; the remainder is
deferred to the next window.
"""
import uuid
from typing import Any, Dict, List, Optional

import structlog

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm
from flavors.manufacturing.models import MaintenanceWorkOrder

logger = structlog.get_logger()


def create_maintenance_council() -> BaseCouncil:
    """Create the underlying BaseCouncil for downtime-window allocation."""
    config = CouncilConfig(
        council_id="mfg_maintenance_council",
        council_type=CouncilType.TASK_FORCE,
        name="Manufacturing Maintenance Council",
        description="Downtime-window allocation across maintenance requests",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.50,
        max_iterations=3,
        min_consensus_quality=0.60,
        meeting_frequency="as_needed",
        quorum_required=3,
    )

    members = [
        CouncilMember(
            member_id="maintenance_lead",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["maintenance", "reliability", "manufacturing"],
            base_accuracy=0.86,
        ),
        CouncilMember(
            member_id="production_scheduler",
            role=MemberRole.PESSIMISTIC,
            domain_expertise=["scheduling", "throughput", "otd"],
            base_accuracy=0.84,
        ),
        CouncilMember(
            member_id="reliability_engineer",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["condition_monitoring", "mtbf", "vibration"],
            base_accuracy=0.85,
        ),
    ]

    return BaseCouncil(config=config, members=members)


class MaintenanceCouncil:
    """Decide()-style wrapper around the maintenance BaseCouncil."""

    def __init__(self, council: Optional[BaseCouncil] = None):
        self.council = council or create_maintenance_council()

    async def decide(
        self,
        requests: List[MaintenanceWorkOrder],
        available_buffer_hours: float,
    ) -> Dict[str, Any]:
        """
        Allocate downtime among maintenance requests.

        Requests are sorted by risk_score (descending) and granted until the
        downtime buffer is exhausted; remaining requests are deferred.
        """
        total_requested = sum(r.estimated_hours for r in requests)
        contention = total_requested > available_buffer_hours

        granted: List[str] = []
        deferred: List[str] = []
        allocated = 0.0
        for request in sorted(
            requests, key=lambda r: r.risk_score, reverse=True
        ):
            if allocated + request.estimated_hours <= available_buffer_hours:
                granted.append(request.maintenance_id)
                allocated += request.estimated_hours
            else:
                deferred.append(request.maintenance_id)

        record = await self.council.convene(
            decision_id=f"mc-{uuid.uuid4().hex[:8]}",
            decision_type="operational",
            description=(
                f"Allocate {available_buffer_hours:.1f}h downtime buffer "
                f"across {len(requests)} maintenance request(s)"
            ),
            data={
                "requests": [
                    {
                        "maintenance_id": r.maintenance_id,
                        "machine_id": r.machine_id,
                        "risk_score": r.risk_score,
                        "estimated_hours": r.estimated_hours,
                    }
                    for r in requests
                ],
                "available_buffer_hours": available_buffer_hours,
                "contention": contention,
            },
            department="manufacturing",
        )
        consensus = record.consensus

        rationale = (
            f"Maintenance council weighted consensus "
            f"{consensus.decision_value:.2f}: granted {len(granted)} of "
            f"{len(requests)} request(s) by descending risk within the "
            f"{available_buffer_hours:.1f}h buffer"
        )
        if deferred:
            rationale += f"; deferred {len(deferred)} to the next window"

        decision = {
            "granted": granted,
            "deferred": deferred,
            "allocated_hours": round(allocated, 2),
            "available_buffer_hours": available_buffer_hours,
            "total_requested_hours": round(total_requested, 2),
            "contention": contention,
            "consensus_score": round(consensus.decision_value, 3),
            "rationale": rationale,
            "votes": {
                v.member_id: round(v.decision_value, 3) for v in record.votes
            },
        }
        logger.info(
            "maintenance_council_decision",
            granted=len(granted),
            deferred=len(deferred),
            allocated_hours=decision["allocated_hours"],
        )
        return decision
