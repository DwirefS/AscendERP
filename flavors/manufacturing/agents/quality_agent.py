"""
Quality Agent for the Manufacturing flavor.

Real SPC mathematics on QualityInspection measurement series:
  - x-bar (mean) and sigma (sample standard deviation, ddof=1)
  - Cp  = (USL - LSL) / (6 * sigma)
  - Cpk = min(USL - xbar, xbar - LSL) / (3 * sigma)
  - Western Electric rules 1-4 on z-scores about the center line:
      Rule 1: any point beyond 3 sigma
      Rule 2: 2 of 3 consecutive points beyond 2 sigma on the same side
      Rule 3: 4 of 5 consecutive points beyond 1 sigma on the same side
      Rule 4: 8 consecutive points on the same side of the center line

Out-of-control series produce a NonConformanceReport whose severity is graded
by Cpk (critical < 0.7 <= major < 1.0 <= minor) and a DispositionType
recommendation. Works fully without an LLM or memory.
"""
import math
from typing import Any, Dict, List, Optional, Tuple

import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext
from flavors.manufacturing.models import (
    DispositionType,
    NonConformanceReport,
    QualityInspection,
)

logger = structlog.get_logger()

# Cap used when there is no observed variation (sigma == 0): the process is
# perfectly capable as observed, so we report a large finite index.
_CAPABILITY_CAP = 99.0

# Severity grading by Cpk (documented policy):
#   Cpk <  0.7  -> critical (process grossly incapable)
#   Cpk <  1.0  -> major    (process incapable, defects expected)
#   Cpk >= 1.0  -> minor    (out-of-control signal but capable process)
_CPK_CRITICAL = 0.7
_CPK_MAJOR = 1.0


class QualityAgent(BaseAgent):
    """SPC control-chart analysis, NCR creation and disposition recommendation."""

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Quality Agent",
                description="SPC analysis, NCR creation, disposition recommendation",
                tools=[
                    "compute_spc_statistics",
                    "apply_western_electric_rules",
                    "create_ncr",
                    "recommend_disposition",
                ],
                max_iterations=5,
                timeout_seconds=120,
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Parse the inspection payload."""
        inspection = input_data.get("inspection")
        if isinstance(inspection, dict):
            inspection = QualityInspection(**inspection)
        if inspection is None:
            raise ValueError("QualityAgent requires an 'inspection' input")

        logger.info(
            "perceiving_quality_inspection",
            trace_id=context.trace_id,
            inspection_id=inspection.inspection_id,
            samples=len(inspection.measurements),
        )

        return {
            "inspection": inspection,
            "supplier_material": bool(input_data.get("supplier_material", False)),
        }

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Retrieve historical quality patterns when memory is available."""
        retrieved: Dict[str, Any] = {}

        if self.memory:
            inspection: QualityInspection = perception["inspection"]
            semantic = await self.memory.retrieve_semantic(
                query=f"quality history for {inspection.characteristic}",
                tenant_id=context.tenant_id,
                limit=5,
            )
            retrieved["quality_history"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Decide on SPC analysis. Deterministic without an LLM."""
        inspection: QualityInspection = perception["inspection"]

        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=(
                        "You are a quality engineer. Review SPC context for "
                        f"characteristic {inspection.characteristic} with "
                        f"{len(inspection.measurements)} samples."
                    ),
                    max_tokens=self.config.max_tokens,
                    temperature=0.2,
                )
                return {
                    "action": {
                        "type": "spc_analysis",
                        "inspection": inspection,
                        "supplier_material": perception["supplier_material"],
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get(
                        "reasoning", "LLM-assisted SPC review"
                    ),
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed", error=str(e), fallback="deterministic"
                )

        return {
            "action": {
                "type": "spc_analysis",
                "inspection": inspection,
                "supplier_material": perception["supplier_material"],
            },
            "confidence": 0.85,
            "reasoning": (
                "Deterministic SPC control-chart analysis with Western Electric "
                f"rules on {len(inspection.measurements)} measurements"
            ),
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext,
    ) -> Any:
        """Run SPC math, fire control rules and create an NCR if needed."""
        inspection: QualityInspection = action["inspection"]
        supplier_material: bool = action.get("supplier_material", False)
        measurements = list(inspection.measurements)

        if not measurements:
            return {
                "analyzed": True,
                "in_control": True,
                "rules_fired": [],
                "ncr": None,
                "recommended_disposition": None,
                "stats": {},
            }

        xbar, sigma, cp, cpk = self.compute_capability(
            measurements, inspection.nominal, inspection.usl, inspection.lsl
        )
        center = inspection.nominal if inspection.nominal else xbar
        z_scores = [
            (x - center) / sigma if sigma > 0 else 0.0 for x in measurements
        ]

        rules_fired = self.western_electric_rules(z_scores)
        in_control = not rules_fired

        out_of_spec = [
            x for x in measurements
            if inspection.usl > inspection.lsl
            and (x > inspection.usl or x < inspection.lsl)
        ]

        ncr = None
        disposition = None
        if not in_control:
            severity = self._severity_from_cpk(cpk)
            disposition = self._recommend_disposition(
                severity, supplier_material, bool(out_of_spec)
            )
            ncr = NonConformanceReport.new(
                work_order_id=inspection.work_order_id,
                description=(
                    f"SPC out-of-control on {inspection.characteristic}: "
                    f"rules fired {sorted(rules_fired)}; "
                    f"xbar={xbar:.4f}, sigma={sigma:.4f}, Cpk={cpk:.3f}"
                ),
                severity=severity,
                quantity_affected=float(len(out_of_spec)),
                disposition=disposition,
            )
            logger.info(
                "ncr_created",
                trace_id=context.trace_id,
                ncr_id=ncr.ncr_id,
                severity=severity,
                disposition=disposition.value,
            )

        return {
            "analyzed": True,
            "in_control": in_control,
            "rules_fired": sorted(rules_fired),
            "stats": {
                "xbar": round(xbar, 6),
                "sigma": round(sigma, 6),
                "cp": round(cp, 4),
                "cpk": round(cpk, 4),
                "center": round(center, 6),
                "n": len(measurements),
                "out_of_spec_count": len(out_of_spec),
            },
            "ncr": ncr,
            "recommended_disposition": disposition,
        }

    async def verify(
        self,
        result: Any,
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Verify analysis completeness and consistency."""
        analyzed = result.get("analyzed", False)
        in_control = result.get("in_control", True)
        ncr_present = result.get("ncr") is not None

        # Consistency: out-of-control series must yield an NCR.
        consistent = in_control or ncr_present

        return {
            "complete": analyzed,
            "quality_score": 1.0 if consistent else 0.3,
            "metrics": {
                "in_control": in_control,
                "rules_fired": len(result.get("rules_fired", [])),
                "ncr_created": ncr_present,
            },
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext,
    ):
        """Persist quality outcomes when memory is available."""
        if not self.memory or not actions_taken:
            return

        last_result = actions_taken[-1].get("result", {})
        await self.memory.store_episodic(
            content={
                "in_control": last_result.get("in_control"),
                "rules_fired": last_result.get("rules_fired"),
                "stats": last_result.get("stats"),
                "trace_id": context.trace_id,
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id,
        )

    # ------------------------------------------------------------------
    # SPC mathematics (deterministic, reusable in tests)
    # ------------------------------------------------------------------

    @staticmethod
    def compute_capability(
        measurements: List[float],
        nominal: float,
        usl: float,
        lsl: float,
    ) -> Tuple[float, float, float, float]:
        """Return (xbar, sigma, Cp, Cpk). Sample sigma with ddof=1."""
        n = len(measurements)
        xbar = sum(measurements) / n
        if n > 1:
            variance = sum((x - xbar) ** 2 for x in measurements) / (n - 1)
            sigma = math.sqrt(variance)
        else:
            sigma = 0.0

        if usl <= lsl:
            # No usable spec limits: capability indices are undefined; cap them.
            return xbar, sigma, _CAPABILITY_CAP, _CAPABILITY_CAP

        if sigma <= 1e-12:
            return xbar, 0.0, _CAPABILITY_CAP, _CAPABILITY_CAP

        cp = (usl - lsl) / (6.0 * sigma)
        cpk = min(usl - xbar, xbar - lsl) / (3.0 * sigma)
        return xbar, sigma, cp, cpk

    @staticmethod
    def western_electric_rules(z_scores: List[float]) -> List[str]:
        """
        Apply Western Electric rules 1-4 to z-scores about the center line.
        Returns the list of rule identifiers that fired.
        """
        fired = set()
        sides = [1 if z > 0 else (-1 if z < 0 else 0) for z in z_scores]

        # Rule 1: one point beyond 3 sigma
        if any(abs(z) > 3.0 for z in z_scores):
            fired.add("rule1_one_beyond_3_sigma")

        # Rule 2: 2 of 3 consecutive points beyond 2 sigma, same side
        for i in range(len(z_scores) - 2):
            window = z_scores[i:i + 3]
            for side in (1, -1):
                if sum(1 for z in window if side * z > 2.0) >= 2:
                    fired.add("rule2_two_of_three_beyond_2_sigma")

        # Rule 3: 4 of 5 consecutive points beyond 1 sigma, same side
        for i in range(len(z_scores) - 4):
            window = z_scores[i:i + 5]
            for side in (1, -1):
                if sum(1 for z in window if side * z > 1.0) >= 4:
                    fired.add("rule3_four_of_five_beyond_1_sigma")

        # Rule 4: 8 consecutive points on the same side of center
        run_length = 0
        prev_side = 0
        for side in sides:
            if side != 0 and side == prev_side:
                run_length += 1
            else:
                run_length = 1 if side != 0 else 0
            prev_side = side
            if run_length >= 8:
                fired.add("rule4_eight_consecutive_same_side")
                break

        return sorted(fired)

    @staticmethod
    def _severity_from_cpk(cpk: float) -> str:
        """Grade NCR severity from process capability."""
        if cpk < _CPK_CRITICAL:
            return "critical"
        if cpk < _CPK_MAJOR:
            return "major"
        return "minor"

    @staticmethod
    def _recommend_disposition(
        severity: str,
        supplier_material: bool,
        out_of_spec: bool,
    ) -> DispositionType:
        """Map severity (and material origin) to a disposition recommendation."""
        if supplier_material and severity in ("major", "critical"):
            return DispositionType.RETURN_TO_SUPPLIER
        if severity == "critical":
            return DispositionType.SCRAP
        if severity == "major":
            return DispositionType.REWORK
        # Minor: capable process, only a control signal.
        return DispositionType.REWORK if out_of_spec else DispositionType.USE_AS_IS
