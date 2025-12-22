"""
ANTS Swarm Intelligence Components.

Implements ant colony-inspired coordination using Azure Event Hub for pheromone messaging.
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

__all__ = [
    "PheromoneClient",
    "PheromoneType",
    "PheromoneStrength",
    "PheromoneTrail",
    "PheromoneDetection",
    "create_pheromone_client",
    "PheromoneSwarmOrchestrator",
    "SwarmTask",
    "create_pheromone_orchestrator",
]
