"""
Predictive Maintenance Workflow for the Manufacturing flavor.

Stages (per design §4):
    telemetry_ingest -> risk_assessment (MaintenanceAgent) ->
    council_allocation (MaintenanceCouncil, only when requested downtime
    exceeds the available buffer) -> pm_orders

Follows the capital-markets workflow style: an async run() that drives named
stages and returns a stage-results dict.
"""
import uuid
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import AgentContext
from flavors.manufacturing.agents.maintenance_agent import MaintenanceAgent
from flavors.manufacturing.councils.maintenance_council import MaintenanceCouncil

logger = structlog.get_logger()

_DEFAULT_BUFFER_HOURS = 16.0


class PredictiveMaintenanceWorkflow:
    """Telemetry -> risk -> (council on contention) -> PM orders."""

    def __init__(
        self,
        agent: Optional[MaintenanceAgent] = None,
        council: Optional[MaintenanceCouncil] = None,
    ):
        self.agent = agent or MaintenanceAgent()
        self.council = council or MaintenanceCouncil()

    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected input:
        {
            "machines": [Machine],
            "telemetry": {machine_id: {"runtime_hours_since_pm", "vibration_trend"}},
            "available_buffer_hours"?: float,
            "risk_threshold"?: float,
            "schedule"?: ProductionSchedule,
        }
        """
        trace_id = f"pdm-{uuid.uuid4().hex[:8]}"
        context = AgentContext(trace_id=trace_id, tenant_id="manufacturing")
        stages: Dict[str, Any] = {}
        errors: List[str] = []

        telemetry: Dict[str, Dict[str, float]] = input_data.get("telemetry", {})
        buffer_hours = float(
            input_data.get("available_buffer_hours", _DEFAULT_BUFFER_HOURS)
        )

        # Stage 1: telemetry ingest
        stages["telemetry_ingest"] = {
            "machines": len(input_data.get("machines", [])),
            "readings": len(telemetry),
        }

        # Stage 2: risk assessment via the maintenance agent
        agent_result = await self.agent.run({
            "machines": input_data.get("machines", []),
            "telemetry": telemetry,
            "risk_threshold": input_data.get("risk_threshold", 0.6),
            "schedule": input_data.get("schedule"),
            "estimated_hours": input_data.get("estimated_hours", 4.0),
        }, context)

        if not agent_result.success:
            errors.append(agent_result.error or "maintenance agent failed")
            stages["risk_assessment"] = {"success": False}
            return {
                "status": "failed",
                "trace_id": trace_id,
                "stages": stages,
                "errors": errors,
            }

        assessment = agent_result.output
        proposed = assessment["maintenance_orders"]
        stages["risk_assessment"] = {
            "success": True,
            "risk_scores": assessment["risk_scores"],
            "risk_threshold": assessment["risk_threshold"],
            "proposed_orders": len(proposed),
        }
        logger.info(
            "pdm_risk_assessment",
            trace_id=trace_id,
            proposed_orders=len(proposed),
        )

        # Stage 3: council allocation when requests exceed the downtime buffer
        total_hours = sum(o.estimated_hours for o in proposed)
        if total_hours > buffer_hours and proposed:
            decision = await self.council.decide(proposed, buffer_hours)
            granted_ids = set(decision["granted"])
            stages["council_allocation"] = {
                "convened": True,
                "decision": decision,
            }
        else:
            granted_ids = {o.maintenance_id for o in proposed}
            stages["council_allocation"] = {
                "convened": False,
                "reason": (
                    f"requested {total_hours:.1f}h within "
                    f"{buffer_hours:.1f}h buffer"
                ),
            }

        # Stage 4: final PM orders
        pm_orders = [o for o in proposed if o.maintenance_id in granted_ids]
        deferred = [o for o in proposed if o.maintenance_id not in granted_ids]
        stages["pm_orders"] = {
            "scheduled": [o.maintenance_id for o in pm_orders],
            "deferred": [o.maintenance_id for o in deferred],
        }
        logger.info(
            "pdm_orders_finalized",
            trace_id=trace_id,
            scheduled=len(pm_orders),
            deferred=len(deferred),
        )

        return {
            "status": "completed",
            "trace_id": trace_id,
            "stages": stages,
            "errors": errors,
            "pm_orders": pm_orders,
            "deferred_orders": deferred,
        }
