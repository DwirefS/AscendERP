"""
S&OP Council - Manufacturing Flavor

Sales & Operations Planning council: production planner (synthesizer),
procurement lead (domain expert) and inventory controller (data driven)
deliberate a demand-supply plan using the core council machinery (weighted
voting). Accepts an optional swarm ScenarioReport (object or dict) as
deliberation evidence; its risks are factored into the decision rationale
and adjustments.
"""
import uuid
from typing import Any, Dict, List, Optional

import structlog

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm

logger = structlog.get_logger()


def create_sop_council() -> BaseCouncil:
    """Create the underlying BaseCouncil for S&OP deliberations."""
    config = CouncilConfig(
        council_id="mfg_sop_council",
        council_type=CouncilType.DEPARTMENT,
        name="Manufacturing S&OP Council",
        description="Demand-supply plan deliberation for the plant",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.50,
        max_iterations=3,
        min_consensus_quality=0.60,
        meeting_frequency="weekly",
        quorum_required=3,
    )

    members = [
        CouncilMember(
            member_id="production_planner",
            role=MemberRole.SYNTHESIZER,
            domain_expertise=["planning", "scheduling", "capacity", "manufacturing"],
            base_accuracy=0.86,
        ),
        CouncilMember(
            member_id="procurement_lead",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["procurement", "suppliers", "lead_times", "manufacturing"],
            base_accuracy=0.84,
        ),
        CouncilMember(
            member_id="inventory_controller",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["inventory", "safety_stock", "abc_analysis", "manufacturing"],
            base_accuracy=0.85,
        ),
    ]

    return BaseCouncil(config=config, members=members)


class SOPCouncil:
    """Decide()-style wrapper around the S&OP BaseCouncil."""

    def __init__(self, council: Optional[BaseCouncil] = None):
        self.council = council or create_sop_council()

    async def decide(
        self,
        plan: Dict[str, Any],
        scenario_report: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Deliberate a demand-supply plan.

        Args:
            plan: plan summary dict (e.g. shortages, capacity, open orders)
            scenario_report: optional swarm ScenarioReport (object or dict)
                used as evidence; its risks are folded into the rationale.

        Returns decision dict with approved, consensus_score, rationale,
        risks_considered, adjustments and per-member votes.
        """
        report = self._normalize_report(scenario_report)
        risks: List[str] = list(report.get("risks", []))
        recommendations: List[str] = list(report.get("recommendations", []))

        record = await self.council.convene(
            decision_id=f"sop-{uuid.uuid4().hex[:8]}",
            decision_type="tactical",
            description="Approve demand-supply plan for the planning horizon",
            data={"plan": plan, "scenario_report": report},
            department="manufacturing",
        )
        consensus = record.consensus

        adjustments = self._derive_adjustments(plan, risks)

        rationale_parts = [
            f"S&OP weighted consensus {consensus.decision_value:.2f} "
            f"(threshold {self.council.config.decision_threshold:.2f})"
        ]
        if risks:
            rationale_parts.append(
                "Scenario risks factored into decision: " + "; ".join(risks)
            )
        if recommendations:
            rationale_parts.append(
                "Scenario recommendations: " + "; ".join(recommendations)
            )
        if plan.get("shortages"):
            rationale_parts.append(
                f"{len(plan['shortages'])} material shortage(s) require "
                "expedited procurement"
            )

        approved = consensus.is_approved(self.council.config.decision_threshold)

        decision = {
            "approved": approved,
            "consensus_score": round(consensus.decision_value, 3),
            "rationale": ". ".join(rationale_parts),
            "risks_considered": risks,
            "recommendations": recommendations,
            "adjustments": adjustments,
            "scenario_considered": scenario_report is not None,
            "votes": {
                v.member_id: round(v.decision_value, 3) for v in record.votes
            },
        }
        logger.info(
            "sop_council_decision",
            approved=approved,
            consensus=decision["consensus_score"],
            risks=len(risks),
        )
        return decision

    @staticmethod
    def _normalize_report(scenario_report: Optional[Any]) -> Dict[str, Any]:
        """Accept a ScenarioReport dataclass, a dict, or None."""
        if scenario_report is None:
            return {}
        if isinstance(scenario_report, dict):
            return scenario_report
        if hasattr(scenario_report, "summary"):
            return scenario_report.summary()
        return {
            "risks": list(getattr(scenario_report, "risks", [])),
            "recommendations": list(
                getattr(scenario_report, "recommendations", [])
            ),
            "kpi_impact": dict(getattr(scenario_report, "kpi_impact", {})),
        }

    @staticmethod
    def _derive_adjustments(
        plan: Dict[str, Any],
        risks: List[str],
    ) -> List[str]:
        """Deterministic plan adjustments from plan gaps and scenario risks."""
        adjustments: List[str] = []

        for shortage in plan.get("shortages", []):
            material = (
                shortage.get("material_id", "unknown")
                if isinstance(shortage, dict) else str(shortage)
            )
            adjustments.append(f"Expedite procurement for {material}")

        capacity = plan.get("capacity", {})
        for wc, info in capacity.items():
            if isinstance(info, dict) and info.get("overloaded"):
                adjustments.append(
                    f"Offload or add shifts at work center {wc}"
                )

        for risk in risks:
            lowered = risk.lower()
            if "supplier" in lowered:
                adjustments.append(
                    f"Mitigate supply risk via alternate sourcing: {risk}"
                )
            elif "demand" in lowered:
                adjustments.append(
                    f"Rebalance capacity for demand risk: {risk}"
                )
            else:
                adjustments.append(f"Monitor and mitigate: {risk}")

        return adjustments
