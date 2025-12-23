"""
Consensus Building Algorithms for Decision-Making Councils

Implements multiple consensus mechanisms:
1. Weighted Voting - Based on expertise, confidence, and track record
2. Delphi Method - Iterative refinement with anonymized feedback
3. Nash Equilibrium - Game-theoretic negotiation

Based on research:
- Condorcet Jury Theorem
- Diversity Prediction Theorem
- Multi-Agent Cooperative Decision-Making (arXiv:2503.13415, 2025)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional
import logging
import numpy as np
from collections import Counter

from src.core.council.member import Vote, Opinion, CouncilMember

logger = logging.getLogger(__name__)


class ConsensusAlgorithm(Enum):
    """Types of consensus algorithms available"""
    WEIGHTED_VOTING = "weighted_voting"
    DELPHI_METHOD = "delphi_method"
    NASH_EQUILIBRIUM = "nash_equilibrium"
    SIMPLE_MAJORITY = "simple_majority"
    SUPERMAJORITY = "supermajority"  # 75% threshold


@dataclass
class ConsensusResult:
    """
    Result of consensus building process
    """
    decision_value: float  # Final aggregated decision (0.0 to 1.0)
    confidence: float  # Confidence in consensus
    algorithm_used: ConsensusAlgorithm
    votes: List[Vote]

    # Metadata
    agreement_level: float  # How much members agreed (0-1)
    diversity_score: float  # Diversity of opinions (0-1)
    iterations: int = 1  # Number of deliberation rounds

    # Explanation
    rationale: str = ""
    supporting_evidence: List[str] = None

    def __post_init__(self):
        if self.supporting_evidence is None:
            self.supporting_evidence = []

    def is_approved(self, threshold: float = 0.5) -> bool:
        """Check if decision is approved above threshold"""
        return self.decision_value >= threshold

    def consensus_quality(self) -> float:
        """
        Calculate consensus quality score (0-1)

        High quality = High agreement + High confidence + Low diversity penalty
        """
        return (
            self.agreement_level * 0.4 +
            self.confidence * 0.4 +
            (1 - self.diversity_score * 0.2)  # Some diversity is good
        )


class ConsensusBuilder(ABC):
    """
    Abstract base class for consensus building algorithms
    """

    @abstractmethod
    async def build_consensus(
        self,
        votes: List[Vote],
        context: Optional[Dict[str, Any]] = None
    ) -> ConsensusResult:
        """
        Build consensus from votes

        Args:
            votes: List of votes from council members
            context: Additional context for decision

        Returns:
            ConsensusResult with final decision
        """
        pass

    def _calculate_agreement_level(self, votes: List[Vote]) -> float:
        """
        Calculate how much members agreed (0-1)

        Low variance in votes = high agreement
        """
        if not votes:
            return 0.0

        values = [v.decision_value for v in votes]
        variance = np.var(values)

        # Convert variance to agreement (0-1 scale)
        # Variance of 0.0 = perfect agreement (1.0)
        # Variance of 0.25 = no agreement (0.0)
        agreement = max(0.0, 1.0 - (variance / 0.25))

        return agreement

    def _calculate_diversity_score(self, votes: List[Vote]) -> float:
        """
        Calculate diversity of opinions (0-1)

        Based on Diversity Prediction Theorem: diversity reduces collective error
        """
        if not votes:
            return 0.0

        values = [v.decision_value for v in votes]

        # Diversity = standard deviation of votes
        diversity = np.std(values)

        # Normalize to 0-1 scale
        return min(diversity * 2, 1.0)


class WeightedVoting(ConsensusBuilder):
    """
    Weighted majority voting based on expertise, confidence, and track record

    Each vote is weighted by:
    - 40% confidence in this specific decision
    - 30% domain expertise relevance
    - 30% historical accuracy

    Formula:
    decision = Σ (vote_value * weight) / Σ (weight)
    """

    async def build_consensus(
        self,
        votes: List[Vote],
        context: Optional[Dict[str, Any]] = None
    ) -> ConsensusResult:
        """Build consensus via weighted voting"""

        if not votes:
            raise ValueError("Cannot build consensus with no votes")

        logger.info(f"Building consensus via weighted voting from {len(votes)} votes")

        # Calculate weighted average
        total_weight = sum(v.weight() for v in votes)
        weighted_sum = sum(v.decision_value * v.weight() for v in votes)

        decision_value = weighted_sum / total_weight if total_weight > 0 else 0.5

        # Aggregate confidence (weighted)
        confidence = sum(v.confidence * v.weight() for v in votes) / total_weight

        # Calculate agreement and diversity
        agreement_level = self._calculate_agreement_level(votes)
        diversity_score = self._calculate_diversity_score(votes)

        # Aggregate rationale
        rationale_votes = sorted(votes, key=lambda v: v.weight(), reverse=True)
        rationale = f"Consensus (weighted voting): {rationale_votes[0].rationale}"

        # Collect supporting evidence
        all_evidence = []
        for vote in votes:
            all_evidence.extend(vote.evidence)

        result = ConsensusResult(
            decision_value=decision_value,
            confidence=confidence,
            algorithm_used=ConsensusAlgorithm.WEIGHTED_VOTING,
            votes=votes,
            agreement_level=agreement_level,
            diversity_score=diversity_score,
            rationale=rationale,
            supporting_evidence=all_evidence[:5]  # Top 5 pieces of evidence
        )

        logger.info(
            f"Weighted voting result: {decision_value:.2f} "
            f"(confidence: {confidence:.2f}, agreement: {agreement_level:.2f})"
        )

        return result


class DelphiMethod(ConsensusBuilder):
    """
    Iterative Delphi method with anonymized feedback

    Process:
    1. Collect independent opinions (round 1)
    2. Share aggregated statistics (not individual opinions)
    3. Members revise based on collective wisdom
    4. Repeat for N iterations (typically 3-5)
    5. Final aggregation

    Based on: Deliberative Delphi for group decision making
    """

    def __init__(self, max_iterations: int = 3, convergence_threshold: float = 0.05):
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold

    async def build_consensus(
        self,
        votes: List[Vote],
        context: Optional[Dict[str, Any]] = None
    ) -> ConsensusResult:
        """
        Build consensus via Delphi method

        Note: This is simplified - full Delphi requires iterative member updates
        """
        if not votes:
            raise ValueError("Cannot build consensus with no votes")

        logger.info(f"Building consensus via Delphi method ({self.max_iterations} iterations)")

        # For now, simulate single iteration (full implementation would need council access)
        # In production, this would call back to members to update beliefs

        # Calculate statistics to share
        values = [v.decision_value for v in votes]
        stats = {
            "mean": np.mean(values),
            "median": np.median(values),
            "std": np.std(values),
            "min": np.min(values),
            "max": np.max(values)
        }

        logger.info(f"Delphi round 1 stats: mean={stats['mean']:.2f}, std={stats['std']:.2f}")

        # Use median as consensus (robust to outliers)
        decision_value = stats["median"]

        # Confidence based on convergence (low std = high confidence)
        confidence = max(0.0, 1.0 - stats["std"])

        # Calculate agreement and diversity
        agreement_level = self._calculate_agreement_level(votes)
        diversity_score = self._calculate_diversity_score(votes)

        result = ConsensusResult(
            decision_value=decision_value,
            confidence=confidence,
            algorithm_used=ConsensusAlgorithm.DELPHI_METHOD,
            votes=votes,
            agreement_level=agreement_level,
            diversity_score=diversity_score,
            iterations=1,  # Simplified for now
            rationale=f"Delphi consensus: median={decision_value:.2f}, convergence={confidence:.2f}"
        )

        return result


class NashNegotiation(ConsensusBuilder):
    """
    Nash equilibrium-based negotiation

    Finds solution where no agent can improve their utility unilaterally.
    Uses game-theoretic principles to find stable consensus.

    Based on: Cooperative game theory and Nash bargaining solution
    """

    async def build_consensus(
        self,
        votes: List[Vote],
        context: Optional[Dict[str, Any]] = None
    ) -> ConsensusResult:
        """
        Build consensus via Nash equilibrium negotiation

        Nash Bargaining Solution maximizes product of utilities:
        maximize: Π (u_i - d_i)
        where u_i = utility for agent i, d_i = disagreement point
        """
        if not votes:
            raise ValueError("Cannot build consensus with no votes")

        logger.info(f"Building consensus via Nash equilibrium from {len(votes)} votes")

        # Disagreement point (fallback if no agreement) = status quo = 0.5
        disagreement_point = 0.5

        # Each member's utility = distance from their ideal vote to consensus
        # Nash solution: maximize product of (utility - disagreement)

        # Simplified: use weighted average but optimize for fairness
        # In full implementation, would use optimization solver

        # Start with simple average
        current_proposal = np.mean([v.decision_value for v in votes])

        # Iterative improvement (simplified Nash bargaining)
        for iteration in range(5):
            # Calculate each member's utility at current proposal
            utilities = []
            for vote in votes:
                # Utility = negative of distance from ideal (closer = better)
                utility = 1.0 - abs(vote.decision_value - current_proposal)
                utilities.append(utility * vote.weight())

            # Nash product = product of (utility - disagreement)
            nash_product = np.prod([max(u - disagreement_point, 0.01) for u in utilities])

            # Try adjusting proposal in both directions
            epsilon = 0.05
            proposal_up = current_proposal + epsilon
            proposal_down = current_proposal - epsilon

            # Calculate Nash product for each
            nash_up = np.prod([
                max(1.0 - abs(v.decision_value - proposal_up) - disagreement_point, 0.01) * v.weight()
                for v in votes
            ])

            nash_down = np.prod([
                max(1.0 - abs(v.decision_value - proposal_down) - disagreement_point, 0.01) * v.weight()
                for v in votes
            ])

            # Move toward better Nash product
            if nash_up > nash_product and nash_up > nash_down:
                current_proposal = proposal_up
            elif nash_down > nash_product:
                current_proposal = proposal_down
            else:
                break  # Converged

        decision_value = np.clip(current_proposal, 0.0, 1.0)

        # Confidence based on how close to equilibrium
        confidence = min(utilities) if utilities else 0.5

        # Calculate agreement and diversity
        agreement_level = self._calculate_agreement_level(votes)
        diversity_score = self._calculate_diversity_score(votes)

        result = ConsensusResult(
            decision_value=decision_value,
            confidence=confidence,
            algorithm_used=ConsensusAlgorithm.NASH_EQUILIBRIUM,
            votes=votes,
            agreement_level=agreement_level,
            diversity_score=diversity_score,
            rationale=f"Nash equilibrium consensus: {decision_value:.2f}"
        )

        logger.info(f"Nash equilibrium result: {decision_value:.2f}")

        return result


class SimpleMajority(ConsensusBuilder):
    """
    Simple majority voting (> 50% threshold)

    Decision value > 0.5 = approved
    Decision value < 0.5 = rejected
    """

    async def build_consensus(
        self,
        votes: List[Vote],
        context: Optional[Dict[str, Any]] = None
    ) -> ConsensusResult:
        """Build consensus via simple majority"""

        if not votes:
            raise ValueError("Cannot build consensus with no votes")

        # Count approve (> 0.5) vs reject (< 0.5)
        approvals = sum(1 for v in votes if v.decision_value > 0.5)
        rejections = len(votes) - approvals

        decision_value = 1.0 if approvals > rejections else 0.0

        # Confidence = margin of victory
        margin = abs(approvals - rejections) / len(votes)
        confidence = margin

        # Calculate agreement and diversity
        agreement_level = self._calculate_agreement_level(votes)
        diversity_score = self._calculate_diversity_score(votes)

        result = ConsensusResult(
            decision_value=decision_value,
            confidence=confidence,
            algorithm_used=ConsensusAlgorithm.SIMPLE_MAJORITY,
            votes=votes,
            agreement_level=agreement_level,
            diversity_score=diversity_score,
            rationale=f"Simple majority: {approvals}/{len(votes)} approve"
        )

        logger.info(f"Simple majority: {approvals}/{len(votes)} approve")

        return result


class SuperMajority(ConsensusBuilder):
    """
    Super-majority voting (75% threshold for approval)

    Used for critical decisions requiring strong consensus
    """

    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold

    async def build_consensus(
        self,
        votes: List[Vote],
        context: Optional[Dict[str, Any]] = None
    ) -> ConsensusResult:
        """Build consensus via super-majority"""

        if not votes:
            raise ValueError("Cannot build consensus with no votes")

        # Count strong approvals (> 0.7)
        approvals = sum(1 for v in votes if v.decision_value > 0.7)
        approval_rate = approvals / len(votes)

        decision_value = 1.0 if approval_rate >= self.threshold else 0.0

        # Confidence = how far above/below threshold
        confidence = abs(approval_rate - self.threshold)

        # Calculate agreement and diversity
        agreement_level = self._calculate_agreement_level(votes)
        diversity_score = self._calculate_diversity_score(votes)

        result = ConsensusResult(
            decision_value=decision_value,
            confidence=confidence,
            algorithm_used=ConsensusAlgorithm.SUPERMAJORITY,
            votes=votes,
            agreement_level=agreement_level,
            diversity_score=diversity_score,
            rationale=f"Super-majority ({self.threshold*100:.0f}%): {approval_rate*100:.1f}% approve"
        )

        logger.info(
            f"Super-majority: {approval_rate*100:.1f}% approve "
            f"(threshold: {self.threshold*100:.0f}%)"
        )

        return result


def create_consensus_builder(algorithm: ConsensusAlgorithm) -> ConsensusBuilder:
    """
    Factory function to create appropriate consensus builder

    Args:
        algorithm: Type of consensus algorithm to use

    Returns:
        ConsensusBuilder instance
    """
    if algorithm == ConsensusAlgorithm.WEIGHTED_VOTING:
        return WeightedVoting()
    elif algorithm == ConsensusAlgorithm.DELPHI_METHOD:
        return DelphiMethod()
    elif algorithm == ConsensusAlgorithm.NASH_EQUILIBRIUM:
        return NashNegotiation()
    elif algorithm == ConsensusAlgorithm.SIMPLE_MAJORITY:
        return SimpleMajority()
    elif algorithm == ConsensusAlgorithm.SUPERMAJORITY:
        return SuperMajority()
    else:
        raise ValueError(f"Unknown consensus algorithm: {algorithm}")
