"""
Quality Council - Manufacturing Flavor

Disposition decisions for major/critical NonConformanceReports. Members:
quality engineer (domain expert), manufacturing engineer (data driven),
customer quality representative (pessimistic) and compliance officer
(ethical), using the core weighted-voting council machinery.

Policy: critical-severity NCRs always carry requires_human_approval=True in
the decision (HITL gate per design §5).
"""
import uuid
from typing import Any, Dict, Optional

import structlog

from src.core.council.base_council import BaseCouncil, CouncilConfig, CouncilType
from src.core.council.member import CouncilMember, MemberRole
from src.core.council.consensus import ConsensusAlgorithm
from flavors.manufacturing.models import DispositionType, NonConformanceReport

logger = structlog.get_logger()


def create_quality_council() -> BaseCouncil:
    """Create the underlying BaseCouncil for NCR disposition deliberations."""
    config = CouncilConfig(
        council_id="mfg_quality_council",
        council_type=CouncilType.TASK_FORCE,
        name="Manufacturing Quality Council",
        description="Disposition of major and critical non-conformances",
        consensus_algorithm=ConsensusAlgorithm.WEIGHTED_VOTING,
        decision_threshold=0.50,
        max_iterations=3,
        min_consensus_quality=0.60,
        meeting_frequency="as_needed",
        quorum_required=3,
    )

    members = [
        CouncilMember(
            member_id="quality_engineer",
            role=MemberRole.DOMAIN_EXPERT,
            domain_expertise=["quality", "spc", "capability", "manufacturing"],
            base_accuracy=0.87,
        ),
        CouncilMember(
            member_id="manufacturing_engineer",
            role=MemberRole.DATA_DRIVEN,
            domain_expertise=["process", "rework", "routing", "manufacturing"],
            base_accuracy=0.85,
        ),
        CouncilMember(
            member_id="customer_quality_rep",
            role=MemberRole.PESSIMISTIC,
            domain_expertise=["customer_requirements", "field_failures"],
            base_accuracy=0.84,
        ),
        CouncilMember(
            member_id="compliance_officer",
            role=MemberRole.ETHICAL,
            domain_expertise=["regulatory", "traceability", "audit"],
            base_accuracy=0.84,
        ),
    ]

    return BaseCouncil(config=config, members=members)


class QualityCouncil:
    """Decide()-style wrapper around the quality BaseCouncil."""

    def __init__(self, council: Optional[BaseCouncil] = None):
        self.council = council or create_quality_council()

    async def decide(
        self,
        ncr: NonConformanceReport,
        supplier_related: bool = False,
    ) -> Dict[str, Any]:
        """
        Deliberate the disposition of an NCR.

        Deterministic disposition policy:
            critical -> SCRAP (RETURN_TO_SUPPLIER if supplier_related),
                        requires_human_approval=True
            major    -> REWORK (RETURN_TO_SUPPLIER if supplier_related)
            minor    -> USE_AS_IS
        """
        severity = (ncr.severity or "minor").lower()
        disposition = self._disposition_for(severity, supplier_related)
        requires_human_approval = severity == "critical"

        record = await self.council.convene(
            decision_id=f"qc-{uuid.uuid4().hex[:8]}",
            decision_type="operational",
            description=f"Disposition NCR {ncr.ncr_id} (severity {severity})",
            data={
                "ncr_id": ncr.ncr_id,
                "work_order_id": ncr.work_order_id,
                "severity": severity,
                "description": ncr.description,
                "quantity_affected": ncr.quantity_affected,
                "supplier_related": supplier_related,
            },
            department="manufacturing",
            authority_level="critical" if severity == "critical" else "standard",
        )
        consensus = record.consensus

        rationale = (
            f"Quality council weighted consensus {consensus.decision_value:.2f}: "
            f"{severity} NCR dispositioned as {disposition.value}"
        )
        if requires_human_approval:
            rationale += (
                "; critical severity requires human approval before execution"
            )

        decision = {
            "ncr_id": ncr.ncr_id,
            "severity": severity,
            "disposition": disposition,
            "requires_human_approval": requires_human_approval,
            "consensus_score": round(consensus.decision_value, 3),
            "rationale": rationale,
            "votes": {
                v.member_id: round(v.decision_value, 3) for v in record.votes
            },
        }
        logger.info(
            "quality_council_decision",
            ncr_id=ncr.ncr_id,
            severity=severity,
            disposition=disposition.value,
            requires_human_approval=requires_human_approval,
        )
        return decision

    @staticmethod
    def _disposition_for(
        severity: str,
        supplier_related: bool,
    ) -> DispositionType:
        """Deterministic severity -> disposition mapping."""
        if supplier_related and severity in ("major", "critical"):
            return DispositionType.RETURN_TO_SUPPLIER
        if severity == "critical":
            return DispositionType.SCRAP
        if severity == "major":
            return DispositionType.REWORK
        return DispositionType.USE_AS_IS
