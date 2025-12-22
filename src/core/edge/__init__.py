"""
Edge deployment module for ANTS.

Azure Arc and Azure Stack HCI integration for ultra-low latency
edge deployment of ANTS agents. Enables:
- On-premises agent deployment (<10ms latency)
- Local model inference (no cloud round-trip)
- Offline operation (zero cloud dependency)
- Hybrid architecture (local execution + cloud analytics)

This is critical for physical world control where cloud latency
(50-200ms) is too slow for real-time operations like:
- Manufacturing: Assembly line control
- Warehouses: Robot coordination
- Facilities: HVAC/lighting control
- Agriculture: Irrigation systems
"""
from src.core.edge.arc_agent_manager import (
    ArcAgentManager,
    EdgeDeploymentMode,
    EdgeCapability,
    EdgeAgentConfig,
    EdgeMetrics,
    create_arc_agent_manager
)

__all__ = [
    "ArcAgentManager",
    "EdgeDeploymentMode",
    "EdgeCapability",
    "EdgeAgentConfig",
    "EdgeMetrics",
    "create_arc_agent_manager",
]
