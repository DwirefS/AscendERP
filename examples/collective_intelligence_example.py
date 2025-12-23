"""
Collective Intelligence Architecture - Comprehensive Example

Demonstrates the complete implementation of:
1. Decision-Making Councils (Executive, Finance)
2. Mixture of Experts (MoE) routing and aggregation
3. Hierarchical coordination between councils
4. Dual-objective optimization (Sustainability + Profitability)

Scenario: Enterprise decides whether to invest in green data center infrastructure

Business Context:
- Investment: $5M capital expenditure
- Decision involves: Finance, Technology, Sustainability
- Dual objectives: Profitability (ROI) AND Sustainability (carbon reduction)
- Requires Executive Council approval (> $1M budget authority)

The example shows:
- MoE routing to domain experts (Finance, Tech, Sustainability)
- Expert analysis and confidence scores
- Finance Council deliberation
- Executive Council ratification
- Consensus building with diverse perspectives
- Dual-objective optimization balancing profit + sustainability
"""

import asyncio
import logging
from datetime import datetime

# Council components
from src.agents.councils.executive_council import create_executive_council
from src.agents.councils.finance_council import create_finance_council

# MoE components
from src.core.moe.moe_agent import (
    MoEAgent,
    MoEConfig,
    DomainExpert,
    ExpertType,
    ConfidenceGate,
    WeightedAverageAggregator
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """
    Execute comprehensive collective intelligence example
    """
    logger.info("="*80)
    logger.info("COLLECTIVE INTELLIGENCE ARCHITECTURE - COMPREHENSIVE EXAMPLE")
    logger.info("="*80)

    # ========================================================================
    # SCENARIO SETUP: Green Data Center Investment Decision
    # ========================================================================

    decision_context = {
        "decision_id": "green_datacenter_2025",
        "description": "Invest $5M in renewable-powered data center infrastructure",
        "domain": "technology",
        "budget_amount": 5_000_000,
        "involves_compliance": True,
        "is_cross_functional": True,
        "complexity": "high",
        "risk_level": "medium",

        # Business case data
        "investment_details": {
            "capex": 5_000_000,
            "annual_opex_savings": 800_000,  # Energy cost savings
            "payback_period_years": 6.25,
            "npv_10_years": 2_100_000,
            "irr": 0.12,  # 12% internal rate of return
        },

        # Sustainability impact
        "sustainability_impact": {
            "carbon_reduction_tons_per_year": 1200,
            "renewable_energy_percentage": 95,
            "esg_rating_improvement": 15,  # points
            "compliance": ["ISO 14001", "Science Based Targets"]
        },

        # Technology considerations
        "technology_details": {
            "location": "Pacific Northwest (renewable grid)",
            "capacity_increase": "40%",
            "power_usage_effectiveness": 1.15,  # Industry-leading
            "estimated_uptime": 0.999  # 99.9% SLA
        }
    }

    # ========================================================================
    # STEP 1: MIXTURE OF EXPERTS ANALYSIS
    # ========================================================================

    logger.info("\n" + "="*80)
    logger.info("STEP 1: MIXTURE OF EXPERTS (MoE) ANALYSIS")
    logger.info("="*80)

    # Create domain experts
    finance_expert = DomainExpert(
        expert_id="finance_expert",
        expert_type=ExpertType.FINANCE,
        domain=["finance", "investment", "roi"]
    )

    sustainability_expert = DomainExpert(
        expert_id="sustainability_expert",
        expert_type=ExpertType.SUSTAINABILITY,
        domain=["sustainability", "esg", "carbon"]
    )

    technology_expert = DomainExpert(
        expert_id="technology_expert",
        expert_type=ExpertType.TECHNOLOGY,
        domain=["technology", "infrastructure", "datacenter"]
    )

    legal_expert = DomainExpert(
        expert_id="legal_expert",
        expert_type=ExpertType.LEGAL,
        domain=["legal", "compliance", "regulatory"]
    )

    # Create MoE agent
    moe_config = MoEConfig(
        moe_id="datacenter_moe",
        gating_strategy="confidence",
        aggregation_strategy="weighted_average",
        top_k_experts=3,
        min_confidence_threshold=0.5
    )

    moe_agent = MoEAgent(
        config=moe_config,
        experts=[finance_expert, sustainability_expert, technology_expert, legal_expert],
        gating_network=ConfidenceGate(),
        aggregator=WeightedAverageAggregator()
    )

    # MoE processes the decision
    logger.info("\nMoE routing to appropriate experts...")
    moe_result = await moe_agent.process_task(decision_context)

    logger.info(f"\n✓ MoE Analysis Complete")
    logger.info(f"  - Experts consulted: {moe_result['experts_consulted']}")
    logger.info(f"  - Aggregated confidence: {moe_result['confidence']:.2f}")
    logger.info(f"  - Reasoning: {moe_result['reasoning'][:150]}...")

    # ========================================================================
    # STEP 2: FINANCE COUNCIL DELIBERATION
    # ========================================================================

    logger.info("\n" + "="*80)
    logger.info("STEP 2: FINANCE COUNCIL DELIBERATION")
    logger.info("="*80)

    # Create Finance Council
    finance_council = create_finance_council()

    logger.info(f"\n✓ Finance Council convened:")
    logger.info(f"  - Council: {finance_council.config.name}")
    logger.info(f"  - Members: {len(finance_council.members)}")
    logger.info(f"  - Decision threshold: {finance_council.config.decision_threshold:.0%}")
    logger.info(f"  - Budget authority: ${finance_council.config.budget_authority:,.0f}")

    # Finance Council deliberates
    logger.info("\nFinance Council deliberation in progress...")
    logger.info("  Phase 1: Independent Analysis (each member analyzes separately)")
    logger.info("  Phase 2: Structured Debate (members challenge each other)")
    logger.info("  Phase 3: Iterative Refinement (Bayesian belief updates)")
    logger.info("  Phase 4: Consensus Building (weighted voting)")
    logger.info("  Phase 5: Meta-Decision (validation)")

    finance_decision = await finance_council.convene(
        decision_id=decision_context["decision_id"],
        decision_type="tactical",
        description=decision_context["description"],
        data=decision_context,
        department="finance",
        budget_amount=decision_context["budget_amount"]
    )

    logger.info(f"\n✓ Finance Council Decision:")
    logger.info(f"  - Decision value: {finance_decision.consensus.decision_value:.2f}")
    logger.info(f"  - Confidence: {finance_decision.consensus.confidence:.2f}")
    logger.info(f"  - Agreement level: {finance_decision.consensus.agreement_level:.0%}")
    logger.info(f"  - Consensus quality: {finance_decision.consensus.consensus_quality():.2f}")
    logger.info(f"  - Duration: {finance_decision.duration_seconds:.1f}s")
    logger.info(f"  - Iterations: {finance_decision.consensus.iterations}")

    # Check if escalation required (budget exceeds authority)
    if decision_context["budget_amount"] > finance_council.config.budget_authority:
        logger.info(f"\n⚠️  Budget ${decision_context['budget_amount']:,.0f} exceeds Finance Council authority")
        logger.info(f"   Escalating to Executive Council for ratification...")

        # ========================================================================
        # STEP 3: EXECUTIVE COUNCIL RATIFICATION
        # ========================================================================

        logger.info("\n" + "="*80)
        logger.info("STEP 3: EXECUTIVE COUNCIL RATIFICATION")
        logger.info("="*80)

        # Create Executive Council
        executive_council = create_executive_council()

        logger.info(f"\n✓ Executive Council convened:")
        logger.info(f"  - Council: {executive_council.config.name}")
        logger.info(f"  - Members: {len(executive_council.members)} (C-suite)")
        logger.info(f"  - Decision threshold: {executive_council.config.decision_threshold:.0%} (super-majority)")
        logger.info(f"  - Budget authority: ${executive_council.config.budget_authority:,.0f}")

        # Add Finance Council recommendation to context
        executive_context = {
            **decision_context,
            "finance_council_recommendation": {
                "decision_value": finance_decision.consensus.decision_value,
                "confidence": finance_decision.consensus.confidence,
                "rationale": finance_decision.consensus.rationale,
                "consensus_quality": finance_decision.consensus.consensus_quality()
            },
            "moe_analysis": moe_result
        }

        # Executive Council deliberates
        logger.info("\nExecutive Council deliberation in progress...")
        logger.info("  Reviewing Finance Council recommendation...")
        logger.info("  Evaluating dual objectives: Profitability AND Sustainability...")

        executive_decision = await executive_council.convene(
            decision_id=decision_context["decision_id"] + "_executive",
            decision_type="strategic",
            description=decision_context["description"],
            data=executive_context,
            department="executive",
            budget_amount=decision_context["budget_amount"],
            authority_level="critical"
        )

        logger.info(f"\n✓ Executive Council Decision:")
        logger.info(f"  - Decision value: {executive_decision.consensus.decision_value:.2f}")
        logger.info(f"  - Confidence: {executive_decision.consensus.confidence:.2f}")
        logger.info(f"  - Agreement level: {executive_decision.consensus.agreement_level:.0%}")
        logger.info(f"  - Consensus quality: {executive_decision.consensus.consensus_quality():.2f}")
        logger.info(f"  - Duration: {executive_decision.duration_seconds:.1f}s")

    # ========================================================================
    # STEP 4: DUAL-OBJECTIVE OPTIMIZATION ANALYSIS
    # ========================================================================

    logger.info("\n" + "="*80)
    logger.info("STEP 4: DUAL-OBJECTIVE OPTIMIZATION (Sustainability + Profitability)")
    logger.info("="*80)

    # Calculate dual-objective score
    # Score = α * Profitability + β * Sustainability
    # α = 0.6 (profitability weight), β = 0.4 (sustainability weight)

    # Profitability score (normalized 0-1)
    roi_score = min(decision_context["investment_details"]["irr"] / 0.20, 1.0)  # 12% IRR vs 20% target
    npv_positive = 1.0 if decision_context["investment_details"]["npv_10_years"] > 0 else 0.0
    profitability_score = (roi_score + npv_positive) / 2

    # Sustainability score (normalized 0-1)
    carbon_reduction_score = min(decision_context["sustainability_impact"]["carbon_reduction_tons_per_year"] / 1500, 1.0)
    renewable_energy_score = decision_context["sustainability_impact"]["renewable_energy_percentage"] / 100
    sustainability_score = (carbon_reduction_score + renewable_energy_score) / 2

    # Dual-objective score
    alpha = 0.6  # Profitability weight
    beta = 0.4   # Sustainability weight
    dual_objective_score = alpha * profitability_score + beta * sustainability_score

    logger.info(f"\n✓ Dual-Objective Optimization:")
    logger.info(f"  PROFITABILITY METRICS:")
    logger.info(f"    - IRR: {decision_context['investment_details']['irr']:.1%}")
    logger.info(f"    - NPV (10 years): ${decision_context['investment_details']['npv_10_years']:,.0f}")
    logger.info(f"    - Payback period: {decision_context['investment_details']['payback_period_years']:.1f} years")
    logger.info(f"    - Profitability score: {profitability_score:.2f}/1.0")

    logger.info(f"\n  SUSTAINABILITY METRICS:")
    logger.info(f"    - Carbon reduction: {decision_context['sustainability_impact']['carbon_reduction_tons_per_year']:,.0f} tons/year")
    logger.info(f"    - Renewable energy: {decision_context['sustainability_impact']['renewable_energy_percentage']}%")
    logger.info(f"    - ESG rating improvement: +{decision_context['sustainability_impact']['esg_rating_improvement']} points")
    logger.info(f"    - Sustainability score: {sustainability_score:.2f}/1.0")

    logger.info(f"\n  DUAL-OBJECTIVE SCORE:")
    logger.info(f"    - Formula: {alpha} * Profitability + {beta} * Sustainability")
    logger.info(f"    - Score: {dual_objective_score:.2f}/1.0")

    if dual_objective_score >= 0.7:
        logger.info(f"    - Assessment: ✅ STRONG PARETO-OPTIMAL SOLUTION")
        logger.info(f"      Both objectives achieved without sacrificing either")
    elif dual_objective_score >= 0.5:
        logger.info(f"    - Assessment: ⚠️  ACCEPTABLE TRADE-OFF")
        logger.info(f"      Balanced but room for improvement")
    else:
        logger.info(f"    - Assessment: ❌ INSUFFICIENT VALUE")
        logger.info(f"      Fails to meet dual-objective criteria")

    # ========================================================================
    # FINAL DECISION SUMMARY
    # ========================================================================

    logger.info("\n" + "="*80)
    logger.info("FINAL DECISION SUMMARY")
    logger.info("="*80)

    final_approved = (
        executive_decision.consensus.decision_value >= executive_council.config.decision_threshold
        and dual_objective_score >= 0.7
    )

    logger.info(f"\n{'✅ DECISION APPROVED' if final_approved else '❌ DECISION REJECTED'}")
    logger.info(f"\nDecision: {decision_context['description']}")
    logger.info(f"Investment: ${decision_context['budget_amount']:,.0f}")

    logger.info(f"\nGOVERNANCE PROCESS:")
    logger.info(f"  1. MoE Analysis:")
    logger.info(f"     - {len(moe_result['experts_consulted'])} experts consulted")
    logger.info(f"     - Confidence: {moe_result['confidence']:.2f}")

    logger.info(f"\n  2. Finance Council:")
    logger.info(f"     - Decision: {finance_decision.consensus.decision_value:.2f}")
    logger.info(f"     - Confidence: {finance_decision.consensus.confidence:.2f}")
    logger.info(f"     - Quality: {finance_decision.consensus.consensus_quality():.2f}")

    logger.info(f"\n  3. Executive Council:")
    logger.info(f"     - Decision: {executive_decision.consensus.decision_value:.2f}")
    logger.info(f"     - Confidence: {executive_decision.consensus.confidence:.2f}")
    logger.info(f"     - Quality: {executive_decision.consensus.consensus_quality():.2f}")

    logger.info(f"\n  4. Dual-Objective Score:")
    logger.info(f"     - Profitability: {profitability_score:.2f}")
    logger.info(f"     - Sustainability: {sustainability_score:.2f}")
    logger.info(f"     - Combined: {dual_objective_score:.2f}")

    if final_approved:
        logger.info(f"\n✅ OUTCOME: PROCEED WITH INVESTMENT")
        logger.info(f"   - Strong consensus across all governance layers")
        logger.info(f"   - Dual objectives (profit + sustainability) both achieved")
        logger.info(f"   - Expected ROI: {decision_context['investment_details']['irr']:.1%}")
        logger.info(f"   - Carbon reduction: {decision_context['sustainability_impact']['carbon_reduction_tons_per_year']:,.0f} tons/year")
    else:
        logger.info(f"\n❌ OUTCOME: REJECT INVESTMENT")
        logger.info(f"   - Insufficient consensus or dual-objective score")
        logger.info(f"   - Recommendation: Revise proposal to improve profitability or sustainability")

    # ========================================================================
    # PERFORMANCE METRICS
    # ========================================================================

    logger.info("\n" + "="*80)
    logger.info("COLLECTIVE INTELLIGENCE PERFORMANCE METRICS")
    logger.info("="*80)

    logger.info(f"\nCOUNCIL PERFORMANCE:")
    finance_perf = finance_council.get_member_performance()
    executive_perf = executive_council.get_member_performance()

    logger.info(f"\n  Finance Council Members:")
    for member_id, perf in list(finance_perf.items())[:3]:
        logger.info(f"    - {member_id}: accuracy={perf['accuracy_history']:.2f}, votes={perf['total_votes']}")

    logger.info(f"\n  Executive Council Members:")
    for member_id, perf in list(executive_perf.items())[:3]:
        logger.info(f"    - {member_id}: accuracy={perf['accuracy_history']:.2f}, votes={perf['total_votes']}")

    logger.info(f"\nMoE EXPERT PERFORMANCE:")
    expert_perf = moe_agent.get_expert_performance()
    for expert_id, performance in expert_perf.items():
        logger.info(f"  - {expert_id}: {performance:.2f}")

    logger.info(f"\nCONDORCET JURY THEOREM VALIDATION:")
    logger.info(f"  - Individual agent accuracy: ~0.70 (70%)")
    logger.info(f"  - Council size: 7 members")
    logger.info(f"  - Theoretical collective accuracy: ~0.87 (87%)")
    logger.info(f"  - Improvement: +24% over individual decision-maker")
    logger.info(f"  - Conclusion: Councils mathematically superior to single agents ✅")

    logger.info("\n" + "="*80)
    logger.info("EXAMPLE COMPLETE")
    logger.info("="*80)


if __name__ == "__main__":
    asyncio.run(main())
