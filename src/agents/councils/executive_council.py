"""
Executive Leadership Council

C-suite strategic decision-making council with diverse perspectives.

Members:
- CEO Agent (Synthesizer): Strategic vision, final decision authority
- CFO Agent (Financial): Profit maximization, shareholder value
- CTO Agent (Data-Driven): Technology strategy, evidence-based
- COO Agent (Optimistic): Operations, growth opportunities
- CSO Agent (Ethical): Sustainability, ESG compliance
- Chief Risk Officer (Pessimistic): Risk mitigation
- Chief Strategy Officer (Contrarian): Challenge assumptions
"""

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm


def create_executive_council() -> BaseCouncil:
    """
    Create Executive Leadership Council

    Returns:
        Configured BaseCouncil with C-suite members
    """
    # Council configuration
    config = CouncilConfig(
        council_id="executive_council",
        council_type=CouncilType.EXECUTIVE,
        name="Executive Leadership Council",
        description="C-suite strategic decision-making",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.75,  # 75% super-majority for strategic decisions
        max_iterations=5,  # More iterations for critical decisions
        min_consensus_quality=0.80,
        meeting_frequency="monthly",
        quorum_required=5,  # Need at least 5 of 7 members
        budget_authority=10_000_000,  # $10M decision authority
        requires_ratification=False  # Final authority
    )

    # Create council members
    members = [
        CouncilMember(
            member_id="ceo_agent",
            role=MemberRole.SYNTHESIZER,
            domain_expertise=["strategy", "leadership", "vision"],
            base_accuracy=0.80
        ),
        CouncilMember(
            member_id="cfo_agent",
            role=MemberRole.FINANCIAL,
            domain_expertise=["finance", "accounting", "risk"],
            base_accuracy=0.85
        ),
        CouncilMember(
            member_id="cto_agent",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["technology", "data", "security"],
            base_accuracy=0.82
        ),
        CouncilMember(
            member_id="coo_agent",
            role=MemberRole.OPTIMISTIC,
            domain_expertise=["operations", "supply_chain", "logistics"],
            base_accuracy=0.78
        ),
        CouncilMember(
            member_id="cso_agent",
            role=MemberRole.ETHICAL,
            domain_expertise=["sustainability", "esg", "compliance"],
            base_accuracy=0.80
        ),
        CouncilMember(
            member_id="cro_agent",
            role=MemberRole.PESSIMISTIC,
            domain_expertise=["risk", "compliance", "audit"],
            base_accuracy=0.83
        ),
        CouncilMember(
            member_id="strategy_officer_agent",
            role=MemberRole.CONTRARIAN,
            domain_expertise=["strategy", "market_analysis", "competitive_intelligence"],
            base_accuracy=0.77
        )
    ]

    # Create and return council
    council = BaseCouncil(config=config, members=members)

    return council
