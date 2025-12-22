"""
ANTS Swarm Intelligence Components.

Implements ant colony-inspired coordination using:
- Azure Event Hub for pheromone messaging
- Azure Cosmos DB for swarm state persistence
"""
from src.core.swarm.pheromone_client import (
    PheromoneClient,
    PheromoneType,
    PheromoneStrength,
    PheromoneTrail,
    PheromoneDetection,
    create_pheromone_client
)
from src.core.swarm.pheromone_orchestrator import (
    PheromoneSwarmOrchestrator,
    SwarmTask,
    create_pheromone_orchestrator
)
from src.core.swarm.swarm_state import (
    SwarmStateManager,
    AgentState,
    TaskState,
    PheromoneRecord,
    SwarmMetrics,
    AgentStatus,
    TaskStatus,
    create_swarm_state_manager
)

__all__ = [
    # Pheromone messaging
    "PheromoneClient",
    "PheromoneType",
    "PheromoneStrength",
    "PheromoneTrail",
    "PheromoneDetection",
    "create_pheromone_client",
    # Swarm orchestration
    "PheromoneSwarmOrchestrator",
    "SwarmTask",
    "create_pheromone_orchestrator",
    # State persistence
    "SwarmStateManager",
    "AgentState",
    "TaskState",
    "PheromoneRecord",
    "SwarmMetrics",
    "AgentStatus",
    "TaskStatus",
    "create_swarm_state_manager",
]
