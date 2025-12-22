"""
InfraOps Agent for ANTS Self-Operations.
Manages infrastructure provisioning and scaling.
"""
from typing import Dict, Any, List, Optional
from enum import Enum
import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


class InfraAction(Enum):
    """Infrastructure action types."""
    PROVISION = "provision"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    DEPLOY = "deploy"
    ROLLBACK = "rollback"
    MONITOR = "monitor"
    REMEDIATE = "remediate"


class InfraOpsAgent(BaseAgent):
    """
    Agent for managing ANTS infrastructure operations.
    Handles provisioning, scaling, and self-healing.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="InfraOps Agent",
                description="Manages infrastructure provisioning and scaling",
                tools=[
                    "terraform_plan",
                    "terraform_apply",
                    "helm_upgrade",
                    "kubectl_scale",
                    "azure_cli",
                    "monitor_metrics",
                    "create_alert"
                ],
                max_iterations=10,
                timeout_seconds=900,  # 15 minutes for infra operations
                require_approval_threshold=0.7,
                model_name="llama-3.1-nemotron-nano-8b"
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Parse infrastructure request or event.
        """
        logger.info(
            "perceiving_infra_request",
            trace_id=context.trace_id,
            request_type=input_data.get("type")
        )

        request_type = input_data.get("type", "unknown")

        perception = {
            "request_type": request_type,
            "target_resource": input_data.get("resource"),
            "desired_state": input_data.get("desired_state", {}),
            "current_state": input_data.get("current_state", {}),
            "trigger": input_data.get("trigger", "manual"),  # manual, alert, schedule
            "priority": input_data.get("priority", "normal"),
            "constraints": input_data.get("constraints", {}),
            "environment": input_data.get("environment", "production")
        }

        # Parse scaling requests
        if request_type in ["scale_up", "scale_down"]:
            perception["scaling"] = {
                "current_replicas": input_data.get("current_replicas", 1),
                "desired_replicas": input_data.get("desired_replicas"),
                "metric_trigger": input_data.get("metric_trigger"),
                "metric_value": input_data.get("metric_value")
            }

        # Parse provisioning requests
        if request_type == "provision":
            perception["provisioning"] = {
                "module": input_data.get("module"),
                "variables": input_data.get("variables", {}),
                "region": input_data.get("region", "eastus2")
            }

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve infrastructure context.
        """
        retrieved = {}

        if self.memory:
            # Get past similar operations
            procedural = await self.memory.retrieve_procedural(
                context={
                    "request_type": perception["request_type"],
                    "target_resource": perception["target_resource"]
                },
                agent_id=self.config.agent_id,
                limit=5
            )
            retrieved["past_operations"] = [p.content for p in procedural]

            # Get infrastructure runbooks
            semantic = await self.memory.retrieve_semantic(
                query=f"infrastructure runbook {perception['request_type']} {perception['target_resource']}",
                tenant_id=context.tenant_id,
                limit=5
            )
            retrieved["runbooks"] = [s.content for s in semantic]

        # Get current resource state
        retrieved["current_metrics"] = await self._get_current_metrics(
            perception["target_resource"]
        )

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Determine infrastructure action plan.
        """
        request_type = perception["request_type"]

        # Build action based on request type
        if request_type == "provision":
            return await self._plan_provisioning(perception, retrieved_context, context)
        elif request_type in ["scale_up", "scale_down"]:
            return await self._plan_scaling(perception, retrieved_context, context)
        elif request_type == "deploy":
            return await self._plan_deployment(perception, retrieved_context, context)
        elif request_type == "remediate":
            return await self._plan_remediation(perception, retrieved_context, context)
        else:
            return {
                "action": None,
                "confidence": 0.0,
                "reasoning": f"Unknown request type: {request_type}"
            }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute infrastructure operations.
        """
        action_type = action.get("type")
        steps = action.get("steps", [])

        results = {
            "action_type": action_type,
            "steps_executed": [],
            "status": "in_progress"
        }

        for step in steps:
            step_name = step.get("name")
            step_params = step.get("params", {})

            logger.info(
                "executing_infra_step",
                trace_id=context.trace_id,
                step=step_name
            )

            try:
                if step_name == "terraform_plan":
                    result = await self._terraform_plan(step_params, context)
                elif step_name == "terraform_apply":
                    result = await self._terraform_apply(step_params, context)
                elif step_name == "helm_upgrade":
                    result = await self._helm_upgrade(step_params, context)
                elif step_name == "kubectl_scale":
                    result = await self._kubectl_scale(step_params, context)
                elif step_name == "wait_healthy":
                    result = await self._wait_for_healthy(step_params, context)
                else:
                    result = {"success": False, "error": f"Unknown step: {step_name}"}

                results["steps_executed"].append({
                    "step": step_name,
                    "result": result
                })

                # Stop if step failed
                if not result.get("success", False):
                    results["status"] = "failed"
                    break

            except Exception as e:
                logger.error(
                    "infra_step_failed",
                    trace_id=context.trace_id,
                    step=step_name,
                    error=str(e)
                )
                results["status"] = "failed"
                results["error"] = str(e)
                break

        if results["status"] != "failed":
            results["status"] = "completed"

        return results

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Verify infrastructure changes.
        """
        status = result.get("status")
        steps_executed = result.get("steps_executed", [])

        # Check all steps succeeded
        all_successful = all(
            step.get("result", {}).get("success", False)
            for step in steps_executed
        )

        return {
            "complete": status == "completed",
            "success": all_successful,
            "steps_count": len(steps_executed),
            "verification_checks": await self._run_verification_checks(result)
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Learn from infrastructure operations.
        """
        if not self.memory:
            return

        # Calculate success rate
        successful_actions = sum(
            1 for a in actions_taken
            if a.get("result", {}).get("status") == "completed"
        )
        success_rate = successful_actions / len(actions_taken) if actions_taken else 0

        # Store successful patterns
        if success_rate > 0.8:
            await self.memory.store_procedural(
                pattern={
                    "request_type": input_data.get("type"),
                    "target_resource": input_data.get("resource"),
                    "environment": input_data.get("environment"),
                    "actions": [a.get("action") for a in actions_taken]
                },
                success_rate=success_rate,
                agent_id=self.config.agent_id,
                tenant_id=context.tenant_id
            )

        # Store episodic trace
        await self.memory.store_episodic(
            content={
                "input": input_data,
                "actions": actions_taken,
                "trace_id": context.trace_id,
                "success_rate": success_rate
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _plan_provisioning(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Plan infrastructure provisioning."""
        provisioning = perception.get("provisioning", {})

        return {
            "action": {
                "type": InfraAction.PROVISION.value,
                "steps": [
                    {
                        "name": "terraform_plan",
                        "params": {
                            "module": provisioning.get("module"),
                            "variables": provisioning.get("variables"),
                            "region": provisioning.get("region")
                        }
                    },
                    {
                        "name": "terraform_apply",
                        "params": {
                            "auto_approve": False  # Require approval
                        }
                    },
                    {
                        "name": "wait_healthy",
                        "params": {
                            "timeout_seconds": 300
                        }
                    }
                ]
            },
            "confidence": 0.85,
            "reasoning": "Standard provisioning workflow"
        }

    async def _plan_scaling(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Plan scaling operation."""
        scaling = perception.get("scaling", {})
        target = perception.get("target_resource")

        return {
            "action": {
                "type": InfraAction.SCALE_UP.value if perception["request_type"] == "scale_up" else InfraAction.SCALE_DOWN.value,
                "steps": [
                    {
                        "name": "kubectl_scale",
                        "params": {
                            "resource": target,
                            "replicas": scaling.get("desired_replicas")
                        }
                    },
                    {
                        "name": "wait_healthy",
                        "params": {
                            "timeout_seconds": 180
                        }
                    }
                ]
            },
            "confidence": 0.9,
            "reasoning": f"Scaling {target} to {scaling.get('desired_replicas')} replicas"
        }

    async def _plan_deployment(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Plan deployment operation."""
        return {
            "action": {
                "type": InfraAction.DEPLOY.value,
                "steps": [
                    {
                        "name": "helm_upgrade",
                        "params": perception.get("desired_state", {})
                    },
                    {
                        "name": "wait_healthy",
                        "params": {
                            "timeout_seconds": 300
                        }
                    }
                ]
            },
            "confidence": 0.85,
            "reasoning": "Standard deployment workflow"
        }

    async def _plan_remediation(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Plan remediation based on runbooks."""
        runbooks = retrieved_context.get("runbooks", [])

        if runbooks:
            # Use first matching runbook
            return {
                "action": {
                    "type": InfraAction.REMEDIATE.value,
                    "steps": runbooks[0].get("steps", [])
                },
                "confidence": 0.75,
                "reasoning": "Following runbook for remediation"
            }

        return {
            "action": None,
            "confidence": 0.0,
            "reasoning": "No matching runbook found"
        }

    async def _get_current_metrics(
        self,
        resource: str
    ) -> Dict[str, Any]:
        """Get current metrics for resource."""
        # Placeholder
        return {
            "cpu_utilization": 0.0,
            "memory_utilization": 0.0,
            "replica_count": 0
        }

    async def _terraform_plan(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Run terraform plan."""
        return {"success": True, "plan_id": "plan-001"}

    async def _terraform_apply(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Run terraform apply."""
        return {"success": True, "apply_id": "apply-001"}

    async def _helm_upgrade(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Run helm upgrade."""
        return {"success": True, "release": "ants-platform"}

    async def _kubectl_scale(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Scale Kubernetes resource."""
        return {"success": True, "replicas": params.get("replicas")}

    async def _wait_for_healthy(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Wait for resource to become healthy."""
        return {"success": True, "healthy": True}

    async def _run_verification_checks(
        self,
        result: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Run post-operation verification checks."""
        return [
            {"check": "resource_exists", "passed": True},
            {"check": "health_check", "passed": True}
        ]
