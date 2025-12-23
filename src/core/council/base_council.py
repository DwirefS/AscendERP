"""
Base Council - Abstract Council Orchestrator

Provides foundation for all council types (Executive, Department, Task Force)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

from src.core.council.member import CouncilMember, MemberRole
from src.core.council.decision_maker import DecisionMaker, DeliberationContext, DeliberationRecord
from src.core.council.consensus import ConsensusAlgorithm

logger = logging.getLogger(__name__)


class CouncilType(Enum):
    """Types of councils in organizational hierarchy"""
    EXECUTIVE = "executive"  # Strategic, enterprise-wide
    DEPARTMENT = "department"  # Tactical, department-level
    TASK_FORCE = "task_force"  # Operational, time-bound


@dataclass
class CouncilConfig:
    """
    Configuration for a council
    """
    council_id: str
    council_type: CouncilType
    name: str
    description: str

    # Decision-making configuration
    consensus_algorithm: ConsensusAlgorithm = ConsensusAlgorithm.WEIGHTED_VOTING
    decision_threshold: float = 0.65  # Minimum score to approve
    max_iterations: int = 3
    min_consensus_quality: float = 0.7

    # Meeting configuration
    meeting_frequency: str = "as_needed"  # "daily", "weekly", "monthly", "as_needed"
    quorum_required: int = 3  # Minimum members for valid decision

    # Authority limits
    budget_authority: Optional[float] = None  # Max budget decision without escalation
    requires_ratification: bool = False  # Must be ratified by higher council


class BaseCouncil:
    """
    Abstract base class for all councils

    Provides common functionality for:
    - Member management
    - Decision-making orchestration
    - Meeting scheduling
    - Decision history tracking
    """

    def __init__(self, config: CouncilConfig, members: List[CouncilMember]):
        """
        Initialize council

        Args:
            config: Council configuration
            members: List of council members
        """
        self.config = config
        self.members = members
        self.decision_maker = DecisionMaker(
            members=members,
            consensus_algorithm=config.consensus_algorithm,
            max_iterations=config.max_iterations,
            min_consensus_quality=config.min_consensus_quality
        )

        # Decision history
        self.decision_history: List[DeliberationRecord] = []

        # Current meeting state
        self.meeting_in_progress = False
        self.current_deliberation: Optional[DeliberationRecord] = None

        logger.info(
            f"Council initialized: {config.name} ({config.council_type.value}), "
            f"{len(members)} members"
        )

    async def convene(
        self,
        decision_id: str,
        decision_type: str,
        description: str,
        data: Dict[str, Any],
        **kwargs
    ) -> DeliberationRecord:
        """
        Convene council to deliberate on a decision

        Args:
            decision_id: Unique identifier for this decision
            decision_type: Type of decision (strategic, tactical, operational)
            description: Human-readable description
            data: Decision context data
            **kwargs: Additional context parameters

        Returns:
            DeliberationRecord with consensus decision

        Raises:
            ValueError: If quorum not met or council already in session
        """
        if self.meeting_in_progress:
            raise ValueError(f"Council {self.config.council_id} already in session")

        if len(self.members) < self.config.quorum_required:
            raise ValueError(
                f"Quorum not met: {len(self.members)} < {self.config.quorum_required}"
            )

        logger.info(f"Convening council {self.config.name} for decision: {decision_id}")

        self.meeting_in_progress = True

        try:
            # Create deliberation context
            context = DeliberationContext(
                decision_id=decision_id,
                decision_type=decision_type,
                description=description,
                data=data,
                **kwargs
            )

            # Check authority limits
            if self.config.budget_authority and kwargs.get("budget_amount"):
                if kwargs["budget_amount"] > self.config.budget_authority:
                    logger.warning(
                        f"Budget ${kwargs['budget_amount']} exceeds authority "
                        f"${self.config.budget_authority} - escalation required"
                    )
                    # In production, would escalate to higher council
                    context.authority_level = "elevated"

            # Execute deliberation
            record = await self.decision_maker.deliberate(context)

            # Check if decision meets threshold
            if record.consensus.decision_value < self.config.decision_threshold:
                logger.warning(
                    f"Decision {decision_id} below threshold: "
                    f"{record.consensus.decision_value:.2f} < {self.config.decision_threshold:.2f}"
                )
                record.consensus.rationale += " (REJECTED - below threshold)"

            # Store in history
            self.decision_history.append(record)
            self.current_deliberation = record

            logger.info(
                f"Council decision complete: {decision_id}, "
                f"result={record.consensus.decision_value:.2f}"
            )

            return record

        finally:
            self.meeting_in_progress = False

    async def escalate_to_higher_council(
        self,
        decision_id: str,
        rationale: str
    ) -> Dict[str, Any]:
        """
        Escalate decision to higher council (e.g., Department → Executive)

        Args:
            decision_id: Decision requiring escalation
            rationale: Reason for escalation

        Returns:
            Escalation metadata
        """
        logger.info(
            f"Escalating decision {decision_id} from {self.config.name}: {rationale}"
        )

        # In production, would route to higher council
        # For now, return escalation metadata

        return {
            "escalated_from": self.config.council_id,
            "escalated_to": "executive_council",  # Would be dynamic
            "decision_id": decision_id,
            "rationale": rationale,
            "timestamp": datetime.utcnow()
        }

    def get_decision_history(
        self,
        limit: int = 10,
        decision_type: Optional[str] = None
    ) -> List[DeliberationRecord]:
        """
        Retrieve decision history

        Args:
            limit: Maximum number of records to return
            decision_type: Filter by decision type

        Returns:
            List of deliberation records
        """
        history = self.decision_history

        if decision_type:
            history = [r for r in history if r.context.decision_type == decision_type]

        # Sort by most recent first
        history = sorted(history, key=lambda r: r.started_at, reverse=True)

        return history[:limit]

    def get_member_performance(self) -> Dict[str, Dict[str, float]]:
        """
        Get performance metrics for each council member

        Returns:
            Dict mapping member_id to performance metrics
        """
        performance = {}

        for member in self.members:
            performance[member.member_id] = {
                "accuracy_history": member.accuracy_history,
                "total_votes": len(member.vote_history),
                "avg_confidence": (
                    sum(v.confidence for v in member.vote_history) / len(member.vote_history)
                    if member.vote_history else 0.0
                ),
                "role": member.role.value
            }

        return performance

    def add_member(self, member: CouncilMember):
        """Add a new member to the council"""
        if member.member_id in [m.member_id for m in self.members]:
            raise ValueError(f"Member {member.member_id} already in council")

        self.members.append(member)
        self.decision_maker.members.append(member)

        logger.info(f"Added member {member.member_id} to council {self.config.name}")

    def remove_member(self, member_id: str):
        """Remove a member from the council"""
        self.members = [m for m in self.members if m.member_id != member_id]
        self.decision_maker.members = [m for m in self.decision_maker.members if m.member_id != member_id]

        logger.info(f"Removed member {member_id} from council {self.config.name}")

    def get_status(self) -> Dict[str, Any]:
        """Get current council status"""
        return {
            "council_id": self.config.council_id,
            "name": self.config.name,
            "type": self.config.council_type.value,
            "member_count": len(self.members),
            "meeting_in_progress": self.meeting_in_progress,
            "total_decisions": len(self.decision_history),
            "decision_maker_phase": self.decision_maker.get_phase_status()
        }
