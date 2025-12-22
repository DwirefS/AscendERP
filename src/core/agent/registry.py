"""
Agent Registry for ANTS.
Manages available agents and their lifecycles.
"""
from typing import Dict, Any, List, Optional, Type
from dataclasses import dataclass
import structlog

from src.core.agent.base import BaseAgent, AgentConfig

logger = structlog.get_logger()


@dataclass
class AgentMetadata:
    """Metadata about a registered agent."""
    agent_type: str
    name: str
    description: str
    version: str
    category: str
    capabilities: List[str]
    agent_class: Type[BaseAgent]
    config_template: AgentConfig


class AgentRegistry:
    """
    Registry for all available agents in the system.
    Provides discovery, instantiation, and lifecycle management.
    """

    def __init__(self):
        self._agents: Dict[str, AgentMetadata] = {}
        self._instances: Dict[str, BaseAgent] = {}

    def register(
        self,
        agent_type: str,
        agent_class: Type[BaseAgent],
        metadata: Dict[str, Any]
    ):
        """Register an agent type."""
        agent_metadata = AgentMetadata(
            agent_type=agent_type,
            name=metadata.get("name", agent_type),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0.0"),
            category=metadata.get("category", "general"),
            capabilities=metadata.get("capabilities", []),
            agent_class=agent_class,
            config_template=metadata.get("config_template", AgentConfig())
        )

        self._agents[agent_type] = agent_metadata

        logger.info(
            "agent_registered",
            agent_type=agent_type,
            name=agent_metadata.name
        )

    def get_metadata(self, agent_type: str) -> Optional[AgentMetadata]:
        """Get metadata for an agent type."""
        return self._agents.get(agent_type)

    def list_agents(
        self,
        category: Optional[str] = None
    ) -> List[AgentMetadata]:
        """List all registered agents, optionally filtered by category."""
        agents = list(self._agents.values())

        if category:
            agents = [a for a in agents if a.category == category]

        return agents

    def create_agent(
        self,
        agent_type: str,
        config: Optional[AgentConfig] = None
    ) -> BaseAgent:
        """Create a new instance of an agent."""
        metadata = self._agents.get(agent_type)

        if not metadata:
            raise ValueError(f"Unknown agent type: {agent_type}")

        # Use provided config or template
        agent_config = config or metadata.config_template

        # Create instance
        agent = metadata.agent_class(agent_config)

        logger.info(
            "agent_created",
            agent_type=agent_type,
            agent_id=agent_config.agent_id
        )

        return agent

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Get a running agent instance by ID."""
        return self._instances.get(agent_id)

    def register_instance(self, agent_id: str, agent: BaseAgent):
        """Register a running agent instance."""
        self._instances[agent_id] = agent

        logger.info(
            "agent_instance_registered",
            agent_id=agent_id
        )

    def unregister_instance(self, agent_id: str):
        """Unregister a running agent instance."""
        if agent_id in self._instances:
            del self._instances[agent_id]

            logger.info(
                "agent_instance_unregistered",
                agent_id=agent_id
            )

    def get_categories(self) -> List[str]:
        """Get all agent categories."""
        categories = set(a.category for a in self._agents.values())
        return sorted(categories)

    def search_agents(self, query: str) -> List[AgentMetadata]:
        """Search agents by name or description."""
        query_lower = query.lower()
        results = []

        for agent in self._agents.values():
            if (query_lower in agent.name.lower() or
                query_lower in agent.description.lower() or
                query_lower in agent.agent_type.lower()):
                results.append(agent)

        return results


# Global registry instance
_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """Get the global agent registry."""
    return _registry


def register_agent(
    agent_type: str,
    agent_class: Type[BaseAgent],
    **metadata
):
    """Decorator to register an agent class."""
    def decorator(cls):
        _registry.register(agent_type, cls, metadata)
        return cls

    # Allow use as decorator with or without calling
    if agent_class is None:
        return decorator
    else:
        _registry.register(agent_type, agent_class, metadata)
        return agent_class
