"""
Risk Committee - Capital Markets Flavor

Governance body for enterprise risk management and regulatory compliance
in capital markets operations.

Members:
- Chief Risk Officer (Synthesizer): Integrates market, credit, model, and compliance risks
- Market Risk Manager (Domain Expert): VaR, stress testing, market exposure
- Credit Risk Manager (Domain Expert): Counterparty risk, default probability, covenants
- Model Validation (Pessimistic): Devil's advocate for model risk and assumptions
- Compliance Officer (Ethical): Regulatory alignment and ethical standards
"""

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm


def create_risk_committee() -> BaseCouncil:
    """
    Create Risk Committee for Capital Markets

    Governance committee with 5 specialized risk experts providing comprehensive
    risk oversight across market, credit, model, and regulatory dimensions.

    Returns:
        Configured BaseCouncil with enterprise risk management specialists
    """
    config = CouncilConfig(
        council_id="cm_risk_committee",
        council_type=CouncilType.DEPARTMENT,
        name="Capital Markets Risk Committee",
        description="Enterprise risk governance and regulatory compliance",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.65,  # 65% majority for risk approvals
        max_iterations=5,  # More deliberation for risk decisions
        min_consensus_quality=0.70,
        meeting_frequency="daily",  # Daily risk reviews
        quorum_required=4,  # Need 4 of 5 members for quorum
        budget_authority=50_000_000,  # $50M risk authority
        requires_ratification=True  # Escalates to executive council if needed
    )

    members = [
        CouncilMember(
            member_id="chief_risk_officer",
            role=MemberRole.SYNTHESIZER,
            domain_expertise=["risk_management", "enterprise_risk", "governance", "compliance"],
            base_accuracy=0.89
        ),
        CouncilMember(
            member_id="market_risk_manager",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["market_risk", "var", "stress_testing", "market_exposure", "scenario_analysis"],
            base_accuracy=0.87
        ),
        CouncilMember(
            member_id="credit_risk_manager",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["credit_risk", "counterparty_risk", "default_probability", "covenants", "ratings"],
            base_accuracy=0.86
        ),
        CouncilMember(
            member_id="model_validation",
            role=MemberRole.PESSIMISTIC,
            domain_expertise=["model_risk", "backtesting", "validation", "assumptions", "edge_cases"],
            base_accuracy=0.85
        ),
        CouncilMember(
            member_id="compliance_officer",
            role=MemberRole.ETHICAL,
            domain_expertise=["regulatory_compliance", "aml", "kyc", "reporting", "legal"],
            base_accuracy=0.88
        )
    ]

    committee = BaseCouncil(config=config, members=members)

    return committee
