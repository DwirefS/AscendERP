"""
Finance Department Leadership Council

Tactical financial planning and resource allocation.

Members:
- CFO Agent (Chair): Strategic financial direction
- Controller Agent: Financial reporting, compliance
- Treasurer Agent: Cash management, liquidity
- FP&A Agent (Data-Driven): Forecasting, budgeting, analysis
- Tax Agent: Tax strategy, optimization
- Audit Agent (Pessimistic): Internal controls, risk
- Sustainability Liaison (Ethical): ESG reporting, carbon accounting
"""

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm


def create_finance_council() -> BaseCouncil:
    """
    Create Finance Department Leadership Council

    Returns:
        Configured BaseCouncil with finance team members
    """
    # Council configuration
    config = CouncilConfig(
        council_id="finance_council",
        council_type=CouncilType.DEPARTMENT,
        name="Finance Department Leadership Council",
        description="Financial planning and resource allocation",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.65,  # 65% majority for tactical decisions
        max_iterations=3,
        min_consensus_quality=0.70,
        meeting_frequency="weekly",
        quorum_required=4,
        budget_authority=1_000_000,  # $1M decision authority
        requires_ratification=True  # Must be ratified by Executive Council for >$1M
    )

    # Create council members
    members = [
        CouncilMember(
            member_id="cfo_finance_council",
            role=MemberRole.SYNTHESIZER,
            domain_expertise=["finance", "strategy", "risk"],
            base_accuracy=0.85
        ),
        CouncilMember(
            member_id="controller_agent",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["accounting", "gaap", "reporting"],
            base_accuracy=0.88
        ),
        CouncilMember(
            member_id="treasurer_agent",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["treasury", "cash_management", "liquidity"],
            base_accuracy=0.82
        ),
        CouncilMember(
            member_id="fpa_agent",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["forecasting", "budgeting", "analytics"],
            base_accuracy=0.83
        ),
        CouncilMember(
            member_id="tax_agent",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["tax", "transfer_pricing", "compliance"],
            base_accuracy=0.86
        ),
        CouncilMember(
            member_id="audit_agent",
            role=MemberRole.PESSIMISTIC,
            domain_expertise=["audit", "controls", "risk"],
            base_accuracy=0.84
        ),
        CouncilMember(
            member_id="sustainability_liaison",
            role=MemberRole.ETHICAL,
            domain_expertise=["esg", "carbon_accounting", "sustainability"],
            base_accuracy=0.80
        )
    ]

    # Create and return council
    council = BaseCouncil(config=config, members=members)

    return council
