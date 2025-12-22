"""
Finance Reconciliation Agent for ANTS.
Automates financial reconciliation processes.
"""
from typing import Dict, Any, List, Optional
import structlog

from src.core.agent.base import BaseAgent, AgentConfig, AgentContext

logger = structlog.get_logger()


class ReconciliationAgent(BaseAgent):
    """
    Agent for automating financial reconciliation tasks.
    Compares transactions across systems and identifies discrepancies.
    """

    def __init__(self, config: Optional[AgentConfig] = None):
        if config is None:
            config = AgentConfig(
                name="Reconciliation Agent",
                description="Automates financial reconciliation processes",
                tools=[
                    "query_erp",
                    "query_bank_statements",
                    "match_transactions",
                    "flag_discrepancy",
                    "generate_report"
                ],
                max_iterations=20,
                timeout_seconds=600,
                model_name="llama-3.1-nemotron-nano-8b"
            )
        super().__init__(config)

    async def perceive(
        self,
        input_data: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Parse reconciliation request and identify data sources.
        """
        logger.info(
            "perceiving_reconciliation_request",
            trace_id=context.trace_id,
            input_keys=list(input_data.keys())
        )

        # Extract key information
        perception = {
            "request_type": input_data.get("type", "standard"),
            "period_start": input_data.get("period_start"),
            "period_end": input_data.get("period_end"),
            "accounts": input_data.get("accounts", []),
            "tolerance_threshold": input_data.get("tolerance", 0.01),
            "source_systems": input_data.get("sources", ["erp", "bank"]),
            "urgency": input_data.get("urgency", "normal")
        }

        return perception

    async def retrieve(
        self,
        perception: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Retrieve relevant context from memory.
        """
        retrieved = {}

        if self.memory:
            # Get past reconciliation patterns for similar accounts
            procedural = await self.memory.retrieve_procedural(
                context={"accounts": perception["accounts"]},
                agent_id=self.config.agent_id,
                limit=5
            )
            retrieved["past_patterns"] = [p.content for p in procedural]

            # Get relevant semantic context
            semantic = await self.memory.retrieve_semantic(
                query=f"reconciliation rules for {perception['accounts']}",
                tenant_id=context.tenant_id,
                limit=10
            )
            retrieved["reconciliation_rules"] = [s.content for s in semantic]

        return retrieved

    async def reason(
        self,
        perception: Dict[str, Any],
        retrieved_context: Dict[str, Any],
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Determine reconciliation strategy and actions.
        """
        # Build prompt for LLM reasoning
        prompt = f"""
        You are a financial reconciliation expert. Based on the following context,
        determine the best reconciliation approach.

        Request:
        - Period: {perception['period_start']} to {perception['period_end']}
        - Accounts: {perception['accounts']}
        - Tolerance: {perception['tolerance_threshold']}
        - Sources: {perception['source_systems']}

        Past Successful Patterns:
        {retrieved_context.get('past_patterns', [])}

        Reconciliation Rules:
        {retrieved_context.get('reconciliation_rules', [])}

        Provide a structured reconciliation plan.
        """

        if self.llm:
            response = await self.llm.generate(
                prompt=prompt,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )

            return {
                "action": {
                    "type": "reconcile",
                    "steps": response.get("steps", []),
                    "matching_criteria": response.get("matching_criteria", {})
                },
                "confidence": response.get("confidence", 0.8),
                "reasoning": response.get("reasoning", "")
            }

        # Fallback logic without LLM
        return {
            "action": {
                "type": "reconcile",
                "steps": [
                    {"name": "fetch_erp_data", "params": perception},
                    {"name": "fetch_bank_data", "params": perception},
                    {"name": "match_transactions", "params": {"tolerance": perception["tolerance_threshold"]}},
                    {"name": "identify_discrepancies", "params": {}},
                    {"name": "generate_report", "params": {}}
                ]
            },
            "confidence": 0.75
        }

    async def execute(
        self,
        action: Dict[str, Any],
        context: AgentContext
    ) -> Any:
        """
        Execute the reconciliation action.
        """
        results = {
            "matched_transactions": [],
            "discrepancies": [],
            "summary": {}
        }

        for step in action.get("steps", []):
            step_name = step.get("name")
            step_params = step.get("params", {})

            logger.info(
                "executing_reconciliation_step",
                trace_id=context.trace_id,
                step=step_name
            )

            if step_name == "fetch_erp_data":
                # Placeholder: Fetch from ERP system
                results["erp_data"] = await self._fetch_erp_data(step_params, context)

            elif step_name == "fetch_bank_data":
                # Placeholder: Fetch from bank
                results["bank_data"] = await self._fetch_bank_data(step_params, context)

            elif step_name == "match_transactions":
                # Match transactions
                results["matched_transactions"] = await self._match_transactions(
                    results.get("erp_data", []),
                    results.get("bank_data", []),
                    step_params.get("tolerance", 0.01)
                )

            elif step_name == "identify_discrepancies":
                # Find discrepancies
                results["discrepancies"] = await self._identify_discrepancies(
                    results.get("erp_data", []),
                    results.get("bank_data", []),
                    results.get("matched_transactions", [])
                )

            elif step_name == "generate_report":
                # Generate summary report
                results["summary"] = await self._generate_report(results)

        return results

    async def verify(
        self,
        result: Any,
        context: AgentContext
    ) -> Dict[str, Any]:
        """
        Verify reconciliation results.
        """
        # Check for completion criteria
        discrepancy_count = len(result.get("discrepancies", []))
        matched_count = len(result.get("matched_transactions", []))

        is_complete = result.get("summary", {}).get("generated", False)

        return {
            "complete": is_complete,
            "quality_score": 1.0 if discrepancy_count == 0 else 0.8,
            "metrics": {
                "matched_count": matched_count,
                "discrepancy_count": discrepancy_count
            }
        }

    async def learn(
        self,
        input_data: Dict[str, Any],
        actions_taken: List[Dict[str, Any]],
        context: AgentContext
    ):
        """
        Store successful reconciliation patterns.
        """
        if not self.memory:
            return

        # Determine success rate
        if actions_taken:
            last_result = actions_taken[-1].get("result", {})
            discrepancy_count = len(last_result.get("discrepancies", []))
            matched_count = len(last_result.get("matched_transactions", []))

            if matched_count > 0:
                success_rate = 1.0 - (discrepancy_count / (matched_count + discrepancy_count))

                # Store procedural memory if success rate is high
                if success_rate > 0.9:
                    await self.memory.store_procedural(
                        pattern={
                            "input_type": input_data.get("type"),
                            "accounts": input_data.get("accounts"),
                            "actions": [a.get("action") for a in actions_taken]
                        },
                        success_rate=success_rate,
                        agent_id=self.config.agent_id,
                        tenant_id=context.tenant_id
                    )

        # Store episodic memory
        await self.memory.store_episodic(
            content={
                "input": input_data,
                "actions": actions_taken,
                "trace_id": context.trace_id
            },
            agent_id=self.config.agent_id,
            tenant_id=context.tenant_id
        )

    async def _fetch_erp_data(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> List[Dict[str, Any]]:
        """Fetch transaction data from ERP system."""
        # Placeholder implementation
        return []

    async def _fetch_bank_data(
        self,
        params: Dict[str, Any],
        context: AgentContext
    ) -> List[Dict[str, Any]]:
        """Fetch transaction data from bank."""
        # Placeholder implementation
        return []

    async def _match_transactions(
        self,
        erp_data: List[Dict[str, Any]],
        bank_data: List[Dict[str, Any]],
        tolerance: float
    ) -> List[Dict[str, Any]]:
        """Match transactions between systems."""
        # Placeholder implementation
        matched = []
        return matched

    async def _identify_discrepancies(
        self,
        erp_data: List[Dict[str, Any]],
        bank_data: List[Dict[str, Any]],
        matched: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identify unmatched or discrepant transactions."""
        discrepancies = []
        return discrepancies

    async def _generate_report(
        self,
        results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate reconciliation summary report."""
        return {
            "generated": True,
            "total_matched": len(results.get("matched_transactions", [])),
            "total_discrepancies": len(results.get("discrepancies", [])),
            "reconciliation_status": "complete"
        }
