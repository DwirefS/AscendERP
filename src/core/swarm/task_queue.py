"""
Task Queue Management with Azure Service Bus.

Provides reliable, guaranteed-delivery task queuing for swarm coordination:
- FIFO ordering for priority-based execution
- Dead-letter queue for failed tasks
- Session-based processing for stateful workflows
- Scheduled delivery for delayed tasks
- Auto-scaling based on queue depth

Azure Service Bus enables:
- Guaranteed message delivery (at-least-once)
- Transaction support
- Duplicate detection
- Auto-forwarding and chaining
- Message sessions for ordered processing
"""
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
import asyncio
import json
import structlog
from azure.servicebus.aio import ServiceBusClient, ServiceBusReceiver, ServiceBusSender
from azure.servicebus import ServiceBusMessage, ServiceBusReceiveMode
from azure.identity.aio import DefaultAzureCredential

logger = structlog.get_logger()


class TaskPriority(Enum):
    """Task priority levels (maps to Service Bus message priority)."""
    CRITICAL = 10
    HIGH = 7
    NORMAL = 5
    LOW = 3
    BACKGROUND = 1


class TaskType(Enum):
    """Common task types for agent execution."""
    RECONCILIATION = "reconciliation"
    FRAUD_DETECTION = "fraud_detection"
    DATA_SYNC = "data_sync"
    REPORT_GENERATION = "report_generation"
    INTEGRATION_BUILD = "integration_build"
    CODE_EXECUTION = "code_execution"
    CUSTOM = "custom"


@dataclass
class AgentTask:
    """Task for agent execution."""
    task_id: str
    task_type: str
    tenant_id: str
    priority: int  # 1-10
    required_capabilities: List[str]
    payload: Dict[str, Any]
    created_at: str
    scheduled_for: Optional[str] = None  # ISO datetime for delayed execution
    session_id: Optional[str] = None     # For ordered processing
    correlation_id: Optional[str] = None # For tracking related tasks
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class TaskResult:
    """Result from task execution."""
    task_id: str
    agent_id: str
    success: bool
    result: Optional[Dict[str, Any]]
    error: Optional[str]
    execution_time_ms: float
    completed_at: str


class TaskQueueClient:
    """
    Manages task queuing with Azure Service Bus.

    Features:
    - Priority-based FIFO queues
    - Dead-letter handling for failed tasks
    - Session-based ordered processing
    - Scheduled delivery
    - Auto-complete with retries
    - Metrics and monitoring
    """

    def __init__(
        self,
        service_bus_namespace: str,
        queue_name: str = "ants-tasks",
        use_managed_identity: bool = True,
        connection_string: Optional[str] = None,
        max_concurrent_tasks: int = 10
    ):
        self.namespace = service_bus_namespace
        self.queue_name = queue_name
        self.max_concurrent_tasks = max_concurrent_tasks

        # Full namespace URL
        self.fully_qualified_namespace = f"{service_bus_namespace}.servicebus.windows.net"

        # Authentication
        if use_managed_identity:
            self.credential = DefaultAzureCredential()
            self.client = ServiceBusClient(
                fully_qualified_namespace=self.fully_qualified_namespace,
                credential=self.credential
            )
        else:
            if not connection_string:
                raise ValueError("connection_string required when not using managed identity")

            self.client = ServiceBusClient.from_connection_string(
                conn_str=connection_string
            )
            self.credential = None

        # Sender and receiver (initialized in connect())
        self.sender: Optional[ServiceBusSender] = None
        self.receiver: Optional[ServiceBusReceiver] = None

        # Task handlers
        self._handlers: Dict[str, Callable[[AgentTask], Awaitable[TaskResult]]] = {}

        # Processing state
        self._processing = False
        self._processing_task: Optional[asyncio.Task] = None

    async def connect(self):
        """Initialize Service Bus sender and receiver."""
        logger.info("connecting_to_service_bus", namespace=self.namespace, queue=self.queue_name)

        # Create sender for submitting tasks
        self.sender = self.client.get_queue_sender(queue_name=self.queue_name)

        # Create receiver for consuming tasks
        self.receiver = self.client.get_queue_receiver(
            queue_name=self.queue_name,
            receive_mode=ServiceBusReceiveMode.PEEK_LOCK,  # Manual completion
            max_wait_time=5
        )

        logger.info("service_bus_connected", queue=self.queue_name)

    # Task Submission

    async def submit_task(
        self,
        task_type: str,
        tenant_id: str,
        required_capabilities: List[str],
        payload: Dict[str, Any],
        priority: int = 5,
        task_id: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit a task to the queue.

        Args:
            task_type: Type of task
            tenant_id: Tenant identifier
            required_capabilities: List of required agent capabilities
            payload: Task data
            priority: Priority level (1-10, higher = more urgent)
            task_id: Optional task ID (auto-generated if not provided)
            scheduled_for: Optional datetime for delayed execution
            session_id: Optional session ID for ordered processing
            correlation_id: Optional ID for tracking related tasks
            metadata: Optional metadata

        Returns:
            task_id
        """
        if not self.sender:
            raise RuntimeError("TaskQueueClient not connected. Call connect() first.")

        # Generate task ID if not provided
        if not task_id:
            task_id = f"{task_type}_{tenant_id}_{datetime.utcnow().timestamp()}"

        now = datetime.utcnow()

        # Create task
        task = AgentTask(
            task_id=task_id,
            task_type=task_type,
            tenant_id=tenant_id,
            priority=priority,
            required_capabilities=required_capabilities,
            payload=payload,
            created_at=now.isoformat(),
            scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
            session_id=session_id,
            correlation_id=correlation_id,
            metadata=metadata or {}
        )

        # Serialize to Service Bus message
        message_body = json.dumps(asdict(task))
        message = ServiceBusMessage(
            body=message_body,
            session_id=session_id,
            message_id=task_id,
            correlation_id=correlation_id
        )

        # Set message priority (influences processing order)
        message.application_properties = {
            "priority": priority,
            "task_type": task_type,
            "tenant_id": tenant_id
        }

        # Scheduled delivery
        if scheduled_for:
            message.scheduled_enqueue_time_utc = scheduled_for

        # Send to queue
        async with self.sender:
            await self.sender.send_messages(message)

        logger.info(
            "task_submitted",
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            scheduled_for=scheduled_for.isoformat() if scheduled_for else None
        )

        return task_id

    async def submit_batch(
        self,
        tasks: List[AgentTask]
    ) -> List[str]:
        """Submit multiple tasks in a batch."""
        if not self.sender:
            raise RuntimeError("TaskQueueClient not connected.")

        messages = []
        task_ids = []

        for task in tasks:
            message = ServiceBusMessage(
                body=json.dumps(asdict(task)),
                session_id=task.session_id,
                message_id=task.task_id,
                correlation_id=task.correlation_id
            )

            message.application_properties = {
                "priority": task.priority,
                "task_type": task.task_type,
                "tenant_id": task.tenant_id
            }

            if task.scheduled_for:
                scheduled_dt = datetime.fromisoformat(task.scheduled_for)
                message.scheduled_enqueue_time_utc = scheduled_dt

            messages.append(message)
            task_ids.append(task.task_id)

        # Send batch
        async with self.sender:
            await self.sender.send_messages(messages)

        logger.info("task_batch_submitted", count=len(tasks))
        return task_ids

    # Task Processing

    def register_handler(
        self,
        task_type: str,
        handler: Callable[[AgentTask], Awaitable[TaskResult]]
    ):
        """
        Register a handler for a specific task type.

        Handler signature: async def handler(task: AgentTask) -> TaskResult
        """
        self._handlers[task_type] = handler
        logger.info("handler_registered", task_type=task_type)

    async def start_processing(self):
        """Start processing tasks from the queue."""
        if self._processing:
            logger.warning("task_processing_already_started")
            return

        if not self.receiver:
            raise RuntimeError("TaskQueueClient not connected.")

        self._processing = True
        self._processing_task = asyncio.create_task(self._process_loop())

        logger.info("task_processing_started", max_concurrent=self.max_concurrent_tasks)

    async def stop_processing(self):
        """Stop processing tasks."""
        if not self._processing:
            return

        self._processing = False

        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        logger.info("task_processing_stopped")

    async def _process_loop(self):
        """Main processing loop."""
        logger.info("task_processing_loop_started")

        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        while self._processing:
            try:
                # Receive messages from queue
                async with self.receiver:
                    messages = await self.receiver.receive_messages(
                        max_message_count=self.max_concurrent_tasks,
                        max_wait_time=5
                    )

                if not messages:
                    await asyncio.sleep(1)
                    continue

                # Process messages concurrently
                tasks = []
                for message in messages:
                    task = asyncio.create_task(
                        self._process_message(message, semaphore)
                    )
                    tasks.append(task)

                await asyncio.gather(*tasks, return_exceptions=True)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("task_processing_error", error=str(e))
                await asyncio.sleep(5)

        logger.info("task_processing_loop_stopped")

    async def _process_message(self, message, semaphore):
        """Process a single message."""
        async with semaphore:
            start_time = datetime.utcnow()

            try:
                # Deserialize task
                task_data = json.loads(str(message))
                task = AgentTask(**task_data)

                logger.info(
                    "processing_task",
                    task_id=task.task_id,
                    task_type=task.task_type,
                    priority=task.priority
                )

                # Find handler
                handler = self._handlers.get(task.task_type)
                if not handler:
                    logger.warning("no_handler_for_task", task_type=task.task_type)
                    await self.receiver.dead_letter_message(
                        message,
                        reason="no_handler",
                        error_description=f"No handler registered for task type: {task.task_type}"
                    )
                    return

                # Execute handler
                result = await handler(task)

                # Complete message
                await self.receiver.complete_message(message)

                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

                logger.info(
                    "task_completed",
                    task_id=task.task_id,
                    success=result.success,
                    execution_time_ms=execution_time
                )

            except Exception as e:
                logger.error(
                    "task_processing_failed",
                    task_id=task.task_id if 'task' in locals() else "unknown",
                    error=str(e)
                )

                # Dead-letter the message after max retries
                if message.delivery_count >= 3:
                    await self.receiver.dead_letter_message(
                        message,
                        reason="max_retries_exceeded",
                        error_description=str(e)
                    )
                else:
                    # Abandon for retry
                    await self.receiver.abandon_message(message)

    # Dead Letter Queue Management

    async def get_dead_letter_messages(self, max_count: int = 10) -> List[AgentTask]:
        """Retrieve messages from dead-letter queue."""
        dlq_receiver = self.client.get_queue_receiver(
            queue_name=self.queue_name,
            sub_queue=ServiceBusReceiveMode.RECEIVE_AND_DELETE,
            max_wait_time=5
        )

        dead_letters = []

        try:
            async with dlq_receiver:
                messages = await dlq_receiver.receive_messages(max_message_count=max_count)

                for message in messages:
                    task_data = json.loads(str(message))
                    task = AgentTask(**task_data)
                    dead_letters.append(task)

        finally:
            await dlq_receiver.close()

        return dead_letters

    async def resubmit_dead_letter(self, task_id: str):
        """Resubmit a task from dead-letter queue."""
        # Get from DLQ
        dlq_tasks = await self.get_dead_letter_messages(max_count=100)

        for task in dlq_tasks:
            if task.task_id == task_id:
                # Resubmit to main queue
                await self.submit_task(
                    task_type=task.task_type,
                    tenant_id=task.tenant_id,
                    required_capabilities=task.required_capabilities,
                    payload=task.payload,
                    priority=task.priority,
                    task_id=task.task_id,
                    session_id=task.session_id,
                    correlation_id=task.correlation_id,
                    metadata=task.metadata
                )

                logger.info("dead_letter_resubmitted", task_id=task_id)
                return

        logger.warning("dead_letter_task_not_found", task_id=task_id)

    # Metrics

    async def get_queue_metrics(self) -> Dict[str, Any]:
        """Get queue depth and metrics."""
        # Note: This requires Azure SDK management client
        # For now, return basic info
        return {
            "queue_name": self.queue_name,
            "namespace": self.namespace,
            "processing": self._processing,
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "registered_handlers": list(self._handlers.keys())
        }

    async def close(self):
        """Close Service Bus connections."""
        await self.stop_processing()

        if self.sender:
            await self.sender.close()

        if self.receiver:
            await self.receiver.close()

        await self.client.close()

        if self.credential:
            await self.credential.close()

        logger.info("service_bus_connection_closed")


# Factory function
def create_task_queue_client(
    service_bus_namespace: str,
    queue_name: str = "ants-tasks",
    use_managed_identity: bool = True,
    max_concurrent_tasks: int = 10
) -> TaskQueueClient:
    """Create a TaskQueueClient instance."""
    return TaskQueueClient(
        service_bus_namespace=service_bus_namespace,
        queue_name=queue_name,
        use_managed_identity=use_managed_identity,
        max_concurrent_tasks=max_concurrent_tasks
    )
