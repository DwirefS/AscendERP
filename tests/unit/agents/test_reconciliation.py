"""
Unit tests for Reconciliation Agent.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agents.finance.reconciliation import ReconciliationAgent
from src.core.agent.base import AgentConfig, AgentContext


@pytest.fixture
def agent():
    """Create reconciliation agent for testing."""
    config = AgentConfig(
        agent_id="test-recon-agent",
        name="Test Reconciliation Agent",
        tools=["query_erp", "query_bank"],
        max_iterations=5,
        timeout_seconds=60
    )
    return ReconciliationAgent(config)


@pytest.fixture
def context():
    """Create test context."""
    return AgentContext(
        trace_id="trace-test-001",
        tenant_id="tenant-test"
    )


class TestReconciliationAgentPerceive:
    """Tests for perceive method."""

    @pytest.mark.asyncio
    async def test_perceive_standard_request(self, agent, context):
        """Test perception of standard reconciliation request."""
        input_data = {
            "type": "standard",
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "accounts": ["acc-001"],
            "tolerance": 0.01
        }

        perception = await agent.perceive(input_data, context)

        assert perception["request_type"] == "standard"
        assert perception["period_start"] == "2024-01-01"
        assert perception["period_end"] == "2024-01-31"
        assert perception["accounts"] == ["acc-001"]
        assert perception["tolerance_threshold"] == 0.01

    @pytest.mark.asyncio
    async def test_perceive_with_defaults(self, agent, context):
        """Test perception uses default values."""
        input_data = {}

        perception = await agent.perceive(input_data, context)

        assert perception["request_type"] == "standard"
        assert perception["accounts"] == []
        assert perception["tolerance_threshold"] == 0.01
        assert perception["urgency"] == "normal"


class TestReconciliationAgentRetrieve:
    """Tests for retrieve method."""

    @pytest.mark.asyncio
    async def test_retrieve_without_memory(self, agent, context):
        """Test retrieve when memory is not available."""
        perception = {
            "accounts": ["acc-001"]
        }

        retrieved = await agent.retrieve(perception, context)

        assert retrieved == {}

    @pytest.mark.asyncio
    async def test_retrieve_with_memory(self, agent, context, mock_memory_substrate):
        """Test retrieve uses memory substrate."""
        agent.memory = mock_memory_substrate
        perception = {
            "accounts": ["acc-001"]
        }

        mock_memory_substrate.retrieve_procedural.return_value = [
            MagicMock(content={"pattern": "test"})
        ]
        mock_memory_substrate.retrieve_semantic.return_value = [
            MagicMock(content="rule 1")
        ]

        retrieved = await agent.retrieve(perception, context)

        assert "past_patterns" in retrieved
        assert "reconciliation_rules" in retrieved


class TestReconciliationAgentReason:
    """Tests for reason method."""

    @pytest.mark.asyncio
    async def test_reason_without_llm(self, agent, context):
        """Test reasoning without LLM uses fallback logic."""
        perception = {
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "accounts": ["acc-001"],
            "tolerance_threshold": 0.01
        }
        retrieved_context = {}

        result = await agent.reason(perception, retrieved_context, context)

        assert "action" in result
        assert result["action"]["type"] == "reconcile"
        assert len(result["action"]["steps"]) > 0
        assert result["confidence"] == 0.75

    @pytest.mark.asyncio
    async def test_reason_with_llm(self, agent, context, mock_llm_client):
        """Test reasoning with LLM."""
        agent.llm = mock_llm_client
        perception = {
            "period_start": "2024-01-01",
            "period_end": "2024-01-31",
            "accounts": ["acc-001"],
            "tolerance_threshold": 0.01
        }
        retrieved_context = {}

        mock_llm_client.generate.return_value = {
            "steps": [{"name": "llm_step"}],
            "matching_criteria": {"key": "value"},
            "confidence": 0.9,
            "reasoning": "LLM reasoning"
        }

        result = await agent.reason(perception, retrieved_context, context)

        assert result["action"]["type"] == "reconcile"
        mock_llm_client.generate.assert_called_once()


class TestReconciliationAgentExecute:
    """Tests for execute method."""

    @pytest.mark.asyncio
    async def test_execute_reconciliation_steps(self, agent, context):
        """Test execution of reconciliation steps."""
        action = {
            "type": "reconcile",
            "steps": [
                {"name": "fetch_erp_data", "params": {}},
                {"name": "fetch_bank_data", "params": {}},
                {"name": "match_transactions", "params": {"tolerance": 0.01}},
                {"name": "identify_discrepancies", "params": {}},
                {"name": "generate_report", "params": {}}
            ]
        }

        result = await agent.execute(action, context)

        assert "matched_transactions" in result
        assert "discrepancies" in result
        assert "summary" in result
        assert result["summary"]["generated"] == True


class TestReconciliationAgentVerify:
    """Tests for verify method."""

    @pytest.mark.asyncio
    async def test_verify_complete_result(self, agent, context):
        """Test verification of complete result."""
        result = {
            "matched_transactions": [{"id": "1"}, {"id": "2"}],
            "discrepancies": [],
            "summary": {"generated": True}
        }

        verification = await agent.verify(result, context)

        assert verification["complete"] == True
        assert verification["quality_score"] == 1.0
        assert verification["metrics"]["matched_count"] == 2
        assert verification["metrics"]["discrepancy_count"] == 0

    @pytest.mark.asyncio
    async def test_verify_with_discrepancies(self, agent, context):
        """Test verification with discrepancies."""
        result = {
            "matched_transactions": [{"id": "1"}],
            "discrepancies": [{"id": "2"}],
            "summary": {"generated": True}
        }

        verification = await agent.verify(result, context)

        assert verification["quality_score"] == 0.8
        assert verification["metrics"]["discrepancy_count"] == 1


class TestReconciliationAgentLearn:
    """Tests for learn method."""

    @pytest.mark.asyncio
    async def test_learn_stores_successful_pattern(self, agent, context, mock_memory_substrate):
        """Test learning stores successful patterns."""
        agent.memory = mock_memory_substrate

        input_data = {
            "type": "standard",
            "accounts": ["acc-001"]
        }
        actions_taken = [
            {
                "action": {"type": "reconcile"},
                "result": {
                    "matched_transactions": [{"id": "1"}, {"id": "2"}],
                    "discrepancies": []
                }
            }
        ]

        await agent.learn(input_data, actions_taken, context)

        # Should store both procedural and episodic
        mock_memory_substrate.store_procedural.assert_called_once()
        mock_memory_substrate.store_episodic.assert_called_once()

    @pytest.mark.asyncio
    async def test_learn_without_memory(self, agent, context):
        """Test learning without memory is a no-op."""
        input_data = {}
        actions_taken = []

        # Should not raise
        await agent.learn(input_data, actions_taken, context)
