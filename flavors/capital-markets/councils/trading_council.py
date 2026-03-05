"""
Trading Council - Capital Markets Flavor

Specialized council for executing equity trades and managing execution quality.
Applies Condorcet Jury Theorem: with 4 members averaging 86% accuracy,
collective accuracy reaches ~95%.

Members:
- Head Trader (Synthesizer): Synthesizes market signals, execution quality, and risk constraints
- Equity Analyst (Domain Expert): Deep fundamental and technical analysis
- Execution Specialist (Data Driven): Quantitative analysis of market microstructure
- Risk Officer (Pessimistic): Worst-case scenario analysis and position limits
"""

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm


def create_trading_council() -> BaseCouncil:
    """
    Create Trading Council for Capital Markets

    Condorcet Jury Theorem Application:
    With N=4 members each with accuracy p=0.86:
    - Collective accuracy = Σ(C(4,k) * p^k * (1-p)^(4-k)) for k > 2
    - Result: ~95% accuracy on consensus decisions

    Weighted voting accounts for:
    - Head Trader's synthesizer expertise (higher weight)
    - Execution Specialist's microstructure knowledge
    - Risk Officer's conservative perspective (devil's advocate)

    Returns:
        Configured BaseCouncil with trading floor members
    """
    config = CouncilConfig(
        council_id="cm_trading_council",
        council_type=CouncilType.TASK_FORCE,
        name="Capital Markets Trading Council",
        description="Real-time trading execution and order routing decisions",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.70,  # 70% weighted majority for execution authority
        max_iterations=3,  # Quick decisions needed on trading floor
        min_consensus_quality=0.75,
        meeting_frequency="continuous",  # Real-time trading decisions
        quorum_required=3,  # Can operate with 3 of 4 members
        budget_authority=10_000_000,  # $10M single trade authority
        requires_ratification=False
    )

    members = [
        CouncilMember(
            member_id="head_trader",
            role=MemberRole.SYNTHESIZER,
            domain_expertise=["trading", "execution", "market_structure", "order_routing"],
            base_accuracy=0.88
        ),
        CouncilMember(
            member_id="equity_analyst",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["equities", "stocks", "fundamental_analysis", "earnings", "sectors"],
            base_accuracy=0.85
        ),
        CouncilMember(
            member_id="execution_specialist",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["market_microstructure", "liquidity", "venue_selection", "slippage"],
            base_accuracy=0.87
        ),
        CouncilMember(
            member_id="risk_officer",
            role=MemberRole.PESSIMISTIC,
            domain_expertise=["risk_management", "position_limits", "counterparty_risk"],
            base_accuracy=0.84
        )
    ]

    council = BaseCouncil(config=config, members=members)

    return council
