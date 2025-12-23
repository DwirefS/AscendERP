"""
Decision Maker - Council Deliberation Engine

Orchestrates the structured debate process for decision-making councils.

Deliberation Protocol (5 Phases):
1. Independent Analysis - Parallel, no communication
2. Structured Debate - Sequential presentations
3. Iterative Refinement - Bayesian belief updates
4. Consensus Building - Weighted voting/aggregation
5. Meta-Decision - Validation and ratification

Based on research:
- Emergent Coordination in Multi-Agent LMs (arXiv:2510.05174, 2025)
- MACIE: Multi-Agent Causal Intelligence (arXiv:2511.15716, 2025)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import asyncio

from src.core.council.member import CouncilMember, Opinion, Vote
from src.core.council.consensus import (
    ConsensusBuilder,
    ConsensusResult,
    ConsensusAlgorithm,
    create_consensus_builder
)

logger = logging.getLogger(__name__)


class DeliberationPhase(Enum):
    """Phases of council deliberation"""
    INDEPENDENT_ANALYSIS = "independent_analysis"
    STRUCTURED_DEBATE = "structured_debate"
    ITERATIVE_REFINEMENT = "iterative_refinement"
    CONSENSUS_BUILDING = "consensus_building"
    META_DECISION = "meta_decision"
    COMPLETED = "completed"


@dataclass
class DeliberationContext:
    """
    Context for a council deliberation session
    """
    decision_id: str
    decision_type: str  # e.g., "strategic", "tactical", "operational"
    description: str
    data: Dict[str, Any]

    # Constraints
    deadline: Optional[datetime] = None
    budget_limit: Optional[float] = None
    authority_level: str = "standard"  # "standard", "elevated", "critical"

    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    requester: Optional[str] = None
    department: Optional[str] = None


@dataclass
class DeliberationRecord:
    """
    Record of a complete deliberation session
    """
    context: DeliberationContext
    members: List[str]  # Member IDs
    opinions: List[Opinion]
    votes: List[Vote]
    consensus: ConsensusResult
    phase_history: List[Dict[str, Any]] = field(default_factory=list)

    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


class DecisionMaker:
    """
    Orchestrates council deliberation process

    Implements the 5-phase deliberation protocol to reach consensus
    on strategic decisions.
    """

    def __init__(
        self,
        members: List[CouncilMember],
        consensus_algorithm: ConsensusAlgorithm = ConsensusAlgorithm.WEIGHTED_VOTING,
        max_iterations: int = 3,
        min_consensus_quality: float = 0.7
    ):
        """
        Initialize decision maker

        Args:
            members: List of council members
            consensus_algorithm: Algorithm for consensus building
            max_iterations: Maximum deliberation iterations
            min_consensus_quality: Minimum acceptable consensus quality
        """
        self.members = members
        self.consensus_algorithm = consensus_algorithm
        self.max_iterations = max_iterations
        self.min_consensus_quality = min_consensus_quality

        self.current_phase = DeliberationPhase.INDEPENDENT_ANALYSIS
        self.iteration = 0

        logger.info(
            f"Decision maker initialized with {len(members)} members, "
            f"algorithm: {consensus_algorithm.value}"
        )

    async def deliberate(
        self,
        context: DeliberationContext
    ) -> DeliberationRecord:
        """
        Execute full deliberation protocol

        Args:
            context: Decision context and data

        Returns:
            DeliberationRecord with consensus decision
        """
        logger.info(f"Starting deliberation: {context.decision_id}")
        started_at = datetime.utcnow()

        phase_history = []

        # Phase 1: Independent Analysis
        logger.info("Phase 1: Independent Analysis")
        self.current_phase = DeliberationPhase.INDEPENDENT_ANALYSIS
        opinions = await self._phase_1_independent_analysis(context)
        phase_history.append({
            "phase": DeliberationPhase.INDEPENDENT_ANALYSIS.value,
            "timestamp": datetime.utcnow(),
            "opinions_count": len(opinions)
        })

        # Phase 2: Structured Debate
        logger.info("Phase 2: Structured Debate")
        self.current_phase = DeliberationPhase.STRUCTURED_DEBATE
        debate_insights = await self._phase_2_structured_debate(opinions)
        phase_history.append({
            "phase": DeliberationPhase.STRUCTURED_DEBATE.value,
            "timestamp": datetime.utcnow(),
            "insights": debate_insights
        })

        # Phase 3: Iterative Refinement
        logger.info("Phase 3: Iterative Refinement")
        self.current_phase = DeliberationPhase.ITERATIVE_REFINEMENT

        for iteration in range(self.max_iterations):
            self.iteration = iteration + 1
            logger.info(f"Iteration {self.iteration}/{self.max_iterations}")

            converged = await self._phase_3_iterative_refinement(
                context,
                opinions,
                iteration
            )

            if converged:
                logger.info(f"Converged after {self.iteration} iterations")
                break

        phase_history.append({
            "phase": DeliberationPhase.ITERATIVE_REFINEMENT.value,
            "timestamp": datetime.utcnow(),
            "iterations": self.iteration
        })

        # Phase 4: Consensus Building
        logger.info("Phase 4: Consensus Building")
        self.current_phase = DeliberationPhase.CONSENSUS_BUILDING
        votes = await self._phase_4_consensus_building(context)
        consensus = await self._build_consensus(votes, context)
        phase_history.append({
            "phase": DeliberationPhase.CONSENSUS_BUILDING.value,
            "timestamp": datetime.utcnow(),
            "consensus_quality": consensus.consensus_quality()
        })

        # Phase 5: Meta-Decision (Validation)
        logger.info("Phase 5: Meta-Decision")
        self.current_phase = DeliberationPhase.META_DECISION
        validated = await self._phase_5_meta_decision(consensus, context)
        phase_history.append({
            "phase": DeliberationPhase.META_DECISION.value,
            "timestamp": datetime.utcnow(),
            "validated": validated
        })

        self.current_phase = DeliberationPhase.COMPLETED

        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()

        record = DeliberationRecord(
            context=context,
            members=[m.member_id for m in self.members],
            opinions=opinions,
            votes=votes,
            consensus=consensus,
            phase_history=phase_history,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration
        )

        logger.info(
            f"Deliberation completed: decision={consensus.decision_value:.2f}, "
            f"quality={consensus.consensus_quality():.2f}, "
            f"duration={duration:.1f}s"
        )

        return record

    async def _phase_1_independent_analysis(
        self,
        context: DeliberationContext
    ) -> List[Opinion]:
        """
        Phase 1: Each member analyzes independently without communication

        Returns list of initial opinions
        """
        opinions = await asyncio.gather(*[
            member.analyze_independently(context.data)
            for member in self.members
        ])

        logger.info(f"Collected {len(opinions)} independent opinions")

        return list(opinions)

    async def _phase_2_structured_debate(
        self,
        opinions: List[Opinion]
    ) -> Dict[str, Any]:
        """
        Phase 2: Members present positions and challenge each other

        Returns insights from debate
        """
        challenges_issued = 0

        # Round-robin presentations with challenges
        for i, member in enumerate(self.members):
            opinion = opinions[i]

            logger.info(
                f"Member {member.member_id} presents: {opinion.position[:50]}..."
            )

            # Other members challenge this opinion
            for j, other_member in enumerate(self.members):
                if i == j:
                    continue

                challenges = other_member.challenge_opinion(opinion)
                if challenges:
                    challenges_issued += len(challenges)
                    opinion.counter_arguments.extend(challenges)

                    logger.debug(
                        f"Member {other_member.member_id} issued {len(challenges)} challenges"
                    )

        insights = {
            "challenges_issued": challenges_issued,
            "avg_challenges_per_opinion": challenges_issued / len(opinions) if opinions else 0
        }

        logger.info(f"Debate complete: {challenges_issued} challenges issued")

        return insights

    async def _phase_3_iterative_refinement(
        self,
        context: DeliberationContext,
        opinions: List[Opinion],
        iteration: int
    ) -> bool:
        """
        Phase 3: Members update beliefs based on collective wisdom

        Returns True if converged (beliefs stable)
        """
        # Calculate collective wisdom (aggregated statistics)
        opinion_values = [
            1.0 if "approve" in op.position.lower() or "support" in op.position.lower()
            else 0.5 if "neutral" in op.position.lower()
            else 0.3
            for op in opinions
        ]

        collective_wisdom = {
            "mean_support": sum(opinion_values) / len(opinion_values),
            "std_support": (sum((x - sum(opinion_values)/len(opinion_values))**2 for x in opinion_values) / len(opinion_values)) ** 0.5,
            "alignment_score": 0.5  # Simplified
        }

        # Members update beliefs (Bayesian updating)
        prior_confidences = [op.confidence for op in opinions]

        for member in self.members:
            member.update_belief(collective_wisdom, iteration)

        posterior_confidences = [m.current_opinion.confidence for m in self.members if m.current_opinion]

        # Check convergence: if beliefs changed < 5%, we've converged
        if prior_confidences and posterior_confidences:
            max_change = max(abs(post - prior) for post, prior in zip(posterior_confidences, prior_confidences))
            converged = max_change < 0.05

            logger.info(f"Max belief change: {max_change:.3f}, converged: {converged}")

            return converged

        return False

    async def _phase_4_consensus_building(
        self,
        context: DeliberationContext
    ) -> List[Vote]:
        """
        Phase 4: Members cast final votes

        Returns list of votes
        """
        votes = []

        for member in self.members:
            # Calculate expertise relevance for this decision
            expertise_relevance = self._calculate_expertise_relevance(
                member,
                context
            )

            vote = member.cast_vote(context.data, expertise_relevance)
            votes.append(vote)

        logger.info(f"Collected {len(votes)} votes")

        return votes

    def _calculate_expertise_relevance(
        self,
        member: CouncilMember,
        context: DeliberationContext
    ) -> float:
        """
        Calculate how relevant member's expertise is to this decision

        Returns score from 0.0 (not relevant) to 1.0 (highly relevant)
        """
        # Check if decision domain matches member expertise
        decision_domain = context.department or "general"

        if decision_domain in member.domain_expertise:
            return 0.9
        elif any(domain in decision_domain for domain in member.domain_expertise):
            return 0.7
        else:
            return 0.5  # General relevance

    async def _build_consensus(
        self,
        votes: List[Vote],
        context: DeliberationContext
    ) -> ConsensusResult:
        """
        Build consensus from votes using configured algorithm
        """
        builder = create_consensus_builder(self.consensus_algorithm)
        consensus = await builder.build_consensus(votes, context.data)

        return consensus

    async def _phase_5_meta_decision(
        self,
        consensus: ConsensusResult,
        context: DeliberationContext
    ) -> bool:
        """
        Phase 5: Validate consensus for quality and consistency

        Returns True if consensus is validated
        """
        # Check 1: Consensus quality above minimum threshold
        quality = consensus.consensus_quality()
        if quality < self.min_consensus_quality:
            logger.warning(
                f"Consensus quality {quality:.2f} below threshold "
                f"{self.min_consensus_quality:.2f}"
            )
            return False

        # Check 2: Logical consistency
        # If decision value is high (approve) but confidence is low, flag for review
        if consensus.decision_value > 0.7 and consensus.confidence < 0.5:
            logger.warning(
                "Inconsistency: High approval with low confidence - requires review"
            )
            return False

        # Check 3: Evidence quality
        if len(consensus.supporting_evidence) < 2:
            logger.warning("Insufficient supporting evidence")
            return False

        # Check 4: Risk assessment for critical decisions
        if context.authority_level == "critical":
            if consensus.agreement_level < 0.8:
                logger.warning(
                    f"Critical decision requires 80%+ agreement, got {consensus.agreement_level:.0%}"
                )
                return False

        logger.info(
            f"Consensus validated: quality={quality:.2f}, "
            f"decision={consensus.decision_value:.2f}"
        )

        return True

    def get_phase_status(self) -> Dict[str, Any]:
        """Get current deliberation phase status"""
        return {
            "current_phase": self.current_phase.value,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "member_count": len(self.members)
        }
