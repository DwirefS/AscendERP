"""
Maintenance Agent for the Manufacturing flavor.

Predictive maintenance risk scoring per machine. Documented risk formula:

    wear_ratio = runtime_hours_since_pm / mtbf_hours      (PM-cycle wear)
    risk       = 0.6 * wear_ratio + 0.4 * vibration_trend
    risk       = clamp(risk, 0.0, 1.0)

Rationale: runtime since the last preventive maintenance relative to the
machine's MTBF is the dominant wear signal (weight 0.6); the vibration trend
(0..1, rising = degrading) is a leading condition-monitoring indicator
(weight 0.4). The score is monotonically increasing in both inputs.

Machines whose risk meets/exceeds the threshold (default 0.6) get a
PREDICTIVE MaintenanceWorkOrder scheduled into the next low-load window of
the production schedule (first gap long enough for the PM job; if no schedule
is known the job is scheduled immediately).
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext
from flavors.manufacturing.models import (
    Machine,
    MaintenanceType,
    MaintenanceWorkOrder,
    ProductionSchedule,
)

logger = structlog.get_logger()

_WEAR_WEIGHT = 0.6
_VIBRATION_WEIGHT = 0.4
_DEFAULT_RISK_THRESHOLD = 0.6
_DEFAULT_PM_HOURS = 4.0


class MaintenanceAgent(BaseAgent):
    """Predictive maintenance risk scoring and PM work order scheduling."""

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Maintenance Agent",
                description=(
                    "Predictive failure risk scoring and PM scheduling into "
                    "low-load windows"
                ),
                tools=[
                    "score_machine_risk",
                    "create_pm_order",
                    "find_low_load_window",
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
        """Parse machines, telemetry overrides and scheduling context."""
        machines: List[Machine] = list(input_data.get("machines", []))
        telemetry: Dict[str, Dict[str, float]] = input_data.get("telemetry", {})

        # Apply telemetry overrides to machine condition fields.
        for machine in machines:
            reading = telemetry.get(machine.machine_id)
            if not reading:
                continue
            if "runtime_hours_since_pm" in reading:
                machine.runtime_hours_since_pm = float(
                    reading["runtime_hours_since_pm"]
                )
            if "vibration_trend" in reading:
                machine.vibration_trend = float(reading["vibration_trend"])

        logger.info(
            "perceiving_maintenance_request",
            trace_id=context.trace_id,
            machines=len(machines),
            telemetry_readings=len(telemetry),
        )

        return {
            "machines": machines,
            "risk_threshold": float(
                input_data.get("risk_threshold", _DEFAULT_RISK_THRESHOLD)
            ),
            "schedule": input_data.get("schedule"),
            "estimated_hours": float(
                input_data.get("estimated_hours", _DEFAULT_PM_HOURS)
            ),
            "now": input_data.get("now") or datetime.utcnow(),
        }

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Retrieve maintenance history when memory is available."""
        retrieved: Dict[str, Any] = {}

        if self.memory:
            procedural = await self.memory.retrieve_procedural(
                context={"task": "predictive_maintenance"},
                agent_id=self.config.agent_id,
                limit=5,
            )
            retrieved["maintenance_history"] = [p.content for p in procedural]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Decide on risk assessment. Deterministic without an LLM."""
        machines = perception["machines"]

        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=(
                        "You are a reliability engineer. Assess failure risk "
                        f"for {len(machines)} machines given runtime and "
                        "vibration telemetry."
                    ),
                    max_tokens=self.config.max_tokens,
                    temperature=0.2,
                )
                return {
                    "action": {
                        "type": "assess_maintenance_risk",
                        "inputs": perception,
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get(
                        "reasoning", "LLM-assisted risk review"
                    ),
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed", error=str(e), fallback="deterministic"
                )

        return {
            "action": {
                "type": "assess_maintenance_risk",
                "inputs": perception,
            },
            "confidence": 0.82,
            "reasoning": (
                "Deterministic risk model: risk = 0.6 * runtime/mtbf "
                f"+ 0.4 * vibration_trend over {len(machines)} machines, "
                f"threshold {perception['risk_threshold']}"
            ),
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext,
    ) -> Any:
        """Score risks and create PM orders in low-load windows."""
        inputs = action.get("inputs", {})
        machines: List[Machine] = inputs.get("machines", [])
        threshold: float = inputs.get("risk_threshold", _DEFAULT_RISK_THRESHOLD)
        schedule: Optional[ProductionSchedule] = inputs.get("schedule")
        estimated_hours: float = inputs.get("estimated_hours", _DEFAULT_PM_HOURS)
        now: datetime = inputs.get("now", datetime.utcnow())

        risk_scores: Dict[str, float] = {}
        orders: List[MaintenanceWorkOrder] = []

        for machine in machines:
            risk = self.compute_risk(machine)
            risk_scores[machine.machine_id] = round(risk, 4)

            if risk >= threshold:
                window_start = self._next_low_load_window(
                    machine.machine_id, schedule, estimated_hours, now
                )
                order = MaintenanceWorkOrder.new(
                    machine_id=machine.machine_id,
                    maintenance_type=MaintenanceType.PREDICTIVE,
                    reason=(
                        f"Predictive risk {risk:.2f} >= threshold {threshold:.2f} "
                        f"(runtime {machine.runtime_hours_since_pm:.0f}h / "
                        f"mtbf {machine.mtbf_hours:.0f}h, vibration "
                        f"{machine.vibration_trend:.2f})"
                    ),
                    estimated_hours=estimated_hours,
                    scheduled_start=window_start,
                    risk_score=round(risk, 4),
                )
                orders.append(order)
                logger.info(
                    "predictive_pm_order_created",
                    trace_id=context.trace_id,
                    machine_id=machine.machine_id,
                    risk=round(risk, 3),
                    scheduled_start=window_start.isoformat(),
                )

        return {
            "assessed": True,
            "risk_scores": risk_scores,
            "risk_threshold": threshold,
            "maintenance_orders": orders,
            "summary": {
                "machines_assessed": len(machines),
                "orders_created": len(orders),
                "max_risk": max(risk_scores.values()) if risk_scores else 0.0,
            },
        }

    async def verify(
        self,
        result: Any,
        context: AgentContext,
    ) -> Dict[str, Any]:
        """Verify every above-threshold machine received a PM order."""
        risk_scores = result.get("risk_scores", {})
        threshold = result.get("risk_threshold", _DEFAULT_RISK_THRESHOLD)
        orders = result.get("maintenance_orders", [])
        ordered_machines = {o.machine_id for o in orders}
        flagged = {m for m, r in risk_scores.items() if r >= threshold}
        covered = flagged.issubset(ordered_machines)

        return {
            "complete": result.get("assessed", False),
            "quality_score": 1.0 if covered else 0.4,
            "metrics": {
                "machines_flagged": len(flagged),
                "orders_created": len(orders),
            },
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext,
    ):
        """Persist risk outcomes when memory is available."""
        if not self.memory or not actions_taken:
            return

        last_result = actions_taken[-1].get("result", {})
        await self.memory.store_episodic(
            content={
                "risk_scores": last_result.get("risk_scores"),
                "orders_created": last_result.get("summary", {}).get(
                    "orders_created"
                ),
                "trace_id": context.trace_id,
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id,
        )

    # ------------------------------------------------------------------
    # Deterministic risk model
    # ------------------------------------------------------------------

    @staticmethod
    def compute_risk(machine: Machine) -> float:
        """
        Failure risk score in [0, 1]:

            risk = clamp(0.6 * runtime_hours_since_pm / mtbf_hours
                         + 0.4 * vibration_trend, 0, 1)

        Monotonically increasing in runtime-since-PM and vibration trend.
        """
        mtbf = max(machine.mtbf_hours, 1e-6)
        wear_ratio = machine.runtime_hours_since_pm / mtbf
        vibration = min(max(machine.vibration_trend, 0.0), 1.0)
        risk = _WEAR_WEIGHT * wear_ratio + _VIBRATION_WEIGHT * vibration
        return min(max(risk, 0.0), 1.0)

    @staticmethod
    def _next_low_load_window(
        machine_id: str,
        schedule: Optional[ProductionSchedule],
        estimated_hours: float,
        now: datetime,
    ) -> datetime:
        """
        Find the next low-load window on a machine: the earliest gap in its
        scheduled entries large enough for the PM job. With no schedule the
        machine is idle, so maintenance can start immediately.
        """
        if schedule is None:
            return now

        entries = schedule.for_machine(machine_id)
        if not entries:
            return now

        needed = timedelta(hours=estimated_hours)

        # Gap before the first scheduled entry.
        if entries[0].start - now >= needed:
            return now

        # Gaps between consecutive entries.
        for current, following in zip(entries, entries[1:]):
            gap_start = max(current.end, now)
            if following.start - gap_start >= needed:
                return gap_start

        # Otherwise: right after the last scheduled entry.
        return max(entries[-1].end, now)
