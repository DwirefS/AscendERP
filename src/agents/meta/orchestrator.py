"""
Meta-Agent Orchestrator - Coordinates the Self-Extending Agent Ecosystem.

This orchestrator manages the complete workflow:
1. ToolDiscoveryAgent finds new APIs
2. IntegrationBuilderAgent generates tools
3. DynamicToolRegistry registers and executes tools
4. Agents can request new capabilities on-the-fly

This is the "brain" that makes the meta-agent framework autonomous.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime
import asyncio
import structlog

from src.core.agent.base import BaseAgent, AgentConfig, ExecutionContext
from src.core.memory.substrate import MemorySubstrate
from src.core.inference.llm_client import LLMClient
from src.agents.meta.integration_builder import IntegrationBuilderAgent, IntegrationRequest
from src.agents.meta.tool_discovery import ToolDiscoveryAgent, DiscoveryRequest
from src.core.tools.dynamic_registry import (
    DynamicToolRegistry,
    get_global_registry,
    SandboxLevel,
    ToolStatus
)

logger = structlog.get_logger()


@dataclass
class CapabilityRequest:
    """Request for a new capability from an agent."""
    requesting_agent_id: str
    capability_description: str
    api_url: Optional[str] = None
    operations: Optional[List[str]] = None
    priority: str = "normal"  # "low", "normal", "high", "critical"
    auto_activate: bool = False  # Auto-activate after testing


@dataclass
class IntegrationResult:
    """Result of the complete integration workflow."""
    success: bool
    tool_ids: List[str]
    api_name: str
    operations_count: int
    discovery_confidence: float
    generation_success_rate: float
    time_taken_seconds: float
    error: Optional[str] = None


class MetaAgentOrchestrator:
    """
    Orchestrates the meta-agent framework.

    Workflow:
    1. Agent requests new capability
    2. ToolDiscoveryAgent explores the API
    3. IntegrationBuilderAgent generates tools for discovered endpoints
    4. DynamicToolRegistry validates and registers tools
    5. Tools are made available to all agents

    This creates a self-extending system where agents can acquire
    new capabilities autonomously.
    """

    def __init__(
        self,
        memory: MemorySubstrate,
        llm_client: LLMClient,
        tenant_id: str = "default"
    ):
        self.memory = memory
        self.llm_client = llm_client
        self.tenant_id = tenant_id

        # Create meta-agents
        self.discovery_agent = self._create_discovery_agent()
        self.builder_agent = self._create_builder_agent()

        # Get registry
        self.registry = get_global_registry()

        # Track integration requests
        self._integration_history: List[IntegrationResult] = []

    def _create_discovery_agent(self) -> ToolDiscoveryAgent:
        """Create ToolDiscoveryAgent instance."""
        from src.agents.meta.tool_discovery import create_tool_discovery_agent

        return create_tool_discovery_agent(
            tenant_id=self.tenant_id,
            memory=self.memory,
            llm_client=self.llm_client
        )

    def _create_builder_agent(self) -> IntegrationBuilderAgent:
        """Create IntegrationBuilderAgent instance."""
        from src.agents.meta.integration_builder import create_integration_builder_agent

        return create_integration_builder_agent(
            tenant_id=self.tenant_id,
            memory=self.memory,
            llm_client=self.llm_client
        )

    async def fulfill_capability_request(
        self,
        request: CapabilityRequest
    ) -> IntegrationResult:
        """
        Fulfill a capability request from an agent.

        Complete workflow from discovery to registration.
        """
        logger.info(
            "capability_request_received",
            requesting_agent=request.requesting_agent_id,
            description=request.capability_description
        )

        start_time = datetime.utcnow()

        try:
            # Step 1: Discover the API
            if request.api_url:
                logger.info("discovering_api", url=request.api_url)

                discovery_context = ExecutionContext(
                    request_id=f"discovery_{datetime.utcnow().timestamp()}",
                    tenant_id=self.tenant_id,
                    input_data={
                        "target_url": request.api_url,
                        "discovery_mode": "auto",
                        "max_endpoints": 50
                    }
                )

                discovery_result = await self.discovery_agent.run(discovery_context)

                if not discovery_result.get("success"):
                    return IntegrationResult(
                        success=False,
                        tool_ids=[],
                        api_name="unknown",
                        operations_count=0,
                        discovery_confidence=0.0,
                        generation_success_rate=0.0,
                        time_taken_seconds=0.0,
                        error=f"Discovery failed: {discovery_result.get('error')}"
                    )

                api_name = discovery_result["api_name"]
                discovered_api = discovery_result["discovered_api"]
                operations = request.operations or [
                    f"{ep.method.lower()}_{ep.path.replace('/', '_').strip('_')}"
                    for ep in discovered_api.endpoints[:10]
                ]

            else:
                # No URL provided - use LLM to find the API
                api_info = await self._find_api_with_llm(request.capability_description)

                if not api_info:
                    return IntegrationResult(
                        success=False,
                        tool_ids=[],
                        api_name="unknown",
                        operations_count=0,
                        discovery_confidence=0.0,
                        generation_success_rate=0.0,
                        time_taken_seconds=0.0,
                        error="Could not find API for requested capability"
                    )

                # Discover the found API
                discovery_context = ExecutionContext(
                    request_id=f"discovery_{datetime.utcnow().timestamp()}",
                    tenant_id=self.tenant_id,
                    input_data={
                        "target_url": api_info["url"],
                        "discovery_mode": "auto"
                    }
                )

                discovery_result = await self.discovery_agent.run(discovery_context)

                if not discovery_result.get("success"):
                    return IntegrationResult(
                        success=False,
                        tool_ids=[],
                        api_name=api_info["name"],
                        operations_count=0,
                        discovery_confidence=0.0,
                        generation_success_rate=0.0,
                        time_taken_seconds=0.0,
                        error="API discovery failed"
                    )

                api_name = discovery_result["api_name"]
                discovered_api = discovery_result["discovered_api"]
                operations = api_info.get("operations", [])

            # Step 2: Generate tools for discovered endpoints
            logger.info("generating_tools", api_name=api_name, operation_count=len(operations))

            generated_tools = []
            generation_errors = []

            for operation in operations[:10]:  # Limit to 10 operations
                try:
                    # Find matching endpoint
                    matching_endpoint = next(
                        (ep for ep in discovered_api.endpoints if operation in ep.path or operation in ep.description),
                        discovered_api.endpoints[0] if discovered_api.endpoints else None
                    )

                    if not matching_endpoint:
                        continue

                    # Generate tool
                    builder_context = ExecutionContext(
                        request_id=f"build_{datetime.utcnow().timestamp()}",
                        tenant_id=self.tenant_id,
                        input_data={
                            "api_name": api_name,
                            "api_documentation": f"Endpoint: {matching_endpoint.path}\nMethod: {matching_endpoint.method}\nDescription: {matching_endpoint.description}\nParameters: {matching_endpoint.parameters}",
                            "operations": [operation],
                            "auth_type": discovered_api.auth_config.get("type", "api_key"),
                            "auth_config": discovered_api.auth_config,
                            "schema_format": "inferred",
                            "sandbox_level": "restricted"
                        }
                    )

                    build_result = await self.builder_agent.run(builder_context)

                    if build_result.get("success"):
                        # Register tool in registry
                        tool_id = await self.registry.register_tool(
                            tool_name=f"{api_name}_{operation}",
                            description=f"{operation} operation for {api_name}",
                            code=build_result.get("generated_code", ""),
                            schema=build_result.get("schema", {}),
                            created_by=self.builder_agent.config.agent_id,
                            sandbox_level=SandboxLevel.RESTRICTED,
                            status=ToolStatus.TESTING if not request.auto_activate else ToolStatus.ACTIVE,
                            metadata={
                                "api_name": api_name,
                                "operation": operation,
                                "requested_by": request.requesting_agent_id
                            }
                        )

                        generated_tools.append(tool_id)

                        logger.info("tool_generated_and_registered", tool_id=tool_id, operation=operation)

                    else:
                        generation_errors.append(f"{operation}: {build_result.get('error')}")

                except Exception as e:
                    logger.error("tool_generation_failed", operation=operation, error=str(e))
                    generation_errors.append(f"{operation}: {str(e)}")

            # Calculate metrics
            time_taken = (datetime.utcnow() - start_time).total_seconds()
            generation_success_rate = len(generated_tools) / max(len(operations), 1)

            result = IntegrationResult(
                success=len(generated_tools) > 0,
                tool_ids=generated_tools,
                api_name=api_name,
                operations_count=len(generated_tools),
                discovery_confidence=discovery_result.get("confidence_score", 0.0),
                generation_success_rate=generation_success_rate,
                time_taken_seconds=time_taken,
                error=None if len(generated_tools) > 0 else f"Errors: {generation_errors}"
            )

            # Store in history
            self._integration_history.append(result)

            logger.info(
                "capability_request_fulfilled",
                success=result.success,
                tool_count=len(generated_tools),
                time_taken=time_taken
            )

            return result

        except Exception as e:
            logger.error("capability_fulfillment_failed", error=str(e))

            return IntegrationResult(
                success=False,
                tool_ids=[],
                api_name="unknown",
                operations_count=0,
                discovery_confidence=0.0,
                generation_success_rate=0.0,
                time_taken_seconds=(datetime.utcnow() - start_time).total_seconds(),
                error=str(e)
            )

    async def quick_integrate(
        self,
        api_url: str,
        operations: Optional[List[str]] = None,
        auto_activate: bool = False
    ) -> IntegrationResult:
        """
        Quick integration for a known API URL.

        Simplified interface for common use case.
        """
        request = CapabilityRequest(
            requesting_agent_id="system",
            capability_description=f"Integrate with API at {api_url}",
            api_url=api_url,
            operations=operations,
            auto_activate=auto_activate
        )

        return await self.fulfill_capability_request(request)

    async def search_and_integrate(
        self,
        capability_description: str,
        auto_activate: bool = False
    ) -> IntegrationResult:
        """
        Search for an API that provides the capability and integrate it.

        Uses LLM to find the right API.
        """
        request = CapabilityRequest(
            requesting_agent_id="system",
            capability_description=capability_description,
            auto_activate=auto_activate
        )

        return await self.fulfill_capability_request(request)

    async def get_integration_history(self) -> List[IntegrationResult]:
        """Get history of all integrations."""
        return self._integration_history

    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get all tools available in the registry."""
        return await self.registry.list_all_tools()

    async def _find_api_with_llm(self, capability_description: str) -> Optional[Dict[str, Any]]:
        """Use LLM to find the right API for a capability."""
        prompt = f"""Given the following capability requirement, identify the most appropriate public API to use:

Capability: {capability_description}

Return a JSON object with:
- "name": API name
- "url": API documentation or base URL
- "operations": List of likely operations needed

Only suggest well-known, public APIs with good documentation.
Return ONLY valid JSON."""

        try:
            response = await self.llm_client.generate(
                prompt=prompt,
                model="gpt-4o-mini",
                temperature=0.2,
                max_tokens=500
            )

            # Parse response
            import json

            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            api_info = json.loads(json_str)

            return api_info

        except Exception as e:
            logger.error("api_search_failed", error=str(e))
            return None


# Factory function
def create_meta_orchestrator(
    memory: MemorySubstrate,
    llm_client: LLMClient,
    tenant_id: str = "default"
) -> MetaAgentOrchestrator:
    """Create a MetaAgentOrchestrator instance."""
    return MetaAgentOrchestrator(
        memory=memory,
        llm_client=llm_client,
        tenant_id=tenant_id
    )


# Example usage
async def example_usage():
    """Example of using the meta-agent orchestrator."""
    from src.core.memory.database import DatabaseClient
    from src.core.memory.substrate import MemorySubstrate
    from src.core.inference.llm_client import LLMClient

    # Initialize dependencies
    db_client = DatabaseClient(
        connection_string="postgresql://user:pass@localhost:5432/ants"
    )
    await db_client.connect()

    memory = MemorySubstrate(db_client)
    llm_client = LLMClient(
        provider="azure_openai",
        api_key="your-key",
        endpoint="https://your-endpoint.openai.azure.com/"
    )

    # Create orchestrator
    orchestrator = create_meta_orchestrator(
        memory=memory,
        llm_client=llm_client,
        tenant_id="example_corp"
    )

    # Example 1: Quick integration with known API
    result1 = await orchestrator.quick_integrate(
        api_url="https://api.stripe.com/v1/",
        operations=["create_payment", "get_customer", "list_charges"],
        auto_activate=True
    )

    print(f"Stripe integration: {result1.success}, {len(result1.tool_ids)} tools created")

    # Example 2: Search for API based on capability
    result2 = await orchestrator.search_and_integrate(
        capability_description="Send SMS messages to customers",
        auto_activate=False  # Require manual activation
    )

    print(f"SMS integration: {result2.success}, API: {result2.api_name}")

    # Example 3: Agent requesting new capability
    capability_request = CapabilityRequest(
        requesting_agent_id="finance_reconciliation_agent",
        capability_description="Query invoice data from QuickBooks",
        api_url="https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/invoice",
        operations=["query_invoices", "get_invoice", "create_invoice"],
        priority="high",
        auto_activate=False
    )

    result3 = await orchestrator.fulfill_capability_request(capability_request)

    print(f"QuickBooks integration: {result3.success}, {result3.operations_count} operations")

    # List all available tools
    tools = await orchestrator.get_available_tools()
    print(f"\nTotal tools available: {len(tools)}")

    for tool in tools[:5]:  # Show first 5
        print(f"  - {tool['tool_name']}: {tool['description']} (used {tool['usage_count']} times)")
