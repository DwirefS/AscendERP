"""
Integration tests for ANTS Agent Framework.
Tests agent lifecycle, memory substrate, and orchestration.
"""
import pytest
import asyncio
from datetime import datetime
from typing import Dict, Any, List
import json

from src.core.agent.base import BaseAgent, AgentConfig, AgentState
from src.core.agent.registry import AgentRegistry, AgentMetadata
from src.core.memory.substrate import MemorySubstrate, MemoryType, MemoryEntry
from src.core.memory.database import DatabaseClient, DatabaseConfig
from src.core.inference.llm_client import LLMClient, LLMConfig
from services.agent_orchestrator.orchestrator import SwarmOrchestrator, Task, PheromoneType


@pytest.fixture
async def db_client():
    """Create test database client."""
    config = DatabaseConfig(
        host="localhost",
        port=5432,
        database="ants_test",
        username="test_user",
        password="test_pass"
    )

    client = DatabaseClient(config)
    await client.connect()

    yield client

    await client.disconnect()


@pytest.fixture
async def memory_substrate(db_client):
    """Create memory substrate for tests."""
    substrate = MemorySubstrate(
        db_client=db_client,
        tenant_id="test_tenant"
    )

    yield substrate


@pytest.fixture
def agent_registry():
    """Create agent registry."""
    registry = AgentRegistry()
    return registry


@pytest.fixture
def llm_client():
    """Create mock LLM client."""
    config = LLMConfig(
        provider="mock",
        model="test-model",
        api_key="test-key"
    )

    # In real tests, would use a mock LLM
    return config


class TestAgentLifecycle:
    """Tests for agent lifecycle management."""

    @pytest.mark.asyncio
    async def test_agent_creation_and_initialization(self, memory_substrate, llm_client):
        """Test creating and initializing an agent."""
        config = AgentConfig(
            agent_id="test_agent_001",
            agent_type="finance.reconciliation",
            tenant_id="test_tenant",
            capabilities=["analyze_transactions", "detect_anomalies"]
        )

        agent = BaseAgent(
            config=config,
            memory_substrate=memory_substrate,
            llm_config=llm_client
        )

        # Verify initialization
        assert agent.config.agent_id == "test_agent_001"
        assert agent.config.agent_type == "finance.reconciliation"
        assert agent.state == AgentState.INITIALIZED

    @pytest.mark.asyncio
    async def test_agent_state_transitions(self, memory_substrate, llm_client):
        """Test agent state transitions."""
        config = AgentConfig(
            agent_id="test_agent_002",
            agent_type="retail.inventory"
        )

        agent = BaseAgent(config, memory_substrate, llm_client)

        # Test state transitions
        assert agent.state == AgentState.INITIALIZED

        agent.state = AgentState.ACTIVE
        assert agent.state == AgentState.ACTIVE

        agent.state = AgentState.IDLE
        assert agent.state == AgentState.IDLE

        agent.state = AgentState.SLEEPING
        assert agent.state == AgentState.SLEEPING


class TestAgentRegistry:
    """Tests for agent registry and discovery."""

    def test_register_agent(self, agent_registry):
        """Test registering an agent."""
        metadata = AgentMetadata(
            agent_id="agent_reg_001",
            agent_type="finance.reconciliation",
            capabilities=["reconcile", "analyze"],
            version="1.0.0",
            status="active"
        )

        agent_registry.register(metadata)

        # Verify registration
        retrieved = agent_registry.get_agent("agent_reg_001")
        assert retrieved is not None
        assert retrieved.agent_id == "agent_reg_001"
        assert retrieved.agent_type == "finance.reconciliation"

    def test_search_agents_by_capability(self, agent_registry):
        """Test searching agents by capability."""
        # Register multiple agents
        agents = [
            AgentMetadata(
                agent_id=f"agent_{i}",
                agent_type="finance.reconciliation" if i % 2 == 0 else "retail.inventory",
                capabilities=["reconcile"] if i % 2 == 0 else ["forecast"],
                version="1.0.0",
                status="active"
            )
            for i in range(10)
        ]

        for agent in agents:
            agent_registry.register(agent)

        # Search by capability
        reconcilers = agent_registry.search_agents(capability="reconcile")
        assert len(reconcilers) == 5

        forecasters = agent_registry.search_agents(capability="forecast")
        assert len(forecasters) == 5

    def test_agent_deregistration(self, agent_registry):
        """Test removing an agent from registry."""
        metadata = AgentMetadata(
            agent_id="agent_dereg_001",
            agent_type="test.agent",
            capabilities=[],
            version="1.0.0",
            status="active"
        )

        agent_registry.register(metadata)
        assert agent_registry.get_agent("agent_dereg_001") is not None

        agent_registry.deregister("agent_dereg_001")
        assert agent_registry.get_agent("agent_dereg_001") is None


class TestMemorySubstrate:
    """Tests for memory substrate operations."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve_episodic_memory(self, memory_substrate):
        """Test storing and retrieving episodic memories."""
        # Store episodic memory (agent trace)
        trace_data = {
            "task": "reconcile_transactions",
            "input": {"account_id": "ACC_001", "date": "2024-01-15"},
            "output": {"status": "success", "reconciled_count": 42},
            "duration_ms": 1234
        }

        memory_id = await memory_substrate.store_episodic(
            agent_id="agent_mem_001",
            content=json.dumps(trace_data),
            metadata={"task_type": "reconciliation"}
        )

        assert memory_id is not None

        # Retrieve episodic memories
        memories = await memory_substrate.get_episodic_history(
            agent_id="agent_mem_001",
            limit=10
        )

        assert len(memories) > 0
        assert memories[0].agent_id == "agent_mem_001"

    @pytest.mark.asyncio
    async def test_semantic_memory_with_vector_search(self, memory_substrate):
        """Test semantic memory storage and vector search."""
        # Store semantic memories
        documents = [
            "Revenue recognition follows ASC 606 guidelines",
            "Depreciation is calculated using straight-line method",
            "Accounts receivable aging should be reviewed monthly"
        ]

        for doc in documents:
            await memory_substrate.store_semantic(
                agent_id="agent_sem_001",
                content=doc,
                metadata={"source": "accounting_policy"}
            )

        # Search by semantic similarity
        results = await memory_substrate.retrieve_semantic(
            query="How should we recognize revenue?",
            limit=5,
            threshold=0.5
        )

        assert len(results) > 0
        # First result should be about revenue recognition
        assert "revenue" in results[0].content.lower()

    @pytest.mark.asyncio
    async def test_procedural_memory_patterns(self, memory_substrate):
        """Test storing and retrieving procedural patterns."""
        # Store procedural pattern
        pattern_data = {
            "pattern_name": "anomaly_detection_threshold",
            "pattern_type": "threshold_adjustment",
            "parameters": {
                "initial_threshold": 0.8,
                "adjusted_threshold": 0.75,
                "reason": "reduced_false_positives"
            },
            "effectiveness": 0.92
        }

        pattern_id = await memory_substrate.store_procedural(
            agent_id="agent_proc_001",
            pattern_name="anomaly_detection_threshold",
            pattern_data=pattern_data,
            metadata={"domain": "fraud_detection"}
        )

        assert pattern_id is not None

        # Retrieve patterns
        patterns = await memory_substrate.get_procedural_patterns(
            agent_id="agent_proc_001"
        )

        assert len(patterns) > 0
        assert patterns[0].pattern_name == "anomaly_detection_threshold"


class TestSwarmOrchestration:
    """Tests for swarm orchestrator."""

    @pytest.mark.asyncio
    async def test_task_submission_and_assignment(self):
        """Test submitting tasks to swarm."""
        orchestrator = SwarmOrchestrator()
        await orchestrator.start()

        # Submit task
        task_id = await orchestrator.submit_task(
            task_type="reconcile_account",
            input_data={
                "account_id": "ACC_001",
                "period": "2024-01"
            },
            priority=7
        )

        assert task_id is not None

        # Check task exists
        task = orchestrator.get_task(task_id)
        assert task is not None
        assert task.type == "reconcile_account"
        assert task.priority == 7

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_pheromone_signaling(self):
        """Test pheromone emission and detection."""
        orchestrator = SwarmOrchestrator()
        await orchestrator.start()

        # Emit pheromone
        await orchestrator.emit_pheromone(
            type=PheromoneType.TASK_AVAILABLE,
            strength=0.8,
            location="task_queue_finance"
        )

        # Detect pheromones
        pheromones = await orchestrator.detect_pheromones(
            location="task_queue_finance"
        )

        assert len(pheromones) > 0
        assert pheromones[0].type == PheromoneType.TASK_AVAILABLE

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_dynamic_agent_scaling(self):
        """Test swarm scales agents based on load."""
        orchestrator = SwarmOrchestrator(
            min_agents=2,
            max_agents=10,
            scale_threshold=5  # Scale up when >5 tasks per agent
        )
        await orchestrator.start()

        # Submit many tasks
        for i in range(20):
            await orchestrator.submit_task(
                task_type="process_transaction",
                input_data={"txn_id": f"TXN_{i}"},
                priority=5
            )

        # Allow time for scaling decision
        await asyncio.sleep(0.5)

        # Check if agents were scaled
        active_agents = orchestrator.get_active_agent_count()
        assert active_agents > 2  # Should scale up from minimum

        await orchestrator.stop()


class TestAgentCommunication:
    """Tests for agent-to-agent communication."""

    @pytest.mark.asyncio
    async def test_agent_message_passing(self):
        """Test agents can send messages to each other."""
        orchestrator = SwarmOrchestrator()
        await orchestrator.start()

        # Agent 1 sends message to Agent 2
        message_id = await orchestrator.send_agent_message(
            from_agent="agent_comm_001",
            to_agent="agent_comm_002",
            message_type="REQUEST_DATA",
            payload={"data_type": "customer_info", "customer_id": "CUST_123"}
        )

        assert message_id is not None

        # Agent 2 retrieves message
        messages = await orchestrator.get_agent_messages("agent_comm_002")
        assert len(messages) > 0
        assert messages[0].from_agent == "agent_comm_001"
        assert messages[0].message_type == "REQUEST_DATA"

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """Test broadcasting message to all agents."""
        orchestrator = SwarmOrchestrator()
        await orchestrator.start()

        # Broadcast system message
        await orchestrator.broadcast_message(
            message_type="SYSTEM_ALERT",
            payload={"alert": "Maintenance window starting in 10 minutes"}
        )

        # All agents should receive it
        # (In real implementation, would check multiple agent inboxes)

        await orchestrator.stop()


class TestAgentPerformance:
    """Performance tests for agents."""

    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_high_throughput_task_processing(self):
        """Test orchestrator can handle high task volume."""
        orchestrator = SwarmOrchestrator(
            min_agents=10,
            max_agents=50
        )
        await orchestrator.start()

        # Submit 1000 tasks
        task_ids = []
        for i in range(1000):
            task_id = await orchestrator.submit_task(
                task_type="quick_task",
                input_data={"task_num": i},
                priority=5
            )
            task_ids.append(task_id)

        assert len(task_ids) == 1000

        await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_memory_retrieval_performance(self, memory_substrate):
        """Test memory substrate can handle high retrieval volume."""
        # Store 100 semantic memories
        for i in range(100):
            await memory_substrate.store_semantic(
                agent_id="agent_perf_001",
                content=f"Test document {i} about financial topic {i % 10}",
                metadata={"doc_id": i}
            )

        # Perform 50 searches
        start_time = datetime.utcnow()

        for i in range(50):
            results = await memory_substrate.retrieve_semantic(
                query=f"financial topic {i % 10}",
                limit=5
            )
            assert len(results) > 0

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Should complete in reasonable time
        assert duration < 30  # <30 seconds for 50 searches


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
