"""
ANTS Agent Orchestrator - The Swarm Coordinator.
Implements ant colony swarm intelligence for multi-agent coordination.
"""
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import uuid
import structlog

from src.core.agent.base import BaseAgent, AgentContext, AgentResult
from src.core.agent.registry import get_registry

logger = structlog.get_logger()


class PheromoneType(Enum):
    """Types of pheromone signals in the swarm."""
    TASK_COMPLETE = "task_complete"
    RESOURCE_AVAILABLE = "resource_available"
    EXPERTISE = "expertise"
    THREAT_DETECTED = "threat_detected"
    LOAD_HIGH = "load_high"
    HELP_NEEDED = "help_needed"
    PATTERN_FOUND = "pattern_found"


@dataclass
class PheromoneSignal:
    """
    Like ant pheromones - signals that coordinate swarm behavior.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: PheromoneType = PheromoneType.TASK_COMPLETE
    strength: float = 1.0  # 0.0 to 1.0
    location: str = ""  # task_id, resource_id, etc.
    emitter_agent: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    decay_rate: float = 0.1  # how fast signal weakens per minute
    metadata: Dict[str, Any] = field(default_factory=dict)

    def current_strength(self) -> float:
        """Calculate current strength after decay."""
        age_minutes = (datetime.utcnow() - self.timestamp).total_seconds() / 60
        return max(0.0, self.strength - (self.decay_rate * age_minutes))


@dataclass
class Task:
    """Work item in the swarm."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    priority: int = 5  # 1-10
    requirements: Dict[str, Any] = field(default_factory=dict)
    input_data: Dict[str, Any] = field(default_factory=dict)
    deadline: Optional[datetime] = None
    assigned_agent: Optional[str] = None
    status: str = "pending"  # pending, assigned, running, complete, failed
    attempts: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None

    def pheromone_strength(self) -> float:
        """Calculate task pheromone strength based on urgency."""
        base_strength = self.priority / 10.0

        # Increase with age
        age_hours = (datetime.utcnow() - self.created_at).total_seconds() / 3600
        age_factor = min(2.0, 1.0 + (age_hours * 0.1))

        # Decrease with failed attempts
        attempt_penalty = max(0.3, 1.0 - (self.attempts * 0.1))

        return min(1.0, base_strength * age_factor * attempt_penalty)


@dataclass
class AgentState:
    """State of an agent in the swarm."""
    agent_id: str
    agent_type: str
    status: str = "idle"  # idle, busy, overloaded, offline
    current_task: Optional[str] = None
    load: float = 0.0  # 0.0 to 1.0
    capabilities: List[str] = field(default_factory=list)
    success_rate: float = 1.0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)


class SwarmOrchestrator:
    """
    Main orchestrator implementing ant colony swarm intelligence.
    Coordinates hundreds to thousands of agents working together.
    """

    def __init__(self):
        self.registry = get_registry()

        # Task management
        self.task_queue: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}

        # Agent pool
        self.agent_states: Dict[str, AgentState] = {}
        self.agent_instances: Dict[str, BaseAgent] = {}

        # Pheromone system
        self.pheromones: List[PheromoneSignal] = []

        # Swarm coordination
        self.swarm_active = False
        self._background_tasks: Set[asyncio.Task] = set()

        logger.info("swarm_orchestrator_initialized")

    async def start_swarm(self):
        """Start the swarm coordination system."""
        self.swarm_active = True

        # Start background workers
        task1 = asyncio.create_task(self._pheromone_decay_worker())
        task2 = asyncio.create_task(self._task_assignment_worker())
        task3 = asyncio.create_task(self._load_balancing_worker())
        task4 = asyncio.create_task(self._health_monitor_worker())

        self._background_tasks.update([task1, task2, task3, task4])

        logger.info("swarm_started", workers=len(self._background_tasks))

    async def stop_swarm(self):
        """Stop the swarm coordination system."""
        self.swarm_active = False

        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()

        await asyncio.gather(*self._background_tasks, return_exceptions=True)

        logger.info("swarm_stopped")

    async def submit_task(
        self,
        task_type: str,
        input_data: Dict[str, Any],
        priority: int = 5,
        deadline: Optional[datetime] = None
    ) -> str:
        """
        Submit a task to the swarm.
        Like dropping food scent - agents will converge.
        """
        task = Task(
            type=task_type,
            priority=priority,
            input_data=input_data,
            deadline=deadline
        )

        self.task_queue[task.id] = task

        # Emit task pheromone
        await self.emit_pheromone(
            type=PheromoneType.TASK_COMPLETE,
            strength=task.pheromone_strength(),
            location=task.id,
            metadata={"task_type": task_type, "priority": priority}
        )

        logger.info(
            "task_submitted",
            task_id=task.id,
            task_type=task_type,
            priority=priority
        )

        return task.id

    async def emit_pheromone(
        self,
        type: PheromoneType,
        strength: float,
        location: str,
        emitter: str = "orchestrator",
        **metadata
    ):
        """Emit a pheromone signal to coordinate swarm."""
        signal = PheromoneSignal(
            type=type,
            strength=strength,
            location=location,
            emitter_agent=emitter,
            metadata=metadata
        )

        self.pheromones.append(signal)

        logger.debug(
            "pheromone_emitted",
            type=type.value,
            strength=strength,
            location=location
        )

    def sense_pheromones(
        self,
        agent_id: str,
        pheromone_types: Optional[List[PheromoneType]] = None
    ) -> List[PheromoneSignal]:
        """
        Agent senses nearby pheromones.
        Returns signals sorted by strength.
        """
        # Filter by type if specified
        signals = self.pheromones

        if pheromone_types:
            signals = [s for s in signals if s.type in pheromone_types]

        # Filter out decayed signals
        signals = [s for s in signals if s.current_strength() > 0.1]

        # Sort by current strength
        signals.sort(key=lambda s: s.current_strength(), reverse=True)

        return signals

    async def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        capabilities: List[str]
    ):
        """Register an agent in the swarm."""
        state = AgentState(
            agent_id=agent_id,
            agent_type=agent_type,
            capabilities=capabilities,
            status="idle",
            load=0.0
        )

        self.agent_states[agent_id] = state

        logger.info(
            "agent_registered",
            agent_id=agent_id,
            agent_type=agent_type
        )

    async def unregister_agent(self, agent_id: str):
        """Remove agent from swarm."""
        if agent_id in self.agent_states:
            del self.agent_states[agent_id]

        if agent_id in self.agent_instances:
            del self.agent_instances[agent_id]

        logger.info("agent_unregistered", agent_id=agent_id)

    async def assign_task_to_agent(
        self,
        task_id: str,
        agent_id: str
    ) -> bool:
        """Assign a task to a specific agent."""
        task = self.task_queue.get(task_id)
        agent_state = self.agent_states.get(agent_id)

        if not task or not agent_state:
            return False

        # Update task
        task.assigned_agent = agent_id
        task.status = "assigned"

        # Update agent state
        agent_state.status = "busy"
        agent_state.current_task = task_id
        agent_state.load += 0.3  # Estimate

        logger.info(
            "task_assigned",
            task_id=task_id,
            agent_id=agent_id,
            task_type=task.type
        )

        # Execute task asynchronously
        asyncio.create_task(self._execute_task(task, agent_id))

        return True

    async def _execute_task(self, task: Task, agent_id: str):
        """Execute a task with an agent."""
        task.status = "running"
        task.attempts += 1

        try:
            # Get or create agent instance
            if agent_id not in self.agent_instances:
                agent_state = self.agent_states[agent_id]
                agent = self.registry.create_agent(agent_state.agent_type)
                self.agent_instances[agent_id] = agent
            else:
                agent = self.agent_instances[agent_id]

            # Create context
            context = AgentContext(
                trace_id=str(uuid.uuid4()),
                tenant_id=task.input_data.get("tenant_id", "default"),
                metadata={"task_id": task.id}
            )

            # Execute
            result = await agent.run(task.input_data, context)

            # Update task
            task.status = "complete" if result.success else "failed"
            task.result = result
            task.completed_at = datetime.utcnow()

            # Move to completed
            self.completed_tasks[task.id] = task
            del self.task_queue[task.id]

            # Update agent state
            agent_state = self.agent_states[agent_id]
            agent_state.status = "idle"
            agent_state.current_task = None
            agent_state.load = max(0.0, agent_state.load - 0.3)

            if result.success:
                # Update success rate
                agent_state.success_rate = (
                    agent_state.success_rate * 0.9 + 0.1
                )

                # Emit completion pheromone
                await self.emit_pheromone(
                    type=PheromoneType.TASK_COMPLETE,
                    strength=0.8,
                    location=task.id,
                    emitter=agent_id,
                    task_type=task.type
                )

            logger.info(
                "task_completed",
                task_id=task.id,
                agent_id=agent_id,
                success=result.success
            )

        except Exception as e:
            logger.error(
                "task_execution_failed",
                task_id=task.id,
                agent_id=agent_id,
                error=str(e)
            )

            task.status = "failed"

            # Update agent state
            agent_state = self.agent_states[agent_id]
            agent_state.status = "idle"
            agent_state.current_task = None
            agent_state.success_rate *= 0.95

            # Re-queue if attempts < 3
            if task.attempts < 3:
                task.status = "pending"
                task.assigned_agent = None

    async def recruit_agents(
        self,
        count: int,
        capability: Optional[str] = None,
        min_success_rate: float = 0.7
    ) -> List[str]:
        """
        Recruit idle agents for a task.
        Like ants recruiting nestmates.
        """
        idle_agents = [
            agent_id for agent_id, state in self.agent_states.items()
            if state.status == "idle" and state.success_rate >= min_success_rate
        ]

        if capability:
            idle_agents = [
                agent_id for agent_id in idle_agents
                if capability in self.agent_states[agent_id].capabilities
            ]

        # Sort by success rate
        idle_agents.sort(
            key=lambda aid: self.agent_states[aid].success_rate,
            reverse=True
        )

        return idle_agents[:count]

    async def scale_agent_pool(
        self,
        agent_type: str,
        target_count: int
    ):
        """
        Scale agent pool up or down.
        Like colony adjusting worker count.
        """
        current_agents = [
            aid for aid, state in self.agent_states.items()
            if state.agent_type == agent_type
        ]

        current_count = len(current_agents)

        if target_count > current_count:
            # Spawn new agents
            for _ in range(target_count - current_count):
                agent_id = f"{agent_type}-{uuid.uuid4().hex[:8]}"
                metadata = self.registry.get_metadata(agent_type)

                await self.register_agent(
                    agent_id=agent_id,
                    agent_type=agent_type,
                    capabilities=metadata.capabilities if metadata else []
                )

            logger.info(
                "agent_pool_scaled_up",
                agent_type=agent_type,
                new_count=target_count
            )

        elif target_count < current_count:
            # Remove idle agents
            idle = [
                aid for aid in current_agents
                if self.agent_states[aid].status == "idle"
            ]

            for agent_id in idle[:current_count - target_count]:
                await self.unregister_agent(agent_id)

            logger.info(
                "agent_pool_scaled_down",
                agent_type=agent_type,
                new_count=target_count
            )

    # Background workers implementing swarm behavior

    async def _pheromone_decay_worker(self):
        """Background worker for pheromone decay."""
        while self.swarm_active:
            # Remove fully decayed pheromones
            self.pheromones = [
                p for p in self.pheromones
                if p.current_strength() > 0.01
            ]

            await asyncio.sleep(60)  # Every minute

    async def _task_assignment_worker(self):
        """
        Background worker for task assignment.
        Implements ant foraging behavior - agents gravitate to strongest signals.
        """
        while self.swarm_active:
            # Get pending tasks
            pending = [t for t in self.task_queue.values() if t.status == "pending"]

            for task in pending:
                # Find suitable agents
                suitable = await self.recruit_agents(
                    count=1,
                    capability=task.type
                )

                if suitable:
                    await self.assign_task_to_agent(task.id, suitable[0])

            await asyncio.sleep(1)  # Check every second

    async def _load_balancing_worker(self):
        """
        Background worker for load balancing.
        Redistributes work like ants balance foraging.
        """
        while self.swarm_active:
            for agent_type in self.registry.get_categories():
                agents = [
                    (aid, state) for aid, state in self.agent_states.items()
                    if state.agent_type == agent_type
                ]

                if not agents:
                    continue

                avg_load = sum(state.load for _, state in agents) / len(agents)

                # Scale up if average load > 0.7
                if avg_load > 0.7:
                    await self.scale_agent_pool(
                        agent_type,
                        int(len(agents) * 1.5)
                    )

                # Scale down if average load < 0.3
                elif avg_load < 0.3 and len(agents) > 2:
                    await self.scale_agent_pool(
                        agent_type,
                        int(len(agents) * 0.7)
                    )

            await asyncio.sleep(30)  # Every 30 seconds

    async def _health_monitor_worker(self):
        """Monitor agent health and remove stale agents."""
        while self.swarm_active:
            now = datetime.utcnow()

            for agent_id, state in list(self.agent_states.items()):
                # Remove if no heartbeat in 5 minutes
                if (now - state.last_heartbeat).total_seconds() > 300:
                    logger.warning(
                        "agent_stale",
                        agent_id=agent_id
                    )
                    await self.unregister_agent(agent_id)

            await asyncio.sleep(60)  # Every minute

    async def get_swarm_status(self) -> Dict[str, Any]:
        """Get current swarm status."""
        agents_by_type = {}
        for state in self.agent_states.values():
            if state.agent_type not in agents_by_type:
                agents_by_type[state.agent_type] = {
                    "total": 0,
                    "idle": 0,
                    "busy": 0,
                    "avg_load": 0.0
                }

            agents_by_type[state.agent_type]["total"] += 1

            if state.status == "idle":
                agents_by_type[state.agent_type]["idle"] += 1
            elif state.status == "busy":
                agents_by_type[state.agent_type]["busy"] += 1

        # Calculate average load
        for stats in agents_by_type.values():
            if stats["total"] > 0:
                agents = [
                    s for s in self.agent_states.values()
                    if s.agent_type in agents_by_type
                ]
                stats["avg_load"] = sum(a.load for a in agents) / len(agents)

        return {
            "swarm_active": self.swarm_active,
            "total_agents": len(self.agent_states),
            "agents_by_type": agents_by_type,
            "pending_tasks": len([t for t in self.task_queue.values() if t.status == "pending"]),
            "running_tasks": len([t for t in self.task_queue.values() if t.status == "running"]),
            "completed_tasks": len(self.completed_tasks),
            "active_pheromones": len([p for p in self.pheromones if p.current_strength() > 0.1])
        }
