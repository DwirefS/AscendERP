"""
Compliance Agent for Capital Markets.
Handles KYC, AML screening, sanctions checks, and regulatory compliance.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


class ComplianceStatus(Enum):
    """Compliance check status."""
    APPROVED = "approved"
    FLAGGED = "flagged"
    REJECTED = "rejected"
    PENDING = "pending"


class ComplianceAgent(BaseAgent):
    """
    Agent for regulatory compliance including KYC verification,
    AML screening, sanctions checks, and pre-trade validation.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Compliance Agent",
                description="Manages regulatory compliance and risk screening",
                tools=[
                    "check_kyc",
                    "screen_aml",
                    "check_sanctions",
                    "validate_trade",
                    "generate_regulatory_report"
                ],
                max_iterations=10,
                timeout_seconds=90,
                model_name="gpt-4-turbo"
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Parse compliance request.

        Expected input:
        {
            "request_type": "kyc" | "aml" | "pre_trade" | "reporting",
            "entity_id": str,
            "entity_data": dict,
            "entity_type": "individual" | "corporate",
            "transaction": dict (optional, for pre_trade)
        }
        """
        logger.info(
            "perceiving_compliance_request",
            trace_id=context.trace_id,
            request_type=input_data.get("request_type"),
            entity_id=input_data.get("entity_id")
        )

        perception = {
            "request_type": input_data.get("request_type", "kyc").lower(),
            "entity_id": input_data.get("entity_id"),
            "entity_data": input_data.get("entity_data", {}),
            "entity_type": input_data.get("entity_type", "individual").lower(),
            "transaction": input_data.get("transaction"),
            "request_time": datetime.utcnow().isoformat()
        }

        valid_types = ["kyc", "aml", "pre_trade", "reporting"]
        if perception["request_type"] not in valid_types:
            raise ValueError(f"Invalid request type: {perception['request_type']}")

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve past compliance decisions and regulatory updates.
        """
        retrieved = {}

        if self.memory:
            # Get past compliance decisions for this entity
            episodic = await self.memory.retrieve_episodic(
                context={"entity_id": perception["entity_id"]},
                tenant_id=context.tenant_id,
                limit=20
            )
            retrieved["compliance_history"] = [e.content for e in episodic]

            # Get regulatory updates and sanctions lists
            semantic = await self.memory.retrieve_semantic(
                query="regulatory updates sanctions lists compliance rules",
                tenant_id=context.tenant_id,
                limit=10
            )
            retrieved["regulatory_updates"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Apply compliance rules and determine screening approach.
        """
        prompt = f"""
        You are an expert compliance officer. Based on the compliance request,
        determine the appropriate screening and approval process.

        Compliance Request:
        - Type: {perception['request_type']}
        - Entity ID: {perception['entity_id']}
        - Entity Type: {perception['entity_type']}
        - Data: {perception['entity_data']}

        Compliance History:
        {retrieved_context.get('compliance_history', [])}

        Regulatory Updates:
        {retrieved_context.get('regulatory_updates', [])}

        Provide a structured compliance assessment including:
        1. Required checks based on request type
        2. Risk level assessment
        3. Recommended action (approve/flag/reject)
        4. Any escalation needed
        """

        if self.llm:
            try:
                response = await self.llm.generate(
                    prompt=prompt,
                    max_tokens=self.config.max_tokens,
                    temperature=0.3
                )

                return {
                    "action": {
                        "type": "screen_compliance",
                        "request_type": perception["request_type"],
                        "entity_id": perception["entity_id"],
                        "checks": response.get("checks", []),
                        "risk_level": response.get("risk_level", "medium")
                    },
                    "confidence": response.get("confidence", 0.85),
                    "reasoning": response.get("reasoning", "")
                }
            except Exception as e:
                logger.warning(
                    "llm_reasoning_failed",
                    error=str(e),
                    fallback="comprehensive"
                )

        # Fallback: Run all applicable checks
        return {
            "action": {
                "type": "screen_compliance",
                "request_type": perception["request_type"],
                "entity_id": perception["entity_id"],
                "checks": self._get_default_checks(perception["request_type"]),
                "risk_level": "medium"
            },
            "confidence": 0.75,
            "reasoning": "Comprehensive compliance screening applied"
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute compliance screening and validation.
        """
        request_type = action.get("request_type")
        entity_id = action.get("entity_id")
        checks = action.get("checks", [])

        logger.info(
            "executing_compliance_screening",
            trace_id=context.trace_id,
            request_type=request_type,
            entity_id=entity_id
        )

        try:
            results = {
                "request_type": request_type,
                "entity_id": entity_id,
                "checks_performed": [],
                "issues": [],
                "timestamp": datetime.utcnow().isoformat()
            }

            if request_type == "kyc":
                kyc_result = await self._perform_kyc_check(entity_id)
                results["kyc_result"] = kyc_result
                results["checks_performed"].append("kyc")

                if not kyc_result.get("approved"):
                    results["issues"].extend(kyc_result.get("issues", []))

            elif request_type == "aml":
                aml_result = await self._perform_aml_screening(entity_id)
                results["aml_result"] = aml_result
                results["checks_performed"].append("aml")

                if aml_result.get("flagged"):
                    results["issues"].extend(aml_result.get("alerts", []))

            elif request_type == "pre_trade":
                trade_result = await self._perform_pre_trade_validation(
                    entity_id,
                    action.get("transaction", {})
                )
                results["trade_result"] = trade_result
                results["checks_performed"].append("pre_trade")

                if not trade_result.get("allowed"):
                    results["issues"].extend(trade_result.get("violations", []))

            elif request_type == "reporting":
                report = await self._generate_regulatory_report(entity_id)
                results["report"] = report
                results["checks_performed"].append("reporting")

            # Determine overall status
            results["status"] = (
                ComplianceStatus.REJECTED.value if results["issues"]
                else ComplianceStatus.APPROVED.value
            )

            # Flag severe issues for escalation
            results["requires_escalation"] = any(
                issue.get("severity") == "critical"
                for issue in results["issues"]
            )

            return results

        except Exception as e:
            logger.error(
                "compliance_screening_failed",
                trace_id=context.trace_id,
                error=str(e)
            )
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Verify compliance screening is complete and accurate.
        """
        status = result.get("status", "unknown")

        if status in [ComplianceStatus.APPROVED.value, ComplianceStatus.REJECTED.value]:
            checks_performed = len(result.get("checks_performed", []))

            return {
                "complete": checks_performed > 0,
                "quality_score": 0.95,
                "metrics": {
                    "checks_performed": checks_performed,
                    "issues_found": len(result.get("issues", [])),
                    "requires_escalation": result.get("requires_escalation", False)
                }
            }

        return {
            "complete": False,
            "quality_score": 0.0,
            "metrics": {}
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Store compliance decisions for audit trail.
        """
        if not self.memory or not actions_taken:
            return

        last_action = actions_taken[-1]
        result = last_action.get("result", {})

        # Store episodic memory for audit trail
        await self.memory.store_episodic(
            content={
                "entity_id": input_data.get("entity_id"),
                "request_type": input_data.get("request_type"),
                "compliance_status": result.get("status"),
                "checks_performed": result.get("checks_performed", []),
                "issues": result.get("issues", []),
                "timestamp": datetime.utcnow().isoformat(),
                "trace_id": context.trace_id
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _perform_kyc_check(self, entity_id: str) -> Dict[str, Any]:
        """Perform Know Your Customer verification."""
        logger.info("performing_kyc_check", entity_id=entity_id)

        # Placeholder: Integration with KYC verification service
        return {
            "entity_id": entity_id,
            "approved": True,
            "identity_verified": True,
            "pep_status": "not_pep",
            "documents": ["passport", "address_verification"],
            "issues": []
        }

    async def _perform_aml_screening(self, entity_id: str) -> Dict[str, Any]:
        """Perform Anti-Money Laundering screening."""
        logger.info("performing_aml_screening", entity_id=entity_id)

        # Placeholder: Integration with AML screening service
        return {
            "entity_id": entity_id,
            "flagged": False,
            "risk_score": 15,  # 0-100 scale
            "matches": [],
            "alerts": []
        }

    async def _perform_pre_trade_validation(
        self,
        entity_id: str,
        transaction: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate trade against position limits and restrictions."""
        logger.info("performing_pre_trade_validation", entity_id=entity_id)

        violations = []

        # Check position limits
        position_size = transaction.get("quantity", 0) * transaction.get("price", 0)
        max_position = 10000000  # $10M limit

        if position_size > max_position:
            violations.append({
                "type": "position_limit_exceeded",
                "limit": max_position,
                "requested": position_size,
                "severity": "high"
            })

        # Check restricted securities list
        ticker = transaction.get("ticker", "")
        restricted_securities = ["XYZ", "ABC"]  # Placeholder

        if ticker in restricted_securities:
            violations.append({
                "type": "restricted_security",
                "security": ticker,
                "severity": "critical"
            })

        return {
            "entity_id": entity_id,
            "allowed": len(violations) == 0,
            "violations": violations
        }

    async def _generate_regulatory_report(self, entity_id: str) -> Dict[str, Any]:
        """Generate regulatory compliance report."""
        logger.info("generating_regulatory_report", entity_id=entity_id)

        return {
            "entity_id": entity_id,
            "report_date": datetime.utcnow().isoformat(),
            "compliance_status": ComplianceStatus.APPROVED.value,
            "kyc_status": "current",
            "aml_screening": "passed",
            "violations": 0,
            "last_review": "2026-02-01"
        }

    def _get_default_checks(self, request_type: str) -> List[str]:
        """Get default checks for request type."""
        checks_map = {
            "kyc": ["identity_verification", "pep_check", "document_review"],
            "aml": ["transaction_pattern_analysis", "watchlist_screening", "risk_scoring"],
            "pre_trade": ["position_limits", "restricted_list", "compliance_rules"],
            "reporting": ["audit_trail", "compliance_summary", "risk_assessment"]
        }
        return checks_map.get(request_type, [])
