"""
Example: Reliable Task Queuing with Azure Service Bus.

Demonstrates how agents use Service Bus for:
- Guaranteed task delivery (at-least-once)
- Priority-based FIFO processing
- Dead-letter queue handling
- Retry logic with exponential backoff
- Integration with pheromone swarm coordination
"""
import asyncio
from datetime import datetime, timedelta

from src.core.swarm import (
    create_task_queue_client,
    create_pheromone_client,
    create_pheromone_orchestrator,
    TaskPriority,
    TaskType,
    AgentTask,
    TaskResult,
    PheromoneType,
    PheromoneStrength
)
from src.core.agent.base import BaseAgent, AgentConfig, ExecutionContext
from src.core.memory.substrate import MemorySubstrate
from src.core.memory.database import DatabaseClient
from src.core.inference.llm_client import LLMClient


class TaskProcessingAgent(BaseAgent):
    """Example agent that processes tasks from Service Bus queue."""

    def __init__(
        self,
        config: AgentConfig,
        memory: MemorySubstrate,
        llm_client: LLMClient,
        task_queue: 'TaskQueueClient'
    ):
        super().__init__(config, memory, llm_client)
        self.task_queue = task_queue

    async def start(self):
        """Start processing tasks from queue."""
        # Register handlers for different task types
        self.task_queue.register_handler(
            task_type=TaskType.RECONCILIATION.value,
            handler=self._handle_reconciliation
        )

        self.task_queue.register_handler(
            task_type=TaskType.FRAUD_DETECTION.value,
            handler=self._handle_fraud_detection
        )

        self.task_queue.register_handler(
            task_type=TaskType.INTEGRATION_BUILD.value,
            handler=self._handle_integration_build
        )

        # Start processing
        await self.task_queue.start_processing()

        print(f"[{self.config.agent_id}] Started processing tasks from queue")

    async def _handle_reconciliation(self, task: AgentTask) -> TaskResult:
        """Handle reconciliation task."""
        start_time = datetime.utcnow()

        try:
            print(f"[{self.config.agent_id}] Processing reconciliation: {task.task_id}")

            # Simulate work
            account = task.payload.get("account")
            date_range = task.payload.get("date_range")

            print(f"   Account: {account}")
            print(f"   Date range: {date_range}")

            # Simulate processing time
            await asyncio.sleep(2)

            # Success result
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.config.agent_id,
                success=True,
                result={
                    "account": account,
                    "discrepancies": 0,
                    "amount_reconciled": "$125,430.50"
                },
                error=None,
                execution_time_ms=execution_time,
                completed_at=datetime.utcnow().isoformat()
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.config.agent_id,
                success=False,
                result=None,
                error=str(e),
                execution_time_ms=execution_time,
                completed_at=datetime.utcnow().isoformat()
            )

    async def _handle_fraud_detection(self, task: AgentTask) -> TaskResult:
        """Handle fraud detection task."""
        start_time = datetime.utcnow()

        try:
            print(f"[{self.config.agent_id}] Processing fraud detection: {task.task_id}")

            transaction_id = task.payload.get("transaction_id")
            amount = task.payload.get("amount")

            print(f"   Transaction: {transaction_id}")
            print(f"   Amount: ${amount}")

            # Simulate fraud check
            await asyncio.sleep(1.5)

            # Check for suspicious patterns (simulated)
            is_fraudulent = amount > 10000  # Simple rule

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            if is_fraudulent:
                # Report danger through pheromone
                print(f"[{self.config.agent_id}] ⚠️  FRAUD DETECTED!")

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.config.agent_id,
                success=True,
                result={
                    "transaction_id": transaction_id,
                    "is_fraudulent": is_fraudulent,
                    "risk_score": 0.85 if is_fraudulent else 0.12
                },
                error=None,
                execution_time_ms=execution_time,
                completed_at=datetime.utcnow().isoformat()
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.config.agent_id,
                success=False,
                result=None,
                error=str(e),
                execution_time_ms=execution_time,
                completed_at=datetime.utcnow().isoformat()
            )

    async def _handle_integration_build(self, task: AgentTask) -> TaskResult:
        """Handle integration build task (delegated to meta-agent)."""
        start_time = datetime.utcnow()

        try:
            print(f"[{self.config.agent_id}] Processing integration build: {task.task_id}")

            api_url = task.payload.get("api_url")
            api_description = task.payload.get("description")

            print(f"   API: {api_url}")
            print(f"   Description: {api_description}")

            # Simulate meta-agent building integration
            await asyncio.sleep(3)

            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.config.agent_id,
                success=True,
                result={
                    "api_url": api_url,
                    "tools_created": 5,
                    "mcp_server_path": f"mcp/servers/{api_url.split('//')[1].split('.')[0]}_mcp"
                },
                error=None,
                execution_time_ms=execution_time,
                completed_at=datetime.utcnow().isoformat()
            )

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000

            return TaskResult(
                task_id=task.task_id,
                agent_id=self.config.agent_id,
                success=False,
                result=None,
                error=str(e),
                execution_time_ms=execution_time,
                completed_at=datetime.utcnow().isoformat()
            )


async def main():
    """Run Service Bus task queue example."""
    print("=== Azure Service Bus Task Queue Example ===\n")

    # 1. Setup task queue client
    print("1. Connecting to Azure Service Bus...")
    task_queue = create_task_queue_client(
        service_bus_namespace="ants-production",  # Replace with your namespace
        queue_name="ants-tasks",
        use_managed_identity=True,
        max_concurrent_tasks=5
    )

    await task_queue.connect()
    print("   ✓ Connected to Service Bus\n")

    # 2. Setup pheromone client (optional, for coordination)
    print("2. Connecting to pheromone system...")
    pheromone_client = create_pheromone_client(
        event_hub_namespace="ants-production",
        event_hub_name="ants-pheromones",
        use_managed_identity=True
    )

    await pheromone_client.connect()
    print("   ✓ Connected to Event Hub\n")

    # 3. Create and start agents
    print("3. Starting task processing agents...")

    # Initialize dependencies (simulated)
    db_client = None
    memory = None
    llm_client = None

    agents = []
    for i in range(3):
        config = AgentConfig(
            agent_id=f"task_agent_{i}",
            agent_type="task.processor",
            tenant_id="acme_corp",
            capabilities=["reconciliation", "fraud_detection", "integration_build"]
        )

        agent = TaskProcessingAgent(config, memory, llm_client, task_queue)
        await agent.start()
        agents.append(agent)

        print(f"   ✓ Started task_agent_{i}")

    print()

    # 4. Submit tasks to queue
    print("4. Submitting tasks to Service Bus queue...\n")

    # 4a. High-priority reconciliation tasks
    print("   Priority: CRITICAL (reconciliation)")
    for i in range(2):
        task_id = await task_queue.submit_task(
            task_type=TaskType.RECONCILIATION.value,
            tenant_id="acme_corp",
            required_capabilities=["reconciliation"],
            payload={
                "account": f"account_{i}",
                "date_range": "2025-12-22"
            },
            priority=TaskPriority.CRITICAL.value
        )
        print(f"      ✓ Submitted {task_id}")

    # 4b. Fraud detection tasks
    print("\n   Priority: HIGH (fraud detection)")
    for i in range(3):
        task_id = await task_queue.submit_task(
            task_type=TaskType.FRAUD_DETECTION.value,
            tenant_id="acme_corp",
            required_capabilities=["fraud_detection"],
            payload={
                "transaction_id": f"txn_{i}",
                "amount": 5000 + (i * 3000)  # Last one triggers fraud
            },
            priority=TaskPriority.HIGH.value
        )
        print(f"      ✓ Submitted {task_id}")

    # 4c. Integration build tasks
    print("\n   Priority: NORMAL (integration build)")
    task_id = await task_queue.submit_task(
        task_type=TaskType.INTEGRATION_BUILD.value,
        tenant_id="acme_corp",
        required_capabilities=["integration_build"],
        payload={
            "api_url": "https://api.salesforce.com",
            "description": "Salesforce CRM integration"
        },
        priority=TaskPriority.NORMAL.value
    )
    print(f"      ✓ Submitted {task_id}")

    # 4d. Scheduled task (delayed execution)
    print("\n   Priority: NORMAL (scheduled for 10 seconds from now)")
    scheduled_time = datetime.utcnow() + timedelta(seconds=10)
    task_id = await task_queue.submit_task(
        task_type=TaskType.RECONCILIATION.value,
        tenant_id="acme_corp",
        required_capabilities=["reconciliation"],
        payload={
            "account": "account_scheduled",
            "date_range": "2025-12-22"
        },
        priority=TaskPriority.NORMAL.value,
        scheduled_for=scheduled_time
    )
    print(f"      ✓ Submitted {task_id} (scheduled)")

    print()

    # 5. Wait for tasks to process
    print("5. Agents processing tasks from queue...\n")
    await asyncio.sleep(15)  # Give time for all tasks including scheduled

    print()

    # 6. Check queue metrics
    print("6. Queue metrics:")
    metrics = await task_queue.get_queue_metrics()

    print(f"   Queue name: {metrics['queue_name']}")
    print(f"   Processing: {metrics['processing']}")
    print(f"   Max concurrent: {metrics['max_concurrent_tasks']}")
    print(f"   Registered handlers: {metrics['registered_handlers']}")

    print()

    # 7. Demonstrate dead-letter queue
    print("7. Checking dead-letter queue...")
    dead_letters = await task_queue.get_dead_letter_messages(max_count=10)

    if dead_letters:
        print(f"   Found {len(dead_letters)} dead-letter messages")
        for task in dead_letters:
            print(f"      - {task.task_id} ({task.task_type})")
    else:
        print("   No dead-letter messages (all tasks processed successfully)")

    print()

    # 8. Cleanup
    print("8. Shutting down...")

    await task_queue.stop_processing()
    print("   ✓ Task processing stopped")

    await task_queue.close()
    print("   ✓ Service Bus connection closed")

    await pheromone_client.close()
    print("   ✓ Pheromone client closed")

    print("\n=== Example Complete ===")
    print("\nKey Takeaways:")
    print("✓ Service Bus provides guaranteed task delivery")
    print("✓ Priority-based processing (CRITICAL → HIGH → NORMAL → LOW)")
    print("✓ Dead-letter queue captures failed tasks")
    print("✓ Scheduled delivery for delayed execution")
    print("✓ Concurrent processing with semaphore-based throttling")
    print("✓ Automatic retry with abandon/complete semantics")
    print("✓ Integration with pheromone swarm coordination")


if __name__ == "__main__":
    asyncio.run(main())
