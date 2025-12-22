"""
Pheromone Client - Azure Event Hub Integration for Swarm Coordination.

This client implements the pheromone-based communication system inspired by
ant colonies. Agents deposit and detect pheromone trails through Azure Event Hub
to coordinate work, share discoveries, and optimize resource allocation.

Pheromone Types:
- Task pheromones: Signal work availability and urgency
- Resource pheromones: Indicate resource discovery and allocation
- Danger pheromones: Alert to errors, threats, or blocked paths
- Success pheromones: Reinforce successful patterns and workflows
- Capability pheromones: Signal integration needs and tool availability
"""
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import structlog
from azure.eventhub.aio import EventHubProducerClient, EventHubConsumerClient
from azure.eventhub import EventData
from azure.identity.aio import DefaultAzureCredential

logger = structlog.get_logger()


class PheromoneType(Enum):
    """Types of pheromone signals in the swarm."""
    TASK = "task"                      # Work availability and urgency
    RESOURCE = "resource"              # Resource discovery and allocation
    DANGER = "danger"                  # Errors, threats, blocked paths
    SUCCESS = "success"                # Successful patterns and workflows
    CAPABILITY = "capability"          # Integration needs and tool availability
    LOAD_BALANCING = "load_balancing"  # Agent capacity and utilization
    COORDINATION = "coordination"      # Multi-agent collaboration signals


class PheromoneStrength(Enum):
    """Strength/intensity of pheromone signal."""
    TRACE = 0.1      # Weak signal, fades quickly
    LOW = 0.3        # Low intensity
    MEDIUM = 0.5     # Standard intensity
    HIGH = 0.7       # Strong signal
    CRITICAL = 1.0   # Maximum intensity, urgent


@dataclass
class PheromoneTrail:
    """A pheromone trail deposited by an agent."""
    trail_id: str
    pheromone_type: PheromoneType
    deposited_by: str  # Agent ID
    strength: float  # 0.0 to 1.0
    deposited_at: datetime
    expires_at: datetime
    data: Dict[str, Any]
    location: Optional[str] = None  # Logical location (e.g., "finance.reconciliation")
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if pheromone has evaporated."""
        return datetime.utcnow() >= self.expires_at

    def current_strength(self) -> float:
        """Calculate current strength with evaporation."""
        if self.is_expired():
            return 0.0

        # Linear evaporation over time
        total_duration = (self.expires_at - self.deposited_at).total_seconds()
        elapsed = (datetime.utcnow() - self.deposited_at).total_seconds()

        if total_duration <= 0:
            return 0.0

        evaporation_factor = 1.0 - (elapsed / total_duration)
        return self.strength * evaporation_factor


@dataclass
class PheromoneDetection:
    """Detection of pheromone trails by an agent."""
    trails: List[PheromoneTrail]
    detected_at: datetime
    total_strength: float
    dominant_type: Optional[PheromoneType]


class PheromoneClient:
    """
    Client for pheromone-based swarm coordination using Azure Event Hub.

    Azure Event Hub provides:
    - High-throughput message ingestion (millions of events/second)
    - Partitioned event streaming for parallel processing
    - Event replay capability (pheromone trail history)
    - Built-in retention (pheromone persistence)
    - Integration with Azure ecosystem

    Usage:
    - Agents deposit pheromones when discovering work, resources, or patterns
    - Agents detect pheromones to find high-value tasks and avoid dangers
    - Pheromone strength guides agent decisions (higher = more agents attracted)
    - Evaporation ensures trails fade over time (solved tasks, stale info)
    """

    def __init__(
        self,
        event_hub_namespace: str,
        event_hub_name: str,
        consumer_group: str = "$Default",
        use_managed_identity: bool = True,
        connection_string: Optional[str] = None
    ):
        self.event_hub_namespace = event_hub_namespace
        self.event_hub_name = event_hub_name
        self.consumer_group = consumer_group

        # Authentication
        if use_managed_identity:
            self.credential = DefaultAzureCredential()
            fully_qualified_namespace = f"{event_hub_namespace}.servicebus.windows.net"
            self.producer = EventHubProducerClient(
                fully_qualified_namespace=fully_qualified_namespace,
                eventhub_name=event_hub_name,
                credential=self.credential
            )
            self.consumer = EventHubConsumerClient(
                fully_qualified_namespace=fully_qualified_namespace,
                eventhub_name=event_hub_name,
                consumer_group=consumer_group,
                credential=self.credential
            )
        else:
            if not connection_string:
                raise ValueError("connection_string required when not using managed identity")

            self.credential = None
            self.producer = EventHubProducerClient.from_connection_string(
                conn_str=connection_string,
                eventhub_name=event_hub_name
            )
            self.consumer = EventHubConsumerClient.from_connection_string(
                conn_str=connection_string,
                eventhub_name=event_hub_name,
                consumer_group=consumer_group
            )

        # Local pheromone cache for quick detection
        self._pheromone_cache: Dict[str, PheromoneTrail] = {}
        self._cache_lock = asyncio.Lock()

        # Detection handlers
        self._detection_handlers: Dict[PheromoneType, List[Callable]] = {
            ptype: [] for ptype in PheromoneType
        }

        # Consumer task
        self._consumer_task: Optional[asyncio.Task] = None
        self._running = False

    async def connect(self):
        """Initialize connection to Event Hub."""
        logger.info(
            "connecting_to_event_hub",
            namespace=self.event_hub_namespace,
            event_hub=self.event_hub_name
        )

        # Test producer connection
        async with self.producer:
            pass

        logger.info("event_hub_connected")

    async def start_detection(self):
        """Start listening for pheromone trails."""
        if self._running:
            logger.warning("pheromone_detection_already_running")
            return

        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_pheromones())

        logger.info("pheromone_detection_started")

    async def stop_detection(self):
        """Stop listening for pheromone trails."""
        self._running = False

        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        logger.info("pheromone_detection_stopped")

    async def deposit_pheromone(
        self,
        pheromone_type: PheromoneType,
        deposited_by: str,
        data: Dict[str, Any],
        strength: PheromoneStrength = PheromoneStrength.MEDIUM,
        ttl_seconds: int = 300,  # 5 minutes default
        location: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Deposit a pheromone trail.

        Args:
            pheromone_type: Type of pheromone signal
            deposited_by: Agent ID depositing the pheromone
            data: Pheromone payload (task info, resource details, etc.)
            strength: Initial signal strength
            ttl_seconds: Time to live before evaporation (default 5 minutes)
            location: Logical location for spatial clustering
            metadata: Additional metadata

        Returns:
            trail_id: Unique identifier for this pheromone trail
        """
        now = datetime.utcnow()
        trail_id = f"{pheromone_type.value}_{deposited_by}_{now.timestamp()}"

        trail = PheromoneTrail(
            trail_id=trail_id,
            pheromone_type=pheromone_type,
            deposited_by=deposited_by,
            strength=strength.value,
            deposited_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            data=data,
            location=location,
            metadata=metadata or {}
        )

        # Serialize to Event Hub
        event_data = EventData(json.dumps({
            "trail_id": trail.trail_id,
            "pheromone_type": trail.pheromone_type.value,
            "deposited_by": trail.deposited_by,
            "strength": trail.strength,
            "deposited_at": trail.deposited_at.isoformat(),
            "expires_at": trail.expires_at.isoformat(),
            "data": trail.data,
            "location": trail.location,
            "metadata": trail.metadata
        }))

        # Set partition key for spatial clustering (same location -> same partition)
        if location:
            event_data = EventData(event_data.body_as_str(), partition_key=location)

        # Send to Event Hub
        async with self.producer:
            await self.producer.send_batch([event_data])

        # Update local cache
        async with self._cache_lock:
            self._pheromone_cache[trail_id] = trail

        logger.info(
            "pheromone_deposited",
            trail_id=trail_id,
            type=pheromone_type.value,
            strength=strength.value,
            deposited_by=deposited_by,
            ttl=ttl_seconds
        )

        return trail_id

    async def detect_pheromones(
        self,
        pheromone_types: Optional[List[PheromoneType]] = None,
        location: Optional[str] = None,
        min_strength: float = 0.1,
        max_age_seconds: Optional[int] = None
    ) -> PheromoneDetection:
        """
        Detect pheromone trails in the environment.

        Args:
            pheromone_types: Filter by types (None = all types)
            location: Filter by location
            min_strength: Minimum current strength to detect
            max_age_seconds: Maximum age in seconds

        Returns:
            PheromoneDetection with matching trails
        """
        now = datetime.utcnow()
        matching_trails = []

        async with self._cache_lock:
            for trail in self._pheromone_cache.values():
                # Check expiration
                if trail.is_expired():
                    continue

                # Filter by type
                if pheromone_types and trail.pheromone_type not in pheromone_types:
                    continue

                # Filter by location
                if location and trail.location != location:
                    continue

                # Calculate current strength with evaporation
                current_strength = trail.current_strength()

                # Check minimum strength
                if current_strength < min_strength:
                    continue

                # Check age
                if max_age_seconds:
                    age = (now - trail.deposited_at).total_seconds()
                    if age > max_age_seconds:
                        continue

                matching_trails.append(trail)

        # Sort by current strength (strongest first)
        matching_trails.sort(key=lambda t: t.current_strength(), reverse=True)

        # Calculate metrics
        total_strength = sum(t.current_strength() for t in matching_trails)

        # Find dominant type
        dominant_type = None
        if matching_trails:
            type_strengths = {}
            for trail in matching_trails:
                ptype = trail.pheromone_type
                current = trail.current_strength()
                type_strengths[ptype] = type_strengths.get(ptype, 0) + current

            dominant_type = max(type_strengths.items(), key=lambda x: x[1])[0]

        detection = PheromoneDetection(
            trails=matching_trails,
            detected_at=now,
            total_strength=total_strength,
            dominant_type=dominant_type
        )

        logger.info(
            "pheromones_detected",
            trail_count=len(matching_trails),
            total_strength=total_strength,
            dominant_type=dominant_type.value if dominant_type else None
        )

        return detection

    def register_handler(
        self,
        pheromone_type: PheromoneType,
        handler: Callable[[PheromoneTrail], Awaitable[None]]
    ):
        """
        Register a handler for specific pheromone type.

        Handler will be called whenever a pheromone of this type is detected.
        """
        self._detection_handlers[pheromone_type].append(handler)

        logger.info(
            "pheromone_handler_registered",
            pheromone_type=pheromone_type.value
        )

    async def _consume_pheromones(self):
        """Background task to consume pheromone events from Event Hub."""
        logger.info("starting_pheromone_consumer")

        async with self.consumer:
            async def on_event(partition_context, event):
                """Process incoming pheromone event."""
                try:
                    # Parse event data
                    event_body = event.body_as_str()
                    data = json.loads(event_body)

                    # Reconstruct pheromone trail
                    trail = PheromoneTrail(
                        trail_id=data["trail_id"],
                        pheromone_type=PheromoneType(data["pheromone_type"]),
                        deposited_by=data["deposited_by"],
                        strength=data["strength"],
                        deposited_at=datetime.fromisoformat(data["deposited_at"]),
                        expires_at=datetime.fromisoformat(data["expires_at"]),
                        data=data["data"],
                        location=data.get("location"),
                        metadata=data.get("metadata", {})
                    )

                    # Update cache
                    async with self._cache_lock:
                        self._pheromone_cache[trail.trail_id] = trail

                    # Invoke handlers
                    handlers = self._detection_handlers.get(trail.pheromone_type, [])
                    for handler in handlers:
                        try:
                            await handler(trail)
                        except Exception as e:
                            logger.error(
                                "pheromone_handler_failed",
                                error=str(e),
                                handler=handler.__name__
                            )

                    # Update checkpoint
                    await partition_context.update_checkpoint(event)

                except Exception as e:
                    logger.error("pheromone_event_processing_failed", error=str(e))

            async def on_error(partition_context, error):
                """Handle consumer errors."""
                logger.error(
                    "pheromone_consumer_error",
                    partition_id=partition_context.partition_id,
                    error=str(error)
                )

            # Start receiving events
            await self.consumer.receive(
                on_event=on_event,
                on_error=on_error,
                starting_position="-1"  # Start from beginning
            )

    async def cleanup_expired(self):
        """Remove expired pheromones from cache."""
        async with self._cache_lock:
            expired_ids = [
                trail_id for trail_id, trail in self._pheromone_cache.items()
                if trail.is_expired()
            ]

            for trail_id in expired_ids:
                del self._pheromone_cache[trail_id]

            if expired_ids:
                logger.info("cleaned_expired_pheromones", count=len(expired_ids))

    async def get_swarm_metrics(self) -> Dict[str, Any]:
        """Get metrics about current pheromone landscape."""
        async with self._cache_lock:
            active_trails = [
                trail for trail in self._pheromone_cache.values()
                if not trail.is_expired()
            ]

            # Metrics by type
            type_counts = {}
            type_strengths = {}
            for trail in active_trails:
                ptype = trail.pheromone_type.value
                type_counts[ptype] = type_counts.get(ptype, 0) + 1
                current_strength = trail.current_strength()
                type_strengths[ptype] = type_strengths.get(ptype, 0) + current_strength

            # Metrics by location
            location_counts = {}
            for trail in active_trails:
                if trail.location:
                    location_counts[trail.location] = location_counts.get(trail.location, 0) + 1

            return {
                "total_active_trails": len(active_trails),
                "total_cached_trails": len(self._pheromone_cache),
                "trails_by_type": type_counts,
                "strength_by_type": type_strengths,
                "trails_by_location": location_counts,
                "oldest_trail_age_seconds": (
                    (datetime.utcnow() - min(t.deposited_at for t in active_trails)).total_seconds()
                    if active_trails else 0
                )
            }

    async def close(self):
        """Close Event Hub connections."""
        await self.stop_detection()

        if self.producer:
            await self.producer.close()

        if self.consumer:
            await self.consumer.close()

        if self.credential:
            await self.credential.close()

        logger.info("pheromone_client_closed")


# Factory function
def create_pheromone_client(
    event_hub_namespace: str,
    event_hub_name: str = "ants-pheromones",
    consumer_group: str = "$Default",
    use_managed_identity: bool = True
) -> PheromoneClient:
    """Create a PheromoneClient instance."""
    return PheromoneClient(
        event_hub_namespace=event_hub_namespace,
        event_hub_name=event_hub_name,
        consumer_group=consumer_group,
        use_managed_identity=use_managed_identity
    )
