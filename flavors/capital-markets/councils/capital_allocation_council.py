"""
Capital Allocation Council - Capital Markets Flavor

Strategic council for portfolio construction, asset allocation, and capital deployment
decisions optimizing both financial returns and sustainability objectives.

Dual-Objective Optimization:
maximize: α × Profit(x) + β × Sustainability(x)

where:
- α = weight on financial returns (typically 0.8-0.9)
- β = weight on sustainability goals (typically 0.1-0.2)
- x = allocation vector across asset classes

Members:
- Portfolio Director (Synthesizer): Integrates allocation strategies and constraints
- Quant Strategist (Data Driven): Quantitative optimization and factor analysis
- Fixed Income Specialist (Domain Expert): Bond markets and credit allocation
- Chief Economist (Data Driven): Macroeconomic forecasts and cycle positioning
- Sustainability Officer (Ethical): ESG considerations and impact assessment
"""

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm


def create_capital_allocation_council() -> BaseCouncil:
    """
    Create Capital Allocation Council for Capital Markets

    Strategic council balancing financial optimization with sustainability goals.
    Uses dual-objective framework:

    Objective: max(α*Return + β*Sustainability) subject to:
    - Position limits: x_i ≤ L_i
    - Sector concentration: Σ(x_i where sector_i = s) ≤ C_s
    - Leverage: Σ(leverage_i * x_i) ≤ Leverage_max
    - Risk: Portfolio VaR ≤ VaR_threshold
    - ESG score: Portfolio ESG ≥ ESG_minimum

    Returns:
        Configured BaseCouncil with strategic capital allocation specialists
    """
    config = CouncilConfig(
        council_id="cm_capital_allocation",
        council_type=CouncilType.EXECUTIVE,
        name="Capital Allocation Council",
        description="Strategic asset allocation and capital deployment decisions",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.75,  # 75% super-majority for strategic allocations
        max_iterations=5,  # Extensive deliberation for strategic decisions
        min_consensus_quality=0.75,
        meeting_frequency="monthly",  # Monthly strategic reviews
        quorum_required=4,  # Need 4 of 5 members
        budget_authority=100_000_000,  # $100M allocation authority
        requires_ratification=False  # Final authority on allocations
    )

    members = [
        CouncilMember(
            member_id="portfolio_director",
            role=MemberRole.SYNTHESIZER,
            domain_expertise=["portfolio_construction", "strategic_allocation", "asset_classes", "rebalancing"],
            base_accuracy=0.87
        ),
        CouncilMember(
            member_id="quant_strategist",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["quantitative_analysis", "optimization", "factor_analysis", "risk_parity"],
            base_accuracy=0.88
        ),
        CouncilMember(
            member_id="fixed_income_specialist",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["bonds", "fixed_income", "credit_allocation", "duration", "yield_curve"],
            base_accuracy=0.86
        ),
        CouncilMember(
            member_id="chief_economist",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["macroeconomics", "economic_forecasting", "business_cycle", "monetary_policy"],
            base_accuracy=0.85
        ),
        CouncilMember(
            member_id="sustainability_officer",
            role=MemberRole.ETHICAL,
            domain_expertise=["esg", "sustainability", "impact_investing", "climate_risk", "governance"],
            base_accuracy=0.82
        )
    ]

    council = BaseCouncil(config=config, members=members)

    return council
