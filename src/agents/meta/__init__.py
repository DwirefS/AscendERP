"""
Meta-agent module for ANTS.

Meta-agents create capabilities for other agents:
- IntegrationBuilderAgent: Generates MCP tool code dynamically
- ToolDiscoveryAgent: Explores APIs and discovers available endpoints
- MetaAgentOrchestrator: Coordinates end-to-end capability acquisition
- CodeExecutionAgent: Executes Python/JavaScript/SQL in secure sandbox
"""
from src.agents.meta.integration_builder import (
    IntegrationBuilderAgent,
    create_integration_builder
)
from src.agents.meta.tool_discovery import (
    ToolDiscoveryAgent,
    DiscoveryMethod,
    create_tool_discovery_agent
)
from src.agents.meta.orchestrator import (
    MetaAgentOrchestrator,
    create_meta_orchestrator
)
from src.agents.meta.code_executor import (
    CodeExecutionAgent,
    CodeLanguage,
    ExecutionStatus,
    ExecutionResult,
    ResourceLimits,
    create_code_executor
)

__all__ = [
    # Integration Builder
    "IntegrationBuilderAgent",
    "create_integration_builder",
    # Tool Discovery
    "ToolDiscoveryAgent",
    "DiscoveryMethod",
    "create_tool_discovery_agent",
    # Orchestrator
    "MetaAgentOrchestrator",
    "create_meta_orchestrator",
    # Code Executor
    "CodeExecutionAgent",
    "CodeLanguage",
    "ExecutionStatus",
    "ExecutionResult",
    "ResourceLimits",
    "create_code_executor",
]
