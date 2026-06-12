"""
Integration tests for the ANTS Agent Framework.

Tests the real interfaces of:
- src/core/agent/registry.py        (AgentRegistry)
- src/core/memory/database.py       (DatabaseClient against live PostgreSQL + pgvector)
- src/agents/finance/reconciliation.py (ReconciliationAgent full PRREEL run)
- services/agent_orchestrator/orchestrator.py (SwarmOrchestrator local behavior)
"""
import asyncio
import json
import uuid

import asyncpg
import pytest

from src.core.agent.base import (
    AgentConfig,
    AgentContext,
    AgentResult,
    AgentState,
    BaseAgent,
)
from src.core.agent.registry import AgentRegistry, AgentMetadata
from src.core.memory.database import DatabaseClient, DatabaseConfig
from src.agents.finance.reconciliation import ReconciliationAgent
from services.agent_orchestrator.orchestrator import (
    PheromoneType,
    SwarmOrchestrator,
)

EMBEDDING_DIM = 1024  # memory.semantic uses vector(1024) (NV-EmbedQA-E5-v5)


def make_embedding(index: int = 0) -> list:
    """Build a 1024-dimensional unit basis vector for pgvector tests."""
    embedding = [0.0] * EMBEDDING_DIM
    embedding[index] = 1.0
    return embedding


class EchoAgent(BaseAgent):
    """Minimal concrete agent used for registry and orchestrator tests."""

    async def perceive(self, input_data, context):
        return {"input": input_data}

    async def retrieve(self, perception, context):
        return {}

    async def reason(self, perception, retrieved_context, context):
        return {
            "action": {"type": "echo", "payload": perception["input"]},
            "confidence": 1.0,
        }

    async def execute(self, action, context):
        return {"echo": action.get("payload")}

    async def verify(self, result, context):
        return {"complete": True}

    async def learn(self, input_data, actions_taken, context):
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_config() -> DatabaseConfig:
    """Connection settings for the live test database."""
    return DatabaseConfig(
        host="localhost",
        port=5432,
        database="ants_test",
        username="test_user",
        password="test_pass",
    )


@pytest.fixture(scope="session")
def database_available(db_config) -> bool:
    """Ping the database once per session; DB tests skip when unreachable."""
    async def _ping():
        conn = await asyncpg.connect(db_config.connection_string, timeout=5)
        await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_ping())
        return True
    except Exception:
        return False
    finally:
        loop.close()


@pytest.fixture
async def db_client(db_config, database_available):
    """Connected DatabaseClient with schemas initialized."""
    if not database_available:
        pytest.skip("PostgreSQL test database is unreachable")

    client = DatabaseClient(db_config)
    await client.connect()
    await client.initialize_schemas()

    yield client

    await client.disconnect()


@pytest.fixture
def registry() -> AgentRegistry:
    """Fresh, isolated agent registry."""
    return AgentRegistry()


@pytest.fixture
def agent_context() -> AgentContext:
    return AgentContext(
        trace_id=f"trace-{uuid.uuid4().hex[:12]}",
        tenant_id="test-tenant",
        user_id="test-user",
    )


@pytest.fixture
async def orchestrator():
    orch = SwarmOrchestrator()

    yield orch

    if orch.swarm_active or orch._background_tasks:
        await orch.stop_swarm()


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

class TestAgentRegistry:
    """Tests for the real AgentRegistry API."""

    def test_register_and_list_agents(self, registry):
        registry.register(
            "test.echo",
            EchoAgent,
            {
                "name": "Echo Agent",
                "description": "Echoes input back for diagnostics",
                "category": "testing",
                "capabilities": ["echo", "diagnostics"],
            },
        )

        agents = registry.list_agents()
        assert len(agents) == 1
        assert isinstance(agents[0], AgentMetadata)
        assert agents[0].agent_type == "test.echo"
        assert agents[0].name == "Echo Agent"
        assert agents[0].agent_class is EchoAgent

    def test_get_metadata_and_defaults(self, registry):
        registry.register("test.minimal", EchoAgent, {})

        metadata = registry.get_metadata("test.minimal")
        assert metadata is not None
        assert metadata.name == "test.minimal"  # falls back to agent_type
        assert metadata.version == "1.0.0"
        assert metadata.category == "general"
        assert metadata.capabilities == []
        assert isinstance(metadata.config_template, AgentConfig)

        assert registry.get_metadata("does.not.exist") is None

    def test_list_agents_filtered_by_category(self, registry):
        registry.register("test.echo", EchoAgent, {"category": "testing"})
        registry.register("finance.recon", ReconciliationAgent, {"category": "finance"})

        finance_agents = registry.list_agents(category="finance")
        assert [a.agent_type for a in finance_agents] == ["finance.recon"]

        assert registry.get_categories() == ["finance", "testing"]

    def test_create_agent(self, registry):
        registry.register("test.echo", EchoAgent, {"name": "Echo Agent"})

        agent = registry.create_agent("test.echo")
        assert isinstance(agent, EchoAgent)

        custom_config = AgentConfig(name="Custom Echo")
        custom_agent = registry.create_agent("test.echo", config=custom_config)
        assert custom_agent.config.name == "Custom Echo"

    def test_create_agent_unknown_type_raises(self, registry):
        with pytest.raises(ValueError, match="Unknown agent type"):
            registry.create_agent("not.registered")

    def test_search_agents(self, registry):
        registry.register(
            "finance.recon",
            ReconciliationAgent,
            {"name": "Reconciliation Agent", "description": "Matches transactions"},
        )
        registry.register(
            "test.echo",
            EchoAgent,
            {"name": "Echo Agent", "description": "Echoes input back"},
        )

        by_name = registry.search_agents("reconciliation")
        assert [a.agent_type for a in by_name] == ["finance.recon"]

        by_description = registry.search_agents("echoes input")
        assert [a.agent_type for a in by_description] == ["test.echo"]

        by_type = registry.search_agents("finance")
        assert [a.agent_type for a in by_type] == ["finance.recon"]

        assert registry.search_agents("no-such-agent") == []

    def test_instance_registration_lifecycle(self, registry):
        registry.register("test.echo", EchoAgent, {})
        agent = registry.create_agent("test.echo")
        agent_id = agent.config.agent_id

        assert registry.get_agent(agent_id) is None

        registry.register_instance(agent_id, agent)
        assert registry.get_agent(agent_id) is agent

        registry.unregister_instance(agent_id)
        assert registry.get_agent(agent_id) is None

        # Unregistering twice is a no-op
        registry.unregister_instance(agent_id)


# ---------------------------------------------------------------------------
# Database client (live PostgreSQL + pgvector)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestDatabaseClient:
    """Round-trip tests against the live memory database."""

    async def test_connect_and_initialize_schemas(self, db_client):
        assert await db_client.fetchval("SELECT 1") == 1

        for table in [
            "memory.episodic",
            "memory.semantic",
            "memory.procedural",
            "ants.agents",
            "ants.executions",
            "audit.receipts",
        ]:
            assert await db_client.fetchval("SELECT to_regclass($1)", table) is not None, (
                f"expected table {table} to exist"
            )

        # Semantic embeddings are 1024-dimensional pgvector columns
        dimension = await db_client.fetchval(
            """
            SELECT atttypmod FROM pg_attribute
            WHERE attrelid = 'memory.semantic'::regclass AND attname = 'embedding'
            """
        )
        assert dimension == EMBEDDING_DIM

    async def test_episodic_round_trip(self, db_client):
        tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
        entry_id = str(uuid.uuid4())

        try:
            returned_id = await db_client.insert_episodic(
                entry_id=entry_id,
                tenant_id=tenant_id,
                agent_id="agent-episodic",
                content={"event": "reconciliation_run", "status": "ok"},
                metadata={"source": "integration-test"},
            )
            assert str(returned_id) == entry_id

            rows = await db_client.query_episodic(
                tenant_id=tenant_id,
                agent_id="agent-episodic",
                limit=10,
            )
            assert len(rows) == 1
            row = rows[0]
            assert str(row["id"]) == entry_id
            assert row["tenant_id"] == tenant_id
            assert row["agent_id"] == "agent-episodic"

            content = row["content"]
            if isinstance(content, str):
                content = json.loads(content)
            assert content == {"event": "reconciliation_run", "status": "ok"}
        finally:
            await db_client.execute(
                "DELETE FROM memory.episodic WHERE tenant_id = $1", tenant_id
            )

    async def test_episodic_query_filters_by_tenant(self, db_client):
        tenant_a = f"tenant-{uuid.uuid4().hex[:8]}"
        tenant_b = f"tenant-{uuid.uuid4().hex[:8]}"

        try:
            await db_client.insert_episodic(
                str(uuid.uuid4()), tenant_a, "agent-x", {"n": 1}, {}
            )
            await db_client.insert_episodic(
                str(uuid.uuid4()), tenant_b, "agent-x", {"n": 2}, {}
            )

            rows_a = await db_client.query_episodic(tenant_id=tenant_a)
            assert len(rows_a) == 1
            assert rows_a[0]["tenant_id"] == tenant_a
        finally:
            await db_client.execute(
                "DELETE FROM memory.episodic WHERE tenant_id = ANY($1::text[])",
                [tenant_a, tenant_b],
            )

    async def test_semantic_insert_and_vector_search(self, db_client):
        tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
        embedding = make_embedding(0)

        try:
            await db_client.insert_semantic(
                entry_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                agent_id="agent-semantic",
                content="Invoices must be matched within tolerance",
                embedding=embedding,
                metadata={"topic": "reconciliation"},
            )

            results = await db_client.vector_search(
                embedding=embedding,
                tenant_id=tenant_id,
                limit=5,
                threshold=0.7,
            )
            assert len(results) == 1
            assert results[0]["content"] == "Invoices must be matched within tolerance"
            assert results[0]["similarity"] == pytest.approx(1.0, abs=1e-6)
        finally:
            await db_client.execute(
                "DELETE FROM memory.semantic WHERE tenant_id = $1", tenant_id
            )

    async def test_vector_search_respects_similarity_threshold(self, db_client):
        tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"

        try:
            await db_client.insert_semantic(
                str(uuid.uuid4()), tenant_id, "agent-semantic",
                "similar document", make_embedding(0), {},
            )
            await db_client.insert_semantic(
                str(uuid.uuid4()), tenant_id, "agent-semantic",
                "orthogonal document", make_embedding(1), {},
            )

            # Querying with the first basis vector: the orthogonal document has
            # cosine similarity 0 and must be excluded by the 0.7 threshold.
            results = await db_client.vector_search(
                embedding=make_embedding(0),
                tenant_id=tenant_id,
                limit=10,
                threshold=0.7,
            )
            assert [r["content"] for r in results] == ["similar document"]
        finally:
            await db_client.execute(
                "DELETE FROM memory.semantic WHERE tenant_id = $1", tenant_id
            )

    async def test_procedural_round_trip_and_update(self, db_client):
        tenant_id = f"tenant-{uuid.uuid4().hex[:8]}"
        entry_id = str(uuid.uuid4())

        try:
            await db_client.insert_procedural(
                entry_id=entry_id,
                tenant_id=tenant_id,
                agent_id="agent-procedural",
                pattern={"steps": ["fetch", "match", "report"]},
                success_rate=0.8,
                metadata={"source": "integration-test"},
            )

            rows = await db_client.query_procedural(
                tenant_id=tenant_id,
                agent_id="agent-procedural",
                min_success_rate=0.5,
            )
            assert len(rows) == 1
            assert rows[0]["success_rate"] == pytest.approx(0.8)
            assert rows[0]["execution_count"] == 1

            await db_client.update_procedural_success(entry_id, 0.9)

            rows = await db_client.query_procedural(
                tenant_id=tenant_id,
                agent_id="agent-procedural",
                min_success_rate=0.85,
            )
            assert len(rows) == 1
            assert rows[0]["success_rate"] == pytest.approx(0.9)
            assert rows[0]["execution_count"] == 2

            # Threshold above the stored rate excludes the entry
            rows = await db_client.query_procedural(
                tenant_id=tenant_id,
                agent_id="agent-procedural",
                min_success_rate=0.95,
            )
            assert rows == []
        finally:
            await db_client.execute(
                "DELETE FROM memory.procedural WHERE tenant_id = $1", tenant_id
            )


# ---------------------------------------------------------------------------
# Reconciliation agent (full PRREEL loop, deterministic fallback)
# ---------------------------------------------------------------------------

class TestReconciliationAgent:
    """Full agent.run() without memory/LLM (deterministic fallback path)."""

    async def test_full_run_succeeds_without_memory_or_llm(self, agent_context):
        agent = ReconciliationAgent()
        await agent.initialize(memory=None, policy_engine=None, llm=None)
        assert agent.state == AgentState.READY

        result = await agent.run(
            input_data={
                "type": "standard",
                "period_start": "2026-01-01",
                "period_end": "2026-01-31",
                "accounts": ["1000", "2000"],
                "tolerance": 0.05,
            },
            context=agent_context,
        )

        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.error is None
        assert result.trace_id == agent_context.trace_id
        assert result.latency_ms >= 0
        assert result.confidence == pytest.approx(0.75)  # fallback confidence
        assert agent.state == AgentState.READY

    async def test_full_run_produces_reconciliation_report(self, agent_context):
        agent = ReconciliationAgent()

        result = await agent.run(
            input_data={"accounts": ["4000"], "tolerance": 0.01},
            context=agent_context,
        )

        assert result.success is True
        assert len(result.actions_taken) == 1
        action_record = result.actions_taken[0]
        assert action_record["action"]["type"] == "reconcile"
        assert action_record["policy_decision"] == {"allowed": True}

        output = result.output
        assert output["summary"]["generated"] is True
        assert output["summary"]["reconciliation_status"] == "complete"
        assert output["matched_transactions"] == []
        assert output["discrepancies"] == []

    async def test_perceive_applies_defaults(self, agent_context):
        agent = ReconciliationAgent()

        perception = await agent.perceive({"accounts": ["A"]}, agent_context)

        assert perception["request_type"] == "standard"
        assert perception["accounts"] == ["A"]
        assert perception["tolerance_threshold"] == 0.01
        assert perception["source_systems"] == ["erp", "bank"]
        assert perception["urgency"] == "normal"


# ---------------------------------------------------------------------------
# Swarm orchestrator (local, in-process behavior)
# ---------------------------------------------------------------------------

class TestSwarmOrchestrator:
    """Tests for SwarmOrchestrator local coordination primitives."""

    async def test_start_and_stop_swarm(self, orchestrator):
        assert orchestrator.swarm_active is False

        await orchestrator.start_swarm()
        assert orchestrator.swarm_active is True
        assert len(orchestrator._background_tasks) == 4

        await orchestrator.stop_swarm()
        assert orchestrator.swarm_active is False
        assert all(task.done() for task in orchestrator._background_tasks)

    async def test_register_and_unregister_agent(self, orchestrator):
        await orchestrator.register_agent("agent-1", "test.echo", ["echo"])

        state = orchestrator.agent_states["agent-1"]
        assert state.agent_type == "test.echo"
        assert state.status == "idle"
        assert state.load == 0.0
        assert state.capabilities == ["echo"]

        await orchestrator.unregister_agent("agent-1")
        assert "agent-1" not in orchestrator.agent_states

    async def test_submit_task_queues_task_and_emits_pheromone(self, orchestrator):
        task_id = await orchestrator.submit_task(
            task_type="reconcile",
            input_data={"accounts": ["1000"]},
            priority=8,
        )

        task = orchestrator.task_queue[task_id]
        assert task.type == "reconcile"
        assert task.priority == 8
        assert task.status == "pending"
        assert task.assigned_agent is None

        task_signals = [p for p in orchestrator.pheromones if p.location == task_id]
        assert len(task_signals) == 1
        assert task_signals[0].metadata["task_type"] == "reconcile"
        assert 0.0 < task_signals[0].strength <= 1.0

    async def test_emit_and_sense_pheromones_sorted_by_strength(self, orchestrator):
        await orchestrator.emit_pheromone(
            type=PheromoneType.EXPERTISE,
            strength=0.5,
            location="loc-weak",
            emitter="agent-a",
        )
        await orchestrator.emit_pheromone(
            type=PheromoneType.EXPERTISE,
            strength=0.9,
            location="loc-strong",
            emitter="agent-b",
            domain="finance",
        )

        signals = orchestrator.sense_pheromones("agent-c")
        assert [s.location for s in signals] == ["loc-strong", "loc-weak"]
        assert signals[0].emitter_agent == "agent-b"
        assert signals[0].metadata == {"domain": "finance"}

    async def test_sense_pheromones_filters_by_type(self, orchestrator):
        await orchestrator.emit_pheromone(
            type=PheromoneType.THREAT_DETECTED,
            strength=0.8,
            location="loc-threat",
        )
        await orchestrator.emit_pheromone(
            type=PheromoneType.RESOURCE_AVAILABLE,
            strength=0.8,
            location="loc-resource",
        )

        threats = orchestrator.sense_pheromones(
            "agent-x", pheromone_types=[PheromoneType.THREAT_DETECTED]
        )
        assert [s.location for s in threats] == ["loc-threat"]

    async def test_recruit_agents_filters_capability_and_success_rate(self, orchestrator):
        await orchestrator.register_agent("agent-good", "test.echo", ["echo"])
        await orchestrator.register_agent("agent-bad", "test.echo", ["echo"])
        await orchestrator.register_agent("agent-other", "test.echo", ["other"])
        orchestrator.agent_states["agent-bad"].success_rate = 0.5  # below cutoff

        recruits = await orchestrator.recruit_agents(count=10, capability="echo")
        assert recruits == ["agent-good"]

        recruits = await orchestrator.recruit_agents(count=10)
        assert set(recruits) == {"agent-good", "agent-other"}

    async def test_get_swarm_status(self, orchestrator):
        await orchestrator.register_agent("agent-1", "test.echo", ["echo"])
        await orchestrator.register_agent("agent-2", "test.echo", ["echo"])
        await orchestrator.submit_task("reconcile", {})

        status = await orchestrator.get_swarm_status()

        assert status["swarm_active"] is False
        assert status["total_agents"] == 2
        assert status["agents_by_type"]["test.echo"]["total"] == 2
        assert status["agents_by_type"]["test.echo"]["idle"] == 2
        assert status["agents_by_type"]["test.echo"]["busy"] == 0
        assert status["pending_tasks"] == 1
        assert status["running_tasks"] == 0
        assert status["completed_tasks"] == 0
        assert status["active_pheromones"] >= 1

    async def test_assign_task_executes_with_registered_agent(self, orchestrator):
        # Use an isolated registry so the global one is not polluted
        registry = AgentRegistry()
        registry.register(
            "test.echo", EchoAgent, {"name": "Echo Agent", "capabilities": ["echo"]}
        )
        orchestrator.registry = registry

        await orchestrator.register_agent("echo-1", "test.echo", ["echo"])
        task_id = await orchestrator.submit_task(
            "echo", {"payload": 42, "tenant_id": "test-tenant"}, priority=7
        )

        assigned = await orchestrator.assign_task_to_agent(task_id, "echo-1")
        assert assigned is True

        # Task execution is scheduled on the running loop; wait for completion
        for _ in range(500):
            if task_id in orchestrator.completed_tasks:
                break
            await asyncio.sleep(0.01)

        task = orchestrator.completed_tasks.get(task_id)
        assert task is not None, "task did not complete in time"
        assert task.status == "complete"
        assert isinstance(task.result, AgentResult)
        assert task.result.success is True
        assert task_id not in orchestrator.task_queue

        state = orchestrator.agent_states["echo-1"]
        assert state.status == "idle"
        assert state.current_task is None

    async def test_assign_task_to_unknown_agent_or_task_fails(self, orchestrator):
        await orchestrator.register_agent("agent-1", "test.echo", ["echo"])
        task_id = await orchestrator.submit_task("echo", {})

        assert await orchestrator.assign_task_to_agent("missing-task", "agent-1") is False
        assert await orchestrator.assign_task_to_agent(task_id, "missing-agent") is False
        assert orchestrator.task_queue[task_id].status == "pending"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
