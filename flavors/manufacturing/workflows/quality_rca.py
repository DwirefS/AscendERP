"""
Quality RCA (8D) Workflow for the Manufacturing flavor.

Takes a NonConformanceReport and event data, walks the structured 8D problem
solving steps D1-D8 with a deterministic fishbone-category root-cause
inference (6M: man, machine, material, method, measurement, environment)
scored from the event data, and produces a CAPA record.

Follows the capital-markets workflow style: an async run() that drives named
stages and returns a stage-results dict.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import structlog

from flavors.manufacturing.models import NonConformanceReport

logger = structlog.get_logger()

# Fishbone (6M) signal keywords matched against event-data keys and values.
FISHBONE_SIGNALS: Dict[str, List[str]] = {
    "man": ["operator", "training", "shift", "fatigue", "manual", "handover"],
    "machine": [
        "machine", "vibration", "tool_wear", "breakdown", "spindle",
        "equipment", "bearing",
    ],
    "material": ["supplier", "material", "lot", "raw", "incoming", "batch"],
    "method": [
        "procedure", "setup", "process", "parameter", "sop",
        "work_instruction", "recipe",
    ],
    "measurement": [
        "gauge", "calibration", "measurement", "inspection", "sensor", "probe",
    ],
    "environment": [
        "temperature", "humidity", "contamination", "dust", "ambient",
    ],
}

_CORRECTIVE_ACTIONS: Dict[str, str] = {
    "man": "Retrain operators and add a verification sign-off to the operation",
    "machine": "Perform corrective maintenance and recalibrate the machine",
    "material": "Quarantine the affected lot and audit the supplier",
    "method": "Revise the process parameters and update the work instruction",
    "measurement": "Recalibrate gauges and repeat the measurement system analysis",
    "environment": "Restore environmental controls and add condition monitoring",
}

_PREVENTIVE_ACTIONS: Dict[str, str] = {
    "man": "Add the failure mode to operator certification and the skills matrix",
    "machine": "Add the machine parameter to the predictive maintenance plan",
    "material": "Add incoming inspection for the characteristic and dual-source",
    "method": "Update the control plan and PFMEA with the new failure mode",
    "measurement": "Shorten the gauge calibration interval and add MSA checks",
    "environment": "Add environmental limits to the control plan with alarms",
}


class QualityRCAWorkflow:
    """NCR -> structured 8D (D1-D8) -> CAPA record."""

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected input:
        {
            "ncr": NonConformanceReport (or dict of its fields),
            "event_data": {...}   # signals for root-cause inference
        }
        """
        trace_id = f"rca-{uuid.uuid4().hex[:8]}"
        now = input_data.get("now") or datetime.utcnow()
        ncr = input_data.get("ncr")
        if isinstance(ncr, dict):
            ncr = NonConformanceReport(**ncr)
        if ncr is None:
            return {
                "status": "failed",
                "trace_id": trace_id,
                "stages": {},
                "errors": ["'ncr' input is required"],
            }

        event_data: Dict[str, Any] = dict(input_data.get("event_data", {}))
        severity = (ncr.severity or "minor").lower()

        category, scores, matched = self._infer_fishbone_category(event_data)
        root_cause = (
            f"Root cause inferred in fishbone category '{category}' from "
            f"signals: {', '.join(matched) if matched else 'none (default)'}"
        )
        corrective = _CORRECTIVE_ACTIONS[category]
        preventive = _PREVENTIVE_ACTIONS[category]

        stages: Dict[str, Any] = {
            "D1": {
                "step": "establish_team",
                "team": [
                    "quality_engineer",
                    "production_supervisor",
                    "maintenance_lead" if category == "machine"
                    else "process_engineer",
                ],
            },
            "D2": {
                "step": "describe_problem",
                "ncr_id": ncr.ncr_id,
                "work_order_id": ncr.work_order_id,
                "description": ncr.description,
                "severity": severity,
                "quantity_affected": ncr.quantity_affected,
            },
            "D3": {
                "step": "containment_actions",
                "actions": self._containment_actions(severity),
            },
            "D4": {
                "step": "root_cause_analysis",
                "method": "fishbone_6m",
                "category_scores": scores,
                "root_cause_category": category,
                "matched_signals": matched,
                "root_cause": root_cause,
            },
            "D5": {
                "step": "select_corrective_actions",
                "corrective_action": corrective,
            },
            "D6": {
                "step": "implement_corrective_actions",
                "owner": "quality_engineer",
                "target_date": (now + timedelta(days=14)).isoformat(),
            },
            "D7": {
                "step": "prevent_recurrence",
                "preventive_action": preventive,
            },
            "D8": {
                "step": "congratulate_team_and_close",
                "closure_criteria": (
                    "Effectiveness verified over 30 days of production with "
                    "no recurrence of the failure mode"
                ),
            },
        }

        # Write findings back onto the NCR and emit the CAPA record.
        ncr.root_cause = root_cause
        ncr.corrective_action = corrective

        capa = {
            "capa_id": f"CAPA-{uuid.uuid4().hex[:10]}",
            "ncr_id": ncr.ncr_id,
            "root_cause_category": category,
            "root_cause": root_cause,
            "corrective_action": corrective,
            "preventive_action": preventive,
            "owner": "quality_engineer",
            "due_date": (now + timedelta(days=30)).isoformat(),
            "status": "open",
        }

        logger.info(
            "quality_rca_completed",
            trace_id=trace_id,
            ncr_id=ncr.ncr_id,
            root_cause_category=category,
            capa_id=capa["capa_id"],
        )

        return {
            "status": "completed",
            "trace_id": trace_id,
            "stages": stages,
            "errors": [],
            "ncr": ncr,
            "capa": capa,
        }

    # ------------------------------------------------------------------

    @staticmethod
    def _infer_fishbone_category(
        event_data: Dict[str, Any],
    ) -> Tuple[str, Dict[str, int], List[str]]:
        """
        Deterministic fishbone inference: lowercase all event-data keys and
        string values, count keyword hits per 6M category, pick the highest
        (ties broken by fixed category order; default 'method').
        """
        corpus_parts: List[str] = []
        for key, value in event_data.items():
            corpus_parts.append(str(key).lower())
            if isinstance(value, str):
                corpus_parts.append(value.lower())
        corpus = " ".join(corpus_parts)

        scores: Dict[str, int] = {}
        matched_by_category: Dict[str, List[str]] = {}
        for category, signals in FISHBONE_SIGNALS.items():
            hits = [signal for signal in signals if signal in corpus]
            scores[category] = len(hits)
            matched_by_category[category] = hits

        best = max(FISHBONE_SIGNALS, key=lambda c: scores[c])
        if scores[best] == 0:
            best = "method"  # default category when no signals match
        return best, scores, matched_by_category[best]

    @staticmethod
    def _containment_actions(severity: str) -> List[str]:
        """Containment scaled to severity."""
        actions = ["Quarantine affected work order quantity", "100% inspect WIP"]
        if severity in ("major", "critical"):
            actions.append("Hold shipments of potentially affected lots")
        if severity == "critical":
            actions.append("Stop production on the affected line pending review")
        return actions
