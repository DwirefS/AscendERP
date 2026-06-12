"""
EHS Compliance Agent for the Manufacturing flavor.

Three deterministic capabilities:

1. Incident triage via a 5x5 severity matrix:
       risk_score = severity (1-5) x likelihood (1-5)
       >= 15 -> critical (stop work, human approval required)
       >=  8 -> high     (corrective action within 24h)
       >=  4 -> medium   (corrective action within 7 days)
       else  -> low      (log and monitor)

2. Lockout/tagout (LOTO) checklist verification against the OSHA-style
   six-step sequence; the checklist input is a dict of step -> bool.

3. Compliance calendar: classifies audit/training items as overdue (date
   before today) or upcoming (within the look-ahead window, default 30 days).
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()

LOTO_REQUIRED_STEPS = [
    "notify_affected_employees",
    "shutdown_equipment",
    "isolate_energy_sources",
    "apply_locks_and_tags",
    "release_stored_energy",
    "verify_zero_energy",
]

_DEFAULT_LOOKAHEAD_DAYS = 30


class EHSComplianceAgent(BaseAgent):
    """Incident triage, LOTO verification and compliance calendar tracking."""

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="EHS Compliance Agent",
                description=(
                    "Incident severity-matrix triage, lockout/tagout checklist "
                    "verification and compliance calendar tracking"
                ),
                tools=[
                    "triage_incident",
                    "verify_loto_checklist",
                    "build_compliance_calendar",
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
        """Parse incidents, LOTO checklist and compliance calendar items."""
        logger.info(
            "perceiving_ehs_request",
            trace_id=context.trace_id,
            incidents=len(input_data.get("incidents", [])),
        )

        return {
            "incidents": list(input_data.get("incidents", [])),
            "loto_checklist": dict(input_data.get("loto_checklist", {})),
            "calendar_items": list(input_data.get("calendar_items", [])),
            "lookahead_days": int(
                input_data.get("lookahead_days", _DEFAULT_LOOKAHEAD_DAYS)
            ),
            "today": input_data.get("today") or datetime.utcnow(),
        }

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Retrieve EHS regulations when memory is available."""
        retrieved: Dict[str, Any] = {}

        if self.memory:
            semantic = await self.memory.retrieve_semantic(
                query="EHS regulations and incident procedures",
                tenant_id=context.tenant_id,
                limit=5,
            )
            retrieved["regulations"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Decide on the EHS review action. Deterministic without an LLM."""
        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=(
                        "You are an EHS officer. Review "
                        f"{len(perception['incidents'])} incidents, a LOTO "
                        "checklist and the compliance calendar."
                    ),
                    max_tokens=self.config.max_tokens,
                    temperature=0.2,
                )
                return {
                    "action": {
                        "type": "ehs_review",
                        "inputs": perception,
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get(
                        "reasoning", "LLM-assisted EHS review"
                    ),
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed", error=str(e), fallback="deterministic"
                )

        return {
            "action": {
                "type": "ehs_review",
                "inputs": perception,
            },
            "confidence": 0.85,
            "reasoning": (
                "Deterministic EHS review: 5x5 severity-matrix triage, "
                "six-step LOTO verification, 30-day compliance look-ahead"
            ),
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext,
    ) -> Any:
        """Run triage, LOTO verification and calendar classification."""
        inputs = action.get("inputs", {})
        incidents: List[Dict[str, Any]] = inputs.get("incidents", [])
        checklist: Dict[str, bool] = inputs.get("loto_checklist", {})
        calendar_items: List[Dict[str, Any]] = inputs.get("calendar_items", [])
        lookahead: int = inputs.get("lookahead_days", _DEFAULT_LOOKAHEAD_DAYS)
        today: datetime = inputs.get("today", datetime.utcnow())

        triage = [self.triage_incident(incident) for incident in incidents]
        loto = self.verify_loto(checklist) if checklist else None
        calendar = self._build_calendar(calendar_items, today, lookahead)

        critical_incidents = [t for t in triage if t["priority"] == "critical"]

        return {
            "reviewed": True,
            "incident_triage": triage,
            "loto": loto,
            "compliance_calendar": calendar,
            "summary": {
                "incidents_triaged": len(triage),
                "critical_incidents": len(critical_incidents),
                "loto_passed": loto["passed"] if loto else None,
                "overdue_items": len(calendar["overdue"]),
                "upcoming_items": len(calendar["upcoming"]),
                "requires_human_approval": bool(critical_incidents),
            },
        }

    async def verify(
        self,
        result: Any,
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Verify the review covered all inputs."""
        summary = result.get("summary", {})
        loto = result.get("loto")

        quality = 1.0
        if loto and not loto.get("passed", True):
            quality = 0.7  # work cannot proceed; flagged correctly
        if summary.get("critical_incidents", 0) > 0:
            quality = min(quality, 0.7)

        return {
            "complete": result.get("reviewed", False),
            "quality_score": quality,
            "metrics": {
                "incidents_triaged": summary.get("incidents_triaged", 0),
                "critical_incidents": summary.get("critical_incidents", 0),
                "overdue_items": summary.get("overdue_items", 0),
            },
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext,
    ):
        """Persist EHS outcomes when memory is available."""
        if not self.memory or not actions_taken:
            return

        last_result = actions_taken[-1].get("result", {})
        await self.memory.store_episodic(
            content={
                "summary": last_result.get("summary"),
                "trace_id": context.trace_id,
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id,
        )

    # ------------------------------------------------------------------
    # Deterministic EHS logic
    # ------------------------------------------------------------------

    @staticmethod
    def triage_incident(incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triage via the 5x5 severity matrix:
        risk = severity(1-5) * likelihood(1-5);
        >=15 critical, >=8 high, >=4 medium, else low.
        """
        severity = int(min(max(incident.get("severity", 1), 1), 5))
        likelihood = int(min(max(incident.get("likelihood", 1), 1), 5))
        risk_score = severity * likelihood

        if risk_score >= 15:
            priority, response = "critical", "stop_work_immediately"
        elif risk_score >= 8:
            priority, response = "high", "corrective_action_within_24h"
        elif risk_score >= 4:
            priority, response = "medium", "corrective_action_within_7d"
        else:
            priority, response = "low", "log_and_monitor"

        return {
            "incident_id": incident.get("incident_id", "unknown"),
            "severity": severity,
            "likelihood": likelihood,
            "risk_score": risk_score,
            "priority": priority,
            "required_response": response,
            "requires_human_approval": priority == "critical",
        }

    @staticmethod
    def verify_loto(checklist: Dict[str, bool]) -> Dict[str, Any]:
        """
        Verify a lockout/tagout checklist dict against the required six-step
        sequence. Steps missing from the dict or marked False fail the check.
        """
        missing = [
            step for step in LOTO_REQUIRED_STEPS if not checklist.get(step, False)
        ]
        extra = [
            step for step in checklist if step not in LOTO_REQUIRED_STEPS
        ]
        return {
            "passed": not missing,
            "missing_or_failed_steps": missing,
            "extra_steps": extra,
            "required_steps": list(LOTO_REQUIRED_STEPS),
        }

    @staticmethod
    def _build_calendar(
        items: List[Dict[str, Any]],
        today: datetime,
        lookahead_days: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Classify audit/training items as overdue / upcoming / later."""
        horizon = today + timedelta(days=lookahead_days)
        overdue, upcoming, later = [], [], []

        for item in items:
            due = item.get("date")
            if isinstance(due, str):
                due = datetime.fromisoformat(due)
            if due is None:
                continue
            entry = {
                "name": item.get("name", "unnamed"),
                "type": item.get("type", "audit"),
                "date": due.isoformat(),
                "days_until_due": (due - today).days,
            }
            if due < today:
                overdue.append(entry)
            elif due <= horizon:
                upcoming.append(entry)
            else:
                later.append(entry)

        key = lambda e: e["date"]  # noqa: E731
        return {
            "overdue": sorted(overdue, key=key),
            "upcoming": sorted(upcoming, key=key),
            "later": sorted(later, key=key),
        }
