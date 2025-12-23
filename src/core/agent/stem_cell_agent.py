"""
Stem Cell AI Agents: Polymorphic Resilience for ANTS

Revolutionary concept inspired by biological stem cells. Just as stem cells can
differentiate into any cell type the body needs, Stem Cell AI Agents can transform
into any agent type required by the enterprise, providing:

- High availability through dynamic role substitution
- Elastic scaling through instant differentiation
- Disaster recovery through rapid reconstitution
- Load balancing through adaptive specialization

Biological Analogy:
┌─────────────────────────────────────────────────────────┐
│  Stem Cell (Pluripotent)                                │
│  - Can become any cell type                             │
│  - Responds to environmental signals                    │
│  - Maintains capability until needed                    │
└────────────────────┬────────────────────────────────────┘
                     │
        Environmental Signal (Agent Failure, Surge, etc.)
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Differentiated Cell (Specialized)                      │
│  - Finance Agent                                        │
│  - Security Agent                                       │
│  - HR Agent                                            │
│  - (Any agent type needed)                             │
└─────────────────────────────────────────────────────────┘

ANTS Implementation:
- Stem cell agents are dormant, consuming minimal resources
- Monitor swarm for failures, surges, or capacity needs
- Differentiate instantly (seconds) into required agent type
- Load full capability set from shared memory substrate
- Operate as specialized agent until no longer needed
- Return to stem cell state (de-differentiate) to save resources

Use Cases:
1. High Availability: Finance agent crashes → stem cell becomes finance agent
2. DDoS Defense: Attack detected → stem cells become security agents
3. Black Friday Surge: Traffic spike → stem cells become CRM support agents
4. Disaster Recovery: Data center fails → stem cells reconstitute entire swarm
5. Cost Optimization: Off-hours → specialized agents sleep, stem cells on standby

This is the breakthrough for enterprise resilience at scale.

Example:
    from src.core.agent.stem_cell_agent import StemCellAgent

    # Create stem cell agent pool
    stem_cell_pool = StemCellPool(size=20)

    # Agent failure detected
    await stem_cell_pool.differentiate(
        target_type="finance.reconciliation",
        reason="primary_agent_failure",
        replace_agent_id="finance_01"
    )

    # Stem cell instantly becomes finance agent
    # Swarm continues operating without interruption
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.agent.base import BaseAgent


logger = logging.getLogger(__name__)


class DifferentiationTrigger(Enum):
    """Triggers for stem cell differentiation."""
    AGENT_FAILURE = "agent_failure"              # Primary agent crashed
    CAPACITY_SURGE = "capacity_surge"            # Load spike requires more agents
    DISASTER_RECOVERY = "disaster_recovery"      # Site/region failure
    SECURITY_THREAT = "security_threat"          # DDoS, attack, breach
    SCHEDULED_MAINTENANCE = "scheduled_maintenance"  # Planned replacement
    COST_OPTIMIZATION = "cost_optimization"      # Replace expensive agent
    TESTING = "testing"                          # A/B testing, canary deployment


class StemCellState(Enum):
    """Stem cell agent states."""
    PLURIPOTENT = "pluripotent"        # Can become any agent type
    DIFFERENTIATING = "differentiating"  # Currently transforming
    SPECIALIZED = "specialized"         # Functioning as specific agent type
    DEDIFFERENTIATING = "dedifferentiating"  # Returning to stem cell state
    DORMANT = "dormant"                 # Sleeping (minimal resources)


@dataclass
class DifferentiationRecord:
    """Record of stem cell differentiation event."""
    stem_cell_id: str
    target_agent_type: str
    trigger: DifferentiationTrigger
    differentiated_at: str
    specialized_duration_seconds: Optional[float] = None
    tasks_completed: int = 0
    reason: Optional[str] = None
    replaced_agent_id: Optional[str] = None


class StemCellAgent(BaseAgent):
    """
    Stem Cell AI Agent - Polymorphic agent with dynamic specialization.

    Capabilities:
    - Differentiate into any agent type on-demand
    - Load specialized capabilities from shared memory
    - Operate as specialized agent with full fidelity
    - De-differentiate back to pluripotent state
    - Minimal resource consumption when dormant
    - Instant activation (< 2 seconds)

    Architecture:
    - Universal agent runtime (can load any agent type's code)
    - Shared memory substrate (access to all agent knowledge)
    - Dynamic model routing (use appropriate models for role)
    - Hot-swappable tools (add/remove MCP tools on-the-fly)
    - State persistence (maintain continuity across differentiation)
    """

    def __init__(
        self,
        stem_cell_id: str,
        swarm_coordinator: Optional[Any] = None,
        **kwargs
    ):
        """
        Initialize Stem Cell Agent.

        Args:
            stem_cell_id: Unique stem cell identifier
            swarm_coordinator: Reference to swarm coordinator
            **kwargs: Additional configuration
        """
        super().__init__(
            agent_id=f"stem_cell_{stem_cell_id}",
            agent_type="meta.stem_cell",
            **kwargs
        )

        self.stem_cell_id = stem_cell_id
        self.swarm_coordinator = swarm_coordinator
        self.state = StemCellState.PLURIPOTENT

        # Current specialization
        self.specialized_type: Optional[str] = None
        self.specialized_capabilities: List[str] = []
        self.differentiation_timestamp: Optional[str] = None

        # History
        self.differentiation_history: List[DifferentiationRecord] = []

        # Statistics
        self.stats = {
            'total_differentiations': 0,
            'total_specialized_time_seconds': 0.0,
            'total_tasks_completed': 0,
            'by_agent_type': {},
            'by_trigger': {t.value: 0 for t in DifferentiationTrigger},
        }

        logger.info(f"Stem cell agent created: {self.stem_cell_id}")

    async def differentiate(
        self,
        target_agent_type: str,
        trigger: DifferentiationTrigger,
        reason: Optional[str] = None,
        replace_agent_id: Optional[str] = None,
        capabilities: Optional[List[str]] = None
    ) -> bool:
        """
        Differentiate into specialized agent type.

        This is the core polymorphic transformation. The stem cell:
        1. Validates it can become the target type
        2. Loads specialized capabilities from memory substrate
        3. Configures tools and models for the role
        4. Updates swarm coordinator with new identity
        5. Begins operating as specialized agent

        Args:
            target_agent_type: Agent type to become (e.g., "finance.reconciliation")
            trigger: What triggered differentiation
            reason: Human-readable reason
            replace_agent_id: If replacing failed agent, its ID
            capabilities: Specific capabilities to load (optional)

        Returns:
            Success status
        """
        if self.state not in [StemCellState.PLURIPOTENT, StemCellState.DORMANT]:
            logger.error(f"Cannot differentiate - already in state: {self.state.value}")
            return False

        logger.info(
            f"Stem cell {self.stem_cell_id} differentiating into {target_agent_type}",
            extra={
                'trigger': trigger.value,
                'reason': reason,
                'replace_agent_id': replace_agent_id
            }
        )

        self.state = StemCellState.DIFFERENTIATING

        try:
            # Step 1: Load agent type definition
            agent_definition = await self._load_agent_definition(target_agent_type)

            # Step 2: Load specialized capabilities from memory substrate
            if capabilities:
                loaded_capabilities = capabilities
            else:
                loaded_capabilities = await self._load_capabilities(target_agent_type)

            # Step 3: Configure tools for specialized role
            await self._configure_tools(target_agent_type, agent_definition)

            # Step 4: Configure models for specialized role
            await self._configure_models(target_agent_type, agent_definition)

            # Step 5: Load episodic/procedural memory for role
            await self._load_specialized_memory(target_agent_type)

            # Step 6: Update swarm coordinator
            if self.swarm_coordinator:
                await self.swarm_coordinator.register_agent(
                    agent_id=self.agent_id,
                    agent_type=target_agent_type,
                    capabilities=loaded_capabilities,
                    replaces=replace_agent_id
                )

            # Mark as specialized
            self.specialized_type = target_agent_type
            self.specialized_capabilities = loaded_capabilities
            self.differentiation_timestamp = datetime.utcnow().isoformat()
            self.state = StemCellState.SPECIALIZED

            # Update agent_type for operation
            self.agent_type = target_agent_type

            # Record differentiation
            record = DifferentiationRecord(
                stem_cell_id=self.stem_cell_id,
                target_agent_type=target_agent_type,
                trigger=trigger,
                differentiated_at=self.differentiation_timestamp,
                reason=reason,
                replaced_agent_id=replace_agent_id
            )
            self.differentiation_history.append(record)

            # Update statistics
            self.stats['total_differentiations'] += 1
            self.stats['by_agent_type'][target_agent_type] = \
                self.stats['by_agent_type'].get(target_agent_type, 0) + 1
            self.stats['by_trigger'][trigger.value] += 1

            logger.info(
                f"Differentiation complete: {self.stem_cell_id} → {target_agent_type}",
                extra={'capabilities': len(loaded_capabilities)}
            )

            return True

        except Exception as e:
            logger.error(f"Differentiation failed: {e}")
            self.state = StemCellState.PLURIPOTENT
            return False

    async def dedifferentiate(self) -> bool:
        """
        Return to pluripotent stem cell state.

        Called when specialized agent is no longer needed:
        - Load decreases below threshold
        - Replaced agent returns to health
        - Cost optimization triggers consolidation
        - Scheduled maintenance completes

        Returns:
            Success status
        """
        if self.state != StemCellState.SPECIALIZED:
            logger.warning(f"Cannot dedifferentiate - not specialized (state: {self.state.value})")
            return False

        logger.info(f"Stem cell {self.stem_cell_id} dedifferentiating from {self.specialized_type}")

        self.state = StemCellState.DEDIFFERENTIATING

        try:
            # Calculate specialized duration
            if self.differentiation_timestamp:
                start = datetime.fromisoformat(self.differentiation_timestamp)
                duration = (datetime.utcnow() - start).total_seconds()
            else:
                duration = 0.0

            # Update last differentiation record
            if self.differentiation_history:
                last_record = self.differentiation_history[-1]
                last_record.specialized_duration_seconds = duration
                last_record.tasks_completed = getattr(self, 'tasks_completed', 0)

            # Update statistics
            self.stats['total_specialized_time_seconds'] += duration
            self.stats['total_tasks_completed'] += getattr(self, 'tasks_completed', 0)

            # Unload specialized capabilities
            await self._unload_capabilities()

            # Unregister from swarm coordinator
            if self.swarm_coordinator:
                await self.swarm_coordinator.unregister_agent(
                    agent_id=self.agent_id,
                    reason="dedifferentiation"
                )

            # Reset to stem cell state
            self.specialized_type = None
            self.specialized_capabilities = []
            self.differentiation_timestamp = None
            self.agent_type = "meta.stem_cell"
            self.state = StemCellState.PLURIPOTENT

            logger.info(
                f"Dedifferentiation complete: {self.stem_cell_id}",
                extra={'specialized_duration_seconds': duration}
            )

            return True

        except Exception as e:
            logger.error(f"Dedifferentiation failed: {e}")
            return False

    async def _load_agent_definition(self, agent_type: str) -> Dict[str, Any]:
        """Load agent type definition from registry."""
        # In production, query agent registry/catalog
        # For now, return simulated definition
        return {
            'agent_type': agent_type,
            'description': f"Agent type: {agent_type}",
            'required_capabilities': [],
            'tools': [],
            'models': [],
            'policies': []
        }

    async def _load_capabilities(self, agent_type: str) -> List[str]:
        """Load specialized capabilities from memory substrate."""
        # In production, query memory substrate for agent type capabilities
        # For now, infer from agent type
        base_capabilities = ['perceive', 'retrieve', 'reason', 'execute', 'verify', 'learn']

        type_specific = []
        if 'finance' in agent_type:
            type_specific = ['financial_analysis', 'reconciliation', 'fraud_detection']
        elif 'security' in agent_type:
            type_specific = ['threat_detection', 'incident_response', 'forensics']
        elif 'hr' in agent_type:
            type_specific = ['recruitment', 'onboarding', 'performance_review']

        return base_capabilities + type_specific

    async def _configure_tools(self, agent_type: str, definition: Dict[str, Any]):
        """Configure MCP tools for specialized role."""
        # In production, load tools dynamically from MCP registry
        logger.debug(f"Configuring tools for {agent_type}")

    async def _configure_models(self, agent_type: str, definition: Dict[str, Any]):
        """Configure AI models for specialized role."""
        # In production, configure model router for agent type
        logger.debug(f"Configuring models for {agent_type}")

    async def _load_specialized_memory(self, agent_type: str):
        """Load episodic/procedural memory for specialized role."""
        # In production, load relevant memories from vector DB
        logger.debug(f"Loading specialized memory for {agent_type}")

    async def _unload_capabilities(self):
        """Unload specialized capabilities."""
        # Clear specialized tools, models, memory
        logger.debug("Unloading specialized capabilities")

    def get_stats(self) -> Dict[str, Any]:
        """Get stem cell statistics."""
        avg_specialized_time = (
            self.stats['total_specialized_time_seconds'] / self.stats['total_differentiations']
            if self.stats['total_differentiations'] > 0 else 0.0
        )

        return {
            **self.stats,
            'current_state': self.state.value,
            'specialized_type': self.specialized_type,
            'avg_specialized_time_seconds': avg_specialized_time,
            'differentiation_count': len(self.differentiation_history)
        }


class StemCellPool:
    """
    Pool of stem cell agents for enterprise resilience.

    Manages a pool of stem cell agents that can differentiate on-demand to:
    - Replace failed agents (high availability)
    - Handle surge capacity (elastic scaling)
    - Respond to threats (security resilience)
    - Optimize costs (dynamic resource allocation)

    Pool maintains optimal size based on:
    - Historical differentiation patterns
    - Current swarm health
    - Predicted demand
    - Cost constraints
    """

    def __init__(
        self,
        pool_size: int = 10,
        min_pool_size: int = 5,
        max_pool_size: int = 50,
        swarm_coordinator: Optional[Any] = None
    ):
        """
        Initialize stem cell pool.

        Args:
            pool_size: Initial pool size
            min_pool_size: Minimum pool size (always maintain)
            max_pool_size: Maximum pool size
            swarm_coordinator: Reference to swarm coordinator
        """
        self.pool_size = pool_size
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self.swarm_coordinator = swarm_coordinator

        # Create stem cell agents
        self.stem_cells: List[StemCellAgent] = []
        for i in range(pool_size):
            stem_cell = StemCellAgent(
                stem_cell_id=f"sc_{i:03d}",
                swarm_coordinator=swarm_coordinator
            )
            self.stem_cells.append(stem_cell)

        # Statistics
        self.stats = {
            'total_differentiations': 0,
            'active_specialized_agents': 0,
            'available_stem_cells': pool_size,
            'by_trigger': {t.value: 0 for t in DifferentiationTrigger},
        }

        logger.info(f"Stem cell pool initialized with {pool_size} agents")

    async def differentiate(
        self,
        target_type: str,
        trigger: DifferentiationTrigger,
        reason: Optional[str] = None,
        count: int = 1,
        **kwargs
    ) -> List[StemCellAgent]:
        """
        Differentiate one or more stem cells into specialized agents.

        Args:
            target_type: Agent type to create
            trigger: Differentiation trigger
            reason: Human-readable reason
            count: Number of agents to create
            **kwargs: Additional differentiation arguments

        Returns:
            List of differentiated agents
        """
        logger.info(
            f"Differentiating {count} stem cells into {target_type}",
            extra={'trigger': trigger.value, 'reason': reason}
        )

        # Find available stem cells
        available = [sc for sc in self.stem_cells if sc.state == StemCellState.PLURIPOTENT]

        if len(available) < count:
            logger.warning(
                f"Insufficient stem cells: requested {count}, available {len(available)}"
            )
            count = len(available)

        if count == 0:
            logger.error("No stem cells available for differentiation")
            return []

        # Differentiate
        differentiated = []
        for i in range(count):
            stem_cell = available[i]
            success = await stem_cell.differentiate(
                target_agent_type=target_type,
                trigger=trigger,
                reason=reason,
                **kwargs
            )

            if success:
                differentiated.append(stem_cell)

        # Update statistics
        self.stats['total_differentiations'] += len(differentiated)
        self.stats['active_specialized_agents'] = sum(
            1 for sc in self.stem_cells if sc.state == StemCellState.SPECIALIZED
        )
        self.stats['available_stem_cells'] = sum(
            1 for sc in self.stem_cells if sc.state == StemCellState.PLURIPOTENT
        )
        self.stats['by_trigger'][trigger.value] += len(differentiated)

        logger.info(f"Differentiated {len(differentiated)} stem cells successfully")
        return differentiated

    async def dedifferentiate_all(self, agent_type: Optional[str] = None) -> int:
        """
        Return specialized agents to stem cell state.

        Args:
            agent_type: If specified, only dedifferentiate this type

        Returns:
            Number of agents dedifferentiated
        """
        specialized = [
            sc for sc in self.stem_cells
            if sc.state == StemCellState.SPECIALIZED
            and (agent_type is None or sc.specialized_type == agent_type)
        ]

        count = 0
        for stem_cell in specialized:
            success = await stem_cell.dedifferentiate()
            if success:
                count += 1

        # Update statistics
        self.stats['active_specialized_agents'] = sum(
            1 for sc in self.stem_cells if sc.state == StemCellState.SPECIALIZED
        )
        self.stats['available_stem_cells'] = sum(
            1 for sc in self.stem_cells if sc.state == StemCellState.PLURIPOTENT
        )

        logger.info(f"Dedifferentiated {count} agents")
        return count

    def get_available_count(self) -> int:
        """Get count of available stem cells."""
        return sum(1 for sc in self.stem_cells if sc.state == StemCellState.PLURIPOTENT)

    def get_specialized_count(self) -> int:
        """Get count of specialized agents."""
        return sum(1 for sc in self.stem_cells if sc.state == StemCellState.SPECIALIZED)

    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            **self.stats,
            'pool_size': len(self.stem_cells),
            'utilization': self.stats['active_specialized_agents'] / len(self.stem_cells)
            if self.stem_cells else 0.0
        }


def create_stem_cell_pool(**kwargs) -> StemCellPool:
    """
    Factory function to create stem cell pool.

    Args:
        **kwargs: Arguments for StemCellPool

    Returns:
        Configured StemCellPool
    """
    return StemCellPool(**kwargs)
