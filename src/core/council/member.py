"""
Council Member - Individual Agent within Decision-Making Council

Implements the council member interface with role specialization and voting.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MemberRole(Enum):
    """
    Roles that council members can assume
    """
    OPTIMISTIC = "optimistic"  # High growth bias, sees opportunities
    PESSIMISTIC = "pessimistic"  # Risk-averse, identifies threats
    DATA_DRIVEN = "data_driven"  # Evidence-based, neutral
    ETHICAL = "ethical"  # Sustainability, compliance focus
    FINANCIAL = "financial"  # Profit maximization focus
    CONTRARIAN = "contrarian"  # Devil's advocate, challenges consensus
    SYNTHESIZER = "synthesizer"  # Integrates perspectives, facilitates
    DOMAIN_EXPERT = "domain_expert"  # Specialized knowledge in specific area


@dataclass
class Vote:
    """
    A vote cast by a council member on a decision
    """
    member_id: str
    decision_value: float  # 0.0 to 1.0 (e.g., 0 = reject, 1 = approve, 0.5 = neutral)
    confidence: float  # 0.0 to 1.0 (how confident in this vote)
    rationale: str
    evidence: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Metadata for weighted voting
    expertise_score: float = 0.5  # Relevance of member's expertise to this decision
    accuracy_history: float = 0.5  # Historical accuracy of this member

    def weight(self) -> float:
        """
        Calculate voting weight based on confidence, expertise, and track record

        Formula: 40% confidence + 30% expertise + 30% historical accuracy
        """
        return (
            self.confidence * 0.4 +
            self.expertise_score * 0.3 +
            self.accuracy_history * 0.3
        )


@dataclass
class Opinion:
    """
    An opinion expressed during council deliberation
    """
    member_id: str
    position: str  # Text description of position
    supporting_arguments: List[str]
    counter_arguments: List[str] = field(default_factory=list)
    data_points: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.5
    iteration: int = 0  # Which deliberation round


class CouncilMember:
    """
    Individual agent participating in a council

    Each member has a role that influences their reasoning and perspective.
    Members engage in structured debate and update beliefs based on evidence.
    """

    def __init__(
        self,
        member_id: str,
        role: MemberRole,
        domain_expertise: List[str],
        base_accuracy: float = 0.7
    ):
        self.member_id = member_id
        self.role = role
        self.domain_expertise = domain_expertise
        self.base_accuracy = base_accuracy

        # Track performance
        self.vote_history: List[Vote] = []
        self.accuracy_history: float = base_accuracy

        # Deliberation state
        self.current_opinion: Optional[Opinion] = None
        self.belief_updates: List[Dict[str, Any]] = []

    async def analyze_independently(
        self,
        decision_context: Dict[str, Any]
    ) -> Opinion:
        """
        Phase 1: Independent analysis without inter-agent communication

        Each member analyzes the decision based on their role and expertise.
        """
        logger.info(f"Member {self.member_id} ({self.role.value}) analyzing independently")

        # Role-specific analysis
        if self.role == MemberRole.OPTIMISTIC:
            opinion = await self._optimistic_analysis(decision_context)
        elif self.role == MemberRole.PESSIMISTIC:
            opinion = await self._pessimistic_analysis(decision_context)
        elif self.role == MemberRole.DATA_DRIVEN:
            opinion = await self._data_driven_analysis(decision_context)
        elif self.role == MemberRole.ETHICAL:
            opinion = await self._ethical_analysis(decision_context)
        elif self.role == MemberRole.FINANCIAL:
            opinion = await self._financial_analysis(decision_context)
        elif self.role == MemberRole.CONTRARIAN:
            opinion = await self._contrarian_analysis(decision_context)
        elif self.role == MemberRole.SYNTHESIZER:
            opinion = await self._synthesizer_analysis(decision_context)
        else:
            opinion = await self._domain_expert_analysis(decision_context)

        self.current_opinion = opinion
        return opinion

    async def _optimistic_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Optimistic member sees opportunities and growth potential"""
        return Opinion(
            member_id=self.member_id,
            position="Opportunities and growth potential",
            supporting_arguments=[
                "Market expansion potential is significant",
                "Innovation opportunities align with trends",
                "Growth trajectory exceeds projections"
            ],
            confidence=0.7,
            iteration=0
        )

    async def _pessimistic_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Pessimistic member identifies risks and threats"""
        return Opinion(
            member_id=self.member_id,
            position="Risk mitigation and threat assessment",
            supporting_arguments=[
                "Market volatility presents downside risk",
                "Competitive threats require defensive strategy",
                "Resource constraints may limit execution"
            ],
            confidence=0.7,
            iteration=0
        )

    async def _data_driven_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Data-driven member focuses on evidence and metrics"""
        return Opinion(
            member_id=self.member_id,
            position="Evidence-based quantitative assessment",
            supporting_arguments=[
                "Historical data shows 15% growth rate",
                "Statistical models predict 85% confidence interval",
                "ROI analysis indicates 2.3x return"
            ],
            data_points=[
                {"metric": "growth_rate", "value": 0.15},
                {"metric": "confidence_interval", "value": 0.85},
                {"metric": "roi", "value": 2.3}
            ],
            confidence=0.8,
            iteration=0
        )

    async def _ethical_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Ethical member evaluates sustainability and compliance"""
        return Opinion(
            member_id=self.member_id,
            position="Sustainability and ethical compliance",
            supporting_arguments=[
                "ESG rating improves by 12 points",
                "Carbon emissions reduced by 25%",
                "Compliance with all regulatory requirements"
            ],
            confidence=0.75,
            iteration=0
        )

    async def _financial_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Financial member maximizes profit and shareholder value"""
        return Opinion(
            member_id=self.member_id,
            position="Profit maximization and shareholder value",
            supporting_arguments=[
                "NPV of $4.2M over 5 years",
                "Payback period of 18 months",
                "Improves operating margin by 3.5%"
            ],
            confidence=0.8,
            iteration=0
        )

    async def _contrarian_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Contrarian member challenges assumptions and consensus"""
        return Opinion(
            member_id=self.member_id,
            position="Critical challenge to assumptions",
            supporting_arguments=[
                "Assumptions may be overly optimistic",
                "Alternative scenarios not fully explored",
                "Risks underestimated in base case"
            ],
            counter_arguments=[
                "Growth projections lack supporting evidence",
                "Competitive response not modeled",
                "Execution risk higher than estimated"
            ],
            confidence=0.6,
            iteration=0
        )

    async def _synthesizer_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Synthesizer member integrates multiple perspectives"""
        return Opinion(
            member_id=self.member_id,
            position="Integrated multi-perspective synthesis",
            supporting_arguments=[
                "Balances growth opportunity with risk management",
                "Sustainability goals align with financial returns",
                "Execution plan addresses identified concerns"
            ],
            confidence=0.7,
            iteration=0
        )

    async def _domain_expert_analysis(self, context: Dict[str, Any]) -> Opinion:
        """Domain expert provides specialized knowledge"""
        expertise_area = self.domain_expertise[0] if self.domain_expertise else "general"
        return Opinion(
            member_id=self.member_id,
            position=f"Specialized {expertise_area} assessment",
            supporting_arguments=[
                f"{expertise_area.title()} best practices support this approach",
                f"Industry benchmarks indicate favorable position",
                f"Technical feasibility confirmed"
            ],
            confidence=0.75,
            iteration=0
        )

    def challenge_opinion(self, other_opinion: Opinion) -> List[str]:
        """
        Challenge another member's opinion based on own perspective

        Returns list of counter-arguments
        """
        challenges = []

        if self.role == MemberRole.CONTRARIAN:
            challenges.extend([
                f"Assumption in '{other_opinion.position}' may be flawed",
                f"Evidence supporting this view is insufficient",
                f"Alternative scenarios contradict this conclusion"
            ])
        elif self.role == MemberRole.PESSIMISTIC:
            challenges.append(f"Risks associated with '{other_opinion.position}' are understated")
        elif self.role == MemberRole.DATA_DRIVEN:
            challenges.append(f"Quantitative evidence for '{other_opinion.position}' is lacking")

        return challenges

    def update_belief(self, collective_wisdom: Dict[str, Any], iteration: int):
        """
        Phase 3: Update beliefs based on council deliberation (Bayesian updating)

        Args:
            collective_wisdom: Aggregated statistics from other members
            iteration: Current deliberation round
        """
        if not self.current_opinion:
            return

        # Bayesian update: adjust confidence based on collective wisdom
        prior_confidence = self.current_opinion.confidence

        # If collective wisdom aligns with our view, increase confidence
        # If diverges, decrease confidence
        alignment_score = collective_wisdom.get("alignment_score", 0.5)

        # Bayesian update formula (simplified)
        posterior_confidence = (
            prior_confidence * 0.7 +
            alignment_score * 0.3
        )

        self.current_opinion.confidence = min(max(posterior_confidence, 0.0), 1.0)
        self.current_opinion.iteration = iteration

        # Log belief update
        self.belief_updates.append({
            "iteration": iteration,
            "prior_confidence": prior_confidence,
            "posterior_confidence": posterior_confidence,
            "alignment_score": alignment_score
        })

        logger.info(
            f"Member {self.member_id} updated belief: "
            f"{prior_confidence:.2f} → {posterior_confidence:.2f}"
        )

    def cast_vote(
        self,
        decision_context: Dict[str, Any],
        expertise_relevance: float = 0.5
    ) -> Vote:
        """
        Cast final vote on the decision

        Args:
            decision_context: Context of the decision being voted on
            expertise_relevance: How relevant member's expertise is (0-1)

        Returns:
            Vote with decision value, confidence, and rationale
        """
        if not self.current_opinion:
            raise ValueError("Must analyze decision before voting")

        # Decision value based on opinion and role
        decision_value = self._calculate_decision_value(decision_context)

        vote = Vote(
            member_id=self.member_id,
            decision_value=decision_value,
            confidence=self.current_opinion.confidence,
            rationale=self.current_opinion.position,
            evidence=self.current_opinion.supporting_arguments,
            expertise_score=expertise_relevance,
            accuracy_history=self.accuracy_history
        )

        self.vote_history.append(vote)

        logger.info(
            f"Member {self.member_id} voted: {decision_value:.2f} "
            f"(weight: {vote.weight():.2f})"
        )

        return vote

    def _calculate_decision_value(self, context: Dict[str, Any]) -> float:
        """
        Calculate decision value (0.0 to 1.0) based on opinion and role

        0.0 = strongly reject
        0.5 = neutral
        1.0 = strongly approve
        """
        if not self.current_opinion:
            return 0.5

        # Base decision value on confidence and role bias
        role_bias = {
            MemberRole.OPTIMISTIC: 0.7,  # Tends to approve
            MemberRole.PESSIMISTIC: 0.3,  # Tends to reject
            MemberRole.DATA_DRIVEN: 0.5,  # Neutral
            MemberRole.ETHICAL: 0.5,
            MemberRole.FINANCIAL: 0.6,
            MemberRole.CONTRARIAN: 0.4,  # Tends to challenge
            MemberRole.SYNTHESIZER: 0.5,
            MemberRole.DOMAIN_EXPERT: 0.5
        }

        base = role_bias.get(self.role, 0.5)

        # Adjust based on confidence and evidence
        confidence_adjustment = (self.current_opinion.confidence - 0.5) * 0.4

        decision_value = base + confidence_adjustment

        return min(max(decision_value, 0.0), 1.0)

    def update_accuracy_history(self, was_correct: bool):
        """
        Update historical accuracy based on outcome of vote

        Uses exponential moving average: new_avg = 0.9 * old_avg + 0.1 * outcome
        """
        outcome_value = 1.0 if was_correct else 0.0
        self.accuracy_history = 0.9 * self.accuracy_history + 0.1 * outcome_value

        logger.info(
            f"Member {self.member_id} accuracy updated: {self.accuracy_history:.2f}"
        )
