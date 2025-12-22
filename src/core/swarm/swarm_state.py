"""
Swarm State Management with Azure Cosmos DB.

Provides globally distributed, low-latency persistence for swarm coordination state:
- Agent registry and health status
- Task assignments and history
- Pheromone trail persistence (beyond Event Hub retention)
- Swarm metrics and analytics
- Multi-region active-active deployment

Cosmos DB enables:
- Global distribution (99.999% availability)
- Single-digit millisecond latency worldwide
- Automatic indexing
- Multi-model (document, graph, key-value)
- Elastic scale
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import structlog
from azure.cosmos.aio import CosmosClient, DatabaseProxy, ContainerProxy
from azure.cosmos import PartitionKey, exceptions
from azure.identity.aio import DefaultAzureCredential

logger = structlog.get_logger()


class AgentStatus(Enum):
    """Agent lifecycle status."""
    ACTIVE = "active"
    SLEEPING = "sleeping"
    COLD = "cold"
    STARTING = "starting"
    STOPPING = "stopping"
    FAILED = "failed"


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentState:
    """Agent state stored in Cosmos DB."""
    id: str  # agent_id
    agent_id: str
    agent_type: str
    tenant_id: str
    status: str  # AgentStatus value
    capabilities: List[str]
    current_load: float  # 0.0-1.0
    current_task_id: Optional[str]
    last_heartbeat: str  # ISO datetime
    created_at: str  # ISO datetime
    updated_at: str  # ISO datetime
    metadata: Dict[str, Any]

    # Cosmos DB partition key
    partition_key: str  # tenant_id for multi-tenancy


@dataclass
class TaskState:
    """Task state stored in Cosmos DB."""
    id: str  # task_id
    task_id: str
    task_type: str
    tenant_id: str
    status: str  # TaskStatus value
    priority: int  # 1-10
    required_capabilities: List[str]
    payload: Dict[str, Any]
    claimed_by: Optional[str]  # agent_id
    claimed_at: Optional[str]  # ISO datetime
    started_at: Optional[str]
    completed_at: Optional[str]
    result: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]

    # Cosmos DB partition key
    partition_key: str  # tenant_id


@dataclass
class PheromoneRecord:
    """Pheromone trail record (persisted beyond Event Hub retention)."""
    id: str  # trail_id
    trail_id: str
    pheromone_type: str
    deposited_by: str
    strength: float
    deposited_at: str
    expires_at: str
    location: Optional[str]
    data: Dict[str, Any]
    tenant_id: str

    # Cosmos DB partition key
    partition_key: str  # tenant_id + location


@dataclass
class SwarmMetrics:
    """Swarm-wide metrics snapshot."""
    id: str  # timestamp-based ID
    tenant_id: str
    timestamp: str
    active_agents: int
    sleeping_agents: int
    pending_tasks: int
    completed_tasks_1h: int
    failed_tasks_1h: int
    average_task_duration_ms: float
    average_agent_load: float
    pheromone_trails_active: int
    total_cost_1h: float

    # Cosmos DB partition key
    partition_key: str  # tenant_id


class SwarmStateManager:
    """
    Manages swarm state in Azure Cosmos DB.

    Provides:
    - Agent registry and health tracking
    - Task assignment and history
    - Pheromone trail long-term storage
    - Swarm metrics and analytics
    - Multi-region consistency
    """

    def __init__(
        self,
        cosmos_endpoint: str,
        database_name: str = "ants_swarm",
        use_managed_identity: bool = True,
        cosmos_key: Optional[str] = None
    ):
        self.cosmos_endpoint = cosmos_endpoint
        self.database_name = database_name

        # Authentication
        if use_managed_identity:
            self.credential = DefaultAzureCredential()
            self.client = CosmosClient(
                url=cosmos_endpoint,
                credential=self.credential
            )
        else:
            if not cosmos_key:
                raise ValueError("cosmos_key required when not using managed identity")

            self.client = CosmosClient(
                url=cosmos_endpoint,
                credential=cosmos_key
            )
            self.credential = None

        # Containers (initialized in connect())
        self.database: Optional[DatabaseProxy] = None
        self.agents_container: Optional[ContainerProxy] = None
        self.tasks_container: Optional[ContainerProxy] = None
        self.pheromones_container: Optional[ContainerProxy] = None
        self.metrics_container: Optional[ContainerProxy] = None

    async def connect(self):
        """Initialize Cosmos DB database and containers."""
        logger.info("connecting_to_cosmos_db", endpoint=self.cosmos_endpoint)

        # Create database if not exists
        self.database = await self.client.create_database_if_not_exists(
            id=self.database_name
        )

        # Create containers with partition keys
        self.agents_container = await self.database.create_container_if_not_exists(
            id="agents",
            partition_key=PartitionKey(path="/partition_key"),
            default_ttl=None  # No auto-expiration for agents
        )

        self.tasks_container = await self.database.create_container_if_not_exists(
            id="tasks",
            partition_key=PartitionKey(path="/partition_key"),
            default_ttl=86400 * 7  # 7 days retention
        )

        self.pheromones_container = await self.database.create_container_if_not_exists(
            id="pheromones",
            partition_key=PartitionKey(path="/partition_key"),
            default_ttl=86400  # 24 hours retention (longer than Event Hub)
        )

        self.metrics_container = await self.database.create_container_if_not_exists(
            id="metrics",
            partition_key=PartitionKey(path="/partition_key"),
            default_ttl=86400 * 30  # 30 days retention
        )

        logger.info("cosmos_db_connected", database=self.database_name)

    # Agent State Management

    async def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        tenant_id: str,
        capabilities: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Register a new agent or update existing."""
        now = datetime.utcnow().isoformat()

        agent_state = AgentState(
            id=agent_id,
            agent_id=agent_id,
            agent_type=agent_type,
            tenant_id=tenant_id,
            status=AgentStatus.ACTIVE.value,
            capabilities=capabilities,
            current_load=0.0,
            current_task_id=None,
            last_heartbeat=now,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            partition_key=tenant_id
        )

        await self.agents_container.upsert_item(body=asdict(agent_state))

        logger.info("agent_registered", agent_id=agent_id, tenant_id=tenant_id)

    async def update_agent_status(
        self,
        agent_id: str,
        tenant_id: str,
        status: AgentStatus,
        current_load: Optional[float] = None,
        current_task_id: Optional[str] = None
    ):
        """Update agent status and health."""
        try:
            # Read current state
            agent_dict = await self.agents_container.read_item(
                item=agent_id,
                partition_key=tenant_id
            )

            # Update fields
            agent_dict["status"] = status.value
            agent_dict["last_heartbeat"] = datetime.utcnow().isoformat()
            agent_dict["updated_at"] = datetime.utcnow().isoformat()

            if current_load is not None:
                agent_dict["current_load"] = current_load

            if current_task_id is not None:
                agent_dict["current_task_id"] = current_task_id

            # Write back
            await self.agents_container.upsert_item(body=agent_dict)

        except exceptions.CosmosResourceNotFoundError:
            logger.warning("agent_not_found", agent_id=agent_id)

    async def get_agent_state(
        self,
        agent_id: str,
        tenant_id: str
    ) -> Optional[AgentState]:
        """Get current state of an agent."""
        try:
            agent_dict = await self.agents_container.read_item(
                item=agent_id,
                partition_key=tenant_id
            )

            return AgentState(**agent_dict)

        except exceptions.CosmosResourceNotFoundError:
            return None

    async def list_agents(
        self,
        tenant_id: str,
        status: Optional[AgentStatus] = None,
        agent_type: Optional[str] = None
    ) -> List[AgentState]:
        """List agents with optional filtering."""
        query = "SELECT * FROM c WHERE c.tenant_id = @tenant_id"
        parameters = [{"name": "@tenant_id", "value": tenant_id}]

        if status:
            query += " AND c.status = @status"
            parameters.append({"name": "@status", "value": status.value})

        if agent_type:
            query += " AND c.agent_type = @agent_type"
            parameters.append({"name": "@agent_type", "value": agent_type})

        items = self.agents_container.query_items(
            query=query,
            parameters=parameters,
            partition_key=tenant_id
        )

        agents = []
        async for item in items:
            agents.append(AgentState(**item))

        return agents

    # Task State Management

    async def create_task(
        self,
        task_id: str,
        task_type: str,
        tenant_id: str,
        priority: int,
        required_capabilities: List[str],
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Create a new task."""
        now = datetime.utcnow().isoformat()

        task_state = TaskState(
            id=task_id,
            task_id=task_id,
            task_type=task_type,
            tenant_id=tenant_id,
            status=TaskStatus.PENDING.value,
            priority=priority,
            required_capabilities=required_capabilities,
            payload=payload,
            claimed_by=None,
            claimed_at=None,
            started_at=None,
            completed_at=None,
            result=None,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            partition_key=tenant_id
        )

        await self.tasks_container.create_item(body=asdict(task_state))

        logger.info("task_created", task_id=task_id, priority=priority)

    async def claim_task(
        self,
        task_id: str,
        tenant_id: str,
        agent_id: str
    ) -> bool:
        """Agent claims a task (optimistic concurrency)."""
        try:
            # Read current state
            task_dict = await self.tasks_container.read_item(
                item=task_id,
                partition_key=tenant_id
            )

            # Check if already claimed
            if task_dict["claimed_by"]:
                return False

            # Claim task
            task_dict["status"] = TaskStatus.CLAIMED.value
            task_dict["claimed_by"] = agent_id
            task_dict["claimed_at"] = datetime.utcnow().isoformat()
            task_dict["updated_at"] = datetime.utcnow().isoformat()

            # Write back (will fail if modified concurrently)
            await self.tasks_container.replace_item(
                item=task_id,
                body=task_dict,
                etag=task_dict["_etag"],
                match_condition=exceptions.MatchConditions.IfNotModified
            )

            logger.info("task_claimed", task_id=task_id, agent_id=agent_id)
            return True

        except exceptions.CosmosAccessConditionFailedError:
            # Task was claimed by another agent
            logger.info("task_claim_conflict", task_id=task_id)
            return False

        except exceptions.CosmosResourceNotFoundError:
            logger.warning("task_not_found", task_id=task_id)
            return False

    async def complete_task(
        self,
        task_id: str,
        tenant_id: str,
        success: bool,
        result: Optional[Dict[str, Any]] = None
    ):
        """Mark task as completed or failed."""
        try:
            task_dict = await self.tasks_container.read_item(
                item=task_id,
                partition_key=tenant_id
            )

            task_dict["status"] = TaskStatus.COMPLETED.value if success else TaskStatus.FAILED.value
            task_dict["completed_at"] = datetime.utcnow().isoformat()
            task_dict["result"] = result
            task_dict["updated_at"] = datetime.utcnow().isoformat()

            await self.tasks_container.upsert_item(body=task_dict)

            logger.info("task_completed", task_id=task_id, success=success)

        except exceptions.CosmosResourceNotFoundError:
            logger.warning("task_not_found", task_id=task_id)

    async def get_task_state(
        self,
        task_id: str,
        tenant_id: str
    ) -> Optional[TaskState]:
        """Get current state of a task."""
        try:
            task_dict = await self.tasks_container.read_item(
                item=task_id,
                partition_key=tenant_id
            )

            return TaskState(**task_dict)

        except exceptions.CosmosResourceNotFoundError:
            return None

    # Pheromone Persistence

    async def persist_pheromone(
        self,
        trail_id: str,
        pheromone_type: str,
        deposited_by: str,
        strength: float,
        deposited_at: datetime,
        expires_at: datetime,
        location: Optional[str],
        data: Dict[str, Any],
        tenant_id: str
    ):
        """Persist pheromone trail beyond Event Hub retention."""
        pheromone = PheromoneRecord(
            id=trail_id,
            trail_id=trail_id,
            pheromone_type=pheromone_type,
            deposited_by=deposited_by,
            strength=strength,
            deposited_at=deposited_at.isoformat(),
            expires_at=expires_at.isoformat(),
            location=location,
            data=data,
            tenant_id=tenant_id,
            partition_key=f"{tenant_id}_{location}" if location else tenant_id
        )

        await self.pheromones_container.create_item(body=asdict(pheromone))

    # Metrics & Analytics

    async def record_metrics(
        self,
        tenant_id: str,
        metrics: SwarmMetrics
    ):
        """Record swarm metrics snapshot."""
        await self.metrics_container.create_item(body=asdict(metrics))

        logger.debug("metrics_recorded", tenant_id=tenant_id)

    async def get_metrics_history(
        self,
        tenant_id: str,
        hours: int = 24
    ) -> List[SwarmMetrics]:
        """Get historical metrics."""
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()

        query = "SELECT * FROM c WHERE c.tenant_id = @tenant_id AND c.timestamp >= @cutoff ORDER BY c.timestamp DESC"
        parameters = [
            {"name": "@tenant_id", "value": tenant_id},
            {"name": "@cutoff", "value": cutoff}
        ]

        items = self.metrics_container.query_items(
            query=query,
            parameters=parameters,
            partition_key=tenant_id
        )

        metrics_list = []
        async for item in items:
            metrics_list.append(SwarmMetrics(**item))

        return metrics_list

    async def get_swarm_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get current swarm state summary."""
        # Count agents by status
        active_agents = await self.list_agents(tenant_id, status=AgentStatus.ACTIVE)
        sleeping_agents = await self.list_agents(tenant_id, status=AgentStatus.SLEEPING)

        # Count tasks by status
        pending_query = "SELECT VALUE COUNT(1) FROM c WHERE c.tenant_id = @tenant_id AND c.status = @status"

        pending_items = self.tasks_container.query_items(
            query=pending_query,
            parameters=[
                {"name": "@tenant_id", "value": tenant_id},
                {"name": "@status", "value": TaskStatus.PENDING.value}
            ],
            partition_key=tenant_id
        )
        pending_count = 0
        async for count in pending_items:
            pending_count = count

        return {
            "tenant_id": tenant_id,
            "active_agents": len(active_agents),
            "sleeping_agents": len(sleeping_agents),
            "pending_tasks": pending_count,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def close(self):
        """Close Cosmos DB connection."""
        if self.client:
            await self.client.close()

        if self.credential:
            await self.credential.close()

        logger.info("cosmos_db_connection_closed")


# Factory function
def create_swarm_state_manager(
    cosmos_endpoint: str,
    database_name: str = "ants_swarm",
    use_managed_identity: bool = True
) -> SwarmStateManager:
    """Create a SwarmStateManager instance."""
    return SwarmStateManager(
        cosmos_endpoint=cosmos_endpoint,
        database_name=database_name,
        use_managed_identity=use_managed_identity
    )
