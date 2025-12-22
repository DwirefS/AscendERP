"""
Pheromone-Enhanced Swarm Orchestrator.

Integrates Azure Event Hub-based pheromone communication with agent orchestration
to enable true swarm intelligence coordination inspired by ant colonies.
"""
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
import structlog

from src.core.swarm.pheromone_client import (
    PheromoneClient,
    PheromoneType,
    PheromoneStrength,
    PheromoneTrail,
    PheromoneDetection
)
from src.core.agent.base import BaseAgent, ExecutionContext

logger = structlog.get_logger()


@dataclass
class SwarmTask:
    """A task in the swarm marketplace."""
    task_id: str
    task_type: str
    priority: int  # 1-10
    required_capabilities: List[str]
    payload: Dict[str, Any]
    created_at: datetime
    claimed_by: Optional[str] = None
    pheromone_strength: float = 0.0


class PheromoneSwarmOrchestrator:
    """
    Swarm orchestrator using pheromone-based coordination.

    Implements ant colony patterns:
    1. Task Discovery: Agents detect TASK pheromones to find work
    2. Resource Sharing: RESOURCE pheromones guide agents to available resources
    3. Danger Avoidance: DANGER pheromones mark failed paths/blocked resources
    4. Success Reinforcement: SUCCESS pheromones strengthen working patterns
    5. Load Balancing: LOAD_BALANCING pheromones distribute work evenly
    6. Capability Coordination: CAPABILITY pheromones signal integration needs
    """

    def __init__(
        self,
        pheromone_client: PheromoneClient,
        tenant_id: str = "default"
    ):
        self.pheromone_client = pheromone_client
        self.tenant_id = tenant_id

        # Task marketplace
        self._tasks: Dict[str, SwarmTask] = {}
        self._tasks_lock = asyncio.Lock()

        # Agent registry
        self._active_agents: Dict[str, BaseAgent] = {}
        self._agent_loads: Dict[str, float] = {}  # agent_id -> load (0.0-1.0)

        # Pheromone handlers registered
        self._handlers_registered = False

    async def start(self):
        """Start the swarm orchestrator."""
        logger.info("starting_pheromone_swarm_orchestrator", tenant_id=self.tenant_id)

        # Connect to Event Hub
        await self.pheromone_client.connect()

        # Register pheromone handlers
        await self._register_pheromone_handlers()

        # Start detecting pheromones
        await self.pheromone_client.start_detection()

        # Start background tasks
        asyncio.create_task(self._cleanup_loop())
        asyncio.create_task(self._load_balancing_loop())

        logger.info("pheromone_swarm_orchestrator_started")

    async def stop(self):
        """Stop the swarm orchestrator."""
        await self.pheromone_client.stop_detection()
        await self.pheromone_client.close()

        logger.info("pheromone_swarm_orchestrator_stopped")

    async def register_agent(self, agent: BaseAgent):
        """Register an agent in the swarm."""
        agent_id = agent.config.agent_id

        self._active_agents[agent_id] = agent
        self._agent_loads[agent_id] = 0.0

        # Deposit presence pheromone
        await self.pheromone_client.deposit_pheromone(
            pheromone_type=PheromoneType.RESOURCE,
            deposited_by=agent_id,
            data={
                "resource_type": "agent_capacity",
                "agent_type": agent.config.agent_type,
                "capabilities": agent.config.capabilities,
                "tenant_id": self.tenant_id
            },
            strength=PheromoneStrength.MEDIUM,
            ttl_seconds=300,  # Refresh every 5 minutes
            location=f"tenant.{self.tenant_id}"
        )

        logger.info("agent_registered_in_swarm", agent_id=agent_id)

    async def submit_task(
        self,
        task_type: str,
        required_capabilities: List[str],
        payload: Dict[str, Any],
        priority: int = 5
    ) -> str:
        """
        Submit a task to the swarm marketplace.

        Agents will detect the task pheromone and claim work.
        """
        task = SwarmTask(
            task_id=f"task_{datetime.utcnow().timestamp()}",
            task_type=task_type,
            priority=priority,
            required_capabilities=required_capabilities,
            payload=payload,
            created_at=datetime.utcnow()
        )

        # Add to marketplace
        async with self._tasks_lock:
            self._tasks[task.task_id] = task

        # Deposit task pheromone
        # Higher priority = stronger pheromone
        strength_map = {
            1: PheromoneStrength.TRACE,
            2: PheromoneStrength.TRACE,
            3: PheromoneStrength.LOW,
            4: PheromoneStrength.LOW,
            5: PheromoneStrength.MEDIUM,
            6: PheromoneStrength.MEDIUM,
            7: PheromoneStrength.HIGH,
            8: PheromoneStrength.HIGH,
            9: PheromoneStrength.CRITICAL,
            10: PheromoneStrength.CRITICAL
        }

        await self.pheromone_client.deposit_pheromone(
            pheromone_type=PheromoneType.TASK,
            deposited_by="orchestrator",
            data={
                "task_id": task.task_id,
                "task_type": task_type,
                "priority": priority,
                "required_capabilities": required_capabilities,
                "payload": payload
            },
            strength=strength_map.get(priority, PheromoneStrength.MEDIUM),
            ttl_seconds=3600,  # 1 hour
            location=f"tenant.{self.tenant_id}.tasks"
        )

        logger.info(
            "task_submitted_to_swarm",
            task_id=task.task_id,
            priority=priority,
            capabilities=required_capabilities
        )

        return task.task_id

    async def claim_task(self, agent_id: str, task_id: str) -> bool:
        """Agent claims a task from the marketplace."""
        async with self._tasks_lock:
            task = self._tasks.get(task_id)

            if not task or task.claimed_by:
                return False

            task.claimed_by = agent_id

            # Deposit success pheromone (task claimed)
            await self.pheromone_client.deposit_pheromone(
                pheromone_type=PheromoneType.SUCCESS,
                deposited_by=agent_id,
                data={
                    "event": "task_claimed",
                    "task_id": task_id,
                    "task_type": task.task_type
                },
                strength=PheromoneStrength.LOW,
                ttl_seconds=60
            )

            logger.info("task_claimed", task_id=task_id, agent_id=agent_id)

            return True

    async def complete_task(
        self,
        agent_id: str,
        task_id: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None
    ):
        """Mark task as complete and deposit success/danger pheromone."""
        async with self._tasks_lock:
            task = self._tasks.get(task_id)

            if not task:
                return

            # Remove from marketplace
            del self._tasks[task_id]

        if success:
            # Deposit strong success pheromone
            await self.pheromone_client.deposit_pheromone(
                pheromone_type=PheromoneType.SUCCESS,
                deposited_by=agent_id,
                data={
                    "event": "task_completed",
                    "task_id": task_id,
                    "task_type": task.task_type,
                    "result": result
                },
                strength=PheromoneStrength.HIGH,
                ttl_seconds=300,  # Reinforce successful patterns
                location=f"tenant.{self.tenant_id}.{task.task_type}"
            )

            logger.info("task_completed_successfully", task_id=task_id, agent_id=agent_id)
        else:
            # Deposit danger pheromone
            await self.pheromone_client.deposit_pheromone(
                pheromone_type=PheromoneType.DANGER,
                deposited_by=agent_id,
                data={
                    "event": "task_failed",
                    "task_id": task_id,
                    "task_type": task.task_type,
                    "error": result.get("error") if result else "unknown"
                },
                strength=PheromoneStrength.HIGH,
                ttl_seconds=600,  # Remember failures longer
                location=f"tenant.{self.tenant_id}.{task.task_type}"
            )

            logger.warning("task_failed", task_id=task_id, agent_id=agent_id)

    async def detect_work(
        self,
        agent_id: str,
        capabilities: List[str]
    ) -> List[SwarmTask]:
        """
        Agent detects available work through task pheromones.

        Returns tasks matching agent capabilities, sorted by pheromone strength.
        """
        # Detect task pheromones
        detection = await self.pheromone_client.detect_pheromones(
            pheromone_types=[PheromoneType.TASK],
            location=f"tenant.{self.tenant_id}.tasks",
            min_strength=0.1
        )

        available_tasks = []

        async with self._tasks_lock:
            for trail in detection.trails:
                task_id = trail.data.get("task_id")
                task = self._tasks.get(task_id)

                if not task or task.claimed_by:
                    continue

                # Check if agent has required capabilities
                required = set(task.required_capabilities)
                agent_caps = set(capabilities)

                if not required.issubset(agent_caps):
                    continue

                # Update task with current pheromone strength
                task.pheromone_strength = trail.current_strength()
                available_tasks.append(task)

        # Sort by pheromone strength (priority)
        available_tasks.sort(key=lambda t: t.pheromone_strength, reverse=True)

        logger.info(
            "work_detected",
            agent_id=agent_id,
            task_count=len(available_tasks),
            total_strength=detection.total_strength
        )

        return available_tasks

    async def report_danger(
        self,
        agent_id: str,
        danger_type: str,
        location: str,
        details: Dict[str, Any]
    ):
        """Agent reports a danger (error, blocked resource, threat)."""
        await self.pheromone_client.deposit_pheromone(
            pheromone_type=PheromoneType.DANGER,
            deposited_by=agent_id,
            data={
                "danger_type": danger_type,
                "details": details,
                "timestamp": datetime.utcnow().isoformat()
            },
            strength=PheromoneStrength.CRITICAL,
            ttl_seconds=900,  # 15 minutes
            location=location
        )

        logger.warning(
            "danger_reported",
            agent_id=agent_id,
            danger_type=danger_type,
            location=location
        )

    async def request_capability(
        self,
        agent_id: str,
        capability_description: str,
        api_url: Optional[str] = None,
        priority: str = "normal"
    ):
        """
        Agent requests a new capability through capability pheromone.

        MetaAgentOrchestrator detects these and fulfills requests.
        """
        strength_map = {
            "low": PheromoneStrength.LOW,
            "normal": PheromoneStrength.MEDIUM,
            "high": PheromoneStrength.HIGH,
            "critical": PheromoneStrength.CRITICAL
        }

        await self.pheromone_client.deposit_pheromone(
            pheromone_type=PheromoneType.CAPABILITY,
            deposited_by=agent_id,
            data={
                "capability_description": capability_description,
                "api_url": api_url,
                "priority": priority,
                "requested_at": datetime.utcnow().isoformat()
            },
            strength=strength_map.get(priority, PheromoneStrength.MEDIUM),
            ttl_seconds=1800,  # 30 minutes
            location=f"tenant.{self.tenant_id}.capabilities"
        )

        logger.info(
            "capability_requested",
            agent_id=agent_id,
            description=capability_description,
            priority=priority
        )

    async def update_load(self, agent_id: str, load: float):
        """Update agent load (0.0 = idle, 1.0 = fully loaded)."""
        self._agent_loads[agent_id] = load

        # If highly loaded, deposit load balancing pheromone
        if load >= 0.8:
            await self.pheromone_client.deposit_pheromone(
                pheromone_type=PheromoneType.LOAD_BALANCING,
                deposited_by=agent_id,
                data={
                    "load": load,
                    "agent_type": self._active_agents[agent_id].config.agent_type,
                    "message": "high_load"
                },
                strength=PheromoneStrength.HIGH,
                ttl_seconds=60,
                location=f"tenant.{self.tenant_id}.load"
            )

    async def get_swarm_status(self) -> Dict[str, Any]:
        """Get current status of the swarm."""
        async with self._tasks_lock:
            pending_tasks = [t for t in self._tasks.values() if not t.claimed_by]
            claimed_tasks = [t for t in self._tasks.values() if t.claimed_by]

        # Get pheromone metrics
        pheromone_metrics = await self.pheromone_client.get_swarm_metrics()

        # Agent metrics
        agent_count = len(self._active_agents)
        total_load = sum(self._agent_loads.values())
        avg_load = total_load / agent_count if agent_count > 0 else 0.0

        return {
            "tenant_id": self.tenant_id,
            "active_agents": agent_count,
            "average_load": avg_load,
            "pending_tasks": len(pending_tasks),
            "claimed_tasks": len(claimed_tasks),
            "pheromone_landscape": pheromone_metrics,
            "timestamp": datetime.utcnow().isoformat()
        }

    # Private methods

    async def _register_pheromone_handlers(self):
        """Register handlers for different pheromone types."""
        if self._handlers_registered:
            return

        # Handle capability requests
        async def on_capability_request(trail: PheromoneTrail):
            logger.info(
                "capability_request_detected",
                requesting_agent=trail.deposited_by,
                description=trail.data.get("capability_description")
            )
            # MetaAgentOrchestrator will handle this

        self.pheromone_client.register_handler(
            PheromoneType.CAPABILITY,
            on_capability_request
        )

        # Handle danger signals
        async def on_danger_detected(trail: PheromoneTrail):
            logger.warning(
                "danger_pheromone_detected",
                danger_type=trail.data.get("danger_type"),
                location=trail.location,
                deposited_by=trail.deposited_by
            )
            # Could trigger alerts, rerouting, etc.

        self.pheromone_client.register_handler(
            PheromoneType.DANGER,
            on_danger_detected
        )

        # Handle success patterns
        async def on_success_pattern(trail: PheromoneTrail):
            logger.info(
                "success_pattern_detected",
                event=trail.data.get("event"),
                task_type=trail.data.get("task_type"),
                strength=trail.current_strength()
            )
            # Could reinforce routing, update agent priorities

        self.pheromone_client.register_handler(
            PheromoneType.SUCCESS,
            on_success_pattern
        )

        self._handlers_registered = True

    async def _cleanup_loop(self):
        """Periodic cleanup of expired pheromones and completed tasks."""
        while True:
            try:
                await asyncio.sleep(60)  # Every minute

                # Cleanup expired pheromones
                await self.pheromone_client.cleanup_expired()

                # Cleanup old tasks
                async with self._tasks_lock:
                    cutoff = datetime.utcnow() - timedelta(hours=2)
                    old_tasks = [
                        task_id for task_id, task in self._tasks.items()
                        if task.created_at < cutoff
                    ]

                    for task_id in old_tasks:
                        del self._tasks[task_id]

                    if old_tasks:
                        logger.info("cleaned_old_tasks", count=len(old_tasks))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cleanup_loop_error", error=str(e))

    async def _load_balancing_loop(self):
        """Periodic load balancing through pheromones."""
        while True:
            try:
                await asyncio.sleep(30)  # Every 30 seconds

                # Detect overloaded agents
                for agent_id, load in self._agent_loads.items():
                    if load >= 0.9:
                        # Deposit strong load pheromone
                        await self.pheromone_client.deposit_pheromone(
                            pheromone_type=PheromoneType.LOAD_BALANCING,
                            deposited_by="orchestrator",
                            data={
                                "agent_id": agent_id,
                                "load": load,
                                "action": "scale_up_recommended"
                            },
                            strength=PheromoneStrength.CRITICAL,
                            ttl_seconds=120
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("load_balancing_loop_error", error=str(e))


# Factory function
def create_pheromone_orchestrator(
    pheromone_client: PheromoneClient,
    tenant_id: str = "default"
) -> PheromoneSwarmOrchestrator:
    """Create a PheromoneSwarmOrchestrator instance."""
    return PheromoneSwarmOrchestrator(
        pheromone_client=pheromone_client,
        tenant_id=tenant_id
    )
