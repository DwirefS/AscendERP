"""
Defender Triage Agent for ANTS.
Automates security alert triage from Microsoft Defender.
"""
from typing import Dict, Any, List, Optional
from enum import Enum
import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


class AlertSeverity(Enum):
    """Security alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class TriageDecision(Enum):
    """Triage decision outcomes."""
    ESCALATE = "escalate"
    INVESTIGATE = "investigate"
    MONITOR = "monitor"
    FALSE_POSITIVE = "false_positive"
    REMEDIATE = "remediate"


class DefenderTriageAgent(BaseAgent):
    """
    Agent for triaging Microsoft Defender security alerts.
    Analyzes alerts, enriches with context, and makes triage decisions.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Defender Triage Agent",
                description="Automates security alert triage from Microsoft Defender",
                tools=[
                    "query_defender_api",
                    "enrich_with_threat_intel",
                    "query_asset_inventory",
                    "check_user_context",
                    "create_incident",
                    "isolate_endpoint",
                    "run_investigation"
                ],
                max_iterations=15,
                timeout_seconds=300,
                require_approval_threshold=0.9,  # High threshold for security actions
                model_name="llama-3.1-nemotron-nano-8b"
            )
        super().__init__(config)

        # Alert severity weights for prioritization
        self.severity_weights = {
            AlertSeverity.CRITICAL: 100,
            AlertSeverity.HIGH: 75,
            AlertSeverity.MEDIUM: 50,
            AlertSeverity.LOW: 25,
            AlertSeverity.INFORMATIONAL: 10
        }

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Parse security alert and extract key indicators.
        """
        logger.info(
            "perceiving_security_alert",
            trace_id=context.trace_id,
            alert_id=input_data.get("alert_id")
        )

        # Extract and normalize alert data
        severity_str = input_data.get("severity", "medium").lower()
        severity = AlertSeverity(severity_str) if severity_str in [s.value for s in AlertSeverity] else AlertSeverity.MEDIUM

        perception = {
            "alert_id": input_data.get("alert_id"),
            "title": input_data.get("title", "Unknown Alert"),
            "description": input_data.get("description", ""),
            "severity": severity,
            "priority_score": self.severity_weights.get(severity, 50),
            "category": input_data.get("category", "unknown"),
            "detection_source": input_data.get("detection_source", "defender"),
            "affected_entities": {
                "users": input_data.get("affected_users", []),
                "devices": input_data.get("affected_devices", []),
                "files": input_data.get("affected_files", []),
                "processes": input_data.get("affected_processes", []),
                "network": input_data.get("network_indicators", [])
            },
            "mitre_tactics": input_data.get("mitre_tactics", []),
            "mitre_techniques": input_data.get("mitre_techniques", []),
            "iocs": input_data.get("indicators_of_compromise", []),
            "timestamp": input_data.get("timestamp"),
            "raw_alert": input_data
        }

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context for triage decision.
        """
        retrieved = {}

        if self.memory:
            # Get similar past alerts and their resolutions
            semantic_results = await self.memory.retrieve_semantic(
                query=f"{perception['title']} {perception['category']} {perception['mitre_techniques']}",
                tenant_id=context.tenant_id,
                limit=10,
                threshold=0.75
            )
            retrieved["similar_alerts"] = [s.content for s in semantic_results]

            # Get successful triage patterns for this alert type
            procedural_results = await self.memory.retrieve_procedural(
                context={
                    "category": perception["category"],
                    "mitre_techniques": perception["mitre_techniques"]
                },
                agent_id=self.config.agent_id,
                limit=5
            )
            retrieved["triage_patterns"] = [p.content for p in procedural_results]

        # Enrich with threat intelligence (placeholder)
        retrieved["threat_intel"] = await self._enrich_threat_intel(perception["iocs"])

        # Get asset context
        retrieved["asset_context"] = await self._get_asset_context(
            perception["affected_entities"]
        )

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Analyze alert and determine triage decision.
        """
        # Build reasoning context
        prompt = f"""
        You are a security analyst performing alert triage. Analyze the following alert
        and determine the appropriate triage decision.

        Alert Details:
        - Title: {perception['title']}
        - Severity: {perception['severity'].value}
        - Category: {perception['category']}
        - MITRE Tactics: {perception['mitre_tactics']}
        - MITRE Techniques: {perception['mitre_techniques']}
        - Affected Entities: {perception['affected_entities']}

        Threat Intelligence:
        {retrieved_context.get('threat_intel', {})}

        Asset Context:
        {retrieved_context.get('asset_context', {})}

        Similar Past Alerts:
        {retrieved_context.get('similar_alerts', [])}

        Successful Triage Patterns:
        {retrieved_context.get('triage_patterns', [])}

        Provide:
        1. Triage decision (escalate, investigate, monitor, false_positive, remediate)
        2. Confidence score (0-1)
        3. Reasoning
        4. Recommended actions
        """

        if self.llm:
            response = await self.llm.generate(
                prompt=prompt,
                max_tokens=self.config.max_tokens,
                temperature=0.3  # Low temperature for security decisions
            )

            decision_str = response.get("decision", "investigate")
            decision = TriageDecision(decision_str) if decision_str in [d.value for d in TriageDecision] else TriageDecision.INVESTIGATE

            return {
                "action": {
                    "type": "triage",
                    "decision": decision,
                    "recommended_actions": response.get("recommended_actions", [])
                },
                "confidence": response.get("confidence", 0.7),
                "reasoning": response.get("reasoning", ""),
                "output": {
                    "decision": decision.value,
                    "severity": perception["severity"].value,
                    "alert_id": perception["alert_id"]
                }
            }

        # Fallback rule-based triage without LLM
        decision = self._rule_based_triage(perception, retrieved_context)

        return {
            "action": {
                "type": "triage",
                "decision": decision,
                "recommended_actions": self._get_default_actions(decision, perception)
            },
            "confidence": 0.6,
            "reasoning": "Rule-based triage applied",
            "output": {
                "decision": decision.value,
                "severity": perception["severity"].value,
                "alert_id": perception["alert_id"]
            }
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute triage actions.
        """
        decision = action.get("decision")
        recommended_actions = action.get("recommended_actions", [])

        results = {
            "decision": decision.value if isinstance(decision, TriageDecision) else decision,
            "actions_executed": [],
            "status": "completed"
        }

        for action_item in recommended_actions:
            action_type = action_item.get("type")
            action_params = action_item.get("params", {})

            logger.info(
                "executing_triage_action",
                trace_id=context.trace_id,
                action_type=action_type
            )

            if action_type == "create_incident":
                result = await self._create_incident(action_params, context)
                results["actions_executed"].append({
                    "type": "create_incident",
                    "result": result
                })

            elif action_type == "isolate_endpoint":
                # High-risk action - would require approval
                result = await self._isolate_endpoint(action_params, context)
                results["actions_executed"].append({
                    "type": "isolate_endpoint",
                    "result": result
                })

            elif action_type == "run_investigation":
                result = await self._run_investigation(action_params, context)
                results["actions_executed"].append({
                    "type": "run_investigation",
                    "result": result
                })

            elif action_type == "update_alert_status":
                result = await self._update_alert_status(action_params, context)
                results["actions_executed"].append({
                    "type": "update_alert_status",
                    "result": result
                })

        return results

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Verify triage execution results.
        """
        actions_executed = result.get("actions_executed", [])
        all_successful = all(
            action.get("result", {}).get("success", False)
            for action in actions_executed
        )

        return {
            "complete": True,
            "success": all_successful,
            "actions_count": len(actions_executed),
            "decision": result.get("decision")
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Learn from triage outcomes.
        """
        if not self.memory:
            return

        # Store as semantic memory for future retrieval
        alert_summary = f"""
        Alert: {input_data.get('title')}
        Category: {input_data.get('category')}
        Techniques: {input_data.get('mitre_techniques', [])}
        Decision: {actions_taken[-1].get('action', {}).get('decision') if actions_taken else 'unknown'}
        """

        await self.memory.store_semantic(
            content=alert_summary,
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id,
            metadata={
                "alert_id": input_data.get("alert_id"),
                "category": input_data.get("category"),
                "mitre_techniques": input_data.get("mitre_techniques", [])
            }
        )

        # Store successful pattern
        if actions_taken:
            last_action = actions_taken[-1]
            decision = last_action.get("action", {}).get("decision")

            if decision and decision != TriageDecision.FALSE_POSITIVE:
                await self.memory.store_procedural(
                    pattern={
                        "category": input_data.get("category"),
                        "mitre_techniques": input_data.get("mitre_techniques", []),
                        "decision": decision.value if isinstance(decision, TriageDecision) else decision,
                        "actions": [a.get("action") for a in actions_taken]
                    },
                    success_rate=0.85,  # Baseline until feedback
                    agent_id=self.config.agent_id,
                    tenant_id=context.tenant_id
                )

    def _rule_based_triage(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any]
    ) -> TriageDecision:
        """Fallback rule-based triage logic."""
        severity = perception["severity"]
        threat_intel = retrieved_context.get("threat_intel", {})

        # Critical severity always escalates
        if severity == AlertSeverity.CRITICAL:
            return TriageDecision.ESCALATE

        # Known malicious IOCs
        if threat_intel.get("malicious_score", 0) > 0.8:
            return TriageDecision.REMEDIATE

        # High severity with active threat
        if severity == AlertSeverity.HIGH:
            return TriageDecision.INVESTIGATE

        # Medium requires investigation
        if severity == AlertSeverity.MEDIUM:
            return TriageDecision.INVESTIGATE

        # Low severity - monitor
        return TriageDecision.MONITOR

    def _get_default_actions(
        self,
        decision: TriageDecision,
        perception: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Get default actions for triage decision."""
        actions = []

        if decision == TriageDecision.ESCALATE:
            actions.append({
                "type": "create_incident",
                "params": {
                    "severity": "critical",
                    "alert_id": perception["alert_id"]
                }
            })

        elif decision == TriageDecision.REMEDIATE:
            actions.append({
                "type": "isolate_endpoint",
                "params": {
                    "devices": perception["affected_entities"]["devices"]
                }
            })

        elif decision == TriageDecision.INVESTIGATE:
            actions.append({
                "type": "run_investigation",
                "params": {
                    "alert_id": perception["alert_id"]
                }
            })

        # Always update alert status
        actions.append({
            "type": "update_alert_status",
            "params": {
                "alert_id": perception["alert_id"],
                "status": decision.value
            }
        })

        return actions

    async def _enrich_threat_intel(
        self,
        iocs: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enrich IOCs with threat intelligence."""
        # Placeholder implementation
        return {
            "malicious_score": 0.0,
            "known_campaigns": [],
            "threat_actors": []
        }

    async def _get_asset_context(
        self,
        affected_entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get context about affected assets."""
        # Placeholder implementation
        return {
            "criticality": "medium",
            "business_unit": "unknown",
            "data_classification": "internal"
        }

    async def _create_incident(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Create security incident."""
        return {"success": True, "incident_id": "INC-001"}

    async def _isolate_endpoint(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Isolate compromised endpoint."""
        return {"success": True, "isolated_devices": params.get("devices", [])}

    async def _run_investigation(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Run automated investigation."""
        return {"success": True, "investigation_id": "INV-001"}

    async def _update_alert_status(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """Update alert status in Defender."""
        return {"success": True, "new_status": params.get("status")}
