"""
Example: Pheromone-Based Swarm Coordination.

Demonstrates how agents use Azure Event Hub pheromones to coordinate work,
share discoveries, and optimize resource allocation.
"""
import asyncio
from datetime import datetime

from src.core.swarm import (
    create_pheromone_client,
    create_pheromone_orchestrator,
    PheromoneType,
    PheromoneStrength
)
from src.core.agent.base import BaseAgent, AgentConfig, ExecutionContext
from src.core.memory.substrate import MemorySubstrate
from src.core.memory.database import DatabaseClient
from src.core.inference.llm_client import LLMClient


class FinanceReconciliationAgent(BaseAgent):
    """Example finance agent that uses pheromone coordination."""

    async def run(self, context: ExecutionContext):
        """Execute reconciliation workflow with pheromone coordination."""
        agent_id = self.config.agent_id

        print(f"[{agent_id}] Starting reconciliation workflow...")

        # 1. Detect available work through task pheromones
        tasks = await orchestrator.detect_work(
            agent_id=agent_id,
            capabilities=self.config.capabilities
        )

        if not tasks:
            print(f"[{agent_id}] No tasks detected, depositing idle pheromone")
            await orchestrator.update_load(agent_id, 0.0)
            return

        # 2. Claim highest priority task (strongest pheromone)
        task = tasks[0]
        claimed = await orchestrator.claim_task(agent_id, task.task_id)

        if not claimed:
            print(f"[{agent_id}] Task already claimed by another agent")
            return

        print(f"[{agent_id}] Claimed task: {task.task_id} (strength: {task.pheromone_strength:.2f})")

        # 3. Update load
        await orchestrator.update_load(agent_id, 0.5)

        try:
            # 4. Check if we have required integration (e.g., Stripe)
            if not hasattr(self, 'stripe_client'):
                print(f"[{agent_id}] Missing Stripe integration, requesting capability...")

                # Request capability through pheromone
                await orchestrator.request_capability(
                    agent_id=agent_id,
                    capability_description="Query payment transactions from Stripe",
                    api_url="https://api.stripe.com/v1/",
                    priority="critical"
                )

                # MetaAgentOrchestrator detects capability pheromone and builds integration
                # For this example, we'll simulate waiting
                await asyncio.sleep(2)
                print(f"[{agent_id}] Stripe integration ready (simulated)")

            # 5. Execute reconciliation
            print(f"[{agent_id}] Reconciling payments...")
            await asyncio.sleep(1)  # Simulate work

            # 6. Complete task successfully
            await orchestrator.complete_task(
                agent_id=agent_id,
                task_id=task.task_id,
                success=True,
                result={"discrepancies_found": 0, "amount_reconciled": "$45,230.50"}
            )

            print(f"[{agent_id}] Task completed successfully! Depositing success pheromone.")

            # 7. Update load
            await orchestrator.update_load(agent_id, 0.0)

        except Exception as e:
            # Report danger through pheromone
            await orchestrator.report_danger(
                agent_id=agent_id,
                danger_type="reconciliation_error",
                location=f"finance.reconciliation.{task.task_id}",
                details={"error": str(e)}
            )

            await orchestrator.complete_task(
                agent_id=agent_id,
                task_id=task.task_id,
                success=False,
                result={"error": str(e)}
            )

            print(f"[{agent_id}] Task failed! Depositing danger pheromone.")


async def main():
    """Run pheromone swarm coordination example."""
    print("=== Pheromone-Based Swarm Coordination Example ===\n")

    # 1. Setup pheromone client (Azure Event Hub)
    print("1. Connecting to Azure Event Hub...")
    pheromone_client = create_pheromone_client(
        event_hub_namespace="ants-production",  # Replace with your namespace
        event_hub_name="ants-pheromones",
        use_managed_identity=True  # Uses Azure managed identity in production
    )

    await pheromone_client.connect()
    print("   ✓ Connected to Event Hub\n")

    # 2. Create swarm orchestrator
    print("2. Starting swarm orchestrator...")
    global orchestrator
    orchestrator = create_pheromone_orchestrator(
        pheromone_client=pheromone_client,
        tenant_id="acme_corp"
    )

    await orchestrator.start()
    print("   ✓ Swarm orchestrator started\n")

    # 3. Create and register agents
    print("3. Registering agents in swarm...")

    # Initialize dependencies (simulated for example)
    db_client = None  # In production: DatabaseClient(...)
    memory = None     # In production: MemorySubstrate(db_client)
    llm_client = None # In production: LLMClient(...)

    agents = []
    for i in range(3):
        config = AgentConfig(
            agent_id=f"finance_agent_{i}",
            agent_type="finance.reconciliation",
            tenant_id="acme_corp",
            capabilities=["reconciliation", "fraud_detection", "payment_processing"]
        )

        agent = FinanceReconciliationAgent(config, memory, llm_client)
        await orchestrator.register_agent(agent)
        agents.append(agent)

        print(f"   ✓ Registered finance_agent_{i}")

    print()

    # 4. Submit tasks to swarm marketplace
    print("4. Submitting tasks to swarm marketplace...")

    tasks = []
    for i in range(5):
        task_id = await orchestrator.submit_task(
            task_type="payment_reconciliation",
            required_capabilities=["reconciliation", "payment_processing"],
            payload={
                "date_range": "2025-12-22",
                "accounts": [f"account_{i}"]
            },
            priority=7 + (i % 3)  # Varying priorities 7-9
        )
        tasks.append(task_id)
        print(f"   ✓ Submitted task {i+1}: {task_id} (priority: {7 + (i % 3)})")

    print()

    # 5. Agents detect and execute tasks through pheromones
    print("5. Agents detecting work through pheromones...\n")

    # Run agents concurrently
    await asyncio.gather(*[agent.run(ExecutionContext(
        request_id=f"req_{i}",
        tenant_id="acme_corp",
        input_data={}
    )) for i, agent in enumerate(agents)])

    print()

    # 6. Check swarm status
    print("6. Swarm status after execution:")
    status = await orchestrator.get_swarm_status()

    print(f"   Active agents: {status['active_agents']}")
    print(f"   Average load: {status['average_load']:.2f}")
    print(f"   Pending tasks: {status['pending_tasks']}")
    print(f"   Claimed tasks: {status['claimed_tasks']}")
    print(f"   Pheromone landscape:")
    print(f"      Total active trails: {status['pheromone_landscape']['total_active_trails']}")
    print(f"      By type: {status['pheromone_landscape']['trails_by_type']}")

    print()

    # 7. Demonstrate capability request
    print("7. Demonstrating capability request pheromone...")

    await orchestrator.request_capability(
        agent_id="finance_agent_0",
        capability_description="Query invoice data from QuickBooks",
        api_url="https://developer.intuit.com/...",
        priority="high"
    )

    print("   ✓ Capability pheromone deposited")
    print("   → MetaAgentOrchestrator will detect and fulfill request")

    print()

    # 8. Check pheromone metrics
    print("8. Final pheromone landscape metrics:")
    metrics = await pheromone_client.get_swarm_metrics()

    print(f"   Total trails: {metrics['total_active_trails']}")
    print(f"   Trails by type: {metrics['trails_by_type']}")
    print(f"   Strength by type: {metrics.get('strength_by_type', {})}")
    print(f"   Oldest trail age: {metrics['oldest_trail_age_seconds']:.0f} seconds")

    print()

    # 9. Cleanup
    print("9. Shutting down swarm...")
    await orchestrator.stop()
    print("   ✓ Swarm orchestrator stopped")

    print("\n=== Example Complete ===")
    print("\nKey Takeaways:")
    print("✓ Agents discovered work through task pheromones")
    print("✓ Highest priority tasks (strongest pheromones) were claimed first")
    print("✓ Success pheromones reinforced working patterns")
    print("✓ Capability pheromones signaled integration needs")
    print("✓ Load balancing pheromones distributed work evenly")
    print("✓ All coordination happened through Azure Event Hub")


if __name__ == "__main__":
    asyncio.run(main())
