"""
Policy Engine for ANTS.
Enforces governance rules using OPA (Open Policy Agent).
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import httpx
import structlog

logger = structlog.get_logger()


class PolicyDecision(Enum):
    """Possible policy decisions."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ALLOW_WITH_REDACTION = "ALLOW_WITH_REDACTION"
    QUARANTINE_AGENT = "QUARANTINE_AGENT"


@dataclass
class PolicyConfig:
    """Configuration for policy engine."""
    opa_url: str = "http://opa:8181"
    default_policy: str = "ants/authz"
    timeout_seconds: int = 5
    cache_ttl_seconds: int = 300


@dataclass
class PolicyResult:
    """Result of policy evaluation."""
    decision: PolicyDecision
    allowed: bool
    reason: Optional[str] = None
    conditions: List[str] = field(default_factory=list)
    redactions: List[str] = field(default_factory=list)
    audit_required: bool = True


class PolicyEngine:
    """
    Policy engine using OPA for governance.
    All agent actions are evaluated against policies.
    """

    def __init__(self, config: PolicyConfig):
        self.config = config
        self._client = httpx.AsyncClient(timeout=config.timeout_seconds)
        self._cache: Dict[str, PolicyResult] = {}

        logger.info("policy_engine_initialized", opa_url=config.opa_url)

    async def evaluate(
        self,
        input_data: Dict[str, Any],
        policy_path: Optional[str] = None
    ) -> PolicyResult:
        """
        Evaluate input against policy.
        """
        policy = policy_path or self.config.default_policy

        # Build OPA input
        opa_input = {
            "input": input_data
        }

        try:
            response = await self._client.post(
                f"{self.config.opa_url}/v1/data/{policy.replace('.', '/')}",
                json=opa_input
            )
            response.raise_for_status()

            result = response.json().get("result", {})

            decision = PolicyDecision(result.get("decision", "DENY"))

            policy_result = PolicyResult(
                decision=decision,
                allowed=decision == PolicyDecision.ALLOW,
                reason=result.get("reason"),
                conditions=result.get("conditions", []),
                redactions=result.get("redactions", []),
                audit_required=result.get("audit_required", True)
            )

            logger.debug(
                "policy_evaluated",
                decision=decision.value,
                policy=policy
            )

            return policy_result

        except Exception as e:
            logger.error("policy_evaluation_error", error=str(e))

            # Fail closed - deny on error
            return PolicyResult(
                decision=PolicyDecision.DENY,
                allowed=False,
                reason=f"Policy evaluation failed: {str(e)}"
            )

    async def check_tool_access(
        self,
        agent_id: str,
        tool_name: str,
        tool_args: Dict[str, Any],
        context: Dict[str, Any]
    ) -> PolicyResult:
        """
        Check if agent can use a specific tool.
        """
        return await self.evaluate({
            "agent_id": agent_id,
            "action": "tool_call",
            "tool": tool_name,
            "args": tool_args,
            "context": context
        }, "ants/tools")

    async def check_data_access(
        self,
        agent_id: str,
        data_classification: str,
        operation: str,
        context: Dict[str, Any]
    ) -> PolicyResult:
        """
        Check if agent can access data with given classification.
        """
        return await self.evaluate({
            "agent_id": agent_id,
            "action": "data_access",
            "classification": data_classification,
            "operation": operation,
            "context": context
        }, "ants/data")

    async def check_approval_required(
        self,
        agent_id: str,
        action: Dict[str, Any],
        estimated_impact: str
    ) -> PolicyResult:
        """
        Check if human approval is required for action.
        """
        return await self.evaluate({
            "agent_id": agent_id,
            "action": action,
            "estimated_impact": estimated_impact
        }, "ants/approval")

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
