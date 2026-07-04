"""
Quality Council - Manufacturing Flavor

Disposition decisions for major/critical NonConformanceReports. Members:
quality engineer (domain expert), manufacturing engineer (data driven),
customer quality representative (pessimistic) and compliance officer
(ethical), using the core weighted-voting council machinery.

Deliberation is evidence-weighted (D-022): each member weighs the actual
evidence on the NCR rather than reading a fixed severity lookup table.

  - Quality engineer: any defective units carrying a spec violation
    (quantity_affected > 0) can never ship as USE_AS_IS; a minor NCR with
    zero defective units is a control signal only.
  - Manufacturing engineer (economics): when rework_cost_per_unit and
    unit_value are both known, REWORK only while economical
    (rework_cost_per_unit < unit_value), otherwise SCRAP.
  - Compliance officer: critical severity -> SCRAP (RETURN_TO_SUPPLIER when
    supplier material) with requires_human_approval=True; supplier-related
    major/critical defects go back to the supplier. Unchanged HITL gate per
    design §5.
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
        rework_cost_per_unit: Optional[float] = None,
        unit_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Deliberate the disposition of an NCR by weighing member evidence.

        Args:
            ncr: the non-conformance report under deliberation.
            supplier_related: True when the defect originates in purchased
                material (compliance member routes it back to the supplier).
            rework_cost_per_unit: optional cost to rework one affected unit;
                enables the economics member's REWORK-vs-SCRAP position.
            unit_value: optional standard/replacement value per unit; the
                economics comparison baseline.

        Evidence-weighted resolution (D-022), replacing the old fixed
        severity->disposition lookup that shipped defective minor-NCR units
        as USE_AS_IS and reworked uneconomical major lots:
            1. Compliance: supplier-related major/critical ->
               RETURN_TO_SUPPLIER; critical -> SCRAP; critical always
               carries requires_human_approval=True.
            2. Quality: a minor NCR with zero defective units is a control
               signal only -> USE_AS_IS; any defective units with a spec
               violation are never shipped as-is.
            3. Economics: with rework_cost_per_unit and unit_value both
               known, REWORK while economical, SCRAP when not.
            4. Default containment when economics are unknown: REWORK.
        """
        severity = (ncr.severity or "minor").lower()
        quantity_affected = float(ncr.quantity_affected or 0.0)
        assessments = self._member_assessments(
            severity,
            supplier_related,
            quantity_affected,
            rework_cost_per_unit,
            unit_value,
        )
        disposition = self._resolve(assessments)
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
                "rework_cost_per_unit": rework_cost_per_unit,
                "unit_value": unit_value,
                "member_assessments": {
                    m: a["position"] for m, a in assessments.items()
                },
            },
            department="manufacturing",
            authority_level="critical" if severity == "critical" else "standard",
        )
        consensus = record.consensus

        member_reasons = "; ".join(
            f"{member}: {assessment['reason']}"
            for member, assessment in assessments.items()
        )
        rationale = (
            f"Quality council weighted consensus {consensus.decision_value:.2f}: "
            f"{severity} NCR dispositioned as {disposition.value} "
            f"({member_reasons})"
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
            "member_assessments": {
                member: dict(assessment)
                for member, assessment in assessments.items()
            },
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

    # ------------------------------------------------------------------
    # Evidence-weighted deliberation (deterministic, D-022)
    # ------------------------------------------------------------------

    @staticmethod
    def _member_assessments(
        severity: str,
        supplier_related: bool,
        quantity_affected: float,
        rework_cost_per_unit: Optional[float],
        unit_value: Optional[float],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Each member weighs the evidence relevant to their charter and takes
        a position (a DispositionType value, or None to defer).
        """
        assessments: Dict[str, Dict[str, Any]] = {}

        # Compliance officer: regulatory posture. Critical defects cannot be
        # certified by rework; supplier defects go back with the paperwork.
        if supplier_related and severity in ("major", "critical"):
            assessments["compliance_officer"] = {
                "position": DispositionType.RETURN_TO_SUPPLIER.value,
                "binding": True,
                "reason": (
                    f"{severity} defect in purchased material returns to "
                    "the supplier with full traceability"
                ),
            }
        elif severity == "critical":
            assessments["compliance_officer"] = {
                "position": DispositionType.SCRAP.value,
                "binding": True,
                "reason": (
                    "critical severity: safety/function cannot be assured "
                    "by rework; scrap under HITL approval"
                ),
            }
        else:
            assessments["compliance_officer"] = {
                "position": None,
                "binding": False,
                "reason": "no regulatory constraint at this severity",
            }

        # Quality engineer: defective units with a spec violation are never
        # shipped as-is; a minor NCR with zero defective units is a control
        # signal from a capable process. Major/critical means the process is
        # incapable — the lot cannot clear without correction even when the
        # defect count is not yet quantified.
        if quantity_affected > 0:
            assessments["quality_engineer"] = {
                "position": DispositionType.REWORK.value,
                "binding": False,
                "reason": (
                    f"{quantity_affected:g} defective unit(s) violate spec; "
                    "USE_AS_IS is off the table, contain and correct"
                ),
            }
        elif severity == "minor":
            assessments["quality_engineer"] = {
                "position": DispositionType.USE_AS_IS.value,
                "binding": False,
                "reason": (
                    "zero defective units on a capable process: "
                    "out-of-control signal only, product conforms"
                ),
            }
        else:
            assessments["quality_engineer"] = {
                "position": DispositionType.REWORK.value,
                "binding": False,
                "reason": (
                    f"{severity} severity: process incapable, defects "
                    "expected; lot requires correction"
                ),
            }

        # Manufacturing engineer: rework economics, when the costs are known.
        if rework_cost_per_unit is not None and unit_value is not None:
            economical = rework_cost_per_unit < unit_value
            assessments["manufacturing_engineer"] = {
                "position": (
                    DispositionType.REWORK.value
                    if economical
                    else DispositionType.SCRAP.value
                ),
                "binding": False,
                "reason": (
                    f"rework {rework_cost_per_unit:g}/u vs unit value "
                    f"{unit_value:g}/u: rework is "
                    f"{'economical' if economical else 'uneconomical'}"
                ),
            }
        else:
            assessments["manufacturing_engineer"] = {
                "position": None,
                "binding": False,
                "reason": "rework economics unknown; deferring to quality",
            }

        return assessments

    @staticmethod
    def _resolve(assessments: Dict[str, Dict[str, Any]]) -> DispositionType:
        """Combine member positions deterministically into a disposition."""
        compliance = assessments["compliance_officer"]
        quality = assessments["quality_engineer"]
        economics = assessments["manufacturing_engineer"]

        # 1. Binding compliance positions override everything.
        if compliance["binding"] and compliance["position"]:
            return DispositionType(compliance["position"])

        # 2. No defective units: the quality engineer's evidence stands.
        if quality["position"] == DispositionType.USE_AS_IS.value:
            return DispositionType.USE_AS_IS

        # 3. Defective units present: economics chooses REWORK vs SCRAP
        #    when the costs are known.
        if economics["position"]:
            return DispositionType(economics["position"])

        # 4. Economics unknown: default containment is rework.
        return DispositionType.REWORK
